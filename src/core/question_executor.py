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
from src.api.error_handler import extract_error_from_raw, format_error_details, normalize_openrouter_error
from src.core.randomizer import AnswerRandomizer
from src.db.models import Error, Question, QuestionSnapshot, Response
from src.db.repository import ErrorRepository, QuestionSnapshotRepository, ResponseRepository
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
        randomizer: Optional[AnswerRandomizer],
        run_id: str,
        model_id: str,
        iteration_number: int,
        experiment_id: str,
        model_kwargs: Optional[dict[str, Any]] = None,
        use_structured_outputs: bool = False,
        reasoning_config: Optional[dict[str, Any]] = None,
        enable_vision: bool = False,
        settings: Optional[Any] = None,
        snapshot_repository: Optional[QuestionSnapshotRepository] = None,
    ) -> None:
        """Initialize the QuestionExecutor.

        Args:
            db_manager: DatabaseManager instance for database connections.
            api_client: OpenRouterClient instance for API calls.
            randomizer: AnswerRandomizer instance for answer shuffling, or None to disable randomization.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_number: Iteration number (1-based).
            experiment_id: ID of the experiment (ALWAYS required, never None).
            model_kwargs: Optional dict with model generation parameters
                (max_tokens, temperature, top_p, top_k, repeat_penalty).
                If None, uses model defaults.
            use_structured_outputs: Whether to use structured outputs (JSON schema)
                for model responses. Falls back to traditional method if not supported.
            reasoning_config: Optional reasoning configuration (OpenRouter standard).
            enable_vision: Whether to send images with questions (default: False).
            snapshot_repository: Optional QuestionSnapshotRepository for creating snapshots.

        Example:
            >>> executor = QuestionExecutor(
            ...     db_manager, api_client, randomizer,
            ...     run_id="run-123", model_id="gpt-4", iteration_number=1,
            ...     experiment_id="exp-001",
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
        self._experiment_id = experiment_id
        self._model_kwargs = model_kwargs or {}
        self._use_structured_outputs = use_structured_outputs
        self._reasoning_config = reasoning_config
        self._enable_vision = enable_vision
        self._settings = settings
        self._snapshot_repository = snapshot_repository
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
            - response_tokens: Number of response tokens generated
            - total_tokens: Total tokens (input + response, excludes reasoning)
            - reasoning_tokens: Number of reasoning tokens (if available)
            - effective_tokens: Total computational cost (input + response + reasoning)
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

            # Step 0: Create snapshot if repository is available
            # This ensures we have an immutable copy of the question for this experiment
            snapshot_id: Optional[int] = None
            if self._snapshot_repository is not None:
                # Build complete question JSON for snapshot
                question_json = json.dumps({
                    "id": question.question_id,
                    "stem": question.stem,
                    "options": json.loads(question.options_json),
                    "answer_key": question.correct_answer,
                    "has_image": question.has_image,
                    "image_path": question.image_path,
                })
                # Use the experiment_id passed to QuestionExecutor
                snapshot_id = self._snapshot_repository.create_if_not_exists(
                    experiment_id=self._experiment_id,
                    question_id=question.question_id,
                    question_json=question_json,
                )
                logger.debug(f"Snapshot ID {snapshot_id} for question {question.question_id} in experiment {self._experiment_id}")
                
                # Store snapshot_id as instance variable for error handling
                self._current_snapshot_id = snapshot_id

            # Step 1: Apply answer randomization (if enabled)
            if self._randomizer is not None:
                randomized_question = self._randomizer.randomize(question)
                logger.debug(
                    f"Randomized question {question.question_id}: "
                    f"correct answer changed from {question.correct_answer} "
                    f"to {randomized_question.correct_answer}"
                )
            else:
                # No randomization: use original question
                randomized_question = question
                logger.debug(f"Using original question {question.question_id} (no randomization)")

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

            # Extract token usage using consolidated method
            # This extracts: input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens, cost
            tokens = self._extract_token_usage(api_response)

            # Extract reasoning details (text) separately
            reasoning_details, _ = self._extract_reasoning_details(api_response)

            # Step 4: Store response in database (in test mode this goes to :memory:)
            logger.debug(f"Creating response: run_id={self._run_id}, snapshot_id={snapshot_id}, model_id={self._model_id}")
            response = self._create_response_object(
                question=randomized_question,
                parsed=parsed,
                api_response=api_response,
                latency_ms=total_latency_ms,
                snapshot_id=snapshot_id,
                reasoning_details=reasoning_details,
                tokens=tokens,  # Pass consolidated token data
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
                    "input_tokens": tokens["input_tokens"],
                    "response_tokens": tokens["response_tokens"],
                    "total_tokens": tokens["total_tokens"],
                    "reasoning_tokens": tokens["reasoning_tokens"],
                    "effective_tokens": tokens["effective_tokens"],
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
            What is...?
            A. Option A
            B. Option B
            ...
        """
        # Parse options from JSON
        import json
        options = json.loads(question.options_json)
        options_text = "\n".join([f"{k}) {v}" for k, v in options.items()])

        # Build the prompt
        # Default instruction for all questions (with or without images)
        default_instruction = "Select the correct answer by providing only the letter (A, B, C, or D)."

        # Use custom prompt from settings or default (NO distinction for images)
        instruction = self._settings.default_prompt or default_instruction

        prompt = f"""{question.stem}

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
            Raw API response dictionary. If debug is enabled, returns
            {"_debug": {...}, "response": {...}}.
        """
        # Build API request with response_format
        api_kwargs = {
            "model": self._model_id,
            "messages": [request_content],
            "response_format": ANSWER_SCHEMA,
            "stream": False,  # Disable streaming to ensure complete response
            "include_debug": self._settings.openrouter_debug_enabled if self._settings else False,
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
            Raw API response dictionary. If debug is enabled, returns
            {"_debug": {...}, "response": {...}}.
        """
        # Build API request with model kwargs (only include non-None values)
        api_kwargs = {
            "model": self._model_id,
            "messages": [request_content],
            "stream": False,  # Disable streaming to ensure complete response
            "include_debug": self._settings.openrouter_debug_enabled if self._settings else False,
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
            api_response: Raw API response dictionary. If debug is enabled,
                this will be {"_debug": {...}, "response": {...}}.
            question: Question object (for answer validation).

        Returns:
            Dictionary containing parsed response data.
        """
        # Handle debug wrapper format:
        # If debug enabled, response is in api_response['response']; otherwise, use api_response directly
        response_data = api_response.get("response", api_response)
        if "_debug" in api_response:
            logger.debug("Debug mode detected: extracting response from wrapper")

        # Extract content
        choices = response_data.get("choices", [])
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
            # Use new AnswerParser for fallback
            from src.core.answer_parser import AnswerParser
            parser = AnswerParser()
            parsed_answer = parser.parse(content)
            selected_answer = parsed_answer.answer or ""

        # Extract token usage using consolidated method
        tokens = self._extract_token_usage(api_response)

        # Capture actual model from response
        actual_model = response_data.get("model", self._model_id)

        # Extract finish_reason from API response
        finish_reason = None
        choices = response_data.get("choices", [])
        if choices:
            finish_reason = choices[0].get("finish_reason")

        # Determine if answer is correct
        is_correct = selected_answer == question.correct_answer

        return {
            "selected_answer": selected_answer,
            "is_correct": is_correct,
            "response_text": content,
            "input_tokens": tokens["input_tokens"],
            "response_tokens": tokens["response_tokens"],
            "total_tokens": tokens["total_tokens"],
            "reasoning_tokens": tokens["reasoning_tokens"],
            "effective_tokens": tokens["effective_tokens"],
            "cost": tokens["cost"],
            "actual_model": actual_model,
            "finish_reason": finish_reason,
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
            api_response: Raw API response dictionary. If debug is enabled,
                this will be {"_debug": {...}, "response": {...}}.
            question: Question object (for answer validation).

        Returns:
            Dictionary containing parsed response data:
            - selected_answer: The letter selected by the model
            - is_correct: Whether the answer is correct
            - response_text: Full response text
            - input_tokens: Input token count
            - response_tokens: Response token count
            - total_tokens: Total tokens (input + response, excludes reasoning)
            - reasoning_tokens: Reasoning token count (if available)
            - effective_tokens: Total computational cost
            - actual_model: The actual model ID from the response
            - finish_reason: The reason for response termination
            - parse_confidence: Confidence level from answer parsing
        """
        # Handle debug wrapper format:
        # If debug enabled, response is in api_response['response']; otherwise, use api_response directly
        response_data = api_response.get("response", api_response)
        if "_debug" in api_response:
            logger.debug("Debug mode detected: extracting response from wrapper")

        # Extract response text
        choices = response_data.get("choices", [])
        response_text = ""
        finish_reason = None

        if choices:
            message = choices[0].get("message", {})
            response_text = message.get("content", "")
            finish_reason = choices[0].get("finish_reason")

            # LOG FULL API RESPONSE FOR DEBUGGING
            logger.debug(f"FULL API RESPONSE: choices={choices}")
            logger.debug(f"Message content: {response_text[:500] if response_text else 'EMPTY'}...")

            # Handle reasoning models (e.g., Qwen with llama.cpp)
            # If content is empty but reasoning_content exists, use reasoning_content
            if not response_text or not response_text.strip():
                reasoning_content = message.get("reasoning_content", "")
                if reasoning_content:
                    logger.debug(f"Using reasoning_content: {reasoning_content[:200]}...")
                    response_text = reasoning_content

        # Extract token usage using consolidated method
        tokens = self._extract_token_usage(api_response)

        # Capture actual model from response for verification
        actual_model = response_data.get("model", self._model_id)
        if actual_model != self._model_id:
            logger.info(
                f"API response indicates different model: "
                f"requested={self._model_id}, actual={actual_model}"
            )

        # Parse selected answer from response text using the new AnswerParser
        from src.core.answer_parser import AnswerParser

        parser = AnswerParser()
        parsed_answer = parser.parse(response_text)
        selected_answer = parsed_answer.answer

        # Log parsing confidence for debugging
        logger.debug(
            f"Answer parsing for question {question.question_id}: "
            f"answer={selected_answer}, confidence={parsed_answer.confidence}, "
            f"raw_matches={parsed_answer.raw_matches}"
        )

        # Store parse confidence for manual review workflow
        parse_confidence = parsed_answer.confidence

        # Determine if answer is correct
        is_correct = selected_answer == question.correct_answer

        return {
            "selected_answer": selected_answer,
            "is_correct": is_correct,
            "response_text": response_text,
            "input_tokens": tokens["input_tokens"],
            "response_tokens": tokens["response_tokens"],
            "total_tokens": tokens["total_tokens"],
            "reasoning_tokens": tokens["reasoning_tokens"],
            "effective_tokens": tokens["effective_tokens"],
            "cost": tokens["cost"],
            "actual_model": actual_model,
            "finish_reason": finish_reason,
            "parse_confidence": parse_confidence,
        }

    # =========================================================================
    # TOKEN USAGE EXTRACTION
    # =========================================================================
    # Token calculation formulas (documented):
    # - total_tokens = input_tokens + response_tokens (excludes reasoning_tokens)
    # - effective_tokens = input_tokens + response_tokens + reasoning_tokens
    # - reasoning_tokens are a subtype of response_tokens, not additional
    # =========================================================================

    def _extract_token_usage(self, api_response: dict[str, Any]) -> dict[str, Any]:
        """Extract all token-related metrics from API response.

        This method consolidates token extraction logic from multiple locations
        into a single, maintainable function. It handles both debug and non-debug
        response formats.

        Token calculation formulas (documented):
        - total_tokens = input_tokens + response_tokens (excludes reasoning_tokens)
        - effective_tokens = input_tokens + response_tokens + reasoning_tokens
        - reasoning_tokens are a subtype of response_tokens, not additional

        Args:
            api_response: Raw API response dictionary. If debug is enabled,
                this will be {"_debug": {...}, "response": {...}}.

        Returns:
            Dictionary containing:
            - input_tokens: Number of tokens in the request (prompt_tokens)
            - response_tokens: Number of tokens in the response (completion_tokens)
            - total_tokens: input_tokens + response_tokens (excludes reasoning_tokens)
            - reasoning_tokens: Number of reasoning tokens used (if available)
            - effective_tokens: input_tokens + response_tokens + reasoning_tokens
            - cost: Cost in credits for this response

        Example:
            >>> tokens = self._extract_token_usage(api_response)
            >>> print(f"Input: {tokens['input_tokens']}, Response: {tokens['response_tokens']}")
            >>> print(f"Total: {tokens['total_tokens']}, Reasoning: {tokens['reasoning_tokens']}")
            >>> print(f"Effective: {tokens['effective_tokens']}, Cost: {tokens['cost']}")
        """
        # Handle debug wrapper: extract actual response from wrapper
        # Format when debug enabled: {"_debug": {...}, "response": {...}}
        # Format when debug disabled: {...} (direct response)
        response_data = api_response.get("response", api_response)
        if "_debug" in api_response:
            logger.debug("Debug mode detected in _extract_token_usage: extracting response from wrapper")

        # Extract usage from response
        usage = response_data.get("usage", {})

        # Extract basic token counts
        input_tokens = usage.get("prompt_tokens", 0)
        response_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + response_tokens)
        cost = usage.get("cost")

        # Extract reasoning tokens using nested search
        reasoning_tokens = self._extract_reasoning_tokens_from_usage(usage)

        # Calculate effective_tokens (total computational cost)
        # Formula: effective_tokens = input_tokens + response_tokens + reasoning_tokens
        effective_tokens = input_tokens + response_tokens + (reasoning_tokens or 0)

        # Log token usage with structured logging
        # Format: INFO - Token usage | model=xxx | question=xxx | input=xxx | response=xxx | reasoning=xxx | total=xxx | effective=xxx
        logger.info(
            "Token usage",
            extra={
                "model_id": self._model_id,
                "question_id": getattr(self, '_current_question_id', None),
                "input_tokens": input_tokens,
                "response_tokens": response_tokens,
                "reasoning_tokens": reasoning_tokens,
                "total_tokens": total_tokens,
                "effective_tokens": effective_tokens,
            }
        )

        return {
            "input_tokens": input_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "reasoning_tokens": reasoning_tokens,
            "effective_tokens": effective_tokens,
            "cost": cost,
        }

    def _extract_reasoning_tokens_from_usage(self, usage: dict[str, Any]) -> Optional[int]:
        """Extract reasoning_tokens from usage dictionary.

        Searches for reasoning_tokens in multiple locations:
        1. usage.completion_tokens_details.reasoning_tokens (OpenRouter standard)
        2. usage.reasoning_tokens (flat format)
        3. usage.extra.usage_reasoning_tokens (llama.cpp format)
        4. Recursive search in nested dictionaries

        Args:
            usage: Usage dictionary from API response.

        Returns:
            reasoning_tokens value if found, None otherwise.
        """
        reasoning_tokens = None

        # Try nested format first (OpenRouter standard)
        completion_tokens_details = usage.get("completion_tokens_details", {})
        if completion_tokens_details and "reasoning_tokens" in completion_tokens_details:
            reasoning_tokens = completion_tokens_details["reasoning_tokens"]
            logger.debug(f"Extracted reasoning_tokens from completion_tokens_details: {reasoning_tokens}")
        # Fallback to flat format (some providers)
        elif "reasoning_tokens" in usage:
            reasoning_tokens = usage["reasoning_tokens"]
            logger.debug(f"Extracted reasoning_tokens from usage (flat): {reasoning_tokens}")
        # Try llama.cpp format (nested in extra)
        elif "extra" in usage:
            extra = usage["extra"]
            if isinstance(extra, dict) and "usage_reasoning_tokens" in extra:
                reasoning_tokens = extra["usage_reasoning_tokens"]
                logger.debug(f"Extracted reasoning_tokens from llama.cpp format: {reasoning_tokens}")
        
        # Additional fallback: recursive search in nested dictionaries
        if reasoning_tokens is None:
            reasoning_tokens = self._find_reasoning_tokens_in_usage(usage)
            if reasoning_tokens is not None:
                logger.debug(f"Extracted reasoning_tokens from nested search: {reasoning_tokens}")

        if reasoning_tokens is None:
            logger.debug(f"No reasoning_tokens found in usage")
        else:
            logger.debug(f"reasoning_tokens extracted: {reasoning_tokens}")

        return reasoning_tokens

    def _find_reasoning_tokens_in_usage(self, usage: dict[str, Any], depth: int = 0) -> Optional[int]:
        """Recursively search for reasoning_tokens in usage dictionary.

        Args:
            usage: Usage dictionary to search.
            depth: Current recursion depth (for logging).

        Returns:
            reasoning_tokens value if found, None otherwise.
        """
        if not isinstance(usage, dict) or depth > 5:  # Limit recursion depth
            return None

        # Direct key check
        if "reasoning_tokens" in usage:
            return usage["reasoning_tokens"]

        # Search in nested dictionaries
        for key, value in usage.items():
            if isinstance(value, dict):
                result = self._find_reasoning_tokens_in_usage(value, depth + 1)
                if result is not None:
                    return result

        return None

    def _extract_reasoning_details(
        self, api_response: dict[str, Any]
    ) -> tuple[Optional[str], Optional[int]]:
        """Extract reasoning details (text) from API response.

        This method extracts the reasoning_details array from the message,
        which contains the model's reasoning process (chain-of-thought).

        Note: For reasoning_tokens extraction, use _extract_token_usage() instead.

        Args:
            api_response: Raw API response dictionary. If debug is enabled,
                this will be {"_debug": {...}, "response": {...}}.

        Returns:
            Tuple of (reasoning_details_json, reasoning_tokens)
            Note: reasoning_tokens is now extracted from _extract_token_usage()
        """
        # Handle debug wrapper: extract actual response from wrapper
        response_data = api_response.get("response", api_response)
        if "_debug" in api_response:
            logger.debug("Debug mode detected in _extract_reasoning_details: extracting response from wrapper")

        # Extract reasoning_details array from message
        message = response_data.get("choices", [{}])[0].get("message", {})

        # Get reasoning_details if present
        reasoning_details = None
        if "reasoning_details" in message:
            details = message["reasoning_details"]
            if details:
                reasoning_details = json.dumps(details)
                logger.debug(f"Extracted reasoning_details: {len(details)} items")

        # Note: reasoning_tokens is now extracted via _extract_token_usage()
        # This method returns None for reasoning_tokens to avoid duplication
        return reasoning_details, None

    def _create_response_object(
        self,
        question: Question,
        parsed: dict[str, Any],
        api_response: dict[str, Any],
        latency_ms: int,
        snapshot_id: Optional[int] = None,
        reasoning_details: Optional[str] = None,
        tokens: Optional[dict[str, Any]] = None,
    ) -> Response:
        """Create a Response object for database storage.

        Args:
            question: Question object (possibly randomized).
            parsed: Parsed response data.
            api_response: Raw API response.
            latency_ms: Total latency in milliseconds.
            snapshot_id: ID of the question snapshot (required).
            reasoning_details: Optional JSON string with reasoning details.
            tokens: Dictionary containing token metrics from _extract_token_usage().
                   Contains: input_tokens, response_tokens, total_tokens, 
                   reasoning_tokens, effective_tokens, cost.

        Returns:
            Response object ready for database storage.
        """
        import json

        if snapshot_id is None:
            logger.error("snapshot_id is required but was not provided")
            raise ValueError("snapshot_id is required for creating a response")

        # Use tokens from consolidated extraction, or fallback to parsed dict
        if tokens is None:
            # Fallback for backward compatibility
            tokens = {
                "input_tokens": parsed.get("input_tokens", 0),
                "response_tokens": parsed.get("response_tokens", parsed.get("output_tokens", 0)),
                "total_tokens": parsed.get("total_tokens"),
                "reasoning_tokens": parsed.get("reasoning_tokens"),
                "effective_tokens": parsed.get("effective_tokens"),
                "cost": parsed.get("cost"),
            }

        # Store with debug wrapper (if enabled):
        # - _debug.request_payload: What we sent to OpenRouter
        # - _debug.upstream_body: What OpenRouter sent to provider
        # - response: Actual model response (downstream consumers should use this)

        return Response(
            run_id=self._run_id,
            snapshot_id=snapshot_id,
            question_id=question.question_id,
            model_id=self._model_id,
            iteration=self._iteration_number,
            selected_answer=parsed["selected_answer"],
            response_text=parsed["response_text"],
            is_correct=parsed["is_correct"],
            status="success",
            finish_reason=parsed.get("finish_reason"),
            latency_ms=latency_ms,
            input_tokens=tokens["input_tokens"],
            response_tokens=tokens["response_tokens"],
            total_tokens=tokens["total_tokens"],
            reasoning_tokens=tokens["reasoning_tokens"],
            effective_tokens=tokens["effective_tokens"],
            cost=tokens["cost"],
            raw_response_json=json.dumps(api_response),
            timestamp=datetime.now(),
            parse_confidence=parsed.get("parse_confidence", "unknown"),
            review_status="auto",
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

        # Extract and normalize error details from response
        try:
            error_body = error.response.json() if error.response.headers.get("content-type") == "application/json" else {}
        except:
            error_body = {}
        
        # Normalize the error using error_handler
        normalized_error = normalize_openrouter_error(error.response.status_code, error_body)
        error_details = format_error_details(normalized_error)

        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            error_details=error_details,
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

        # Create normalized error details for timeout
        normalized_error = {
            "error_type": "timeout",
            "http_status": None,
            "message": f"Request timed out after {self._api_client._timeout}s",
            "timeout_seconds": self._api_client._timeout,
        }
        error_details = format_error_details(normalized_error)
        
        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            error_details=error_details,
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

        # Create normalized error details for request errors
        normalized_error = {
            "error_type": "request_error",
            "http_status": None,
            "message": error_message,
            "request_error_type": type(error).__name__,
        }
        error_details = format_error_details(normalized_error)
        
        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            error_details=error_details,
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

        # Create normalized error details for general errors
        normalized_error = {
            "error_type": "unexpected_error",
            "http_status": None,
            "message": error_message,
            "exception_type": type(error).__name__,
        }
        error_details = format_error_details(normalized_error)
        
        # Store error in database
        self._store_error(
            question=question,
            error_type=error_type,
            error_message=error_message,
            latency_ms=latency_ms,
            stack_trace=self._get_stack_trace(),
            error_details=error_details,
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
        error_details: Optional[str] = None,
    ) -> None:
        """Store an error in the database.

        Args:
            question: Question that caused the error.
            error_type: Type of error.
            error_message: Error message.
            latency_ms: Latency when error occurred.
            stack_trace: Optional stack trace.
            error_details: Optional detailed error information (e.g., full error response body).
        """
        # First create a response record for the error
        # Store response and error in database (skip in test mode)
        if self._settings is None or not self._settings.is_test_mode:
            # For errors, we still need a snapshot_id - create one if not already created
            # This should have been created earlier in execute_question
            # If not available, we can't create a response - log and skip
            if not hasattr(self, '_current_snapshot_id') or self._current_snapshot_id is None:
                logger.warning(f"Cannot store error response: no snapshot_id available for question {question.question_id}")
                return

            response = Response(
                run_id=self._run_id,
                snapshot_id=self._current_snapshot_id,
                question_id=question.question_id,
                model_id=self._model_id,
                iteration=self._iteration_number,
                selected_answer=None,
                response_text="",
                is_correct=None,
                status="error",
                latency_ms=latency_ms,
                input_tokens=0,
                response_tokens=0,
                total_tokens=None,
                cost=None,
                error_details=error_details,
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
