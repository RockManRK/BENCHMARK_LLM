"""Tests for ExportService and ExportedResponse computed fields.

This module tests the ExportService component that provides read-only
export functionality for benchmark results.

Key Domain Rules:
1. ExportService is READ-ONLY - no database modifications
2. final_answer = manual_answer OR selected_answer (null-coalescing)
3. answer_source = 'manual' if manual_answer else 'automatic' if selected_answer else None
4. effective_tokens = input_tokens + response_tokens + reasoning_tokens
5. Export output is deterministic (same DB state = same output)
6. All export operations are logged
"""

import json
import pytest
import sqlite3
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import patch

from src.core.export_service import ExportService, ExportedResponse, ExportedError, ExportResult
from src.db.repository import ResponseRepository, RunRepository, ExperimentRepository
from src.db.models import Response, Run, Experiment


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
def setup_test_data(in_memory_db: sqlite3.Connection) -> dict:
    """Insert test data into database.

    Creates:
    - 1 experiment
    - 1 model variant
    - 1 question snapshot
    - 1 run (status='completed')
    - 1 response

    Returns:
        dict: IDs of created entities
    """
    cursor = in_memory_db.cursor()

    # Insert experiment
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, description, config_json, config_hash)
        VALUES ('exp-test-001', 'Test Experiment', 'Test Description', '{}', 'abc123')
    """)

    # Insert model variant
    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES ('var-abc-123', 'exp-test-001', 'openai/gpt-4', 'gpt-4-default', '{}')
    """)

    # Insert question snapshot
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
        VALUES ('snap-xyz-789', 'exp-test-001', 'Q001', 1, '{"stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer_key": "4"}')
    """)

    # Insert run
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status, duration)
        VALUES ('run-test-001', 'exp-test-001', '{"seed": 42}', 'completed', 0)
    """)

    # Insert response
    cursor.execute("""
        INSERT INTO responses (
            response_id, run_id, variant_id, snapshot_id, model_id, question_id,
            status, response_text, selected_answer, is_correct, parse_confidence,
            manual_answer, input_tokens, response_tokens, reasoning_tokens,
            latency_ms, cost, started_at, finished_at
        )
        VALUES (
            'resp-001', 'run-test-001', 'var-abc-123', 'snap-xyz-789',
            'openai/gpt-4', 'Q001', 'success', 'The answer is (B).',
            'B', 1, 'clear', NULL, 50, 10, 5, 500, 0.001,
            '2024-01-01 10:00:00', '2024-01-01 10:00:01'
        )
    """)

    in_memory_db.commit()

    return {
        'experiment_id': 'exp-test-001',
        'variant_id': 'var-abc-123',
        'snapshot_id': 'snap-xyz-789',
        'run_id': 'run-test-001',
        'response_id': 'resp-001',
    }


# =============================================================================
# ExportedResponse Computed Fields Tests
# =============================================================================

class TestExportedResponseComputedFields:
    """Test computed fields in ExportedResponse."""

    def test_final_answer_with_manual_override(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """final_answer uses manual_answer when provided (override)."""
        # Arrange: Update response with manual_answer
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET selected_answer = 'B', manual_answer = 'C'
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert len(result.responses) == 1
        exported_response = result.responses[0]
        assert exported_response['selected_answer'] == 'B'
        assert exported_response['manual_answer'] == 'C'
        assert exported_response['final_answer'] == 'C', "final_answer should use manual_answer override"
        assert exported_response['answer_source'] == 'manual'

    def test_final_answer_with_selected_answer(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """final_answer uses selected_answer when manual_answer is null."""
        # Arrange: Ensure manual_answer is null
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET selected_answer = 'B', manual_answer = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert len(result.responses) == 1
        exported_response = result.responses[0]
        assert exported_response['selected_answer'] == 'B'
        assert exported_response['manual_answer'] is None
        assert exported_response['final_answer'] == 'B', "final_answer should use selected_answer"
        assert exported_response['answer_source'] == 'automatic'

    def test_final_answer_both_null(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """final_answer is null when both selected_answer and manual_answer are null."""
        # Arrange: Set both to null
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET selected_answer = NULL, manual_answer = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert len(result.responses) == 1
        exported_response = result.responses[0]
        assert exported_response['selected_answer'] is None
        assert exported_response['manual_answer'] is None
        assert exported_response['final_answer'] is None, "final_answer should be null when both are null"
        assert exported_response['answer_source'] is None

    def test_answer_source_manual(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """answer_source is 'manual' when manual_answer is provided."""
        # Arrange
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET manual_answer = 'D'
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['answer_source'] == 'manual'

    def test_answer_source_automatic(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """answer_source is 'automatic' when only selected_answer is provided."""
        # Arrange
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET selected_answer = 'A', manual_answer = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['answer_source'] == 'automatic'

    def test_answer_source_null(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """answer_source is None when both answers are null."""
        # Arrange
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET selected_answer = NULL, manual_answer = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['answer_source'] is None

    def test_effective_tokens_calculation(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """effective_tokens = input_tokens + response_tokens + reasoning_tokens."""
        # Arrange: Set token values
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET input_tokens = 100, response_tokens = 50, reasoning_tokens = 25
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['input_tokens'] == 100
        assert exported_response['output_tokens'] == 50  # Maps to response_tokens
        assert exported_response['reasoning_tokens'] == 25
        assert exported_response['effective_tokens'] == 175, "effective_tokens should be sum of all token types"

    def test_effective_tokens_with_nulls(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """effective_tokens handles null values correctly (treats as 0)."""
        # Arrange: Set only input_tokens, others null
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET input_tokens = 100, response_tokens = NULL, reasoning_tokens = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['input_tokens'] == 100
        assert exported_response['output_tokens'] is None
        assert exported_response['reasoning_tokens'] is None
        assert exported_response['effective_tokens'] == 100, "Null tokens should be treated as 0"

    def test_effective_tokens_all_null(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """effective_tokens is null when all token fields are null."""
        # Arrange: Set all to null
        cursor = in_memory_db.cursor()
        cursor.execute("""
            UPDATE responses
            SET input_tokens = NULL, response_tokens = NULL, reasoning_tokens = NULL
            WHERE response_id = 'resp-001'
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        exported_response = result.responses[0]
        assert exported_response['effective_tokens'] is None


# =============================================================================
# ExportService Tests
# =============================================================================

class TestExportService:

    def test_export_run_with_data(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run returns ExportResult with responses and errors."""
        # Arrange
        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert isinstance(result, ExportResult)
        assert result.run_id == 'run-test-001'
        assert result.experiment_name == 'Test Experiment'
        assert result.total_responses == 1
        assert result.total_errors == 0
        assert len(result.responses) == 1
        assert len(result.errors) == 0

    def test_export_run_empty(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run returns empty result when run has no responses or errors."""
        # Arrange: Delete the response
        cursor = in_memory_db.cursor()
        cursor.execute("DELETE FROM responses WHERE run_id = 'run-test-001'")
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert result.total_responses == 0
        assert result.total_errors == 0
        assert len(result.responses) == 0
        assert len(result.errors) == 0

    def test_export_run_with_errors(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run includes errors from errors table."""
        # Arrange: Add an error
        cursor = in_memory_db.cursor()
        cursor.execute("""
            INSERT INTO errors (
                error_id, run_id, variant_id, snapshot_id, question_id,
                error_type, error_message, attempt_count, occurred_at
            )
            VALUES (
                'err-001', 'run-test-001', 'var-abc-123', 'snap-xyz-789',
                'Q001', 'timeout', 'Request timed out after 30s', 3,
                '2024-01-01 10:00:00'
            )
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert result.total_responses == 1
        assert result.total_errors == 1
        assert len(result.errors) == 1
        error = result.errors[0]
        assert error['error_type'] == 'timeout'
        assert error['error_message'] == 'Request timed out after 30s'
        assert error['attempt_count'] == 3

    def test_export_result_json_serialization(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """ExportResult.to_json() produces valid JSON."""
        # Arrange
        export_service = ExportService(in_memory_db)
        result = export_service.export_run('run-test-001')

        # Act
        json_str = result.to_json()

        # Assert
        assert json_str is not None
        # Verify it's valid JSON
        parsed = json.loads(json_str)
        assert parsed['run_id'] == 'run-test-001'
        assert parsed['total_responses'] == 1
        assert 'responses' in parsed
        assert 'errors' in parsed

    def test_export_result_determinism(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """Export produces deterministic output (excluding timestamp)."""
        # Arrange
        export_service = ExportService(in_memory_db)

        # Act: Export twice
        result1 = export_service.export_run('run-test-001')
        result2 = export_service.export_run('run-test-001')

        # Assert: All fields except exported_at should be identical
        assert result1.run_id == result2.run_id
        assert result1.experiment_name == result2.experiment_name
        assert result1.total_responses == result2.total_responses
        assert result1.total_errors == result2.total_errors
        assert result1.responses == result2.responses
        assert result1.errors == result2.errors

        # Verify JSON determinism (excluding exported_at)
        json1 = json.loads(result1.to_json())
        json2 = json.loads(result2.to_json())

        # Remove timestamp fields
        del json1['exported_at']
        del json2['exported_at']

        assert json1 == json2, "Export output should be deterministic"

    def test_export_run_not_found(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run handles non-existent run gracefully."""
        # Arrange
        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-non-existent')

        # Assert
        assert isinstance(result, ExportResult)
        assert result.run_id == 'run-non-existent'
        assert result.total_responses == 0
        assert result.total_errors == 0

    def test_export_multiple_responses(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run handles multiple responses correctly."""
        # Arrange: Add more responses
        cursor = in_memory_db.cursor()
        cursor.execute("""
            INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
            VALUES ('snap-xyz-790', 'exp-test-001', 'Q002', 2, '{"stem": "What is 3+3?", "options": ["5", "6", "7", "8"], "answer_key": "6"}')
        """)
        cursor.execute("""
            INSERT INTO responses (
                response_id, run_id, variant_id, snapshot_id, model_id, question_id,
                status, response_text, selected_answer, is_correct, parse_confidence,
                input_tokens, response_tokens, reasoning_tokens, latency_ms
            )
            VALUES (
                'resp-002', 'run-test-001', 'var-abc-123', 'snap-xyz-790',
                'openai/gpt-4', 'Q002', 'success', 'The answer is (B).',
                'B', 1, 'clear', 60, 12, 8, 600
            )
        """)
        in_memory_db.commit()

        export_service = ExportService(in_memory_db)

        # Act
        result = export_service.export_run('run-test-001')

        # Assert
        assert result.total_responses == 2
        assert len(result.responses) == 2
        response_ids = {r['response_id'] for r in result.responses}
        assert response_ids == {'resp-001', 'resp-002'}


# =============================================================================
# ExportResult Tests
# =============================================================================

class TestExportResult:

    def test_export_result_default_values(self) -> None:
        """ExportResult initializes with correct default values."""
        # Act
        result = ExportResult()

        # Assert
        assert result.export_version == "1.0"
        assert result.responses == []
        assert result.errors == []
        assert result.total_responses == 0
        assert result.total_errors == 0
        assert result.exported_at is not None  # Auto-set in __post_init__

    def test_export_result_to_dict(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """ExportResult.to_dict() returns dictionary representation."""
        # Arrange
        export_service = ExportService(in_memory_db)
        result = export_service.export_run('run-test-001')

        # Act
        result_dict = result.to_dict()

        # Assert
        assert isinstance(result_dict, dict)
        assert 'export_version' in result_dict
        assert 'exported_at' in result_dict
        assert 'run_id' in result_dict
        assert 'responses' in result_dict
        assert 'errors' in result_dict
        assert result_dict['run_id'] == 'run-test-001'

    def test_export_result_custom_indent(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """ExportResult.to_json() produces different output with different indent values."""
        # Arrange
        export_service = ExportService(in_memory_db)
        result = export_service.export_run('run-test-001')

        # Act
        json_compact = result.to_json(indent=0)
        json_pretty = result.to_json(indent=4)

        # Assert: Different indent values produce different output
        # Both are valid JSON but with different formatting
        assert json_compact != json_pretty
        # Verify both are valid JSON
        import json
        assert json.loads(json_compact) == json.loads(json_pretty)


# =============================================================================
# Read-Only Behavior Tests
# =============================================================================

class TestReadOnlyBehavior:

    def test_export_does_not_modify_responses(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run does not modify response records."""
        # Arrange
        export_service = ExportService(in_memory_db)
        cursor = in_memory_db.cursor()

        # Get initial state
        cursor.execute("SELECT * FROM responses WHERE run_id = 'run-test-001'")
        before = cursor.fetchall()

        # Act
        export_service.export_run('run-test-001')

        # Assert
        cursor.execute("SELECT * FROM responses WHERE run_id = 'run-test-001'")
        after = cursor.fetchall()

        assert len(before) == len(after)
        assert before[0] == after[0], "Response record should not be modified"

    def test_export_does_not_modify_runs(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run does not modify run status or other fields."""
        # Arrange
        export_service = ExportService(in_memory_db)
        cursor = in_memory_db.cursor()

        # Get initial state
        cursor.execute("SELECT status FROM runs WHERE run_id = 'run-test-001'")
        before_status = cursor.fetchone()[0]

        # Act
        export_service.export_run('run-test-001')

        # Assert
        cursor.execute("SELECT status FROM runs WHERE run_id = 'run-test-001'")
        after_status = cursor.fetchone()[0]

        assert before_status == after_status, "Run status should not be modified"

    def test_export_does_not_insert_records(self, in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
        """export_run does not insert new records into any table."""
        # Arrange
        export_service = ExportService(in_memory_db)
        cursor = in_memory_db.cursor()

        # Get initial counts
        cursor.execute("SELECT COUNT(*) FROM responses")
        responses_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM errors")
        errors_before = cursor.fetchone()[0]

        # Act
        export_service.export_run('run-test-001')

        # Assert
        cursor.execute("SELECT COUNT(*) FROM responses")
        responses_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM errors")
        errors_after = cursor.fetchone()[0]

        assert responses_before == responses_after
        assert errors_before == errors_after


# =============================================================================
# Logging Tests
# =============================================================================

class TestLogging:

    def test_export_logs_start_and_complete(self, in_memory_db: sqlite3.Connection, setup_test_data: dict, caplog) -> None:
        """export_run logs EXPORT_START and EXPORT_COMPLETE."""
        # Arrange
        import logging
        
        # Get the logger used by export_service
        logger = logging.getLogger('benchmark_llm.core.export_service')
        logger.setLevel(logging.INFO)
        
        # Add caplog handler to capture records
        logger.addHandler(caplog.handler)

        export_service = ExportService(in_memory_db)

        # Act
        with caplog.at_level(logging.INFO, logger='benchmark_llm'):
            export_service.export_run('run-test-001')

        # Assert
        assert any("EXPORT_START" in record.message for record in caplog.records)
        assert any("EXPORT_COMPLETE" in record.message for record in caplog.records)

    def test_export_logs_fetch_counts(self, in_memory_db: sqlite3.Connection, setup_test_data: dict, caplog) -> None:
        """export_run logs EXPORT_COMPLETE with response and error counts."""
        # Arrange
        import logging
        
        # Get the logger used by export_service
        logger = logging.getLogger('benchmark_llm.core.export_service')
        logger.setLevel(logging.INFO)
        logger.addHandler(caplog.handler)

        export_service = ExportService(in_memory_db)

        # Act
        with caplog.at_level(logging.INFO, logger='benchmark_llm'):
            export_service.export_run('run-test-001')

        # Assert: Check EXPORT_COMPLETE contains counts
        complete_records = [r for r in caplog.records if "EXPORT_COMPLETE" in r.message]
        assert len(complete_records) >= 1
        # Check that counts are logged
        assert any("responses=1" in record.message for record in complete_records)
