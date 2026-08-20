"""Tests that Model Seed (ModelConfig.model_seed) reaches the API payload
and request_json identically, and never interferes with AnswerRandomizer
(Checkpoint B — total separation from Randomization Seed).
"""

import asyncio
import json
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock

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


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.debug_enabled = False
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def randomizer():
    return AnswerRandomizer(seed=42)


@pytest.fixture
def parser():
    return AnswerParser()


def _create_mock_response(content: str = "The answer is (B)."):
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


def _build_plan(model_config: ModelConfig, randomization_seed_effective: int | None) -> ExecutionPlan:
    question_payload = QuestionPayload(
        stem="What is 2+2?", options=["3", "4", "5", "6"], answer_key="B"
    )
    item = PlanItem(
        item_id="run-001::var-001::snap-001::it-1",
        run_id="run-001",
        variant_id="var-001",
        snapshot_id="snap-001",
        question_id="q1",
        question_payload=question_payload,
    )
    variant = PlanVariant(
        variant_id="var-001",
        model_id="openai/gpt-4",
        model_config_effective=model_config,
        resolved_provider=None,
    )
    prompts = Prompts(system=None, user="Answer the following question.")
    plan_run = PlanRun(
        run_id="run-001",
        randomization_seed_effective=randomization_seed_effective,
        prompts_effective=prompts,
        retry_policy=RetryPolicy(),
        variants=[variant],
        items=[item],
    )
    return ExecutionPlan(
        plan_id="plan-001",
        created_at=datetime.now(),
        experiment_id="exp-001",
        runs=[plan_run],
    )


class TestModelSeedReachesPayloadAndRequestJson:
    @pytest.mark.asyncio
    async def test_model_seed_in_call_kwargs_payload(self, mock_api_client, randomizer, parser):
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_plan(ModelConfig(model_seed=42), randomization_seed_effective=None)

        result_queue = asyncio.Queue()
        results = await engine.execute_async(plan, result_queue)

        call_kwargs = mock_api_client.chat_completion.call_args.kwargs
        assert call_kwargs["payload"]["seed"] == 42
        # And request_json (the audit record) agrees exactly
        assert json.loads(results[0].request_json)["seed"] == 42

    @pytest.mark.asyncio
    async def test_model_seed_zero_sent_not_omitted(self, mock_api_client, randomizer, parser):
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_plan(ModelConfig(model_seed=0), randomization_seed_effective=None)

        result_queue = asyncio.Queue()
        results = await engine.execute_async(plan, result_queue)

        call_kwargs = mock_api_client.chat_completion.call_args.kwargs
        assert call_kwargs["payload"]["seed"] == 0
        assert json.loads(results[0].request_json)["seed"] == 0

    @pytest.mark.asyncio
    async def test_model_seed_none_omits_seed_from_both(self, mock_api_client, randomizer, parser):
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_plan(ModelConfig(model_seed=None), randomization_seed_effective=None)

        result_queue = asyncio.Queue()
        results = await engine.execute_async(plan, result_queue)

        call_kwargs = mock_api_client.chat_completion.call_args.kwargs
        assert "seed" not in call_kwargs["payload"]
        assert "seed" not in json.loads(results[0].request_json)


class TestModelSeedNeverInterferesWithAnswerRandomizer:
    @pytest.mark.asyncio
    async def test_randomization_fields_unaffected_by_model_seed(
        self, mock_api_client, randomizer, parser
    ):
        """The ExecutionResult's randomization_enabled/randomization_seed
        fields must be identical whether or not a model_seed is set — the
        two are fully independent."""
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)

        plan_with_model_seed = _build_plan(
            ModelConfig(model_seed=999), randomization_seed_effective=7
        )
        plan_without_model_seed = _build_plan(
            ModelConfig(model_seed=None), randomization_seed_effective=7
        )

        results_with = await engine.execute_async(plan_with_model_seed, asyncio.Queue())
        results_without = await engine.execute_async(plan_without_model_seed, asyncio.Queue())

        assert results_with[0].randomization_enabled == results_without[0].randomization_enabled
        assert results_with[0].randomization_seed == results_without[0].randomization_seed
        assert results_with[0].randomization_seed == 7
        assert results_with[0].randomization_enabled is True

    @pytest.mark.asyncio
    async def test_model_seed_never_appears_in_randomization_seed_field(
        self, mock_api_client, randomizer, parser
    ):
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_plan(ModelConfig(model_seed=123), randomization_seed_effective=None)

        results = await engine.execute_async(plan, asyncio.Queue())

        # Randomization is off (seed_effective=None); model_seed=123 must
        # not have leaked into the randomization decision or its recorded seed.
        assert results[0].randomization_enabled is False
        assert results[0].randomization_seed is None

    @pytest.mark.asyncio
    async def test_randomization_seed_never_sent_to_api(self, mock_api_client, randomizer, parser):
        """RANDOMIZATION_SEED must never appear anywhere in the API payload,
        regardless of model_seed."""
        mock_api_client.chat_completion = AsyncMock(return_value=_create_mock_response())
        engine = ExecutionEngine(mock_api_client, randomizer, parser)
        plan = _build_plan(ModelConfig(model_seed=1), randomization_seed_effective=99)

        await engine.execute_async(plan, asyncio.Queue())

        call_kwargs = mock_api_client.chat_completion.call_args.kwargs
        payload = call_kwargs["payload"]
        assert "randomization_seed" not in payload
        assert "RANDOMIZATION_SEED" not in payload
        assert payload["seed"] == 1  # only the Model Seed reaches the API
        assert 99 not in payload.values()  # the randomization seed's value never leaks in
