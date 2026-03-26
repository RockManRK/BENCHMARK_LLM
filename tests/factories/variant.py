"""Factory for creating ModelVariant instances in tests."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class ModelVariant:
    """ModelVariant entity for testing.
    
    Matches src.db.models.ModelVariant structure.
    """
    variant_id: str
    experiment_id: str
    model_id: str
    variant_signature: str
    reasoning_mode: str = "off"
    reasoning_effort: Optional[str] = None
    max_output_tokens: Optional[int] = None
    vision_enabled: bool = False
    structured_output: bool = False
    web_access_enabled: bool = False
    created_at: Optional[str] = None
    is_active: bool = True


class VariantFactory:
    """Factory for creating ModelVariant instances in tests.

    This factory provides sensible defaults and allows customization
    through overrides. It returns dataclass instances, not database records.

    Example:
        # Basic usage
        variant = VariantFactory.create(experiment_id="exp-123")

        # With overrides
        variant = VariantFactory.create(
            experiment_id="exp-123",
            model_id="openai/gpt-4",
            is_active=False,
        )

        # In a test
        def test_variant_creation(in_memory_db):
            variant = VariantFactory.create(experiment_id="exp-123")
            repo = VariantRepository(in_memory_db)
            repo.save(variant)
    """

    @staticmethod
    def create(
        experiment_id: str,
        model_id: str = "openai/gpt-4",
        variant_id: Optional[str] = None,
        variant_signature: Optional[str] = None,
        reasoning_mode: str = "off",
        reasoning_effort: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        vision_enabled: bool = False,
        structured_output: bool = False,
        web_access_enabled: bool = False,
        is_active: bool = True,
    ) -> ModelVariant:
        """
        Create a ModelVariant with defaults.

        Args:
            experiment_id: Parent experiment ID (required)
            model_id: Base model identifier
            variant_id: Unique ID (auto-generated if None)
            variant_signature: Human-readable identity (auto-generated if None)
            reasoning_mode: Reasoning mode
            reasoning_effort: Reasoning effort level
            max_output_tokens: Max tokens for budget mode
            vision_enabled: Enable vision capabilities
            structured_output: Enable structured output
            web_access_enabled: Enable web access
            is_active: Whether the variant is active

        Returns:
            ModelVariant instance

        Example:
            >>> variant = VariantFactory.create(
            ...     experiment_id="exp-123",
            ...     model_id="anthropic/claude-3",
            ... )
            >>> variant.experiment_id
            'exp-123'
            >>> variant.model_id
            'anthropic/claude-3'
        """
        if variant_id is None:
            variant_id = f"var-{uuid.uuid4().hex[:8]}"

        if variant_signature is None:
            variant_signature = model_id.replace('/', '_')

        return ModelVariant(
            variant_id=variant_id,
            experiment_id=experiment_id,
            model_id=model_id,
            variant_signature=variant_signature,
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            max_output_tokens=max_output_tokens,
            vision_enabled=vision_enabled,
            structured_output=structured_output,
            web_access_enabled=web_access_enabled,
            is_active=is_active,
        )
