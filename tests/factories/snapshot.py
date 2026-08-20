"""Factory for creating QuestionSnapshot instances in tests.

Builds the real `src.db.models.QuestionSnapshot` entity — no duplicate/
parallel dataclass. The real field is `json_question_id` (not
`question_id`) and `question_position` is required (UNIQUE with
`experiment_id` — see `src/db/schema.py`); there is no `is_active`.
"""

import json
import uuid
from typing import Any, Optional

from src.db.models import QuestionSnapshot

# Positions only need to be distinct per experiment (UNIQUE(experiment_id,
# question_position) in schema). A wide random range keeps collisions
# negligible across the handful of snapshots any one test creates, without
# making the factory stateful.
_POSITION_RANGE = 1_000_000


class SnapshotFactory:
    """Factory for creating QuestionSnapshot instances in tests.

    The question_payload is stored as a JSON string, matching the
    real schema.

    Example:
        # Basic usage
        snapshot = SnapshotFactory.create(
            experiment_id="exp-123",
            question_id="q1",
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
        question_payload: Optional[dict[str, Any] | str] = None,
        question_position: Optional[int] = None,
        created_at: Optional[str] = None,
        **overrides: Any,
    ) -> QuestionSnapshot:
        """
        Create a QuestionSnapshot with defaults.

        Args:
            experiment_id: Parent experiment ID (required)
            question_id: Original dataset question ID — maps to the real
                entity's `json_question_id` field.
            question_payload: Question data as dict or JSON string
                (auto-generated if None)
            question_position: 1-based position within the experiment
                (auto-generated, distinct per call, if None)
            created_at: Creation timestamp (None = database default)
            **overrides: `snapshot_id` may be overridden

        Returns:
            QuestionSnapshot instance (src.db.models.QuestionSnapshot)
        """
        if question_payload is None:
            default_payload = {
                "stem": f"Question {question_id}: What is the correct answer?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "answer_key": "B",
            }
            question_payload = json.dumps(default_payload)
        elif isinstance(question_payload, dict):
            question_payload = json.dumps(question_payload)

        if question_position is None:
            question_position = uuid.uuid4().int % _POSITION_RANGE

        return QuestionSnapshot(
            snapshot_id=overrides.get('snapshot_id', f"snap-{uuid.uuid4().hex[:8]}"),
            experiment_id=experiment_id,
            json_question_id=question_id,
            question_position=question_position,
            question_payload=question_payload,
            created_at=created_at,
        )
