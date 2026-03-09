"""Repository module for database CRUD operations.

This module provides repository classes for each entity in the database,
encapsulating all data access logic and providing a clean API for
database operations.

Modules:
    - ExperimentRepository: Experiment tracking
    - RunRepository: Run management
    - ModelRepository: Model registry
    - QuestionRepository: Question persistence
    - ResponseRepository: Response storage
    - ErrorRepository: Error tracking
"""

import json
import logging
import sqlite3

logger = logging.getLogger(__name__)
from datetime import datetime
from typing import Optional

from src.db.models import Error, Experiment, Model, Question, QuestionSnapshot, Response, Run
from src.db.schema import DatabaseManager


class ExperimentRepository:
    """Repository for Experiment entity CRUD operations.

    Experiments store frozen configurations for reproducible research.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ExperimentRepository.

        Args:
            db_manager: DatabaseManager instance for database connections.
        """
        self.db_manager = db_manager

    def create(self, experiment: Experiment) -> Experiment:
        """Create a new experiment record.

        Args:
            experiment: Experiment object to create.

        Returns:
            The created Experiment object with database-generated experiment_id.
        """
        conn = self.db_manager.get_connection()
        try:
            import uuid
            if experiment.experiment_id is None:
                experiment.experiment_id = f"exp-{uuid.uuid4().hex[:8]}"
                
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO experiments (
                    experiment_id, name, description, config_json, config_hash,
                    system_prompt, user_prompt_template
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment.experiment_id,
                    experiment.name,
                    experiment.description,
                    experiment.config_json,
                    experiment.config_hash,
                    experiment.system_prompt,
                    experiment.user_prompt_template,
                ),
            )
            conn.commit()
            conn.commit()
            return experiment
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, experiment_id: str) -> Optional[Experiment]:
        """Retrieve an experiment by its ID.

        Args:
            experiment_id: The unique identifier of the experiment.

        Returns:
            Experiment object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt_template, created_at
                FROM experiments WHERE experiment_id = ?
                """,
                (experiment_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Experiment(
                experiment_id=row["experiment_id"],
                name=row["name"],
                description=row["description"],
                config_json=row["config_json"],
                config_hash=row["config_hash"],
                system_prompt=row["system_prompt"],
                user_prompt_template=row["user_prompt_template"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_name(self, name: str) -> Optional[Experiment]:
        """Retrieve an experiment by its name.

        Args:
            name: The experiment name.

        Returns:
            Experiment object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt_template, created_at
                FROM experiments WHERE name = ?
                """,
                (name,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Experiment(
                experiment_id=row["experiment_id"],
                name=row["name"],
                description=row["description"],
                config_json=row["config_json"],
                config_hash=row["config_hash"],
                system_prompt=row["system_prompt"],
                user_prompt_template=row["user_prompt_template"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_hash(self, config_hash: str) -> Optional[Experiment]:
        """Retrieve an experiment by its configuration hash.

        Args:
            config_hash: The configuration hash.

        Returns:
            Experiment object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt_template, created_at
                FROM experiments WHERE config_hash = ?
                """,
                (config_hash,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Experiment(
                experiment_id=row["experiment_id"],
                name=row["name"],
                description=row["description"],
                config_json=row["config_json"],
                config_hash=row["config_hash"],
                system_prompt=row["system_prompt"],
                user_prompt_template=row["user_prompt_template"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Experiment]:
        """Retrieve all experiments.

        Returns:
            List of all Experiment objects.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT experiment_id, name, description, config_json, config_hash,
                       system_prompt, user_prompt_template, created_at
                FROM experiments ORDER BY created_at DESC
                """
            )
            experiments = []
            for row in cursor.fetchall():
                experiments.append(
                    Experiment(
                        experiment_id=row["experiment_id"],
                        name=row["name"],
                        description=row["description"],
                        config_json=row["config_json"],
                        config_hash=row["config_hash"],
                        system_prompt=row["system_prompt"],
                        user_prompt_template=row["user_prompt_template"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return experiments
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, experiment_id: str) -> bool:
        """Delete an experiment record.

        Args:
            experiment_id: The unique identifier of the experiment.

        Returns:
            True if deleted successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM experiments WHERE experiment_id = ?", (experiment_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class RunRepository:
    """Repository for Run entity CRUD operations.

    Runs track individual benchmark executions.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the RunRepository."""
        self.db_manager = db_manager

    def create(self, run: Run) -> Run:
        """Create a new run record.

        Args:
            run: Run object to create.

        Returns:
            The created Run object.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO runs (run_id, experiment_id, seed, is_dev, started_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.experiment_id,
                    run.seed,
                    1 if run.is_dev else 0,
                    run.started_at.isoformat(),
                    run.status,
                ),
            )
            conn.commit()
            return run
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Retrieve a run by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, experiment_id, seed, is_dev, started_at, finished_at, status
                FROM runs WHERE run_id = ?
                """,
                (run_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Run(
                run_id=row["run_id"],
                experiment_id=row["experiment_id"],
                seed=row["seed"],
                is_dev=bool(row["is_dev"]),
                started_at=datetime.fromisoformat(row["started_at"]),
                finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                status=row["status"],
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_experiment(self, experiment_id: str) -> list[Run]:
        """Retrieve all runs for an experiment."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, experiment_id, seed, is_dev, started_at, finished_at, status
                FROM runs WHERE experiment_id = ? ORDER BY started_at DESC
                """,
                (experiment_id,),
            )
            runs = []
            for row in cursor.fetchall():
                runs.append(
                    Run(
                        run_id=row["run_id"],
                        experiment_id=row["experiment_id"],
                        seed=row["seed"],
                        is_dev=bool(row["is_dev"]),
                        started_at=datetime.fromisoformat(row["started_at"]),
                        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                        status=row["status"],
                    )
                )
            return runs
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Run]:
        """Retrieve all runs."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, experiment_id, seed, is_dev, started_at, finished_at, status
                FROM runs ORDER BY started_at DESC
                """
            )
            runs = []
            for row in cursor.fetchall():
                runs.append(
                    Run(
                        run_id=row["run_id"],
                        experiment_id=row["experiment_id"],
                        seed=row["seed"],
                        is_dev=bool(row["is_dev"]),
                        started_at=datetime.fromisoformat(row["started_at"]),
                        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                        status=row["status"],
                    )
                )
            return runs
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def update(self, run: Run) -> Optional[Run]:
        """Update an existing run record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE runs SET
                    experiment_id = ?, seed = ?, is_dev = ?,
                    started_at = ?, finished_at = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    run.experiment_id,
                    run.seed,
                    1 if run.is_dev else 0,
                    run.started_at.isoformat(),
                    run.finished_at.isoformat() if run.finished_at else None,
                    run.status,
                    run.run_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return run
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, run_id: str) -> bool:
        """Delete a run record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class ModelRepository:
    """Repository for Model entity CRUD operations.

    Models registry stores information about LLMs being benchmarked.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ModelRepository."""
        self.db_manager = db_manager

    def create(self, model: Model) -> Model:
        """Create a new model record.

        Args:
            model: Model object to create.

        Returns:
            The created Model object.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO models (model_id, provider, model_name, supports_multimodal, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    model.model_id,
                    model.provider,
                    model.model_name,
                    1 if model.supports_multimodal else 0,
                    model.metadata_json,
                ),
            )
            conn.commit()
            return model
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, model_id: str) -> Optional[Model]:
        """Retrieve a model by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, provider, model_name, supports_multimodal, metadata_json, created_at
                FROM models WHERE model_id = ?
                """,
                (model_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Model(
                model_id=row["model_id"],
                provider=row["provider"],
                model_name=row["model_name"],
                supports_multimodal=bool(row["supports_multimodal"]),
                metadata_json=row["metadata_json"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Model]:
        """Retrieve all models."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT model_id, provider, model_name, supports_multimodal, metadata_json, created_at
                FROM models ORDER BY model_name
                """
            )
            models = []
            for row in cursor.fetchall():
                models.append(
                    Model(
                        model_id=row["model_id"],
                        provider=row["provider"],
                        model_name=row["model_name"],
                        supports_multimodal=bool(row["supports_multimodal"]),
                        metadata_json=row["metadata_json"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return models
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, model_id: str) -> bool:
        """Delete a model record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM models WHERE model_id = ?", (model_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class QuestionRepository:
    """Repository for Question entity CRUD operations.

    Questions are loaded from external files and persisted for reproducibility.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the QuestionRepository."""
        self.db_manager = db_manager

    def create(self, question: Question) -> Question:
        """Create a new question record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO questions (question_id, stem, options_json, correct_answer, has_image, image_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.question_id,
                    question.stem,
                    question.options_json,
                    question.correct_answer,
                    1 if question.has_image else 0,
                    question.image_path,
                    question.status,
                ),
            )
            conn.commit()
            return question
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, question_id: str) -> Optional[Question]:
        """Retrieve a question by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT question_id, stem, options_json, correct_answer, has_image, image_path, status
                FROM questions WHERE question_id = ?
                """,
                (question_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Question(
                question_id=row["question_id"],
                stem=row["stem"],
                options_json=row["options_json"],
                correct_answer=row["correct_answer"],
                has_image=bool(row["has_image"]),
                image_path=row["image_path"],
                status=row["status"],
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[Question]:
        """Retrieve all questions."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT question_id, stem, options_json, correct_answer, has_image, image_path, status
                FROM questions ORDER BY question_id
                """
            )
            questions = []
            for row in cursor.fetchall():
                questions.append(
                    Question(
                        question_id=row["question_id"],
                        stem=row["stem"],
                        options_json=row["options_json"],
                        correct_answer=row["correct_answer"],
                        has_image=bool(row["has_image"]),
                        image_path=row["image_path"],
                        status=row["status"],
                    )
                )
            return questions
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_active(self) -> list[Question]:
        """Retrieve all active questions."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT question_id, stem, options_json, correct_answer, has_image, image_path, status
                FROM questions WHERE status = 'active' ORDER BY question_id
                """
            )
            questions = []
            for row in cursor.fetchall():
                questions.append(
                    Question(
                        question_id=row["question_id"],
                        stem=row["stem"],
                        options_json=row["options_json"],
                        correct_answer=row["correct_answer"],
                        has_image=bool(row["has_image"]),
                        image_path=row["image_path"],
                        status=row["status"],
                    )
                )
            return questions
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, question_id: str) -> bool:
        """Delete a question record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM questions WHERE question_id = ?", (question_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class QuestionSnapshotRepository:
    """Repository for QuestionSnapshot entity CRUD operations.

    QuestionSnapshots store immutable copies of questions used in experiments.
    Each snapshot captures the complete question JSON at the moment it was
    first used, ensuring reproducibility even if the canonical question changes.

    Snapshots are created only once per (experiment_id, question_id) pair.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the QuestionSnapshotRepository."""
        self.db_manager = db_manager

    def create_if_not_exists(
        self, experiment_id: str, question_id: str, question_json: str
    ) -> int:
        """Create a snapshot if it doesn't exist, return snapshot_id.

        This is the primary method for ensuring snapshot immutability.
        If a snapshot already exists for the given (experiment_id, question_id)
        pair, returns the existing snapshot_id without creating a duplicate.

        IMPORTANT: experiment_id is ALWAYS required. There is NO support for
        experiment_id = NULL. Every snapshot must belong to a valid experiment.

        Args:
            experiment_id: ID of the experiment (ALWAYS required, never None).
            question_id: ID of the question to snapshot.
            question_json: Complete JSON representation of the question.

        Returns:
            The snapshot_id (either newly created or existing).

        Raises:
            ValueError: If experiment_id is None or empty.

        Example:
            >>> repo = QuestionSnapshotRepository(db_manager)
            >>> snapshot_id = repo.create_if_not_exists(
            ...     experiment_id="exp-001",
            ...     question_id="Q001",
            ...     question_json='{"id": "Q001", "stem": "What is 2+2?"}'
            ... )
            >>> print(snapshot_id)
            1
        """
        if not experiment_id:
            raise ValueError("experiment_id is required and cannot be None or empty")

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()

            # Check if snapshot already exists for this (experiment_id, question_id)
            existing = cursor.execute(
                """
                SELECT snapshot_id FROM question_snapshots
                WHERE experiment_id = ? AND question_id = ?
                """,
                (experiment_id, question_id),
            ).fetchone()

            if existing is not None:
                logger.debug(
                    f"Snapshot already exists for experiment={experiment_id}, question={question_id} (ID={existing['snapshot_id']})"
                )
                return existing["snapshot_id"]

            # Create new snapshot
            cursor.execute(
                """
                INSERT INTO question_snapshots (experiment_id, question_id, question_json)
                VALUES (?, ?, ?)
                """,
                (experiment_id, question_id, question_json),
            )
            conn.commit()
            snapshot_id = cursor.lastrowid
            logger.info(
                f"Created snapshot {snapshot_id} for experiment={experiment_id}, question={question_id}"
            )
            return snapshot_id

        except sqlite3.Error as e:
            logger.error(f"Failed to create snapshot: {e}")
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, snapshot_id: int) -> Optional[QuestionSnapshot]:
        """Retrieve a snapshot by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT snapshot_id, experiment_id, question_id, question_json, created_at
                FROM question_snapshots WHERE snapshot_id = ?
                """,
                (snapshot_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return QuestionSnapshot(
                snapshot_id=row["snapshot_id"],
                experiment_id=row["experiment_id"],
                question_id=row["question_id"],
                question_json=row["question_json"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_experiment(self, experiment_id: str) -> list[QuestionSnapshot]:
        """Retrieve all snapshots for an experiment."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT snapshot_id, experiment_id, question_id, question_json, created_at
                FROM question_snapshots WHERE experiment_id = ?
                ORDER BY question_id
                """,
                (experiment_id,),
            )
            snapshots = []
            for row in cursor.fetchall():
                snapshots.append(
                    QuestionSnapshot(
                        snapshot_id=row["snapshot_id"],
                        experiment_id=row["experiment_id"],
                        question_id=row["question_id"],
                        question_json=row["question_json"],
                        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    )
                )
            return snapshots
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_question(self, question_id: str) -> list[QuestionSnapshot]:
        """Retrieve all snapshots for a question (across experiments)."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT snapshot_id, experiment_id, question_id, question_json, created_at
                FROM question_snapshots WHERE question_id = ?
                ORDER BY experiment_id, created_at
                """,
                (question_id,),
            )
            snapshots = []
            for row in cursor.fetchall():
                snapshots.append(
                    QuestionSnapshot(
                        snapshot_id=row["snapshot_id"],
                        experiment_id=row["experiment_id"],
                        question_id=row["question_id"],
                        question_json=row["question_json"],
                        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    )
                )
            return snapshots
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def validate_snapshot_integrity(self, snapshot_id: int) -> tuple[bool, str]:
        """Validate that snapshot JSON matches question_id.

        This method ensures data integrity by verifying that the question_id
        stored in the snapshot metadata matches the 'id' field inside the
        question_json.

        Args:
            snapshot_id: ID of the snapshot to validate.

        Returns:
            Tuple of (is_valid, error_message).
            If valid: (True, "")
            If invalid: (False, "error description")

        Example:
            >>> repo = QuestionSnapshotRepository(db_manager)
            >>> is_valid, error = repo.validate_snapshot_integrity(1)
            >>> if not is_valid:
            ...     print(f"Snapshot integrity check failed: {error}")
        """
        snapshot = self.get_by_id(snapshot_id)
        if not snapshot:
            return False, "Snapshot not found"

        try:
            import json
            question_data = json.loads(snapshot.question_json)
            if question_data.get("id") != snapshot.question_id:
                return (
                    False,
                    f"Question ID mismatch: snapshot.question_id={snapshot.question_id}, "
                    f"json.id={question_data.get('id')}",
                )
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in question_json: {e}"
        except Exception as e:
            return False, f"Unexpected error validating snapshot: {e}"


class ResponseRepository:
    """Repository for Response entity CRUD operations.

    Responses store model answers to questions with all metrics.
    Responses reference question_snapshots (not questions directly) to
    ensure immutability and reproducibility of experiment results.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ResponseRepository."""
        self.db_manager = db_manager

    def create(self, response: Response) -> Response:
        """Create a new response record.

        Args:
            response: Response object to create.

        Returns:
            The created Response object with database-generated response_id.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            logger.info(
                f"Saving response: run_id={response.run_id}, snapshot_id={response.snapshot_id}, "
                f"question_id={response.question_id}, model_id={response.model_id}"
            )
            cursor.execute(
                """
                INSERT INTO responses (
                    run_id, snapshot_id, question_id, model_id, iteration,
                    selected_answer, response_text, is_correct,
                    status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.run_id,
                    response.snapshot_id,
                    response.question_id,
                    response.model_id,
                    response.iteration,
                    response.selected_answer,
                    response.response_text,
                    response.is_correct,
                    response.status,
                    response.latency_ms,
                    response.input_tokens,
                    response.output_tokens,
                    response.total_tokens,
                    response.reasoning_tokens,
                    response.cost,
                    response.raw_response_json,
                ),
            )
            conn.commit()
            response.response_id = cursor.lastrowid
            logger.info(f"Response saved with ID {response.response_id}")
            return response
        except sqlite3.Error as e:
            logger.error(f"Failed to save response: {e}")
            logger.error(
                f"Response data: run_id={response.run_id}, snapshot_id={response.snapshot_id}, "
                f"question_id={response.question_id}, model_id={response.model_id}"
            )
            # Check which FK is failing
            run_exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (response.run_id,)).fetchone() is not None
            snapshot_exists = conn.execute("SELECT 1 FROM question_snapshots WHERE snapshot_id = ?", (response.snapshot_id,)).fetchone() is not None
            question_exists = conn.execute("SELECT 1 FROM questions WHERE question_id = ?", (response.question_id,)).fetchone() is not None
            model_exists = conn.execute("SELECT 1 FROM models WHERE model_id = ?", (response.model_id,)).fetchone() is not None
            logger.error(
                f"FK check: run_exists={run_exists}, snapshot_exists={snapshot_exists}, "
                f"question_exists={question_exists}, model_exists={model_exists}"
            )
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, response_id: int) -> Optional[Response]:
        """Retrieve a response by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, question_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE response_id = ?
                """,
                (response_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Response(
                response_id=row["response_id"],
                run_id=row["run_id"],
                snapshot_id=row["snapshot_id"],
                question_id=row["question_id"],
                model_id=row["model_id"],
                iteration=row["iteration"],
                selected_answer=row["selected_answer"],
                response_text=row["response_text"],
                is_correct=row["is_correct"],
                status=row["status"],
                latency_ms=row["latency_ms"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                total_tokens=row["total_tokens"],
                reasoning_tokens=row["reasoning_tokens"],
                cost=row["cost"],
                raw_response_json=row["raw_response_json"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run(self, run_id: str) -> list[Response]:
        """Retrieve all responses for a run."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, question_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE run_id = ? ORDER BY iteration, question_id
                """,
                (run_id,),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        run_id=row["run_id"],
                        snapshot_id=row["snapshot_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return responses
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_model(self, model_id: str) -> list[Response]:
        """Retrieve all responses for a model."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, question_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE model_id = ? ORDER BY run_id, iteration, question_id
                """,
                (model_id,),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        run_id=row["run_id"],
                        snapshot_id=row["snapshot_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return responses
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run_and_model(self, run_id: str, model_id: str) -> list[Response]:
        """Retrieve all responses for a run and model combination."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, question_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE run_id = ? AND model_id = ? ORDER BY iteration, question_id
                """,
                (run_id, model_id),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        run_id=row["run_id"],
                        snapshot_id=row["snapshot_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return responses
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_model(self, model_id: str) -> list[Response]:
        """Retrieve all responses for a model."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE model_id = ? ORDER BY run_id, iteration, snapshot_id
                """,
                (model_id,),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        run_id=row["run_id"],
                        snapshot_id=row["snapshot_id"],
                        model_id=row["model_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return responses
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run_and_model(self, run_id: str, model_id: str) -> list[Response]:
        """Retrieve all responses for a run and model combination."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response_id, run_id, snapshot_id, model_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, latency_ms, input_tokens, output_tokens, total_tokens, reasoning_tokens, cost, raw_response_json, timestamp
                FROM responses WHERE run_id = ? AND model_id = ? ORDER BY iteration, snapshot_id
                """,
                (run_id, model_id),
            )
            responses = []
            for row in cursor.fetchall():
                responses.append(
                    Response(
                        response_id=row["response_id"],
                        run_id=row["run_id"],
                        snapshot_id=row["snapshot_id"],
                        model_id=row["model_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        output_tokens=row["output_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return responses
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def update(self, response: Response) -> Optional[Response]:
        """Update an existing response record."""
        if response.response_id is None:
            return None

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE responses SET
                    run_id = ?, snapshot_id = ?, question_id = ?, model_id = ?, iteration = ?,
                    selected_answer = ?, response_text = ?, is_correct = ?,
                    status = ?, latency_ms = ?, input_tokens = ?, output_tokens = ?, total_tokens = ?, reasoning_tokens = ?, cost = ?, raw_response_json = ?
                WHERE response_id = ?
                """,
                (
                    response.run_id,
                    response.snapshot_id,
                    response.question_id,
                    response.model_id,
                    response.iteration,
                    response.selected_answer,
                    response.response_text,
                    response.is_correct,
                    response.status,
                    response.latency_ms,
                    response.input_tokens,
                    response.output_tokens,
                    response.total_tokens,
                    response.reasoning_tokens,
                    response.cost,
                    response.raw_response_json,
                    response.response_id,
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return response
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, response_id: int) -> bool:
        """Delete a response record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM responses WHERE response_id = ?", (response_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class ErrorRepository:
    """Repository for Error entity CRUD operations.

    Errors track failures during benchmark execution.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ErrorRepository."""
        self.db_manager = db_manager

    def create(self, error: Error) -> Error:
        """Create a new error record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO errors (run_id, question_id, model_id, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    error.run_id,
                    error.question_id,
                    error.model_id,
                    error.error_type,
                    error.error_message,
                    error.stack_trace,
                ),
            )
            conn.commit()
            error.error_id = cursor.lastrowid
            return error
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, error_id: int) -> Optional[Error]:
        """Retrieve an error by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT error_id, run_id, question_id, model_id, error_type, error_message, stack_trace, timestamp
                FROM errors WHERE error_id = ?
                """,
                (error_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Error(
                error_id=row["error_id"],
                run_id=row["run_id"],
                question_id=row["question_id"],
                model_id=row["model_id"],
                error_type=row["error_type"],
                error_message=row["error_message"],
                stack_trace=row["stack_trace"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run(self, run_id: str) -> list[Error]:
        """Retrieve all errors for a run."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT error_id, run_id, question_id, model_id, error_type, error_message, stack_trace, timestamp
                FROM errors WHERE run_id = ? ORDER BY timestamp
                """,
                (run_id,),
            )
            errors = []
            for row in cursor.fetchall():
                errors.append(
                    Error(
                        error_id=row["error_id"],
                        run_id=row["run_id"],
                        question_id=row["question_id"],
                        model_id=row["model_id"],
                        error_type=row["error_type"],
                        error_message=row["error_message"],
                        stack_trace=row["stack_trace"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                    )
                )
            return errors
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, error_id: int) -> bool:
        """Delete an error record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM errors WHERE error_id = ?", (error_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()
