"""ResultWriter module for TO-BE architecture.

This module provides the ResultWriter component that persists ExecutionResults
to the database. It is the ONLY component with database write access.

Key Principles:
- Only DB write component (ExecutionEngine and Planner have NO write access)
- Calculates needs_review before INSERT
- Idempotent writes (UNIQUE constraint + INSERT OR IGNORE)
- Each result is written individually via write_result()
"""

import json
import logging
import sqlite3
from logging import Logger
from typing import Optional

from src.core.execution_engine import ExecutionResult
from src.core.json_serializer import serialize_json
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event


class ResultWriter:
    """Persists execution outcomes to database.

    The ResultWriter is the ONLY component with database write access.
    It is responsible for:

    - Calculating review_status from parse_confidence and selected_answer
    - Idempotent writes using UNIQUE constraint + INSERT OR IGNORE
    - Writing success results to responses table
    - Writing failure results to errors table

    Attributes:
        db_connection: SQLite database connection

    Example:
        >>> conn = sqlite3.connect('benchmark.db')
        >>> writer = ResultWriter(conn)
        >>> writer.write_result(result)
    """

    def __init__(
        self,
        db_connection: sqlite3.Connection,
        logger: Optional[Logger] = None,
        operation_id: str | None = None,
    ) -> None:
        """Initialize with database connection.

        Args:
            db_connection: SQLite database connection with row_factory enabled
            logger: Optional logger instance. If not provided, uses get_logger('core.result_writer').
            operation_id: Correlation ID for the CLI invocation (logging only).

        Example:
            >>> conn = sqlite3.connect(':memory:')
            >>> conn.row_factory = sqlite3.Row
            >>> writer = ResultWriter(conn)
        """
        self.db_connection = db_connection
        self._logger = logger or get_logger('core.result_writer')
        self._operation_id = operation_id

    def write_result(self, result: ExecutionResult) -> None:
        """Write a single ExecutionResult to the database.

        Dispatches to _write_response() or _write_error() based on result.status.

        Args:
            result: ExecutionResult to persist
        """
        if result.status == 'success':
            self._write_response(result)
        else:
            self._write_error(result)

    def _calculate_review_status(
        self,
        parse_confidence: str | None,
        selected_answer: str | None,
    ) -> str:
        """Calculate review_status from parse_confidence and selected_answer.

        Domain Rules:
        - parse_confidence in ('ambiguous', 'no_answer', 'low_confidence') → 'needs_review'
        - selected_answer is None → 'needs_review'
        - parse_confidence == 'clear' AND selected_answer is not None → 'auto'

        Args:
            parse_confidence: Confidence level from answer parser
            selected_answer: Parsed answer letter (A/B/C/D) or None

        Returns:
            'needs_review' if manual review needed, 'auto' otherwise

        Example:
            >>> writer._calculate_review_status('clear', 'B')
            'auto'
            >>> writer._calculate_review_status('ambiguous', 'B')
            'needs_review'
            >>> writer._calculate_review_status('clear', None)
            'needs_review'
        """
        # Check confidence level first
        if parse_confidence in ('ambiguous', 'no_answer', 'low_confidence'):
            return 'needs_review'

        # Check if answer was selected
        if selected_answer is None:
            return 'needs_review'

        # Clear confidence with answer = no review needed
        return 'auto'

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

        # Calculate review_status directly
        review_status = self._calculate_review_status(
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

        # Calculate is_correct by comparing selected_answer vs correct_option_presented
        # Both are LETTERS (A/B/C/D), never text.
        #
        # IMPORTANT: When options are randomized, correct_option_presented contains
        # the correct answer letter IN THE PRESENTED SPACE (not the original answer_key).
        # This ensures the LLM's answer is evaluated against what was actually shown.
        is_correct = None

        if result.selected_answer and result.correct_option_presented:
            is_correct = (result.selected_answer.upper() == result.correct_option_presented.upper())

        # Serialize raw_response to JSON (supports dict and list)
        raw_response_json = serialize_json(result.raw_response, pretty=True)

        # raw_response_consolidated is already JSON (serialized dict from consolidation).
        # Guard: if a dict/list is accidentally passed, serialize it safely.
        if result.raw_response_consolidated is not None and not isinstance(result.raw_response_consolidated, str):
            raw_response_consolidated_json = serialize_json(result.raw_response_consolidated, pretty=True)
        else:
            raw_response_consolidated_json = result.raw_response_consolidated

        # Serialize timestamps to ISO format
        started_at_str = result.started_at.isoformat() if result.started_at else None
        finished_at_str = result.finished_at.isoformat() if result.finished_at else None

        # Error versioning: prepend error history to response_text if there are
        # previous errors for this response. This provides observability into retry
        # attempts while maintaining a single response row per item.
        response_text = result.response_text
        if result.status == "success" and response_text:
            error_history = self._get_error_history(response_id)
            if error_history:
                response_text = self._prepend_error_history(response_text, error_history)

        # INSERT OR IGNORE (idempotency via UNIQUE constraint)
        cursor.execute("""
            INSERT OR IGNORE INTO responses (
                response_id, run_id, variant_id, snapshot_id,
                model_id, question_id, status, finish_reason, error_details,
                response_text, selected_answer, is_correct,
                parse_confidence, review_status, latency_ms,
                input_tokens, response_tokens, reasoning_tokens, cost, effective_tokens,
                raw_response, raw_response_consolidated, request_json, started_at, finished_at,
                randomization_enabled, randomization_seed,
                options_presented, correct_option_presented, option_letter_map
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response_id,
            result.run_id,
            result.variant_id,
            result.snapshot_id,
            model_id,
            result.question_id,
            result.status,
            result.finish_reason,
            result.error_details,
            response_text,
            result.selected_answer,
            is_correct,
            result.parse_confidence,
            review_status,
            result.latency_ms,
            result.input_tokens,
            result.response_tokens,
            result.reasoning_tokens,
            result.cost,
            result.effective_tokens,
            raw_response_json,
            raw_response_consolidated_json,
            result.request_json,
            started_at_str,
            finished_at_str,
            # Experimental context
            result.randomization_enabled,
            result.randomization_seed,
            json.dumps(result.options_presented, ensure_ascii=False) if result.options_presented else None,
            result.correct_option_presented,
            json.dumps(result.option_letter_map, ensure_ascii=False) if result.option_letter_map else None,
        ))

        self.db_connection.commit()

        # rowcount > 0 means INSERT succeeded (not ignored)
        if cursor.rowcount > 0:
            emit_event(
                self._logger, Event.WRITE_COMPLETE, level=logging.DEBUG,
                operation_id=self._operation_id, run_id=result.run_id, response_id=response_id,
            )
            return True
        else:
            emit_event(
                self._logger, Event.WRITE_SKIP_IDEMPOTENT, level=logging.DEBUG,
                operation_id=self._operation_id, run_id=result.run_id, response_id=response_id,
            )
            return False

    def _write_error(self, result: ExecutionResult) -> None:
        """Write error result to errors table.

        Appends a new error row with incremented attempt_number to support
        error versioning. Errors are keyed by (response_id, attempt_number).

        Args:
            result: ExecutionResult with status='failure'

        Example:
            >>> writer._write_error(failed_result)
        """
        cursor = self.db_connection.cursor()

        # Generate response_id (deterministic per item) — this is the canonical key
        response_id = self._generate_response_id(
            result.run_id,
            result.variant_id,
            result.snapshot_id,
        )

        # Compute next attempt_number for this response
        cursor.execute(
            "SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM errors WHERE response_id = ?",
            (response_id,)
        )
        next_attempt = cursor.fetchone()[0]

        # error_id is retained for backward compatibility but is no longer the PK
        error_id = self._generate_error_id(
            result.run_id,
            result.variant_id,
            result.snapshot_id,
        )

        cursor.execute("""
            INSERT INTO errors (
                error_id, response_id, run_id, variant_id, snapshot_id,
                question_id, error_type, error_message, attempt_number, attempt_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            error_id,
            response_id,
            result.run_id,
            result.variant_id,
            result.snapshot_id,
            result.question_id,
            result.error_type,
            result.error_message,
            next_attempt,
            result.attempt_count,
        ))

        self.db_connection.commit()

        self._logger.debug(
            f"WRITE_COMPLETE | run={result.run_id} | response_id={response_id} | "
            f"attempt_number={next_attempt}"
        )

    def _get_error_history(
        self, response_id: str
    ) -> list[dict]:
        """Retrieve error history for a specific response.

        Args:
            response_id: Deterministic response identifier

        Returns:
            List of error dicts sorted by attempt_number ascending.
        """
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT error_type, error_message, attempt_number, occurred_at
            FROM errors
            WHERE response_id = ?
            ORDER BY attempt_number ASC
        """, (response_id,))

        rows = cursor.fetchall()
        return [
            {
                "error_type": row[0],
                "error_message": row[1],
                "attempt_number": row[2],
                "occurred_at": row[3],
            }
            for row in rows
        ]

    @staticmethod
    def _prepend_error_history(response_text: str, error_history: list[dict]) -> str:
        """Prepend error history to response text in reverse chronological order.

        Args:
            response_text: Original successful response text
            error_history: List of previous error dicts

        Returns:
            Response text with error history prepended.
        """
        # Reverse for chronological order (newest first)
        chronological = list(reversed(error_history))
        total_attempts = len(chronological)

        lines = [
            f"[ERROR HISTORY - {total_attempts} attempt(s) before success]"
        ]
        for error in chronological:
            lines.append(
                f"Attempt {error['attempt_number']}: {error['error_type']} - "
                f"{error['error_message']} (at {error['occurred_at']})"
            )
        lines.append("")  # Blank line before actual response
        lines.append("[SUCCESSFUL RESPONSE]")

        return "\n".join(lines) + "\n" + response_text

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
            emit_event(
                self._logger, Event.WRITE_ERROR, level=logging.ERROR,
                operation_id=self._operation_id, variant_id=variant_id,
                error="Variant not found",
            )
            raise ValueError(f"Variant not found: {variant_id}")

        return row['model_id']

    def _get_answer_key_from_snapshot(self, snapshot_id: str) -> str | None:
        """Get answer_key from question snapshot.

        Args:
            snapshot_id: Question snapshot identifier

        Returns:
            Answer key (A/B/C/D) or None if not found
        """
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT question_payload FROM question_snapshots WHERE snapshot_id = ?
        """, (snapshot_id,))

        row = cursor.fetchone()
        if row is None or row[0] is None:
            return None

        try:
            question_payload = json.loads(row[0])
            return question_payload.get('answer_key')
        except (json.JSONDecodeError, KeyError):
            return None
