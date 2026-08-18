"""RunFinalizer — Single owner of EXECUTION-OUTCOME runs.status/duration updates.

The RunFinalizer computes run status and duration from the actual database
state AFTER all items have been executed and written. It is the ONLY component
that may derive runs.status/duration FROM EXECUTION RESULTS (response/error
counts) — no other code in the execution pipeline (Planner, ExecutionEngine,
ResultWriter) may write an execution-outcome status.

Key Principles:
- Duration is computed from a FRESH DB query: SUM(latency_ms) where raw_response IS NOT NULL
- Status is determined from counts of responses with actual data vs errors
- Uses a single transaction for both reads and the write
- Duration stored as integer milliseconds
- NO execution-pipeline code may write runs.status/duration after this

Scope note: this owns status values DERIVED FROM EXECUTION
('completed'/'failed'/'partial_failed'), not the full lifecycle of the
column. `--remove-run` (src/cli/bcllm_run.py::handle_remove_run) sets
status='removed' as a separate, administrative, out-of-band transition —
not part of the execution pipeline this module governs, analogous to how
Response.review_status/manual_answer are mutated by the Review UI, a
different subsystem, without conflicting with ResultWriter's ownership of
the original response data (see docs/contracts/immutability.md).

This fixes the critical bug where re-execution double-counts duration because
the old approach summed latency from ALL in-memory results (including items
that were already executed and got INSERT OR IGNORE'd at write time).

Example:
    >>> import sqlite3
    >>> from src.core.run_finalizer import RunFinalizer
    >>>
    >>> conn = sqlite3.connect('benchmark.db')
    >>> finalizer = RunFinalizer(conn)
    >>> result = finalizer.finalize_run('run-001')
    >>> print(f"Status: {result['status']}, Duration: {result['duration_ms']}ms")
"""

import sqlite3
from logging import Logger
from typing import Optional

from src.utils.logging_config import get_logger


class RunFinalizer:
    """Computes and persists run status and duration from DB state.

    This is the SINGLE owner of runs.status and runs.duration updates.
    It queries the database directly to compute accurate values, avoiding
    the double-counting bug that occurs when summing in-memory results
    that include idempotent-skipped items.

    Attributes:
        conn: Database connection
        logger: Optional logger instance

    Example:
        >>> finalizer = RunFinalizer(conn)
        >>> result = finalizer.finalize_run('run-001')
        >>> print(result)  # {'status': 'completed', 'duration_ms': 5000, 'response_count': 10}
    """

    def __init__(self, db_connection: sqlite3.Connection, logger: Optional[Logger] = None) -> None:
        """Initialize with database connection.

        Args:
            db_connection: SQLite database connection with row_factory enabled
            logger: Optional logger instance. If not provided, uses
                    get_logger('core.run_finalizer').
        """
        self.conn = db_connection
        self._logger = logger or get_logger('core.run_finalizer')

    def finalize_run(self, run_id: str) -> dict:
        """Compute run status and duration from DB state.

        Called AFTER all items have been executed and written.
        Queries the database directly to compute accurate values.

        Returns:
            dict with keys:
                - status: str ('completed', 'failed', 'partial_failed')
                - duration_ms: int (total latency in milliseconds from successful responses)
                - response_count: int (number of items with actual response data)

        Example:
            >>> result = finalizer.finalize_run('run-001')
            >>> print(result['status'])  # 'completed'
            >>> print(result['duration_ms'])  # 5000
        """
        cursor = self.conn.cursor()

        # Use standard autocommit — all reads and the final write are atomic
        # since this runs after the writer has fully drained (no concurrent writes).

        try:
            # Duration: sum latency from successful responses only
            # raw_response IS NOT NULL ensures we only count actual API responses,
            # not error-only records that may exist in the responses table
            cursor.execute(
                """
                SELECT COALESCE(SUM(latency_ms), 0) as total_ms
                FROM responses
                WHERE run_id = ? AND raw_response IS NOT NULL
                """,
                (run_id,),
            )
            duration_row = cursor.fetchone()
            duration_ms = int(duration_row['total_ms'])

            # Status: count successful responses vs errors from both tables
            # responses with raw_response = successful API responses
            # errors table entries = failed items
            cursor.execute(
                """
                SELECT
                    COUNT(*) as success_count
                FROM responses
                WHERE run_id = ? AND raw_response IS NOT NULL
                """,
                (run_id,),
            )
            success_count = cursor.fetchone()['success_count']

            cursor.execute(
                """
                SELECT COUNT(*) as error_count
                FROM errors
                WHERE run_id = ?
                """,
                (run_id,),
            )
            error_count = cursor.fetchone()['error_count']

            # Determine status based on counts
            status = self._determine_status(success_count, error_count)

            # Single UPDATE for both status and duration
            cursor.execute(
                """
                UPDATE runs
                SET status = ?, duration = ?
                WHERE run_id = ?
                """,
                (status, duration_ms, run_id),
            )

            self.conn.commit()

            self._logger.info(
                f"RUN_FINALIZED | run={run_id} | status={status} | "
                f"duration_ms={duration_ms} | responses={success_count} | errors={error_count}"
            )

            return {
                'status': status,
                'duration_ms': duration_ms,
                'response_count': success_count,
            }

        except Exception:
            self.conn.rollback()
            raise

    def _determine_status(self, success_count: int, error_count: int) -> str:
        """Determine run status from success and error counts.

        Rules:
        - All succeeded (error_count == 0) → "completed"
        - All failed (success_count == 0) → "failed"
        - Mixed → "partial_failed"

        Args:
            success_count: Number of responses with actual data
            error_count: Number of responses with errors

        Returns:
            Status string: 'completed', 'failed', or 'partial_failed'
        """
        if error_count == 0:
            return 'completed'
        elif success_count == 0:
            return 'failed'
        else:
            return 'partial_failed'
