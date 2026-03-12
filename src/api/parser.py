"""Response parser module for OpenRouter API client.

This module provides functionality to parse API responses,
extracting answers, token usage, latency, and status information.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Exception raised when response parsing fails."""

    def __init__(self, message: str) -> None:
        """Initialize ParseError.

        Args:
            message: Error message describing the parsing failure.
        """
        super().__init__(message)


@dataclass
class ParsedResponse:
    """Parsed response data from OpenRouter API.

    Attributes:
        response_id: Unique identifier for the API response.
        selected_answer: The extracted answer letter (A, B, C, D, etc.).
        response_text: Full text content of the response.
        input_tokens: Number of tokens in the prompt.
        response_tokens: Number of tokens in the completion (renamed from output_tokens).
        output_tokens: Deprecated - kept for backward compatibility, use response_tokens.
        total_tokens: Total tokens used (input + output).
        cost: Cost in credits for this response (from usage.cost).
        latency_ms: Request latency in milliseconds.
        status: Response status (success, error, etc.).
        model: Model identifier that generated the response.
        finish_reason: Reason why generation stopped.
        effective_tokens: Total effective tokens (input + response + reasoning).

    Example:
        >>> response = ParsedResponse(
        ...     response_id="chatcmpl-123",
        ...     selected_answer="A",
        ...     response_text="The answer is A",
        ...     input_tokens=50,
        ...     response_tokens=10,
        ... )
    """

    response_id: str
    selected_answer: str
    response_text: str
    input_tokens: int = 0
    response_tokens: int = 0  # Renamed from output_tokens
    output_tokens: int = 0  # Deprecated: kept for backward compatibility
    total_tokens: int = 0
    cost: Optional[float] = None
    latency_ms: int = 0
    status: str = "success"
    model: str = ""
    finish_reason: str = ""
    effective_tokens: Optional[int] = None  # NEW: input + response + reasoning


class ResponseParser:
    """Parser for OpenRouter API responses.

    This class extracts relevant information from API responses,
    including the selected answer, token usage, and metadata.

    Example:
        >>> parser = ResponseParser()
        >>> parsed = parser.parse(api_response)
        >>> print(parsed.selected_answer)
        'A'
    """

    # Status codes that indicate successful completion
    SUCCESS_FINISH_REASONS = {"stop", "length", "eos_token"}

    # Status codes that indicate errors
    ERROR_FINISH_REASONS = {"content_filter", "function_call"}

    def parse(
        self,
        response: dict[str, Any],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ParsedResponse:
        """Parse an API response into structured data.

        Args:
            response: The raw API response dictionary.
            start_time: Optional request start time for latency calculation.
            end_time: Optional request end time for latency calculation.

        Returns:
            ParsedResponse object with extracted information.

        Raises:
            ParseError: If the response structure is invalid or missing required fields.

        Example:
            >>> parser = ResponseParser()
            >>> parsed = parser.parse(api_response)
        """
        # Validate required fields
        self._validate_response(response)

        # Extract basic information
        response_id = response.get("id", "")
        model = response.get("model", "")

        # Extract choice information
        choice = response["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")
        finish_reason = choice.get("finish_reason", "")
        
        # Handle reasoning models (e.g., Qwen with llama.cpp)
        # Some models output reasoning_content separately from content
        # If content is empty but reasoning_content exists, use reasoning_content
        if not content or not content.strip():
            reasoning_content = message.get("reasoning_content", "")
            if reasoning_content:
                content = reasoning_content

        if content is None:
            raise ParseError("Empty content in response")

        # Extract token usage
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        response_tokens = usage.get("completion_tokens", 0)  # New name
        output_tokens = response_tokens  # Deprecated: alias for backward compatibility
        total_tokens = usage.get("total_tokens", input_tokens + response_tokens)
        cost = usage.get("cost")
        
        # Calculate effective tokens
        effective_tokens = None
        reasoning_tokens = 0
        completion_tokens_details = usage.get("completion_tokens_details", {})
        if completion_tokens_details and "reasoning_tokens" in completion_tokens_details:
            reasoning_tokens = completion_tokens_details["reasoning_tokens"]
        effective_tokens = input_tokens + response_tokens + reasoning_tokens

        # Calculate latency
        latency_ms = 0
        if start_time and end_time:
            latency_ms = int((end_time - start_time).total_seconds() * 1000)

        # Extract answer from content
        selected_answer = self._extract_answer(content)

        # Determine status
        status = self._determine_status(finish_reason, content)

        return ParsedResponse(
            response_id=response_id,
            selected_answer=selected_answer.upper() if selected_answer else "",
            response_text=content.strip(),
            input_tokens=input_tokens,
            response_tokens=response_tokens,
            output_tokens=output_tokens,  # Deprecated: alias
            total_tokens=total_tokens,
            cost=cost,
            latency_ms=latency_ms,
            status=status,
            model=model,
            finish_reason=finish_reason,
            effective_tokens=effective_tokens,
        )

    def _validate_response(self, response: dict[str, Any]) -> None:
        """Validate that response has required fields.

        Args:
            response: The API response dictionary to validate.

        Raises:
            ParseError: If required fields are missing.
        """
        if not response:
            raise ParseError("Missing required field: response is empty")

        if "choices" not in response:
            raise ParseError("Missing required field: choices")

        if not response["choices"]:
            raise ParseError("No choices in response")

        choice = response["choices"][0]
        if "message" not in choice:
            raise ParseError("Missing message in choice")

        message = choice["message"]
        if "content" not in message:
            raise ParseError("Missing content in message")

    def _extract_answer(self, content: str) -> str:
        """Extract the answer letter from response content.

        Uses the new AnswerParser module for robust pattern matching.

        Args:
            content: The response text content.

        Returns:
            The extracted answer letter, or empty string if not found.

        Example:
            >>> parser = ResponseParser()
            >>> parser._extract_answer("The correct answer is B.")
            'B'
        """
        if not content:
            return ""

        # Use the new AnswerParser for robust extraction
        from src.core.answer_parser import AnswerParser
        
        answer_parser = AnswerParser()
        parsed = answer_parser.parse(content)
        
        # Return the answer or empty string if None
        return parsed.answer or ""

    def _determine_status(self, finish_reason: str, content: str) -> str:
        """Determine the response status based on finish reason and content.

        Args:
            finish_reason: The finish reason from the API response.
            content: The response text content.

        Returns:
            Status string: "success", "error", or "incomplete".
        """
        if finish_reason in self.ERROR_FINISH_REASONS:
            return "error"

        if finish_reason in self.SUCCESS_FINISH_REASONS:
            return "success"

        # If we have content, consider it a success
        if content and content.strip():
            return "success"

        return "incomplete"
