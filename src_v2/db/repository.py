"""TO-BE repository layer.

CRUD operations for all 6 entities:
- ExperimentRepository
- VariantRepository
- SnapshotRepository
- RunRepository
- ResponseRepository
- ErrorRepository

Each repository:
- Takes a sqlite3.Connection in __init__
- Provides save(), get_by_id(), list_all() methods
- Uses dataclasses for type-safe I/O
- NO soft delete (is_active removed)
- NO created_at in INSERT (DB DEFAULT CURRENT_TIMESTAMP)
"""

import json
import sqlite3
from typing import Any

from src_v2.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
    Error,
)


# =============================================================================
# ExperimentRepository
# =============================================================================

class ExperimentRepository:
    """CRUD operations for experiments."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection.

        Args:
            conn: SQLite database connection.
        """
        self.conn = conn

    def save(self, experiment: Experiment) -> None:
        """Insert or update experiment.

        Uses INSERT OR REPLACE for idempotency.
        Does NOT pass created_at - let DB DEFAULT handle it.

        Args:
            experiment: Experiment dataclass to save.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO experiments (
                experiment_id, name, description, config_json, config_hash
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            experiment.experiment_id,
            experiment.name,
            experiment.description,
            experiment.config_json,
            experiment.config_hash,
        ))
        self.conn.commit()

    def get_by_id(self, experiment_id: str) -> Experiment | None:
        """Get experiment by ID.

        Args:
            experiment_id: Primary key.

        Returns:
            Experiment dataclass or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT experiment_id, name, description, config_json, config_hash,
                   created_at
            FROM experiments
            WHERE experiment_id = ?
        """, (experiment_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_experiment(row)

    def get_by_name(self, name: str) -> Experiment | None:
        """Get experiment by name.

        Args:
            name: Human-readable unique name.

        Returns:
            Experiment dataclass or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT experiment_id, name, description, config_json, config_hash,
                   created_at
            FROM experiments
            WHERE name = ?
        """, (name,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_experiment(row)

    def list_all(self) -> list[Experiment]:
        """List all experiments.

        Returns:
            List of Experiment dataclasses.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT experiment_id, name, description, config_json, config_hash,
                   created_at
            FROM experiments
            ORDER BY created_at DESC
        """)
        return [self._row_to_experiment(row) for row in cursor.fetchall()]

    def delete(self, experiment_id: str) -> None:
        """Delete experiment by ID.

        Args:
            experiment_id: Primary key.

        Note:
            This is a hard delete. All related data (runs, responses, etc.)
            will be deleted via CASCADE.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM experiments WHERE experiment_id = ?
        """, (experiment_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_experiment(row: sqlite3.Row) -> Experiment:
        """Convert database row to Experiment dataclass."""
        return Experiment(
            experiment_id=row["experiment_id"],
            name=row["name"],
            description=row["description"],
            config_json=row["config_json"],
            config_hash=row["config_hash"],
            created_at=row["created_at"],
        )


# =============================================================================
# VariantRepository
# =============================================================================

class VariantRepository:
    """CRUD operations for model variants."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, variant: ModelVariant) -> None:
        """Insert or update variant.

        Does NOT pass created_at - let DB DEFAULT handle it.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO model_variants (
                variant_id, experiment_id, model_id, variant_signature, config
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            variant.variant_id,
            variant.experiment_id,
            variant.model_id,
            variant.variant_signature,
            variant.config,
        ))
        self.conn.commit()

    def get_by_id(self, variant_id: str) -> ModelVariant | None:
        """Get variant by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT variant_id, experiment_id, model_id, variant_signature,
                   config, created_at
            FROM model_variants
            WHERE variant_id = ?
        """, (variant_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_variant(row)

    def get_by_signature(self, experiment_id: str, signature: str) -> ModelVariant | None:
        """Get variant by signature within an experiment."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT variant_id, experiment_id, model_id, variant_signature,
                   config, created_at
            FROM model_variants
            WHERE experiment_id = ? AND variant_signature = ?
        """, (experiment_id, signature))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_variant(row)

    def list_by_experiment(self, experiment_id: str) -> list[ModelVariant]:
        """List variants for an experiment."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT variant_id, experiment_id, model_id, variant_signature,
                   config, created_at
            FROM model_variants
            WHERE experiment_id = ?
            ORDER BY created_at ASC
        """, (experiment_id,))
        return [self._row_to_variant(row) for row in cursor.fetchall()]

    def delete(self, variant_id: str) -> None:
        """Delete variant by ID.

        Args:
            variant_id: Primary key.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM model_variants WHERE variant_id = ?
        """, (variant_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_variant(row: sqlite3.Row) -> ModelVariant:
        """Convert database row to ModelVariant dataclass."""
        return ModelVariant(
            variant_id=row["variant_id"],
            experiment_id=row["experiment_id"],
            model_id=row["model_id"],
            variant_signature=row["variant_signature"],
            config=row["config"],
            created_at=row["created_at"],
        )


# =============================================================================
# SnapshotRepository
# =============================================================================

class SnapshotRepository:
    """CRUD operations for question snapshots."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, snapshot: QuestionSnapshot) -> None:
        """Insert or update snapshot.

        Does NOT pass created_at - let DB DEFAULT handle it.
        Uses json_question_id and question_position from new schema.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO question_snapshots (
                snapshot_id, experiment_id, json_question_id, question_position,
                question_payload
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            snapshot.snapshot_id,
            snapshot.experiment_id,
            snapshot.json_question_id,
            snapshot.question_position,
            snapshot.question_payload,
        ))
        self.conn.commit()

    def get_by_id(self, snapshot_id: str) -> QuestionSnapshot | None:
        """Get snapshot by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, experiment_id, json_question_id, question_position,
                   question_payload, created_at
            FROM question_snapshots
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    def get_by_experiment_and_question(self, experiment_id: str, json_question_id: str) -> QuestionSnapshot | None:
        """Get snapshot by experiment and question ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, experiment_id, json_question_id, question_position,
                   question_payload, created_at
            FROM question_snapshots
            WHERE experiment_id = ? AND json_question_id = ?
        """, (experiment_id, json_question_id))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    def list_by_experiment(self, experiment_id: str) -> list[QuestionSnapshot]:
        """List snapshots for an experiment."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, experiment_id, json_question_id, question_position,
                   question_payload, created_at
            FROM question_snapshots
            WHERE experiment_id = ?
            ORDER BY created_at ASC
        """, (experiment_id,))
        return [self._row_to_snapshot(row) for row in cursor.fetchall()]

    def delete(self, snapshot_id: str) -> None:
        """Delete snapshot by ID.

        Args:
            snapshot_id: Primary key.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM question_snapshots WHERE snapshot_id = ?
        """, (snapshot_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> QuestionSnapshot:
        """Convert database row to QuestionSnapshot dataclass."""
        return QuestionSnapshot(
            snapshot_id=row["snapshot_id"],
            experiment_id=row["experiment_id"],
            json_question_id=row["json_question_id"],
            question_position=row["question_position"],
            question_payload=row["question_payload"],
            created_at=row["created_at"],
        )


# =============================================================================
# RunRepository
# =============================================================================

class RunRepository:
    """CRUD operations for runs."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, run: Run, config: dict) -> None:
        """Insert or update run.

        Args:
            run: Run dataclass to save.
            config: Configuration dict (will be serialized to JSON).

        Notes:
            - Does NOT pass created_at - let DB DEFAULT handle it
            - Config dict is serialized to JSON string for storage
        """
        config_json = json.dumps(config)
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO runs (
                run_id, experiment_id, config, status, duration
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.experiment_id,
            config_json,
            run.status,
            run.duration,
        ))
        self.conn.commit()

    def get_by_id(self, run_id: str) -> Run | None:
        """Get run by ID.

        Args:
            run_id: Primary key.

        Returns:
            Run dataclass or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT run_id, experiment_id, config, status, duration, created_at
            FROM runs
            WHERE run_id = ?
        """, (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_by_experiment(self, experiment_id: str) -> list[Run]:
        """List runs for an experiment.

        Args:
            experiment_id: Parent experiment ID.

        Returns:
            List of Run dataclasses.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT run_id, experiment_id, config, status, duration, created_at
            FROM runs
            WHERE experiment_id = ?
            ORDER BY created_at ASC
        """, (experiment_id,))
        return [self._row_to_run(row) for row in cursor.fetchall()]

    def list_pending(self) -> list[Run]:
        """List all pending runs.

        Returns:
            List of Run dataclasses with status 'pending'.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT run_id, experiment_id, config, status, duration, created_at
            FROM runs
            WHERE status = 'pending'
            ORDER BY created_at ASC
        """)
        return [self._row_to_run(row) for row in cursor.fetchall()]

    def update_status(self, run_id: str, status: str) -> None:
        """Update run status.

        Args:
            run_id: Run primary key.
            status: New status value.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE runs SET status = ?
            WHERE run_id = ?
        """, (status, run_id))
        self.conn.commit()

    def delete(self, run_id: str) -> None:
        """Delete run by ID.

        Args:
            run_id: Primary key.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            DELETE FROM runs WHERE run_id = ?
        """, (run_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        """Convert database row to Run dataclass.

        Deserializes config JSON string to dict.
        """
        return Run(
            run_id=row["run_id"],
            experiment_id=row["experiment_id"],
            config=row["config"],
            status=row["status"],
            duration=row["duration"],
            created_at=row["created_at"],
        )


# =============================================================================
# ResponseRepository
# =============================================================================

class ResponseRepository:
    """CRUD operations for responses."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, response: Response) -> None:
        """Insert or update response.

        Calculates effective_tokens before save:
        effective_tokens = input_tokens + response_tokens + reasoning_tokens

        Does NOT pass created_at - let DB DEFAULT handle it.
        """
        effective_tokens = self._calculate_effective_tokens(
            response.input_tokens,
            response.response_tokens,
            response.reasoning_tokens,
        )

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO responses (
                response_id, run_id, variant_id, snapshot_id,
                model_id, question_id, status, finish_reason, error_details,
                response_text, selected_answer, is_correct, parse_confidence,
                review_status, manual_answer, raw_response, cost,
                input_tokens, response_tokens, reasoning_tokens, effective_tokens,
                latency_ms, started_at, finished_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id,
            response.run_id,
            response.variant_id,
            response.snapshot_id,
            response.model_id,
            response.question_id,
            response.status,
            response.finish_reason,
            response.error_details,
            response.response_text,
            response.selected_answer,
            response.is_correct,
            response.parse_confidence,
            response.review_status,
            response.manual_answer,
            response.raw_response,
            response.cost,
            response.input_tokens,
            response.response_tokens,
            response.reasoning_tokens,
            effective_tokens,
            response.latency_ms,
            response.started_at,
            response.finished_at,
        ))
        self.conn.commit()

    def get_by_id(self, response_id: str) -> Response | None:
        """Get response by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, status, finish_reason, error_details,
                   response_text, selected_answer, is_correct, parse_confidence,
                   review_status, manual_answer, raw_response, cost,
                   input_tokens, response_tokens, reasoning_tokens, effective_tokens,
                   latency_ms, started_at, finished_at
            FROM responses
            WHERE response_id = ?
        """, (response_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_response(row)

    def list_by_run(self, run_id: str) -> list[Response]:
        """List responses for a run."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, status, finish_reason, error_details,
                   response_text, selected_answer, is_correct, parse_confidence,
                   review_status, manual_answer, raw_response, cost,
                   input_tokens, response_tokens, reasoning_tokens, effective_tokens,
                   latency_ms, started_at, finished_at
            FROM responses
            WHERE run_id = ?
            ORDER BY started_at ASC
        """, (run_id,))
        return [self._row_to_response(row) for row in cursor.fetchall()]

    def list_needs_review(self) -> list[Response]:
        """List all responses that need review."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, status, finish_reason, error_details,
                   response_text, selected_answer, is_correct, parse_confidence,
                   review_status, manual_answer, raw_response, cost,
                   input_tokens, response_tokens, reasoning_tokens, effective_tokens,
                   latency_ms, started_at, finished_at
            FROM responses
            WHERE review_status = 'needs_review'
            ORDER BY started_at ASC
        """)
        return [self._row_to_response(row) for row in cursor.fetchall()]

    def update_manual_answer(self, response_id: str, manual_answer: str) -> None:
        """Update manual answer and set review_status to 'reviewed'."""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT snapshot_id FROM responses
            WHERE response_id = ?
        """, (response_id,))
        row = cursor.fetchone()
        if not row:
            return

        snapshot_id = row[0]

        cursor.execute("""
            SELECT question_payload FROM question_snapshots
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        snap_row = cursor.fetchone()
        if not snap_row:
            return

        payload = json.loads(snap_row[0])
        answer_key = payload.get('answer_key', '')

        is_correct = manual_answer.upper() == answer_key.upper() if answer_key else None

        cursor.execute("""
            UPDATE responses
            SET manual_answer = ?, is_correct = ?, review_status = 'reviewed'
            WHERE response_id = ?
        """, (manual_answer.upper(), is_correct, response_id))
        self.conn.commit()

    @staticmethod
    def _calculate_effective_tokens(
        input_tokens: int | None,
        response_tokens: int | None,
        reasoning_tokens: int | None,
    ) -> int | None:
        """Calculate effective_tokens as sum of all token types."""
        if input_tokens is None or response_tokens is None or reasoning_tokens is None:
            return None
        return input_tokens + response_tokens + reasoning_tokens

    @staticmethod
    def _row_to_response(row: sqlite3.Row) -> Response:
        """Convert database row to Response dataclass."""
        return Response(
            response_id=row["response_id"],
            run_id=row["run_id"],
            variant_id=row["variant_id"],
            snapshot_id=row["snapshot_id"],
            model_id=row["model_id"],
            question_id=row["question_id"],
            status=row["status"],
            finish_reason=row["finish_reason"],
            error_details=row["error_details"],
            response_text=row["response_text"],
            selected_answer=row["selected_answer"],
            is_correct=bool(row["is_correct"]) if row["is_correct"] is not None else None,
            parse_confidence=row["parse_confidence"],
            review_status=row["review_status"],
            manual_answer=row["manual_answer"],
            raw_response=row["raw_response"],
            cost=row["cost"],
            input_tokens=row["input_tokens"],
            response_tokens=row["response_tokens"],
            reasoning_tokens=row["reasoning_tokens"],
            effective_tokens=row["effective_tokens"],
            latency_ms=row["latency_ms"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )


# =============================================================================
# ErrorRepository
# =============================================================================

class ErrorRepository:
    """CRUD operations for errors."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, error: Error) -> None:
        """Insert or update error.

        Does NOT pass occurred_at - let DB DEFAULT handle it.
        Uses variant_id (not model_id).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO errors (
                error_id, run_id, variant_id, snapshot_id,
                question_id, error_type, error_message,
                attempt_count, stack_trace
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            error.error_id,
            error.run_id,
            error.variant_id,
            error.snapshot_id,
            error.question_id,
            error.error_type,
            error.error_message,
            error.attempt_count,
            error.stack_trace,
        ))
        self.conn.commit()

    def get_by_id(self, error_id: str) -> Error | None:
        """Get error by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT error_id, run_id, variant_id, snapshot_id,
                   question_id, error_type, error_message,
                   attempt_count, stack_trace, occurred_at
            FROM errors
            WHERE error_id = ?
        """, (error_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_error(row)

    def list_by_run(self, run_id: str) -> list[Error]:
        """List errors for a run."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT error_id, run_id, variant_id, snapshot_id,
                   question_id, error_type, error_message,
                   attempt_count, stack_trace, occurred_at
            FROM errors
            WHERE run_id = ?
            ORDER BY occurred_at ASC
        """, (run_id,))
        return [self._row_to_error(row) for row in cursor.fetchall()]

    @staticmethod
    def _row_to_error(row: sqlite3.Row) -> Error:
        """Convert database row to Error dataclass."""
        return Error(
            error_id=row["error_id"],
            run_id=row["run_id"],
            variant_id=row["variant_id"],
            snapshot_id=row["snapshot_id"],
            question_id=row["question_id"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            attempt_count=row["attempt_count"],
            stack_trace=row["stack_trace"],
            occurred_at=row["occurred_at"],
        )
