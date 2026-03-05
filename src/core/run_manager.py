"""Run manager module for benchmark_llm project.

This module provides functionality to manage benchmark run lifecycle,
including run initialization, configuration storage, and status tracking.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Optional

from src.db.models import Model, Run
from src.db.repository import RunRepository
from src.db.schema import DatabaseManager

logger = logging.getLogger(__name__)


class RunManager:
    """Manages benchmark run lifecycle.

    This class handles the creation, tracking, and management of benchmark
    test runs. Each run represents a complete execution of the benchmark
    with specific configuration.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        current_run: Currently active run, if any.

    Example:
        >>> run_manager = RunManager(db_manager)
        >>> run = run_manager.initialize_run({
        ...     "models": ["gpt-4", "claude-3"],
        ...     "iterations": 3
        ... })
        >>> print(run.run_id)
        run-<timestamp>
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the RunManager.

        Args:
            db_manager: DatabaseManager instance for database connections.

        Example:
            >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> run_manager = RunManager(db_manager)
        """
        self.db_manager = db_manager
        self._run_repository = RunRepository(db_manager)
        self.current_run: Optional[Run] = None
        logger.info("RunManager initialized")

    def initialize_run(self, config: dict[str, Any]) -> Run:
        """Initialize a new benchmark run.

        Creates a new run with a unique run_id, stores the configuration,
        and sets the initial status to 'running'.

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

        # Create run object
        run = Run(
            run_id=run_id,
            created_at=datetime.now(),
            config=json.dumps(config),
            status="running",
        )

        # Save to database
        self._run_repository.create(run)

        # Register models in database (required for foreign key constraints)
        from src.db.repository import ModelRepository
        model_repo = ModelRepository(self.db_manager)
        models = config.get("models", [])
        for model_id in models:
            # Extract provider from model_id (e.g., "openai/gpt-4" -> "openai")
            if "/" in model_id:
                provider = model_id.split("/")[0]
                model_name = model_id.split("/")[1]
            else:
                provider = "unknown"
                model_name = model_id
            
            try:
                model_repo.create(model_id, model_name, provider)
                logger.debug(f"Registered model: {model_id}")
            except sqlite3.Error:
                # Model might already exist, ignore error
                pass

        # Set as current run
        self.current_run = run

        logger.info(f"Initialized run {run_id} with config: {config}")
        logger.debug(f"Run configuration JSON: {run.config}")

        return run

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
