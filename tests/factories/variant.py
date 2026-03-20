"""Factory for creating ModelVariant instances in tests."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class ModelVariant:
    """ModelVariant entity for testing."""
    variant_id: str
    experiment_id: str
    model_id: str
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
        **overrides,
    ) -> ModelVariant:
        """
        Create a ModelVariant with defaults.
        
        Args:
            experiment_id: Parent experiment ID (required)
            model_id: Base model identifier
            **overrides: Any field can be overridden
        
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
        return ModelVariant(
            variant_id=overrides.get('variant_id', f"var-{uuid.uuid4().hex[:8]}"),
            experiment_id=experiment_id,
            model_id=model_id,
            is_active=overrides.get('is_active', True),
        )
