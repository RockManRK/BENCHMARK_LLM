"""Factory for creating Run instances in tests."""

from dataclasses import dataclass
from typing import Optional, Literal
import uuid


@dataclass
class Run:
    """Run entity for testing."""
    run_id: str
    experiment_id: str
    seed: Optional[int]
    status: Literal['pending', 'running', 'completed', 'failed', 'partial_failed'] = 'pending'


class RunFactory:
    """Factory for creating Run instances in tests.
    
    This factory provides sensible defaults and allows customization
    through overrides. It returns dataclass instances, not database records.
    
    Example:
        # Basic usage - pending run
        run = RunFactory.create(experiment_id="exp-123")
        
        # Completed run with seed
        run = RunFactory.create(
            experiment_id="exp-123",
            seed=42,
            status="completed",
        )
        
        # In a test
        def test_run_creation(in_memory_db):
            run = RunFactory.create(experiment_id="exp-123")
            repo = RunRepository(in_memory_db)
            repo.save(run)
    """

    @staticmethod
    def create(
        experiment_id: str,
        seed: Optional[int] = None,
        status: Literal['pending', 'running', 'completed', 'failed', 'partial_failed'] = 'pending',
        **overrides,
    ) -> Run:
        """
        Create a Run with defaults.
        
        Args:
            experiment_id: Parent experiment ID (required)
            seed: Random seed for answer shuffling (None = no randomization)
            status: Run status (default: 'pending')
            **overrides: Any field can be overridden
        
        Returns:
            Run instance
        
        Example:
            >>> run = RunFactory.create(
            ...     experiment_id="exp-123",
            ...     seed=42,
            ...     status="pending",
            ... )
            >>> run.experiment_id
            'exp-123'
            >>> run.seed
            42
            >>> run.status
            'pending'
        """
        return Run(
            run_id=overrides.get('run_id', f"run-{uuid.uuid4().hex[:8]}"),
            experiment_id=experiment_id,
            seed=seed,
            status=status,
        )
