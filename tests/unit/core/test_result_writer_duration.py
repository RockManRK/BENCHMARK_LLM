"""Test cases for runs.duration accumulation in ResultWriter.

This module tests that:
1. runs.duration is incremented by latency_ms of successful responses
2. Failed responses do NOT contribute to duration
3. Duration accumulates across multiple executions (incremental runs)
4. Duration is correctly persisted in the database
"""

import pytest
import sqlite3
from unittest.mock import MagicMock

from src.core.result_writer import ResultWriter, WriteReport
from src.core.execution_engine import ExecutionResult


@pytest.fixture
def db_connection():
    """Create an in-memory SQLite database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create minimal schema for testing
    conn.executescript("""
        CREATE TABLE experiments (
            experiment_id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            config_json TEXT NOT NULL,
            config_hash TEXT NOT NULL
        );

        CREATE TABLE model_variants (
            variant_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            variant_signature TEXT NOT NULL,
            config TEXT NOT NULL
        );

        CREATE TABLE question_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            json_question_id TEXT NOT NULL,
            question_position INTEGER NOT NULL,
            question_payload TEXT NOT NULL
        );

        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            config TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            duration INTEGER DEFAULT 0
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
            raw_response_consolidated TEXT,
            request_json TEXT,
            cost REAL,
            input_tokens INTEGER,
            response_tokens INTEGER,
            reasoning_tokens INTEGER,
            effective_tokens INTEGER,
            latency_ms INTEGER,
            started_at TIMESTAMP,
            finished_at TIMESTAMP,
            randomization_enabled BOOLEAN DEFAULT FALSE,
            randomization_seed INTEGER,
            options_presented TEXT,
            correct_option_presented TEXT,
            option_letter_map TEXT,
            UNIQUE(run_id, variant_id, snapshot_id)
        );

        CREATE TABLE errors (
            error_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            variant_id TEXT NOT NULL,
            snapshot_id NOT NULL,
            question_id TEXT NOT NULL,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            attempt_count INTEGER DEFAULT 1
        );
    """)

    # Insert test data
    conn.execute(
        "INSERT INTO experiments VALUES (?, ?, ?, ?)",
        ("exp-001", "test-exp", "{}", "hash123"),
    )
    conn.execute(
        "INSERT INTO model_variants VALUES (?, ?, ?, ?, ?)",
        ("var-001", "exp-001", "openai/gpt-4", "sig1", "{}"),
    )
    conn.execute(
        "INSERT INTO question_snapshots VALUES (?, ?, ?, ?, ?)",
        ("snap-001", "exp-001", "q-001", 1, "{}"),
    )
    conn.execute(
        "INSERT INTO question_snapshots VALUES (?, ?, ?, ?, ?)",
        ("snap-002", "exp-001", "q-002", 2, "{}"),
    )
    conn.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
        ("run-001", "exp-001", "{}", "pending", 0),
    )

    yield conn
    conn.close()


@pytest.fixture
def writer(db_connection):
    """Create ResultWriter with test database."""
    return ResultWriter(db_connection)


def create_success_result(
    run_id: str = "run-001",
    variant_id: str = "var-001",
    snapshot_id: str = "snap-001",
    question_id: str = "q-001",
    latency_ms: int = 1000,
    selected_answer: str = "A",
    parse_confidence: str = "clear",
) -> ExecutionResult:
    """Helper to create a success ExecutionResult."""
    return ExecutionResult(
        item_id=f"item-{variant_id}-{snapshot_id}",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status="success",
        response_text="Test response",
        selected_answer=selected_answer,
        parse_confidence=parse_confidence,
        latency_ms=latency_ms,
        input_tokens=100,
        response_tokens=50,
        reasoning_tokens=0,
        cost=0.001,
        effective_tokens=150,
        error_type=None,
        error_message=None,
        attempt_count=1,
        raw_response="{}",
        raw_response_consolidated="{}",
        started_at=None,
        finished_at=None,
        finish_reason="stop",
        error_details=None,
        request_json="{}",
        randomization_enabled=False,
        randomization_seed=None,
        options_presented=None,
        correct_option_presented=None,
        option_letter_map=None,
    )


def create_failure_result(
    run_id: str = "run-001",
    variant_id: str = "var-001",
    snapshot_id: str = "snap-001",
    question_id: str = "q-001",
    error_type: str = "api_error",
    error_message: str = "Test error",
) -> ExecutionResult:
    """Helper to create a failure ExecutionResult."""
    return ExecutionResult(
        item_id=f"item-{variant_id}-{snapshot_id}",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status="failure",
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        latency_ms=None,
        input_tokens=None,
        response_tokens=None,
        reasoning_tokens=None,
        cost=None,
        effective_tokens=None,
        error_type=error_type,
        error_message=error_message,
        attempt_count=1,
        raw_response=None,
        raw_response_consolidated=None,
        started_at=None,
        finished_at=None,
        finish_reason=None,
        error_details=None,
        request_json=None,
        randomization_enabled=False,
        randomization_seed=None,
        options_presented=None,
        correct_option_presented=None,
        option_letter_map=None,
    )


class TestDurationAccumulation:
    """Test that runs.duration is correctly accumulated from successful responses."""

    def test_single_success_response_adds_latency(self, writer: ResultWriter, db_connection):
        """Test that a single successful response adds its latency to run duration."""
        result = create_success_result(latency_ms=1500)

        report = writer.write_results([result])

        # Verify write report
        assert report.responses_written == 1
        assert len(report.runs_updated) == 1

        # Verify duration in database
        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 1500
        assert row["status"] == "completed"

    def test_multiple_success_responses_accumulate_latency(
        self, writer: ResultWriter, db_connection
    ):
        """Test that multiple successful responses accumulate their latencies."""
        results = [
            create_success_result(
                snapshot_id="snap-001",
                question_id="q-001",
                latency_ms=1000,
            ),
            create_success_result(
                snapshot_id="snap-002",
                question_id="q-002",
                latency_ms=2000,
            ),
        ]

        report = writer.write_results(results)

        # Verify duration is sum of both latencies
        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 3000  # 1000 + 2000
        assert row["status"] == "completed"

    def test_failed_response_does_not_contribute_to_duration(
        self, writer: ResultWriter, db_connection
    ):
        """Test that failed responses do NOT add to run duration."""
        results = [
            create_success_result(
                snapshot_id="snap-001",
                question_id="q-001",
                latency_ms=1500,
            ),
            create_failure_result(
                snapshot_id="snap-002",
                question_id="q-002",
            ),
        ]

        report = writer.write_results(results)

        # Only the success response should contribute to duration
        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 1500  # Only from success
        assert row["status"] == "partial_failed"

    def test_all_failures_duration_remains_zero(self, writer: ResultWriter, db_connection):
        """Test that if all responses fail, duration remains 0."""
        results = [
            create_failure_result(
                snapshot_id="snap-001",
                question_id="q-001",
            ),
        ]

        report = writer.write_results(results)

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 0
        assert row["status"] == "failed"


class TestIncrementalExecution:
    """Test that duration accumulates across multiple executions."""

    def test_duration_accumulates_across_executions(self, writer: ResultWriter, db_connection):
        """Test that duration is accumulated when run is executed multiple times."""
        # First execution: 2 successful responses
        first_results = [
            create_success_result(
                snapshot_id="snap-001",
                question_id="q-001",
                latency_ms=1000,
            ),
        ]
        writer.write_results(first_results)

        # Verify duration after first execution
        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()
        assert row["duration"] == 1000

        # Second execution: 1 more successful response
        # Note: In real scenario, these would have different snapshot_id
        # For testing, we'll manually reset the run status to allow re-execution
        db_connection.execute(
            "UPDATE runs SET status = 'pending' WHERE run_id = ?",
            ("run-001",),
        )
        db_connection.commit()

        second_results = [
            create_success_result(
                snapshot_id="snap-002",
                question_id="q-002",
                latency_ms=2500,
            ),
        ]
        writer.write_results(second_results)

        # Verify duration is accumulated
        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 3500  # 1000 + 2500

    def test_mixed_successes_and_failures_accumulate_correctly(
        self, writer: ResultWriter, db_connection
    ):
        """Test that only successful responses contribute to accumulated duration."""
        # First execution: 1 success, 1 failure
        first_results = [
            create_success_result(
                snapshot_id="snap-001",
                question_id="q-001",
                latency_ms=1200,
            ),
            create_failure_result(
                snapshot_id="snap-002",
                question_id="q-002",
            ),
        ]
        writer.write_results(first_results)

        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()
        assert row["duration"] == 1200

        # Second execution: 1 success
        db_connection.execute(
            "UPDATE runs SET status = 'pending' WHERE run_id = ?",
            ("run-001",),
        )
        db_connection.commit()

        # Need to use different snapshot to avoid idempotency skip
        second_results = [
            create_success_result(
                snapshot_id="snap-002",
                question_id="q-002",
                latency_ms=800,
            ),
        ]
        writer.write_results(second_results)

        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 2000  # 1200 + 800


class TestEdgeCases:
    """Test edge cases for duration accumulation."""

    def test_null_latency_does_not_cause_error(self, writer: ResultWriter, db_connection):
        """Test that success response with null latency doesn't break accumulation."""
        result = create_success_result(latency_ms=None)
        # This shouldn't happen in practice, but let's be safe

        # The code filters out None latency, so this should not add to duration
        report = writer.write_results([result])

        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        # Duration should be 0 since latency_ms was None
        assert row["duration"] == 0

    def test_zero_latency_is_added(self, writer: ResultWriter, db_connection):
        """Test that zero latency is still added to duration (edge case)."""
        result = create_success_result(latency_ms=0)

        report = writer.write_results([result])

        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        # Duration should be 0 (0 latency added)
        assert row["duration"] == 0

    def test_large_latency_values(self, writer: ResultWriter, db_connection):
        """Test that large latency values are handled correctly."""
        result = create_success_result(latency_ms=30000)  # 30 seconds

        report = writer.write_results([result])

        row = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 30000
