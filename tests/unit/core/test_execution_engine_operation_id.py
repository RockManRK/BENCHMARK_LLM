"""Tests for operation_id correlation and the new NORMAL/DETAILED-tier
events added to ExecutionEngine in Checkpoint C: PROVIDER_REQUESTED,
PROVIDER_EFFECTIVE, PARSE_DECISION, RANDOMIZATION_APPLIED.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.execution_engine import ExecutionEngine
from src.core.execution_plan import (
    ExecutionPlan,
    ModelConfig,
    PlanItem,
    PlanRun,
    PlanVariant,
    Prompts,
    QuestionPayload,
    RetryPolicy,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.utils.log_events import Event


def _mock_response(content="The answer is (B)."):
    response = MagicMock()
    response.content = content
    response.input_tokens = 50
    response.response_tokens = 10
    response.reasoning_tokens = None
    response.cost = 0.0001
    response.latency_ms = 500
    response.finish_reason = "stop"
    response.raw_response = [
        {"provider": "Google AI Studio", "choices": [{"delta": {"content": content}, "finish_reason": "stop"}]}
    ]
    return response


def _build_plan(operation_id: str | None, resolved_provider=None, randomization_seed_effective=None):
    question_payload = QuestionPayload(stem="Q?", options=["3", "4", "5", "6"], answer_key="B")
    item = PlanItem(
        item_id="run-1::var-1::snap-1::it-1", run_id="run-1", variant_id="var-1",
        snapshot_id="snap-1", question_id="q1", question_payload=question_payload,
    )
    variant = PlanVariant(
        variant_id="var-1", model_id="openai/gpt-4",
        model_config_effective=ModelConfig(), resolved_provider=resolved_provider,
    )
    prompts = Prompts(system=None, user="Answer.")
    plan_run = PlanRun(
        run_id="run-1", randomization_seed_effective=randomization_seed_effective,
        prompts_effective=prompts, retry_policy=RetryPolicy(),
        variants=[variant], items=[item],
    )
    return ExecutionPlan(
        plan_id="plan-1", created_at=datetime.now(), experiment_id="exp-1",
        runs=[plan_run], operation_id=operation_id,
    )


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.debug_enabled = False
    client.chat_completion = AsyncMock(return_value=_mock_response())
    return client


class TestOperationIdThreading:
    @pytest.mark.asyncio
    async def test_operation_id_appears_on_every_emitted_event(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_test_abc123")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        assert spy.call_count > 0
        for call in spy.call_args_list:
            assert call.kwargs.get("operation_id") == "op_test_abc123"

    @pytest.mark.asyncio
    async def test_operation_id_none_when_plan_has_none(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id=None)

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        for call in spy.call_args_list:
            assert call.kwargs.get("operation_id") is None

    @pytest.mark.asyncio
    async def test_execution_start_and_complete_present(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        event_names = [call.args[1] for call in spy.call_args_list]
        assert Event.EXECUTION_START in event_names
        assert Event.EXECUTION_COMPLETE in event_names


class TestProviderRequestedEffective:
    @pytest.mark.asyncio
    async def test_provider_requested_emitted_with_none_when_unresolved(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1", resolved_provider=None)

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        requested_calls = [c for c in spy.call_args_list if c.args[1] == Event.PROVIDER_REQUESTED]
        assert len(requested_calls) == 1
        assert requested_calls[0].kwargs["provider"] is None

    @pytest.mark.asyncio
    async def test_provider_requested_emitted_with_slug_when_resolved(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1", resolved_provider="deepinfra/turbo")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        requested_calls = [c for c in spy.call_args_list if c.args[1] == Event.PROVIDER_REQUESTED]
        assert requested_calls[0].kwargs["provider"] == "deepinfra/turbo"

    @pytest.mark.asyncio
    async def test_provider_effective_extracted_from_response(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        effective_calls = [c for c in spy.call_args_list if c.args[1] == Event.PROVIDER_EFFECTIVE]
        assert len(effective_calls) == 1
        assert effective_calls[0].kwargs["provider"] == "Google AI Studio"

    @pytest.mark.asyncio
    async def test_provider_effective_omitted_when_response_has_none(self, mock_api_client):
        response = _mock_response()
        response.raw_response = [{"choices": [{"delta": {"content": "x"}, "finish_reason": "stop"}]}]
        mock_api_client.chat_completion = AsyncMock(return_value=response)
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        effective_calls = [c for c in spy.call_args_list if c.args[1] == Event.PROVIDER_EFFECTIVE]
        assert len(effective_calls) == 0


class TestParseDecisionAndRandomizationApplied:
    @pytest.mark.asyncio
    async def test_parse_decision_emitted_with_answer_and_confidence(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1")

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        parse_calls = [c for c in spy.call_args_list if c.args[1] == Event.PARSE_DECISION]
        assert len(parse_calls) == 1
        assert parse_calls[0].kwargs["selected_answer"] == "B"

    @pytest.mark.asyncio
    async def test_randomization_applied_reflects_disabled_state(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1", randomization_seed_effective=None)

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        rand_calls = [c for c in spy.call_args_list if c.args[1] == Event.RANDOMIZATION_APPLIED]
        assert len(rand_calls) == 1
        assert rand_calls[0].kwargs["randomization_enabled"] is False
        assert rand_calls[0].kwargs["randomization_seed"] is None

    @pytest.mark.asyncio
    async def test_randomization_applied_reflects_enabled_state(self, mock_api_client):
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan(operation_id="op_1", randomization_seed_effective=7)

        with patch("src.core.execution_engine.emit_event") as spy:
            await engine.execute_async(plan, asyncio.Queue())

        rand_calls = [c for c in spy.call_args_list if c.args[1] == Event.RANDOMIZATION_APPLIED]
        assert rand_calls[0].kwargs["randomization_enabled"] is True
        assert rand_calls[0].kwargs["randomization_seed"] == 7
