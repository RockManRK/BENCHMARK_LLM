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


class _SelectiveFailureResultWriter(ResultWriter):
    """Wraps the REAL ResultWriter (real SQLite writes on success),
    injecting failures keyed by `item_id` + per-item attempt number —
    never a global call counter, which conflates a retried item's earlier
    failed attempts with entirely different items being processed next
    (the exact bug the pre-rewrite G8 tests had — see
    docs/status/known-issues.md, 2026-08-21).

    `fail_until_attempt`: item_id -> N. Attempts 1..N for that item_id
    raise; attempt N+1 delegates to the real write. N=None means the item
    fails on every attempt (permanent failure — exhausts AsyncWriter's
    retries and triggers fail-fast abort). item_ids absent from the dict
    never fail.
    """

    def __init__(self, *args, fail_until_attempt: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fail_until_attempt = fail_until_attempt or {}
        self._attempts_by_item: dict[str, int] = {}

    def write_result(self, result):
        item_id = result.item_id
        attempt = self._attempts_by_item.get(item_id, 0) + 1
        self._attempts_by_item[item_id] = attempt
        fail_until = self._fail_until_attempt.get(item_id, 0)
        if fail_until is None or attempt <= fail_until:
            raise sqlite3.OperationalError(
                f"Simulated failure for {item_id}, attempt {attempt}"
            )
        return super().write_result(result)


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


class TestAsyncWriterFailFastContract:
    """Normative contract (user decision, 2026-08-21, following an
    independent G8 investigation that confirmed the pre-existing tests
    here were wrong but also surfaced a real coverage gap — the suite had
    no test actually proving fail-fast behavior): AsyncWriter keeps its
    CURRENT fail-fast behavior. After a permanent write failure (all
    retries exhausted): run the configured retries; set aborted=True;
    fill abort_info; emit the CRITICAL event; stop consuming; stop new
    items from being produced (the caller sees abort_event set); finalize
    the Run via the existing RunFinalizer flow; do NOT silently continue
    processing later items. Production was NOT changed to implement
    "per-item resilience" — these tests exist to lock in the fail-fast
    contract that was already true in the code, not to test new
    behavior. See docs/status/known-issues.md."""

    @pytest.mark.asyncio
    async def test_transient_failure_then_retry_succeeds(self, db_connection):
        """One attempt fails, the retry succeeds: written increments,
        errors does NOT increment (a retried item that ultimately
        succeeds is not an error), aborted stays False."""
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _SelectiveFailureResultWriter(
                *args, fail_until_attempt={"item-001": 1}, **kwargs
            )

        with patch('src.core.async_writer.ResultWriter', side_effect=_writer_factory):
            writer = AsyncWriter(queue, db_connection)
            await queue.put(_make_success_result("item-001"))
            await queue.put(None)
            stats = await writer.consume()

        assert stats["written"] == 1
        assert stats["errors"] == 0
        assert stats["aborted"] is False
        assert stats["abort_info"] is None
        assert len(writer.results_written) == 1

    @pytest.mark.asyncio
    async def test_permanent_failure_on_second_item_fails_fast(self, db_connection):
        """Permanent failure (all retries exhausted) on the SECOND item:
        the first item is persisted; the second fails permanently;
        written=1, errors=1, aborted=True, abort_info correctly
        identifies the failing write; the third item and the sentinel
        are never even dequeued — fail-fast, not per-item resilience."""
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _SelectiveFailureResultWriter(
                *args, fail_until_attempt={"item-002": None}, **kwargs
            )

        with patch('src.core.async_writer.ResultWriter', side_effect=_writer_factory):
            writer = AsyncWriter(queue, db_connection)
            await queue.put(_make_success_result("item-001"))
            await queue.put(_make_success_result("item-002"))
            await queue.put(_make_success_result("item-003"))
            await queue.put(None)
            stats = await writer.consume()

        assert stats["written"] == 1
        assert stats["errors"] == 1
        assert stats["aborted"] is True
        assert stats["abort_info"] is not None
        assert stats["abort_info"]["run_id"] == "run-001"
        assert stats["abort_info"]["variant_id"] == "var-001"
        assert stats["abort_info"]["snapshot_id"] == "snap-000"
        assert stats["abort_info"]["attempts"] == AsyncWriter.MAX_RETRIES
        assert "item-002" in stats["abort_info"]["error"]
        assert len(writer.results_written) == 1
        assert writer.results_written[0].item_id == "item-001"

        # item-003 and the sentinel were never dequeued at all (not just
        # un-acknowledged) — the consume loop broke before calling
        # queue.get() again.
        assert queue.qsize() == 2

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
    async def test_stats_distinguish_retry_attempts_from_item_outcomes(self, db_connection):
        """written/errors reflect logical ITEM outcomes, not raw
        write_result() call counts — a transient failure's retry
        attempts on the SAME item must not be miscounted as a separate
        item or a separate error. Selection is by item_id, never a
        global call counter (the bug the old version of this test had:
        "every 3rd call fails" conflated a retry attempt with the next
        item — see docs/status/known-issues.md, 2026-08-21)."""
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _SelectiveFailureResultWriter(
                *args, fail_until_attempt={"item-002": 1}, **kwargs
            )

        with patch('src.core.async_writer.ResultWriter', side_effect=_writer_factory):
            writer = AsyncWriter(queue, db_connection)
            for i in range(1, 6):
                await queue.put(_make_success_result(f"item-{i:03d}"))
            await queue.put(None)
            stats = await writer.consume()

        # item-002's one failed attempt is a retry, not a separate item —
        # all 5 items ultimately succeed, zero errors.
        assert stats["written"] == 5
        assert stats["errors"] == 0
        assert stats["aborted"] is False

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
    async def test_stats_select_failing_item_by_id_not_position(self, db_connection):
        """The item that fails is selected by item_id, not by its
        position in the queue or a global call counter — proves
        failure-injection targets the correct logical item regardless of
        processing order, and (per the fail-fast contract) that a
        permanent failure stops consumption before later items are
        reached."""
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _SelectiveFailureResultWriter(
                *args, fail_until_attempt={"item-003": None}, **kwargs
            )

        with patch('src.core.async_writer.ResultWriter', side_effect=_writer_factory):
            writer = AsyncWriter(queue, db_connection)
            await queue.put(_make_success_result("item-001"))
            await queue.put(_make_success_result("item-002"))
            await queue.put(_make_success_result("item-003"))
            await queue.put(_make_success_result("item-004"))
            await queue.put(None)
            stats = await writer.consume()

        assert stats["written"] == 2
        assert stats["errors"] == 1
        assert stats["aborted"] is True
        assert [r.item_id for r in writer.results_written] == ["item-001", "item-002"]
        # item-004 and the sentinel are never reached.
        assert queue.qsize() == 2


class TestAsyncWriterSentinel:
    """Test sentinel handling specifically."""

    @pytest.mark.asyncio
    async def test_sentinel_at_start_exits_immediately(self):
        """Verify writer exits cleanly when sentinel is first item on
        queue. Checks the specific fields that matter, not brittle
        whole-dict equality — the real stats dict also carries
        aborted/abort_info, which a strict `==` against a 2-key dict
        would break on every time a new field is added (see
        docs/status/known-issues.md, 2026-08-21). db_connection is
        deliberately not needed here: the sentinel is the first item, so
        no write ever happens — a bare MagicMock() for db_connection is
        appropriate (nothing touches it; ResultWriter.__init__ itself
        never accesses the connection, only write_result() does)."""
        queue: asyncio.Queue = asyncio.Queue()
        await queue.put(None)

        writer = AsyncWriter(queue, MagicMock())
        stats = await writer.consume()

        assert stats["written"] == 0
        assert stats["errors"] == 0
        assert stats["aborted"] is False
        assert stats["abort_info"] is None

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
    async def test_task_done_called_for_each_item_on_the_happy_path(self, db_connection):
        """On the happy path (no failures), task_done() is called for
        every consumed item including the sentinel — proven via
        queue.join() completing promptly, the public asyncio.Queue API
        for exactly this question (no private attribute reads)."""
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, db_connection)

        await queue.put(_make_success_result("item-001"))
        await queue.put(_make_success_result("item-002"))
        await queue.put(None)

        assert queue.qsize() == 3

        stats = await writer.consume()

        assert stats["written"] == 2
        assert queue.qsize() == 0
        # join() must complete promptly — every get() had a matching
        # task_done(), including the sentinel.
        await asyncio.wait_for(queue.join(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_task_done_not_called_for_the_item_that_triggers_abort(self, db_connection):
        """Documents the REAL, current task_done() semantics around a
        permanent failure — deliberately NOT changed here, per
        instruction: a queue-semantics change needs its own impact
        analysis presented first, not bundled into a test rewrite.

        consume()'s permanent-failure branch (`else: break` after
        `_write_result_with_retry` returns False) exits the loop WITHOUT
        calling task_done() for the item that triggered the abort —
        unlike every other path (success, or the sentinel), which always
        calls task_done(). Practical consequence: after an abort,
        task_done() has been called one fewer time than get() for the
        items actually dequeued, so a caller that later awaited
        queue.join() on this same queue would hang. Today's real caller
        (AsyncOrchestrator) never calls queue.join() after an abort (see
        execute()'s abort_event handling), so this is inert in
        production today — but is exactly the trap the next person
        adding a queue.join() call would fall into without this test
        documenting it explicitly. See docs/status/known-issues.md,
        2026-08-21."""
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _SelectiveFailureResultWriter(
                *args, fail_until_attempt={"item-001": None}, **kwargs
            )

        with patch('src.core.async_writer.ResultWriter', side_effect=_writer_factory):
            writer = AsyncWriter(queue, db_connection)
            await queue.put(_make_success_result("item-001"))
            await queue.put(None)
            stats = await writer.consume()

        assert stats["aborted"] is True
        # A join() issued now must NOT complete promptly — the aborting
        # item's task_done() was never called (the sentinel's get() was
        # never even reached, since consume() broke out of the loop
        # before getting to it — but the aborting item WAS dequeued via
        # get() and still owes a task_done() that never came).
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.join(), timeout=0.1)


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
