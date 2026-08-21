"""Tests for TRACE-tier logging in ExecutionEngine (Checkpoint C):
REQUEST_PAYLOAD_TRACE, UPSTREAM_ECHO_TRACE, STREAM_CHUNK_TRACE. Confirms
these only fire when LOG_PROFILE=TRACE, that redaction is applied, and
that the upstream echo never overwrites/gets merged into request_json.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

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


def _mock_response_with_debug_echo():
    response = MagicMock()
    response.content = "The answer is (B)."
    response.input_tokens = 50
    response.response_tokens = 10
    response.reasoning_tokens = None
    response.cost = 0.0001
    response.latency_ms = 500
    response.finish_reason = "stop"
    response.raw_response = [
        {
            "choices": [],
            "debug": {
                "echo_upstream_body": {
                    "generationConfig": {"seed": 42},
                    "api_key": "sk-should-never-leak",
                }
            },
        },
        {"choices": [{"delta": {"content": "The answer is (B)."}, "finish_reason": "stop"}]},
    ]
    return response


def _build_plan(model_seed=42):
    question_payload = QuestionPayload(stem="Q?", options=["3", "4", "5", "6"], answer_key="B")
    item = PlanItem(
        item_id="run-1::var-1::snap-1::it-1", run_id="run-1", variant_id="var-1",
        snapshot_id="snap-1", question_id="q1", question_payload=question_payload,
    )
    variant = PlanVariant(
        variant_id="var-1", model_id="openai/gpt-4",
        model_config_effective=ModelConfig(model_seed=model_seed), resolved_provider=None,
    )
    prompts = Prompts(system=None, user="Answer.")
    plan_run = PlanRun(
        run_id="run-1", randomization_seed_effective=None, prompts_effective=prompts,
        retry_policy=RetryPolicy(), variants=[variant], items=[item],
    )
    return ExecutionPlan(
        plan_id="plan-1", created_at=datetime.now(), experiment_id="exp-1",
        runs=[plan_run], operation_id="op_trace_test",
    )


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.debug_enabled = False
    client.chat_completion = AsyncMock(return_value=_mock_response_with_debug_echo())
    return client


class TestTraceProfileGating:
    @pytest.mark.asyncio
    async def test_trace_events_absent_below_trace_profile(self, mock_api_client, monkeypatch):
        monkeypatch.setenv("LOG_PROFILE", "DETAILED")
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan()

        # Capture real JSONL output via the emitter's actual gating (not mocked)
        from src.utils.log_emitter import JSONL_LOGGER_NAME
        import logging

        jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)
        jsonl_logger.handlers.clear()
        jsonl_logger.setLevel(logging.DEBUG)
        jsonl_logger.propagate = False
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(json.loads(record.getMessage()))

        jsonl_logger.addHandler(_Capture())

        await engine.execute_async(plan, asyncio.Queue())

        event_names = {r["event_name"] for r in records}
        assert Event.REQUEST_PAYLOAD_TRACE not in event_names
        assert Event.UPSTREAM_ECHO_TRACE not in event_names
        assert Event.STREAM_CHUNK_TRACE not in event_names

    @pytest.mark.asyncio
    async def test_trace_events_present_at_trace_profile(self, mock_api_client, monkeypatch):
        monkeypatch.setenv("LOG_PROFILE", "TRACE")
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan()

        from src.utils.log_emitter import JSONL_LOGGER_NAME
        import logging

        jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)
        jsonl_logger.handlers.clear()
        jsonl_logger.setLevel(logging.DEBUG)
        jsonl_logger.propagate = False
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(json.loads(record.getMessage()))

        jsonl_logger.addHandler(_Capture())

        results = await engine.execute_async(plan, asyncio.Queue())

        event_names = [r["event_name"] for r in records]
        assert Event.REQUEST_PAYLOAD_TRACE in event_names
        assert Event.UPSTREAM_ECHO_TRACE in event_names
        assert Event.STREAM_CHUNK_TRACE in event_names

        # Payload trace carries the model_seed we configured
        payload_trace = next(r for r in records if r["event_name"] == Event.REQUEST_PAYLOAD_TRACE)
        assert payload_trace["payload"]["seed"] == 42

        # Upstream echo trace is redacted — the leaked-looking api_key never survives
        echo_trace = next(r for r in records if r["event_name"] == Event.UPSTREAM_ECHO_TRACE)
        assert "sk-should-never-leak" not in json.dumps(echo_trace)

        # Upstream echo never overwrites/merges into request_json
        request_json = json.loads(results[0].request_json)
        assert "generationConfig" not in request_json
        assert "echo_upstream_body" not in request_json


class TestUpstreamEchoDistinctFromPayloadTrace:
    @pytest.mark.asyncio
    async def test_payload_trace_and_upstream_echo_are_separate_events(self, mock_api_client, monkeypatch):
        monkeypatch.setenv("LOG_PROFILE", "TRACE")
        engine = ExecutionEngine(mock_api_client, AnswerRandomizer(seed=1), AnswerParser())
        plan = _build_plan()

        from src.utils.log_emitter import JSONL_LOGGER_NAME
        import logging

        jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)
        jsonl_logger.handlers.clear()
        jsonl_logger.setLevel(logging.DEBUG)
        jsonl_logger.propagate = False
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(json.loads(record.getMessage()))

        jsonl_logger.addHandler(_Capture())

        await engine.execute_async(plan, asyncio.Queue())

        payload_trace = next(r for r in records if r["event_name"] == Event.REQUEST_PAYLOAD_TRACE)
        echo_trace = next(r for r in records if r["event_name"] == Event.UPSTREAM_ECHO_TRACE)

        # Our own request never contains the upstream-specific shape
        assert "generationConfig" not in payload_trace["payload"]
        # The echo carries the upstream-transformed shape
        assert "generationConfig" in echo_trace["echo"]["echo_upstream_body"]
