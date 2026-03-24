"""Tests for variant signature generation."""

import pytest
from src_v2.utils.variant_signature import (
    generate_variant_signature,
    parse_variant_signature,
    normalize_float,
)


class TestNormalizeFloat:
    """Test float normalization."""
    
    def test_float_three_decimals(self):
        """Float values should be normalized to 3 decimal places."""
        assert normalize_float(0.8) == "0.800"
    
    def test_int_to_float(self):
        """Integer values should be converted to float with 3 decimals."""
        assert normalize_float(42) == "42.000"
    
    def test_bool(self):
        """Boolean values should be lowercase strings."""
        assert normalize_float(True) == "true"
        assert normalize_float(False) == "false"
    
    def test_string(self):
        """String values should be returned as-is."""
        assert normalize_float("low") == "low"


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
            {"reasoning_effort": "low"}
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low"
    
    def test_vision_only(self):
        """Single vision config should produce correct signature."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {"vision": True}
        )
        assert result == "gemini-3.1-flash-lite-preview|vision=true"
    
    def test_multiple_configs(self):
        """Multiple configs should produce signature in fixed field order."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            {"reasoning_effort": "xhigh", "temperature": 0.8}
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=xhigh|temp=0.800"
    
    def test_json_string_config(self):
        """JSON string config should be parsed correctly."""
        result = generate_variant_signature(
            "google/gemini-3.1-flash-lite-preview",
            '{"reasoning_effort": "high"}'
        )
        assert result == "gemini-3.1-flash-lite-preview|reasoning=high"
    
    def test_deterministic(self):
        """Same inputs should produce same output (deterministic)."""
        config = {"reasoning_effort": "low", "temperature": 0.8}
        result1 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        result2 = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result1 == result2
    
    def test_field_order(self):
        """Fields should appear in SIGNATURE_FIELD_ORDER regardless of dict order."""
        config = {
            "temperature": 0.8,
            "reasoning_effort": "low",
            "vision": True,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low|vision=true|temp=0.800"
    
    def test_none_values_skipped(self):
        """None values in config should be skipped."""
        config = {
            "reasoning_effort": "low",
            "temperature": None,
            "vision": True,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        assert result == "gemini-3.1-flash-lite-preview|reasoning=low|vision=true"
    
    def test_all_fields(self):
        """All fields should appear in correct order."""
        config = {
            "reasoning_effort": "high",
            "vision": False,
            "structured": True,
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
            "reasoning_tokens": 1024,
        }
        result = generate_variant_signature("google/gemini-3.1-flash-lite-preview", config)
        expected = (
            "gemini-3.1-flash-lite-preview|"
            "reasoning=high|"
            "vision=false|"
            "structured=true|"
            "temp=0.700|"
            "top_p=0.950|"
            "top_k=40.000|"
            "max_tokens=2048.000|"
            "reasoning_tokens=1024.000"
        )
        assert result == expected


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
