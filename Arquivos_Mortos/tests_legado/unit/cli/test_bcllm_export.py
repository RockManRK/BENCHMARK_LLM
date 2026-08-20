"""Unit tests for bcllm_export.py CLI module.

Tests cover all export CLI functionality:
- Export to stdout
- Export to file
- JSON validity
- Determinism
- Validation errors

Test Pattern:
- Use capsys for output capture
- Use patch for mocking database connection
- Use in_memory_db fixture for integration tests
- Mark domain rules with @pytest.mark.domain_rule
"""

import json
import os
import pytest
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.db import create_schema
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository, ResponseRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run, Response
from tests.factories import ExperimentFactory, VariantFactory, SnapshotFactory, RunFactory


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory SQLite database with TO-BE schema.

    Yields:
        sqlite3.Connection: Database connection with row_factory enabled
    """
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    # Create full TO-BE schema
    conn.executescript("""
        CREATE TABLE experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            config_json TEXT NOT NULL DEFAULT '{}',
            config_hash TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE model_variants (
            variant_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            variant_signature TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE question_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            json_question_id TEXT NOT NULL,
            question_position INTEGER NOT NULL,
            question_payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            config TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            duration INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE responses (
            response_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            status TEXT,
            finish_reason TEXT,
            error_details TEXT,
            response_text TEXT,
            selected_answer TEXT,
            is_correct BOOLEAN,
            parse_confidence TEXT DEFAULT 'unknown',
            review_status TEXT,
            manual_answer TEXT,
            raw_response TEXT,
            cost REAL,
            input_tokens INTEGER,
            response_tokens INTEGER,
            reasoning_tokens INTEGER,
            effective_tokens INTEGER,
            latency_ms INTEGER,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            UNIQUE(run_id, variant_id, snapshot_id)
        );

        CREATE TABLE errors (
            error_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            snapshot_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 1,
            stack_trace TEXT,
            occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

    yield conn

    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def setup_export_test_data(in_memory_db: sqlite3.Connection) -> dict:
    """Insert test data for export CLI tests.

    Creates:
    - 1 experiment
    - 1 model variant
    - 2 question snapshots
    - 1 run (status='completed')
    - 2 responses
    - 1 error

    Returns:
        dict: IDs of created entities
    """
    cursor = in_memory_db.cursor()

    # Insert experiment
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, config_json, config_hash)
        VALUES ('exp-export-test', 'Export Test Experiment', 'Test for export CLI', '{}', 'hash123')
    """)

    # Insert model variant
    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES ('var-export-123', 'exp-export-test', 'openai/gpt-4', 'gpt-4-default', '{}')
    """)

    # Insert question snapshots
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
        VALUES ('snap-001', 'exp-export-test', 'Q001', 1, '{"stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer_key": "4"}')
    """)
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
        VALUES ('snap-002', 'exp-export-test', 'Q002', 2, '{"stem": "What is 3+3?", "options": ["5", "6", "7", "8"], "answer_key": "6"}')
    """)

    # Insert run
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status, duration)
        VALUES ('run-export-001', 'exp-export-test', '{"seed": 42}', 'completed', 0)
    """)

    # Insert responses
    cursor.execute("""
        INSERT INTO responses (
            response_id, run_id, variant_id, snapshot_id, model_id, question_id,
            status, response_text, selected_answer, is_correct, parse_confidence,
            manual_answer, input_tokens, response_tokens, reasoning_tokens,
            latency_ms, cost, started_at, finished_at
        )
        VALUES (
            'resp-export-001', 'run-export-001', 'var-export-123', 'snap-001',
            'openai/gpt-4', 'Q001', 'success', 'The answer is (B).',
            'B', 1, 'clear', NULL, 50, 10, 5, 500, 0.001,
            '2024-01-01 10:00:00', '2024-01-01 10:00:01'
        )
    """)
    cursor.execute("""
        INSERT INTO responses (
            response_id, run_id, variant_id, snapshot_id, model_id, question_id,
            status, response_text, selected_answer, is_correct, parse_confidence,
            manual_answer, input_tokens, response_tokens, reasoning_tokens,
            latency_ms, cost, started_at, finished_at
        )
        VALUES (
            'resp-export-002', 'run-export-001', 'var-export-123', 'snap-002',
            'openai/gpt-4', 'Q002', 'success', 'The answer is (B).',
            'B', 1, 'clear', NULL, 60, 12, 8, 600, 0.002,
            '2024-01-01 10:00:02', '2024-01-01 10:00:03'
        )
    """)

    # Insert error
    cursor.execute("""
        INSERT INTO errors (
            error_id, run_id, variant_id, snapshot_id, question_id,
            error_type, error_message, attempt_count, occurred_at
        )
        VALUES (
            'err-export-001', 'run-export-001', 'var-export-123', 'snap-002',
            'Q002', 'timeout', 'Request timed out after 30s', 3,
            '2024-01-01 10:00:03'
        )
    """)

    in_memory_db.commit()

    return {
        'experiment_id': 'exp-export-test',
        'variant_id': 'var-export-123',
        'snapshot_ids': ['snap-001', 'snap-002'],
        'run_id': 'run-export-001',
        'response_ids': ['resp-export-001', 'resp-export-002'],
        'error_id': 'err-export-001',
    }


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


# =============================================================================
# Test: Export to stdout
# =============================================================================

@pytest.mark.domain_rule
def test_export_to_stdout_success(in_memory_db, setup_export_test_data, capsys):
    """--export outputs valid JSON to stdout."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    # Create mock args
    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 0
    captured = capsys.readouterr()
    
    # Verify JSON output
    output = captured.out
    assert output is not None
    assert len(output) > 0
    
    # Parse and verify JSON structure
    data = json.loads(output)
    assert data['run_id'] == 'run-export-001'
    assert data['experiment_name'] == 'Export Test Experiment'
    assert data['total_responses'] == 2
    assert 'responses' in data
    assert 'errors' in data


@pytest.mark.domain_rule
def test_export_to_stdout_includes_experiment_name(in_memory_db, setup_export_test_data, capsys):
    """Export includes experiment_name for context."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data['experiment_name'] == 'Export Test Experiment'


# =============================================================================
# Test: Export to file
# =============================================================================

@pytest.mark.domain_rule
def test_export_to_file_success(in_memory_db, setup_export_test_data, capsys, tmp_path):
    """--export --output-file writes JSON to file."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    output_file = tmp_path / "export_results.json"
    output_file_str = str(output_file)

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = output_file_str
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 0
    assert output_file.exists()

    # Verify file content
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert data['run_id'] == 'run-export-001'
    assert data['total_responses'] == 2


@pytest.mark.domain_rule
def test_export_to_file_creates_parent_directories(in_memory_db, setup_export_test_data, capsys, tmp_path):
    """--output-file creates parent directories if needed."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    output_file = tmp_path / "subdir" / "nested" / "export_results.json"
    output_file_str = str(output_file)

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = output_file_str
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 0
    assert output_file.exists()


@pytest.mark.domain_rule
def test_export_to_file_prints_confirmation(in_memory_db, setup_export_test_data, capsys, tmp_path):
    """--output-file prints confirmation message."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    output_file = tmp_path / "export_results.json"
    output_file_str = str(output_file)

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = output_file_str
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    captured = capsys.readouterr()
    assert "Exported" in captured.out
    assert "responses" in captured.out.lower()
    assert output_file_str in captured.out


# =============================================================================
# Test: JSON validity
# =============================================================================

@pytest.mark.domain_rule
def test_export_json_validity(in_memory_db, setup_export_test_data, capsys):
    """Export output is always valid JSON."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert: Should not raise JSONDecodeError
    captured = capsys.readouterr()
    try:
        data = json.loads(captured.out)
        assert isinstance(data, dict)
    except json.JSONDecodeError as e:
        pytest.fail(f"Export output is not valid JSON: {e}")


@pytest.mark.domain_rule
def test_export_json_structure(in_memory_db, setup_export_test_data, capsys):
    """Export JSON has expected structure."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    
    # Check required fields
    assert 'export_version' in data
    assert 'exported_at' in data
    assert 'experiment_name' in data
    assert 'run_id' in data
    assert 'total_responses' in data
    assert 'total_errors' in data
    assert 'responses' in data
    assert 'errors' in data
    
    # Check types
    assert isinstance(data['responses'], list)
    assert isinstance(data['errors'], list)
    assert isinstance(data['total_responses'], int)
    assert isinstance(data['total_errors'], int)


# =============================================================================
# Test: Determinism
# =============================================================================

@pytest.mark.domain_rule
def test_export_determinism(in_memory_db, setup_export_test_data, capsys):
    """Export produces deterministic output (excluding timestamp)."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act: Export twice
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)
        captured1 = capsys.readouterr()
        
        handle_export(args, in_memory_db, Mode.EXPORT)
        captured2 = capsys.readouterr()

    # Assert
    data1 = json.loads(captured1.out)
    data2 = json.loads(captured2.out)
    
    # Remove timestamp fields
    del data1['exported_at']
    del data2['exported_at']
    
    assert data1 == data2, "Export output should be deterministic"


@pytest.mark.domain_rule
def test_export_determinism_response_order(in_memory_db, setup_export_test_data, capsys):
    """Export maintains deterministic response ordering."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act: Export multiple times
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        handle_export(args, in_memory_db, Mode.EXPORT)
        captured1 = capsys.readouterr()
        
        handle_export(args, in_memory_db, Mode.EXPORT)
        captured2 = capsys.readouterr()

    # Assert
    data1 = json.loads(captured1.out)
    data2 = json.loads(captured2.out)
    
    # Response order should be identical
    response_ids1 = [r['response_id'] for r in data1['responses']]
    response_ids2 = [r['response_id'] for r in data2['responses']]
    
    assert response_ids1 == response_ids2, "Response ordering should be deterministic"


# =============================================================================
# Test: Validation errors
# =============================================================================

@pytest.mark.domain_rule
def test_export_experiment_not_found(in_memory_db, capsys):
    """--export fails with 'experiment not found' message."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'non-existent-experiment'
        run = 'run-any'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_export_run_not_found(in_memory_db, setup_export_test_data, capsys):
    """--export fails with 'run not found' message."""
    # Arrange
    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-non-existent'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower()


@pytest.mark.domain_rule
def test_export_run_wrong_experiment(in_memory_db, setup_export_test_data, capsys):
    """--export fails if run does not belong to specified experiment."""
    # Arrange: Create a second experiment and run
    cursor = in_memory_db.cursor()
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, config_json, config_hash)
        VALUES ('exp-other', 'Other Experiment', 'Other', '{}', 'hash456')
    """)
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status, duration)
        VALUES ('run-other', 'exp-other', '{"seed": 42}', 'completed', 0)
    """)
    in_memory_db.commit()

    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'  # Wrong experiment
        run = 'run-other'  # Run belongs to different experiment
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 1
    captured = capsys.readouterr()
    assert "does not belong" in captured.err.lower() or "not found" in captured.err.lower()


# =============================================================================
# Test: Empty export
# =============================================================================

@pytest.mark.domain_rule
def test_export_run_with_no_responses(in_memory_db, setup_export_test_data, capsys):
    """--export handles run with no responses."""
    # Arrange: Delete all responses
    cursor = in_memory_db.cursor()
    cursor.execute("DELETE FROM responses WHERE run_id = 'run-export-001'")
    in_memory_db.commit()

    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data['total_responses'] == 0
    assert data['responses'] == []


@pytest.mark.domain_rule
def test_export_run_with_no_errors(in_memory_db, setup_export_test_data, capsys):
    """--export handles run with no errors."""
    # Arrange: Delete all errors
    cursor = in_memory_db.cursor()
    cursor.execute("DELETE FROM errors WHERE run_id = 'run-export-001'")
    in_memory_db.commit()

    from src.cli.bcllm_export import handle_export
    from src.core.mode import Mode

    class Args:
        experiment = 'Export Test Experiment'
        run = 'run-export-001'
        output_file = None
        format = 'json'
        export = True

    args = Args()

    # Act
    with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
        mock_connect.return_value = in_memory_db
        result = handle_export(args, in_memory_db, Mode.EXPORT)

    # Assert
    assert result == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data['total_errors'] == 0
    assert data['errors'] == []


# =============================================================================
# Integration Tests (without mocking)
# =============================================================================

class TestExportIntegration:
    """Integration tests for export with real DB."""

    def test_export_and_verify_json(self, in_memory_db, setup_export_test_data, tmp_path):
        """Export to file and verify JSON can be read back."""
        # Arrange
        from src.cli.bcllm_export import handle_export
        from src.core.mode import Mode

        output_file = tmp_path / "integration_export.json"
        output_file_str = str(output_file)

        class Args:
            experiment = 'Export Test Experiment'
            run = 'run-export-001'
            output_file = output_file_str
            format = 'json'
            export = True

        args = Args()

        # Act
        with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            result = handle_export(args, in_memory_db, Mode.EXPORT)

        # Assert
        assert result == 0
        assert output_file.exists()

        # Verify file can be read as JSON
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data['run_id'] == 'run-export-001'
        assert len(data['responses']) == 2
        assert len(data['errors']) == 1

    def test_export_response_fields_complete(self, in_memory_db, setup_export_test_data, capsys):
        """Export includes all expected response fields."""
        # Arrange
        from src.cli.bcllm_export import handle_export
        from src.core.mode import Mode

        class Args:
            experiment = 'Export Test Experiment'
            run = 'run-export-001'
            output_file = None
            format = 'json'
            export = True

        args = Args()

        # Act
        with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            handle_export(args, in_memory_db, Mode.EXPORT)

        # Assert
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        # Check response has all expected fields
        response = data['responses'][0]
        expected_fields = [
            'response_id', 'question_id', 'variant_id', 'model_id',
            'snapshot_id', 'run_id', 'selected_answer', 'manual_answer',
            'final_answer', 'answer_source', 'is_correct', 'parse_confidence',
            'latency_ms', 'input_tokens', 'output_tokens', 'reasoning_tokens',
            'effective_tokens', 'status', 'error_details', 'cost',
            'started_at', 'finished_at'
        ]
        
        for field in expected_fields:
            assert field in response, f"Missing field: {field}"

    def test_export_error_fields_complete(self, in_memory_db, setup_export_test_data, capsys):
        """Export includes all expected error fields."""
        # Arrange
        from src.cli.bcllm_export import handle_export
        from src.core.mode import Mode

        class Args:
            experiment = 'Export Test Experiment'
            run = 'run-export-001'
            output_file = None
            format = 'json'
            export = True

        args = Args()

        # Act
        with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
            mock_connect.return_value = in_memory_db
            handle_export(args, in_memory_db, Mode.EXPORT)

        # Assert
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        
        # Check error has all expected fields
        error = data['errors'][0]
        expected_fields = [
            'error_id', 'question_id', 'variant_id', 'snapshot_id',
            'run_id', 'error_type', 'error_message', 'attempt_count',
            'occurred_at'
        ]
        
        for field in expected_fields:
            assert field in error, f"Missing field: {field}"


# =============================================================================
# Logging Tests
# =============================================================================

class TestExportLogging:

    def test_export_logs_command_start(self, in_memory_db, setup_export_test_data, caplog):
        """Export logs EXPORT_COMMAND_START."""
        # Arrange
        import logging
        from src.utils.logging_config import setup_logging
        from src.cli.bcllm_export import handle_export
        from src.core.mode import Mode

        setup_logging()
        logger = logging.getLogger('benchmark_llm.cli.export')
        logger.setLevel(logging.INFO)
        logger.addHandler(caplog.handler)

        class Args:
            experiment = 'Export Test Experiment'
            run = 'run-export-001'
            output_file = None
            format = 'json'
            export = True

        args = Args()

        # Act
        with caplog.at_level(logging.INFO, logger='benchmark_llm'):
            with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                handle_export(args, in_memory_db, Mode.EXPORT)

        # Assert
        assert any("EXPORT_COMMAND_START" in record.message for record in caplog.records)

    def test_export_logs_complete(self, in_memory_db, setup_export_test_data, caplog):
        """Export logs EXPORT_COMPLETE."""
        # Arrange
        import logging
        from src.utils.logging_config import setup_logging
        from src.cli.bcllm_export import handle_export
        from src.core.mode import Mode

        setup_logging()
        logger = logging.getLogger('benchmark_llm.cli.export')
        logger.setLevel(logging.INFO)
        logger.addHandler(caplog.handler)

        class Args:
            experiment = 'Export Test Experiment'
            run = 'run-export-001'
            output_file = None
            format = 'json'
            export = True

        args = Args()

        # Act
        with caplog.at_level(logging.INFO, logger='benchmark_llm'):
            with patch("src.cli.bcllm_export.sqlite3.connect") as mock_connect:
                mock_connect.return_value = in_memory_db
                handle_export(args, in_memory_db, Mode.EXPORT)

        # Assert
        assert any("EXPORT_COMPLETE" in record.message for record in caplog.records)
