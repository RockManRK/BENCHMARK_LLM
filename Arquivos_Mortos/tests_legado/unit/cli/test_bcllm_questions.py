"""Unit tests for bcllm_questions.py CLI module.

Tests cover all CLI commands:
- --add-questions
- --list-questions
- --remove-question

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import pytest
import sys
from unittest.mock import patch

from src.core.mode import Mode
from src.db import create_schema
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.db.models import Experiment, QuestionSnapshot
from tests.factories import ExperimentFactory, SnapshotFactory


# =============================================================================
# Test: --add-questions
# =============================================================================

@pytest.mark.domain_rule
def test_add_questions_success(in_memory_db, capsys):
    """--add-questions creates snapshots and prints success count."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--add-questions", "q1,q2,q3",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "added" in captured.out.lower() or "snapped" in captured.out.lower()
            assert "3" in captured.out  # Count


@pytest.mark.domain_rule
def test_add_questions_experiment_not_found(in_memory_db, capsys):
    """--add-questions fails with 'experiment not found' message."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    test_args = [
        "bcllm_questions.py",
        "--experiment", "non-existent-exp",
        "--add-questions", "q1,q2",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_add_questions_idempotent(in_memory_db, capsys):
    """--add-questions skips duplicates silently (idempotent)."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create snapshot for q1
    snap = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snap)

    # Try to add q1 again (should skip) plus q2 (should add)
    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--add-questions", "q1,q2",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "1" in captured.out  # Only 1 added
            assert "already existed" in captured.out.lower() or "skipped" in captured.out.lower()


@pytest.mark.domain_rule
def test_add_questions_invalid_spec(in_memory_db, capsys):
    """--add-questions fails with 'invalid question spec' message."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Invalid format: contains invalid characters
    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--add-questions", "q1,@invalid,q3",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "invalid" in captured.err.lower()


# =============================================================================
# Test: --list-questions
# =============================================================================

def test_list_questions_empty(in_memory_db, capsys):
    """--list-questions shows 'no questions' message when empty."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--list-questions",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no questions" in captured.out.lower()


@pytest.mark.domain_rule
def test_list_questions_with_data(in_memory_db, capsys):
    """--list-questions lists questions in table format."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create snapshots
    snap1 = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
        question_payload={"stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer_key": "B"},
    )
    snap2 = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q02",
        question_payload={"stem": "What is the capital of France?", "options": ["Paris", "London", "Berlin", "Madrid"], "answer_key": "A"},
    )
    _insert_snapshot(in_memory_db, snap1)
    _insert_snapshot(in_memory_db, snap2)

    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--list-questions",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "Q01" in captured.out
            assert "Q02" in captured.out
            # Check table format (header row)
            assert "ID" in captured.out
            assert "Question ID" in captured.out
            assert "Stem" in captured.out


@pytest.mark.domain_rule
def test_list_questions_for_experiment(in_memory_db, capsys):
    """--list-questions filters by experiment."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add snapshot to exp1 only
    snap1 = SnapshotFactory.create(
        experiment_id=exp1.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snap1)

    # List questions for exp2 (should be empty)
    test_args = [
        "bcllm_questions.py",
        "--experiment", "experiment-two",
        "--list-questions",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no questions" in captured.out.lower()
            assert "Q01" not in captured.out


# =============================================================================
# Test: --remove-question
# =============================================================================

@pytest.mark.domain_rule
def test_remove_question_success(in_memory_db, capsys):
    """--remove-question soft deletes snapshot and prints confirmation."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create snapshot
    snap = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snap)

    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--remove-question", snap.snapshot_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "removed" in captured.out.lower()
            assert "Q01" in captured.out

            # Verify soft delete
            snap_repo = SnapshotRepository(in_memory_db)
            retrieved = snap_repo.get_by_id(snap.snapshot_id)
            assert retrieved is not None
            assert retrieved.is_active is False


@pytest.mark.domain_rule
def test_remove_question_not_found(in_memory_db, capsys):
    """--remove-question fails with 'snapshot not found' message."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create experiment (but no snapshot)
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_questions.py",
        "--experiment", "test-exp",
        "--remove-question", "snap-non-existent",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_remove_question_from_wrong_experiment(in_memory_db, capsys):
    """--remove-question fails if snapshot is not in specified experiment."""
    # Arrange
    from src.cli.bcllm_questions import main as questions_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add snapshot to exp1
    snap = SnapshotFactory.create(
        experiment_id=exp1.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snap)

    # Try to remove from exp2
    test_args = [
        "bcllm_questions.py",
        "--experiment", "experiment-two",
        "--remove-question", snap.snapshot_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = questions_main(Mode.MODIFY)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower() or "not in experiment" in captured.err.lower()


# =============================================================================
# Integration Tests (without mocking)
# =============================================================================

class TestAddQuestionsIntegration:
    """Integration tests for --add-questions with real DB."""

    def test_add_and_list_questions(self, in_memory_db, capsys):
        """Add questions and verify they appear in list."""
        from src.cli.bcllm_questions import main as questions_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="integration-test")
        _insert_experiment(in_memory_db, exp)

        # Add questions
        add_args = [
            "bcllm_questions.py",
            "--experiment", "integration-test",
            "--add-questions", "q1,q2",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = questions_main(Mode.MODIFY)
                assert result == 0

        # List questions
        capsys.readouterr()  # Clear previous output
        list_args = [
            "bcllm_questions.py",
            "--experiment", "integration-test",
            "--list-questions",
        ]
        with patch.object(sys, "argv", list_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = questions_main(Mode.MODIFY)
                assert result == 0
                captured = capsys.readouterr()
                assert "Q01" in captured.out
                assert "Q02" in captured.out

    def test_add_range_format(self, in_memory_db, capsys):
        """Add questions using range format (1-5)."""
        from src.cli.bcllm_questions import main as questions_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="range-test")
        _insert_experiment(in_memory_db, exp)

        # Add questions using range
        add_args = [
            "bcllm_questions.py",
            "--experiment", "range-test",
            "--add-questions", "1-3",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = questions_main(Mode.MODIFY)
                assert result == 0
                captured = capsys.readouterr()
                assert "3" in captured.out  # 3 questions added

        # Verify all 3 questions exist
        snap_repo = SnapshotRepository(in_memory_db)
        snapshots = snap_repo.list_by_experiment(exp.experiment_id)
        assert len(snapshots) == 3


class TestRemoveQuestionIntegration:
    """Integration tests for --remove-question with real DB."""

    def test_remove_then_list_excludes(self, in_memory_db, capsys):
        """Removed question should not appear in list."""
        from src.cli.bcllm_questions import main as questions_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="remove-test")
        _insert_experiment(in_memory_db, exp)

        # Add question
        add_args = [
            "bcllm_questions.py",
            "--experiment", "remove-test",
            "--add-questions", "q1",
        ]
        with patch.object(sys, "argv", add_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                questions_main(Mode.MODIFY)

        # Get snapshot ID
        snap_repo = SnapshotRepository(in_memory_db)
        snapshots = snap_repo.list_by_experiment(exp.experiment_id)
        snapshot_id = snapshots[0].snapshot_id

        # Remove question
        remove_args = [
            "bcllm_questions.py",
            "--experiment", "remove-test",
            "--remove-question", snapshot_id,
        ]
        with patch.object(sys, "argv", remove_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                questions_main(Mode.MODIFY)

        # Clear captured output before list
        capsys.readouterr()

        # List - should show "no questions" since the only question was removed
        list_args = [
            "bcllm_questions.py",
            "--experiment", "remove-test",
            "--list-questions",
        ]
        with patch.object(sys, "argv", list_args):
            with patch("src.cli.database.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = questions_main(Mode.MODIFY)
                assert result == 0
                captured = capsys.readouterr()
                assert "no questions" in captured.out.lower()


# =============================================================================
# Helper Functions
# =============================================================================

def _insert_experiment(conn, experiment: Experiment) -> None:
    """Insert experiment directly into database."""
    repo = ExperimentRepository(conn)
    repo.save(experiment)


def _insert_snapshot(conn, snapshot: QuestionSnapshot) -> None:
    """Insert snapshot directly into database."""
    repo = SnapshotRepository(conn)
    repo.save(snapshot)
