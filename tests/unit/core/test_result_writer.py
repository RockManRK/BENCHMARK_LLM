"""Tests for ResultWriter module.

This module tests the ResultWriter component that persists ExecutionResults.
Following test-first approach: tests define domain rules before implementation.

Key Domain Rules:
1. ResultWriter calculates needs_review from parse_confidence and selected_answer
2. Writes are idempotent (UNIQUE constraint + INSERT OR IGNORE)
3. Success results go to responses table
4. Failure results go to errors table
5. Run status is updated after all writes complete
"""

import pytest
import sqlite3
from datetime import datetime
from typing import Generator

from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def in_memory_db() -> Generator[sqlite3.Connection, None, None]:
    """Create in-memory SQLite database with TO-BE schema.

    Yields:
        sqlite3.Connection: Database connection with row_factory enabled
    """
    from src.db.schema import create_schema

    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Create full TO-BE schema
    create_schema(conn)

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
    - 1 run (status='pending')

    Returns:
        dict: IDs of created entities
    """
    cursor = in_memory_db.cursor()

    # Insert experiment (prompts live in config_json, not dedicated columns)
    cursor.execute("""
        INSERT INTO experiments (experiment_id, name, config_json, config_hash)
        VALUES ('exp-test-001', 'Test Experiment', '{"SYSTEM_PROMPT": "System prompt", "USER_PROMPT": "User prompt"}', 'test-hash')
    """)

    # Insert model variant (config is NOT NULL in current schema)
    cursor.execute("""
        INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
        VALUES ('var-abc-123', 'exp-test-001', 'openai/gpt-4', 'gpt-4-default', '{}')
    """)

    # Insert question snapshot (columns are json_question_id + question_position, not question_id)
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
        VALUES ('snap-xyz-789', 'exp-test-001', 'q1', 1, '{"stem": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer_key": "4"}')
    """)

    # Insert run (seed lives in config_json, not a dedicated column)
    cursor.execute("""
        INSERT INTO runs (run_id, experiment_id, config, status)
        VALUES ('run-test-001', 'exp-test-001', '{"RANDOMIZATION_SEED": 42}', 'pending')
    """)

    in_memory_db.commit()

    return {
        'experiment_id': 'exp-test-001',
        'variant_id': 'var-abc-123',
        'snapshot_id': 'snap-xyz-789',
        'run_id': 'run-test-001',
    }


# =============================================================================
# Domain Rule Tests: needs_review calculation
# =============================================================================

@pytest.mark.domain_rule
def test_writer_calculates_review_status_clear(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter calculates needs_review=False for clear confidence with answer."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert: needs_review was calculated as FALSE
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT review_status FROM responses WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None, "Response was not written"
    assert row[0] == 'auto', "review_status should be 'auto' (0) for clear confidence with answer"


@pytest.mark.domain_rule
def test_writer_calculates_review_status_ambiguous(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter calculates needs_review=True for ambiguous confidence."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="I think the answer might be B, but I'm not sure.",
        selected_answer="B",
        parse_confidence="ambiguous",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert: needs_review was calculated as TRUE
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT review_status FROM responses WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 'needs_review', "review_status should be 'needs_review' (1) for ambiguous confidence"


@pytest.mark.domain_rule
def test_writer_calculates_review_status_no_answer(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter calculates needs_review=True for no_answer confidence."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="I cannot answer this question.",
        selected_answer=None,
        parse_confidence="no_answer",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert: needs_review was calculated as TRUE
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT review_status FROM responses WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 'needs_review', "review_status should be 'needs_review' (1) for no_answer confidence"


@pytest.mark.domain_rule
def test_writer_calculates_review_status_low_confidence(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter calculates needs_review=True for low_confidence."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer could be B or C, leaning towards B.",
        selected_answer="B",
        parse_confidence="low_confidence",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert: needs_review was calculated as TRUE
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT review_status FROM responses WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 'needs_review', "review_status should be 'needs_review' (1) for low_confidence"


@pytest.mark.domain_rule
def test_writer_calculates_review_status_null_answer(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter calculates needs_review=True when selected_answer is None."""
    # Arrange: clear confidence but no answer selected
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The response does not contain a clear answer.",
        selected_answer=None,
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert: needs_review was calculated as TRUE (null answer trumps clear confidence)
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT review_status FROM responses WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 'needs_review', "review_status should be 'needs_review' (1) when selected_answer is None"


# =============================================================================
# Idempotency Tests
# =============================================================================

@pytest.mark.domain_rule
def test_writer_idempotent_writes(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter writes are idempotent - duplicate results are skipped."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act: Write twice
    # Fixed 2026-08-21 (test-debt reconciliation, group 5): write_result()
    # is documented (docs/contracts/idempotency.md's Implementation
    # Pattern) and implemented to return None — idempotency is proven by
    # querying persisted state, not by an internal return value. No
    # consumer (AsyncWriter._write_result_with_retry) uses or needs a
    # return value from write_result() today.
    writer.write_result(result)
    writer.write_result(result)  # Duplicate — must be silently skipped

    # Verify only one row in DB
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id = 'run-test-001'")
    count = cursor.fetchone()[0]
    assert count == 1, "Only one response should exist in database"


# =============================================================================
# Persistence Tests
# =============================================================================

def test_writer_persists_success_results(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter persists success results to responses table."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Verify response in database
    cursor = in_memory_db.cursor()
    cursor.execute("""
        SELECT response_id, run_id, variant_id, snapshot_id, model_id, question_id,
               response_text, selected_answer, parse_confidence, latency_ms,
               input_tokens, response_tokens
        FROM responses
        WHERE run_id = 'run-test-001'
    """)
    row = cursor.fetchone()
    assert row is not None
    assert row['run_id'] == 'run-test-001'
    assert row['variant_id'] == 'var-abc-123'
    assert row['snapshot_id'] == 'snap-xyz-789'
    assert row['question_id'] == 'q1'
    assert row['response_text'] == 'The answer is (B).'
    assert row['selected_answer'] == 'B'
    assert row['parse_confidence'] == 'clear'
    assert row['latency_ms'] == 500
    assert row['input_tokens'] == 50
    assert row['response_tokens'] == 10


def test_writer_persists_failure_results(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter persists failure results to errors table."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="failure",
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        latency_ms=100,
        input_tokens=0,
        response_tokens=0,
        error_type="timeout",
        error_message="Request timed out after 30s",
        attempt_count=3,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Verify error in database
    cursor = in_memory_db.cursor()
    cursor.execute("""
        SELECT error_id, run_id, variant_id, snapshot_id, question_id,
               error_type, error_message, attempt_count
        FROM errors
        WHERE run_id = 'run-test-001'
    """)
    row = cursor.fetchone()
    assert row is not None
    assert row['run_id'] == 'run-test-001'
    assert row['variant_id'] == 'var-abc-123'
    assert row['snapshot_id'] == 'snap-xyz-789'
    assert row['question_id'] == 'q1'
    assert row['error_type'] == 'timeout'
    assert row['error_message'] == 'Request timed out after 30s'
    assert row['attempt_count'] == 3


# =============================================================================
# Run Status Update Tests
# NOTE: These tests are skipped because run status updates were moved to RunFinalizer.
# See tests/unit/core/test_run_finalizer.py for run status update tests.
# =============================================================================

@pytest.mark.skip(reason="Run status updates handled by RunFinalizer, not ResultWriter")
def test_writer_updates_run_status_completed(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter updates run status to completed when all results succeed."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT status FROM runs WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row['status'] == 'completed'


@pytest.mark.skip(reason="Run status updates handled by RunFinalizer, not ResultWriter")
def test_writer_updates_run_status_partial_failed(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter updates run status to partial_failed when some results fail."""
    # Arrange: Add another snapshot for second item
    cursor = in_memory_db.cursor()
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
        VALUES ('snap-xyz-790', 'exp-test-001', 'q2', '{"stem": "What is 3+3?", "options": ["5", "6", "7", "8"], "answer_key": "6"}')
    """)
    in_memory_db.commit()

    results = [
        ExecutionResult(
            item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
            run_id="run-test-001",
            variant_id="var-abc-123",
            snapshot_id="snap-xyz-789",
            question_id="q1",
            status="success",
            response_text="The answer is (B).",
            selected_answer="B",
            parse_confidence="clear",
            latency_ms=500,
            input_tokens=50,
            response_tokens=10,
            error_type=None,
            error_message=None,
            attempt_count=1,
        ),
        ExecutionResult(
            item_id="run-test-001::var-abc-123::snap-xyz-790::it-2",
            run_id="run-test-001",
            variant_id="var-abc-123",
            snapshot_id="snap-xyz-790",
            question_id="q2",
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=100,
            input_tokens=0,
            response_tokens=0,
            error_type="timeout",
            error_message="Request timed out",
            attempt_count=3,
        ),
    ]

    writer = ResultWriter(in_memory_db)

    # Act
    report = writer.write_results(results)

    # Assert
    assert len(report.runs_updated) == 1
    assert report.runs_updated[0] == ('run-test-001', 'partial_failed')

    # Verify run status in database
    cursor.execute("SELECT status FROM runs WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row['status'] == 'partial_failed'


@pytest.mark.skip(reason="Run status updates handled by RunFinalizer, not ResultWriter")
def test_writer_updates_run_status_failed(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter updates run status to failed when all results fail."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="failure",
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        latency_ms=100,
        input_tokens=0,
        response_tokens=0,
        error_type="api_error",
        error_message="API returned 500",
        attempt_count=3,
    )

    writer = ResultWriter(in_memory_db)

    # Act
    writer.write_result(result)

    # Assert
    assert len(report.runs_updated) == 1
    assert report.runs_updated[0] == ('run-test-001', 'failed')

    # Verify run status in database
    cursor = in_memory_db.cursor()
    cursor.execute("SELECT status FROM runs WHERE run_id = 'run-test-001'")
    row = cursor.fetchone()
    assert row is not None
    assert row['status'] == 'failed'


# =============================================================================
# WriteReport Tests
# NOTE: Skipped because WriteReport was removed with write_results().
# =============================================================================

@pytest.mark.skip(reason="WriteReport removed with write_results()")
def test_writer_returns_write_report(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """ResultWriter.write_results returns WriteReport with counts and run status updates."""
    # Arrange: Add another snapshot for mixed results test
    cursor = in_memory_db.cursor()
    cursor.execute("""
        INSERT INTO question_snapshots (snapshot_id, experiment_id, question_id, question_payload)
        VALUES ('snap-xyz-790', 'exp-test-001', 'q2', '{"stem": "What is 3+3?", "options": ["5", "6", "7", "8"], "answer_key": "6"}')
    """)
    in_memory_db.commit()

    results = [
        ExecutionResult(
            item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
            run_id="run-test-001",
            variant_id="var-abc-123",
            snapshot_id="snap-xyz-789",
            question_id="q1",
            status="success",
            response_text="The answer is (B).",
            selected_answer="B",
            parse_confidence="clear",
            latency_ms=500,
            input_tokens=50,
            response_tokens=10,
            error_type=None,
            error_message=None,
            attempt_count=1,
        ),
        ExecutionResult(
            item_id="run-test-001::var-abc-123::snap-xyz-790::it-2",
            run_id="run-test-001",
            variant_id="var-abc-123",
            snapshot_id="snap-xyz-790",
            question_id="q2",
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=100,
            input_tokens=0,
            response_tokens=0,
            error_type="timeout",
            error_message="Request timed out",
            attempt_count=3,
        ),
    ]

    writer = ResultWriter(in_memory_db)

    # Act
    report = writer.write_results(results)

    # Assert: WriteReport structure
    assert hasattr(report, 'responses_written')
    assert hasattr(report, 'responses_skipped')
    assert hasattr(report, 'errors_written')
    assert hasattr(report, 'runs_updated')

    assert report.responses_written == 1
    assert report.responses_skipped == 0
    assert report.errors_written == 1
    assert len(report.runs_updated) == 1
    assert report.runs_updated[0] == ('run-test-001', 'partial_failed')


@pytest.mark.skip(reason="WriteReport removed with write_results()")
def test_writer_report_includes_skipped_count(in_memory_db: sqlite3.Connection, setup_test_data: dict) -> None:
    """WriteReport includes count of skipped responses from idempotent writes."""
    # Arrange
    result = ExecutionResult(
        item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
        run_id="run-test-001",
        variant_id="var-abc-123",
        snapshot_id="snap-xyz-789",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=500,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
    )

    writer = ResultWriter(in_memory_db)

    # Act: Write twice
    report1 = writer.write_result(result)
    report2 = writer.write_result(result)

    # Assert
    assert report1.responses_written == 1
    assert report1.responses_skipped == 0
    assert report2.responses_written == 0
    assert report2.responses_skipped == 1


class TestErrorVersioning:
    """Regression tests for error versioning contract.

    ResultWriter is the sole writer for errors. Each error written for the
    same (run_id, variant_id, snapshot_id) must increment attempt_number.
    """

    @staticmethod
    def _setup_minimal_experiment(conn):
        """Create minimal FK records needed for error writes."""
        conn.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-test-001", "Test", "{}", "hash"),
        )
        conn.execute(
            "INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
            ("var-abc-123", "exp-test-001", "test/model", "sig", "{}"),
        )
        conn.execute(
            "INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
            ("snap-xyz-789", "exp-test-001", "q1", 1, "{}"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, experiment_id, config, status) VALUES (?, ?, ?, ?)",
            ("run-test-001", "exp-test-001", "{}", "pending"),
        )
        conn.commit()

    def test_write_error_increments_attempt_number(self, in_memory_db):
        """Multiple errors for the same item produce incrementing attempt_number."""
        from src.core.execution_engine import ExecutionResult
        from datetime import datetime

        # Create required FK records
        self._setup_minimal_experiment(in_memory_db)

        writer = ResultWriter(in_memory_db)

        # Write two failure results for the same item
        for i in range(2):
            error_result = ExecutionResult(
                item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
                run_id="run-test-001",
                variant_id="var-abc-123",
                snapshot_id="snap-xyz-789",
                question_id="q1",
                status="failure",
                error_type="timeout",
                error_message=f"Timeout attempt {i+1}",
                attempt_count=i + 1,
                response_text=None,
                selected_answer=None,
                parse_confidence=None,
                latency_ms=None,
                input_tokens=None,
                response_tokens=None,
                reasoning_tokens=None,
                raw_response=None,
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            writer.write_result(error_result)

        # Verify both errors exist with incrementing attempt_number
        cursor = in_memory_db.cursor()
        cursor.execute("""
            SELECT attempt_number, error_message
            FROM errors
            WHERE run_id = 'run-test-001'
            ORDER BY attempt_number ASC
        """)
        rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0]["attempt_number"] == 1
        assert "Timeout attempt 1" in rows[0]["error_message"]
        assert rows[1]["attempt_number"] == 2
        assert "Timeout attempt 2" in rows[1]["error_message"]

    def test_error_response_id_is_deterministic(self, in_memory_db):
        """response_id follows the deterministic format resp-{run_id}-{variant_id}-{snapshot_id}."""
        from src.core.execution_engine import ExecutionResult
        from datetime import datetime

        self._setup_minimal_experiment(in_memory_db)

        writer = ResultWriter(in_memory_db)
        error_result = ExecutionResult(
            item_id="run-test-001::var-abc-123::snap-xyz-789::it-1",
            run_id="run-test-001",
            variant_id="var-abc-123",
            snapshot_id="snap-xyz-789",
            question_id="q1",
            status="failure",
            error_type="api_error",
            error_message="Test error",
            attempt_count=1,
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=None,
            input_tokens=None,
            response_tokens=None,
            reasoning_tokens=None,
            raw_response=None,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
        writer.write_result(error_result)

        cursor = in_memory_db.cursor()
        cursor.execute("SELECT response_id FROM errors WHERE run_id = 'run-test-001'")
        row = cursor.fetchone()

        assert row is not None
        assert row["response_id"] == "resp-run-test-001-var-abc-123-snap-xyz-789"
