"""Mandatory fidelity test: request_json must equal the payload actually
handed to the HTTP transport, byte-for-byte.

This intercepts the HTTP call at the OpenRouterClient boundary (patching
httpx.AsyncClient.post, same pattern as tests/unit/api/test_client.py) and
proves the ONE canonical payload built by ExecutionEngine reaches both
destinations identically — the whole point of
docs/status/model-seed-checkpoint-b-design.md, Part 1's centralization.

Uses a REAL OpenRouterClient (not a hand-rolled mock) so the fidelity
claim is genuine: nothing in this test's own code re-derives or re-checks
the payload independently.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.api.client import OpenRouterClient
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


DEFAULT_SSE_CHUNKS = [
    'data: {"choices": [{"delta": {"content": "Answer is (B)."}, "finish_reason": "stop"}], '
    '"usage": {"prompt_tokens": 10, "completion_tokens": 5}}',
    "data: [DONE]",
]


async def _run_single_item(
    *,
    model_config: ModelConfig,
    resolved_provider: str | None = None,
    debug_enabled: bool = False,
    sse_chunks: list[str] | None = None,
    api_key: str = "sk-super-secret-test-key",
):
    """Execute exactly one PlanItem through a real OpenRouterClient with
    the HTTP POST intercepted. Returns (ExecutionResult, sent_json,
    request_headers)."""
    client = OpenRouterClient(api_key=api_key, debug_enabled=debug_enabled)
    randomizer = AnswerRandomizer(seed=42)
    parser = AnswerParser()
    engine = ExecutionEngine(client, randomizer, parser)

    question_payload = QuestionPayload(
        stem="What is 2+2?",
        options=["3", "4", "5", "6"],
        answer_key="B",
    )
    item = PlanItem(
        item_id="run-1::var-1::snap-1::it-1",
        run_id="run-1",
        variant_id="var-1",
        snapshot_id="snap-1",
        question_id="q1",
        question_payload=question_payload,
    )
    variant = PlanVariant(
        variant_id="var-1",
        model_id="openai/gpt-4",
        model_config_effective=model_config,
        resolved_provider=resolved_provider,
    )
    prompts = Prompts(system=None, user="Answer the question.")
    plan_run = PlanRun(
        run_id="run-1",
        randomization_seed_effective=None,
        prompts_effective=prompts,
        retry_policy=RetryPolicy(),
        variants=[variant],
        items=[item],
    )
    plan = ExecutionPlan(
        plan_id="plan-1",
        created_at=datetime.now(),
        experiment_id="exp-1",
        runs=[plan_run],
    )

    chunks = sse_chunks if sse_chunks is not None else DEFAULT_SSE_CHUNKS

    with patch("src.api.client.httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_aiter_lines():
            for line in chunks:
                yield line

        mock_response.aiter_lines = mock_aiter_lines
        mock_post.return_value = mock_response

        result_queue = asyncio.Queue()
        results = await engine.execute_async(plan, result_queue)

        sent_json = mock_post.call_args.kwargs["json"]
        sent_headers = mock_post.call_args.kwargs["headers"]

    return results[0], sent_json, sent_headers


class TestFidelityCoreClaim:
    """json.loads(request_json) must equal the payload actually passed as
    json= to the POST call, in every scenario below."""

    @pytest.mark.asyncio
    async def test_no_optionals_set(self):
        result, sent_json, _ = await _run_single_item(model_config=ModelConfig())
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_all_optionals_set(self):
        model_config = ModelConfig(
            temperature=0.8,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            max_output_tokens=256,
            reasoning_effort="high",
            model_seed=42,
            structured_output=True,
        )
        result, sent_json, _ = await _run_single_item(
            model_config=model_config, resolved_provider="deepinfra/turbo"
        )
        assert json.loads(result.request_json) == sent_json
        # Sanity: the fields we set are actually present, not silently dropped
        assert sent_json["temperature"] == 0.8
        assert sent_json["seed"] == 42
        assert sent_json["response_format"] == {"type": "json_object"}
        assert sent_json["provider"] == {"only": ["deepinfra/turbo"], "allow_fallbacks": False}

    @pytest.mark.asyncio
    async def test_model_seed_none_omits_seed_from_both(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(model_seed=None)
        )
        assert "seed" not in sent_json
        assert "seed" not in json.loads(result.request_json)
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_model_seed_zero_sent_not_omitted(self):
        result, sent_json, _ = await _run_single_item(model_config=ModelConfig(model_seed=0))
        assert sent_json["seed"] == 0
        assert json.loads(result.request_json)["seed"] == 0
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_model_seed_42(self):
        result, sent_json, _ = await _run_single_item(model_config=ModelConfig(model_seed=42))
        assert sent_json["seed"] == 42
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_provider_lock(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(), resolved_provider="togethercomputer/llama"
        )
        assert sent_json["provider"] == {
            "only": ["togethercomputer/llama"],
            "allow_fallbacks": False,
        }
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_reasoning(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(reasoning_effort="high")
        )
        assert sent_json["reasoning"] == {"effort": "high"}
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_structured(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(structured_output=True)
        )
        assert sent_json["response_format"] == {"type": "json_object"}
        assert json.loads(result.request_json) == sent_json


class TestDebugFidelity:
    @pytest.mark.asyncio
    async def test_debug_off_key_absent_from_both(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(), debug_enabled=False
        )
        assert "debug" not in sent_json
        assert "debug" not in json.loads(result.request_json)
        assert json.loads(result.request_json) == sent_json

    @pytest.mark.asyncio
    async def test_debug_on_key_present_and_identical_in_both(self):
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(), debug_enabled=True
        )
        assert sent_json["debug"] == {"echo_upstream_body": True}
        assert json.loads(result.request_json)["debug"] == {"echo_upstream_body": True}
        assert json.loads(result.request_json) == sent_json


class TestUpstreamEchoDistinctFromRequestJson:
    """The echoed upstream body (returned IN THE RESPONSE when debug is on)
    must never overwrite or merge into request_json — the two represent
    different steps (our own request vs. what OpenRouter forwarded
    upstream) and must stay distinguishable."""

    @pytest.mark.asyncio
    async def test_model_seed_matches_in_payload_and_upstream_echo(self):
        # Synthetic debug chunk shaped like the real, empirically-observed
        # OpenRouter -> Google AI Studio transformation (see the smoke
        # test recorded in model-seed-checkpoint-b-design.md, Part 2).
        # Shape is provider-specific; this is illustrative, not a claim
        # that every provider echoes this exact structure.
        chunks = [
            'data: {"choices": [], "debug": {"echo_upstream_body": '
            '{"generationConfig": {"seed": 42, "temperature": 0.0}}}}',
            'data: {"choices": [{"delta": {"content": "Answer is (B)."}, '
            '"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}',
            "data: [DONE]",
        ]
        result, sent_json, _ = await _run_single_item(
            model_config=ModelConfig(model_seed=42),
            debug_enabled=True,
            sse_chunks=chunks,
        )

        # What we SENT (request_json / sent_json) carries our own "seed" field.
        assert sent_json["seed"] == 42
        assert json.loads(result.request_json) == sent_json
        assert json.loads(result.request_json)["seed"] == 42

        # What OpenRouter echoes back (response-side) is captured in
        # raw_response — NOT merged into request_json.
        assert result.raw_response is not None
        first_chunk = result.raw_response[0]
        assert first_chunk["debug"]["echo_upstream_body"]["generationConfig"]["seed"] == 42

        # request_json must never contain the upstream-specific shape
        # (generationConfig is a Gemini-native key, not an OpenRouter
        # request field — its presence in request_json would mean the
        # response overwrote the request, which must never happen).
        assert "generationConfig" not in json.loads(result.request_json)

    @pytest.mark.asyncio
    async def test_debug_related_parsing_does_not_alter_scientific_result(self):
        """A debug-enabled call still parses the normal answer correctly —
        the presence of debug data must not perturb selected_answer/
        is_correct-relevant fields."""
        chunks = [
            'data: {"choices": [], "debug": {"echo_upstream_body": {"anything": "here"}}}',
            'data: {"choices": [{"delta": {"content": "Answer is (B)."}, '
            '"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}',
            "data: [DONE]",
        ]
        result, _, _ = await _run_single_item(
            model_config=ModelConfig(), debug_enabled=True, sse_chunks=chunks
        )
        assert result.status == "success"
        assert result.selected_answer == "B"
        assert result.response_text == "Answer is (B)."

    @pytest.mark.asyncio
    async def test_malformed_debug_chunk_does_not_invalidate_normal_response(self):
        """A malformed/unexpected debug chunk shape must not fail the item
        — normal response fields are unaffected by debug-side problems."""
        chunks = [
            'data: {"choices": [], "debug": "not-a-dict-unexpected-shape"}',
            'data: {"choices": [{"delta": {"content": "Answer is (B)."}, '
            '"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}',
            "data: [DONE]",
        ]
        result, _, _ = await _run_single_item(
            model_config=ModelConfig(), debug_enabled=True, sse_chunks=chunks
        )
        assert result.status == "success"
        assert result.selected_answer == "B"


class TestSecretsNeverLeaked:
    @pytest.mark.asyncio
    async def test_api_key_absent_from_request_json_and_sent_json(self):
        result, sent_json, headers = await _run_single_item(
            model_config=ModelConfig(), api_key="sk-super-secret-test-key"
        )
        request_json_text = result.request_json
        sent_json_text = json.dumps(sent_json)

        assert "sk-super-secret-test-key" not in request_json_text
        assert "sk-super-secret-test-key" not in sent_json_text
        assert "Authorization" not in request_json_text
        assert "Authorization" not in sent_json

        # The secret DOES correctly reach the real HTTP header (that's how
        # auth is supposed to work) — just never the audited payload.
        assert headers["Authorization"] == "Bearer sk-super-secret-test-key"


class TestRepeatedAttemptFidelity:
    """A second identical attempt produces an identical payload/request_json
    pair — the input side of fidelity does not depend on call ordering or
    accumulate state across attempts."""

    @pytest.mark.asyncio
    async def test_two_independent_runs_produce_identical_payloads(self):
        model_config = ModelConfig(model_seed=42, temperature=0.5)
        result1, sent1, _ = await _run_single_item(model_config=model_config)
        result2, sent2, _ = await _run_single_item(model_config=model_config)

        assert sent1 == sent2
        assert json.loads(result1.request_json) == json.loads(result2.request_json)
