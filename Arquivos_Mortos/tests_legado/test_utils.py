"""Test utilities for model variant system.

This module provides helper functions for creating test data
with proper model variant support.
"""

from src.core.variant_config import VariantConfig


def create_test_variant_id(
    model_id: str = "test-model",
    reasoning_mode: str = "unspecified",
    reasoning_effort: str | None = None,
    reasoning_max_tokens: int | None = None,
    vision_enabled: bool = False,
    structured_enabled: bool = False,
) -> str:
    """Generate a deterministic variant_id for tests.

    This function creates a VariantConfig and generates the variant_id,
    ensuring consistency across tests.

    Args:
        model_id: Base model identifier.
        reasoning_mode: Reasoning mode ('unspecified', 'auto', 'off', 'effort', 'budget').
        reasoning_effort: Reasoning effort (when mode='effort').
        reasoning_max_tokens: Reasoning max tokens (when mode='budget').
        vision_enabled: Whether vision is enabled.
        structured_enabled: Whether structured outputs are enabled.

    Returns:
        Deterministic variant_id string (e.g., "var-a1b2c3d4").

    Example:
        >>> variant_id = create_test_variant_id("openai/gpt-4", reasoning_mode="auto")
        >>> print(variant_id)
        var-a1b2c3d4
    """
    config = VariantConfig(
        reasoning_mode=reasoning_mode,
        reasoning_effort=reasoning_effort,
        reasoning_max_tokens=reasoning_max_tokens,
        vision_enabled=vision_enabled,
        structured_enabled=structured_enabled,
    )
    return config.build_variant_id(model_id)


def create_test_variant_signature(
    model_id: str = "test-model",
    reasoning_mode: str = "unspecified",
    reasoning_effort: str | None = None,
    reasoning_max_tokens: int | None = None,
    vision_enabled: bool = False,
    structured_enabled: bool = False,
) -> str:
    """Generate a human-readable variant_signature for tests.

    Args:
        model_id: Base model identifier.
        reasoning_mode: Reasoning mode.
        reasoning_effort: Reasoning effort (when mode='effort').
        reasoning_max_tokens: Reasoning max tokens (when mode='budget').
        vision_enabled: Whether vision is enabled.
        structured_enabled: Whether structured outputs are enabled.

    Returns:
        Human-readable variant_signature string.

    Example:
        >>> signature = create_test_variant_signature("openai/gpt-4", reasoning_mode="auto")
        >>> print(signature)
        openai/gpt-4::reasoning=auto::vision=false::structured=false
    """
    config = VariantConfig(
        reasoning_mode=reasoning_mode,
        reasoning_effort=reasoning_effort,
        reasoning_max_tokens=reasoning_max_tokens,
        vision_enabled=vision_enabled,
        structured_enabled=structured_enabled,
    )
    return config.build_signature(model_id)


# Pre-defined variant IDs for common test scenarios
VARIANT_AUTO = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="unspecified",
    vision_enabled=False,
    structured_enabled=False,
)

VARIANT_OFF = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="off",
    vision_enabled=False,
    structured_enabled=False,
)

VARIANT_HIGH_EFFORT = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="effort",
    reasoning_effort="high",
    vision_enabled=False,
    structured_enabled=False,
)

VARIANT_BUDGET_8K = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="budget",
    reasoning_max_tokens=8000,
    vision_enabled=False,
    structured_enabled=False,
)

VARIANT_VISION = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="unspecified",
    vision_enabled=True,
    structured_enabled=False,
)

VARIANT_STRUCTURED = create_test_variant_id(
    model_id="test-model",
    reasoning_mode="unspecified",
    vision_enabled=False,
    structured_enabled=True,
)
