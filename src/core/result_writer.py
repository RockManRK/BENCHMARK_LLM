"""ResultWriter module for TO-BE architecture.

This module provides the ResultWriter component that persists ExecutionResults
to the database. It is the ONLY component with database write access.

Key Principles:
- Only DB write component (ExecutionEngine and Planner have NO write access)
- Calculates needs_review before INSERT
- Idempotent writes (UNIQUE constraint + INSERT OR IGNORE)
- Updates run status after all writes complete

Example:
    >>> import sqlite3
    >>> from src.core.result_writer import ResultWriter
    >>>
    >>> conn = sqlite3.connect(':memory:')
    >>> writer = ResultWriter(conn)
    >>> report = writer.write_results(results)
    >>> print(f"Written: {report.responses_written}, Skipped: {report.responses_skipped}")
"""

import sqlite3
from dataclasses import dataclass
from logging import Logger
from typing import Literal, Optional

from src.core.execution_engine import ExecutionResult
from src.utils.logging_config import get_logger


@dataclass
class WriteReport:
    """Summary of write operations.

    This dataclass is returned by ResultWriter.write_results() and
    provides a summary of what was persisted to the database.

    Attributes:
        responses_written: Number of new responses inserted
        responses_skipped: Number of responses already existed (idempotency)
        errors_written: Number of errors inserted
        runs_updated: List of (run_id, new_status) tuples for status updates

    Example:
        >>> report = writer.write_results(results)
        >>> print(f"Responses: {report.responses_written}")
        >>> print(f"Errors: {report.errors_written}")
        >>> print(f"Runs updated: {report.runs_updated}")
    """

    responses_written: int = 0
    responses_skipped: int = 0
    errors_written: int = 0
    runs_updated: list[tuple[str, str]] = None

    def __post_init__(self) -> None:
        """Initialize runs_updated to empty list if None."""
        if self.runs_updated is None:
            self.runs_updated = []


class ResultWriter:
    """Persists execution outcomes to database.

    The ResultWriter is the ONLY component with database write access.
    It is responsible for:

    - Calculating needs_review from parse_confidence and selected_answer
    - Idempotent writes using UNIQUE constraint + INSERT OR IGNORE
    - Updating run status after all writes complete
    - Writing success results to responses table
    - Writing failure results to errors table

    Attributes:
        db_connection: SQLite database connection

    Example:
        >>> conn = sqlite3.connect('benchmark.db')
        >>> writer = ResultWriter(conn)
        >>> report = writer.write_results(results)
    """

    def __init__(self, db_connection: sqlite3.Connection, logger: Optional[Logger] = None) -> None:
        """Initialize with database connection.

        Args:
            db_connection: SQLite database connection with row_factory enabled
            logger: Optional logger instance. If not provided, uses get_logger('core.result_writer').

        Example:
            >>> conn = sqlite3.connect(':memory:')
            >>> conn.row_factory = sqlite3.Row
            >>> writer = ResultWriter(conn)
        """
        self.db_connection = db_connection
        self._logger = logger or get_logger('core.result_writer')

    def write_results(self, results: list[ExecutionResult]) -> WriteReport:
        """Persist execution results to database.

        This method processes all ExecutionResult instances and:
        1. Calculates needs_review for each result
        2. Writes success results to responses table (idempotent)
        3. Writes failure results to errors table
        4. Updates run status based on overall results

        Args:
            results: List of ExecutionResult from ExecutionEngine

        Returns:
            WriteReport with counts and run status updates

        Example:
            >>> results = engine.execute(plan)
            >>> report = writer.write_results(results)
            >>> print(f"Written: {report.responses_written}")
        """
        report = WriteReport()

        # Extract run_id for logging (use first result if available)
        run_id = results[0].run_id if results else "unknown"

        # Log write start
        self._logger.info(f"WRITE_START | run={run_id} | items={len(results)}")

        # Group results by run_id for status updates
        results_by_run: dict[str, list[ExecutionResult]] = {}
        for result in results:
            if result.run_id not in results_by_run:
                results_by_run[result.run_id] = []
            results_by_run[result.run_id].append(result)

        # Process each result
        for result in results:
            if result.status == 'success':
                written = self._write_response(result)
                if written:
                    report.responses_written += 1
                else:
                    report.responses_skipped += 1
            else:  # failure
                self._write_error(result)
                report.errors_written += 1

        # Update run statuses
        for run_id, run_results in results_by_run.items():
            status = self._determine_run_status(run_results)
            self._update_run_status(run_id, status)
            report.runs_updated.append((run_id, status))

        # Log write complete
        self._logger.info(
            f"WRITE_COMPLETE | run={run_id} | written={report.responses_written} | skipped={report.responses_skipped}"
        )

        return report

    def _calculate_needs_review(
        self,
        parse_confidence: str | None,
        selected_answer: str | None,
    ) -> bool:
        """Calculate needs_review flag from parse_confidence and selected_answer.

        Domain Rules:
        - parse_confidence in ('ambiguous', 'no_answer', 'low_confidence') → TRUE
        - selected_answer is None → TRUE
        - parse_confidence == 'clear' AND selected_answer is not None → FALSE

        Args:
            parse_confidence: Confidence level from answer parser
            selected_answer: Parsed answer letter (A/B/C/D) or None

        Returns:
            True if result needs manual review, False otherwise

        Example:
            >>> writer._calculate_needs_review('clear', 'B')
            False
            >>> writer._calculate_needs_review('ambiguous', 'B')
            True
            >>> writer._calculate_needs_review('clear', None)
            True
        """
        # Check confidence level first
        if parse_confidence in ('ambiguous', 'no_answer', 'low_confidence'):
            return True

        # Check if answer was selected
        if selected_answer is None:
            return True

        # Clear confidence with answer = no review needed
        return False

    def _generate_response_id(
        self,
        run_id: str,
        variant_id: str,
        snapshot_id: str,
    ) -> str:
        """Generate deterministic response ID from item components.

        Args:
            run_id: Run identifier
            variant_id: Variant identifier
            snapshot_id: Snapshot identifier

        Returns:
            Response ID in format 'resp-{run_id}-{variant_id}-{snapshot_id}'

        Example:
            >>> response_id = writer._generate_response_id('run-001', 'var-abc', 'snap-xyz')
            >>> assert response_id == 'resp-run-001-var-abc-snap-xyz'
        """
        return f"resp-{run_id}-{variant_id}-{snapshot_id}"

    def _generate_error_id(
        self,
        run_id: str,
        variant_id: str,
        snapshot_id: str,
    ) -> str:
        """Generate deterministic error ID from item components.

        Args:
            run_id: Run identifier
            variant_id: Variant identifier
            snapshot_id: Snapshot identifier

        Returns:
            Error ID in format 'err-{run_id}-{variant_id}-{snapshot_id}'

        Example:
            >>> error_id = writer._generate_error_id('run-001', 'var-abc', 'snap-xyz')
            >>> assert error_id == 'err-run-001-var-abc-snap-xyz'
        """
        return f"err-{run_id}-{variant_id}-{snapshot_id}"

    def _write_response(self, result: ExecutionResult) -> bool:
        """Write single response with idempotency.

        Uses INSERT OR IGNORE with UNIQUE constraint on (run_id, variant_id, snapshot_id).
        Returns True if written, False if already existed.

        Args:
            result: ExecutionResult to persist

        Returns:
            True if response was written, False if already existed

        Example:
            >>> written = writer._write_response(result)
            >>> if written:
            ...     print("New response written")
            ... else:
            ...     print("Response already existed (idempotency)")
        """
        cursor = self.db_connection.cursor()

        # Calculate needs_review before INSERT
        needs_review = self._calculate_needs_review(
            result.parse_confidence,
            result.selected_answer,
        )

        # Get model_id from variant (we need to look it up)
        model_id = self._get_model_id_from_variant(result.variant_id)

        # Generate response_id (deterministic from item components)
        response_id = self._generate_response_id(
            result.run_id,
            result.variant_id,
            result.snapshot_id,
        )

        # INSERT OR IGNORE (idempotency via UNIQUE constraint)
        cursor.execute("""
            INSERT OR IGNORE INTO responses (
                response_id, run_id, variant_id, snapshot_id,
                model_id, question_id, response_text, selected_answer,
                parse_confidence, needs_review, latency_ms,
                input_tokens, output_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response_id,
            result.run_id,
            result.variant_id,
            result.snapshot_id,
            model_id,
            result.question_id,
            result.response_text,
            result.selected_answer,
            result.parse_confidence,
            1 if needs_review else 0,
            result.latency_ms,
            result.input_tokens,
            result.output_tokens,
        ))

        self.db_connection.commit()

        # rowcount > 0 means INSERT succeeded (not ignored)
        if cursor.rowcount > 0:
            self._logger.debug(f"WRITE_COMPLETE | run={result.run_id} | response_id={response_id}")
            return True
        else:
            self._logger.debug(f"WRITE_SKIP_IDEMPOTENT | run={result.run_id} | response_id={response_id}")
            return False

    def _write_error(self, result: ExecutionResult) -> None:
        """Write error result to errors table.

        Args:
            result: ExecutionResult with status='failure'

        Example:
            >>> writer._write_error(failed_result)
        """
        cursor = self.db_connection.cursor()

        # Generate error_id
        error_id = self._generate_error_id(
            result.run_id,
            result.variant_id,
            result.snapshot_id,
        )

        cursor.execute("""
            INSERT OR IGNORE INTO errors (
                error_id, run_id, variant_id, snapshot_id,
                question_id, error_type, error_message, attempt_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            error_id,
            result.run_id,
            result.variant_id,
            result.snapshot_id,
            result.question_id,
            result.error_type,
            result.error_message,
            result.attempt_count,
        ))

        self.db_connection.commit()

        self._logger.debug(f"WRITE_COMPLETE | run={result.run_id} | error_id={error_id}")

    def _determine_run_status(self, results: list[ExecutionResult]) -> Literal['completed', 'failed', 'partial_failed']:
        """Determine run status based on results.

        Rules:
        - All success → 'completed'
        - All failure → 'failed'
        - Mixed → 'partial_failed'

        Args:
            results: List of ExecutionResult for a single run

        Returns:
            Run status string

        Example:
            >>> status = writer._determine_run_status([success_result])
            >>> assert status == 'completed'
        """
        if not results:
            return 'completed'

        successes = sum(1 for r in results if r.status == 'success')
        failures = sum(1 for r in results if r.status == 'failure')

        if failures == 0:
            return 'completed'
        elif successes == 0:
            return 'failed'
        else:
            return 'partial_failed'

    def _update_run_status(self, run_id: str, status: str) -> None:
        """Update run status in database.

        Args:
            run_id: Run identifier
            status: New status ('completed', 'failed', 'partial_failed')

        Example:
            >>> writer._update_run_status('run-001', 'completed')
        """
        cursor = self.db_connection.cursor()

        # Update status for terminal states (no finished_at in schema)
        if status in ('completed', 'failed', 'partial_failed'):
            cursor.execute("""
                UPDATE runs
                SET status = ?
                WHERE run_id = ?
            """, (status, run_id))
        else:
            cursor.execute("""
                UPDATE runs
                SET status = ?
                WHERE run_id = ?
            """, (status, run_id))

        self.db_connection.commit()

    def _get_model_id_from_variant(self, variant_id: str) -> str:
        """Get model_id from variant_id.

        Args:
            variant_id: Variant identifier

        Returns:
            Model ID (e.g., 'openai/gpt-4')

        Raises:
            ValueError: If variant not found

        Example:
            >>> model_id = writer._get_model_id_from_variant('var-abc-123')
            >>> assert model_id == 'openai/gpt-4'
        """
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT model_id FROM model_variants WHERE variant_id = ?
        """, (variant_id,))

        row = cursor.fetchone()
        if row is None:
            self._logger.error(f"WRITE_ERROR | variant={variant_id} | error=Variant not found")
            raise ValueError(f"Variant not found: {variant_id}")

        return row['model_id']
