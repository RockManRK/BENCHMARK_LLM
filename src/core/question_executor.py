"""Question executor module for benchmark_llm project.

This module provides functionality to execute individual questions,
including answer randomization, API request building, response handling,
and database storage.
"""

import asyncio
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
        iteration_id: ID of the current iteration.

    Example:
        >>> executor = QuestionExecutor(
        ...     db_manager, api_client, randomizer,
        ...     run_id="run-123", model_id="gpt-4", iteration_id=1
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
        iteration_id: int,
    ) -> None:
        """Initialize the QuestionExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
            api_client: OpenRouterClient instance for API calls.
            randomizer: AnswerRandomizer instance for answer shuffling.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_id: ID of the current iteration.

        Example:
            >>> executor = QuestionExecutor(
            ...     db_manager, api_client, randomizer,
            ...     run_id="run-123", model_id="gpt-4", iteration_id=1
            ... )
        """
        self.db_manager = db_manager
        self._api_client = api_client
        self._randomizer = randomizer
        self._run_id = run_id
        self._model_id = model_id
        self._iteration_id = iteration_id
        self._response_repository = ResponseRepository(db_manager)
        self._error_repository = ErrorRepository(db_manager)
        logger.debug(
            f"QuestionExecutor initialized for run={run_id}, "
            f"model={model_id}, iteration={iteration_id}"
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
            - error_message: Error message if status is "error"

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
            latency_start = time.time()
            api_response = await self._api_client.chat_completion(
                model=self._model_id,
                messages=[request_content],
                max_tokens=100,
                temperature=0.0,
            )
            latency_ms = int((time.time() - latency_start) * 1000)

            # Step 4: Parse response
            parsed = self._parse_api_response(api_response, randomized_question)

            # Calculate total execution time
            total_latency_ms = int((time.time() - start_time) * 1000)

            # Step 5: Store response in database
            response = self._create_response_object(
                question=randomized_question,
                parsed=parsed,
                api_response=api_response,
                latency_ms=total_latency_ms,
            )
            self._response_repository.create(response)

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
                }
            )

            logger.info(
                f"Question {question.question_id} completed: "
                f"selected={parsed['selected_answer']}, "
                f"correct={randomized_question.correct_answer}, "
                f"is_correct={parsed['is_correct']}, "
                f"latency={latency_ms}ms"
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
        # Format options as a string
        options_text = "\n".join(
            f"{letter}. {text}" for letter, text in question.options.items()
        )

        # Build the prompt
        prompt = f"""Question: {question.question_text}

Options:
{options_text}

Select the correct answer by providing only the letter (A, B, C, or D)."""

        # Check if question has an image
        if question.has_image and question.image_path:
            from pathlib import Path

            image_path = Path(question.image_path)
            if image_path.exists():
                return MessageBuilder.build_multimodal_message(prompt, image_path)

        return MessageBuilder.build_user_message(prompt)

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

        Example:
            >>> parsed = self._parse_api_response(response, question)
            >>> print(f"Model selected: {parsed['selected_answer']}")
        """
        # Extract response text
        choices = api_response.get("choices", [])
        response_text = ""
        if choices:
            message = choices[0].get("message", {})
            response_text = message.get("content", "")

        # Extract token usage
        usage = api_response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

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
            r"\*\*([A-D])\*\*",  # **A**, **B**, etc.
            r"\b([A-D])\b\s*:",  # A:, B:, etc.
            r"answer\s*is\s*([A-D])",  # "answer is A"
            r"correct\s*answer\s*is\s*([A-D])",  # "correct answer is A"
            r"option\s*([A-D])",  # "option A"
            r"^[A-D]\b",  # Line starting with A, B, C, or D
            r"\b([A-D])\b",  # Any standalone letter A-D
        ]

        response_upper = response_text.upper()

        for pattern in patterns:
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                letter = match.group(1).upper()
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

    def _create_response_object(
        self,
        question: Question,
        parsed: dict[str, Any],
        api_response: dict[str, Any],
        latency_ms: int,
    ) -> Response:
        """Create a Response object for database storage.

        Args:
            question: Question object (possibly randomized).
            parsed: Parsed response data.
            api_response: Raw API response.
            latency_ms: Total latency in milliseconds.

        Returns:
            Response object ready for database storage.
        """
        import json

        return Response(
            iteration_id=self._iteration_id,
            question_id=question.question_id,
            model_id=self._model_id,
            run_id=self._run_id,
            question_text=question.question_text,
            options_json=json.dumps(question.options),
            options_randomized=self._randomizer.is_randomized(question),
            selected_answer=parsed["selected_answer"],
            correct_answer=question.correct_answer,
            is_correct=parsed["is_correct"],
            response_text=parsed["response_text"],
            input_tokens=parsed["input_tokens"],
            output_tokens=parsed["output_tokens"],
            latency_ms=latency_ms,
            timestamp=datetime.now(),
            status="success",
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
        response = Response(
            iteration_id=self._iteration_id,
            question_id=question.question_id,
            model_id=self._model_id,
            run_id=self._run_id,
            question_text=question.question_text,
            options_json="{}",
            options_randomized=False,
            selected_answer=None,
            correct_answer=question.correct_answer,
            is_correct=None,
            response_text="",
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
            timestamp=datetime.now(),
            status="error",
        )
        self._response_repository.create(response)

        # Then create the error record
        if response.response_id:
            error = Error(
                response_id=response.response_id,
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
