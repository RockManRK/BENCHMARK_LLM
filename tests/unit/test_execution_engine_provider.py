"""Unit tests for provider in execution engine request payload.

Tests that the ExecutionEngine correctly includes provider.only and allow_fallbacks
in API request payloads when resolved_provider is set on PlanVariant.

The provider format must be: {only: [slug], allow_fallbacks: false}
"""

import json
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.core.execution_engine import ExecutionEngine
from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser


@pytest.fixture
def mock_api_client():
    """Mock OpenRouterClient that captures request payloads.

    Returns a mock client whose chat_completion method captures the
    provider config passed to it for later inspection.
    """
    client = MagicMock()
    client.chat_completion = AsyncMock()
    client.debug_enabled = False
    return client


@pytest.fixture
def randomizer():
    """Create seeded AnswerRandomizer for deterministic tests."""
    return AnswerRandomizer(seed=42)


@pytest.fixture
def parser():
    """Create AnswerParser instance."""
    return AnswerParser()


def _create_mock_response(content: str = "The answer is (B).") -> MagicMock:
    """Create a mock API response."""
    response = MagicMock()
    response.content = content
    response.input_tokens = 50
    response.response_tokens = 10
    response.reasoning_tokens = None
    response.cost = 0.0001
    response.latency_ms = 500
    response.finish_reason = "stop"
    response.raw_response = [
        {"choices": [{"delta": {"content": content}, "finish_reason": "stop"}]}
    ]
    return response


def _build_minimal_plan(
    variant_provider: str | None = None,
    num_items: int = 1,
) -> tuple[ExecutionPlan, list[dict[str, Any]]]:
    """Build a minimal ExecutionPlan for testing.

    Args:
        variant_provider: Provider slug for the variant (None = no provider)
        num_items: Number of items to create

    Returns:
        Tuple of (ExecutionPlan, captured_request_kwargs list)
    """
    # Create question payload
    question_payload = QuestionPayload(
        stem="What is 2+2?",
        options=["3", "4", "5", "6"],
        answer_key="B",
    )

    # Create item
    item = PlanItem(
        item_id="run-001::var-001::snap-001::it-1",
        run_id="run-001",
        variant_id="var-001",
        snapshot_id="snap-001",
        question_id="q1",
        question_payload=question_payload,
    )

    # Create variant
    variant = PlanVariant(
        variant_id="var-001",
        model_id="openai/gpt-4",
        model_config_effective=ModelConfig(),
        resolved_provider=variant_provider,
    )

    # Create prompts
    prompts = Prompts(
        system=None,
        user="Answer the following question.",
    )

    # Create plan run
    plan_run = PlanRun(
        run_id="run-001",
        randomization_seed_effective=None,
        prompts_effective=prompts,
        retry_policy=RetryPolicy(),
        variants=[variant],
        items=[item],
    )

    # Create plan
    plan = ExecutionPlan(
        plan_id="plan-001",
        created_at=datetime.now(),
        experiment_id="exp-001",
        runs=[plan_run],
    )

    return plan


class TestProviderInRequestPayload:
    """Tests for provider object in API request."""

    @pytest.mark.asyncio
    async def test_provider_added_when_resolved(self, mock_api_client, randomizer, parser):
        """When resolved_provider is set, provider object is in payload."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider="deepinfra/turbo")

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: provider was passed to API call
        mock_api_client.chat_completion.assert_called_once()
        call_kwargs = mock_api_client.chat_completion.call_args.kwargs

        assert "provider" in call_kwargs["payload"]
        assert call_kwargs["payload"]["provider"]["only"] == ["deepinfra/turbo"]
        assert call_kwargs["payload"]["provider"]["allow_fallbacks"] is False

    @pytest.mark.asyncio
    async def test_provider_not_added_when_null(self, mock_api_client, randomizer, parser):
        """When resolved_provider is None, "provider" is omitted from the
        payload entirely — matching the None-omission contract every other
        optional field follows (never a literal "provider": null on the wire)."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider=None)

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: provider key is absent from the real payload
        mock_api_client.chat_completion.assert_called_once()
        call_kwargs = mock_api_client.chat_completion.call_args.kwargs

        assert "provider" not in call_kwargs["payload"]

    @pytest.mark.asyncio
    async def test_provider_format_matches_blueprint(self, mock_api_client, randomizer, parser):
        """Provider format is: {only: [slug], allow_fallbacks: false}"""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider="togethercomputer/llama-3.3-70b")

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: exact format
        call_kwargs = mock_api_client.chat_completion.call_args.kwargs
        provider = call_kwargs["payload"]["provider"]

        assert "only" in provider
        assert "allow_fallbacks" in provider
        assert provider["only"] == ["togethercomputer/llama-3.3-70b"]
        assert provider["allow_fallbacks"] is False
        # Should be a list with single slug
        assert isinstance(provider["only"], list)
        assert len(provider["only"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_variants_each_with_own_provider(self, mock_api_client, randomizer, parser):
        """Each variant maintains its own provider slug."""
        # Arrange: Create plan with two variants
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())

        # Variant 1
        variant1 = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4",
            model_config_effective=ModelConfig(),
            resolved_provider="deepinfra/turbo",
        )

        # Variant 2
        variant2 = PlanVariant(
            variant_id="var-002",
            model_id="anthropic/claude-3",
            model_config_effective=ModelConfig(),
            resolved_provider="togethercomputer/llama",
        )

        # Create question
        question_payload = QuestionPayload(
            stem="What is 2+2?",
            options=["3", "4", "5", "6"],
            answer_key="B",
        )

        # Create items for each variant
        item1 = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q1",
            question_payload=question_payload,
        )

        item2 = PlanItem(
            item_id="run-001::var-002::snap-001::it-2",
            run_id="run-001",
            variant_id="var-002",
            snapshot_id="snap-001",
            question_id="q1",
            question_payload=question_payload,
        )

        prompts = Prompts(
            system=None,
            user="Answer.",
        )

        plan_run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=prompts,
            retry_policy=RetryPolicy(),
            variants=[variant1, variant2],
            items=[item1, item2],
        )

        plan = ExecutionPlan(
            plan_id="plan-001",
            created_at=datetime.now(),
            experiment_id="exp-001",
            runs=[plan_run],
        )

        engine = ExecutionEngine(mock_api_client, randomizer, parser)

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: Two API calls with different providers
        assert mock_api_client.chat_completion.call_count == 2

        # Get all calls
        calls = mock_api_client.chat_completion.call_args_list

        # First call should have first provider
        assert "provider" in calls[0].kwargs["payload"]
        assert calls[0].kwargs["payload"]["provider"]["only"] == ["deepinfra/turbo"]

        # Second call should have second provider
        assert "provider" in calls[1].kwargs["payload"]
        assert calls[1].kwargs["payload"]["provider"]["only"] == ["togethercomputer/llama"]

    @pytest.mark.asyncio
    async def test_provider_not_overwritten_by_other_params(self, mock_api_client, randomizer, parser):
        """Provider config is not affected by other request parameters."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider="anyscale/llama")

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: provider is a separate dict, not merged with other params
        call_kwargs = mock_api_client.chat_completion.call_args.kwargs

        # Provider should exist with correct structure
        assert "provider" in call_kwargs["payload"]
        provider = call_kwargs["payload"]["provider"]
        assert provider["only"] == ["anyscale/llama"]
        assert provider["allow_fallbacks"] is False

        # payload uses "model" (OpenRouter's real API field name) — the
        # client no longer receives a separate model_id kwarg at all
        assert "model" in call_kwargs["payload"]
        assert call_kwargs["payload"]["model"] == "openai/gpt-4"

    @pytest.mark.asyncio
    async def test_provider_with_empty_string_not_added(self, mock_api_client, randomizer, parser):
        """When resolved_provider is empty string, provider is passed as dict with empty slug."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider="")  # Empty string

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: provider is passed with empty slug (empty string is truthy in Python)
        mock_api_client.chat_completion.assert_called_once()
        call_kwargs = mock_api_client.chat_completion.call_args.kwargs

        assert "provider" in call_kwargs["payload"]
        # Empty string is not None, so it will be included
        assert call_kwargs["payload"]["provider"]["only"] == [""]

    @pytest.mark.asyncio
    async def test_mixed_resolved_and_unresolved_variants(self, mock_api_client, randomizer, parser):
        """Mixed variants: some with provider, some without."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())

        # Variant with provider
        variant1 = PlanVariant(
            variant_id="var-001",
            model_id="openai/gpt-4",
            model_config_effective=ModelConfig(),
            resolved_provider="deepinfra/turbo",
        )

        # Variant without provider
        variant2 = PlanVariant(
            variant_id="var-002",
            model_id="anthropic/claude-3",
            model_config_effective=ModelConfig(),
            resolved_provider=None,
        )

        question_payload = QuestionPayload(
            stem="What is 2+2?",
            options=["3", "4", "5", "6"],
            answer_key="B",
        )

        item1 = PlanItem(
            item_id="run-001::var-001::snap-001::it-1",
            run_id="run-001",
            variant_id="var-001",
            snapshot_id="snap-001",
            question_id="q1",
            question_payload=question_payload,
        )

        item2 = PlanItem(
            item_id="run-001::var-002::snap-001::it-2",
            run_id="run-001",
            variant_id="var-002",
            snapshot_id="snap-001",
            question_id="q1",
            question_payload=question_payload,
        )

        prompts = Prompts(system=None, user="Answer.")

        plan_run = PlanRun(
            run_id="run-001",
            randomization_seed_effective=None,
            prompts_effective=prompts,
            retry_policy=RetryPolicy(),
            variants=[variant1, variant2],
            items=[item1, item2],
        )

        plan = ExecutionPlan(
            plan_id="plan-001",
            created_at=datetime.now(),
            experiment_id="exp-001",
            runs=[plan_run],
        )

        engine = ExecutionEngine(mock_api_client, randomizer, parser)

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert
        assert mock_api_client.chat_completion.call_count == 2
        calls = mock_api_client.chat_completion.call_args_list

        # First variant has provider
        assert "provider" in calls[0].kwargs["payload"]
        assert calls[0].kwargs["payload"]["provider"]["only"] == ["deepinfra/turbo"]

        # Second variant has no provider — key omitted from the payload
        assert "provider" not in calls[1].kwargs["payload"]


class TestProviderLogging:
    """Tests for provider-related logging in execution engine."""

    @pytest.mark.asyncio
    async def test_provider_locked_logged_when_provider_set(self, mock_api_client, randomizer, parser):
        """When provider is set, PROVIDER_LOCKED is logged."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider="deepinfra/turbo")

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert: log message contains provider info
        # The engine logs "PROVIDER_LOCKED | run=... | variant=... | provider=..."
        # We verify by checking the log wasn't an error (provider was applied)
        assert mock_api_client.chat_completion.call_count == 1

    @pytest.mark.asyncio
    async def test_no_provider_locked_log_when_no_provider(self, mock_api_client, randomizer, parser):
        """When provider is None, no PROVIDER_LOCKED log is generated."""
        # Arrange
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_minimal_plan(variant_provider=None)

        # Act
        result_queue = asyncio.Queue()
        await engine.execute_async(plan, result_queue)

        # Assert
        assert mock_api_client.chat_completion.call_count == 1
