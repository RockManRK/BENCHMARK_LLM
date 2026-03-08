"""Run manager module for benchmark_llm project.

This module provides functionality to manage benchmark run lifecycle,
including run initialization, configuration storage, and status tracking.
Supports three execution modes: test, dev, and experiment.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Optional

from src.db.models import Experiment, Model, Run
from src.db.repository import ExperimentRepository, ModelRepository, RunRepository
from src.db.schema import DatabaseManager
from src.utils.config import Settings

logger = logging.getLogger(__name__)


class RunManager:
    """Manages benchmark run lifecycle.

    This class handles the creation, tracking, and management of benchmark
    test runs. Each run represents a complete execution of the benchmark
    with specific configuration.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        current_run: Currently active run, if any.
        current_experiment: Currently active experiment, if any.

    Example:
        >>> run_manager = RunManager(db_manager, settings)
        >>> run = run_manager.initialize_run({
        ...     "models": ["gpt-4", "claude-3"],
        ...     "iterations": 3
        ... })
        >>> print(run.run_id)
        run-<timestamp>
    """

    def __init__(self, db_manager: DatabaseManager, settings: Optional[Settings] = None) -> None:
        """Initialize the RunManager.

        Args:
            db_manager: DatabaseManager instance for database connections.
            settings: Optional settings for experiment mode configuration.

        Example:
            >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> run_manager = RunManager(db_manager, settings)
        """
        self.db_manager = db_manager
        self.settings = settings
        self._run_repository = RunRepository(db_manager)
        self._experiment_repository = ExperimentRepository(db_manager)
        self._model_repository = ModelRepository(db_manager)
        self.current_run: Optional[Run] = None
        self.current_experiment: Optional[Experiment] = None
        logger.info("RunManager initialized")

    def initialize_run(self, config: dict[str, Any]) -> Run:
        """Initialize a new benchmark run.

        Creates a new run with a unique run_id, stores the configuration,
        and sets the initial status to 'running'.

        In experiment mode, creates or retrieves an experiment with frozen
        configuration.

        Args:
            config: Run configuration dictionary containing models,
                    iterations, and other settings.

        Returns:
            The created Run object with unique run_id and initial status.

        Raises:
            sqlite3.Error: If there's an error saving to database.

        Example:
            >>> config = {
            ...     "models": ["gpt-4", "claude-3"],
            ...     "iterations": 3,
            ...     "questions": ["Q001", "Q002"]
            ... }
            >>> run = run_manager.initialize_run(config)
            >>> print(f"Run {run.run_id} started with status: {run.status}")
        """
        # Generate unique run_id with timestamp component
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        run_id = f"run-{timestamp}-{unique_id}"

        # Determine execution mode and experiment tracking
        experiment_id = None
        is_dev = True

        if self.settings and self.settings.is_experiment_mode:
            # Experiment mode: create or retrieve experiment
            experiment = self._get_or_create_experiment(config)
            experiment_id = experiment.experiment_id
            is_dev = False
            logger.info(f"Using experiment: {experiment.name} (hash={experiment.config_hash})")
        elif self.settings and self.settings.is_test_mode:
            # Test mode: no persistence
            is_dev = False
            logger.debug("Test mode: run will not be persisted")
        else:
            # Dev mode: persist without experiment
            is_dev = True
            logger.debug("Dev mode: persisting run without experiment")

        # Create run object
        run = Run(
            run_id=run_id,
            experiment_id=experiment_id,
            seed=config.get("seed"),
            is_dev=is_dev,
            started_at=datetime.now(),
            status="running",
        )

        # Save to database (in test mode this goes to :memory:)
        logger.info(f"Creating run in database: {run_id}")
        self._run_repository.create(run)
        logger.info(f"Run created successfully")

        # Register models in database (required for foreign key constraints)
        models = config.get("models", [])
        logger.info(f"Registering {len(models)} models: {models}")
        for model_id in models:
            self._register_model(model_id)
            logger.info(f"Model {model_id} registered")

        # Set as current run
        self.current_run = run

        logger.info(f"Initialized run {run_id} with config: {config}")
        logger.debug(f"Run configuration: experiment_id={experiment_id}, is_dev={is_dev}")

        return run

    def _get_or_create_experiment(self, config: dict[str, Any]) -> Experiment:
        """Get existing experiment or create new one with frozen config.

        Args:
            config: Run configuration dictionary.

        Returns:
            Existing or newly created Experiment object.
        """
        if not self.settings or not self.settings.experiment_name:
            raise ValueError("Experiment name required for experiment mode")

        # Check if experiment already exists by name
        existing = self._experiment_repository.get_by_name(self.settings.experiment_name)
        if existing:
            logger.info(f"Found existing experiment: {existing.name}")
            current_hash = self.settings.get_config_hash()
            if current_hash != existing.config_hash:
                logger.warning(
                    f"Configuration mismatch for experiment '{existing.name}'. "
                    f"Current settings (hash={current_hash}) will be IGNORADA/DESCARTADA "
                    f"in favor of the frozen configuration (hash={existing.config_hash})."
                )
                # Overwrite current mutable settings with the frozen configuration
                try:
                    frozen_config = json.loads(existing.config_json)
                    for key, value in frozen_config.items():
                        if hasattr(self.settings, key):
                            setattr(self.settings, key, value)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse frozen config for '{existing.name}'")
                    
            self.current_experiment = existing
            return existing

        # Create new experiment with frozen configuration
        config_json = json.dumps(self.settings.get_config_dict(), sort_keys=True, default=str)
        config_hash = self.settings.get_config_hash()

        experiment = Experiment(
            name=self.settings.experiment_name,
            config_json=config_json,
            config_hash=config_hash,
            system_prompt=self.settings.system_prompt,
            user_prompt_template=self.settings.user_prompt_template,
            description=f"Experiment created on {datetime.now().isoformat()}",
        )

        created = self._experiment_repository.create(experiment)
        logger.info(f"Created new experiment: {created.name} (hash={config_hash})")
        self.current_experiment = created
        return created

    def _register_model(self, model_id: str) -> None:
        """Register a model in the database if it doesn't exist.

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4").
        """
        # Check if model already exists
        existing = self._model_repository.get_by_id(model_id)
        if existing:
            logger.debug(f"Model already registered: {model_id}")
            return

        # Extract provider from model_id
        if "/" in model_id:
            parts = model_id.split("/", 1)
            provider = parts[0]
            model_name = parts[1] if len(parts) > 1 else model_id
        else:
            provider = "unknown"
            model_name = model_id

        # Create model record
        model = Model(
            model_id=model_id,
            provider=provider,
            model_name=model_name,
        )

        try:
            self._model_repository.create(model)
            logger.debug(f"Registered model: {model_id}")
        except sqlite3.IntegrityError:
            # Model might have been registered concurrently, ignore
            logger.debug(f"Model registration conflict (ignored): {model_id}")

    def update_run_status(self, run_id: str, status: str) -> Optional[Run]:
        """Update the status of a run.

        Args:
            run_id: The unique identifier of the run to update.
            status: New status value (pending, running, completed, failed).

        Returns:
            The updated Run object if successful, None if run not found.

        Raises:
            ValueError: If status is not a valid status value.

        Example:
            >>> run_manager.update_run_status("run-123", "completed")
            <Run object with status='completed'>
        """
        valid_statuses = {"pending", "running", "completed", "failed"}
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of {valid_statuses}"
            )

        run = self._run_repository.get_by_id(run_id)
        if run is None:
            logger.warning(f"Run {run_id} not found for status update")
            return None

        run.status = status
        self._run_repository.update(run)

        # Update current run if it's the same run
        if self.current_run and self.current_run.run_id == run_id:
            self.current_run.status = status

        logger.info(f"Updated run {run_id} status to: {status}")

        return run

    def get_run_by_id(self, run_id: str) -> Optional[Run]:
        """Retrieve a run by its ID.

        Args:
            run_id: The unique identifier of the run to retrieve.

        Returns:
            Run object if found, None otherwise.

        Example:
            >>> run = run_manager.get_run_by_id("run-123")
            >>> if run:
            ...     print(f"Run {run.run_id} created at {run.created_at}")
        """
        run = self._run_repository.get_by_id(run_id)
        if run:
            logger.debug(f"Retrieved run {run_id}")
        else:
            logger.warning(f"Run {run_id} not found")
        return run

    def get_current_run(self) -> Optional[Run]:
        """Get the current active run.

        Returns:
            The current Run object if one exists, None otherwise.

        Example:
            >>> run = run_manager.get_current_run()
            >>> if run:
            ...     print(f"Current run: {run.run_id}")
        """
        return self.current_run

    def get_run_config(self, run_id: str) -> Optional[dict[str, Any]]:
        """Get the configuration for a run.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            Configuration dictionary if run exists, None otherwise.

        Example:
            >>> config = run_manager.get_run_config("run-123")
            >>> if config:
            ...     models = config.get("models", [])
        """
        run = self._run_repository.get_by_id(run_id)
        if run is None:
            return None

        try:
            config = json.loads(run.config)
            logger.debug(f"Retrieved config for run {run_id}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config for run {run_id}: {e}")
            return None

    def complete_run(self, run_id: str) -> Optional[Run]:
        """Mark a run as completed.

        Args:
            run_id: The unique identifier of the run to complete.

        Returns:
            The updated Run object if successful, None if run not found.

        Example:
            >>> run_manager.complete_run("run-123")
            <Run object with status='completed'>
        """
        return self.update_run_status(run_id, "completed")

    def fail_run(self, run_id: str, error_message: Optional[str] = None) -> Optional[Run]:
        """Mark a run as failed.

        Args:
            run_id: The unique identifier of the run to fail.
            error_message: Optional error message to log.

        Returns:
            The updated Run object if successful, None if run not found.

        Example:
            >>> run_manager.fail_run("run-123", "Database connection failed")
            <Run object with status='failed'>
        """
        if error_message:
            logger.error(f"Run {run_id} failed: {error_message}")
        else:
            logger.error(f"Run {run_id} failed")

        return self.update_run_status(run_id, "failed")
