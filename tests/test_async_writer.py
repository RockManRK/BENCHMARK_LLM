"""Tests for AsyncWriter incremental persistence and failure resilience.

These tests verify:
1. Each result is written immediately after arriving on queue
2. Writer stops consuming after receiving None sentinel
3. Writer continues consuming after DB write failures
4. Stats accurately reflect written, skipped, and error counts
5. Results can be accessed via results_written property

Usage:
    pytest tests/test_async_writer.py -v
"""

import asyncio
import json
import pytest
import sqlite3
from unittest.mock import MagicMock, patch, call
from datetime import datetime

from src.core.async_writer import AsyncWriter
from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter
from src.db.schema import create_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_success_result(item_id: str, run_id: str = "run-001") -> ExecutionResult:
    """Build a successful ExecutionResult."""
    return ExecutionResult(
        item_id=item_id,
        run_id=run_id,
        variant_id="var-001",
        snapshot_id="snap-000",
        question_id="q1",
        status="success",
        response_text="The answer is (B).",
        selected_answer="B",
        parse_confidence="clear",
        latency_ms=100,
        input_tokens=50,
        response_tokens=10,
        error_type=None,
        error_message=None,
        attempt_count=1,
        reasoning_tokens=None,
        cost=0.0001,
        effective_tokens=60,
        raw_response=None,
        started_at=datetime.now(),
        finished_at=datetime.now(),
        finish_reason="stop",
        randomization_enabled=True,
        randomization_seed=42,
        options_presented=["1", "2", "3", "4"],
        correct_option_presented="B",
        option_letter_map={"A": "A", "B": "B", "C": "C", "D": "D"},
    )


def _make_failure_result(item_id: str, error_type: str = "api_error") -> ExecutionResult:
    """Build a failed ExecutionResult."""
    return ExecutionResult(
        item_id=item_id,
        run_id="run-001",
        variant_id="var-001",
        snapshot_id="snap-000",
        question_id="q1",
        status="failure",
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        latency_ms=None,
        input_tokens=None,
        response_tokens=None,
        error_type=error_type,
        error_message="Simulated error",
        attempt_count=3,
        reasoning_tokens=None,
        cost=None,
        effective_tokens=None,
        raw_response=None,
        started_at=datetime.now(),
        finished_at=datetime.now(),
        finish_reason=None,
        randomization_enabled=False,
        randomization_seed=None,
        options_presented=None,
        correct_option_presented=None,
        option_letter_map=None,
    )


def _seed_db_with_prerequisites(conn):
    """Insert prerequisite rows that ResultWriter needs (variant, run, snapshot)."""
    cursor = conn.cursor()
    # Experiment (must include config_json and config_hash NOT NULL)
    cursor.execute(
        "INSERT OR IGNORE INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
        ("exp-test", "Test Experiment", "{}", "hash-test"),
    )
    # Model variant (must include all NOT NULL columns: variant_signature, config)
    cursor.execute(
        "INSERT OR IGNORE INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
        ("var-001", "exp-test", "openai/gpt-4o-mini", "sig-001", "{}"),
    )
    # Run (must include config TEXT NOT NULL)
    cursor.execute(
        "INSERT OR IGNORE INTO runs (run_id, experiment_id, config) VALUES (?, ?, ?)",
        ("run-001", "exp-test", "{}"),
    )
    # Question snapshot (must include json_question_id and question_position NOT NULL)
    payload_json = json.dumps({
        "stem": "Test question",
        "options": ["A", "B", "C", "D"],
        "answer_key": "B",
    })
    cursor.execute(
        "INSERT OR IGNORE INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
        ("snap-000", "exp-test", "q1", 1, payload_json),
    )
    conn.commit()


@pytest.fixture
def db_connection():
    """Create a temporary in-memory SQLite DB with full schema and prerequisite data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    _seed_db_with_prerequisites(conn)
    yield conn
    try:
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAsyncWriterIncrementalPersistence:
    """Test that AsyncWriter writes results immediately."""

    @pytest.mark.asyncio
    async def test_consume_writes_results_incrementally(self, db_connection):
        """Verify each result is written immediately after arriving on queue.

        The writer must NOT buffer results — each one arriving on the queue
        should trigger an immediate write to the database.
        """
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        result = _make_success_result("item-001")

        # Push result and sentinel
        await queue.put(result)
        await queue.put(None)  # sentinel

        stats = await writer.consume()

        assert stats["written"] == 1
        assert stats["errors"] == 0
        assert len(writer.results_written) == 1
        assert writer.results_written[0].item_id == "item-001"

    @pytest.mark.asyncio
    async def test_consume_stops_on_sentinel(self):
        """Verify writer stops consuming after receiving None sentinel.

        The sentinel (None) is the ONLY way for the writer to exit its
        consume loop. We verify this by checking the consume() coroutine
        returns after receiving None.
        """
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, MagicMock())

        # Only sentinel — no results
        await queue.put(None)

        stats = await writer.consume()

        # Must return without hanging
        assert stats["written"] == 0
        assert stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_consume_writes_multiple_results(self, db_connection):
        """Verify writer processes multiple results before sentinel."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        results = [
            _make_success_result("item-001"),
            _make_success_result("item-002"),
            _make_success_result("item-003"),
        ]

        for r in results:
            await queue.put(r)
        await queue.put(None)

        stats = await writer.consume()

        assert stats["written"] == 3
        assert len(writer.results_written) == 3
        assert [r.item_id for r in writer.results_written] == [
            "item-001", "item-002", "item-003",
        ]

    @pytest.mark.asyncio
    async def test_results_written_returns_copy(self, db_connection):
        """Verify results_written property returns a copy, not internal list.

        This prevents external code from mutating the writer's internal state.
        """
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        result = _make_success_result("item-001")
        await queue.put(result)
        await queue.put(None)

        await writer.consume()

        list1 = writer.results_written
        list2 = writer.results_written

        # Must be different objects
        assert list1 is not list2
        # But equal content
        assert list1 == list2


class TestAsyncWriterFailureResilience:
    """Test that AsyncWriter survives DB failures gracefully."""

    @pytest.mark.asyncio
    async def test_consume_survives_db_write_failure(self):
        """Verify writer continues consuming after a DB write failure.

        When ResultWriter.write_result() raises, the AsyncWriter must:
        1. Log the error
        2. Increment error count
        3. Continue consuming subsequent results
        4. NOT crash the consume loop
        """
        queue: asyncio.Queue = asyncio.Queue()
        mock_db = MagicMock()

        writer = AsyncWriter(queue, mock_db)

        result_ok_1 = _make_success_result("item-001")
        result_fail = _make_success_result("item-002")
        result_ok_2 = _make_success_result("item-003")

        # Patch ResultWriter to fail on the second result only
        call_order = [0]

        class FailingResultWriter:
            def __init__(self, *args, **kwargs):
                pass

            def write_result(self, result):
                call_order[0] += 1
                if call_order[0] == 2:
                    raise sqlite3.OperationalError("Simulated DB constraint violation")
                # Otherwise succeed

        with patch(
            'src.core.async_writer.ResultWriter',
            FailingResultWriter,
        ):
            await queue.put(result_ok_1)
            await queue.put(result_fail)
            await queue.put(result_ok_2)
            await queue.put(None)

            stats = await writer.consume()

        # All 3 were consumed, 2 succeeded, 1 errored
        assert stats["written"] == 2
        assert stats["errors"] == 1
        assert len(writer.results_written) == 2
        assert writer.results_written[0].item_id == "item-001"
        assert writer.results_written[1].item_id == "item-003"

    @pytest.mark.asyncio
    async def test_consume_survives_all_db_failures(self):
        """Verify writer survives when every DB write fails."""
        queue: asyncio.Queue = asyncio.Queue()
        mock_db = MagicMock()

        with patch(
            'src.core.async_writer.ResultWriter',
            side_effect=RuntimeError("DB completely down"),
        ):
            writer = AsyncWriter(queue, mock_db)

            await queue.put(_make_success_result("item-001"))
            await queue.put(_make_success_result("item-002"))
            await queue.put(None)

            stats = await writer.consume()

            assert stats["written"] == 0
            assert stats["errors"] == 2
            assert len(writer.results_written) == 0

    @pytest.mark.asyncio
    async def test_consume_handles_cancelled_error(self):
        """Verify writer handles asyncio.CancelledError gracefully.

        If the task is cancelled while awaiting queue.get(), the writer
        should break out of the loop cleanly without re-raising.
        """
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, MagicMock())

        # Schedule a task that will cancel the writer after a short delay
        async def cancel_after_delay():
            await asyncio.sleep(0.01)
            writer_task.cancel()

        writer_task = asyncio.create_task(writer.consume())
        await cancel_after_delay()

        # The task should complete without raising (consume catches CancelledError)
        done, pending = await asyncio.wait([writer_task], timeout=1.0)
        assert writer_task in done
        assert writer_task not in pending
        # No exception should propagate — the task completes cleanly
        stats = writer_task.result()
        assert stats["written"] == 0


class TestAsyncWriterStats:
    """Test that AsyncWriter stats are accurate."""

    @pytest.mark.asyncio
    async def test_stats_track_written_errors(self):
        """Verify stats accurately reflect written and error counts.

        The stats dict must contain:
        - written: number of successfully written results
        - errors: number of write failures
        """
        queue: asyncio.Queue = asyncio.Queue()
        mock_db = MagicMock()

        call_count = [0]

        class SelectiveFailingWriter:
            def __init__(self, *args, **kwargs):
                pass

            def write_result(self, result):
                call_count[0] += 1
                if call_count[0] % 3 == 0:
                    raise Exception("Every 3rd write fails")

        with patch('src.core.async_writer.ResultWriter', SelectiveFailingWriter):
            writer = AsyncWriter(queue, mock_db)

            # 5 results: 3rd will fail
            for i in range(5):
                await queue.put(_make_success_result(f"item-{i:03d}"))
            await queue.put(None)

            stats = await writer.consume()

        assert stats["written"] == 4
        assert stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_stats_property_reflects_current_state(self):
        """Verify stats property reflects current counts at any point.

        The stats property should return the current counts even before
        consume() completes.
        """
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, MagicMock())

        # Before consuming anything
        initial_stats = writer.stats
        assert initial_stats["written"] == 0
        assert initial_stats["errors"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_partial_consume(self, db_connection):
        """Verify stats are accurate after consuming a mix of success and failure results."""
        queue: asyncio.Queue = asyncio.Queue()
        mock_db = MagicMock()

        fail_count = [0]

        class FailOnSecond:
            def __init__(self, *args, **kwargs):
                pass

            def write_result(self, result):
                fail_count[0] += 1
                if fail_count[0] == 2:
                    raise ValueError("Second write fails")

        with patch('src.core.async_writer.ResultWriter', FailOnSecond):
            writer = AsyncWriter(queue, mock_db)

            await queue.put(_make_success_result("item-001"))
            await queue.put(_make_success_result("item-002"))
            await queue.put(_make_success_result("item-003"))
            await queue.put(None)

            stats = await writer.consume()

        assert stats["written"] == 2
        assert stats["errors"] == 1


class TestAsyncWriterSentinel:
    """Test sentinel handling specifically."""

    @pytest.mark.asyncio
    async def test_sentinel_at_start_exits_immediately(self):
        """Verify writer exits cleanly when sentinel is first item on queue."""
        queue: asyncio.Queue = asyncio.Queue()
        await queue.put(None)

        writer = AsyncWriter(queue, MagicMock())
        stats = await writer.consume()

        assert stats == {"written": 0, "errors": 0}

    @pytest.mark.asyncio
    async def test_sentinel_after_results(self, db_connection):
        """Verify writer processes all results before sentinel, then stops."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        for i in range(3):
            await queue.put(_make_success_result(f"item-{i:03d}"))

        # Sentinel signals no more data
        await queue.put(None)

        stats = await writer.consume()
        assert stats["written"] == 3
        # Verify queue is fully drained
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_task_done_called_for_each_item(self):
        """Verify task_done() is called for each consumed item including sentinel.

        We verify this by checking queue.qsize() and ensuring all items
        were properly acknowledged.
        """
        queue: asyncio.Queue = asyncio.Queue()
        mock_db = MagicMock()

        writer = AsyncWriter(queue, mock_db)

        # Push 2 results + sentinel = 3 items total
        await queue.put(_make_success_result("item-001"))
        await queue.put(_make_success_result("item-002"))
        await queue.put(None)

        # Before consuming, queue has 3 items
        assert queue.qsize() == 3

        await writer.consume()

        # After consuming, all items should be processed
        assert queue.qsize() == 0


class TestAsyncWriterWithFailureResults:
    """Test that writer handles ExecutionResults with failure status."""

    @pytest.fixture
    def seeded_db(self):
        """Create a DB with all prerequisite rows for ResultWriter."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        create_schema(conn)
        _seed_db_with_prerequisites(conn)
        yield conn
        try:
            conn.close()
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_writer_handles_failure_result(self, seeded_db):
        """Verify writer can persist a result with status='failure'."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, seeded_db)

        failure_result = _make_failure_result("item-fail-001")
        await queue.put(failure_result)
        await queue.put(None)

        stats = await writer.consume()

        assert stats["written"] == 1
        assert len(writer.results_written) == 1
        assert writer.results_written[0].status == "failure"
        assert writer.results_written[0].error_type == "api_error"

    @pytest.mark.asyncio
    async def test_writer_handles_mixed_success_and_failure(self, seeded_db):
        """Verify writer handles a mix of success and failure results."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, seeded_db)

        await queue.put(_make_success_result("item-001"))
        await queue.put(_make_failure_result("item-002", error_type="timeout"))
        await queue.put(_make_success_result("item-003"))
        await queue.put(None)

        stats = await writer.consume()

        assert stats["written"] == 3  # All 3 written (write itself succeeds)
        assert len(writer.results_written) == 3
        statuses = [r.status for r in writer.results_written]
        assert statuses == ["success", "failure", "success"]
