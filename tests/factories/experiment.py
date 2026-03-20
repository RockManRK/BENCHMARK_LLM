"""Factory for creating Experiment instances in tests."""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass
class Experiment:
    """Experiment entity for testing.
    
    Matches src_v2.db.models.Experiment structure.
    """
    experiment_id: str
    name: str
    description: Optional[str] = None
    config_json: str = "{}"
    config_hash: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    created_at: Optional[str] = None
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
        user_prompt: str = "Answer the following question.",
        experiment_id: Optional[str] = None,
        description: Optional[str] = None,
        config_json: str = "{}",
        config_hash: str = "",
        is_active: bool = True,
    ) -> Experiment:
        """
        Create an Experiment with defaults.

        Args:
            name: Experiment name (auto-generated if None)
            system_prompt: System prompt template
            user_prompt: User prompt template
            experiment_id: Unique ID (auto-generated if None)
            description: Optional description
            config_json: Frozen configuration snapshot
            config_hash: SHA-256 hash of protocol config
            is_active: Whether the experiment is active

        Returns:
            Experiment instance

        Example:
            >>> exp = ExperimentFactory.create(name="math-benchmark")
            >>> exp.name
            'math-benchmark'
            >>> exp.is_active
            True
        """
        if name is None:
            name = f"test-experiment-{uuid.uuid4().hex[:8]}"

        if experiment_id is None:
            experiment_id = f"exp-{uuid.uuid4().hex[:8]}"

        return Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            config_json=config_json,
            config_hash=config_hash,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            is_active=is_active,
        )
