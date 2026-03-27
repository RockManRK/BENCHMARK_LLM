"""ResultWriter component for persisting execution outcomes.

This module provides the ResultWriter class, which is responsible for
persisting ExecutionResult objects to the database and updating run status.
The ResultWriter is the ONLY component that writes execution outcomes.

Design Principles:
    - ResultWriter does NOT execute (only receives ExecutionResult)
    - ResultWriter does NOT decide scope (only persists what it receives)
    - ResultWriter is idempotent (same input produces same database state)
    - ResultWriter is deterministic (no random behavior)

Example:
    >>> writer = ResultWriter(db_manager)
    >>> result = writer.write_results(plan, execution_results)
    >>> print(f"Wrote {result.responses_written} responses")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core.execution_plan import ExecutionPlan, ExecutionResult
from src.db.models import Response, Error
from src.db.repository import (
    ResponseRepository,
    ErrorRepository,
    RunRepository,
    RunModelRepository,
)
from src.db.schema import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class WriteResult:
    """Result of write operation.

    Attributes:
        responses_written: Number of new responses inserted
        errors_written: Number of new errors inserted
        responses_skipped: Number of responses skipped (already existed)
        errors_skipped: Number of errors skipped (already existed)
        runs_updated: List of run IDs with updated status

    Example:
        >>> result = WriteResult(
        ...     responses_written=50,
        ...     errors_written=2,
        ...     responses_skipped=0,
        ...     errors_skipped=0,
        ...     runs_updated=["run-001"]
        ... )
    """

    responses_written: int = 0
    errors_written: int = 0
    responses_skipped: int = 0
    errors_skipped: int = 0
    runs_updated: list[str] = field(default_factory=list)


class ResultWriter:
    """Persists execution outcomes and updates run status.

    The ResultWriter is responsible for:
    1. Persisting successful responses to the responses table
    2. Persisting failures to the errors table
    3. Updating run status (completed, partial_failed, failed)
    4. Updating run_model status
    5. Ensuring idempotency (no duplicates)

    Attributes:
        db_manager: DatabaseManager instance for database connections

    Example:
        >>> writer = ResultWriter(db_manager)
        >>> result = writer.write_results(plan, execution_results)
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ResultWriter with database access.

        Args:
            db_manager: DatabaseManager instance for database connections

        Example:
            >>> writer = ResultWriter(db_manager)
        """
        self.db_manager = db_manager
        self._response_repo = ResponseRepository(db_manager)
        self._error_repo = ErrorRepository(db_manager)
        self._run_repo = RunRepository(db_manager)
        self._run_model_repo = RunModelRepository(db_manager)

        logger.info("ResultWriter initialized")

    def write_results(
        self,
        plan: ExecutionPlan,
        results: list[ExecutionResult],
    ) -> WriteResult:
        """Persist all results and update run status.

        This method:
        1. Groups results by run_id
        2. For each result:
           - success → insert into responses (idempotent)
           - failure → insert into errors (idempotent)
        3. Updates run status based on results
        4. Updates run_model status
        5. Returns WriteResult with counts

        Args:
            plan: ExecutionPlan that was executed
            results: List of ExecutionResult objects from ExecutionEngine

        Returns:
            WriteResult with counts and updated run IDs

        Example:
            >>> writer = ResultWriter(db_manager)
            >>> result = writer.write_results(plan, execution_results)
            >>> print(f"Wrote {result.responses_written} responses")
        """
        logger.info(f"Writing {len(results)} results for plan {plan.plan_id}")

        write_result = WriteResult()

        # Group results by run_id
        results_by_run: dict[str, list[ExecutionResult]] = {}
        for result in results:
            if result.run_id not in results_by_run:
                results_by_run[result.run_id] = []
            results_by_run[result.run_id].append(result)

        # Process each run
        for run_id, run_results in results_by_run.items():
            logger.info(f"Processing {len(run_results)} results for run {run_id}")

            # Group by variant_id for run_model status updates
            results_by_variant: dict[str, list[ExecutionResult]] = {}
            for result in run_results:
                if result.variant_id not in results_by_variant:
                    results_by_variant[result.variant_id] = []
                results_by_variant[result.variant_id].append(result)

            # Write each result
            for result in run_results:
                if result.status == "success":
                    written, skipped = self._write_response(result)
                    write_result.responses_written += written
                    write_result.responses_skipped += skipped
                else:
                    written, skipped = self._write_error(result)
                    write_result.errors_written += written
                    write_result.errors_skipped += skipped

            # Update run status
            new_status = self._update_run_status(run_id, run_results)
            if new_status:
                write_result.runs_updated.append(run_id)

            # Update run_model status for each variant
            for variant_id, variant_results in results_by_variant.items():
                self._update_run_model_status(run_id, variant_id, variant_results)

        logger.info(
            f"Write completed: {write_result.responses_written} responses, "
            f"{write_result.errors_written} errors, "
            f"{write_result.responses_skipped} responses skipped, "
            f"{write_result.runs_updated} runs updated"
        )

        return write_result

    def _write_response(self, result: ExecutionResult) -> tuple[int, int]:
        """Write a single response (idempotent).

        Args:
            result: ExecutionResult with status="success"

        Returns:
            Tuple of (written, skipped) - either (1, 0) or (0, 1)
        """
        # Check if response already exists (idempotency)
        if self._response_exists(result):
            logger.debug(f"Response already exists for {result.item_id}, skipping")
            return (0, 1)

        # Build Response object
        response = Response(
            run_id=result.run_id,
            snapshot_id=result.snapshot_id,
            question_id=result.question_id,
            model_id=result.model_id,
            variant_id=result.variant_id,
            selected_answer=result.selected_answer,
            response_text=result.response_text,
            is_correct=result.is_correct,
            status="success",
            finish_reason="stop",
            error_details=None,
            latency_ms=result.latency_ms,
            input_tokens=result.input_tokens,
            response_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            reasoning_tokens=None,  # Stubbed for future
            effective_tokens=None,  # Stubbed for future
            cost=None,  # Stubbed for future
            raw_response_json=None,  # Stubbed for future
            parse_confidence="clear" if result.selected_answer else "no_answer",
            # needs_review per contract: TRUE when parse_confidence is low OR selected_answer is NULL
            needs_review=(
                ("clear" if result.selected_answer else "no_answer") in ("ambiguous", "no_answer", "low_confidence")
                or result.selected_answer is None
            ),
        )

        # Persist response
        try:
            self._response_repo.create(response)
            logger.info(
                f"Wrote response: run={result.run_id}, variant={result.variant_id}, "
                f"question={result.question_id}, answer={result.selected_answer}"
            )
            return (1, 0)
        except Exception as e:
            logger.error(f"Failed to write response: {e}")
            # Convert to error
            return (0, 0)

    def _write_error(self, result: ExecutionResult) -> tuple[int, int]:
        """Write a single error (idempotent).

        Args:
            result: ExecutionResult with status="failure"

        Returns:
            Tuple of (written, skipped) - either (1, 0) or (0, 1)
        """
        # Check if error already exists (idempotency)
        if self._error_exists(result):
            logger.debug(f"Error already exists for {result.item_id}, skipping")
            return (0, 1)

        # Build Error object
        error = Error(
            run_id=result.run_id,
            variant_id=result.variant_id,
            question_id=result.question_id,
            error_type=result.error_type or "ExecutionError",
            error_message=result.error_message or "Unknown error",
            stack_trace="",
            attempt_count=1,
        )

        # Persist error
        try:
            self._error_repo.create(error)
            logger.info(
                f"Wrote error: run={result.run_id}, variant={result.variant_id}, "
                f"question={result.question_id}, error={result.error_message}"
            )
            return (1, 0)
        except Exception as e:
            logger.error(f"Failed to write error: {e}")
            return (0, 0)

    def _response_exists(self, result: ExecutionResult) -> bool:
        """Check if response already exists (idempotency check).

        Key: (run_id, variant_id, snapshot_id)

        Args:
            result: ExecutionResult to check

        Returns:
            True if response already exists
        """
        # Query database for existing response
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM responses
                WHERE run_id = ? AND variant_id = ? AND snapshot_id = ?
                """,
                (result.run_id, result.variant_id, result.snapshot_id),
            )
            return cursor.fetchone() is not None
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def _error_exists(self, result: ExecutionResult) -> bool:
        """Check if error already exists (idempotency check).

        Key: (run_id, variant_id, snapshot_id)

        Args:
            result: ExecutionResult to check

        Returns:
            True if error already exists
        """
        # Query database for existing error
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM errors
                WHERE run_id = ? AND variant_id = ? AND snapshot_id = ?
                """,
                (result.run_id, result.variant_id, result.snapshot_id),
            )
            return cursor.fetchone() is not None
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def _update_run_status(self, run_id: str, results: list[ExecutionResult]) -> Optional[str]:
        """Update run status based on results.

        Status rules:
        - completed: All items succeeded
        - partial_failed: Some items failed, some succeeded
        - failed: All items failed

        Args:
            run_id: Run identifier
            results: List of ExecutionResult for this run

        Returns:
            New status if updated, None if run not found
        """
        # Count successes and failures
        successes = sum(1 for r in results if r.status == "success")
        failures = sum(1 for r in results if r.status == "failure")

        # Determine new status
        if failures == 0 and successes > 0:
            new_status = "completed"
        elif successes > 0:
            new_status = "partial_failed"
        else:
            new_status = "failed"

        # Update run status
        run = self._run_repo.get_by_id(run_id)
        if not run:
            logger.warning(f"Run {run_id} not found for status update")
            return None

        # Don't update if already in a final state
        if run.status in ("completed", "failed"):
            logger.info(f"Run {run_id} already in final state {run.status}, not updating")
            return run.status

        self._run_repo.update_status(run_id, new_status)
        logger.info(f"Updated run {run_id} status to {new_status}")

        return new_status

    def _update_run_model_status(
        self,
        run_id: str,
        variant_id: str,
        results: list[ExecutionResult],
    ) -> None:
        """Update run_model status based on results.

        Status rules:
        - completed: All items for this variant succeeded
        - partial_failed: Some items failed, some succeeded
        - failed: All items failed

        Args:
            run_id: Run identifier
            variant_id: Variant identifier
            results: List of ExecutionResult for this variant
        """
        # Count successes and failures
        successes = sum(1 for r in results if r.status == "success")
        failures = sum(1 for r in results if r.status == "failure")

        # Determine new status
        if failures == 0 and successes > 0:
            new_status = "completed"
        elif successes > 0:
            new_status = "partial_failed"
        else:
            new_status = "failed"

        # Update run_model status
        self._run_model_repo.update_status(run_id, variant_id, new_status)
        logger.info(
            f"Updated run_model status: run={run_id}, variant={variant_id}, status={new_status}"
        )
