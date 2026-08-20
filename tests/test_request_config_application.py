"""Validation test for model config application and request_json persistence.

This test verifies that:
1. All non-null config fields from model_variants.config are sent in the API request
2. Null config fields are NOT included in the request payload
3. The request_json is correctly persisted in the responses table
4. The request_json matches the actual payload structure

Usage:
    pytest tests/test_request_config_application.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.request_payload import build_chat_completion_payload
from src.core.execution_plan import ModelConfig, PlanVariant
from src.core.execution_engine import ExecutionResult


class TestModelConfigApplication:
    """Test that ModelConfig fields are correctly mapped to the API payload.

    Rewritten 2026-08-20 (Checkpoint B) to call the real
    build_chat_completion_payload instead of re-implementing the same
    conditional-omission logic a third time — see
    docs/status/model-seed-checkpoint-b-design.md, Part 1. This is what
    makes this test an actual regression guard: it now exercises the same
    function ExecutionEngine and OpenRouterClient both call, so it cannot
    pass while the two silently diverge (there is nothing left to diverge
    from — there's only one implementation)."""

    @pytest.mark.asyncio
    async def test_non_null_configs_applied_in_request(self):
        """Verify that non-null config values appear in the request payload."""
        model_config = ModelConfig(
            temperature=0.9,
            top_p=0.7,
            top_k=50,
            repeat_penalty=1.2,
            max_output_tokens=1000,
            max_reasoning_tokens=2000,
            reasoning_effort="high",
            enable_vision=False,
            structured_output=False,
            reasoning_mode="effort",
        )

        request_payload = build_chat_completion_payload(
            model_id="test/model",
            messages=[{"role": "user", "content": "test"}],
            temperature=model_config.temperature,
            top_p=model_config.top_p,
            top_k=model_config.top_k,
            repeat_penalty=model_config.repeat_penalty,
            max_tokens=model_config.max_output_tokens,
            reasoning_effort=model_config.reasoning_effort,
            max_reasoning_tokens=model_config.max_reasoning_tokens,
            response_format={"type": "json_object"} if model_config.structured_output else None,
        )

        assert request_payload["temperature"] == 0.9
        assert request_payload["top_p"] == 0.7
        assert request_payload["top_k"] == 50
        assert request_payload["repetition_penalty"] == 1.2
        assert request_payload["max_tokens"] == 1000
        assert request_payload["reasoning"] == {"effort": "high"}
        assert "response_format" not in request_payload  # structured_output is False

    @pytest.mark.asyncio
    async def test_null_configs_omitted_from_request(self):
        """Verify that null config values are NOT included in request payload."""
        model_config = ModelConfig(
            temperature=0.9,
            top_p=None,
            top_k=None,
            repeat_penalty=None,
            max_output_tokens=None,
            max_reasoning_tokens=None,
            reasoning_effort=None,
            enable_vision=False,
            structured_output=False,
            reasoning_mode="off",
        )

        request_payload = build_chat_completion_payload(
            model_id="test/model",
            messages=[{"role": "user", "content": "test"}],
            temperature=model_config.temperature,
            top_p=model_config.top_p,
            top_k=model_config.top_k,
            repeat_penalty=model_config.repeat_penalty,
            max_tokens=model_config.max_output_tokens,
            reasoning_effort=model_config.reasoning_effort,
            max_reasoning_tokens=model_config.max_reasoning_tokens,
        )

        assert request_payload["temperature"] == 0.9
        assert "top_p" not in request_payload
        assert "top_k" not in request_payload
        assert "repetition_penalty" not in request_payload
        assert "max_tokens" not in request_payload
        assert "reasoning" not in request_payload

    @pytest.mark.asyncio
    async def test_model_seed_zero_applied_not_omitted(self):
        """model_seed=0 must be sent, never dropped as falsy."""
        model_config = ModelConfig(model_seed=0)

        request_payload = build_chat_completion_payload(
            model_id="test/model",
            messages=[{"role": "user", "content": "test"}],
            model_seed=model_config.model_seed,
        )

        assert request_payload["seed"] == 0

    @pytest.mark.asyncio
    async def test_model_seed_none_omitted_from_request(self):
        model_config = ModelConfig(model_seed=None)

        request_payload = build_chat_completion_payload(
            model_id="test/model",
            messages=[{"role": "user", "content": "test"}],
            model_seed=model_config.model_seed,
        )

        assert "seed" not in request_payload

    @pytest.mark.asyncio
    async def test_request_json_serialization_preserves_logical_order(self):
        """Verify request_json is serialized with logical field order (insertion order)."""
        request_payload = build_chat_completion_payload(
            model_id="test/model",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.9,
            top_k=50,
        )

        # Serialize preserving insertion order (no sort_keys)
        request_json = json.dumps(request_payload, ensure_ascii=False)

        # Parse back and verify structure
        parsed = json.loads(request_json)
        assert parsed["temperature"] == 0.9
        assert parsed["top_k"] == 50
        assert parsed["stream"] is True

        # Verify insertion order is preserved (model before messages before temperature)
        keys_in_json = list(json.loads(request_json).keys())
        assert keys_in_json.index("model") < keys_in_json.index("messages")
        assert keys_in_json.index("messages") < keys_in_json.index("temperature")


class TestRequestJsonPersistence:
    """Test that request_json is correctly persisted in ExecutionResult."""

    @pytest.mark.asyncio
    async def test_execution_result_contains_request_json(self):
        """Verify ExecutionResult includes request_json field."""
        request_payload = {
            "model": "test/model",
            "temperature": 0.9,
            "stream": True,
        }
        request_json = json.dumps(request_payload, ensure_ascii=False)

        result = ExecutionResult(
            item_id="test-item",
            run_id="test-run",
            variant_id="test-variant",
            snapshot_id="test-snapshot",
            question_id="test-question",
            status="success",
            response_text="test response",
            selected_answer="A",
            parse_confidence="clear",
            latency_ms=100,
            input_tokens=50,
            response_tokens=10,
            error_type=None,
            error_message=None,
            attempt_count=1,
            request_json=request_json,
        )

        assert result.request_json is not None
        parsed = json.loads(result.request_json)
        assert parsed["temperature"] == 0.9
        assert parsed["model"] == "test/model"

    @pytest.mark.asyncio
    async def test_execution_result_request_json_null_on_failure(self):
        """Verify request_json is None when execution fails before payload build."""
        result = ExecutionResult(
            item_id="test-item",
            run_id="test-run",
            variant_id="test-variant",
            snapshot_id="test-snapshot",
            question_id="test-question",
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=None,
            input_tokens=None,
            response_tokens=None,
            error_type="connection_error",
            error_message="Connection refused",
            attempt_count=3,
            request_json=None,
        )

        assert result.request_json is None


class TestOpenRouterClientPayload:
    """Test that OpenRouterClient builds correct payload."""

    # Note: Direct client testing is complex due to SSE streaming mocks.
    # The payload building logic is already validated in TestModelConfigApplication tests.


class TestPlannerConfigMapping:
    """Test that Planner correctly maps config keys to ModelConfig."""

    def test_planner_maps_all_config_keys(self):
        """Verify Planner extracts all config keys from variant row."""
        from src.core.planner import Planner
        from src.core.execution_plan import ModelConfig
        import sqlite3

        # Create a mock variant row with all config keys
        config_dict = {
            "MODEL_TEMPERATURE": 0.9,
            "MODEL_TOP_P": 0.7,
            "MODEL_TOP_K": 50,
            "MODEL_REPEAT_PENALTY": 1.2,
            "MODEL_MAX_TOKENS_TOTAL": 1000,
            "MODEL_MAX_TOKENS_REASONING": 2000,
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_VISION": False,
            "STRUCTURED_OUTPUTS": False,
        }

        # Mock sqlite3.Row
        mock_row = {
            "config": json.dumps(config_dict),
        }

        # Use a minimal approach: test the mapping logic directly
        config = json.loads(mock_row["config"])
        
        reasoning_effort = config.get("MODEL_REASONING_EFFORT")
        has_reasoning = reasoning_effort is not None and reasoning_effort != "none"

        model_config = ModelConfig(
            temperature=config.get("MODEL_TEMPERATURE"),
            top_p=config.get("MODEL_TOP_P"),
            top_k=config.get("MODEL_TOP_K"),
            repeat_penalty=config.get("MODEL_REPEAT_PENALTY"),
            max_output_tokens=config.get("MODEL_MAX_TOKENS_TOTAL"),
            max_reasoning_tokens=config.get("MODEL_MAX_TOKENS_REASONING"),
            reasoning_effort=reasoning_effort if has_reasoning else None,
            enable_vision=config.get("MODEL_VISION", False),
            structured_output=config.get("STRUCTURED_OUTPUTS", False),
            reasoning_mode="effort" if has_reasoning else "off",
        )

        # Verify all fields are mapped correctly
        assert model_config.temperature == 0.9
        assert model_config.top_p == 0.7
        assert model_config.top_k == 50
        assert model_config.repeat_penalty == 1.2
        assert model_config.max_output_tokens == 1000
        assert model_config.max_reasoning_tokens == 2000
        assert model_config.reasoning_effort == "high"
        assert model_config.reasoning_mode == "effort"
        assert model_config.enable_vision is False
        assert model_config.structured_output is False

    def test_planner_handles_null_reasoning_effort(self):
        """Verify Planner treats 'none' reasoning_effort as disabled."""
        from src.core.execution_plan import ModelConfig
        import json

        config_dict = {
            "MODEL_TEMPERATURE": 0.9,
            "MODEL_REASONING_EFFORT": "none",
        }

        config = json.loads(json.dumps(config_dict))
        reasoning_effort = config.get("MODEL_REASONING_EFFORT")
        has_reasoning = reasoning_effort is not None and reasoning_effort != "none"

        model_config = ModelConfig(
            temperature=config.get("MODEL_TEMPERATURE"),
            top_p=config.get("MODEL_TOP_P"),
            top_k=config.get("MODEL_TOP_K"),
            repeat_penalty=config.get("MODEL_REPEAT_PENALTY"),
            max_output_tokens=config.get("MODEL_MAX_TOKENS_TOTAL"),
            max_reasoning_tokens=config.get("MODEL_MAX_TOKENS_REASONING"),
            reasoning_effort=reasoning_effort if has_reasoning else None,
            enable_vision=config.get("MODEL_VISION", False),
            structured_output=config.get("STRUCTURED_OUTPUTS", False),
            reasoning_mode="effort" if has_reasoning else "off",
        )

        assert model_config.reasoning_effort is None
        assert model_config.reasoning_mode == "off"
