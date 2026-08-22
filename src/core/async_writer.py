"""AsyncWriter module for incremental result persistence.

This module provides the AsyncWriter component that consumes results from an
asyncio.Queue and writes them to the database immediately — providing incremental
persistence instead of batch-writing at the end of a run.

Contract:
- Runs as a single consumer task via consume()
- Writes each result to DB immediately after receiving it
- Shuts down on sentinel (None) from queue OR on abort event
- DB write failures: retry up to 3 times with exponential backoff
- If all retries fail: set abort_event and return immediately
- NEVER creates or destroys resources (queue and DB connection are injected)

Example:
    >>> import asyncio
    >>> import sqlite3
    >>> from src.core.async_writer import AsyncWriter
    >>>
    >>> queue = asyncio.Queue()
    >>> conn = sqlite3.connect(':memory:')
    >>> writer = AsyncWriter(queue, conn)
    >>> task = asyncio.create_task(writer.consume())
    >>> # Push results to queue...
    >>> queue.put_nowait(result)
    >>> # Send sentinel to stop
    >>> queue.put_nowait(None)
    >>> stats = await task
    >>> print(f"Written: {stats['written']}, Errors: {stats['errors']}")
"""

import asyncio
from dataclasses import replace
from logging import Logger
from typing import Optional

from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event
import logging


def _bounded_excerpt(text: str | None, max_len: int = 200) -> str | None:
    """Truncate response_text for inclusion in a best-effort audit
    error_message (ADR-004) — bounded, not the full verbatim content."""
    if text is None:
        return None
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...(truncated)"


def _build_persistence_failure_message(
    result: ExecutionResult, reason: str, original_exception: Exception,
) -> str:
    """Build the error_message for a best-effort errors-row audit trail
    (ADR-004, ASY-01) recording that a received ExecutionResult could not
    be persisted as a response. Includes: that a result was received, that
    the failure was one of persistence (not the original API/parse
    outcome), the original exception, item identity, the ExecutionResult's
    original status (and its own error_type/error_message, if it already
    had one), a bounded response_text excerpt, and token/cost fields —
    all already present on ExecutionResult, no new schema needed."""
    parts = [
        f"Received ExecutionResult could not be persisted as a response — {reason}.",
        f"original_exception={original_exception!r}",
        f"item_id={result.item_id!r} run_id={result.run_id!r} variant_id={result.variant_id!r} "
        f"snapshot_id={result.snapshot_id!r} question_id={result.question_id!r}",
        f"original_status={result.status!r}",
    ]
    if result.error_type is not None or result.error_message is not None:
        parts.append(
            f"original_error_type={result.error_type!r} original_error_message={result.error_message!r}"
        )
    excerpt = _bounded_excerpt(result.response_text)
    if excerpt is not None:
        parts.append(f"response_text_excerpt={excerpt!r}")
    token_bits = []
    if result.input_tokens is not None:
        token_bits.append(f"input_tokens={result.input_tokens}")
    if result.response_tokens is not None:
        token_bits.append(f"response_tokens={result.response_tokens}")
    if result.reasoning_tokens is not None:
        token_bits.append(f"reasoning_tokens={result.reasoning_tokens}")
    if result.cost is not None:
        token_bits.append(f"cost={result.cost}")
    if token_bits:
        parts.append(" ".join(token_bits))
    return " | ".join(parts)


class AsyncWriter:
    """Consumes results from async queue and writes them to DB incrementally.

    Contract:
    - Runs as a single consumer task via consume()
    - Writes each result to DB immediately after receiving it
    - Shuts down on sentinel (None) from queue OR on abort_event
    - DB write failures: retry 3x with backoff, then abort

    Attributes:
        results_written: List of successfully written ExecutionResult instances
        stats: Dictionary with written and error counts
        abort_event: Set when persistence fails after retries

    Example:
        >>> queue = asyncio.Queue()
        >>> conn = sqlite3.connect(':memory:')
        >>> writer = AsyncWriter(queue, conn)
        >>> task = asyncio.create_task(writer.consume())
        >>> queue.put_nowait(result)
        >>> queue.put_nowait(None)
        >>> stats = await task
    """

    MAX_RETRIES = 3
    RETRY_BACKOFF_BASE = 0.5  # seconds: 0.5s, 1.0s, 1.5s

    def __init__(
        self,
        queue: asyncio.Queue,
        db_connection,
        logger: Optional[Logger] = None,
        operation_id: str | None = None,
    ) -> None:
        """Initialize with queue and database connection.

        Args:
            queue: asyncio.Queue to consume results from
            db_connection: SQLite database connection
            logger: Optional logger instance
            operation_id: Correlation ID for the CLI invocation (logging only).

        Example:
            >>> queue = asyncio.Queue()
            >>> conn = sqlite3.connect(':memory:')
            >>> writer = AsyncWriter(queue, conn)
        """
        self._queue = queue
        self._db = db_connection
        self._logger = logger or get_logger('core.async_writer')
        self._operation_id = operation_id
        self._results_written: list[ExecutionResult] = []
        self._write_count: int = 0
        self._error_count: int = 0
        self._abort_event = asyncio.Event()
        self._abort_info: dict | None = None
        # Single ResultWriter instance reused for all writes (avoids per-retry allocation)
        self._result_writer = ResultWriter(self._db, logger=self._logger, operation_id=operation_id)

    @property
    def abort_event(self) -> asyncio.Event:
        """Returns the abort event. Set when persistence fails after retries."""
        return self._abort_event

    @property
    def abort_info(self) -> dict | None:
        """Returns abort details if writer failed, None otherwise."""
        return self._abort_info

    async def consume(self) -> dict:
        """Main consumer loop. Runs until sentinel (None) or abort.

        Returns:
            Statistics dict: {written, errors, aborted, abort_info}

        Behavior:
        - Awaits queue.get() in a loop
        - If item is None (sentinel): break loop
        - If abort_event is set: break loop
        - Try to write the result to DB with retry
        - On DB failure after all retries: set abort_event, return immediately

        Example:
            >>> task = asyncio.create_task(writer.consume())
            >>> queue.put_nowait(result)
            >>> queue.put_nowait(None)
            >>> stats = await task
            >>> print(stats)
            {'written': 1, 'errors': 0, 'aborted': False}
        """
        while True:
            if self._abort_event.is_set():
                break

            try:
                result = await self._queue.get()
            except asyncio.CancelledError:
                break

            if result is None:
                self._queue.task_done()
                break

            try:
                success = await self._write_result_with_retry(result)
                if success:
                    self._write_count += 1
                    self._results_written.append(result)
                    emit_event(
                        self._logger, Event.WRITE_OK, level=logging.DEBUG,
                        operation_id=self._operation_id, run_id=result.run_id,
                        variant_id=result.variant_id, snapshot_id=result.snapshot_id,
                        outcome=result.status,
                    )
                else:
                    # Write failed after retries — abort
                    break
            except Exception as e:
                self._error_count += 1
                emit_event(
                    self._logger, Event.WRITE_FAIL, level=logging.ERROR,
                    operation_id=self._operation_id, run_id=result.run_id,
                    variant_id=result.variant_id, snapshot_id=result.snapshot_id,
                    error=str(e),
                )

            self._queue.task_done()

        return {
            "written": self._write_count,
            "errors": self._error_count,
            "aborted": self._abort_event.is_set(),
            "abort_info": self._abort_info,
        }

    async def _write_result_with_retry(self, result: ExecutionResult) -> bool:
        """Write a single result with retry logic.

        Uses a single reusable ResultWriter instance to avoid per-retry allocation.

        Args:
            result: ExecutionResult to persist

        Returns:
            True if write succeeded, False if all retries exhausted.
        """
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self._result_writer.write_result(result)
                return True
            except Exception as e:
                if attempt < self.MAX_RETRIES:
                    backoff = self.RETRY_BACKOFF_BASE * attempt
                    emit_event(
                        self._logger, Event.WRITE_RETRY, level=logging.WARNING,
                        operation_id=self._operation_id, run_id=result.run_id,
                        variant_id=result.variant_id, snapshot_id=result.snapshot_id,
                        attempt=attempt, max_attempts=self.MAX_RETRIES,
                        delay_ms=round(backoff * 1000), error=str(e),
                    )
                    await asyncio.sleep(backoff)
                else:
                    self._error_count += 1
                    emit_event(
                        self._logger, Event.WRITE_ABORT, level=logging.CRITICAL,
                        operation_id=self._operation_id, run_id=result.run_id,
                        variant_id=result.variant_id, snapshot_id=result.snapshot_id,
                        attempts=self.MAX_RETRIES, error=str(e),
                    )
                    self._abort_info = {
                        "run_id": result.run_id,
                        "variant_id": result.variant_id,
                        "snapshot_id": result.snapshot_id,
                        "error": str(e),
                        "attempts": self.MAX_RETRIES,
                    }
                    self._abort_event.set()
                    # ADR-004/ASY-01: fail-fast is preserved — this does
                    # NOT retry the response write again. It records one
                    # additional, best-effort, already-shaped errors row
                    # so the received result stays auditable and the run
                    # can never be finalized as 'completed' having lost it.
                    self._record_persistence_failure_as_error(
                        result, error_type="write_failure",
                        reason="persistence failed after all retries",
                        original_exception=e,
                        recorded_event=Event.WRITE_FAILURE_RECORDED,
                    )
                    return False

        return False

    def _record_persistence_failure_as_error(
        self,
        result: ExecutionResult,
        error_type: str,
        reason: str,
        original_exception: Exception,
        recorded_event: str,
    ) -> None:
        """Best-effort audit trail for a received ExecutionResult that
        could not be durably persisted as a response (ADR-004, ASY-01).

        Reuses ResultWriter._write_error() UNMODIFIED — it only ever reads
        error_type/error_message/attempt_count, never `status`, so it
        applies cleanly even to an originally-`status='success'` result
        whose *persistence* failed, not its API call. Never raises: if
        even this best-effort write fails (total DB unavailability), the
        CRITICAL WRITE_FAILURE_TRACE_FAILED log event is the final,
        explicitly-accepted fallback (ADR-004, Decision 2) — it must never
        mask or interrupt the original abort.
        """
        message = _build_persistence_failure_message(result, reason, original_exception)
        error_result = replace(result, error_type=error_type, error_message=message)
        try:
            self._result_writer._write_error(error_result)
        except Exception as trace_exc:
            emit_event(
                self._logger, Event.WRITE_FAILURE_TRACE_FAILED, level=logging.CRITICAL,
                operation_id=self._operation_id, item_id=result.item_id,
                run_id=result.run_id, variant_id=result.variant_id, snapshot_id=result.snapshot_id,
                error_type=error_type, original_exception=repr(original_exception),
                trace_exception=repr(trace_exc),
            )
            return
        emit_event(
            self._logger, recorded_event, level=logging.ERROR,
            operation_id=self._operation_id, item_id=result.item_id,
            run_id=result.run_id, variant_id=result.variant_id, snapshot_id=result.snapshot_id,
            error_type=error_type,
        )

    def drain_abandoned(self) -> int:
        """Best-effort, non-blocking drain of any items left in the queue
        after an abort (ADR-004, ASY-01). Called by the caller (e.g.
        AsyncOrchestrator) once consume() has returned with abort_event
        set — never resumes normal consumption, never retries a write,
        never re-executes an item.

        Each real ExecutionResult found is recorded as an auditable error
        row (error_type='abandoned_after_writer_abort'), never persisted
        as a normal response. A sentinel (None) or any other
        non-ExecutionResult queue entry is drained and discarded safely —
        never treated as a lost item. Never raises.

        Returns:
            Count of ExecutionResult items recorded as abandoned.
        """
        abandoned = 0
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            self._queue.task_done()
            if not isinstance(item, ExecutionResult):
                # Sentinel or other structural entry — not a lost item.
                continue
            self._record_persistence_failure_as_error(
                item, error_type="abandoned_after_writer_abort",
                reason=(
                    "never reached the writer — abandoned in the queue "
                    "after a sibling item's writer abort"
                ),
                original_exception=RuntimeError(
                    "writer aborted before this item could be attempted"
                ),
                recorded_event=Event.ITEM_ABANDONED_AFTER_WRITER_ABORT,
            )
            abandoned += 1
        return abandoned

    @property
    def results_written(self) -> list[ExecutionResult]:
        """Return a copy of successfully written results.

        Returns:
            List of ExecutionResult instances

        Example:
            >>> results = writer.results_written
            >>> len(results)
            5
        """
        return list(self._results_written)

    @property
    def stats(self) -> dict:
        """Return current writer statistics.

        Returns:
            Dictionary with written and error counts

        Example:
            >>> writer.stats
            {'written': 5, 'errors': 0}
        """
        return {
            "written": self._write_count,
            "errors": self._error_count,
        }
