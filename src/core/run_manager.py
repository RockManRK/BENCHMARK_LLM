"""Run manager module for benchmark_llm project.

This module provides functionality to manage benchmark run lifecycle,
including run initialization, configuration storage, and status tracking.
Supports three execution modes: test, dev, and experiment.
"""

import json
import logging
import random
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Optional

from src.db.models import Experiment, Model, ModelVariant, Run
from src.db.repository import ExperimentRepository, ModelRepository, ModelVariantRepository, RunRepository
from src.db.schema import DatabaseManager
from src.utils.config import Settings
from src.core.variant_config import VariantConfig

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
        self._variant_repository = ModelVariantRepository(db_manager)
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
        # IMPORTANT: Every run MUST have an experiment_id (no NULL allowed)
        experiment_id: str | None = None
        is_dev = True

        if self.settings and self.settings.is_experiment_mode:
            # Experiment mode: create or retrieve experiment
            experiment = self._get_or_create_experiment(config)
            experiment_id = experiment.experiment_id
            is_dev = False
            logger.info(f"Using experiment: {experiment.name} (hash={experiment.config_hash})")
        elif self.settings and self.settings.is_test_mode:
            # Test mode: no persistence (in-memory database)
            is_dev = False
            logger.debug("Test mode: run will not be persisted")
        else:
            # Dev mode: create shadow experiment for this run
            # This ensures every snapshot has a valid experiment_id
            experiment = self._create_shadow_experiment(run_id, config)
            experiment_id = experiment.experiment_id
            is_dev = True
            logger.info(f"Created shadow experiment for dev mode: {experiment.name}")

        # Create run object
        # Determine seed value based on configuration
        seed_value = self._determine_seed(config)

        run = Run(
            run_id=run_id,
            experiment_id=experiment_id,
            seed=seed_value,
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
            self._register_model_variant(model_id)
            logger.info(f"Model variant registered for {model_id}")

        # Set as current run
        self.current_run = run

        logger.info(f"Initialized run {run_id} with config: {config}")
        logger.debug(f"Run configuration: experiment_id={experiment_id}, is_dev={is_dev}")

        return run

    def _determine_seed(self, config: dict[str, Any]) -> Optional[int]:
        """Determine the seed value based on configuration.

        This is the SINGLE SOURCE OF TRUTH for seed generation.
        All seed logic is centralized here.

        Rules (precedence order):
        1. CLI --seed explicit → Use fixed seed from CLI
        2. RANDOM_SEED=AUTO in .env → Generate unique random seed per RUN
        3. RANDOM_SEED=<int> in .env → Use fixed seed from .env
        4. No seed → Keep original order (None)

        Args:
            config: Run configuration dictionary containing seed setting.

        Returns:
            Integer seed value or None if no seed should be used.

        Example:
            >>> config = {"seed": "AUTO"}
            >>> seed = manager._determine_seed(config)
            >>> isinstance(seed, int)
            True
        """
        seed_config = config.get("seed")

        # Case 1: CLI --seed explicit has highest precedence
        if seed_config is not None and isinstance(seed_config, int):
            logger.info(f"Run initialized with seed: {seed_config} (policy=CLI)")
            return seed_config

        # Case 2: RANDOM_SEED=AUTO in .env → Generate unique seed per RUN
        if self.settings and self.settings.random_seed == "AUTO":
            auto_seed = random.randint(0, 2**31 - 1)
            logger.info(f"Run initialized with seed: {auto_seed} (policy=AUTO)")
            return auto_seed

        # Case 3: RANDOM_SEED=<int> in .env → Use fixed seed
        if self.settings and isinstance(self.settings.random_seed, int):
            logger.info(f"Run initialized with seed: {self.settings.random_seed} (policy=FIXED)")
            return self.settings.random_seed

        # Case 4: No seed configured → Keep original order
        logger.info("Run initialized with seed: None (policy=NONE, original A,B,C,D order)")
        return None

    def _get_or_create_experiment(self, config: dict[str, Any]) -> Experiment:
        """Get existing experiment or create new one with frozen config.

        Protocol configuration is frozen per experiment. Model variants
        (temperature, reasoning, vision) are NOT frozen and can vary
        between runs within the same experiment.

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
                # Protocol mismatch - only PROTOCOL settings are overwritten
                # Model variants (temperature, reasoning, vision) are preserved
                frozen_config = json.loads(existing.config_json)

                # Protocol keys that MUST be frozen per experiment
                protocol_keys = {"default_prompt", "use_structured_outputs", "random_seed_policy"}

                # Track which protocol settings were overwritten
                overwritten_protocol = []

                try:
                    for key, value in frozen_config.items():
                        # Only overwrite PROTOCOL settings, NOT model variants
                        if key in protocol_keys and hasattr(self.settings, key):
                            setattr(self.settings, key, value)
                            overwritten_protocol.append(key)
                except (json.JSONDecodeError, AttributeError):
                    logger.error(f"Failed to parse frozen config for '{existing.name}'")

                # Log explicit warning about protocol mismatch
                logger.warning(f"Frozen experiment protocol mismatch for '{existing.name}'.")

                if overwritten_protocol:
                    logger.warning(f"Using frozen protocol settings: {', '.join(overwritten_protocol)}")

                logger.warning(
                    f"Model variants (temperature, max_tokens, reasoning, vision) are preserved "
                    f"and will NOT be overwritten by frozen configuration."
                )

            # Check for prompt template conflicts (source of truth is the database)
            # Prompts from experiment take precedence over current settings
            if existing.system_prompt_template is not None:
                if self.settings.system_prompt != existing.system_prompt_template:
                    logger.warning(
                        f"Experiment '{existing.name}' has frozen system_prompt_template. "
                        f"Using frozen value instead of current setting."
                    )
                    self.settings.system_prompt = existing.system_prompt_template

            if existing.user_prompt_template is not None:
                if self.settings.user_prompt_template != existing.user_prompt_template:
                    logger.warning(
                        f"Experiment '{existing.name}' has frozen user_prompt_template. "
                        f"Using frozen value instead of current setting."
                    )
                    self.settings.user_prompt_template = existing.user_prompt_template

            self.current_experiment = existing
            return existing

        # Create new experiment with frozen configuration
        config_json = json.dumps(self.settings.get_config_dict(), sort_keys=True, default=str)
        config_hash = self.settings.get_config_hash()

        experiment = Experiment(
            name=self.settings.experiment_name,
            config_json=config_json,
            config_hash=config_hash,
            system_prompt_template=self.settings.system_prompt,
            user_prompt_template=self.settings.user_prompt_template,
            description=f"Experiment created on {datetime.now().isoformat()}",
        )

        created = self._experiment_repository.create(experiment)
        logger.info(f"Created new experiment: {created.name} (hash={config_hash})")
        self.current_experiment = created
        return created

    def _create_shadow_experiment(self, run_id: str, config: dict[str, Any]) -> Experiment:
        """Create a shadow experiment for dev mode runs.

        In dev mode, we still need a valid experiment_id for question snapshots.
        This method creates a temporary "shadow" experiment that is uniquely
        associated with this specific run.

        Shadow experiments:
        - Are named automatically: "shadow-{run_id}"
        - Have frozen configuration like normal experiments
        - Ensure snapshots are isolated per run
        - Are marked with is_dev=True for identification

        Args:
            run_id: ID of the run this shadow experiment is for.
            config: Run configuration dictionary.

        Returns:
            Created Experiment object.
        """
        # Generate unique shadow experiment name
        shadow_name = f"shadow-{run_id}"

        # Check if shadow experiment already exists (shouldn't happen, but be safe)
        existing = self._experiment_repository.get_by_name(shadow_name)
        if existing:
            logger.warning(f"Shadow experiment already exists: {shadow_name}, reusing")
            self.current_experiment = existing
            return existing

        # Create shadow experiment with frozen configuration
        config_json = json.dumps(self.settings.get_config_dict() if self.settings else config, sort_keys=True, default=str)
        config_hash = self.settings.get_config_hash() if self.settings else str(hash(config_json))[:16]

        experiment = Experiment(
            name=shadow_name,
            config_json=config_json,
            config_hash=config_hash,
            system_prompt_template=self.settings.system_prompt if self.settings else None,
            user_prompt_template=self.settings.user_prompt_template if self.settings else None,
            description=f"Shadow experiment for dev mode run {run_id}, created on {datetime.now().isoformat()}",
        )

        created = self._experiment_repository.create(experiment)
        logger.info(f"Created shadow experiment: {created.name} (hash={config_hash})")
        self.current_experiment = created
        return created

    def _register_model_variant(self, model_id: str) -> str:
        """Register a model variant in the database.

        This method:
        1. Registers the base model if it doesn't exist
        2. Creates a variant config from current settings
        3. Generates variant_id and variant_signature
        4. Registers the variant if it doesn't exist
        5. Logs the registration with variant details

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4").

        Returns:
            The variant_id of the registered or existing variant.

        Example:
            >>> variant_id = manager._register_model_variant("openai/gpt-4")
            >>> print(variant_id)
            var-a1b2c3d4
        """
        # Step 1: Register base model if it doesn't exist
        existing_model = self._model_repository.get_by_id(model_id)
        if not existing_model:
            # Extract provider from model_id
            if "/" in model_id:
                parts = model_id.split("/", 1)
                provider = parts[0]
                model_name = parts[1] if len(parts) > 1 else model_id
            else:
                provider = "unknown"
                model_name = model_id

            model = Model(
                model_id=model_id,
                provider=provider,
                model_name=model_name,
            )

            try:
                self._model_repository.create(model)
                logger.debug(f"Registered base model: {model_id}")
            except sqlite3.IntegrityError:
                # Model might have been registered concurrently, ignore
                logger.debug(f"Base model registration conflict (ignored): {model_id}")

        # Step 2: Build variant config from settings
        # Priority: 1) reasoning_mode from Settings (explicit), 2) legacy reasoning_enabled/effort/max_tokens
        reasoning_mode = "unspecified"
        reasoning_effort = None
        reasoning_max_tokens = None

        if self.settings:
            # Check for explicit reasoning_mode first (new system)
            if hasattr(self.settings, 'reasoning_mode') and self.settings.reasoning_mode:
                reasoning_mode = self.settings.reasoning_mode
                
                # If mode is 'effort', get effort level
                if reasoning_mode == "effort" and self.settings.reasoning_effort:
                    reasoning_effort = self.settings.reasoning_effort
                
                # If mode is 'budget', get max tokens
                if reasoning_mode == "budget" and self.settings.reasoning_max_tokens is not None:
                    reasoning_max_tokens = self.settings.reasoning_max_tokens
            else:
                # Fallback to legacy reasoning configuration
                if self.settings.reasoning_enabled is False:
                    reasoning_mode = "off"
                elif self.settings.reasoning_effort:
                    reasoning_mode = "effort"
                    reasoning_effort = self.settings.reasoning_effort
                elif self.settings.reasoning_max_tokens is not None:
                    reasoning_mode = "budget"
                    reasoning_max_tokens = self.settings.reasoning_max_tokens
                elif self.settings.reasoning_enabled is True:
                    # reasoning_enabled=True without effort/tokens → use "auto"
                    reasoning_mode = "auto"

        variant_config = VariantConfig(
            reasoning_mode=reasoning_mode,
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
            vision_enabled=self.settings.enable_vision if self.settings else False,
            structured_enabled=self.settings.enable_structured if self.settings else False,
        )

        # Step 3: Generate variant_id and variant_signature
        variant_signature = variant_config.build_signature(model_id)
        variant_id = variant_config.build_variant_id(model_id)

        # Step 4: Check if variant already exists
        existing_variant = self._variant_repository.get_by_id(variant_id)
        if existing_variant:
            logger.debug(f"Variant already registered: {variant_id}")
            return variant_id

        # Step 5: Create variant record
        variant = ModelVariant(
            variant_id=variant_id,
            model_id=model_id,
            reasoning_mode=variant_config.reasoning_mode,
            reasoning_effort=variant_config.reasoning_effort,
            reasoning_max_tokens=variant_config.reasoning_max_tokens,
            vision_enabled=variant_config.vision_enabled,
            structured_enabled=variant_config.structured_enabled,
            variant_signature=variant_signature,
        )

        try:
            self._variant_repository.create(variant)
            logger.info(
                f"Registered model variant: {variant_id} | "
                f"model={model_id} | signature={variant_signature}"
            )
        except sqlite3.IntegrityError:
            # Variant might have been registered concurrently, ignore
            logger.debug(f"Variant registration conflict (ignored): {variant_id}")

        return variant_id

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

        # Set finished_at when completing or failing a run
        if status in ("completed", "failed") and run.finished_at is None:
            run.finished_at = datetime.now()
            logger.debug(f"Run {run_id} finished_at set to {run.finished_at}")

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

    def get_current_experiment_id(self) -> Optional[str]:
        """Get the experiment_id for the current run.

        This method is used to retrieve the experiment_id that should be
        used when creating question snapshots. Every run has an experiment_id
        (even dev mode runs with shadow experiments).

        Returns:
            The experiment_id string if available, None otherwise.

        Example:
            >>> experiment_id = run_manager.get_current_experiment_id()
            >>> if experiment_id:
            ...     snapshot_id = snapshot_repo.create_if_not_exists(
            ...         experiment_id=experiment_id,
            ...         question_id="Q001",
            ...         question_json=question_json
            ...     )
        """
        if self.current_run and self.current_run.experiment_id:
            return self.current_run.experiment_id
        if self.current_experiment and self.current_experiment.experiment_id:
            return self.current_experiment.experiment_id
        return None

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
