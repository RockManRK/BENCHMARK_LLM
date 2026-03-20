"""Factory for creating Experiment instances in tests."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class Experiment:
    """Experiment entity for testing."""
    experiment_id: str
    name: str
    system_prompt: str
    user_prompt: str
    is_active: bool = True


class ExperimentFactory:
    """Factory for creating Experiment instances in tests.
    
    This factory provides sensible defaults and allows customization
    through overrides. It returns dataclass instances, not database records.
    
    Example:
        # Basic usage
        experiment = ExperimentFactory.create(name="my-experiment")
        
        # With overrides
        experiment = ExperimentFactory.create(
            name="custom-experiment",
            system_prompt="Custom system prompt",
            is_active=False,
        )
        
        # In a test
        def test_experiment_creation(in_memory_db):
            experiment = ExperimentFactory.create(name="test-exp")
            repo = ExperimentRepository(in_memory_db)
            repo.save(experiment)
    """

    @staticmethod
    def create(
        name: Optional[str] = None,
        system_prompt: str = "You are a helpful assistant.",
        user_prompt: str = "Answer the question.",
        **overrides,
    ) -> Experiment:
        """
        Create an Experiment with defaults.
        
        Args:
            name: Experiment name (auto-generated if None)
            system_prompt: System prompt template
            user_prompt: User prompt template
            **overrides: Any field can be overridden
        
        Returns:
            Experiment instance
        
        Example:
            >>> exp = ExperimentFactory.create(name="math-benchmark")
            >>> exp.name
            'math-benchmark'
            >>> exp.is_active
            True
        """
        return Experiment(
            experiment_id=overrides.get('experiment_id', f"exp-{uuid.uuid4().hex[:8]}"),
            name=name or f"experiment-{uuid.uuid4().hex[:8]}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            is_active=overrides.get('is_active', True),
        )
