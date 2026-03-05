"""Tests for the response parser module.

This module tests the parsing of OpenRouter API responses,
including extraction of answers, token usage, and latency.
"""

from datetime import datetime

import pytest

from src.api.parser import (
    ParseError,
    ParsedResponse,
    ResponseParser,
)


@pytest.fixture
def parser() -> ResponseParser:
    """Create a ResponseParser instance for testing."""
    return ResponseParser()


@pytest.fixture
def successful_response() -> dict:
    """Create a sample successful API response."""
    return {
        "id": "chatcmpl-123456",
        "model": "openai/gpt-4",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The correct answer is A."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 10,
            "total_tokens": 60
        },
        "created": 1709500000,
    }


@pytest.fixture
def minimal_response() -> dict:
    """Create a minimal valid API response."""
    return {
        "id": "chatcmpl-minimal",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "A"
                },
                "finish_reason": "stop"
            }
        ],
    }


class TestParsedResponse:
    """Test cases for ParsedResponse dataclass."""

    def test_parsed_response_creation(self) -> None:
        """Test creating a ParsedResponse instance."""
        response = ParsedResponse(
            response_id="chatcmpl-123",
            selected_answer="A",
            response_text="The answer is A",
            input_tokens=50,
            output_tokens=10,
            total_tokens=60,
            latency_ms=1500,
            status="success",
        )
        
        assert response.response_id == "chatcmpl-123"
        assert response.selected_answer == "A"
        assert response.input_tokens == 50
        assert response.output_tokens == 10

    def test_parsed_response_defaults(self) -> None:
        """Test ParsedResponse default values."""
        response = ParsedResponse(
            response_id="chatcmpl-456",
            selected_answer="B",
            response_text="The answer is B",
        )
        
        assert response.input_tokens == 0
        assert response.output_tokens == 0
        assert response.total_tokens == 0
        assert response.latency_ms == 0
        assert response.status == "success"


class TestResponseParserBasic:
    """Test cases for basic response parsing."""

    def test_parse_successful_response(
        self, parser: ResponseParser, successful_response: dict
    ) -> None:
        """Test parsing a successful API response."""
        result = parser.parse(successful_response)
        
        assert result.response_id == "chatcmpl-123456"
        assert result.selected_answer == "A"
        assert "The correct answer is A" in result.response_text
        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.total_tokens == 60
        assert result.status == "success"

    def test_parse_minimal_response(
        self, parser: ResponseParser, minimal_response: dict
    ) -> None:
        """Test parsing a minimal valid response."""
        result = parser.parse(minimal_response)
        
        assert result.response_id == "chatcmpl-minimal"
        assert result.selected_answer == "A"
        assert result.status == "success"

    def test_parse_with_latency(
        self, parser: ResponseParser, successful_response: dict
    ) -> None:
        """Test parsing response with latency information."""
        start_time = datetime.now()
        result = parser.parse(
            successful_response,
            start_time=start_time,
            end_time=datetime.now()
        )
        
        assert result.latency_ms >= 0


class TestAnswerExtraction:
    """Test cases for answer extraction from response text."""

    def test_extract_answer_letter_only(
        self, parser: ResponseParser
    ) -> None:
        """Test extracting answer when response is just a letter."""
        response = {
            "id": "test-1",
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.selected_answer == "A"

    def test_extract_answer_from_sentence(
        self, parser: ResponseParser
    ) -> None:
        """Test extracting answer from a sentence."""
        response = {
            "id": "test-2",
            "choices": [{"message": {"content": "The answer is B."}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.selected_answer == "B"

    def test_extract_answer_uppercase(
        self, parser: ResponseParser
    ) -> None:
        """Test extracting uppercase answer letter."""
        response = {
            "id": "test-3",
            "choices": [{"message": {"content": "CORRECT ANSWER: C"}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.selected_answer == "C"

    def test_extract_answer_lowercase_converted(
        self, parser: ResponseParser
    ) -> None:
        """Test that lowercase answers are converted to uppercase."""
        response = {
            "id": "test-4",
            "choices": [{"message": {"content": "the answer is d"}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.selected_answer == "D"

    def test_extract_answer_with_reasoning(
        self, parser: ResponseParser
    ) -> None:
        """Test extracting answer when response includes reasoning."""
        response = {
            "id": "test-5",
            "choices": [{
                "message": {
                    "content": "The correct answer is A because the capital of France is Paris."
                },
                "finish_reason": "stop"
            }],
        }
        result = parser.parse(response)
        assert result.selected_answer == "A"

    def test_no_answer_found(
        self, parser: ResponseParser
    ) -> None:
        """Test handling when no answer letter can be extracted."""
        response = {
            "id": "test-6",
            "choices": [{"message": {"content": "I don't know the answer."}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.selected_answer == ""


class TestTokenUsageExtraction:
    """Test cases for token usage extraction."""

    def test_extract_full_usage(
        self, parser: ResponseParser, successful_response: dict
    ) -> None:
        """Test extracting complete token usage information."""
        result = parser.parse(successful_response)
        
        assert result.input_tokens == 50
        assert result.output_tokens == 10
        assert result.total_tokens == 60

    def test_extract_partial_usage(
        self, parser: ResponseParser
    ) -> None:
        """Test extracting partial token usage."""
        response = {
            "id": "test-usage",
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 30,
            }
        }
        result = parser.parse(response)
        
        assert result.input_tokens == 30
        assert result.output_tokens == 0
        assert result.total_tokens == 30

    def test_missing_usage(
        self, parser: ResponseParser
    ) -> None:
        """Test handling missing usage information."""
        response = {
            "id": "test-no-usage",
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0


class TestErrorHandling:
    """Test cases for error handling in response parsing."""

    def test_parse_empty_response(self, parser: ResponseParser) -> None:
        """Test parsing empty response raises error."""
        with pytest.raises(ParseError, match="Missing required field"):
            parser.parse({})

    def test_parse_missing_choices(self, parser: ResponseParser) -> None:
        """Test parsing response without choices raises error."""
        response = {"id": "test-123"}
        with pytest.raises(ParseError, match="Missing required field"):
            parser.parse(response)

    def test_parse_empty_choices(self, parser: ResponseParser) -> None:
        """Test parsing response with empty choices raises error."""
        response = {
            "id": "test-123",
            "choices": [],
        }
        with pytest.raises(ParseError, match="No choices in response"):
            parser.parse(response)

    def test_parse_missing_message(self, parser: ResponseParser) -> None:
        """Test parsing response without message raises error."""
        response = {
            "id": "test-123",
            "choices": [{"finish_reason": "stop"}],
        }
        with pytest.raises(ParseError, match="Missing message in choice"):
            parser.parse(response)

    def test_parse_missing_content(self, parser: ResponseParser) -> None:
        """Test parsing response without content raises error."""
        response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant"}, "finish_reason": "stop"}],
        }
        with pytest.raises(ParseError, match="Missing content in message"):
            parser.parse(response)

    def test_parse_none_content(self, parser: ResponseParser) -> None:
        """Test parsing response with None content raises error."""
        response = {
            "id": "test-123",
            "choices": [{"message": {"role": "assistant", "content": None}, "finish_reason": "stop"}],
        }
        with pytest.raises(ParseError, match="Empty content in response"):
            parser.parse(response)


class TestResponseStatus:
    """Test cases for response status determination."""

    def test_status_success_on_stop(
        self, parser: ResponseParser
    ) -> None:
        """Test status is success when finish_reason is stop."""
        response = {
            "id": "test-status",
            "choices": [{"message": {"content": "A"}, "finish_reason": "stop"}],
        }
        result = parser.parse(response)
        assert result.status == "success"

    def test_status_success_on_length(
        self, parser: ResponseParser
    ) -> None:
        """Test status is success when finish_reason is length."""
        response = {
            "id": "test-status",
            "choices": [{"message": {"content": "A"}, "finish_reason": "length"}],
        }
        result = parser.parse(response)
        assert result.status == "success"

    def test_status_error_on_content_filter(
        self, parser: ResponseParser
    ) -> None:
        """Test status is error when finish_reason is content_filter."""
        response = {
            "id": "test-status",
            "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
        }
        result = parser.parse(response)
        assert result.status == "error"
