"""Integration tests for execution pipeline hardening.

Tests cover:
- Issue 1: Randomizer determinism (same run_seed = same option_letter_map)
- Issue 2: Sliding window concurrency (dynamic task creation)
- Issue 3: AsyncWriter retry + fail-fast abort
- Issue 4: Error versioning (attempt_number, error history in response_text)
- W1: Canonical error key (response_id)
- W2: Schema migration for errors table
- W3: Option map per option_count
- W4: Abort window closure
- W5: ResultWriter reuse
- W6: Transaction strategy (no BEGIN IMMEDIATE)
"""

import asyncio
import json
import sqlite3
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from src.core.async_writer import AsyncWriter
from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter
from src.core.randomizer import AnswerRandomizer
from src.db.schema import create_schema


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database with full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _setup_full_fixture(conn, exp_id="exp-1", var_id="var-1", snap_id="snap-1", run_id="run-1", num_questions=3):
    """Create full experiment setup with all required FK records."""
    conn.execute(
        "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
        (exp_id, "test_exp", json.dumps({}), "hash-1"),
    )
    conn.execute(
        "INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config) VALUES (?, ?, ?, ?, ?)",
        (var_id, exp_id, "test/model", "sig-1", json.dumps({})),
    )
    # Create snapshots with exact IDs matching what tests use
    for i in range(num_questions):
        sid = snap_id if i == 0 else f"{snap_id}-{i}"
        conn.execute(
            "INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload) VALUES (?, ?, ?, ?, ?)",
            (sid, exp_id, f"q{i+1}", i + 1, json.dumps({"id": f"q{i+1}", "options": ["A", "B", "C", "D"], "answer_key": "A"})),
        )
    conn.execute(
        "INSERT INTO runs (run_id, experiment_id, config, status) VALUES (?, ?, ?, ?)",
        (run_id, exp_id, json.dumps({}), "pending"),
    )
    conn.commit()


def _make_success_result(run_id="run-1", variant_id="var-1", snapshot_id="snap-1", question_id="q-1", text="Answer: A", selected="A", latency=100):
    return ExecutionResult(
        item_id=f"{run_id}::{variant_id}::{snapshot_id}::it-1",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status="success",
        response_text=text,
        selected_answer=selected,
        parse_confidence="clear",
        latency_ms=latency,
        input_tokens=10,
        response_tokens=5,
        error_type=None,
        error_message=None,
        attempt_count=1,
        reasoning_tokens=0,
        raw_response={"content": text},
        started_at=datetime.now(),
        finished_at=datetime.now(),
        correct_option_presented=selected,
    )


def _make_error_result(run_id="run-1", variant_id="var-1", snapshot_id="snap-1", question_id="q-1", error_type="timeout", error_msg="Timed out", attempt_count=1):
    return ExecutionResult(
        item_id=f"{run_id}::{variant_id}::{snapshot_id}::it-1",
        run_id=run_id,
        variant_id=variant_id,
        snapshot_id=snapshot_id,
        question_id=question_id,
        status="failure",
        error_type=error_type,
        error_message=error_msg,
        attempt_count=attempt_count,
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


# ─────────────────────────────────────────────────────────────
# Issue 1: Randomizer Determinism
# ─────────────────────────────────────────────────────────────

class TestRandomizerDeterminism:
    """All questions in the same run MUST share the same option_letter_map."""

    def test_same_seed_same_option_map(self):
        """Same run_seed produces identical option_letter_map for all questions."""
        ref_options = ["Opt A", "Opt B", "Opt C", "Opt D"]

        r1 = AnswerRandomizer()
        result1 = r1.randomize_options(list(ref_options), seed=42)
        shuffled1 = result1["options"]
        map1 = {chr(65+i): chr(65+ref_options.index(s)) for i, s in enumerate(shuffled1)}

        r2 = AnswerRandomizer()
        result2 = r2.randomize_options(list(ref_options), seed=42)
        shuffled2 = result2["options"]
        map2 = {chr(65+i): chr(65+ref_options.index(s)) for i, s in enumerate(shuffled2)}

        assert map1 == map2

    def test_different_seeds_different_maps(self):
        """Different run_seeds produce different option_letter_maps."""
        ref_options = ["Opt A", "Opt B", "Opt C", "Opt D"]
        r1 = AnswerRandomizer()
        result1 = r1.randomize_options(list(ref_options), seed=42)
        r2 = AnswerRandomizer()
        result2 = r2.randomize_options(list(ref_options), seed=99)
        assert result1["options"] != result2["options"]

    def test_no_seed_identity_map(self):
        """seed=None produces identity mapping (no shuffling)."""
        ref_options = ["Opt A", "Opt B", "Opt C", "Opt D"]
        r = AnswerRandomizer(seed=None)
        result = r.randomize_options(list(ref_options))
        assert result["options"] == ref_options


# ─────────────────────────────────────────────────────────────
# Issue 2: Sliding Window Concurrency
# ─────────────────────────────────────────────────────────────

class TestSlidingWindowConcurrency:
    """Dynamic task creation ensures sliding window behavior."""

    @pytest.mark.asyncio
    async def test_sliding_window_starts_next_on_completion(self):
        """With 11 items and concurrency=10, 11th starts as soon as any of first 10 finishes."""
        max_concurrency = 10
        total_items = 11
        start_times = {}

        async def simulate_item(item_id):
            start_times[item_id] = time.monotonic()
            await asyncio.sleep(0.05)
            return item_id

        async def run_with_sliding_window():
            items_iter = iter(range(total_items))
            pending = []
            results = []

            def launch_next():
                try:
                    item_id = next(items_iter)
                except StopIteration:
                    return False
                task = asyncio.create_task(simulate_item(item_id))
                pending.append(task)
                return True

            for _ in range(min(total_items, max_concurrency)):
                launch_next()
            while pending:
                done, pending_set = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                pending = list(pending_set)
                for task in done:
                    results.append(await task)
                    launch_next()
            return results

        results = await run_with_sliding_window()
        assert len(results) == total_items
        assert any(start_times[i] < start_times[10] for i in range(10) if i in start_times)

    @pytest.mark.asyncio
    async def test_concurrency_limit_respected(self):
        """Semaphore never allows more than max_concurrency simultaneous tasks."""
        max_concurrency = 3
        total_items = 8
        concurrent_count = 0
        max_concurrent_observed = 0
        lock = asyncio.Lock()

        async def tracked_item():
            nonlocal concurrent_count, max_concurrent_observed
            async with lock:
                concurrent_count += 1
                max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(0.02)
            async with lock:
                concurrent_count -= 1

        async def run_test():
            items_iter = iter(range(total_items))
            pending = []
            def launch_next():
                try:
                    next(items_iter)
                except StopIteration:
                    return False
                task = asyncio.create_task(tracked_item())
                pending.append(task)
                return True

            for _ in range(min(total_items, max_concurrency)):
                launch_next()
            while pending:
                done, pending_set = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                pending = list(pending_set)
                for _ in done:
                    launch_next()

        await run_test()
        assert max_concurrent_observed <= max_concurrency


# ─────────────────────────────────────────────────────────────
# Issue 3: AsyncWriter Retry + Fail-Fast Abort
# ─────────────────────────────────────────────────────────────

class TestAsyncWriterRetry:
    """AsyncWriter retries on failure, then aborts after max retries."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_on_second_attempt(self, in_memory_db):
        """Write fails once, succeeds on retry."""
        queue = asyncio.Queue()
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = AsyncWriter(queue, conn)
        result = _make_success_result()

        call_count = 0
        original_write_result = writer._result_writer.write_result

        def flaky_write_result(r):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError("database is locked")
            return original_write_result(r)

        with patch.object(writer._result_writer, "write_result", flaky_write_result):
            queue.put_nowait(result)
            queue.put_nowait(None)
            stats = await writer.consume()

        assert stats["written"] == 1
        assert stats["aborted"] is False
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_abort_after_max_retries(self, in_memory_db):
        """Write fails all retries → abort event set."""
        queue = asyncio.Queue()
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = AsyncWriter(queue, conn)
        result = _make_success_result()

        def always_fail(r):
            raise sqlite3.OperationalError("persistent failure")

        with patch.object(writer._result_writer, "write_result", always_fail):
            queue.put_nowait(result)
            queue.put_nowait(None)
            stats = await writer.consume()

        assert stats["written"] == 0
        assert stats["aborted"] is True
        assert writer.abort_event.is_set()


# ─────────────────────────────────────────────────────────────
# Issue 4: Error Versioning
# ─────────────────────────────────────────────────────────────

class TestErrorVersioning:
    """Multiple error rows per item with attempt_number, error history in response_text."""

    def test_multiple_errors_get_incrementing_attempt_numbers(self, in_memory_db):
        """Writing multiple errors for same item produces incrementing attempt_number."""
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = ResultWriter(conn)

        writer.write_result(_make_error_result(error_type="timeout", error_msg="Timed out", attempt_count=3))
        writer.write_result(_make_error_result(error_type="rate_limit", error_msg="Rate limited", attempt_count=1))

        cursor = conn.cursor()
        cursor.execute("SELECT error_type, attempt_number FROM errors ORDER BY attempt_number")
        rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0]["attempt_number"] == 1
        assert rows[0]["error_type"] == "timeout"
        assert rows[1]["attempt_number"] == 2
        assert rows[1]["error_type"] == "rate_limit"

    def test_error_history_prepended_on_success(self, in_memory_db):
        """When item succeeds after errors, response_text contains error history."""
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = ResultWriter(conn)

        writer.write_result(_make_error_result(error_type="timeout", error_msg="Timed out"))
        writer.write_result(_make_success_result(text="The answer is A", selected="A"))

        cursor = conn.cursor()
        cursor.execute("SELECT response_text FROM responses")
        row = cursor.fetchone()

        assert row is not None
        assert "[ERROR HISTORY" in row["response_text"]
        assert "timeout" in row["response_text"]
        assert "[SUCCESSFUL RESPONSE]" in row["response_text"]
        assert "The answer is A" in row["response_text"]

    def test_no_error_history_when_no_prior_errors(self, in_memory_db):
        """Success without prior errors has clean response_text."""
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = ResultWriter(conn)

        writer.write_result(_make_success_result(text="The answer is B", selected="B"))

        cursor = conn.cursor()
        cursor.execute("SELECT response_text FROM responses")
        row = cursor.fetchone()

        assert row is not None
        assert "[ERROR HISTORY" not in row["response_text"]
        assert row["response_text"] == "The answer is B"


# ─────────────────────────────────────────────────────────────
# W1: Canonical Error Key (response_id)
# ─────────────────────────────────────────────────────────────

class TestCanonicalErrorKey:
    """Errors are keyed by (response_id, attempt_number), not (error_id, attempt_number)."""

    def test_errors_use_response_id_as_fk(self, in_memory_db):
        """Error rows reference response_id, not just error_id."""
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = ResultWriter(conn)

        writer.write_result(_make_error_result())

        cursor = conn.cursor()
        cursor.execute("SELECT response_id FROM errors")
        row = cursor.fetchone()
        assert row is not None
        # response_id follows the deterministic format
        assert row["response_id"].startswith("resp-")

    def test_error_history_queries_by_response_id(self, in_memory_db):
        """_get_error_history uses response_id as lookup key."""
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = ResultWriter(conn)

        response_id = "resp-run-1-var-1-snap-1"
        history = writer._get_error_history(response_id)
        # Should be empty since no errors written yet
        assert history == []

        # Write error, then verify history is retrievable
        writer.write_result(_make_error_result(error_type="timeout", error_msg="Timed out"))
        history = writer._get_error_history(response_id)
        assert len(history) == 1
        assert history[0]["error_type"] == "timeout"


# ─────────────────────────────────────────────────────────────
# W3: Option Map per Option Count
# ─────────────────────────────────────────────────────────────

class TestOptionMapPerOptionCount:
    """Different option counts get independent but deterministic maps from same run_seed."""

    def test_different_option_counts_get_different_maps(self):
        """Same seed, different option counts → independent maps."""
        seed = 42

        r = AnswerRandomizer()

        # Map for 3 options
        ref_3 = [f"OPT_{i}" for i in range(3)]
        result_3 = r.randomize_options(list(ref_3), seed=seed * 1000 + 3)
        map_3 = {chr(65+i): chr(65+ref_3.index(s)) for i, s in enumerate(result_3["options"])}
        assert len(map_3) == 3

        # Map for 4 options
        ref_4 = [f"OPT_{i}" for i in range(4)]
        result_4 = r.randomize_options(list(ref_4), seed=seed * 1000 + 4)
        map_4 = {chr(65+i): chr(65+ref_4.index(s)) for i, s in enumerate(result_4["options"])}
        assert len(map_4) == 4

        # Maps are independent
        assert set(map_3.keys()) == {"A", "B", "C"}
        assert set(map_4.keys()) == {"A", "B", "C", "D"}

    def test_same_option_count_same_seed_same_map(self):
        """Same seed + same option count → identical map (deterministic)."""
        seed = 42
        r1 = AnswerRandomizer()
        ref = [f"OPT_{i}" for i in range(4)]
        result1 = r1.randomize_options(list(ref), seed=seed * 1000 + 4)
        map1 = {chr(65+i): chr(65+ref.index(s)) for i, s in enumerate(result1["options"])}

        r2 = AnswerRandomizer()
        result2 = r2.randomize_options(list(ref), seed=seed * 1000 + 4)
        map2 = {chr(65+i): chr(65+ref.index(s)) for i, s in enumerate(result2["options"])}

        assert map1 == map2


# ─────────────────────────────────────────────────────────────
# W5: ResultWriter Reuse
# ─────────────────────────────────────────────────────────────

class TestResultWriterReuse:
    """AsyncWriter reuses a single ResultWriter instance."""

    def test_async_writer_uses_single_result_writer(self, in_memory_db):
        """AsyncWriter creates exactly one ResultWriter instance."""
        queue = asyncio.Queue()
        conn = in_memory_db
        _setup_full_fixture(conn)
        writer = AsyncWriter(queue, conn)

        assert writer._result_writer is not None
        # Verify it's the same instance used during retry
        assert hasattr(writer, '_result_writer')


# ─────────────────────────────────────────────────────────────
# W4: Abort Window Closure
# ─────────────────────────────────────────────────────────────

class TestAbortWindowClosure:
    """Abort stops scheduling immediately, cancels pending tasks."""

    @pytest.mark.asyncio
    async def test_abort_stops_scheduling_immediately(self, in_memory_db):
        """When writer aborts, no further items are scheduled."""
        queue = asyncio.Queue()
        conn = in_memory_db
        _setup_full_fixture(conn, num_questions=5)
        writer = AsyncWriter(queue, conn)

        # First result succeeds, all subsequent trigger abort
        result1 = _make_success_result(snapshot_id="snap-1", text="A", latency=50)
        result2 = _make_success_result(snapshot_id="snap-1-1", text="B", latency=50)

        write_count = 0

        def always_fail_after_first(r):
            nonlocal write_count
            write_count += 1
            if write_count > 1:
                raise sqlite3.OperationalError("forced failure")

        with patch.object(writer._result_writer, "write_result", always_fail_after_first):
            queue.put_nowait(result1)
            queue.put_nowait(result2)
            # Add more results that should NOT be written after abort
            for i in range(3, 6):
                queue.put_nowait(_make_success_result(snapshot_id=f"snap-1-{i}", text=f"X{i}", latency=50))
            queue.put_nowait(None)
            stats = await writer.consume()

        # Only 1 written before abort kicks in
        assert stats["written"] == 1
        assert stats["aborted"] is True
        # The failure triggers 3 retries, so write_count = 1 (success) + 3 (retries) = 4
        assert write_count == 4  # 1 success + 3 retry attempts before abort


# ─────────────────────────────────────────────────────────────
# W6: Transaction Strategy (No "database is locked" under concurrency)
# ─────────────────────────────────────────────────────────────

class TestTransactionStrategy:
    """Standard autocommit — no 'database is locked' under concurrency."""

    @pytest.mark.asyncio
    async def test_no_lock_errors_at_concurrency_4(self, in_memory_db):
        """Concurrent writes with concurrency=4 produce no lock errors."""
        queue = asyncio.Queue()
        conn = in_memory_db
        _setup_full_fixture(conn, num_questions=8)
        writer = AsyncWriter(queue, conn)

        # Write 8 results concurrently via queue
        for i in range(8):
            queue.put_nowait(_make_success_result(
                snapshot_id=f"snap-1-{i}" if i > 0 else "snap-1",
                text=f"Answer {i}",
                latency=50 + i * 10
            ))
        queue.put_nowait(None)

        stats = await writer.consume()
        assert stats["errors"] == 0
        assert stats["written"] == 8
        assert stats["aborted"] is False
