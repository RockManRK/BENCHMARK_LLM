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
- Supports soft delete via deactivate()
- Uses dataclasses for type-safe I/O
"""

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

        Args:
            experiment: Experiment dataclass to save.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO experiments (
                experiment_id, name, description, config_json, config_hash,
                system_prompt, user_prompt, created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experiment.experiment_id,
            experiment.name,
            experiment.description,
            experiment.config_json,
            experiment.config_hash,
            experiment.system_prompt,
            experiment.user_prompt,
            experiment.created_at,
            experiment.is_active,
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
                   system_prompt, user_prompt, created_at, is_active
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
                   system_prompt, user_prompt, created_at, is_active
            FROM experiments
            WHERE name = ?
        """, (name,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_experiment(row)

    def list_all(self, active_only: bool = True) -> list[Experiment]:
        """List all experiments.

        Args:
            active_only: If True, only return active experiments.

        Returns:
            List of Experiment dataclasses.
        """
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("""
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt, created_at, is_active
                FROM experiments
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """)
        else:
            cursor.execute("""
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt, created_at, is_active
                FROM experiments
                ORDER BY created_at DESC
            """)
        return [self._row_to_experiment(row) for row in cursor.fetchall()]

    def deactivate(self, experiment_id: str) -> None:
        """Soft delete: set is_active = FALSE.

        Args:
            experiment_id: Primary key.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE experiments SET is_active = FALSE
            WHERE experiment_id = ?
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
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
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
        """Insert or update variant."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO model_variants (
                variant_id, experiment_id, model_id, variant_signature,
                reasoning_mode, reasoning_effort, max_output_tokens,
                vision_enabled, structured_output, web_access_enabled,
                created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            variant.variant_id,
            variant.experiment_id,
            variant.model_id,
            variant.variant_signature,
            variant.reasoning_mode,
            variant.reasoning_effort,
            variant.max_output_tokens,
            1 if variant.vision_enabled else 0,
            1 if variant.structured_output else 0,
            1 if variant.web_access_enabled else 0,
            variant.created_at,
            1 if variant.is_active else 0,
        ))
        self.conn.commit()

    def get_by_id(self, variant_id: str) -> ModelVariant | None:
        """Get variant by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT variant_id, experiment_id, model_id, variant_signature,
                   reasoning_mode, reasoning_effort, max_output_tokens,
                   vision_enabled, structured_output, web_access_enabled,
                   created_at, is_active
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
                   reasoning_mode, reasoning_effort, max_output_tokens,
                   vision_enabled, structured_output, web_access_enabled,
                   created_at, is_active
            FROM model_variants
            WHERE experiment_id = ? AND variant_signature = ?
        """, (experiment_id, signature))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_variant(row)

    def list_by_experiment(self, experiment_id: str, active_only: bool = True) -> list[ModelVariant]:
        """List variants for an experiment."""
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("""
                SELECT variant_id, experiment_id, model_id, variant_signature,
                       reasoning_mode, reasoning_effort, max_output_tokens,
                       vision_enabled, structured_output, web_access_enabled,
                       created_at, is_active
                FROM model_variants
                WHERE experiment_id = ? AND is_active = TRUE
                ORDER BY created_at ASC
            """, (experiment_id,))
        else:
            cursor.execute("""
                SELECT variant_id, experiment_id, model_id, variant_signature,
                       reasoning_mode, reasoning_effort, max_output_tokens,
                       vision_enabled, structured_output, web_access_enabled,
                       created_at, is_active
                FROM model_variants
                WHERE experiment_id = ?
                ORDER BY created_at ASC
            """, (experiment_id,))
        return [self._row_to_variant(row) for row in cursor.fetchall()]

    def deactivate(self, variant_id: str) -> None:
        """Soft delete: set is_active = FALSE."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE model_variants SET is_active = FALSE
            WHERE variant_id = ?
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
            reasoning_mode=row["reasoning_mode"],
            reasoning_effort=row["reasoning_effort"],
            max_output_tokens=row["max_output_tokens"],
            vision_enabled=bool(row["vision_enabled"]),
            structured_output=bool(row["structured_output"]),
            web_access_enabled=bool(row["web_access_enabled"]),
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
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
        """Insert or update snapshot."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO question_snapshots (
                snapshot_id, experiment_id, question_id, question_payload,
                created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            snapshot.snapshot_id,
            snapshot.experiment_id,
            snapshot.question_id,
            snapshot.question_payload,
            snapshot.created_at,
            1 if snapshot.is_active else 0,
        ))
        self.conn.commit()

    def get_by_id(self, snapshot_id: str) -> QuestionSnapshot | None:
        """Get snapshot by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, experiment_id, question_id, question_payload,
                   created_at, is_active
            FROM question_snapshots
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    def get_by_experiment_and_question(self, experiment_id: str, question_id: str) -> QuestionSnapshot | None:
        """Get snapshot by experiment and question ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT snapshot_id, experiment_id, question_id, question_payload,
                   created_at, is_active
            FROM question_snapshots
            WHERE experiment_id = ? AND question_id = ?
        """, (experiment_id, question_id))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_snapshot(row)

    def list_by_experiment(self, experiment_id: str, active_only: bool = True) -> list[QuestionSnapshot]:
        """List snapshots for an experiment."""
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("""
                SELECT snapshot_id, experiment_id, question_id, question_payload,
                       created_at, is_active
                FROM question_snapshots
                WHERE experiment_id = ? AND is_active = TRUE
                ORDER BY created_at ASC
            """, (experiment_id,))
        else:
            cursor.execute("""
                SELECT snapshot_id, experiment_id, question_id, question_payload,
                       created_at, is_active
                FROM question_snapshots
                WHERE experiment_id = ?
                ORDER BY created_at ASC
            """, (experiment_id,))
        return [self._row_to_snapshot(row) for row in cursor.fetchall()]

    def deactivate(self, snapshot_id: str) -> None:
        """Soft delete: set is_active = FALSE."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE question_snapshots SET is_active = FALSE
            WHERE snapshot_id = ?
        """, (snapshot_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> QuestionSnapshot:
        """Convert database row to QuestionSnapshot dataclass."""
        return QuestionSnapshot(
            snapshot_id=row["snapshot_id"],
            experiment_id=row["experiment_id"],
            question_id=row["question_id"],
            question_payload=row["question_payload"],
            created_at=row["created_at"],
            is_active=bool(row["is_active"]),
        )


# =============================================================================
# RunRepository
# =============================================================================

class RunRepository:
    """CRUD operations for runs."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize with database connection."""
        self.conn = conn

    def save(self, run: Run, system_prompt: str = "", user_prompt: str = "") -> None:
        """Insert or update run.

        Args:
            run: Run dataclass to save.
            system_prompt: System prompt for this run (inherits from experiment if empty).
            user_prompt: User prompt for this run (inherits from experiment if empty).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO runs (
                run_id, experiment_id, seed, system_prompt, user_prompt,
                status, started_at, finished_at, created_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run.run_id,
            run.experiment_id,
            run.seed,
            system_prompt,
            user_prompt,
            run.status,
            run.started_at,
            run.finished_at,
            run.created_at,
            True,
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
            SELECT run_id, experiment_id, seed, status, started_at,
                   finished_at, created_at
            FROM runs
            WHERE run_id = ?
        """, (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def get_by_id_with_prompts(self, run_id: str) -> dict | None:
        """Get run by ID with prompt fields.

        Args:
            run_id: Primary key.

        Returns:
            Dictionary with run data including prompts, or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT run_id, experiment_id, seed, system_prompt, user_prompt,
                   status, started_at, finished_at, created_at, is_active
            FROM runs
            WHERE run_id = ?
        """, (run_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "run_id": row["run_id"],
            "experiment_id": row["experiment_id"],
            "seed": row["seed"],
            "system_prompt": row["system_prompt"],
            "user_prompt": row["user_prompt"],
            "status": row["status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "created_at": row["created_at"],
            "is_active": bool(row["is_active"]),
        }

    def list_by_experiment(self, experiment_id: str, active_only: bool = True) -> list[Run]:
        """List runs for an experiment.

        Args:
            experiment_id: Parent experiment ID.
            active_only: If True, only return active runs.

        Returns:
            List of Run dataclasses.
        """
        cursor = self.conn.cursor()
        if active_only:
            cursor.execute("""
                SELECT run_id, experiment_id, seed, status, started_at,
                       finished_at, created_at
                FROM runs
                WHERE experiment_id = ? AND is_active = TRUE
                ORDER BY created_at ASC
            """, (experiment_id,))
        else:
            cursor.execute("""
                SELECT run_id, experiment_id, seed, status, started_at,
                       finished_at, created_at
                FROM runs
                WHERE experiment_id = ?
                ORDER BY created_at ASC
            """, (experiment_id,))
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

    def deactivate(self, run_id: str) -> None:
        """Soft delete: set is_active = FALSE.

        Args:
            run_id: Primary key.

        Notes:
            - Does not delete historical response/error data
            - Prevents future execution of this run
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE runs SET is_active = FALSE
            WHERE run_id = ?
        """, (run_id,))
        self.conn.commit()

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        """Convert database row to Run dataclass."""
        return Run(
            run_id=row["run_id"],
            experiment_id=row["experiment_id"],
            seed=row["seed"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
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

        Calculates needs_review if not explicitly set:
        - needs_review = True if parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
        - needs_review = True if selected_answer is None
        - needs_review = False otherwise
        """
        needs_review = response.needs_review
        if not needs_review:
            needs_review = self._calculate_needs_review(
                response.parse_confidence,
                response.selected_answer,
            )

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO responses (
                response_id, run_id, variant_id, snapshot_id,
                model_id, question_id, response_text, selected_answer,
                is_correct, parse_confidence, needs_review, manual_answer,
                latency_ms, input_tokens, output_tokens, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            response.response_id,
            response.run_id,
            response.variant_id,
            response.snapshot_id,
            response.model_id,
            response.question_id,
            response.response_text,
            response.selected_answer,
            response.is_correct,
            response.parse_confidence,
            needs_review,
            response.manual_answer,
            response.latency_ms,
            response.input_tokens,
            response.output_tokens,
            response.created_at,
        ))
        self.conn.commit()

    def get_by_id(self, response_id: str) -> Response | None:
        """Get response by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, response_text, selected_answer,
                   is_correct, parse_confidence, needs_review, manual_answer,
                   latency_ms, input_tokens, output_tokens, created_at
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
                   model_id, question_id, response_text, selected_answer,
                   is_correct, parse_confidence, needs_review, manual_answer,
                   latency_ms, input_tokens, output_tokens, created_at
            FROM responses
            WHERE run_id = ?
            ORDER BY created_at ASC
        """, (run_id,))
        return [self._row_to_response(row) for row in cursor.fetchall()]

    def list_needs_review(self) -> list[Response]:
        """List all responses that need review."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT response_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, response_text, selected_answer,
                   is_correct, parse_confidence, needs_review, manual_answer,
                   latency_ms, input_tokens, output_tokens, created_at
            FROM responses
            WHERE needs_review = TRUE
            ORDER BY created_at ASC
        """)
        return [self._row_to_response(row) for row in cursor.fetchall()]

    def update_manual_answer(self, response_id: str, manual_answer: str) -> None:
        """Update manual answer and recalculate is_correct."""
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

        import json
        payload = json.loads(snap_row[0])
        answer_key = payload.get('answer_key', '')

        is_correct = manual_answer.upper() == answer_key.upper() if answer_key else None

        cursor.execute("""
            UPDATE responses
            SET manual_answer = ?, is_correct = ?
            WHERE response_id = ?
        """, (manual_answer.upper(), is_correct, response_id))
        self.conn.commit()

    @staticmethod
    def _calculate_needs_review(parse_confidence: str | None, selected_answer: str | None) -> bool:
        """Calculate needs_review flag."""
        if selected_answer is None:
            return True
        if parse_confidence in ('ambiguous', 'no_answer', 'low_confidence', 'unknown'):
            return True
        return False

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
            response_text=row["response_text"],
            selected_answer=row["selected_answer"],
            is_correct=bool(row["is_correct"]) if row["is_correct"] is not None else None,
            parse_confidence=row["parse_confidence"],
            needs_review=bool(row["needs_review"]),
            manual_answer=row["manual_answer"],
            latency_ms=row["latency_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            created_at=row["created_at"],
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
        """Insert or update error."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO errors (
                error_id, run_id, variant_id, snapshot_id,
                model_id, question_id, error_type, error_message,
                attempt_count, stack_trace, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            error.error_id,
            error.run_id,
            error.variant_id,
            error.snapshot_id,
            error.model_id,
            error.question_id,
            error.error_type,
            error.error_message,
            error.attempt_count,
            error.stack_trace,
            error.created_at,
        ))
        self.conn.commit()

    def get_by_id(self, error_id: str) -> Error | None:
        """Get error by ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT error_id, run_id, variant_id, snapshot_id,
                   model_id, question_id, error_type, error_message,
                   attempt_count, stack_trace, created_at
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
                   model_id, question_id, error_type, error_message,
                   attempt_count, stack_trace, created_at
            FROM errors
            WHERE run_id = ?
            ORDER BY created_at ASC
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
            model_id=row["model_id"],
            question_id=row["question_id"],
            error_type=row["error_type"],
            error_message=row["error_message"],
            attempt_count=row["attempt_count"],
            stack_trace=row["stack_trace"],
            created_at=row["created_at"],
        )
