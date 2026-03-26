"""Unit tests for bcllm_run.py CLI module.

Tests cover all CLI commands:
- --create-run
- --list-runs
- --run (show details)

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import pytest
import sys
from unittest.mock import patch

from src.db import create_schema
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run
from tests.factories import ExperimentFactory, VariantFactory, SnapshotFactory, RunFactory


# =============================================================================
# Test: --create-run
# =============================================================================

@pytest.mark.domain_rule
def test_create_run_success(in_memory_db, capsys):
    """--create-run creates run and prints success with run_id."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment with models and snapshots
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snapshot)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp",
        "--create-run",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            assert "test-exp" in captured.out


@pytest.mark.domain_rule
def test_create_run_experiment_not_found(in_memory_db, capsys):
    """--create-run fails with 'experiment not found' message."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    test_args = [
        "bcllm_run.py",
        "--experiment", "non-existent-exp",
        "--create-run",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_create_run_no_models(in_memory_db, capsys):
    """--create-run fails with 'no models' message when experiment has no variants."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment without models
    exp = ExperimentFactory.create(name="test-exp-no-models")
    _insert_experiment(in_memory_db, exp)

    # Add snapshot but no variants
    snapshot = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snapshot)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp-no-models",
        "--create-run",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "no models" in captured.err.lower()


@pytest.mark.domain_rule
def test_create_run_no_snapshots(in_memory_db, capsys):
    """--create-run fails with 'no questions' message when experiment has no snapshots."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment without snapshots
    exp = ExperimentFactory.create(name="test-exp-no-questions")
    _insert_experiment(in_memory_db, exp)

    # Add variant but no snapshots
    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp-no-questions",
        "--create-run",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "no questions" in captured.err.lower()


@pytest.mark.domain_rule
def test_create_run_with_seed(in_memory_db, capsys):
    """--create-run with --seed creates run with specified seed."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    exp = ExperimentFactory.create(name="test-exp-seed")
    _insert_experiment(in_memory_db, exp)

    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    snapshot = SnapshotFactory.create(
        experiment_id=exp.experiment_id,
        question_id="Q01",
    )
    _insert_snapshot(in_memory_db, snapshot)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp-seed",
        "--create-run",
        "--seed", "12345",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            assert "12345" in captured.out


# =============================================================================
# Test: --list-runs
# =============================================================================

def test_list_runs_empty(in_memory_db, capsys):
    """--list-runs shows 'no runs' message when empty."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp",
        "--list-runs",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no runs" in captured.out.lower()


@pytest.mark.domain_rule
def test_list_runs_with_data(in_memory_db, capsys):
    """--list-runs lists runs in table format with status."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create runs
    run1 = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    run2 = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=None,
        status="completed",
    )
    _insert_run(in_memory_db, run1)
    _insert_run(in_memory_db, run2)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp",
        "--list-runs",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "test-exp" in captured.out
            assert run1.run_id in captured.out
            assert run2.run_id in captured.out
            assert "pending" in captured.out
            assert "completed" in captured.out
            # Check table format (header row)
            assert "ID" in captured.out
            assert "Seed" in captured.out
            assert "Status" in captured.out


@pytest.mark.domain_rule
def test_list_runs_for_experiment(in_memory_db, capsys):
    """--list-runs filters by experiment."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add run to exp1 only
    run1 = RunFactory.create(
        experiment_id=exp1.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run1)

    # List runs for exp2 (should be empty)
    test_args = [
        "bcllm_run.py",
        "--experiment", "experiment-two",
        "--list-runs",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "no runs" in captured.out.lower()
            assert run1.run_id not in captured.out


# =============================================================================
# Test: --run (show details)
# =============================================================================

@pytest.mark.domain_rule
def test_show_run_success(in_memory_db, capsys):
    """--run shows run details."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Pre-create run
    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert run.run_id in captured.out
            assert "test-exp" in captured.out
            assert "42" in captured.out
            assert "pending" in captured.out


@pytest.mark.domain_rule
def test_show_run_not_found(in_memory_db, capsys):
    """--run fails with 'run not found' message."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create experiment (but no run)
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_run.py",
        "--experiment", "test-exp",
        "--run", "run-non-existent",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_show_run_wrong_experiment(in_memory_db, capsys):
    """--run fails if run is not in specified experiment."""
    # Arrange
    from src.cli.bcllm_run import main as run_main

    # Pre-create two experiments
    exp1 = ExperimentFactory.create(name="experiment-one")
    exp2 = ExperimentFactory.create(name="experiment-two")
    _insert_experiment(in_memory_db, exp1)
    _insert_experiment(in_memory_db, exp2)

    # Add run to exp1
    run = RunFactory.create(
        experiment_id=exp1.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    # Try to show run from exp2
    test_args = [
        "bcllm_run.py",
        "--experiment", "experiment-two",
        "--run", run.run_id,
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = run_main()

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower() or "not in experiment" in captured.err.lower()


# =============================================================================
# Integration Tests (without mocking)
# =============================================================================

class TestCreateRunIntegration:
    """Integration tests for --create-run with real DB."""

    def test_create_and_list_run(self, in_memory_db, capsys):
        """Create run and verify it appears in list."""
        from src.cli.bcllm_run import main as run_main

        # Pre-create experiment with models and snapshots
        exp = ExperimentFactory.create(name="integration-test")
        _insert_experiment(in_memory_db, exp)

        variant = VariantFactory.create(
            experiment_id=exp.experiment_id,
            model_id="openai/gpt-4",
            variant_signature="openai_gpt-4",
        )
        _insert_variant(in_memory_db, variant)

        snapshot = SnapshotFactory.create(
            experiment_id=exp.experiment_id,
            question_id="Q01",
        )
        _insert_snapshot(in_memory_db, snapshot)

        # Create run
        create_args = [
            "bcllm_run.py",
            "--experiment", "integration-test",
            "--create-run",
            "--seed", "999",
        ]
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = run_main()
                assert result == 0

        # List runs
        capsys.readouterr()  # Clear previous output
        list_args = [
            "bcllm_run.py",
            "--experiment", "integration-test",
            "--list-runs",
        ]
        with patch.object(sys, "argv", list_args):
            with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = run_main()
                assert result == 0
                captured = capsys.readouterr()
                assert "999" in captured.out
                assert "pending" in captured.out

    def test_create_run_without_models_fails(self, in_memory_db, capsys):
        """Creating run without models fails."""
        from src.cli.bcllm_run import main as run_main

        # Pre-create experiment without models
        exp = ExperimentFactory.create(name="no-models-test")
        _insert_experiment(in_memory_db, exp)

        # Add snapshot but no variants
        snapshot = SnapshotFactory.create(
            experiment_id=exp.experiment_id,
            question_id="Q01",
        )
        _insert_snapshot(in_memory_db, snapshot)

        create_args = [
            "bcllm_run.py",
            "--experiment", "no-models-test",
            "--create-run",
        ]
        with patch.object(sys, "argv", create_args):
            with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = run_main()
                assert result == 1
                captured = capsys.readouterr()
                assert "no models" in captured.err.lower()


class TestShowRunIntegration:
    """Integration tests for --run with real DB."""

    def test_show_run_details(self, in_memory_db, capsys):
        """Show run displays all details."""
        from src.cli.bcllm_run import main as run_main

        # Pre-create experiment
        exp = ExperimentFactory.create(name="show-test")
        _insert_experiment(in_memory_db, exp)

        # Pre-create run
        run = RunFactory.create(
            experiment_id=exp.experiment_id,
            seed=777,
            status="pending",
        )
        _insert_run(in_memory_db, run)

        show_args = [
            "bcllm_run.py",
            "--experiment", "show-test",
            "--run", run.run_id,
        ]
        with patch.object(sys, "argv", show_args):
            with patch("src.cli.bcllm_run.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                result = run_main()
                assert result == 0
                captured = capsys.readouterr()
                assert run.run_id in captured.out
                assert "777" in captured.out
                assert "show-test" in captured.out


# =============================================================================
# Helper Functions
# =============================================================================

def _insert_experiment(conn, experiment: Experiment) -> None:
    """Insert experiment directly into database."""
    repo = ExperimentRepository(conn)
    repo.save(experiment)


def _insert_variant(conn, variant: ModelVariant) -> None:
    """Insert variant directly into database."""
    repo = VariantRepository(conn)
    repo.save(variant)


def _insert_snapshot(conn, snapshot: QuestionSnapshot) -> None:
    """Insert snapshot directly into database."""
    repo = SnapshotRepository(conn)
    repo.save(snapshot)


def _insert_run(conn, run: Run) -> None:
    """Insert run directly into database."""
    repo = RunRepository(conn)
    repo.save(run)
