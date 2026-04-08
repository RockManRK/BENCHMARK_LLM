"""Unit tests for RunFinalizer.

Tests cover:
1. All responses succeeded → status = "completed", duration = SUM of all latency_ms
2. All responses failed → status = "failed", duration = 0 (no successful responses to sum)
3. Mixed → status = "partial_failed", duration = SUM of successful only
4. Empty run (no responses) → status = "completed", duration = 0
5. Duration is integer milliseconds
"""

import sqlite3
import pytest

from src.core.run_finalizer import RunFinalizer
from src.db.schema import create_schema, drop_all_tables


@pytest.fixture()
def conn():
    """Provide an in-memory database with full schema and seed data."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    create_schema(c)

    # Seed experiment (FK target for runs, variants, snapshots)
    _seed_experiment(c)

    # Seed model variants (FK target for responses)
    _seed_variant(c, "v1")
    _seed_variant(c, "v2")

    # Seed question snapshots (FK target for responses)
    _seed_snapshot(c, "s1", question_position=1)
    _seed_snapshot(c, "s2", question_position=2)

    yield c
    drop_all_tables(c)
    c.close()


def _seed_run(conn, run_id: str, status: str = "pending") -> None:
    """Insert a run row for testing. Requires experiment 'exp-test' to exist."""
    conn.execute(
        "INSERT INTO runs (run_id, experiment_id, config, status) VALUES (?, ?, ?, ?)",
        (run_id, "exp-test", "{}", status),
    )
    conn.commit()


def _seed_experiment(conn, experiment_id: str = "exp-test") -> None:
    """Insert an experiment row for testing (FK target for runs, variants, snapshots)."""
    import json
    config = json.dumps({"RUN_RESPONSES_SEED": 42})
    conn.execute(
        "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
        (experiment_id, "test-experiment", config, "hash-test"),
    )
    conn.commit()


def _seed_variant(conn, variant_id: str = "v1", experiment_id: str = "exp-test") -> None:
    """Insert a model variant row for testing (FK target for responses)."""
    import json
    config = json.dumps({})
    conn.execute(
        "INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
        (variant_id, experiment_id, "test-model", f"sig-{variant_id}", config),
    )
    conn.commit()


def _seed_snapshot(conn, snapshot_id: str = "s1", experiment_id: str = "exp-test", question_position: int = 1) -> None:
    """Insert a question snapshot row for testing (FK target for responses)."""
    import json
    payload = json.dumps({
        "stem": "Test question?",
        "options": {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
        "answer_key": "A",
        "meta": {},
        "assets": [],
    })
    conn.execute(
        "INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
        (snapshot_id, experiment_id, f"q-{snapshot_id}", question_position, payload),
    )
    conn.commit()


def _seed_response(
    conn,
    run_id: str,
    variant_id: str,
    snapshot_id: str,
    latency_ms: int | None = None,
    raw_response: str | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a response row for testing."""
    import json
    response_id = f"resp-{run_id}-{variant_id}-{snapshot_id}"
    options = json.dumps({"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"})
    conn.execute(
        """
        INSERT INTO responses (
            response_id, run_id, variant_id, snapshot_id,
            model_id, question_id, latency_ms, raw_response,
            options_presented, randomization_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            response_id,
            run_id,
            variant_id,
            snapshot_id,
            "test-model",
            "q-1",
            latency_ms,
            raw_response,
            options,
            False,
        ),
    )
    conn.commit()


def _seed_error_response(
    conn,
    run_id: str,
    variant_id: str,
    snapshot_id: str,
    error_message: str = "API timeout",
) -> None:
    """Insert an error row for testing (goes to errors table, not responses)."""
    error_id = f"err-{run_id}-{variant_id}-{snapshot_id}"
    conn.execute(
        """
        INSERT INTO errors (
            error_id, run_id, variant_id, snapshot_id,
            question_id, error_type, error_message, attempt_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            error_id,
            run_id,
            variant_id,
            snapshot_id,
            "q-1",
            "api_error",
            error_message,
            1,
        ),
    )
    conn.commit()


class TestRunFinalizerAllSucceeded:
    """Test: All responses succeeded → status = 'completed', duration = SUM of all latency_ms."""

    def test_all_succeeded_status_and_duration(self, conn):
        run_id = "run-all-ok"
        _seed_run(conn, run_id)
        _seed_response(conn, run_id, "v1", "s1", latency_ms=100, raw_response="{}")
        _seed_response(conn, run_id, "v1", "s2", latency_ms=200, raw_response="{}")
        _seed_response(conn, run_id, "v2", "s1", latency_ms=300, raw_response="{}")

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert result["status"] == "completed"
        assert result["duration_ms"] == 600  # 100 + 200 + 300
        assert result["response_count"] == 3

        # Verify DB state
        row = conn.execute("SELECT status, duration FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row["status"] == "completed"
        assert row["duration"] == 600


class TestRunFinalizerAllFailed:
    """Test: All responses failed → status = 'failed', duration = 0."""

    def test_all_failed_status_and_duration(self, conn):
        run_id = "run-all-fail"
        _seed_run(conn, run_id)
        _seed_error_response(conn, run_id, "v1", "s1", error_message="API timeout")
        _seed_error_response(conn, run_id, "v1", "s2", error_message="Rate limit")

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert result["status"] == "failed"
        assert result["duration_ms"] == 0  # no successful responses to sum
        assert result["response_count"] == 0  # no responses with raw_response

        row = conn.execute("SELECT status, duration FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row["status"] == "failed"
        assert row["duration"] == 0


class TestRunFinalizerMixed:
    """Test: Mixed → status = 'partial_failed', duration = SUM of successful only."""

    def test_mixed_status_and_duration(self, conn):
        run_id = "run-mixed"
        _seed_run(conn, run_id)
        _seed_response(conn, run_id, "v1", "s1", latency_ms=150, raw_response="{}")
        _seed_response(conn, run_id, "v1", "s2", latency_ms=250, raw_response="{}")
        _seed_error_response(conn, run_id, "v2", "s1", error_message="API timeout")
        _seed_response(conn, run_id, "v2", "s2", latency_ms=100, raw_response="{}")

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert result["status"] == "partial_failed"
        assert result["duration_ms"] == 500  # 150 + 250 + 100 (only successful)
        assert result["response_count"] == 3  # 3 with raw_response, 1 with error

        row = conn.execute("SELECT status, duration FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row["status"] == "partial_failed"
        assert row["duration"] == 500


class TestRunFinalizerEmpty:
    """Test: Empty run (no responses) → status = 'completed', duration = 0."""

    def test_empty_run_status_and_duration(self, conn):
        run_id = "run-empty"
        _seed_run(conn, run_id)

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert result["status"] == "completed"
        assert result["duration_ms"] == 0
        assert result["response_count"] == 0

        row = conn.execute("SELECT status, duration FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        assert row["status"] == "completed"
        assert row["duration"] == 0


class TestRunFinalizerDurationType:
    """Test: Duration is integer milliseconds."""

    def test_duration_is_integer(self, conn):
        run_id = "run-int-check"
        _seed_run(conn, run_id)
        _seed_response(conn, run_id, "v1", "s1", latency_ms=123, raw_response="{}")

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert isinstance(result["duration_ms"], int)
        assert result["duration_ms"] == 123

    def test_duration_is_integer_when_zero(self, conn):
        run_id = "run-int-zero"
        _seed_run(conn, run_id)

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert isinstance(result["duration_ms"], int)
        assert result["duration_ms"] == 0

    def test_duration_coalesces_null_latency(self, conn):
        """Ensure NULL latency_ms values are handled via COALESCE."""
        run_id = "run-null-latency"
        _seed_run(conn, run_id)
        # Insert response with NULL latency_ms
        import json
        response_id = f"resp-{run_id}-v1-s1"
        options = json.dumps({"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"})
        conn.execute(
            """
            INSERT INTO responses (
                response_id, run_id, variant_id, snapshot_id,
                model_id, question_id, latency_ms, raw_response,
                options_presented, randomization_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                response_id,
                run_id,
                "v1",
                "s1",
                "test-model",
                "q-1",
                None,  # NULL latency
                "{}",  # but has raw_response
                options,
                False,
            ),
        )
        conn.commit()

        finalizer = RunFinalizer(conn)
        result = finalizer.finalize_run(run_id)

        assert isinstance(result["duration_ms"], int)
        assert result["duration_ms"] == 0  # COALESCE(SUM(NULL), 0) = 0
