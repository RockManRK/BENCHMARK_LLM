"""Tests that ExecutionEngine forwards a variant's resolved base_url to the
API client on every call.

Context: this is the last hop of the BASE_URL seam. Planner._build_model_config
(tested in tests/unit/core/test_planner_base_url.py) puts the variant's
resolved BASE_URL into ModelConfig.base_url; this test verifies the Engine
actually passes that value through to api_client.chat_completion(base_url=...)
instead of dropping it (the previous behavior: --url was persisted and
hashed but silently ignored at execution time, so every --execute call
went to OpenRouter's default endpoint regardless of variant config).

Self-contained: builds a minimal one-item ExecutionPlan directly rather than
depending on tests/unit/core/test_execution_engine.py's fixtures, which
currently fail for an unrelated, pre-existing reason (ParsedAnswer no longer
accepts 'raw_matches').
"""

import asyncio
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.client import OpenRouterClient, CompletionResponse
from src.core.answer_parser import AnswerParser
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


def _build_plan(base_url: str | None) -> ExecutionPlan:
    variant = PlanVariant(
        variant_id="var-1",
        model_id="openai/gpt-4",
        model_config_effective=ModelConfig(base_url=base_url),
    )
    item = PlanItem(
        item_id="run-1::var-1::snap-1::it-1",
        run_id="run-1",
        variant_id="var-1",
        snapshot_id="snap-1",
        question_id="q1",
        question_payload=QuestionPayload(
            stem="2+2?",
            options=["3", "4", "5", "6"],
            answer_key="4",
        ),
    )
    run = PlanRun(
        run_id="run-1",
        randomization_seed_effective=None,
        prompts_effective=Prompts(system=None, user="Answer: {question}"),
        retry_policy=RetryPolicy(max_attempts=1),
        variants=[variant],
        items=[item],
    )
    return ExecutionPlan(
        plan_id="plan-1",
        created_at=datetime.now(),
        experiment_id="exp-1",
        runs=[run],
    )


def _mock_client() -> AsyncMock:
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(return_value=CompletionResponse(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=10,
        response_tokens=5,
        latency_ms=100,
    ))
    return client


class TestExecutionEngineBaseUrlPassthrough:
    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_variant_base_url_reaches_api_client(self):
        client = _mock_client()
        engine = ExecutionEngine(client, AnswerRandomizer(), AnswerParser())
        plan = _build_plan(base_url="http://127.0.0.1:8080/v1")

        await engine.execute_async(plan, asyncio.Queue())

        client.chat_completion.assert_awaited_once()
        assert client.chat_completion.call_args.kwargs["base_url"] == "http://127.0.0.1:8080/v1"

    @pytest.mark.asyncio
    @pytest.mark.domain_rule
    async def test_variant_without_base_url_passes_none(self):
        """Not specified must mean 'let the client use its own default',
        not silently reuse whatever URL a previous variant resolved to."""
        client = _mock_client()
        engine = ExecutionEngine(client, AnswerRandomizer(), AnswerParser())
        plan = _build_plan(base_url=None)

        await engine.execute_async(plan, asyncio.Queue())

        client.chat_completion.assert_awaited_once()
        assert client.chat_completion.call_args.kwargs["base_url"] is None
