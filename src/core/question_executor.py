"""Question executor module for benchmark_llm project.

This module provides functionality to execute individual questions,
including answer randomization, API request building, response handling,
and database storage.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from src.api.client import MessageBuilder, OpenRouterClient
from src.core.randomizer import AnswerRandomizer
from src.db.models import Error, Question, Response
from src.db.repository import ErrorRepository, ResponseRepository
from src.db.schema import DatabaseManager
from src.utils.answer_schema import ANSWER_SCHEMA

logger = logging.getLogger(__name__)


class QuestionExecutor:
    """Executes individual questions for benchmark testing.

    This class handles the complete lifecycle of executing a single question:
    - Applying answer randomization
    - Building API requests
    - Sending requests and capturing responses
    - Parsing and storing responses
    - Error handling and logging

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        api_client: OpenRouterClient instance for API calls.
        randomizer: AnswerRandomizer instance for answer shuffling.
        run_id: ID of the current benchmark run.
        model_id: ID of the model being tested.
        iteration_number: Iteration number (1-based).

    Example:
        >>> executor = QuestionExecutor(
        ...     db_manager, api_client, randomizer,
        ...     run_id="run-123", model_id="gpt-4", iteration_number=1
        ... )
        >>> result = await executor.execute_question(question)
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        api_client: OpenRouterClient,
        randomizer: AnswerRandomizer,
        run_id: str,
        model_id: str,
        iteration_number: int,
        model_kwargs: Optional[dict[str, Any]] = None,
        use_structured_outputs: bool = False,
        reasoning_config: Optional[dict[str, Any]] = None,
        enable_vision: bool = False,
        settings: Optional[Any] = None,
    ) -> None:
        """Initialize the QuestionExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
            api_client: OpenRouterClient instance for API calls.
            randomizer: AnswerRandomizer instance for answer shuffling.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_number: Iteration number (1-based).
            model_kwargs: Optional dict with model generation parameters
                (max_tokens, temperature, top_p, top_k, repeat_penalty).
                If None, uses model defaults.
            use_structured_outputs: Whether to use structured outputs (JSON schema)
                for model responses. Falls back to traditional method if not supported.
            reasoning_config: Optional reasoning configuration (OpenRouter standard).
            enable_vision: Whether to send images with questions (default: False).

        Example:
            >>> executor = QuestionExecutor(
            ...     db_manager, api_client, randomizer,
            ...     run_id="run-123", model_id="gpt-4", iteration_number=1,
            ...     model_kwargs={"max_tokens": 16384, "temperature": 0.0},
            ...     use_structured_outputs=True,
            ...     reasoning_config={"effort": "high"},
            ...     enable_vision=True
            ... )
        """
        self.db_manager = db_manager
        self._api_client = api_client
        self._randomizer = randomizer
        self._run_id = run_id
        self._model_id = model_id
        self._iteration_number = iteration_number
        self._model_kwargs = model_kwargs or {}
        self._use_structured_outputs = use_structured_outputs
        self._reasoning_config = reasoning_config
        self._enable_vision = enable_vision
        self._settings = settings
        self._response_repository = ResponseRepository(db_manager)
        self._error_repository = ErrorRepository(db_manager)
        logger.debug(
            f"QuestionExecutor initialized for run={run_id}, "
            f"model={model_id}, iteration={self._iteration_number}, "
            f"use_structured_outputs={self._use_structured_outputs}, "
            f"enable_vision={self._enable_vision}, "
            f"model_kwargs={self._model_kwargs}, "
            f"reasoning_config={self._reasoning_config}"
        )

    async def execute_question(self, question: Question) -> dict[str, Any]:
        """Execute a single question.

        This method performs the complete execution flow:
        1. Apply answer randomization
        2. Build API request
        3. Send request and capture response
        4. Parse response and extract answer
        5. Store response in database
        6. Handle and log errors

        Args:
            question: Question object to execute.

        Returns:
            Dictionary containing execution results:
            - status: "success" or "error"
            - selected_answer: The answer selected by the model
            - correct_answer: The correct answer
            - is_correct: Whether the answer was correct
            - input_tokens: Number of input tokens used
            - output_tokens: Number of output tokens generated
            - latency_ms: Response time in milliseconds
            - error_type: Type of error if status is "error"
            - metadata: Additional metadata (e.g., used_structured_outputs)

        Raises:
            Exception: Any unexpected errors during execution.

        Example:
            >>> result = await executor.execute_question(question)
            >>> if result["status"] == "success":
            ...     print(f"Model answered: {result['selected_answer']}")
            ...     print(f"Correct: {result['is_correct']}")
        """
        start_time = time.time()
        result: dict[str, Any] = {
            "status": "pending",
            "question_id": question.question_id,
        }

        try:
            logger.debug(f"Executing question {question.question_id}")

            # Step 1: Apply answer randomization
            randomized_question = self._randomizer.randomize(question)
            logger.debug(
                f"Randomized question {question.question_id}: "
                f"correct answer changed from {question.correct_answer} "
                f"to {randomized_question.correct_answer}"
            )

            # Step 2: Build API request
            request_content = self._build_request_content(randomized_question)

            # Step 3: Send request and capture response
            # Try structured outputs if enabled, otherwise use traditional method
            used_structured_outputs = False
            parsed: dict[str, Any] = {}
            latency_ms = 0

            if self._use_structured_outputs:
                try:
                    # Try with structured outputs
                    latency_start = time.time()
                    api_response = await self._execute_with_structured_output(
                        request_content
                    )
                    latency_ms = int((time.time() - latency_start) * 1000)
                    parsed = self._parse_structured_response(
                        api_response, randomized_question
                    )
                    used_structured_outputs = True
                    logger.debug(
                        f"Question {question.question_id}: Used structured outputs"
                    )
                except Exception as e:
                    # Check if it's an unsupported error
                    if self._is_unsupported_error(e):
                        logger.info(
                            f"Model doesn't support structured outputs, falling back "
                            f"for question {question.question_id}"
                        )
                    else:
                        # Re-raise if it's a different error
                        raise

            # If not using structured outputs or fallback
            if not used_structured_outputs:
                latency_start = time.time()
                api_response = await self._execute_traditional(request_content)
                latency_ms = int((time.time() - latency_start) * 1000)
                parsed = self._parse_api_response(api_response, randomized_question)

            # Calculate total execution time
            total_latency_ms = int((time.time() - start_time) * 1000)

            # Extract reasoning details
            reasoning_details, reasoning_tokens = self._extract_reasoning_details(api_response)

            # Step 4: Store response in database (in test mode this goes to :memory:)
            logger.debug(f"Creating response: run_id={self._run_id}, question_id={randomized_question.question_id}, model_id={self._model_id}")
            response = self._create_response_object(
                question=randomized_question,
                parsed=parsed,
                api_response=api_response,
                latency_ms=total_latency_ms,
                reasoning_details=reasoning_details,
                reasoning_tokens=reasoning_tokens,
            )
            logger.debug(f"Response object created, saving to DB")
            self._response_repository.create(response)
            logger.info(f"Response saved successfully")

            # Populate result
            result.update(
                {
                    "status": "success",
                    "selected_answer": parsed["selected_answer"],
                    "correct_answer": randomized_question.correct_answer,
                    "is_correct": parsed["is_correct"],
                    "input_tokens": parsed["input_tokens"],
                    "output_tokens": parsed["output_tokens"],
                    "latency_ms": latency_ms,
                    "response_text": parsed["response_text"],
                    "metadata": {"used_structured_outputs": used_structured_outputs},
                }
            )

            logger.info(
                f"Question {question.question_id} completed: "
                f"selected={parsed['selected_answer']}, "
                f"correct={randomized_question.correct_answer}, "
                f"is_correct={parsed['is_correct']}, "
                f"latency={latency_ms}ms, "
                f"structured_outputs={used_structured_outputs}"
            )

        except httpx.HTTPStatusError as e:
            result = self._handle_http_error(e, question, start_time)
        except httpx.TimeoutException as e:
            result = self._handle_timeout_error(e, question, start_time)
        except httpx.RequestError as e:
            result = self._handle_request_error(e, question, start_time)
        except Exception as e:
            result = self._handle_general_error(e, question, start_time)

        return result

    def _build_request_content(self, question: Question) -> dict[str, Any]:
        """Build the API request content for a question.

        Args:
            question: Question object (possibly randomized).

        Returns:
            Dictionary with role and content for the API request.

        Example:
            >>> content = self._build_request_content(question)
            >>> print(content["content"])
            Question: What is...?
            Options:
            A. Option A
            B. Option B
            ...
        """
        # Parse options from JSON
        import json
        options = json.loads(question.options_json)
        options_text = "\n".join([f"{k}) {v}" for k, v in options.items()])

        # Build the prompt
        # Base instruction for text-only questions
        default_instruction = "Select the correct answer by providing only the letter (A, B, C, or D)."

        # Get custom prompt from settings or use default
        if question.has_image and self._enable_vision:
            default_with_image = "First, describe what you see in the image in detail. Then, " + default_instruction.lower()
            instruction = self._settings.prompt_with_image or default_with_image
        else:
            instruction = default_instruction

        # Parse options from JSON
        import json
        options = json.loads(question.options_json)
        options_text = "\n".join([f"{k}) {v}" for k, v in options.items()])

        prompt = f"""Question: {question.stem}

Options:
{options_text}

{instruction}"""

        # Check if question has an image and vision is enabled
        if question.has_image and question.image_path and self._enable_vision:
            from pathlib import Path

            image_path = Path(question.image_path)
            if image_path.exists():
                return MessageBuilder.build_multimodal_message(prompt, image_path)
            else:
                logger.warning(f"Image not found for question {question.question_id}: {image_path}")

        return MessageBuilder.build_user_message(prompt)

    async def _execute_with_structured_output(
        self, request_content: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute request with structured output format.

        Args:
            request_content: The request content dictionary.

        Returns:
            Raw API response dictionary.
        """
        # Build API request with response_format
        api_kwargs = {
            "model": self._model_id,
            "messages": [request_content],
            "response_format": ANSWER_SCHEMA,
        }
        # Add optional parameters only if configured
        if "max_tokens" in self._model_kwargs:
            api_kwargs["max_tokens"] = self._model_kwargs["max_tokens"]
        if "temperature" in self._model_kwargs:
            api_kwargs["temperature"] = self._model_kwargs["temperature"]
        if "top_p" in self._model_kwargs:
            api_kwargs["top_p"] = self._model_kwargs["top_p"]
        if "top_k" in self._model_kwargs:
            api_kwargs["top_k"] = self._model_kwargs["top_k"]
        if "repeat_penalty" in self._model_kwargs:
            api_kwargs["repeat_penalty"] = self._model_kwargs["repeat_penalty"]
        
        # Add reasoning config if provided
        if self._reasoning_config:
            api_kwargs["reasoning"] = self._reasoning_config

        return await self._api_client.chat_completion(**api_kwargs)

    async def _execute_traditional(
        self, request_content: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute request with traditional method (no structured output).

        Args:
            request_content: The request content dictionary.

        Returns:
            Raw API response dictionary.
        """
        # Build API request with model kwargs (only include non-None values)
        api_kwargs = {
            "model": self._model_id,
            "messages": [request_content],
        }
        # Add optional parameters only if configured
        if "max_tokens" in self._model_kwargs:
            api_kwargs["max_tokens"] = self._model_kwargs["max_tokens"]
        if "temperature" in self._model_kwargs:
            api_kwargs["temperature"] = self._model_kwargs["temperature"]
        if "top_p" in self._model_kwargs:
            api_kwargs["top_p"] = self._model_kwargs["top_p"]
        if "top_k" in self._model_kwargs:
            api_kwargs["top_k"] = self._model_kwargs["top_k"]
        if "repeat_penalty" in self._model_kwargs:
            api_kwargs["repeat_penalty"] = self._model_kwargs["repeat_penalty"]
        
        # Add reasoning config if provided
        if self._reasoning_config:
            api_kwargs["reasoning"] = self._reasoning_config

        return await self._api_client.chat_completion(**api_kwargs)

    def _parse_structured_response(
        self, api_response: dict[str, Any], question: Question
    ) -> dict[str, Any]:
        """Parse structured JSON response.

        Args:
            api_response: Raw API response dictionary.
            question: Question object (for answer validation).

        Returns:
            Dictionary containing parsed response data.
        """
        # Extract content
        choices = api_response.get("choices", [])
        content = ""
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

        # Parse JSON
        try:
            data = json.loads(content)
            selected_answer = data.get("answer", "").upper()
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse structured response: {e}")
            selected_answer = self._extract_answer_letter(content) or ""

        # Extract token usage
        usage = api_response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        cost = usage.get("cost")

        # Capture actual model from response
        actual_model = api_response.get("model", self._model_id)

        # Determine if answer is correct
        is_correct = selected_answer == question.correct_answer

        return {
            "selected_answer": selected_answer,
            "is_correct": is_correct,
            "response_text": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "actual_model": actual_model,
        }

    def _is_unsupported_error(self, error: Exception) -> bool:
        """Check if error indicates lack of structured output support.

        Args:
            error: The exception to check.

        Returns:
            True if the error indicates structured outputs are not supported.
        """
        error_str = str(error).lower()
        return any(
            keyword in error_str
            for keyword in [
                "structured",
                "response_format",
                "not supported",
                "unsupported",
            ]
        )

    def _parse_api_response(
        self, api_response: dict[str, Any], question: Question
    ) -> dict[str, Any]:
        """Parse the API response and extract the answer.

        Args:
            api_response: Raw API response dictionary.
            question: Question object (for answer validation).

        Returns:
            Dictionary containing parsed response data:
            - selected_answer: The letter selected by the model
            - is_correct: Whether the answer is correct
            - response_text: Full response text
            - input_tokens: Input token count
            - output_tokens: Output token count
            - actual_model: The actual model ID from the response
        """
        # Extract response text
        choices = api_response.get("choices", [])
        response_text = ""
        if choices:
            message = choices[0].get("message", {})
            response_text = message.get("content", "")

            # Handle reasoning models (e.g., Qwen with llama.cpp)
            # If content is empty but reasoning_content exists, use reasoning_content
            if not response_text or not response_text.strip():
                reasoning_content = message.get("reasoning_content", "")
                if reasoning_content:
                    response_text = reasoning_content

        # Extract token usage
        usage = api_response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
        cost = usage.get("cost")

        # Capture actual model from response for verification
        actual_model = api_response.get("model", self._model_id)
        if actual_model != self._model_id:
            logger.info(
                f"API response indicates different model: "
                f"requested={self._model_id}, actual={actual_model}"
            )

        # Parse selected answer from response text
        selected_answer = self._extract_answer_letter(response_text)

        # Determine if answer is correct
        is_correct = selected_answer == question.correct_answer

        return {
            "selected_answer": selected_answer,
            "is_correct": is_correct,
            "response_text": response_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "actual_model": actual_model,
        }

    def _extract_answer_letter(self, response_text: str) -> Optional[str]:
        """Extract the answer letter from response text.

        Uses regex patterns to find the most likely answer letter
        in the model's response.

        Args:
            response_text: Full text response from the model.

        Returns:
            The extracted answer letter (A, B, C, or D), or None if not found.

        Example:
            >>> letter = self._extract_answer_letter("The answer is **B**")
            >>> print(letter)
            B
        """
        # Common patterns for answer extraction
        patterns = [
            (r"\*\*([A-D])\*\*", True),  # **A**, **B**, etc. (has group)
            (r"\b([A-D])\b\s*:", True),  # A:, B:, etc. (has group)
            (r"answer\s*is\s*([A-D])", True),  # "answer is A" (has group)
            (r"correct\s*answer\s*is\s*([A-D])", True),  # "correct answer is A" (has group)
            (r"option\s*([A-D])", True),  # "option A" (has group)
            (r"^[A-D]\b", False),  # Line starting with A, B, C, or D (no group)
            (r"\b([A-D])\b", True),  # Any standalone letter A-D (has group)
        ]

        response_upper = response_text.upper()

        for pattern, has_group in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                if has_group:
                    letter = match.group(1).upper()
                else:
                    letter = match.group(0).upper()
                if letter in ("A", "B", "C", "D"):
                    logger.debug(f"Extracted answer '{letter}' using pattern: {pattern}")
                    return letter

        # Fallback: look for any A-D in the response
        for char in response_upper:
            if char in ("A", "B", "C", "D"):
                logger.debug(f"Extracted answer '{char}' as fallback")
                return char

        logger.warning(f"Could not extract answer letter from: {response_text[:100]}")
        return None

    def _extract_reasoning_details(
        self, api_response: dict[str, Any]
    ) -> tuple[Optional[str], Optional[int]]:
        """Extract reasoning details and tokens from API response.

        Args:
            api_response: Raw API response dictionary.

        Returns:
            Tuple of (reasoning_details_json, reasoning_tokens)
        """
        reasoning_details = None
        reasoning_tokens = None

        # Extract reasoning_details array from message
        message = api_response.get("choices", [{}])[0].get("message", {})

        # Get reasoning_details if present
        if "reasoning_details" in message:
            details = message["reasoning_details"]
            if details:
                reasoning_details = json.dumps(details)
                logger.debug(f"Extracted reasoning_details: {len(details)} items")

        # Extract reasoning tokens from usage
        # OpenRouter standard: usage.completion_tokens_details.reasoning_tokens
        # Some providers may use: usage.reasoning_tokens (flat)
        usage = api_response.get("usage", {})
        reasoning_tokens = None
        
        # Try nested format first (OpenRouter standard)
        completion_tokens_details = usage.get("completion_tokens_details", {})
        if completion_tokens_details and "reasoning_tokens" in completion_tokens_details:
            reasoning_tokens = completion_tokens_details["reasoning_tokens"]
        # Fallback to flat format (some providers)
        elif "reasoning_tokens" in usage:
            reasoning_tokens = usage["reasoning_tokens"]

        return reasoning_details, reasoning_tokens

    def _create_response_object(
        self,
        question: Question,
        parsed: dict[str, Any],
        api_response: dict[str, Any],
        latency_ms: int,
        reasoning_details: Optional[str] = None,
        reasoning_tokens: Optional[int] = None,
    ) -> Response:
        """Create a Response object for database storage.

        Args:
            question: Question object (possibly randomized).
            parsed: Parsed response data.
            api_response: Raw API response.
            latency_ms: Total latency in milliseconds.
            reasoning_details: Optional JSON string with reasoning details.
            reasoning_tokens: Optional number of reasoning tokens used.

        Returns:
            Response object ready for database storage.
        """
        import json

        return Response(
            run_id=self._run_id,
            question_id=question.question_id,
            model_id=self._model_id,
            iteration=self._iteration_number,
            selected_answer=parsed["selected_answer"],
            response_text=parsed["response_text"],
            is_correct=parsed["is_correct"],
            status="success",
            latency_ms=latency_ms,
            input_tokens=parsed["input_tokens"],
            output_tokens=parsed["output_tokens"],
            total_tokens=parsed.get("total_tokens"),
            cost=parsed.get("cost"),
            reasoning_tokens=reasoning_tokens,
            timestamp=datetime.now(),
        )

    def _handle_http_error(
        self, error: httpx.HTTPStatusError, question: Question, start_time: float
    ) -> dict[str, Any]:
        """Handle HTTP status errors.

        Args:
            error: The HTTP status error that occurred.
            question: Question being executed.
            start_time: Execution start time for latency calculation.

        Returns:
            Error result dictionary.
        """
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = f"HTTPError_{error.response.status_code}"
        error_message = str(error)

        logger.error(
            f"HTTP error for question {question.question_id}: "
            f"{error.response.status_code} - {error_message}"
        )

        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
        )

        return {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "latency_ms": latency_ms,
            "question_id": question.question_id,
        }

    def _handle_timeout_error(
        self, error: httpx.TimeoutException, question: Question, start_time: float
    ) -> dict[str, Any]:
        """Handle timeout errors.

        Args:
            error: The timeout error that occurred.
            question: Question being executed.
            start_time: Execution start time for latency calculation.

        Returns:
            Error result dictionary.
        """
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = "TimeoutError"
        error_message = str(error)

        logger.error(f"Timeout for question {question.question_id}: {error_message}")

        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
        )

        return {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "latency_ms": latency_ms,
            "question_id": question.question_id,
        }

    def _handle_request_error(
        self, error: httpx.RequestError, question: Question, start_time: float
    ) -> dict[str, Any]:
        """Handle general request errors.

        Args:
            error: The request error that occurred.
            question: Question being executed.
            start_time: Execution start time for latency calculation.

        Returns:
            Error result dictionary.
        """
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = "RequestError"
        error_message = str(error)

        logger.error(
            f"Request error for question {question.question_id}: {error_message}"
        )

        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
        )

        return {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "latency_ms": latency_ms,
            "question_id": question.question_id,
        }

    def _handle_general_error(
        self, error: Exception, question: Question, start_time: float
    ) -> dict[str, Any]:
        """Handle general/unexpected errors.

        Args:
            error: The exception that occurred.
            question: Question being executed.
            start_time: Execution start time for latency calculation.

        Returns:
            Error result dictionary.
        """
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = type(error).__name__
        error_message = str(error)

        logger.exception(
            f"Unexpected error for question {question.question_id}: {error_message}"
        )

        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            stack_trace=self._get_stack_trace(),
        )

        return {
            "status": "error",
            "error_type": error_type,
            "error_message": error_message,
            "latency_ms": latency_ms,
            "question_id": question.question_id,
        }

    def _store_error(
        self,
        question: Question,
        error_type: str,
        error_message: str,
        latency_ms: int,
        stack_trace: str = "",
    ) -> None:
        """Store an error in the database.

        Args:
            question: Question that caused the error.
            error_type: Type of error.
            error_message: Error message.
            latency_ms: Latency when error occurred.
            stack_trace: Optional stack trace.
        """
        # First create a response record for the error
        # Store response and error in database (skip in test mode)
        if self._settings is None or not self._settings.is_test_mode:
            response = Response(
                run_id=self._run_id,
                question_id=question.question_id,
                model_id=self._model_id,
                iteration=self._iteration_number,
                selected_answer=None,
                response_text="",
                is_correct=None,
                status="error",
                latency_ms=latency_ms,
                input_tokens=0,
                output_tokens=0,
                total_tokens=None,
                cost=None,
                timestamp=datetime.now(),
            )
            self._response_repository.create(response)

            # Then create the error record
            error = Error(
                run_id=self._run_id,
                question_id=question.question_id,
                model_id=self._model_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                timestamp=datetime.now(),
            )
            self._error_repository.create(error)

    def _get_stack_trace(self) -> str:
        """Get the current stack trace as a string.

        Returns:
            Stack trace string.
        """
        import traceback

        return traceback.format_exc()
