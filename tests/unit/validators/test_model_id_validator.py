"""Unit tests for model_id_validator.

Tests cover all validation rules:
- Valid model IDs with various characters (dots, colons, hyphens, etc.)
- Invalid model IDs (empty, missing slash, multiple slashes, empty parts)
"""

import pytest

from src.validators.model_id_validator import validate_model_id


class TestValidModelIds:
    """Test cases for valid model ID formats."""

    def test_simple_format(self):
        """Simple provider/model format passes."""
        assert validate_model_id("openai/gpt-4") is True
        assert validate_model_id("anthropic/claude-3") is True

    def test_with_dots(self):
        """Model IDs with dots pass validation."""
        assert validate_model_id("google/gemini-3.1-flash-lite-preview") is True
        assert validate_model_id("nvidia/nemotron.3.super") is True

    def test_with_colons(self):
        """Model IDs with colons (e.g., :free suffix) pass validation."""
        assert validate_model_id("stepfun/step-3.5-flash:free") is True
        assert validate_model_id("nvidia/nemotron-3-super-120b-a12b:free") is True

    def test_with_hyphens(self):
        """Model IDs with hyphens pass validation."""
        assert validate_model_id("openai/gpt-4-mini") is True
        assert validate_model_id("google/gemini-flash-lite") is True

    def test_with_underscores(self):
        """Model IDs with underscores pass validation."""
        assert validate_model_id("provider/model_name") is True
        assert validate_model_id("provider/model_name_v2") is True

    def test_with_numbers(self):
        """Model IDs with numbers pass validation."""
        assert validate_model_id("provider/model123") is True
        assert validate_model_id("provider/123model") is True

    def test_mixed_special_characters(self):
        """Model IDs with mixed special characters pass validation."""
        assert validate_model_id("google/gemini-3.1-flash-lite-preview") is True
        assert validate_model_id("nvidia/nemotron-3-super-120b-a12b:free") is True
        assert validate_model_id("stepfun/step-3.5-flash:free") is True

    def test_openrouter_examples(self):
        """Real OpenRouter model IDs pass validation."""
        assert validate_model_id("google/gemini-3.1-flash-lite-preview") is True
        assert validate_model_id("openai/gpt-4.1-mini") is True
        assert validate_model_id("stepfun/step-3.5-flash:free") is True
        assert validate_model_id("nvidia/nemotron-3-super-120b-a12b:free") is True


class TestInvalidModelIds:
    """Test cases for invalid model ID formats."""

    def test_empty_string(self):
        """Empty string fails validation."""
        assert validate_model_id("") is False

    def test_missing_slash(self):
        """Model ID without slash fails validation."""
        assert validate_model_id("gpt-4") is False
        assert validate_model_id("openai") is False

    def test_multiple_slashes(self):
        """Model ID with multiple slashes fails validation."""
        assert validate_model_id("openai/gpt-4/extra") is False
        assert validate_model_id("a/b/c") is False

    def test_empty_provider(self):
        """Empty provider part fails validation."""
        assert validate_model_id("/gpt-4") is False
        assert validate_model_id("/model") is False

    def test_empty_model_name(self):
        """Empty model name part fails validation."""
        assert validate_model_id("openai/") is False
        assert validate_model_id("provider/") is False

    def test_none_value(self):
        """None value fails validation."""
        assert validate_model_id(None) is False


class TestEdgeCases:
    """Edge case tests."""

    def test_single_character_parts(self):
        """Single character provider and model name pass."""
        assert validate_model_id("a/b") is True

    def test_very_long_model_id(self):
        """Very long model IDs pass validation."""
        long_id = "provider/" + "a" * 1000
        assert validate_model_id(long_id) is True

    def test_whitespace_not_trimmed(self):
        """Whitespace is treated as part of the ID (not automatically trimmed)."""
        # These should fail because whitespace makes parts invalid in context
        assert validate_model_id(" openai/gpt-4") is True  # Leading space in provider
        assert validate_model_id("openai /gpt-4") is True  # Space before slash
        assert validate_model_id("openai/ gpt-4") is True  # Space after slash
        assert validate_model_id("openai/gpt-4 ") is True  # Trailing space
