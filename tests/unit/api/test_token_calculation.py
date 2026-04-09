"""Unit tests for token calculation correctness.

Tests the corrected token calculation contract:
- response_tokens = output_tokens - reasoning_tokens
- effective_tokens = input_tokens + response_tokens + reasoning_tokens
"""

import pytest

from src.api.response_parser import parse_to_completion_response


class FakeAggregatedResponse:
    """Minimal fake aggregated response for testing."""

    def __init__(self, content, usage=None, raw_response=None):
        self.content = content
        self.usage = usage or {}
        self.raw_response = raw_response or []


class TestTokenCalculation:
    """Tests proving the corrected token calculation is correct."""

    def test_response_tokens_excludes_reasoning(self):
        """response_tokens MUST equal output_tokens - reasoning_tokens."""
        aggregated = FakeAggregatedResponse(
            content="Answer is (B).",
            usage={
                "prompt_tokens": 50,
                "completion_tokens": 15,  # output_tokens (includes reasoning)
                "completion_tokens_details": {"reasoning_tokens": 5},
                "cost": 0.0001,
            },
        )

        result = parse_to_completion_response(aggregated, "test/model", latency_ms=500)

        # response_tokens = 15 - 5 = 10
        assert result.response_tokens == 10
        assert result.reasoning_tokens == 5
        assert result.input_tokens == 50
        # effective_tokens = 50 + 10 + 5 = 65
        assert result.effective_tokens == 65

    def test_no_reasoning_tokens(self):
        """When no reasoning_tokens, response_tokens == output_tokens."""
        aggregated = FakeAggregatedResponse(
            content="Answer is (A).",
            usage={
                "prompt_tokens": 30,
                "completion_tokens": 8,
                "cost": 0.00005,
            },
        )

        result = parse_to_completion_response(aggregated, "test/model", latency_ms=300)

        assert result.response_tokens == 8
        assert result.reasoning_tokens is None
        assert result.input_tokens == 30
        # effective_tokens = 30 + 8 + 0 = 38
        assert result.effective_tokens == 38

    def test_effective_tokens_calculation(self):
        """effective_tokens MUST equal input + response + reasoning."""
        input_tokens = 100
        output_tokens = 50  # completion_tokens
        reasoning_tokens = 20

        aggregated = FakeAggregatedResponse(
            content="Long reasoning here...Answer is (C).",
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
                "cost": 0.001,
            },
        )

        result = parse_to_completion_response(aggregated, "test/model", latency_ms=1000)

        expected_response_tokens = output_tokens - reasoning_tokens  # 50 - 20 = 30
        expected_effective = input_tokens + expected_response_tokens + reasoning_tokens  # 100 + 30 + 20 = 150

        assert result.response_tokens == expected_response_tokens
        assert result.reasoning_tokens == reasoning_tokens
        assert result.effective_tokens == expected_effective

    def test_zero_reasoning_tokens(self):
        """When reasoning_tokens is explicitly 0, response_tokens == output_tokens."""
        aggregated = FakeAggregatedResponse(
            content="Direct answer.",
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        )

        result = parse_to_completion_response(aggregated, "test/model", latency_ms=200)

        assert result.response_tokens == 10
        assert result.reasoning_tokens is None  # 0 means no reasoning
        assert result.effective_tokens == 30  # 20 + 10 + 0

    def test_empty_usage(self):
        """When usage is missing/empty, all tokens default to 0."""
        aggregated = FakeAggregatedResponse(
            content="Empty",
            usage={},
        )

        result = parse_to_completion_response(aggregated, "test/model", latency_ms=100)

        assert result.response_tokens == 0
        assert result.reasoning_tokens is None
        assert result.effective_tokens == 0
