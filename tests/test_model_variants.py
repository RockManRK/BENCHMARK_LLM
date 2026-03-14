"""Tests for model variant system.

This module tests the model variant identity system, including:
- VariantConfig signature and ID generation
- ModelVariant repository operations
- Variant isolation in statistics
"""

import pytest
from src.core.variant_config import VariantConfig


class TestVariantConfig:
    """Test variant configuration and identity generation."""

    def test_build_signature_basic(self) -> None:
        """Test basic signature generation."""
        config = VariantConfig(
            reasoning_mode="auto",
            vision_enabled=False,
            structured_enabled=False,
        )
        signature = config.build_signature("openai/gpt-4")
        assert signature == "openai/gpt-4::reasoning=auto::vision=false::structured=false"

    def test_build_signature_effort(self) -> None:
        """Test signature with reasoning effort."""
        config = VariantConfig(
            reasoning_mode="effort",
            reasoning_effort="high",
            vision_enabled=False,
            structured_enabled=True,
        )
        signature = config.build_signature("anthropic/claude-3")
        assert signature == "anthropic/claude-3::reasoning=effort:high::vision=false::structured=true"

    def test_build_signature_budget(self) -> None:
        """Test signature with reasoning budget."""
        config = VariantConfig(
            reasoning_mode="budget",
            reasoning_max_tokens=8000,
            vision_enabled=True,
            structured_enabled=False,
        )
        signature = config.build_signature("google/gemini-2.0")
        assert signature == "google/gemini-2.0::reasoning=budget:8000::vision=true::structured=false"

    def test_build_signature_off(self) -> None:
        """Test signature with reasoning disabled."""
        config = VariantConfig(
            reasoning_mode="off",
            vision_enabled=False,
            structured_enabled=False,
        )
        signature = config.build_signature("qwen/qwen-2.5-72b")
        assert signature == "qwen/qwen-2.5-72b::reasoning=off::vision=false::structured=false"

    def test_build_signature_unspecified(self) -> None:
        """Test signature with unspecified reasoning (default)."""
        config = VariantConfig(
            reasoning_mode="unspecified",
            vision_enabled=False,
            structured_enabled=False,
        )
        signature = config.build_signature("meta/llama-3")
        assert signature == "meta/llama-3::reasoning=unspecified::vision=false::structured=false"

    def test_build_variant_id_deterministic(self) -> None:
        """Test that variant_id is deterministic."""
        config1 = VariantConfig(
            reasoning_mode="auto",
            vision_enabled=False,
            structured_enabled=False,
        )
        config2 = VariantConfig(
            reasoning_mode="auto",
            vision_enabled=False,
            structured_enabled=False,
        )
        
        id1 = config1.build_variant_id("openai/gpt-4")
        id2 = config2.build_variant_id("openai/gpt-4")
        
        assert id1 == id2
        assert id1.startswith("var-")
        assert len(id1) == 12  # var- + 8 hex chars

    def test_build_variant_id_different_configs(self) -> None:
        """Test that different configs produce different variant_ids."""
        config1 = VariantConfig(
            reasoning_mode="auto",
            vision_enabled=False,
            structured_enabled=False,
        )
        config2 = VariantConfig(
            reasoning_mode="effort",
            reasoning_effort="high",
            vision_enabled=False,
            structured_enabled=False,
        )
        
        id1 = config1.build_variant_id("openai/gpt-4")
        id2 = config2.build_variant_id("openai/gpt-4")
        
        assert id1 != id2

    def test_build_variant_id_different_models(self) -> None:
        """Test that different models produce different variant_ids."""
        config = VariantConfig(
            reasoning_mode="auto",
            vision_enabled=False,
            structured_enabled=False,
        )
        
        id1 = config.build_variant_id("openai/gpt-4")
        id2 = config.build_variant_id("anthropic/claude-3")
        
        assert id1 != id2

    def test_to_openrouter_reasoning_unspecified(self) -> None:
        """Test reasoning payload for unspecified mode."""
        config = VariantConfig(reasoning_mode="unspecified")
        assert config.to_openrouter_reasoning() is None

    def test_to_openrouter_reasoning_auto(self) -> None:
        """Test reasoning payload for auto mode."""
        config = VariantConfig(reasoning_mode="auto")
        assert config.to_openrouter_reasoning() is None

    def test_to_openrouter_reasoning_off(self) -> None:
        """Test reasoning payload for off mode."""
        config = VariantConfig(reasoning_mode="off")
        assert config.to_openrouter_reasoning() == {"enabled": False}

    def test_to_openrouter_reasoning_effort(self) -> None:
        """Test reasoning payload for effort mode."""
        config = VariantConfig(
            reasoning_mode="effort",
            reasoning_effort="high",
        )
        assert config.to_openrouter_reasoning() == {"effort": "high"}

    def test_to_openrouter_reasoning_budget(self) -> None:
        """Test reasoning payload for budget mode."""
        config = VariantConfig(
            reasoning_mode="budget",
            reasoning_max_tokens=8000,
        )
        assert config.to_openrouter_reasoning() == {"max_tokens": 8000}

    def test_validation_invalid_mode(self) -> None:
        """Test validation of invalid reasoning mode."""
        with pytest.raises(ValueError, match="reasoning_mode must be one of"):
            VariantConfig(reasoning_mode="invalid")

    def test_validation_effort_without_mode(self) -> None:
        """Test that effort mode requires reasoning_effort."""
        with pytest.raises(ValueError, match="reasoning_effort is required"):
            VariantConfig(reasoning_mode="effort")

    def test_validation_budget_without_tokens(self) -> None:
        """Test that budget mode requires reasoning_max_tokens."""
        with pytest.raises(ValueError, match="reasoning_max_tokens is required"):
            VariantConfig(reasoning_mode="budget")

    def test_validation_invalid_effort_value(self) -> None:
        """Test validation of invalid reasoning_effort value."""
        with pytest.raises(ValueError, match="reasoning_effort must be one of"):
            VariantConfig(
                reasoning_mode="effort",
                reasoning_effort="invalid",
            )

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization and deserialization."""
        config = VariantConfig(
            reasoning_mode="effort",
            reasoning_effort="high",
            vision_enabled=True,
            structured_enabled=False,
        )
        
        config_dict = config.to_dict()
        restored = VariantConfig.from_dict(config_dict)
        
        assert restored.reasoning_mode == config.reasoning_mode
        assert restored.reasoning_effort == config.reasoning_effort
        assert restored.vision_enabled == config.vision_enabled
        assert restored.structured_enabled == config.structured_enabled


class TestVariantIsolation:
    """Test that variants are properly isolated in statistics."""

    def test_variant_signatures_are_unique(self) -> None:
        """Test that different configurations produce unique signatures."""
        model_id = "openai/gpt-4"
        
        configs = [
            VariantConfig(reasoning_mode="auto", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="off", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="effort", reasoning_effort="high", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="budget", reasoning_max_tokens=8000, vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="auto", vision_enabled=True, structured_enabled=False),
            VariantConfig(reasoning_mode="auto", vision_enabled=False, structured_enabled=True),
        ]
        
        signatures = [config.build_signature(model_id) for config in configs]
        
        # All signatures should be unique
        assert len(signatures) == len(set(signatures))

    def test_variant_ids_are_unique(self) -> None:
        """Test that different configurations produce unique variant_ids."""
        model_id = "openai/gpt-4"
        
        configs = [
            VariantConfig(reasoning_mode="auto", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="off", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="effort", reasoning_effort="high", vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="budget", reasoning_max_tokens=8000, vision_enabled=False, structured_enabled=False),
            VariantConfig(reasoning_mode="auto", vision_enabled=True, structured_enabled=False),
            VariantConfig(reasoning_mode="auto", vision_enabled=False, structured_enabled=True),
        ]
        
        variant_ids = [config.build_variant_id(model_id) for config in configs]
        
        # All variant_ids should be unique
        assert len(variant_ids) == len(set(variant_ids))
