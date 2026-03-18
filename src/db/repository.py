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

from src.db.models import Error, Experiment, Model, ModelVariant, Run, RunModel, Question, QuestionSnapshot, Response
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
                    system_prompt_template, user_prompt_template
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment.experiment_id,
                    experiment.name,
                    experiment.description,
                    experiment.config_json,
                    experiment.config_hash,
                    experiment.system_prompt_template,
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
                       system_prompt_template, user_prompt_template, created_at
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
                system_prompt_template=row["system_prompt_template"],
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
                       system_prompt_template, user_prompt_template, created_at
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
                system_prompt_template=row["system_prompt_template"],
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
                       system_prompt_template, user_prompt_template, created_at
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
                system_prompt_template=row["system_prompt_template"],
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
                       system_prompt_template, user_prompt_template, created_at
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
                        system_prompt_template=row["system_prompt_template"],
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
                INSERT INTO runs (run_id, experiment_id, seed, started_at, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.experiment_id,
                    run.seed,
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
                SELECT run_id, experiment_id, seed, started_at, finished_at, status
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
                SELECT run_id, experiment_id, seed, started_at, finished_at, status
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
                SELECT run_id, experiment_id, seed, started_at, finished_at, status
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
                        started_at=datetime.fromisoformat(row["started_at"]),
                        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
                        status=row["status"],
                    )
                )
            return runs
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def update_status(self, run_id: str, status: str) -> bool:
        """Update the status of a run.

        Args:
            run_id: ID of the run.
            status: New status to set.

        Returns:
            True if updated successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE runs SET status = ? WHERE run_id = ?",
                (status, run_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
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
                    experiment_id = ?, seed = ?,
                    started_at = ?, finished_at = ?, status = ?
                WHERE run_id = ?
                """,
                (
                    run.experiment_id,
                    run.seed,
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
                INSERT INTO models (model_id, provider, model_name)
                VALUES (?, ?, ?)
                """,
                (
                    model.model_id,
                    model.provider,
                    model.model_name,
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
                SELECT model_id, provider, model_name, created_at
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
                SELECT model_id, provider, model_name, created_at
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


class ModelVariantRepository:
    """Repository for ModelVariant entity CRUD operations.

    Model variants store execution parameters (reasoning, vision, structured)
    for each base model. Each variant is a unique combination of:
    - Base model (model_id)
    - Reasoning mode (off/auto/effort/budget/unspecified)
    - Reasoning effort (when mode='effort')
    - Reasoning max tokens (when mode='budget')
    - Vision enabled
    - Structured enabled
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ModelVariantRepository."""
        self.db_manager = db_manager

    def create(self, variant: ModelVariant) -> ModelVariant:
        """Create a new model variant record.

        Args:
            variant: ModelVariant object to create.

        Returns:
            The created ModelVariant object.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO model_variants (
                    variant_id, model_id, reasoning_mode, reasoning_effort,
                    max_output_tokens, vision_enabled, structured_output,
                    web_access_enabled, temperature, top_p,
                    variant_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    variant.variant_id,
                    variant.model_id,
                    variant.reasoning_mode,
                    variant.reasoning_effort,
                    variant.max_output_tokens,
                    1 if variant.vision_enabled else 0,
                    1 if variant.structured_output else 0,
                    1 if variant.web_access_enabled else 0,
                    variant.temperature,
                    variant.top_p,
                    variant.variant_signature,
                ),
            )
            conn.commit()
            return variant
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_id(self, variant_id: str) -> Optional[ModelVariant]:
        """Retrieve a model variant by its ID."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT variant_id, model_id, reasoning_mode, reasoning_effort,
                       max_output_tokens, vision_enabled, structured_output,
                       web_access_enabled, temperature, top_p,
                       variant_signature, created_at
                FROM model_variants WHERE variant_id = ?
                """,
                (variant_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ModelVariant(
                variant_id=row["variant_id"],
                model_id=row["model_id"],
                reasoning_mode=row["reasoning_mode"],
                reasoning_effort=row["reasoning_effort"],
                max_output_tokens=row["max_output_tokens"],
                vision_enabled=bool(row["vision_enabled"]),
                structured_output=bool(row["structured_output"]),
                web_access_enabled=bool(row["web_access_enabled"]),
                temperature=row["temperature"],
                top_p=row["top_p"],
                variant_signature=row["variant_signature"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_signature(self, model_id: str, variant_signature: str) -> Optional[ModelVariant]:
        """Retrieve a model variant by model_id and variant_signature."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT variant_id, model_id, reasoning_mode, reasoning_effort,
                       max_output_tokens, vision_enabled, structured_output,
                       web_access_enabled, temperature, top_p,
                       variant_signature, created_at
                FROM model_variants WHERE model_id = ? AND variant_signature = ?
                """,
                (model_id, variant_signature),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return ModelVariant(
                variant_id=row["variant_id"],
                model_id=row["model_id"],
                reasoning_mode=row["reasoning_mode"],
                reasoning_effort=row["reasoning_effort"],
                max_output_tokens=row["max_output_tokens"],
                vision_enabled=bool(row["vision_enabled"]),
                structured_output=bool(row["structured_output"]),
                web_access_enabled=bool(row["web_access_enabled"]),
                temperature=row["temperature"],
                top_p=row["top_p"],
                variant_signature=row["variant_signature"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_all(self) -> list[ModelVariant]:
        """Retrieve all model variants."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT variant_id, model_id, reasoning_mode, reasoning_effort,
                       max_output_tokens, vision_enabled, structured_output,
                       web_access_enabled, temperature, top_p,
                       variant_signature, created_at
                FROM model_variants ORDER BY model_id, variant_signature
                """
            )
            variants = []
            for row in cursor.fetchall():
                variants.append(
                    ModelVariant(
                        variant_id=row["variant_id"],
                        model_id=row["model_id"],
                        reasoning_mode=row["reasoning_mode"],
                        reasoning_effort=row["reasoning_effort"],
                        max_output_tokens=row["max_output_tokens"],
                        vision_enabled=bool(row["vision_enabled"]),
                        structured_output=bool(row["structured_output"]),
                        variant_signature=row["variant_signature"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return variants
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_model(self, model_id: str) -> list[ModelVariant]:
        """Retrieve all variants for a base model."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT variant_id, model_id, reasoning_mode, reasoning_effort,
                       max_output_tokens, vision_enabled, structured_output,
                       web_access_enabled, temperature, top_p,
                       variant_signature, created_at
                FROM model_variants WHERE model_id = ?
                ORDER BY variant_signature
                """,
                (model_id,),
            )
            variants = []
            for row in cursor.fetchall():
                variants.append(
                    ModelVariant(
                        variant_id=row["variant_id"],
                        model_id=row["model_id"],
                        reasoning_mode=row["reasoning_mode"],
                        reasoning_effort=row["reasoning_effort"],
                        max_output_tokens=row["max_output_tokens"],
                        vision_enabled=bool(row["vision_enabled"]),
                        structured_output=bool(row["structured_output"]),
                        variant_signature=row["variant_signature"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return variants
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, variant_id: str) -> bool:
        """Delete a model variant record."""
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM model_variants WHERE variant_id = ?", (variant_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class RunModelRepository:
    """Repository for RunModel entity CRUD operations.

    RunModel tracks the association between runs and model variants,
    allowing models to be added to runs dynamically.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the RunModelRepository."""
        self.db_manager = db_manager

    def add(self, run_id: str, variant_id: str, status: str = "pending") -> None:
        """Add a model variant to a run.

        Convenience method for creating run-model associations.

        Args:
            run_id: ID of the run.
            variant_id: ID of the model variant.
            status: Initial status (default: "pending").
        """
        from datetime import datetime
        from src.db.models import RunModel
        
        run_model = RunModel(
            run_id=run_id,
            variant_id=variant_id,
            status=status,
            added_at=datetime.now(),
            completed_at=None,
        )
        self.create(run_model)

    def create(self, run_model: RunModel) -> RunModel:
        """Create a new run-model association.

        Args:
            run_model: RunModel object to create.

        Returns:
            The created RunModel object.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO run_models (run_id, variant_id, status, added_at, completed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_model.run_id,
                    run_model.variant_id,
                    run_model.status,
                    run_model.added_at.isoformat(),
                    run_model.completed_at.isoformat() if run_model.completed_at else None,
                ),
            )
            conn.commit()
            return run_model
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run(self, run_id: str) -> list[RunModel]:
        """Retrieve all model variants for a run.

        Args:
            run_id: ID of the run.

        Returns:
            List of RunModel objects for the run.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, variant_id, status, added_at, completed_at
                FROM run_models WHERE run_id = ?
                ORDER BY added_at
                """,
                (run_id,),
            )
            run_models = []
            for row in cursor.fetchall():
                run_models.append(
                    RunModel(
                        run_id=row["run_id"],
                        variant_id=row["variant_id"],
                        status=row["status"],
                        added_at=datetime.fromisoformat(row["added_at"]),
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    )
                )
            return run_models
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_variant(self, variant_id: str) -> list[RunModel]:
        """Retrieve all runs for a model variant.

        Args:
            variant_id: ID of the model variant.

        Returns:
            List of RunModel objects for the variant.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, variant_id, status, added_at, completed_at
                FROM run_models WHERE variant_id = ?
                ORDER BY added_at
                """,
                (variant_id,),
            )
            run_models = []
            for row in cursor.fetchall():
                run_models.append(
                    RunModel(
                        run_id=row["run_id"],
                        variant_id=row["variant_id"],
                        status=row["status"],
                        added_at=datetime.fromisoformat(row["added_at"]),
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    )
                )
            return run_models
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_run_and_variant(self, run_id: str, variant_id: str) -> Optional[RunModel]:
        """Retrieve a run-model association by run and variant.

        Args:
            run_id: ID of the run.
            variant_id: ID of the model variant.

        Returns:
            RunModel object if found, None otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_id, variant_id, status, added_at, completed_at
                FROM run_models WHERE run_id = ? AND variant_id = ?
                """,
                (run_id, variant_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return RunModel(
                run_id=row["run_id"],
                variant_id=row["variant_id"],
                status=row["status"],
                added_at=datetime.fromisoformat(row["added_at"]),
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def update_status(self, run_id: str, variant_id: str, status: str) -> bool:
        """Update the status of a run-model association.

        Args:
            run_id: ID of the run.
            variant_id: ID of the model variant.
            status: New status ('pending', 'running', 'completed', 'removed').

        Returns:
            True if updated successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            
            # Set completed_at when status changes to 'completed'
            if status == 'completed':
                cursor.execute(
                    """
                    UPDATE run_models 
                    SET status = ?, completed_at = ?
                    WHERE run_id = ? AND variant_id = ?
                    """,
                    (status, datetime.now().isoformat(), run_id, variant_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE run_models SET status = ?
                    WHERE run_id = ? AND variant_id = ?
                    """,
                    (status, run_id, variant_id),
                )
            
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def delete(self, run_id: str, variant_id: str) -> bool:
        """Delete a run-model association.

        Args:
            run_id: ID of the run.
            variant_id: ID of the model variant.

        Returns:
            True if deleted successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM run_models WHERE run_id = ? AND variant_id = ?",
                (run_id, variant_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()


class ExperimentModelRepository:
    """Repository for Experiment-Model association.

    This table defines which model variants belong to an experiment.
    Simple association: no status field, removal is physical (DELETE).
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ExperimentModelRepository."""
        self.db_manager = db_manager

    def add_variant(self, experiment_id: str, variant_id: str) -> None:
        """Associate a model variant with an experiment.

        Args:
            experiment_id: ID of the experiment.
            variant_id: ID of the model variant.

        Raises:
            sqlite3.IntegrityError: If association already exists.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO experiment_models (experiment_id, variant_id)
                VALUES (?, ?)
                """,
                (experiment_id, variant_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_by_experiment(self, experiment_id: str) -> list["ModelVariant"]:
        """Retrieve all model variants associated with an experiment.

        Args:
            experiment_id: ID of the experiment.

        Returns:
            List of ModelVariant objects.
        """
        from src.db.models import ModelVariant

        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT mv.variant_id, mv.model_id, mv.reasoning_mode, mv.reasoning_effort,
                       mv.max_output_tokens, mv.vision_enabled, mv.structured_output,
                       mv.variant_signature, mv.created_at
                FROM experiment_models em
                JOIN model_variants mv ON em.variant_id = mv.variant_id
                WHERE em.experiment_id = ?
                ORDER BY em.added_at
                """,
                (experiment_id,),
            )
            variants = []
            for row in cursor.fetchall():
                variants.append(
                    ModelVariant(
                        variant_id=row["variant_id"],
                        model_id=row["model_id"],
                        reasoning_mode=row["reasoning_mode"],
                        reasoning_effort=row["reasoning_effort"],
                        max_output_tokens=row["max_output_tokens"],
                        vision_enabled=bool(row["vision_enabled"]),
                        structured_output=bool(row["structured_output"]),
                        variant_signature=row["variant_signature"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
            return variants
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def remove_variant(self, experiment_id: str, variant_id: str) -> bool:
        """Remove a model variant from an experiment.

        Args:
            experiment_id: ID of the experiment.
            variant_id: ID of the model variant.

        Returns:
            True if removed successfully, False if not found.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM experiment_models WHERE experiment_id = ? AND variant_id = ?",
                (experiment_id, variant_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            conn.rollback()
            raise
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def exists(self, experiment_id: str, variant_id: str) -> bool:
        """Check if a model variant is associated with an experiment.

        Args:
            experiment_id: ID of the experiment.
            variant_id: ID of the model variant.

        Returns:
            True if association exists, False otherwise.
        """
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT 1 FROM experiment_models
                WHERE experiment_id = ? AND variant_id = ?
                """,
                (experiment_id, variant_id),
            )
            return cursor.fetchone() is not None
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
        self, experiment_id: str, question_id: str, question_payload: str
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
            question_payload: Complete JSON representation of the question.

        Returns:
            The snapshot_id (either newly created or existing).

        Raises:
            ValueError: If experiment_id is None or empty.

        Example:
            >>> repo = QuestionSnapshotRepository(db_manager)
            >>> snapshot_id = repo.create_if_not_exists(
            ...     experiment_id="exp-001",
            ...     question_id="Q001",
            ...     question_payload='{"id": "Q001", "stem": "What is 2+2?"}'
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
                INSERT INTO question_snapshots (experiment_id, question_id, question_payload)
                VALUES (?, ?, ?)
                """,
                (experiment_id, question_id, question_payload),
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
                SELECT snapshot_id, experiment_id, question_id, question_payload, created_at
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
                question_payload=row["question_payload"],
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
                SELECT snapshot_id, experiment_id, question_id, question_payload, created_at
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
                        question_payload=row["question_payload"],
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
                SELECT snapshot_id, experiment_id, question_id, question_payload, created_at
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
                        question_payload=row["question_payload"],
                        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                    )
                )
            return snapshots
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def validate_snapshot_integrity(self, snapshot_id: int) -> tuple[bool, str]:
        """Validate that snapshot payload matches question_id.

        This method ensures data integrity by verifying that the question_id
        stored in the snapshot metadata matches the 'id' field inside the
        question_payload.

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
            question_data = json.loads(snapshot.question_payload)
            if question_data.get("id") != snapshot.question_id:
                return (
                    False,
                    f"Question ID mismatch: snapshot.question_id={snapshot.question_id}, "
                    f"payload.id={question_data.get('id')}",
                )
            return True, ""
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in question_payload: {e}"
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
                f"question_id={response.question_id}, variant_id={response.variant_id}"
            )
            cursor.execute(
                """
                INSERT INTO responses (
                    run_id, snapshot_id, question_id, model_id, variant_id, iteration,
                    selected_answer, response_text, is_correct,
                    status, finish_reason, error_details, latency_ms,
                    input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                    cost, raw_response_json,
                    parse_confidence, needs_review, manual_answer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response.run_id,
                    response.snapshot_id,
                    response.question_id,
                    response.model_id,
                    response.variant_id,
                    response.iteration,
                    response.selected_answer,
                    response.response_text,
                    response.is_correct,
                    response.status,
                    response.finish_reason,
                    response.error_details,
                    response.latency_ms,
                    response.input_tokens,
                    response.response_tokens,
                    response.total_tokens,
                    response.reasoning_tokens,
                    response.effective_tokens,
                    response.cost,
                    response.raw_response_json,
                    response.parse_confidence,
                    1 if response.needs_review else 0,
                    response.manual_answer,
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
                f"question_id={response.question_id}, variant_id={response.variant_id}"
            )
            # Check which FK is failing
            run_exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (response.run_id,)).fetchone() is not None
            snapshot_exists = conn.execute("SELECT 1 FROM question_snapshots WHERE snapshot_id = ?", (response.snapshot_id,)).fetchone() is not None
            question_exists = conn.execute("SELECT 1 FROM questions WHERE question_id = ?", (response.question_id,)).fetchone() is not None
            variant_exists = conn.execute("SELECT 1 FROM model_variants WHERE variant_id = ?", (response.variant_id,)).fetchone() is not None
            logger.error(
                f"FK check: run_exists={run_exists}, snapshot_exists={snapshot_exists}, "
                f"question_exists={question_exists}, variant_exists={variant_exists}"
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
                SELECT response_id, run_id, snapshot_id, question_id, variant_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                variant_id=row["variant_id"],
                iteration=row["iteration"],
                selected_answer=row["selected_answer"],
                response_text=row["response_text"],
                is_correct=row["is_correct"],
                status=row["status"],
                finish_reason=row["finish_reason"],
                error_details=row["error_details"],
                latency_ms=row["latency_ms"],
                input_tokens=row["input_tokens"],
                response_tokens=row["response_tokens"],
                total_tokens=row["total_tokens"],
                reasoning_tokens=row["reasoning_tokens"],
                effective_tokens=row["effective_tokens"],
                cost=row["cost"],
                raw_response_json=row["raw_response_json"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                needs_review=bool(row["needs_review"]),
                manual_answer=row["manual_answer"],
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
                SELECT response_id, run_id, snapshot_id, question_id, model_id, variant_id, iteration,
                       selected_answer, response_text, is_correct,
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                        variant_id=row["variant_id"],
                        iteration=row["iteration"],
                        selected_answer=row["selected_answer"],
                        response_text=row["response_text"],
                        is_correct=row["is_correct"],
                        status=row["status"],
                        finish_reason=row["finish_reason"],
                        error_details=row["error_details"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        response_tokens=row["response_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        effective_tokens=row["effective_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                        needs_review=bool(row["needs_review"]),
                        manual_answer=row["manual_answer"],
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
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                        finish_reason=row["finish_reason"],
                        error_details=row["error_details"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        response_tokens=row["response_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        effective_tokens=row["effective_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                        needs_review=bool(row["needs_review"]),
                        manual_answer=row["manual_answer"],
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
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                        finish_reason=row["finish_reason"],
                        error_details=row["error_details"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        response_tokens=row["response_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        effective_tokens=row["effective_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                        needs_review=bool(row["needs_review"]),
                        manual_answer=row["manual_answer"],
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
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                        finish_reason=row["finish_reason"],
                        error_details=row["error_details"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        response_tokens=row["response_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        effective_tokens=row["effective_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                        needs_review=bool(row["needs_review"]),
                        manual_answer=row["manual_answer"],
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
                       status, finish_reason, error_details, latency_ms,
                       input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
                       cost, raw_response_json, timestamp,
                       parse_confidence, needs_review, manual_answer
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
                        finish_reason=row["finish_reason"],
                        error_details=row["error_details"],
                        latency_ms=row["latency_ms"],
                        input_tokens=row["input_tokens"],
                        response_tokens=row["response_tokens"],
                        total_tokens=row["total_tokens"],
                        reasoning_tokens=row["reasoning_tokens"],
                        effective_tokens=row["effective_tokens"],
                        cost=row["cost"],
                        raw_response_json=row["raw_response_json"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        parse_confidence=row["parse_confidence"] if row["parse_confidence"] else "unknown",
                        needs_review=bool(row["needs_review"]),
                        manual_answer=row["manual_answer"],
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
                    run_id = ?, snapshot_id = ?, question_id = ?, variant_id = ?, iteration = ?,
                    selected_answer = ?, response_text = ?, is_correct = ?,
                    status = ?, finish_reason = ?, error_details = ?, latency_ms = ?,
                    input_tokens = ?, response_tokens = ?,
                    total_tokens = ?, reasoning_tokens = ?, effective_tokens = ?,
                    cost = ?, raw_response_json = ?,
                    parse_confidence = ?, needs_review = ?
                WHERE response_id = ?
                """,
                (
                    response.run_id,
                    response.snapshot_id,
                    response.question_id,
                    response.variant_id,
                    response.iteration,
                    response.selected_answer,
                    response.response_text,
                    response.is_correct,
                    response.status,
                    response.finish_reason,
                    response.error_details,
                    response.latency_ms,
                    response.input_tokens,
                    response.response_tokens,
                    response.total_tokens,
                    response.reasoning_tokens,
                    response.effective_tokens,
                    response.cost,
                    response.raw_response_json,
                    response.parse_confidence,
                    1 if response.needs_review else 0,
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
                INSERT INTO errors (run_id, question_id, variant_id, error_type, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    error.run_id,
                    error.question_id,
                    error.variant_id,
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
                SELECT error_id, run_id, question_id, variant_id, error_type, error_message, stack_trace, timestamp
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
                variant_id=row["variant_id"],
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
                SELECT error_id, run_id, question_id, variant_id, error_type, error_message, stack_trace, timestamp
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
                        variant_id=row["variant_id"],
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
