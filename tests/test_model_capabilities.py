"""Tests for the model capabilities module.

This module tests the model capability checker, including
vision support detection and capability caching.
"""

from typing import Any

import pytest
from pytest_mock import MockerFixture

from src.api.model_capabilities import (
    ModelCapabilities,
    ModelCapabilityChecker,
    VisionSupport,
)


@pytest.fixture
def checker() -> ModelCapabilityChecker:
    """Create a ModelCapabilityChecker instance for testing."""
    return ModelCapabilityChecker()


@pytest.fixture
def vision_models() -> list[str]:
    """List of models known to support vision."""
    return [
        "openai/gpt-4-vision",
        "openai/gpt-4o",
        "anthropic/claude-3-opus",
        "anthropic/claude-3-sonnet",
        "anthropic/claude-3-haiku",
        "google/gemini-pro-vision",
    ]


@pytest.fixture
def text_only_models() -> list[str]:
    """List of models known to be text-only."""
    return [
        "openai/gpt-3.5-turbo",
        "openai/gpt-4",
        "anthropic/claude-2",
        "meta/llama-2-70b",
        "mistral/mistral-7b",
    ]


class TestModelCapabilities:
    """Test cases for ModelCapabilities dataclass."""

    def test_model_capabilities_creation(self) -> None:
        """Test creating a ModelCapabilities instance."""
        capabilities = ModelCapabilities(
            model_id="openai/gpt-4-vision",
            supports_vision=True,
            max_image_size_mb=20,
            supported_image_formats=["png", "jpg", "jpeg"],
        )
        
        assert capabilities.model_id == "openai/gpt-4-vision"
        assert capabilities.supports_vision is True
        assert capabilities.max_image_size_mb == 20

    def test_model_capabilities_defaults(self) -> None:
        """Test ModelCapabilities default values."""
        capabilities = ModelCapabilities(model_id="openai/gpt-3.5-turbo")
        
        assert capabilities.supports_vision is False
        assert capabilities.max_image_size_mb == 0
        assert capabilities.supported_image_formats == []


class TestVisionSupport:
    """Test cases for VisionSupport enum."""

    def test_vision_support_values(self) -> None:
        """Test VisionSupport enum values."""
        assert VisionSupport.SUPPORTED.value == "supported"
        assert VisionSupport.UNSUPPORTED.value == "unsupported"
        assert VisionSupport.UNKNOWN.value == "unknown"


class TestModelCapabilityCheckerBasic:
    """Test cases for basic model capability checking."""

    def test_checker_initialization(self, checker: ModelCapabilityChecker) -> None:
        """Test that checker initializes correctly."""
        assert checker._cache is not None
        assert len(checker._cache) == 0

    def test_check_vision_model_supports_vision(
        self, checker: ModelCapabilityChecker, vision_models: list[str]
    ) -> None:
        """Test that vision models are detected as supporting vision."""
        for model in vision_models:
            result = checker.check_vision_support(model)
            assert result == VisionSupport.SUPPORTED, f"Model {model} should support vision"

    def test_check_text_only_model_does_not_support_vision(
        self, checker: ModelCapabilityChecker, text_only_models: list[str]
    ) -> None:
        """Test that text-only models are detected as not supporting vision."""
        for model in text_only_models:
            result = checker.check_vision_support(model)
            assert result == VisionSupport.UNSUPPORTED, f"Model {model} should not support vision"

    def test_check_unknown_model_returns_unknown(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test that unknown models return unknown status."""
        result = checker.check_vision_support("unknown/model")
        assert result == VisionSupport.UNKNOWN


class TestModelCapabilityCaching:
    """Test cases for model capability caching."""

    def test_cache_populated_after_check(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test that cache is populated after checking a model."""
        model = "openai/gpt-4-vision"
        checker.check_vision_support(model)
        
        assert model in checker._cache
        assert checker._cache[model].supports_vision is True

    def test_cache_used_on_subsequent_checks(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test that cache is used on subsequent checks."""
        model = "anthropic/claude-3-opus"
        
        # First check populates cache
        checker.check_vision_support(model)
        cached_result = checker._cache[model]
        
        # Second check should use cache
        result = checker.check_vision_support(model)
        assert result == VisionSupport.SUPPORTED
        
        # Verify same object is returned from cache
        assert checker._cache[model] is cached_result

    def test_cache_prevents_repeated_lookups(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test that caching prevents repeated lookups."""
        model = "google/gemini-pro-vision"
        
        # Check multiple times
        checker.check_vision_support(model)
        checker.check_vision_support(model)
        checker.check_vision_support(model)
        
        # Should only have one cache entry
        assert model in checker._cache
        assert len(checker._cache) == 1


class TestModelCapabilityCheckerWithProvider:
    """Test cases for provider-specific capability checking."""

    def test_openai_vision_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test OpenAI vision model detection."""
        assert checker.check_vision_support("openai/gpt-4-vision") == VisionSupport.SUPPORTED
        assert checker.check_vision_support("openai/gpt-4o") == VisionSupport.SUPPORTED
        assert checker.check_vision_support("openai/gpt-4-turbo") == VisionSupport.SUPPORTED

    def test_openai_text_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test OpenAI text-only model detection."""
        assert checker.check_vision_support("openai/gpt-3.5-turbo") == VisionSupport.UNSUPPORTED
        assert checker.check_vision_support("openai/gpt-4") == VisionSupport.UNSUPPORTED

    def test_anthropic_vision_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test Anthropic vision model detection."""
        assert checker.check_vision_support("anthropic/claude-3-opus") == VisionSupport.SUPPORTED
        assert checker.check_vision_support("anthropic/claude-3-sonnet") == VisionSupport.SUPPORTED
        assert checker.check_vision_support("anthropic/claude-3-haiku") == VisionSupport.SUPPORTED

    def test_anthropic_text_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test Anthropic text-only model detection."""
        assert checker.check_vision_support("anthropic/claude-2") == VisionSupport.UNSUPPORTED
        assert checker.check_vision_support("anthropic/claude-instant") == VisionSupport.UNSUPPORTED

    def test_google_vision_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test Google vision model detection."""
        assert checker.check_vision_support("google/gemini-pro-vision") == VisionSupport.SUPPORTED
        assert checker.check_vision_support("google/gemini-1.5-pro") == VisionSupport.SUPPORTED

    def test_mistral_text_models(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test Mistral text-only model detection."""
        assert checker.check_vision_support("mistral/mistral-7b") == VisionSupport.UNSUPPORTED
        assert checker.check_vision_support("mistral/mixtral-8x7b") == VisionSupport.UNSUPPORTED


class TestGetCapabilities:
    """Test cases for get_capabilities method."""

    def test_get_capabilities_vision_model(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test getting full capabilities for vision model."""
        capabilities = checker.get_capabilities("openai/gpt-4-vision")
        
        assert capabilities.model_id == "openai/gpt-4-vision"
        assert capabilities.supports_vision is True
        assert capabilities.max_image_size_mb > 0

    def test_get_capabilities_text_model(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test getting full capabilities for text model."""
        capabilities = checker.get_capabilities("openai/gpt-3.5-turbo")
        
        assert capabilities.model_id == "openai/gpt-3.5-turbo"
        assert capabilities.supports_vision is False
        assert capabilities.max_image_size_mb == 0

    def test_get_capabilities_caches_result(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test that get_capabilities caches the result."""
        model = "anthropic/claude-3-opus"
        
        capabilities = checker.get_capabilities(model)
        
        assert model in checker._cache
        assert checker._cache[model] is capabilities


class TestIsModelCompatible:
    """Test cases for is_model_compatible method."""

    def test_is_model_compatible_vision_question(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test compatibility check for vision question."""
        # Vision model with vision question should be compatible
        assert checker.is_model_compatible("openai/gpt-4-vision", has_image=True) is True
        
        # Text model with vision question should be incompatible
        assert checker.is_model_compatible("openai/gpt-3.5-turbo", has_image=True) is False

    def test_is_model_compatible_text_question(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test compatibility check for text-only question."""
        # Both vision and text models should be compatible with text questions
        assert checker.is_model_compatible("openai/gpt-4-vision", has_image=False) is True
        assert checker.is_model_compatible("openai/gpt-3.5-turbo", has_image=False) is True

    def test_is_model_compatible_unknown_model(
        self, checker: ModelCapabilityChecker
    ) -> None:
        """Test compatibility check for unknown model."""
        # Unknown model with vision question - should be incompatible (safe default)
        assert checker.is_model_compatible("unknown/model", has_image=True) is False
        
        # Unknown model with text question - should be compatible
        assert checker.is_model_compatible("unknown/model", has_image=False) is True


class TestClearCache:
    """Test cases for cache clearing."""

    def test_clear_cache(self, checker: ModelCapabilityChecker) -> None:
        """Test that cache can be cleared."""
        # Populate cache
        checker.check_vision_support("openai/gpt-4-vision")
        checker.check_vision_support("anthropic/claude-3-opus")
        
        assert len(checker._cache) == 2
        
        # Clear cache
        checker.clear_cache()
        
        assert len(checker._cache) == 0
