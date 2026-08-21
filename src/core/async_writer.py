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
from logging import Logger
from typing import Optional

from src.core.execution_engine import ExecutionResult
from src.core.result_writer import ResultWriter
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event
import logging


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
                    return False

        return False

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
