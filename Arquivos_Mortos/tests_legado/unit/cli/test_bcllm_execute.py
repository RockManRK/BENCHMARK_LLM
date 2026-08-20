"""Unit tests for bcllm_execute.py CLI module.

Tests cover the execute command orchestration:
- Planner → ExecutionEngine → ResultWriter flow
- Validation errors (experiment not found, run not found, etc.)
- Success execution with summary output
- Error handling (API errors, partial failures)
- Idempotency (running twice doesn't duplicate results)

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection and API client
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import json
import pytest
import sys
from unittest.mock import patch, MagicMock, AsyncMock

from src.core.mode import Mode
from src.db import create_schema
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository, ResponseRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run
from tests.factories import ExperimentFactory, VariantFactory, SnapshotFactory, RunFactory


# =============================================================================
# Test: --execute success flow
# =============================================================================

@pytest.mark.domain_rule
def test_execute_success(in_memory_db, capsys):
    """--execute orchestrates Planner → Engine → Writer and prints summary."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create full setup
    exp = ExperimentFactory.create(
        name="test-exp",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question: {question}",
    )
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

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Mock API client to return successful response
            with patch("src.cli.bcllm_execute.OpenRouterClient") as MockClient:
                mock_api = MagicMock()
                mock_api.chat_completion = AsyncMock(return_value=MagicMock(
                    content="The answer is (B).",
                    model_id="openai/gpt-4",
                    input_tokens=50,
                    output_tokens=10,
                    latency_ms=500,
                ))
                MockClient.return_value = mock_api

                # Act
                result = execute_main(Mode.EXECUTE)

                # Assert
                assert result == 0
                captured = capsys.readouterr()
                assert "completed" in captured.out.lower() or "executed" in captured.out.lower()
                assert run.run_id in captured.out


@pytest.mark.domain_rule
def test_execute_experiment_not_found(in_memory_db, capsys):
    """--execute fails with 'experiment not found' message."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    test_args = [
        "bcllm_execute.py",
        "--experiment", "non-existent-exp",
        "--run", "run_abc123",
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = execute_main(Mode.EXECUTE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()
            assert "experiment" in captured.err.lower()


@pytest.mark.domain_rule
def test_execute_run_not_found(in_memory_db, capsys):
    """--execute fails with 'run not found' message."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create experiment (but no run)
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", "run-non-existent",
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = execute_main(Mode.EXECUTE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()
            assert "run" in captured.err.lower()


@pytest.mark.domain_rule
def test_execute_run_not_in_experiment(in_memory_db, capsys):
    """--execute fails if run is not in specified experiment."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

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

    # Try to execute run from exp2
    test_args = [
        "bcllm_execute.py",
        "--experiment", "experiment-two",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = execute_main(Mode.EXECUTE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not in experiment" in captured.err.lower() or "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_execute_run_not_pending(in_memory_db, capsys):
    """--execute fails if run is not in pending status."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create experiment and run (completed status)
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="completed",  # Already completed
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = execute_main(Mode.EXECUTE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "not pending" in captured.err.lower()


@pytest.mark.domain_rule
def test_execute_no_items(in_memory_db, capsys):
    """--execute fails with 'nothing to execute' when planner returns empty plan."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create experiment with no snapshots
    exp = ExperimentFactory.create(name="test-exp")
    _insert_experiment(in_memory_db, exp)

    # Add variant but no snapshots
    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Act
            result = execute_main(Mode.EXECUTE)

            # Assert
            assert result == 1
            captured = capsys.readouterr()
            assert "nothing to execute" in captured.err.lower() or "no" in captured.err.lower()


# =============================================================================
# Test: --execute with API errors
# =============================================================================

@pytest.mark.domain_rule
def test_execute_with_api_error(in_memory_db, capsys):
    """--execute handles API errors and reports partial failure."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create full setup
    exp = ExperimentFactory.create(
        name="test-exp",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question: {question}",
    )
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

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Mock API client to raise error
            with patch("src.cli.bcllm_execute.OpenRouterClient") as MockClient:
                mock_api = MagicMock()
                mock_api.chat_completion = AsyncMock(side_effect=Exception("API connection failed"))
                MockClient.return_value = mock_api

                # Act
                result = execute_main(Mode.EXECUTE)

                # Assert
                # Should return non-zero (failure) but still write error to DB
                assert result == 1
                captured = capsys.readouterr()
                # Should report the error
                assert "error" in captured.err.lower() or "failed" in captured.err.lower()


# =============================================================================
# Test: --execute summary output
# =============================================================================

@pytest.mark.domain_rule
def test_execute_prints_summary(in_memory_db, capsys):
    """--execute prints execution summary with success/failed counts."""
    # Arrange
    from src.cli.bcllm_execute import main as execute_main

    # Pre-create full setup with multiple snapshots
    exp = ExperimentFactory.create(
        name="test-exp",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question: {question}",
    )
    _insert_experiment(in_memory_db, exp)

    variant = VariantFactory.create(
        experiment_id=exp.experiment_id,
        model_id="openai/gpt-4",
        variant_signature="openai_gpt-4",
    )
    _insert_variant(in_memory_db, variant)

    # Add multiple snapshots
    for i in range(3):
        snapshot = SnapshotFactory.create(
            experiment_id=exp.experiment_id,
            question_id=f"Q{i+1:02d}",
        )
        _insert_snapshot(in_memory_db, snapshot)

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    test_args = [
        "bcllm_execute.py",
        "--experiment", "test-exp",
        "--run", run.run_id,
        "--execute",
    ]

    with patch.object(sys, "argv", test_args):
        with patch("src.cli.database.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db

            # Mock API client to return successful responses
            with patch("src.cli.bcllm_execute.OpenRouterClient") as MockClient:
                mock_api = MagicMock()
                mock_api.chat_completion = AsyncMock(return_value=MagicMock(
                    content="The answer is (B).",
                    model_id="openai/gpt-4",
                    input_tokens=50,
                    output_tokens=10,
                    latency_ms=500,
                ))
                MockClient.return_value = mock_api

                # Act
                result = execute_main(Mode.EXECUTE)

                # Assert
                assert result == 0
                captured = capsys.readouterr()
                # Should show summary with counts
                assert "success" in captured.out.lower() or "completed" in captured.out.lower()


# =============================================================================
# Test: --execute idempotency
# =============================================================================

@pytest.mark.domain_rule
def test_execute_idempotent(in_memory_db, capsys):
    """--execute running twice doesn't duplicate results."""
    # Arrange
    from src.cli.bcllm_execute import handle_execute, OpenRouterClient
    import argparse

    # Pre-create full setup
    exp = ExperimentFactory.create(
        name="test-exp",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question: {question}",
    )
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

    run = RunFactory.create(
        experiment_id=exp.experiment_id,
        seed=42,
        status="pending",
    )
    _insert_run(in_memory_db, run)

    # Mock API client
    mock_api = MagicMock()
    mock_api.chat_completion = AsyncMock(return_value=MagicMock(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=50,
        output_tokens=10,
        latency_ms=500,
    ))

    with patch.object(OpenRouterClient, "__new__", return_value=mock_api):
        # Create args namespace
        args = argparse.Namespace(
            experiment="test-exp",
            run=run.run_id,
            execute=True,
        )

        # First execution
        result1 = handle_execute(args, in_memory_db)
        assert result1 == 0

        # Count responses after first execution
        repo = ResponseRepository(in_memory_db)
        responses_after_first = len(repo.list_by_run(run.run_id))

        # Second execution (run status is no longer pending, should fail)
        capsys.readouterr()  # Clear previous output
        result2 = handle_execute(args, in_memory_db)

        # Assert
        # Second execution should fail because run is no longer pending
        assert result2 == 1
        captured = capsys.readouterr()
        assert "not pending" in captured.err.lower()

        # Response count should be unchanged (idempotency via status check)
        responses_after_second = len(repo.list_by_run(run.run_id))
        assert responses_after_first == responses_after_second


# =============================================================================
# Integration Tests (without mocking DB)
# =============================================================================

class TestExecuteIntegration:
    """Integration tests for --execute with real DB and mocked API."""

    def test_execute_full_flow(self, in_memory_db, capsys):
        """Full execution flow: Planner → Engine → Writer."""
        from src.cli.bcllm_execute import handle_execute, OpenRouterClient
        import argparse

        # Pre-create full setup
        exp = ExperimentFactory.create(
            name="integration-exp",
            system_prompt="You are a helpful assistant.",
            user_prompt="Answer the following question: {question}",
        )
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

        run = RunFactory.create(
            experiment_id=exp.experiment_id,
            seed=42,
            status="pending",
        )
        _insert_run(in_memory_db, run)

        # Mock API client
        mock_api = MagicMock()
        mock_api.chat_completion = AsyncMock(return_value=MagicMock(
            content="The answer is (B).",
            model_id="openai/gpt-4",
            input_tokens=50,
            output_tokens=10,
            latency_ms=500,
        ))

        with patch.object(OpenRouterClient, "__new__", return_value=mock_api):
            # Create args namespace
            args = argparse.Namespace(
                experiment="integration-exp",
                run=run.run_id,
                execute=True,
            )

            # Act
            result = handle_execute(args, in_memory_db)

            # Assert
            assert result == 0
            captured = capsys.readouterr()
            assert "completed" in captured.out.lower()

            # Verify response was written
            resp_repo = ResponseRepository(in_memory_db)
            responses = resp_repo.list_by_run(run.run_id)
            assert len(responses) == 1

            # Verify run status was updated
            run_repo = RunRepository(in_memory_db)
            updated_run = run_repo.get_by_id(run.run_id)
            assert updated_run.status in ("completed", "partial_failed", "failed")


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
    """Insert run directly into database.

    RunRepository.save() takes `config` as a separate dict argument
    rather than reading Run.config (see src/db/repository.py).
    """
    repo = RunRepository(conn)
    repo.save(run, config=json.loads(run.config))
