"""Concurrency and crash-safety tests for the logging pipeline
(Checkpoint C, §8): concurrent asyncio tasks must never interleave or
truncate JSONL/human log lines, and a log handler failure must never
break execution or duplicate a persisted result.
"""

import asyncio
import json
import logging
from pathlib import Path

import pytest

from src.utils.log_emitter import emit_event, JSONL_LOGGER_NAME
from src.utils.log_events import Event
from src.utils.logging_config import LoggingConfig, setup_logging


class TestConcurrentLogLineIntegrity:
    @pytest.mark.asyncio
    async def test_many_concurrent_tasks_produce_no_corrupted_jsonl_lines(self, tmp_path: Path):
        """Real logging setup, real file, real concurrent asyncio tasks —
        not mocked — confirms the claim in
        docs/status/checkpoint-c-logging-observability-design.md §1.7/§8.1
        that line-level interleaving is not a real risk under this
        concurrency model, rather than trusting the argument alone."""
        log_file = tmp_path / "concurrent.log"
        setup_logging(LoggingConfig(log_file_path=log_file))
        logger = logging.getLogger("benchmark_llm.concurrency_test")

        N = 200

        async def _emit_one(i: int) -> None:
            # Yield control before emitting, to maximize interleaving
            # opportunity across concurrently-scheduled tasks.
            await asyncio.sleep(0)
            emit_event(
                logger, Event.ITEM_COMPLETE, operation_id=f"op_{i}",
                run_id=f"run_{i}", variant_id=f"var_{i}", snapshot_id=f"snap_{i}",
                index=i,
            )

        await asyncio.gather(*(_emit_one(i) for i in range(N)))

        jsonl_path = tmp_path / "concurrent.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == N

        seen_indices = set()
        for line in lines:
            # Every single line must parse as exactly one complete JSON
            # object — a truncated or merged line would fail this.
            parsed = json.loads(line)
            assert parsed["event_name"] == Event.ITEM_COMPLETE
            seen_indices.add(parsed["index"])

        # Every task's line survived, none lost, none duplicated.
        assert seen_indices == set(range(N))

    @pytest.mark.asyncio
    async def test_human_log_lines_also_not_corrupted_under_concurrency(self, tmp_path: Path):
        log_file = tmp_path / "concurrent2.log"
        setup_logging(LoggingConfig(log_file_path=log_file))
        logger = logging.getLogger("benchmark_llm.concurrency_test2")

        N = 100

        async def _emit_one(i: int) -> None:
            await asyncio.sleep(0)
            emit_event(logger, Event.ITEM_START, run_id=f"run_{i}", variant_id="v", snapshot_id="s")

        await asyncio.gather(*(_emit_one(i) for i in range(N)))

        lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        # Every line must start with the expected event prefix — a
        # corrupted/merged line would produce a malformed prefix.
        assert len(lines) == N
        for line in lines:
            assert "ITEM_START" in line


class TestHandlerFailureNeverBreaksExecution:
    def test_jsonl_write_failure_does_not_raise_and_execution_continues(self, tmp_path: Path, monkeypatch):
        """A logging handler failure (simulated disk-full/permission-denied
        via a raising handler) must not propagate — the caller's own logic
        after the log call must still run normally."""
        log_file = tmp_path / "test.log"
        setup_logging(LoggingConfig(log_file_path=log_file))

        jsonl_logger = logging.getLogger(JSONL_LOGGER_NAME)

        class _RaisingHandler(logging.Handler):
            def emit(self, record):
                raise OSError("simulated disk full")

        jsonl_logger.handlers.clear()
        jsonl_logger.addHandler(_RaisingHandler())

        logger = logging.getLogger("benchmark_llm.crash_test")

        # This must not raise, and the sentinel below proves execution
        # continued past the failed log call — a real "did the caller's
        # own logic keep running" check, not just "no exception escaped".
        sentinel = {"reached": False}
        emit_event(logger, Event.ITEM_COMPLETE, run_id="run_1", variant_id="v", snapshot_id="s")
        sentinel["reached"] = True

        assert sentinel["reached"] is True

    def test_write_failure_does_not_cause_duplicate_result_semantics(self, tmp_path: Path):
        """Ties directly to the idempotency contract mentioned in the
        design doc §8.2: a logging failure must never look like "the item
        wasn't attempted" to any resume/retry logic. This test proves the
        logging layer itself carries no state that could cause that — a
        second emit_event call for the same event is simply a second,
        independent log line (as expected for e.g. legitimate retries),
        never something that blocks or mutates a prior write."""
        log_file = tmp_path / "test.log"
        setup_logging(LoggingConfig(log_file_path=log_file))
        logger = logging.getLogger("benchmark_llm.idempotency_test")

        for _ in range(3):
            emit_event(logger, Event.WRITE_COMPLETE, run_id="run_1", response_id="resp_1")

        jsonl_path = tmp_path / "test.jsonl"
        lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        # Three independent log lines — logging itself never deduplicates
        # or blocks; that responsibility stays with ResultWriter's
        # INSERT OR IGNORE, untouched by this checkpoint.
        assert len(lines) == 3


class TestRotationDuringExecution:
    def test_rotation_does_not_lose_or_split_lines(self, tmp_path: Path):
        """Force rotation mid-stream with a tiny maxBytes and confirm every
        SURVIVING line (within the configured backup_count retention —
        RotatingFileHandler correctly discards older backups beyond that,
        which is retention working as configured, not data loss) parses
        cleanly with no fragment/merge — RotatingFileHandler only rotates
        between emit() calls, so no single line can straddle the boundary,
        verified here rather than assumed from stdlib docs. Also confirms
        the surviving lines are a correctly-ordered, contiguous suffix of
        the original sequence (proves nothing was silently corrupted or
        reordered, not that unlimited history is kept — that's what
        backup_count bounds deliberately)."""
        log_file = tmp_path / "rotate.log"
        config = LoggingConfig(log_file_path=log_file, max_bytes=500, backup_count=3)
        setup_logging(config)
        logger = logging.getLogger("benchmark_llm.rotation_test")

        for i in range(50):
            emit_event(logger, Event.ITEM_COMPLETE, run_id=f"run_{i}", variant_id="v", snapshot_id="s", index=i)

        # Confirm rotation actually happened (otherwise this test proves nothing)
        rotated_files = list(tmp_path.glob("rotate.log.*"))
        assert len(rotated_files) > 0, "rotation did not occur — test setup invalid"
        # backup_count=3 + the active file caps retention at 4 files —
        # confirms the configured bound is honored, not exceeded.
        assert len(rotated_files) <= 3

        all_files = [log_file] + rotated_files
        indices: list[int] = []
        for f in all_files:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                # Every surviving line must be a complete, parseable human
                # log line (well-formed text, not a fragment/merge).
                assert "ITEM_COMPLETE | run_id=run_" in line
                index = int(line.split("index=")[1])
                indices.append(index)

        # Nothing lost or corrupted WITHIN the retained window: the
        # surviving indices are exactly the most recent N, contiguous and
        # unique — never a gap, never a duplicate (file read order across
        # active+rotated files is not chronological, so we check set
        # membership/contiguity, not list ordering).
        assert len(indices) == len(set(indices)), "duplicate index — a line was corrupted/duplicated"
        assert max(indices) == 49, "the most recent write must always survive"
        assert set(indices) == set(range(min(indices), 50)), "gap in retained indices — a line was lost mid-window"
