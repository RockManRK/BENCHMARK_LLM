"""Tests for variant signature generation."""

import pytest
from src.utils.variant_signature import (
    generate_variant_signature,
    parse_variant_signature,
    normalize_float,
    SIGNATURE_FIELD_ORDER,
)


class TestNormalizeFloat:
    """Test float normalization."""

    def test_float_minimal(self):
        """Float values should be normalized to minimal representation."""
        assert normalize_float(0.8) == "0.8"

    def test_int_to_string(self):
        """Integer values should be converted without decimal point."""
        assert normalize_float(42) == "42"

    def test_bool(self):
        """Boolean values should be lowercase strings."""
        assert normalize_float(True) == "true"
        assert normalize_float(False) == "false"

    def test_string(self):
        """String values should be returned as-is."""
        assert normalize_float("low") == "low"

    def test_integer_like_float(self):
        """Float values that are whole numbers should render as integers."""
        assert normalize_float(1000.0) == "1000"

    def test_trailing_zeros_stripped(self):
        """Float values should have trailing zeros stripped."""
        assert normalize_float(0.400) == "0.4"
        assert normalize_float(0.950) == "0.95"


class TestGenerateVariantSignature:
    """Test signature generation."""

    def test_no_config(self):
        """Empty config should return just the model name."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {}
        )
        assert result == "gemini-3.1-flash-lite-preview"

    def test_reasoning_only(self):
        """Single reasoning_effort config should produce correct signature."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {"MODEL_REASONING_EFFORT": "low"}
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low"

    def test_vision_only(self):
        """Single vision config should produce correct signature."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {"MODEL_VISION": True}
        )
        assert result == "gemini-3.1-flash-lite-preview|vision=true"

    def test_multiple_configs(self):
        """Multiple configs should produce signature in fixed field order."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {"MODEL_REASONING_EFFORT": "xhigh", "MODEL_TEMPERATURE": 0.8}
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=xhigh|temp=0.8"

    def test_json_string_config(self):
        """JSON string config should be parsed correctly."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            '{"MODEL_REASONING_EFFORT": "high"}'
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=high"

    def test_deterministic(self):
        """Same inputs should produce same output (deterministic)."""
        config = {"MODEL_REASONING_EFFORT": "low", "MODEL_TEMPERATURE": 0.8}
        result1 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        result2 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result1 == result2

    def test_field_order(self):
        """Fields should appear in SIGNATURE_FIELD_ORDER regardless of dict order."""
        config = {
            "MODEL_TEMPERATURE": 0.8,
            "MODEL_REASONING_EFFORT": "low",
            "MODEL_VISION": True,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low|vision=true|temp=0.8"

    def test_none_values_skipped(self):
        """None values in config should be skipped."""
        config = {
            "MODEL_REASONING_EFFORT": "low",
            "MODEL_TEMPERATURE": None,
            "MODEL_VISION": True,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low|vision=true"

    def test_empty_string_values_skipped(self):
        """Empty string values should be treated as unset and skipped."""
        config = {
            "MODEL_REASONING_EFFORT": "",
            "MODEL_TEMPERATURE": 0.7,
            "MODEL_VISION": True,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        # Empty reasoning should be omitted, same as None
        assert result == "gemini-3.1-flash-lite-preview|vision=true|temp=0.7"
        assert "reasoning=" not in result

    def test_all_fields(self):
        """All fields should appear in correct order."""
        config = {
            "MODEL_REASONING_EFFORT": "high",
            "MODEL_VISION": False,
            "STRUCTURED_OUTPUTS": True,
            "MODEL_TEMPERATURE": 0.7,
            "MODEL_TOP_P": 0.95,
            "MODEL_TOP_K": 40,
            "MODEL_MAX_TOKENS_TOTAL": 2048,
            "MODEL_MAX_TOKENS_REASONING": 1024,
            "PROVIDER": "deepinfra/turbo",
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        expected = (
            "gemini-3.1-flash-lite-preview|"
            "reasoning=high|"
            "vision=false|"
            "structured=true|"
            "temp=0.7|"
            "top_p=0.95|"
            "top_k=40|"
            "max_tokens=2048|"
            "reasoning_tokens=1024|"
            "provider=deepinfra/turbo"
        )
        assert result == expected

    def test_provider_differentiation(self):
        """Different PROVIDER values should produce different signatures.

        This test ensures that variants with same model_id and config but
        different providers generate unique signatures, preventing collisions.
        """
        base_config = {
            "MODEL_TEMPERATURE": 0.7,
        }

        # Same model, same config, different providers
        sig1 = generate_variant_signature("openai/gpt-4", {**base_config, "PROVIDER": "deepinfra/turbo"})
        sig2 = generate_variant_signature("openai/gpt-4", {**base_config, "PROVIDER": "together"})
        sig3 = generate_variant_signature("openai/gpt-4", base_config)  # No provider

        # All signatures should be different
        assert sig1 != sig2
        assert sig1 != sig3
        assert sig2 != sig3

        # Verify provider appears in signature
        assert "provider=deepinfra/turbo" in sig1
        assert "provider=together" in sig2
        assert "provider=" not in sig3


class TestModelSeedInSignature:
    """Model Seed (Checkpoint B) participation in variant_signature.
    Documented position: directly after repeat_penalty. Pre-production
    system, test data only — no back-compat handling for previously-stored
    signatures (per ADR-003), so this only tests newly-generated
    signatures."""

    def test_stable_field_order(self):
        """Regression guard for the full, mandatory field order itself —
        catches any accidental reordering, not just missing/extra fields."""
        assert SIGNATURE_FIELD_ORDER == [
            ('MODEL_REASONING_EFFORT', 'reasoning'),
            ('MODEL_VISION', 'vision'),
            ('STRUCTURED_OUTPUTS', 'structured'),
            ('MODEL_TEMPERATURE', 'temp'),
            ('MODEL_TOP_P', 'top_p'),
            ('MODEL_TOP_K', 'top_k'),
            ('MODEL_REPEAT_PENALTY', 'repeat_penalty'),
            ('MODEL_SEED', 'model_seed'),
            ('MODEL_MAX_TOKENS_TOTAL', 'max_tokens'),
            ('MODEL_MAX_TOKENS_REASONING', 'reasoning_tokens'),
            ('PROVIDER', 'provider'),
            ('BASE_URL', 'base_url'),
        ]

    def test_model_seed_only(self):
        result = generate_variant_signature("openai/gpt-4", {"MODEL_SEED": 42})
        assert result == "gpt-4|model_seed=42"

    def test_model_seed_appears_after_repeat_penalty(self):
        config = {
            "MODEL_REPEAT_PENALTY": 1.2,
            "MODEL_SEED": 42,
            "MODEL_MAX_TOKENS_TOTAL": 2048,
        }
        result = generate_variant_signature("openai/gpt-4", config)
        assert result == "gpt-4|repeat_penalty=1.2|model_seed=42|max_tokens=2048"

    def test_model_seed_zero_included_not_treated_as_unset(self):
        """0 is a valid Model Seed — must not be skipped like None/''."""
        result = generate_variant_signature("openai/gpt-4", {"MODEL_SEED": 0})
        assert result == "gpt-4|model_seed=0"

    def test_model_seed_none_skipped(self):
        result = generate_variant_signature("openai/gpt-4", {"MODEL_SEED": None, "MODEL_TEMPERATURE": 0.7})
        assert "model_seed=" not in result

    def test_differing_only_by_model_seed_produces_different_signatures(self):
        """Two variants differing ONLY by --model-seed must not collide —
        direct analogue of the repeat_penalty/base_url collision-regression
        tests already covering this exact class of bug."""
        base_config = {"MODEL_TEMPERATURE": 0.7}

        sig1 = generate_variant_signature("openai/gpt-4", {**base_config, "MODEL_SEED": 42})
        sig2 = generate_variant_signature("openai/gpt-4", {**base_config, "MODEL_SEED": 99})
        sig3 = generate_variant_signature("openai/gpt-4", base_config)  # no seed at all

        assert sig1 != sig2
        assert sig1 != sig3
        assert sig2 != sig3

    def test_model_seed_never_conflated_with_randomization_seed_key(self):
        """RANDOMIZATION_SEED must never participate in variant_signature —
        total separation between the two seed concepts."""
        config = {"RANDOMIZATION_SEED": 7, "MODEL_SEED": 42}
        result = generate_variant_signature("openai/gpt-4", config)
        assert result == "gpt-4|model_seed=42"  # RANDOMIZATION_SEED=7 never appears


class TestParseVariantSignature:
    """Test signature parsing (for debugging)."""
    
    def test_parse_simple(self):
        """Simple signature without config should parse correctly."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview")
        assert result == {"model_name": "gemini-3.1-flash-lite-preview", "config": {}}
    
    def test_parse_reasoning(self):
        """Signature with reasoning should parse correctly."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview|reasoning=low")
        assert result["model_name"] == "gemini-3.1-flash-lite-preview"
        assert result["config"]["reasoning"] == "low"
    
    def test_parse_multiple(self):
        """Signature with multiple configs should parse correctly."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview|reasoning=xhigh|temp=0.800")
        assert result["model_name"] == "gemini-3.1-flash-lite-preview"
        assert result["config"]["reasoning"] == "xhigh"
        assert result["config"]["temp"] == 0.8
    
    def test_parse_boolean_values(self):
        """Boolean values should parse to Python bool."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview|vision=true|structured=false")
        assert result["config"]["vision"] is True
        assert result["config"]["structured"] is False
    
    def test_parse_integer_values(self):
        """Integer values should parse to Python int."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview|top_k=40")
        assert result["config"]["top_k"] == 40
    
    def test_parse_float_values(self):
        """Float values should parse to Python float."""
        result = parse_variant_signature("gemini-3.1-flash-lite-preview|temp=0.800")
        assert result["config"]["temp"] == 0.8


class TestV8ContractKeysOnly:
    """V8: Verify signature uses only contract keys, no hardcoded defaults.

    This test suite ensures that:
    - Only explicit config keys are used (MODEL_* prefix)
    - No hardcoded dataset paths
    - No hidden defaults - only what's passed in config
    """

    def test_uses_contract_keys_with_model_prefix(self):
        """Signature should use MODEL_* contract keys from config."""
        config = {
            'MODEL_REASONING_EFFORT': 'low',
            'MODEL_TEMPERATURE': 0.7,
            'MODEL_VISION': True,
        }
        result = generate_variant_signature('openai/gpt-4', config)
        # Should use the config values, not hardcoded defaults
        assert 'reasoning=low' in result
        assert 'temp=0.7' in result
        assert 'vision=true' in result

    def test_no_hardcoded_defaults(self):
        """Signature should only include what's explicitly in config."""
        # Empty config should produce minimal signature
        result = generate_variant_signature('openai/gpt-4', {})
        assert result == 'gpt-4'
        
        # Single key should produce single field
        result = generate_variant_signature('openai/gpt-4', {'MODEL_VISION': True})
        assert result == 'gpt-4|vision=true'

    def test_skips_missing_keys(self):
        """Missing config keys should be skipped, not defaulted."""
        config = {
            'MODEL_REASONING_EFFORT': 'high',
            # MODEL_TEMPERATURE is missing - should be skipped
        }
        result = generate_variant_signature('openai/gpt-4', config)
        assert 'reasoning=high' in result
        assert 'temp=' not in result

    def test_none_values_not_hardcoded(self):
        """None values should be skipped, not replaced with defaults."""
        config = {
            'MODEL_REASONING_EFFORT': None,
            'MODEL_TEMPERATURE': None,
            'MODEL_VISION': True,
        }
        result = generate_variant_signature('openai/gpt-4', config)
        # Only vision should appear (non-None value)
        assert result == 'gpt-4|vision=true'

    def test_empty_string_not_hardcoded(self):
        """Empty string values should be skipped, not rendered as empty."""
        config = {
            'MODEL_REASONING_EFFORT': '',
            'MODEL_TEMPERATURE': 0.7,
            'MODEL_VISION': True,
        }
        result = generate_variant_signature('openai/gpt-4', config)
        # Empty reasoning should not appear
        assert 'reasoning=' not in result
        assert 'temp=0.7' in result
        assert 'vision=true' in result

    def test_config_from_variant_config_column(self):
        """Simulate real usage: config comes from variant.config JSON.

        This test verifies that the signature generation uses the config
        directly from the contract (model_variants.config column), with
        no hardcoded paths or defaults.
        """
        import json
        
        # Simulate config from database (variant.config column)
        variant_config_json = json.dumps({
            'MODEL_REASONING_EFFORT': 'xhigh',
            'MODEL_TEMPERATURE': 0.9,
            'MODEL_VISION': False,
            'MODEL_MAX_TOKENS_TOTAL': 4096,
        })
        variant_config = json.loads(variant_config_json)
        
        result = generate_variant_signature('google/gemini-pro', variant_config)
        
        # All values should come from config, no hardcoded defaults
        assert 'reasoning=xhigh' in result
        assert 'temp=0.9' in result
        assert 'vision=false' in result
        assert 'max_tokens=4096' in result
