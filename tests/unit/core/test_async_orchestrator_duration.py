"""Test cases for AsyncOrchestrator._update_run_statuses() duration accumulation.

This module tests that the AsyncOrchestrator correctly accumulates duration
from successful responses when updating run statuses.
"""

import pytest
import sqlite3

from src.core.async_orchestrator import AsyncOrchestrator
from src.core.execution_engine import ExecutionResult


@pytest.fixture
def db_connection():
    """Create an in-memory SQLite database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

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
            latency_ms INTEGER,
            UNIQUE(run_id, variant_id, snapshot_id)
        );
    """)

    conn.execute(
        "INSERT INTO experiments VALUES (?, ?, ?, ?)",
        ("exp-001", "test-exp", "{}", "hash123"),
    )
    conn.execute(
        "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
        ("run-001", "exp-001", "{}", "pending", 0),
    )

    yield conn
    conn.close()


def create_success_result(
    run_id: str = "run-001",
    variant_id: str = "var-001",
    snapshot_id: str = "snap-001",
    question_id: str = "q-001",
    latency_ms: int = 1000,
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
        selected_answer="A",
        parse_confidence="clear",
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
        error_type="api_error",
        error_message="Test error",
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


class TestAsyncOrchestratorDurationAccumulation:
    """Test that AsyncOrchestrator._update_run_statuses accumulates duration."""

    def test_single_success_adds_latency(self, db_connection):
        """Test that a single success result adds its latency to duration."""
        orchestrator = AsyncOrchestrator(
            api_client=None,  # Not needed for this test
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        results = [create_success_result(latency_ms=1500)]
        orchestrator._update_run_statuses(results)

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 1500
        assert row["status"] == "completed"

    def test_multiple_successes_accumulate_latency(self, db_connection):
        """Test that multiple success results accumulate their latencies."""
        orchestrator = AsyncOrchestrator(
            api_client=None,
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        results = [
            create_success_result(snapshot_id="snap-001", question_id="q-001", latency_ms=1000),
            create_success_result(snapshot_id="snap-002", question_id="q-002", latency_ms=2000),
        ]
        orchestrator._update_run_statuses(results)

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 3000  # 1000 + 2000
        assert row["status"] == "completed"

    def test_failures_do_not_contribute_to_duration(self, db_connection):
        """Test that failed results do NOT add to duration."""
        orchestrator = AsyncOrchestrator(
            api_client=None,
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        results = [
            create_success_result(snapshot_id="snap-001", question_id="q-001", latency_ms=1500),
            create_failure_result(snapshot_id="snap-002", question_id="q-002"),
        ]
        orchestrator._update_run_statuses(results)

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 1500  # Only from success
        assert row["status"] == "partial_failed"

    def test_all_failures_duration_remains_zero(self, db_connection):
        """Test that if all results fail, duration remains 0."""
        orchestrator = AsyncOrchestrator(
            api_client=None,
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        results = [create_failure_result()]
        orchestrator._update_run_statuses(results)

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 0
        assert row["status"] == "failed"

    def test_null_latency_does_not_contribute(self, db_connection):
        """Test that success with null latency doesn't add to duration."""
        orchestrator = AsyncOrchestrator(
            api_client=None,
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        result = create_success_result(latency_ms=None)
        orchestrator._update_run_statuses([result])

        row = db_connection.execute(
            "SELECT duration, status FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()

        assert row["duration"] == 0
        assert row["status"] == "completed"

    def test_multiple_runs_accumulate_duration_independently(self, db_connection):
        """Test that multiple runs accumulate duration independently."""
        # Create second run
        db_connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?)",
            ("run-002", "exp-001", "{}", "pending", 0),
        )
        db_connection.commit()

        orchestrator = AsyncOrchestrator(
            api_client=None,
            db_connection=db_connection,
            randomizer=None,
            parser=None,
        )

        results = [
            create_success_result(run_id="run-001", snapshot_id="snap-001", question_id="q-001", latency_ms=1000),
            create_success_result(run_id="run-002", snapshot_id="snap-002", question_id="q-002", latency_ms=2500),
        ]
        orchestrator._update_run_statuses(results)

        row1 = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-001",),
        ).fetchone()
        row2 = db_connection.execute(
            "SELECT duration FROM runs WHERE run_id = ?",
            ("run-002",),
        ).fetchone()

        assert row1["duration"] == 1000
        assert row2["duration"] == 2500
