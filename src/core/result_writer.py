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
import sqlite3
from logging import Logger
from typing import Optional

from src.core.execution_engine import ExecutionResult
from src.core.json_serializer import serialize_json
from src.utils.logging_config import get_logger


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
            result.response_text,
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
