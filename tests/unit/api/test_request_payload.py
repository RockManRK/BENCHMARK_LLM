"""Unit tests for src.api.request_payload.build_chat_completion_payload.

This is the ONE canonical payload builder — see
docs/status/model-seed-checkpoint-b-design.md, Part 1. These tests cover
the builder in isolation; end-to-end fidelity (the same object reaching
both request_json and the real HTTP POST) is covered separately in
tests/unit/core/test_request_fidelity.py.
"""

import pytest

from src.api.request_payload import build_chat_completion_payload


MESSAGES = [{"role": "user", "content": "Question?"}]


class TestMinimalPayload:
    def test_minimal_payload_has_only_model_messages_stream(self):
        payload = build_chat_completion_payload(model_id="openai/gpt-4", messages=MESSAGES)

        assert payload == {
            "model": "openai/gpt-4",
            "messages": MESSAGES,
            "stream": True,
        }


class TestNoneOmission:
    """Every optional field is omitted entirely when None — never `null`."""

    @pytest.mark.parametrize(
        "kwarg,key",
        [
            ("temperature", "temperature"),
            ("top_p", "top_p"),
            ("top_k", "top_k"),
            ("repeat_penalty", "repetition_penalty"),
            ("model_seed", "seed"),
            ("max_tokens", "max_tokens"),
            ("stop", "stop"),
            ("response_format", "response_format"),
            ("provider", "provider"),
        ],
    )
    def test_field_omitted_when_none(self, kwarg, key):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES)
        assert key not in payload

    def test_debug_omitted_by_default(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES)
        assert "debug" not in payload

    def test_reasoning_omitted_when_neither_set(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES)
        assert "reasoning" not in payload


class TestFalsyValuesPreserved:
    """0 (and other falsy-but-not-None values) must never be dropped —
    only `is not None` checks are used, matching the Randomization Seed
    0-is-valid precedent."""

    def test_model_seed_zero_is_sent(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, model_seed=0)
        assert payload["seed"] == 0

    def test_top_k_zero_is_sent(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, top_k=0)
        assert payload["top_k"] == 0

    def test_temperature_zero_is_sent(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, temperature=0.0)
        assert payload["temperature"] == 0.0

    def test_model_seed_none_omits_key_entirely(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, model_seed=None)
        assert "seed" not in payload


class TestFieldOrder:
    def test_full_payload_field_order(self):
        payload = build_chat_completion_payload(
            model_id="openai/gpt-4",
            messages=MESSAGES,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            max_tokens=512,
            reasoning_effort="high",
            model_seed=42,
            provider={"only": ["deepinfra/turbo"], "allow_fallbacks": False},
            response_format={"type": "json_object"},
            debug_enabled=True,
        )
        assert list(payload.keys()) == [
            "model",
            "messages",
            "response_format",
            "stream",
            "max_tokens",
            "temperature",
            "top_p",
            "top_k",
            "repetition_penalty",
            "seed",
            "reasoning",
            "provider",
            "debug",
        ]


class TestReasoningConflict:
    def test_effort_wins_when_both_set(self):
        payload = build_chat_completion_payload(
            model_id="m",
            messages=MESSAGES,
            reasoning_effort="high",
            max_reasoning_tokens=2000,
        )
        assert payload["reasoning"] == {"effort": "high"}

    def test_effort_only(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, reasoning_effort="low")
        assert payload["reasoning"] == {"effort": "low"}

    def test_max_tokens_only(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, max_reasoning_tokens=1000)
        assert payload["reasoning"] == {"max_tokens": 1000}


class TestProviderLockShape:
    def test_provider_shape_passed_through_unmodified(self):
        provider = {"only": ["deepinfra/turbo"], "allow_fallbacks": False}
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, provider=provider)
        assert payload["provider"] == provider
        assert payload["provider"] is provider  # not copied/rebuilt


class TestDebugField:
    def test_debug_enabled_adds_echo_upstream_body_true(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, debug_enabled=True)
        assert payload["debug"] == {"echo_upstream_body": True}

    def test_debug_disabled_by_default(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES)
        assert "debug" not in payload


class TestRepeatPenaltyFieldRename:
    def test_repeat_penalty_sent_as_repetition_penalty(self):
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, repeat_penalty=1.2)
        assert payload["repetition_penalty"] == 1.2
        assert "repeat_penalty" not in payload


class TestModelSeedNeverConflatedWithRandomizationSeed:
    def test_payload_has_no_randomization_seed_key(self):
        """Randomization Seed must never appear in the API payload under
        any name — this builder doesn't even accept a randomization_seed
        parameter, so this is really a documentation-anchoring test."""
        payload = build_chat_completion_payload(model_id="m", messages=MESSAGES, model_seed=7)
        assert "randomization_seed" not in payload
        assert "RANDOMIZATION_SEED" not in payload
        assert payload["seed"] == 7
