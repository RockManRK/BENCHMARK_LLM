"""Factory for creating QuestionSnapshot instances in tests."""

from dataclasses import dataclass
from typing import Optional
import uuid
import json


@dataclass
class QuestionSnapshot:
    """QuestionSnapshot entity for testing."""
    snapshot_id: str
    experiment_id: str
    question_id: str
    question_payload: str  # JSON string
    is_active: bool = True


class SnapshotFactory:
    """Factory for creating QuestionSnapshot instances in tests.
    
    This factory provides sensible defaults and allows customization
    through overrides. It returns dataclass instances, not database records.
    
    The question_payload is stored as a JSON string, matching the
    TO-BE schema design.
    
    Example:
        # Basic usage
        snapshot = SnapshotFactory.create(
            experiment_id="exp-123",
            question_id="q1",
        )
        
        # With custom payload
        payload = {"stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer": "4"}
        snapshot = SnapshotFactory.create(
            experiment_id="exp-123",
            question_id="q1",
            question_payload=json.dumps(payload),
        )
        
        # In a test
        def test_snapshot_creation(in_memory_db):
            snapshot = SnapshotFactory.create(experiment_id="exp-123", question_id="q1")
            repo = SnapshotRepository(in_memory_db)
            repo.save(snapshot)
    """

    @staticmethod
    def create(
        experiment_id: str,
        question_id: str,
        question_payload: Optional[str] = None,
        **overrides,
    ) -> QuestionSnapshot:
        """
        Create a QuestionSnapshot with defaults.
        
        Args:
            experiment_id: Parent experiment ID (required)
            question_id: Question identifier (required)
            question_payload: JSON string with question data (auto-generated if None)
            **overrides: Any field can be overridden
        
        Returns:
            QuestionSnapshot instance
        
        Example:
            >>> snapshot = SnapshotFactory.create(
            ...     experiment_id="exp-123",
            ...     question_id="q1",
            ... )
            >>> snapshot.question_id
            'q1'
            >>> import json
            >>> payload = json.loads(snapshot.question_payload)
            >>> 'stem' in payload
            True
        """
        # Default payload if not provided
        if question_payload is None:
            default_payload = {
                "stem": f"Question {question_id}: What is the correct answer?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "answer_key": "B",
            }
            question_payload = json.dumps(default_payload)
        
        return QuestionSnapshot(
            snapshot_id=overrides.get('snapshot_id', f"snap-{uuid.uuid4().hex[:8]}"),
            experiment_id=experiment_id,
            question_id=question_id,
            question_payload=question_payload,
            is_active=overrides.get('is_active', True),
        )
