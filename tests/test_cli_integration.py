#!/usr/bin/env python3
"""Comprehensive CLI integration test suite.

This module provides end-to-end integration tests for the bcllm CLI:
1. Full workflow tests (create experiment → add models → add questions → create run → execute → review)
2. Model ID validation tests (all spec examples)
3. Structured output flag persistence tests
4. Partial execution scenario tests
5. Idempotent operation tests
6. Error scenario tests (not found, invalid input, collisions)

All tests use:
- Temporary file SQLite database (simulates real persistent database)
- Mocked API client (no real API calls)
- CLI entry points (verifies full integration from argument parsing to database)
"""

import json
import os
import pytest
import sys
import tempfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO

# Add src_v2 to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src_v2.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
    ErrorRepository,
)
from src_v2.db.models import Experiment, ModelVariant, QuestionSnapshot, Run
from src_v2.api.client import CompletionResponse


@pytest.fixture
def temp_db_file():
    """Create a temporary database file for CLI tests.
    
    This fixture creates a temporary file that simulates the real persistent
    database used by the CLI. Tests can share this file across multiple CLI
    invocations to test state persistence.
    
    Yields:
        Path: Path to temporary database file
    """
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield Path(temp_path)
    # Cleanup
    try:
        os.unlink(temp_path)
    except Exception:
        pass


@pytest.fixture
def mock_api_client():
    """Create configurable mock API client for integration tests.
    
    Returns:
        MagicMock: Mocked API client
    """
    from src_v2.api.client import OpenRouterClient
    
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion = AsyncMock(return_value=CompletionResponse(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=50,
        output_tokens=10,
        latency_ms=500,
    ))
    return client


def patch_database_path(temp_db_path: Path):
    """Create a context manager that patches the database path.
    
    Args:
        temp_db_path: Path to temporary database file
        
    Returns:
        Context manager that patches get_database_path
    """
    from src_v2.cli import database as db_module
    
    original_get_path = db_module.get_database_path
    
    def mock_get_path():
        return temp_db_path
    
    return patch.object(db_module, 'get_database_path', mock_get_path)


def patch_api_client_in_execute(mock_client):
    """Create a context manager that patches the API client in execute module.
    
    Args:
        mock_client: Mock API client to use
        
    Returns:
        Context manager that patches OpenRouterClient
    """
    from src_v2.cli import bcllm_execute
    
    return patch.object(
        bcllm_execute, 
        'OpenRouterClient',
        return_value=mock_client
    )


# =============================================================================
# Test Class 1: Full Workflow Integration
# =============================================================================

@pytest.mark.integration
class TestFullWorkflowIntegration:
    """Test complete CLI workflow from experiment creation to review."""

    def test_full_workflow_happy_path(self, temp_db_file, mock_api_client, capsys):
        """
        Test complete workflow:
        1. Create experiment
        2. Add model variant
        3. Add question snapshots
        4. Create run
        5. Execute run
        6. Verify results in database
        7. Review interface can access results

        This is the primary happy path test for the entire CLI system.
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Step 1: Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "workflow-test",
            ]):
                result = experiment_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            exp_id = self._extract_experiment_id(captured.out)
            assert exp_id is not None

            # Step 2: Add model variant
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "workflow-test",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "added" in captured.out.lower()
            var_id = self._extract_variant_id(captured.out)
            assert var_id is not None

            # Step 3: Add question snapshots
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "workflow-test",
                "--add-questions", "q1", "q2", "q3",
            ]):
                result = questions_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "3 question" in captured.out.lower()

            # Step 4: Create run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "workflow-test",
                "--add-run",
            ]):
                result = run_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            run_id = self._extract_run_id(captured.out)
            assert run_id is not None

            # Step 5: Execute run
            mock_api_client.chat_completion.return_value = CompletionResponse(
                content="The answer is (B).",
                model_id="openai/gpt-4",
                input_tokens=50,
                output_tokens=10,
                latency_ms=500,
            )

            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "workflow-test",
                    "--execute",
                ]):
                    result = execute_main()
                    assert result == 0

            captured = capsys.readouterr()
            assert "Execution completed" in captured.out

        # Step 6: Verify results in database
        conn = self._get_db_connection(temp_db_file)
        try:
            resp_repo = ResponseRepository(conn)
            responses = resp_repo.list_by_run(run_id)

            assert len(responses) == 3  # 3 questions
            for response in responses:
                assert response.selected_answer == "B"
                assert response.parse_confidence == "clear"
                assert response.needs_review == False

            # Step 7: Verify run status updated
            run_repo = RunRepository(conn)
            run = run_repo.get_by_id(run_id)
            assert run.status == "completed"
        finally:
            conn.close()

    def test_workflow_with_multiple_models(self, temp_db_file, mock_api_client, capsys):
        """
        Test workflow with multiple model variants:
        1. Create experiment
        2. Add 2 model variants
        3. Add questions
        4. Create run
        5. Execute
        6. Verify both models have responses
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "multi-model-test",
            ]):
                experiment_main()

            # Add first model
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "multi-model-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            # Add second model
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "multi-model-test",
                "--add-model", "anthropic/claude-3",
            ]):
                model_main()

            # Add questions
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "multi-model-test",
                "--add-questions", "q1", "q2",
            ]):
                questions_main()

            # Create run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "multi-model-test",
                "--add-run",
            ]):
                run_main()
                captured = capsys.readouterr()
                run_id = self._extract_run_id(captured.out)

            # Execute with multiple models
            call_count = [0]
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                model_id = "openai/gpt-4" if call_count[0] % 2 == 1 else "anthropic/claude-3"
                return CompletionResponse(
                    content="The answer is (B).",
                    model_id=model_id,
                    input_tokens=50,
                    output_tokens=10,
                    latency_ms=500,
                )
            mock_api_client.chat_completion.side_effect = side_effect

            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "multi-model-test",
                    "--execute",
                ]):
                    execute_main()

        # Verify: Should have 4 responses (2 models × 2 questions)
        conn = self._get_db_connection(temp_db_file)
        try:
            resp_repo = ResponseRepository(conn)
            responses = resp_repo.list_by_run(run_id)

            assert len(responses) == 4

            # Verify both models have responses
            variant_ids = {r.variant_id for r in responses}
            assert len(variant_ids) == 2
        finally:
            conn.close()

    def test_workflow_with_multiple_runs(self, temp_db_file, mock_api_client, capsys):
        """
        Test workflow with multiple runs:
        1. Create experiment with model and questions
        2. Create 2 runs
        3. Execute both runs
        4. Verify results are isolated by run_id
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Setup: Create experiment with model and questions
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "multi-run-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "multi-run-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "multi-run-test",
                "--add-questions", "q1",
            ]):
                questions_main()

            # Create 2 runs
            run_ids = []
            for i in range(2):
                with patch.object(sys, "argv", [
                    "bcllm_run.py",
                    "--experiment", "multi-run-test",
                    "--add-run",
                ]):
                    run_main()
                    captured = capsys.readouterr()
                    run_ids.append(self._extract_run_id(captured.out))

            # Execute both runs
            for run_id in run_ids:
                with patch_api_client_in_execute(mock_api_client):
                    with patch.object(sys, "argv", [
                        "bcllm_execute.py",
                        "--experiment", "multi-run-test",
                        "--run", run_id,
                        "--execute",
                    ]):
                        execute_main()

        # Verify: Each run should have 1 response (1 model × 1 question)
        conn = self._get_db_connection(temp_db_file)
        try:
            resp_repo = ResponseRepository(conn)
            for run_id in run_ids:
                responses = resp_repo.list_by_run(run_id)
                assert len(responses) == 1

            # Verify runs are isolated (no shared responses)
            all_response_ids = set()
            for run_id in run_ids:
                responses = resp_repo.list_by_run(run_id)
                run_response_ids = {r.response_id for r in responses}
                assert len(all_response_ids.intersection(run_response_ids)) == 0
                all_response_ids.update(run_response_ids)
        finally:
            conn.close()

    def _extract_experiment_id(self, output: str) -> str | None:
        """Extract experiment ID from CLI output."""
        import re
        match = re.search(r'ID:\s*(exp_\w+)', output)
        return match.group(1) if match else None

    def _extract_variant_id(self, output: str) -> str | None:
        """Extract variant ID from CLI output."""
        import re
        match = re.search(r'ID:\s*(var_\w+)', output)
        return match.group(1) if match else None

    def _extract_run_id(self, output: str) -> str | None:
        """Extract run ID from CLI output."""
        import re
        match = re.search(r'ID:\s*(run_\w+)', output)
        return match.group(1) if match else None

    def _get_db_connection(self, db_path: Path):
        """Get database connection with row_factory enabled."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


# =============================================================================
# Test Class 2: Model ID Validation
# =============================================================================

@pytest.mark.integration
class TestModelIDValidation:
    """Test model ID validation with all spec examples."""

    def test_model_id_google_gemini(self, temp_db_file, capsys):
        """Test model ID: google/gemini-3.1-flash-lite-preview"""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        model_id = "google/gemini-3.1-flash-lite-preview"

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "model-validation-test",
            ]):
                result = experiment_main()
                assert result == 0

            # Add model
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "model-validation-test",
                "--add-model", model_id,
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert model_id in captured.out
            assert "added" in captured.out.lower()

    def test_model_id_openai_gpt(self, temp_db_file, capsys):
        """Test model ID: openai/gpt-4.1-mini"""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        model_id = "openai/gpt-4.1-mini"

        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "model-test-2",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "model-test-2",
                "--add-model", model_id,
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert model_id in captured.out

    def test_model_id_anthropic_claude(self, temp_db_file, capsys):
        """Test model ID: anthropic/claude-3.5-sonnet"""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        model_id = "anthropic/claude-3.5-sonnet"

        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "model-test-3",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "model-test-3",
                "--add-model", model_id,
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert model_id in captured.out

    def test_model_id_stepfun_with_free_suffix(self, temp_db_file, capsys):
        """Test model ID: stepfun/step-3.5-flash:free"""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        model_id = "stepfun/step-3.5-flash:free"

        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "model-test-4",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "model-test-4",
                "--add-model", model_id,
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert model_id in captured.out

    def test_model_id_nvidia_with_free_suffix(self, temp_db_file, capsys):
        """Test model ID: nvidia/nemotron-3-super-120b-a12b:free"""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        model_id = "nvidia/nemotron-3-super-120b-a12b:free"

        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "model-test-5",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "model-test-5",
                "--add-model", model_id,
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert model_id in captured.out

    def test_model_id_validation_rejects_invalid(self, temp_db_file, capsys):
        """Test that invalid model IDs are rejected."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        invalid_ids = [
            "invalid-no-slash",
            "double//slash",
            "/missing-provider",
            "missing-model/",
            "too/many/slashes",
        ]

        for model_id in invalid_ids:
            with patch_database_path(temp_db_file):
                with patch.object(sys, "argv", [
                    "bcllm_experiment.py",
                    "--create-experiment", f"test-{abs(hash(model_id)) % 10000}",
                ]):
                    experiment_main()

                with patch.object(sys, "argv", [
                    "bcllm_model.py",
                    "--experiment", f"test-{abs(hash(model_id)) % 10000}",
                    "--add-model", model_id,
                ]):
                    result = model_main()
                    assert result == 1

                captured = capsys.readouterr()
                assert "invalid" in captured.err.lower() or "format" in captured.err.lower()


# =============================================================================
# Test Class 3: Structured Output Flag Persistence
# =============================================================================

@pytest.mark.integration
class TestStructuredOutputPersistence:
    """Test structured output flag persistence in model variants."""

    def test_structured_output_flag_persists(self, temp_db_file, capsys):
        """
        Test that --structured-output flag is persisted to database.

        Verifies:
        - Flag can be set at model creation
        - Flag is stored in database
        - Flag is displayed in list output
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        # Create experiment and add model with structured output enabled
        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "structured-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "structured-test",
                "--add-model", "openai/gpt-4",
                "--structured-output",
            ]):
                result = model_main()
                assert result == 0

            # Verify flag in list output (same database context)
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "structured-test",
                "--list-models",
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            # Table should show structured output status
            assert "Structured" in captured.out or "Yes" in captured.out

        # Verify flag in database
        conn = self._get_db_connection(temp_db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT structured_output FROM model_variants
                WHERE model_id = 'openai/gpt-4'
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 1  # SQLite stores booleans as 0/1
        finally:
            conn.close()

    def test_vision_flag_persists(self, temp_db_file, capsys):
        """
        Test that --vision flag is persisted to database.

        Verifies:
        - Flag can be set at model creation
        - Flag is stored in database
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "vision-test",
            ]):
                experiment_main()

            # Add model with vision enabled
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "vision-test",
                "--add-model", "openai/gpt-4-vision",
                "--vision",
            ]):
                result = model_main()
                assert result == 0

        # Verify flag in database
        conn = self._get_db_connection(temp_db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT vision_enabled FROM model_variants
                WHERE model_id = 'openai/gpt-4-vision'
            """)
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == 1
        finally:
            conn.close()

    def _get_db_connection(self, db_path: Path):
        """Get database connection with row_factory enabled."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


# =============================================================================
# Test Class 4: Partial Execution Scenarios
# =============================================================================

@pytest.mark.integration
class TestPartialExecution:
    """Test partial execution scenarios with filters."""

    def test_execute_specific_run(self, temp_db_file, mock_api_client, capsys):
        """
        Test executing a specific run with --run filter.

        Verifies:
        - Only specified run is executed
        - Other runs remain pending
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Setup: Create experiment with model and questions
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "partial-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "partial-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "partial-test",
                "--add-questions", "q1",
            ]):
                questions_main()

            # Create 2 runs
            run_ids = []
            for i in range(2):
                with patch.object(sys, "argv", [
                    "bcllm_run.py",
                    "--experiment", "partial-test",
                    "--add-run",
                ]):
                    run_main()
                    captured = capsys.readouterr()
                    run_ids.append(self._extract_run_id(captured.out))

            # Execute only first run
            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "partial-test",
                    "--run", run_ids[0],
                    "--execute",
                ]):
                    execute_main()

        # Verify: First run completed, second run still pending
        conn = self._get_db_connection(temp_db_file)
        try:
            run_repo = RunRepository(conn)
            run1 = run_repo.get_by_id(run_ids[0])
            run2 = run_repo.get_by_id(run_ids[1])

            assert run1.status == "completed"
            assert run2.status == "pending"

            # Verify: Only first run has responses
            resp_repo = ResponseRepository(conn)
            assert len(resp_repo.list_by_run(run_ids[0])) == 1
            assert len(resp_repo.list_by_run(run_ids[1])) == 0
        finally:
            conn.close()

    def test_execute_specific_questions(self, temp_db_file, mock_api_client, capsys):
        """
        Test executing specific questions with --questions filter.

        Verifies:
        - Only specified questions are executed
        - Other questions remain unexecuted
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Setup
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "question-filter-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "question-filter-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            # Add 5 questions
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "question-filter-test",
                "--add-questions", "q1", "q2", "q3", "q4", "q5",
            ]):
                questions_main()

            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "question-filter-test",
                "--add-run",
            ]):
                run_main()
                captured = capsys.readouterr()
                run_id = self._extract_run_id(captured.out)

            # Execute only q2 and q4
            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "question-filter-test",
                    "--run", run_id,
                    "--questions", "Q002", "Q004",
                    "--execute",
                ]):
                    execute_main()

        # Verify: Only 2 responses created
        conn = self._get_db_connection(temp_db_file)
        try:
            resp_repo = ResponseRepository(conn)
            responses = resp_repo.list_by_run(run_id)
            assert len(responses) == 2

            # Verify correct questions were executed
            question_ids = {r.question_id for r in responses}
            assert question_ids == {"Q002", "Q004"}
        finally:
            conn.close()

    def test_execute_no_pending_items(self, temp_db_file, mock_api_client, capsys):
        """
        Test executing when all items are already completed.

        Verifies:
        - Appropriate message is shown
        - Exit code is 0 (not an error)
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main
        from src_v2.cli.bcllm_execute import main as execute_main

        with patch_database_path(temp_db_file):
            # Setup and execute once
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "already-done-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "already-done-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "already-done-test",
                "--add-questions", "q1",
            ]):
                questions_main()

            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "already-done-test",
                "--add-run",
            ]):
                run_main()
                captured = capsys.readouterr()
                run_id = self._extract_run_id(captured.out)

            # First execution
            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "already-done-test",
                    "--run", run_id,
                    "--execute",
                ]):
                    execute_main()

        # Try to execute again
        with patch_database_path(temp_db_file):
            with patch_api_client_in_execute(mock_api_client):
                with patch.object(sys, "argv", [
                    "bcllm_execute.py",
                    "--experiment", "already-done-test",
                    "--run", run_id,
                    "--execute",
                ]):
                    result = execute_main()

            captured = capsys.readouterr()
            # Should indicate no pending items or skip existing
            assert result == 0  # Not an error

    def _extract_run_id(self, output: str) -> str | None:
        """Extract run ID from CLI output."""
        import re
        match = re.search(r'ID:\s*(run_\w+)', output)
        return match.group(1) if match else None

    def _get_db_connection(self, db_path: Path):
        """Get database connection with row_factory enabled."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


# =============================================================================
# Test Class 5: Idempotent Operations
# =============================================================================

@pytest.mark.integration
class TestIdempotentOperations:
    """Test idempotent operations (re-adding same items)."""

    def test_re_add_same_model(self, temp_db_file, capsys):
        """
        Test re-adding the same model variant.

        Verifies:
        - Second add is rejected (collision)
        - No duplicate created
        - Appropriate error message shown
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "idempotent-model-test",
            ]):
                experiment_main()

            # Add model first time
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "idempotent-model-test",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0

            # Try to add same model again
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "idempotent-model-test",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 1  # Error

            captured = capsys.readouterr()
            assert "already exists" in captured.err.lower() or "collision" in captured.err.lower() or "Variant" in captured.err

        # Verify only one variant exists
        conn = self._get_db_connection(temp_db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM model_variants
                WHERE model_id = 'openai/gpt-4' AND experiment_id IN (
                    SELECT experiment_id FROM experiments WHERE name = 'idempotent-model-test'
                )
            """)
            count = cursor.fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def test_re_add_same_question(self, temp_db_file, capsys):
        """
        Test re-adding the same question snapshot.

        Verifies:
        - Second add is skipped (idempotent)
        - No duplicate created
        - Message indicates skip
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_questions import main as questions_main

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "idempotent-question-test",
            ]):
                experiment_main()

            # Add question first time
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "idempotent-question-test",
                "--add-questions", "q1",
            ]):
                result = questions_main()
                assert result == 0

            # Add same question again
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "idempotent-question-test",
                "--add-questions", "q1",
            ]):
                result = questions_main()
                assert result == 0  # Success (idempotent)

            captured = capsys.readouterr()
            assert "already existed" in captured.out.lower() or "skipped" in captured.out.lower()

        # Verify only one snapshot exists
        conn = self._get_db_connection(temp_db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM question_snapshots
                WHERE question_id = 'Q001' AND experiment_id IN (
                    SELECT experiment_id FROM experiments WHERE name = 'idempotent-question-test'
                )
            """)
            count = cursor.fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def test_re_create_experiment(self, temp_db_file, capsys):
        """
        Test re-creating an experiment with the same name.

        Verifies:
        - Second create is rejected (collision)
        - No duplicate created
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main

        with patch_database_path(temp_db_file):
            # Create experiment first time
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "duplicate-test",
            ]):
                result = experiment_main()
                assert result == 0

            # Try to create again
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "duplicate-test",
            ]):
                result = experiment_main()
                assert result == 1  # Error

            captured = capsys.readouterr()
            assert "already exists" in captured.err.lower()

        # Verify only one experiment exists
        conn = self._get_db_connection(temp_db_file)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM experiments WHERE name = 'duplicate-test'
            """)
            count = cursor.fetchone()[0]
            assert count == 1
        finally:
            conn.close()

    def _get_db_connection(self, db_path: Path):
        """Get database connection with row_factory enabled."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn


# =============================================================================
# Test Class 6: Error Scenarios
# =============================================================================

@pytest.mark.integration
class TestErrorScenarios:
    """Test error scenarios (not found, invalid input, collisions)."""

    def test_experiment_not_found(self, temp_db_file, capsys):
        """Test error when experiment doesn't exist."""
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main

        with patch_database_path(temp_db_file):
            # Try to add model to non-existent experiment
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "nonexistent",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 1

            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()

            # Try to add questions to non-existent experiment
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "nonexistent",
                "--add-questions", "q1",
            ]):
                result = questions_main()
                assert result == 1

            # Try to create run for non-existent experiment
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "nonexistent",
                "--add-run",
            ]):
                result = run_main()
                assert result == 1

    def test_run_not_found(self, temp_db_file, capsys):
        """Test error when run doesn't exist."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_run import main as run_main

        with patch_database_path(temp_db_file):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "run-not-found-test",
            ]):
                experiment_main()

            # Try to show non-existent run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "run-not-found-test",
                "--run", "run_nonexistent",
            ]):
                result = run_main()
                assert result == 1

            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()

    def test_invalid_question_spec(self, temp_db_file, capsys):
        """Test error when question spec is invalid."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_questions import main as questions_main

        with patch_database_path(temp_db_file):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "invalid-spec-test",
            ]):
                experiment_main()

            # Invalid range (start > end)
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "invalid-spec-test",
                "--add-questions", "10-5",
            ]):
                result = questions_main()
                assert result == 1

            captured = capsys.readouterr()
            assert "invalid" in captured.err.lower() or "range" in captured.err.lower()

            # Invalid format
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "invalid-spec-test",
                "--add-questions", "invalid",
            ]):
                result = questions_main()
                assert result == 1

    def test_create_run_without_models(self, temp_db_file, capsys):
        """Test creating run without models (may or may not validate)."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_run import main as run_main

        with patch_database_path(temp_db_file):
            # Create experiment without models
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "no-models-test",
            ]):
                experiment_main()

            # Try to create run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "no-models-test",
                "--add-run",
            ]):
                result = run_main()
                # Note: Current implementation allows this - documents expected behavior

    def test_create_run_without_questions(self, temp_db_file, capsys):
        """Test creating run without questions (may or may not validate)."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_run import main as run_main

        with patch_database_path(temp_db_file):
            # Create experiment with model but no questions
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "no-questions-test",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "no-questions-test",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()

            # Try to create run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "no-questions-test",
                "--add-run",
            ]):
                result = run_main()
                # Note: Current implementation allows this

    def test_variant_not_in_experiment(self, temp_db_file, capsys):
        """Test error when variant doesn't belong to experiment."""
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main

        with patch_database_path(temp_db_file):
            # Create two experiments
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "exp-1",
            ]):
                experiment_main()

            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "exp-2",
            ]):
                experiment_main()

            # Add model to first experiment
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "exp-1",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()
                captured = capsys.readouterr()
                var_id = self._extract_variant_id(captured.out)

            # Try to remove from second experiment
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "exp-2",
                "--remove-model", var_id,
            ]):
                result = model_main()
                assert result == 1

            captured = capsys.readouterr()
            assert "not in experiment" in captured.err.lower() or "not found" in captured.err.lower()

    def _extract_variant_id(self, output: str) -> str | None:
        """Extract variant ID from CLI output."""
        import re
        match = re.search(r'ID:\s*(var_\w+)', output)
        return match.group(1) if match else None


# =============================================================================
# Test Class 7: Cross-Invocation State Persistence
# =============================================================================

@pytest.mark.integration
class TestCrossInvocationPersistence:
    """Test that state persists correctly across CLI invocations."""

    def test_state_persists_across_invocations(self, temp_db_file, capsys):
        """
        Test that state created in one invocation is visible in subsequent invocations.

        Verifies:
        - Experiment created in invocation 1 is visible in invocation 2
        - Model added in invocation 2 is visible in invocation 3
        - Questions added in invocation 3 are visible in invocation 4
        - Run created in invocation 4 is visible in invocation 5
        """
        from src_v2.cli.bcllm_experiment import main as experiment_main
        from src_v2.cli.bcllm_model import main as model_main
        from src_v2.cli.bcllm_questions import main as questions_main
        from src_v2.cli.bcllm_run import main as run_main

        with patch_database_path(temp_db_file):
            # Invocation 1: Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "persistence-test",
            ]):
                result = experiment_main()
                assert result == 0

            # Invocation 2: Verify experiment exists and add model
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--experiment", "persistence-test",
            ]):
                result = experiment_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "persistence-test" in captured.out

            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "persistence-test",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0

            # Invocation 3: Verify model exists and add questions
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "persistence-test",
                "--list-models",
            ]):
                result = model_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "openai/gpt-4" in captured.out

            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "persistence-test",
                "--add-questions", "q1", "q2",
            ]):
                result = questions_main()
                assert result == 0

            # Invocation 4: Verify questions exist and create run
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "persistence-test",
                "--list-questions",
            ]):
                result = questions_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "Q001" in captured.out
            assert "Q002" in captured.out

            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "persistence-test",
                "--add-run",
            ]):
                result = run_main()
                assert result == 0

            # Invocation 5: Verify run exists
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "persistence-test",
                "--list-runs",
            ]):
                result = run_main()
                assert result == 0

            captured = capsys.readouterr()
            assert "run_" in captured.out
            assert "pending" in captured.out.lower()

    def _get_db_connection(self, db_path: Path):
        """Get database connection with row_factory enabled."""
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
