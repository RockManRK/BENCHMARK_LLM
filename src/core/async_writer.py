"""AsyncWriter module for incremental result persistence.

This module provides the AsyncWriter component that consumes results from an
asyncio.Queue and writes them to the database immediately — providing incremental
persistence instead of batch-writing at the end of a run.

Contract:
- Runs as a single consumer task via consume()
- Writes each result to DB immediately after receiving it
- Shuts down ONLY on sentinel (None) from queue
- DB write failures are logged and skipped — writer continues consuming
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


class AsyncWriter:
    """Consumes results from async queue and writes them to DB incrementally.

    Contract:
    - Runs as a single consumer task via consume()
    - Writes each result to DB immediately after receiving it
    - Shuts down ONLY on sentinel (None) from queue
    - DB write failures are logged and skipped — writer continues consuming

    Attributes:
        results_written: List of successfully written ExecutionResult instances
        stats: Dictionary with written and error counts

    Example:
        >>> queue = asyncio.Queue()
        >>> conn = sqlite3.connect(':memory:')
        >>> writer = AsyncWriter(queue, conn)
        >>> task = asyncio.create_task(writer.consume())
        >>> queue.put_nowait(result)
        >>> queue.put_nowait(None)
        >>> stats = await task
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        db_connection,
        logger: Optional[Logger] = None,
    ) -> None:
        """Initialize with queue and database connection.

        Args:
            queue: asyncio.Queue to consume results from
            db_connection: SQLite database connection
            logger: Optional logger instance

        Example:
            >>> queue = asyncio.Queue()
            >>> conn = sqlite3.connect(':memory:')
            >>> writer = AsyncWriter(queue, conn)
        """
        self._queue = queue
        self._db = db_connection
        self._logger = logger or get_logger('core.async_writer')
        self._results_written: list[ExecutionResult] = []
        self._write_count: int = 0
        self._error_count: int = 0

    async def consume(self) -> dict:
        """Main consumer loop. Runs until sentinel (None) is received.

        Returns:
            Statistics dict: {written, errors}

        Behavior:
        - Awaits queue.get() in a loop
        - If item is None (sentinel): break loop
        - Try to write the result to DB
        - On DB failure: log error with full context, increment error_count, CONTINUE
        - On success: track result

        Example:
            >>> task = asyncio.create_task(writer.consume())
            >>> queue.put_nowait(result)
            >>> queue.put_nowait(None)
            >>> stats = await task
            >>> print(stats)
            {'written': 1, 'skipped': 0, 'errors': 0}
        """
        while True:
            try:
                result = await self._queue.get()
            except asyncio.CancelledError:
                break

            if result is None:
                self._queue.task_done()
                break

            try:
                self._write_result(result)
                self._write_count += 1
                self._results_written.append(result)
                self._logger.debug(
                    f"WRITE_OK | run={result.run_id} | variant={result.variant_id} | "
                    f"snapshot={result.snapshot_id} | status={result.status}"
                )
            except Exception as e:
                self._error_count += 1
                self._logger.error(
                    f"WRITE_FAIL | run={result.run_id} | variant={result.variant_id} | "
                    f"snapshot={result.snapshot_id} | error={e}"
                )

            self._queue.task_done()

        return {
            "written": self._write_count,
            "errors": self._error_count,
        }

    def _write_result(self, result: ExecutionResult) -> None:
        """Write a single ExecutionResult to DB using existing ResultWriter logic.

        Args:
            result: ExecutionResult to persist

        Raises:
            Exception: Any exception from ResultWriter.write_result()
        """
        writer = ResultWriter(self._db, logger=self._logger)
        writer.write_result(result)

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
