"""ADR-004 / ASY-01 regression suite: a received ExecutionResult must
never disappear without traceability, even when it cannot be persisted
as a normal response — and a Run must never be finalized as 'completed'
when that happened.

Covers the required test matrix from the ASY-01 implementation checklist:
  A. Original reproduction, now fixed end-to-end (AsyncWriter -> drain ->
     RunFinalizer).
  B. Zero responses persisted -> RunFinalizer produces 'failed'.
  C. Partial case (one success, one write-failure, one abandoned) ->
     RunFinalizer produces 'partial_failed'.
  D. The best-effort errors-row write itself fails -> no unhandled
     exception, CRITICAL event, controlled termination.
  E. Sentinel drained -> no errors row, no fictitious item failure.
  F. Re-execution eligibility -> an item with only an errors row is still
     "not yet executed" per Planner._get_executed_items (unmodified).
  G. Fail-fast regression -> the abort path never resumes normal
     consumption or becomes per-item resilience.
  H. AsyncOrchestrator's except-Exception cleanup path (a second,
     narrower instance of the same ASY-01 risk, found by the Essence
     Guardian review of the first checkpoint and fixed in the same
     ADR-004 spirit) also drains abandoned items — never for a
     sentinel, never twice for the same item, never breaking the
     original exception's propagation.

No production code is touched by this file — it is verification only.
Isolation: real in-memory SQLite via the real create_schema(). No real
.env/production DB touched.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.async_orchestrator import AsyncOrchestrator
from src.core.async_writer import AsyncWriter
from src.core.execution_plan import ExecutionPlan, PlanRun, Prompts, RetryPolicy
from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter
from src.core.run_finalizer import RunFinalizer
from src.core.planner import Planner
from src.db.schema import create_schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(item_id: str, run_id: str, snapshot_id: str, variant_id: str = "var-001") -> ExecutionResult:
    """A real, fully-computed success ExecutionResult — exactly what a
    concurrent API call finishing mid-backoff would produce."""
    return ExecutionResult(
        item_id=item_id,
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=f"Q-{item_id}",
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
        cost=0.0002,
        # A real success row must have raw_response set — RunFinalizer's
        # success_count query is WHERE raw_response IS NOT NULL (this is
        # what makes a genuinely-persisted item countable as a success;
        # omitting it here would make even a correctly-written row
        # invisible to RunFinalizer, which is a test-fixture bug, not a
        # production one — see PLN-03 in docs/status/auditoria-profunda-922603c.md
        # for why this exact column is the single source of truth).
        raw_response={"id": f"chatcmpl-{item_id}", "choices": [{"message": {"content": "The answer is (B)."}}]},
        started_at=datetime.now(),
        finished_at=datetime.now(),
    )


def _seed_db(conn: sqlite3.Connection, run_id: str, snapshot_ids: list[str], variant_id: str = "var-001") -> None:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
        ("exp-asy01", "ASY-01 test", "{}", "hash-asy01"),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
        (variant_id, "exp-asy01", "openai/gpt-4", f"sig-{variant_id}", "{}"),
    )
    cursor.execute(
        "INSERT OR IGNORE INTO runs (run_id, experiment_id, config, status) VALUES (?, ?, ?, ?)",
        (run_id, "exp-asy01", "{}", "pending"),
    )
    payload = json.dumps({"stem": "s", "options": ["A", "B"], "answer_key": "B"})
    for i, snapshot_id in enumerate(snapshot_ids, start=1):
        cursor.execute(
            "INSERT OR IGNORE INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, "exp-asy01", f"Q{i}", i, payload),
        )
    conn.commit()


class _PermanentlyFailingResultWriter(ResultWriter):
    """Every write_result() call for the named item_id(s) raises,
    permanently — exhausts AsyncWriter's retries. write_result() for
    every other item_id delegates to the real write. _write_error()
    (the best-effort audit trail path) is intentionally left untouched
    by default so it can succeed independently of write_result()'s own
    failure — that independence is exactly the point of ADR-004."""

    def __init__(self, *args, fail_item_ids: set[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._fail_item_ids = fail_item_ids or set()

    def write_result(self, result):
        if result.item_id in self._fail_item_ids:
            raise sqlite3.OperationalError(f"simulated permanent DB failure for {result.item_id}")
        return super().write_result(result)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    create_schema(c)
    yield c
    try:
        c.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# A. Original reproduction, now fixed end-to-end
# ---------------------------------------------------------------------------

class TestOriginalReproductionFixed:
    @pytest.mark.asyncio
    async def test_lost_item_now_traceable_and_run_not_completed(self, conn):
        """item-1 (real success) fails to persist permanently; item-2
        (real success) arrives mid-backoff. After abort + drain, both
        must be traceable in `errors`, and the run must never finalize
        as 'completed'."""
        run_id = "run-asy01-a"
        _seed_db(conn, run_id, ["snap-1", "snap-2"])

        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            await asyncio.sleep(0)  # let consume() pick up item-1 before item-2 arrives
            writer_task = asyncio.create_task(writer.consume())
            await asyncio.sleep(0.6)  # mid-backoff (0.5s, 1.0s, 1.5s schedule)
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            stats = await writer_task

        assert stats["aborted"] is True
        assert queue.qsize() >= 1  # item-2 (and possibly the never-sent sentinel) still queued

        abandoned = writer.drain_abandoned()
        assert abandoned == 1
        assert queue.qsize() == 0

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 0, "no silent partial persistence — neither item was a real response"

        cursor.execute("SELECT snapshot_id, error_type, error_message FROM errors WHERE run_id = ? ORDER BY snapshot_id", (run_id,))
        rows = cursor.fetchall()
        assert len(rows) == 2, "both the write-failed item and the abandoned item must be traceable"
        by_snapshot = {r["snapshot_id"]: r for r in rows}
        assert by_snapshot["snap-1"]["error_type"] == "write_failure"
        assert "item-1" in by_snapshot["snap-1"]["error_message"]
        assert "persistence" in by_snapshot["snap-1"]["error_message"].lower()
        assert by_snapshot["snap-2"]["error_type"] == "abandoned_after_writer_abort"
        assert "item-2" in by_snapshot["snap-2"]["error_message"]

        result = RunFinalizer(conn).finalize_run(run_id)
        assert result["status"] != "completed", (
            "the exact original bug: a run with lost items must never report completed"
        )
        cursor.execute("SELECT status FROM runs WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()["status"] != "completed"


# ---------------------------------------------------------------------------
# B. Zero responses persisted
# ---------------------------------------------------------------------------

class TestZeroResponsesCase:
    @pytest.mark.asyncio
    async def test_zero_responses_produces_failed_not_completed(self, conn):
        run_id = "run-asy01-b"
        _seed_db(conn, run_id, ["snap-1", "snap-2"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            stats = await writer.consume()

        assert stats["aborted"] is True
        writer.drain_abandoned()

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 2, "both received-but-unpersisted items must have an errors row"

        result = RunFinalizer(conn).finalize_run(run_id)
        assert result["status"] == "failed"
        assert result["response_count"] == 0


# ---------------------------------------------------------------------------
# C. Partial case
# ---------------------------------------------------------------------------

class TestPartialCase:
    @pytest.mark.asyncio
    async def test_partial_success_produces_partial_failed(self, conn):
        run_id = "run-asy01-c"
        _seed_db(conn, run_id, ["snap-1", "snap-2", "snap-3"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-2"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))  # persists successfully
            await queue.put(_make_result("item-2", run_id, "snap-2"))  # permanent write failure
            await queue.put(_make_result("item-3", run_id, "snap-3"))  # abandoned in queue
            stats = await writer.consume()

        assert stats["written"] == 1
        assert stats["aborted"] is True
        abandoned = writer.drain_abandoned()
        assert abandoned == 1

        cursor = conn.cursor()
        cursor.execute("SELECT snapshot_id FROM responses WHERE run_id = ?", (run_id,))
        assert {r["snapshot_id"] for r in cursor.fetchall()} == {"snap-1"}

        cursor.execute("SELECT snapshot_id, error_type FROM errors WHERE run_id = ?", (run_id,))
        errors_by_snapshot = {r["snapshot_id"]: r["error_type"] for r in cursor.fetchall()}
        assert errors_by_snapshot == {
            "snap-2": "write_failure",
            "snap-3": "abandoned_after_writer_abort",
        }

        result = RunFinalizer(conn).finalize_run(run_id)
        assert result["status"] == "partial_failed"
        assert result["response_count"] == 1


# ---------------------------------------------------------------------------
# D. The best-effort errors-row write itself fails
# ---------------------------------------------------------------------------

class TestTraceWriteItselfFails:
    @pytest.mark.asyncio
    async def test_double_failure_never_raises_and_emits_critical_event(self, conn, caplog):
        """If even the best-effort errors-row write fails (total DB
        unavailability), AsyncWriter must not raise, and a CRITICAL
        WRITE_FAILURE_TRACE_FAILED event must be emitted as the
        explicitly-accepted final fallback."""
        import logging
        from src.utils.logging_config import get_logger

        run_id = "run-asy01-d"
        _seed_db(conn, run_id, ["snap-1"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        logger = get_logger("core.async_writer")
        logger.addHandler(caplog.handler)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory), \
             patch.object(ResultWriter, "_write_error", side_effect=sqlite3.OperationalError("db is fully gone")):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            with caplog.at_level(logging.CRITICAL, logger="benchmark_llm"):
                stats = await writer.consume()  # must return normally, never raise

        assert stats["aborted"] is True
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 0, "the trace write itself failed — no row could be created"

        # emit_event() logs to both a human-readable and a JSONL channel
        # per call, so this asserts existence (any), not an exact count —
        # matching the pattern already used elsewhere (e.g.
        # test_export_service.py's caplog assertions).
        critical_records = [r for r in caplog.records if "WRITE_FAILURE_TRACE_FAILED" in r.message]
        assert len(critical_records) >= 1
        assert all(r.levelno == logging.CRITICAL for r in critical_records)
        assert any("item-1" in r.message for r in critical_records)

        # The process still terminates in a controlled way: finalize_run
        # doesn't raise either, and reports the honest (if minimal) state.
        result = RunFinalizer(conn).finalize_run(run_id)
        assert result["status"] == "completed"  # nothing at all was recorded — see note below
        logger.removeHandler(caplog.handler)


# Note on TestTraceWriteItselfFails: when even the errors-row fallback
# fails, RunFinalizer legitimately cannot distinguish "nothing happened"
# from "something happened and even its trace was lost" — this is the
# explicitly-accepted, documented limit of ADR-004 Decision 2 ("this is a
# real limit, not a silent gap"): the CRITICAL log line is the only
# remaining record in that double-failure scenario, which is why the test
# above asserts on the log event, not on run status, as the actual proof
# of correct behavior for this case.


# ---------------------------------------------------------------------------
# E. Sentinel drained
# ---------------------------------------------------------------------------

class TestSentinelDuringDrain:
    @pytest.mark.asyncio
    async def test_sentinel_in_queue_creates_no_errors_row(self, conn):
        """A sentinel left in the queue after an abort (because
        AsyncOrchestrator always puts one, even post-abort) must be
        drained and discarded, never treated as a lost item."""
        run_id = "run-asy01-e"
        _seed_db(conn, run_id, ["snap-1"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            stats = await writer.consume()

        assert stats["aborted"] is True
        # Simulate AsyncOrchestrator's unconditional `await queue.put(None)`
        # happening after the writer already aborted.
        await queue.put(None)

        abandoned = writer.drain_abandoned()
        assert abandoned == 0, "the sentinel must not be counted as an abandoned item"

        cursor = conn.cursor()
        cursor.execute("SELECT error_type FROM errors WHERE run_id = ?", (run_id,))
        error_types = {r["error_type"] for r in cursor.fetchall()}
        assert error_types == {"write_failure"}, "only item-1's real failure — no phantom sentinel error"
        assert queue.qsize() == 0


# ---------------------------------------------------------------------------
# F. Re-execution eligibility
# ---------------------------------------------------------------------------

class TestReExecutionEligibility:
    @pytest.mark.asyncio
    async def test_item_with_only_errors_row_stays_eligible_for_planner(self, conn):
        """Planner._get_executed_items (UNMODIFIED) already excludes an
        item only when responses.raw_response IS NOT NULL — an item that
        only has an errors row (ADR-004's trace) must still be
        considered 'not yet executed'. No Planner code is touched by
        this test or by ASY-01."""
        run_id = "run-asy01-f"
        _seed_db(conn, run_id, ["snap-1", "snap-2"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            stats = await writer.consume()

        writer.drain_abandoned()

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 2

        executed = Planner(conn)._get_executed_items(run_id)
        assert executed == set(), (
            "neither item has a responses.raw_response row — both remain "
            "eligible for re-execution via the existing, unmodified mechanism"
        )


# ---------------------------------------------------------------------------
# G. Fail-fast regression
# ---------------------------------------------------------------------------

class TestFailFastNotWeakened:
    @pytest.mark.asyncio
    async def test_consume_still_stops_immediately_on_permanent_failure(self, conn):
        """The abort path must still stop consuming the moment
        persistence is confirmed broken — items queued after the
        failing one are never even dequeued by consume() itself (they
        are only later picked up by the separate, explicit
        drain_abandoned() call, never by consume() resuming)."""
        run_id = "run-asy01-g"
        _seed_db(conn, run_id, ["snap-1", "snap-2", "snap-3"])
        queue: asyncio.Queue = asyncio.Queue()

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory):
            writer = AsyncWriter(queue, conn)
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            await queue.put(_make_result("item-3", run_id, "snap-3"))
            await queue.put(None)
            stats = await writer.consume()

        # Only item-1 was ever dequeued by consume(); item-2/item-3/sentinel
        # remain — consume() itself never became per-item resilient.
        assert stats["written"] == 0
        assert queue.qsize() == 3

        # drain_abandoned() is a SEPARATE, explicit, one-time action — not
        # consume() resuming. It must record exactly the leftover
        # ExecutionResults, never attempt to process the sentinel as work,
        # and never call write_result() (the normal path) again.
        with patch.object(ResultWriter, "write_result") as mock_write_result:
            abandoned = writer.drain_abandoned()
            mock_write_result.assert_not_called()

        assert abandoned == 2
        assert queue.qsize() == 0

    @pytest.mark.asyncio
    async def test_drain_abandoned_is_noop_on_clean_shutdown(self, conn):
        """On a clean, non-aborted shutdown, drain_abandoned() finds
        nothing (the queue is already empty) — confirms it's not a
        second, hidden write path exercised on every run."""
        run_id = "run-asy01-g2"
        _seed_db(conn, run_id, ["snap-1"])
        queue: asyncio.Queue = asyncio.Queue()
        writer = AsyncWriter(queue, conn)

        await queue.put(_make_result("item-1", run_id, "snap-1"))
        await queue.put(None)
        stats = await writer.consume()

        assert stats["aborted"] is False
        assert writer.drain_abandoned() == 0


# ---------------------------------------------------------------------------
# H. AsyncOrchestrator's except-Exception cleanup path
# ---------------------------------------------------------------------------

def _make_minimal_plan(run_id: str) -> ExecutionPlan:
    """A plan with no items — sufficient here because these tests bypass
    _execute_plan_with_semaphore entirely (patched), so the real item
    list is never consulted."""
    run = PlanRun(
        run_id=run_id,
        randomization_seed_effective=None,
        prompts_effective=Prompts(system=None, user="Answer: {question}"),
        retry_policy=RetryPolicy(max_attempts=1),
        variants=[],
        items=[],
    )
    return ExecutionPlan(
        plan_id="plan-except-test",
        created_at=datetime.now(),
        experiment_id="exp-asy01",
        runs=[run],
    )


def _make_orchestrator(conn) -> AsyncOrchestrator:
    api_client = MagicMock()
    api_client.close = AsyncMock()
    return AsyncOrchestrator(
        api_client=api_client,
        db_connection=conn,
        randomizer=MagicMock(),
        parser=MagicMock(),
    )


class TestExceptExceptionPathDrainsAbandoned:
    """AsyncOrchestrator._execute_async's pre-existing `except Exception:`
    cleanup branch — unmodified in shape, now also drains any real
    ExecutionResult left in the queue when the writer had independently
    aborted, mirroring the normal-completion path's own drain call.
    `_execute_plan_with_semaphore` is patched directly (not the engine)
    because the existing test_async_orchestrator.py fixtures that mock
    ExecutionEngine.execute_async predate the semaphore-based per-item
    scheduler and no longer reflect what the real code calls — this file
    does not inherit that pre-existing, out-of-scope test debt."""

    @pytest.mark.asyncio
    async def test_unexpected_exception_with_item_already_queued(self, conn):
        """1. An unexpected exception occurs in orchestration scheduling
        itself, AFTER the writer has already permanently failed to
        persist item-1 (so it aborted) and item-2 has already been
        queued. The except-path fix must still record item-2 as
        traceable, and the run must never finalize as 'completed'."""
        run_id = "run-except-h1"
        _seed_db(conn, run_id, ["snap-1", "snap-2"])
        plan = _make_minimal_plan(run_id)

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        async def _fake_execute_plan_with_semaphore(self_, engine, plan_, queue, semaphore, abort_event, operation_id=None):
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            # Give the real writer time to exhaust its 3 retries (0.5s+1.0s backoff)
            # and abort before the "unexpected" exception below fires.
            for _ in range(500):
                if abort_event.is_set():
                    break
                await asyncio.sleep(0.01)
            assert abort_event.is_set(), "writer must have aborted before this test's exception fires"
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            raise RuntimeError("simulated unexpected orchestration bug")

        orchestrator = _make_orchestrator(conn)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory), \
             patch.object(
                 AsyncOrchestrator, "_execute_plan_with_semaphore",
                 _fake_execute_plan_with_semaphore,
             ):
            with pytest.raises(RuntimeError, match="simulated unexpected orchestration bug"):
                await orchestrator._execute_async(plan)

        cursor = conn.cursor()
        cursor.execute("SELECT snapshot_id, error_type FROM errors WHERE run_id = ?", (run_id,))
        errors_by_snapshot = {r["snapshot_id"]: r["error_type"] for r in cursor.fetchall()}
        assert errors_by_snapshot == {
            "snap-1": "write_failure",
            "snap-2": "abandoned_after_writer_abort",
        }

        # RunFinalizer is never called on the exception path (unchanged,
        # out of this fix's scope) — but confirm the run's status, if
        # anyone finalizes it later from this DB state, could never
        # legitimately be 'completed' given these error rows.
        result = RunFinalizer(conn).finalize_run(run_id)
        assert result["status"] != "completed"

    @pytest.mark.asyncio
    async def test_unexpected_exception_with_empty_queue(self, conn):
        """2. An unexpected exception occurs but the writer never
        aborted and nothing was left in the queue — no artificial error
        row is created, and cleanup/finalization is not broken."""
        run_id = "run-except-h2"
        _seed_db(conn, run_id, ["snap-1"])
        plan = _make_minimal_plan(run_id)

        async def _fake_execute_plan_with_semaphore(self_, engine, plan_, queue, semaphore, abort_event, operation_id=None):
            raise RuntimeError("simulated unexpected orchestration bug, no items ever queued")

        orchestrator = _make_orchestrator(conn)

        with patch.object(
            AsyncOrchestrator, "_execute_plan_with_semaphore",
            _fake_execute_plan_with_semaphore,
        ):
            with pytest.raises(RuntimeError, match="no items ever queued"):
                await orchestrator._execute_async(plan)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 0, "nothing was received — no artificial error should be recorded"
        cursor.execute("SELECT COUNT(*) FROM responses WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 0

    @pytest.mark.asyncio
    async def test_no_double_recording_across_paths(self, conn):
        """3. Safety against a duplicated call: draining is only ever
        reachable from ONE of the two paths per invocation (normal
        completion XOR the except branch — they are mutually exclusive
        by construction, since the except branch only runs when the try
        block itself raised). This test proves that even calling
        drain_abandoned() a second time on the same writer afterward
        (simulating a hypothetical double-invocation bug) does not
        record the same item twice, since the queue is already empty
        after the first drain."""
        run_id = "run-except-h3"
        _seed_db(conn, run_id, ["snap-1", "snap-2"])
        plan = _make_minimal_plan(run_id)

        def _writer_factory(*args, **kwargs):
            return _PermanentlyFailingResultWriter(*args, fail_item_ids={"item-1"}, **kwargs)

        captured_writer: dict = {}
        real_async_writer_cls = AsyncWriter

        def _capturing_async_writer(*args, **kwargs):
            w = real_async_writer_cls(*args, **kwargs)
            captured_writer["writer"] = w
            return w

        async def _fake_execute_plan_with_semaphore(self_, engine, plan_, queue, semaphore, abort_event, operation_id=None):
            await queue.put(_make_result("item-1", run_id, "snap-1"))
            for _ in range(500):
                if abort_event.is_set():
                    break
                await asyncio.sleep(0.01)
            await queue.put(_make_result("item-2", run_id, "snap-2"))
            raise RuntimeError("simulated bug")

        orchestrator = _make_orchestrator(conn)

        with patch("src.core.async_writer.ResultWriter", side_effect=_writer_factory), \
             patch("src.core.async_writer.AsyncWriter", side_effect=_capturing_async_writer), \
             patch.object(
                 AsyncOrchestrator, "_execute_plan_with_semaphore",
                 _fake_execute_plan_with_semaphore,
             ):
            with pytest.raises(RuntimeError, match="simulated bug"):
                await orchestrator._execute_async(plan)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 2

        # A second, redundant drain call on the SAME writer instance must
        # be a safe no-op — the queue is already empty, so no duplicate
        # errors row (which would violate the (response_id, attempt_number)
        # PRIMARY KEY and raise, not silently duplicate — this test proves
        # it doesn't even attempt a second write).
        second_pass_count = captured_writer["writer"].drain_abandoned()
        assert second_pass_count == 0
        cursor.execute("SELECT COUNT(*) FROM errors WHERE run_id = ?", (run_id,))
        assert cursor.fetchone()[0] == 2, "no duplicate error rows from a redundant drain call"
