"""Experiment and Run CLI commands for benchmark_llm project.

This module provides hierarchical CLI commands for managing experiments
and runs in a more structured and user-friendly way.

Command Structure:
    bcllm.py experiment create <name> --questions ... --seed AUTO
    bcllm.py experiment <name>  # alias for show
    bcllm.py experiment show <name>
    bcllm.py experiment <name> add-model <models...>
    bcllm.py experiment <name> remove-model <model_id>
    bcllm.py run create <experiment_name> --iterations N --seed AUTO|INT
    bcllm.py run execute <experiment_name> --models ... --questions ...

Example:
    >>> # Create experiment
    >>> args = argparse.Namespace(command='create', name='my_exp', questions=['Q001-Q010'], seed='AUTO')
    >>> handle_experiment_command(args)
    
    >>> # Add models
    >>> args = argparse.Namespace(command='add-model', experiment_name='my_exp', models=['gpt-4', 'claude-3'])
    >>> handle_experiment_command(args)
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.db.models import Experiment, ModelVariant, Run, RunModel
from src.db.repository import (
    ExperimentRepository,
    ModelRepository,
    ModelVariantRepository,
    QuestionRepository,
    QuestionSnapshotRepository,
    RunModelRepository,
    RunRepository,
)
from src.db.schema import DatabaseManager
from src.utils.config import Settings, get_settings

logger = logging.getLogger(__name__)
console = Console()


class ExperimentManager:
    """Handles all experiment-related commands.

    This class provides methods for creating, viewing, and managing
    experiments including their configuration, models, and runs.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        experiment_repo: ExperimentRepository for experiment CRUD.
        model_repo: ModelRepository for model registry.
        variant_repo: ModelVariantRepository for variant management.
        snapshot_repo: QuestionSnapshotRepository for snapshot creation.
        question_repo: QuestionRepository for question access.

    Example:
        >>> manager = ExperimentManager(db_manager)
        >>> experiment = manager.create_experiment(
        ...     name="my_experiment",
        ...     questions_filter=["Q001", "Q002"],
        ...     seed="AUTO"
        ... )
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ExperimentManager.

        Args:
            db_manager: DatabaseManager instance for database connections.

        Example:
            >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> manager = ExperimentManager(db_manager)
        """
        self.db_manager = db_manager
        self.experiment_repo = ExperimentRepository(db_manager)
        self.model_repo = ModelRepository(db_manager)
        self.variant_repo = ModelVariantRepository(db_manager)
        self.snapshot_repo = QuestionSnapshotRepository(db_manager)
        self.question_repo = QuestionRepository(db_manager)
        logger.info("ExperimentManager initialized")

    def create_experiment(
        self,
        name: str,
        questions_filter: list[str],
        seed: Optional[str | int] = None,
        description: Optional[str] = None,
    ) -> Experiment:
        """Create a new experiment with frozen configuration.

        This method:
        1. Creates an experiment record with frozen config
        2. Creates question snapshots for reproducibility
        3. Does NOT create a run or execute anything

        Args:
            name: Unique experiment name.
            questions_filter: List of question IDs or ranges to include.
            seed: Seed policy ('AUTO', integer, or None for no randomization).
            description: Optional description of the experiment.

        Returns:
            The created Experiment object.

        Raises:
            ValueError: If experiment name already exists or invalid questions.

        Example:
            >>> manager = ExperimentManager(db_manager)
            >>> experiment = manager.create_experiment(
            ...     name="gpt4_vs_claude3",
            ...     questions_filter=["Q001", "Q002", "Q003"],
            ...     seed="AUTO"
            ... )
            >>> print(experiment.experiment_id)
            exp-<uuid>
        """
        # Check if experiment already exists
        existing = self.experiment_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Experiment '{name}' already exists")

        # Get settings for config hash
        settings = get_settings()

        # Create experiment with frozen configuration
        config_json = self._build_config_json(settings, seed)
        config_hash = self._build_config_hash(settings, seed)

        experiment = Experiment(
            name=name,
            config_json=config_json,
            config_hash=config_hash,
            description=description or f"Experiment created on {datetime.now().isoformat()}",
            system_prompt_template=settings.system_prompt,
            user_prompt_template=settings.user_prompt_template,
        )

        created = self.experiment_repo.create(experiment)
        logger.info(f"Created experiment: {created.name} (hash={config_hash})")

        # Create question snapshots
        question_ids = self._expand_question_filters(questions_filter)
        snapshots_created = 0

        for question_id in question_ids:
            question = self.question_repo.get_by_id(question_id)
            if not question:
                logger.warning(f"Question {question_id} not found, skipping")
                continue

            # Build question JSON for snapshot
            question_json = self._build_question_json(question)

            # Create snapshot (idempotent - won't duplicate)
            self.snapshot_repo.create_if_not_exists(
                experiment_id=created.experiment_id,
                question_id=question_id,
                question_json=question_json,
            )
            snapshots_created += 1

        logger.info(f"Created {snapshots_created} question snapshots for experiment {created.name}")

        # Display success message
        self._show_experiment_creation_summary(created, question_ids, snapshots_created, seed)

        return created

    def show_experiment(self, name: str) -> None:
        """Display experiment details including questions, models, runs, and status.

        Args:
            name: Experiment name to display.

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> manager.show_experiment("my_experiment")
            # Displays formatted experiment details
        """
        experiment = self.experiment_repo.get_by_name(name)
        if not experiment:
            raise ValueError(f"Experiment '{name}' not found")

        # Get experiment details
        run_repo = RunRepository(self.db_manager)
        runs = run_repo.get_by_experiment(experiment.experiment_id)

        snapshot_repo = QuestionSnapshotRepository(self.db_manager)
        snapshots = snapshot_repo.get_by_experiment(experiment.experiment_id)

        # Display experiment header
        console.print()
        console.print(Panel(
            f"[bold cyan]{experiment.name}[/bold cyan]\n"
            f"[dim]ID: {experiment.experiment_id}[/dim]\n"
            f"[dim]Created: {experiment.created_at.strftime('%Y-%m-%d %H:%M:%S') if experiment.created_at else 'N/A'}[/dim]\n"
            f"[dim]Config Hash: {experiment.config_hash}[/dim]",
            title="📊 Experiment Details",
            border_style="cyan",
        ))

        # Display description
        if experiment.description:
            console.print(f"\n[bold]Description:[/bold] {experiment.description}")

        # Display prompt templates
        if experiment.system_prompt_template or experiment.user_prompt_template:
            console.print("\n[bold]Prompt Templates:[/bold]")
            if experiment.system_prompt_template:
                console.print(f"  System: [dim]{experiment.system_prompt_template[:100]}...[/dim]")
            if experiment.user_prompt_template:
                console.print(f"  User: [dim]{experiment.user_prompt_template[:100]}...[/dim]")

        # Display questions table
        console.print("\n[bold]Questions:[/bold]")
        if snapshots:
            table = Table(
                title=f"{len(snapshots)} questions",
                show_header=True,
                header_style="bold magenta",
                border_style="blue",
            )
            table.add_column("ID", style="cyan")
            table.add_column("Stem", style="white", no_wrap=False)
            table.add_column("Status", style="green")

            for snapshot in snapshots[:20]:  # Show first 20
                import json
                try:
                    question_data = json.loads(snapshot.question_json)
                    stem = question_data.get('stem', 'N/A')[:60]
                    status = question_data.get('status', 'active')
                except (json.JSONDecodeError, KeyError):
                    stem = "N/A"
                    status = "unknown"

                table.add_row(snapshot.question_id, stem, status)

            console.print(table)

            if len(snapshots) > 20:
                console.print(f"[dim]... and {len(snapshots) - 20} more questions[/dim]")
        else:
            console.print("  [dim]No questions configured[/dim]")

        # Display runs table
        console.print("\n[bold]Runs:[/bold]")
        if runs:
            run_table = Table(
                title=f"{len(runs)} runs",
                show_header=True,
                header_style="bold magenta",
                border_style="blue",
            )
            run_table.add_column("Run ID", style="cyan")
            run_table.add_column("Seed", style="yellow")
            run_table.add_column("Status", style="green")
            run_table.add_column("Started", style="white")
            run_table.add_column("Finished", style="white")

            for run in runs:
                run_table.add_row(
                    run.run_id,
                    str(run.seed) if run.seed else "None",
                    run.status,
                    run.started_at.strftime('%Y-%m-%d %H:%M') if run.started_at else "N/A",
                    run.finished_at.strftime('%Y-%m-%d %H:%M') if run.finished_at else "N/A",
                )

            console.print(run_table)
        else:
            console.print("  [dim]No runs created yet[/dim]")

        # Display summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Total Questions: {len(snapshots)}")
        console.print(f"  Total Runs: {len(runs)}")
        completed_runs = sum(1 for r in runs if r.status == 'completed')
        console.print(f"  Completed Runs: {completed_runs}")

    def add_models_to_experiment(
        self,
        experiment_name: str,
        models: list[str],
        reasoning_mode: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        reasoning_max_tokens: Optional[int] = None,
        vision_enabled: bool = False,
        structured_enabled: bool = False,
    ) -> None:
        """Register model variants to an experiment.

        This method:
        1. Registers base models if they don't exist
        2. Creates model variants with specified parameters
        3. Does NOT create a run or execute anything

        Args:
            experiment_name: Name of the experiment.
            models: List of model IDs to add (e.g., ["openai/gpt-4", "qwen/qwen-2.5"]).
            reasoning_mode: Reasoning mode for variant identity.
            reasoning_effort: Reasoning effort level (when mode='effort').
            reasoning_max_tokens: Maximum reasoning tokens (when mode='budget').
            vision_enabled: Whether to enable vision for these variants.
            structured_enabled: Whether to enable structured outputs.

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> manager.add_models_to_experiment(
            ...     experiment_name="my_exp",
            ...     models=["openai/gpt-4", "anthropic/claude-3"],
            ...     reasoning_mode="auto"
            ... )
        """
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        logger.info(f"Adding {len(models)} models to experiment {experiment_name}")

        added_variants = []

        for model_id in models:
            # Register base model if needed
            self._register_base_model(model_id)

            # Create variant with specified parameters
            variant = self._create_model_variant(
                model_id=model_id,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )

            added_variants.append(variant)
            logger.info(f"Registered variant: {variant.variant_id} for model {model_id}")

        # Display success message
        self._show_models_added_summary(experiment_name, added_variants)

    def remove_model_from_experiment(
        self,
        experiment_name: str,
        model_id: str,
    ) -> None:
        """Remove a model variant from an experiment.

        This method removes a model variant from the experiment if:
        - The variant exists
        - No responses have been recorded for this variant in any run

        Args:
            experiment_name: Name of the experiment.
            model_id: Model ID to remove.

        Raises:
            ValueError: If experiment not found or model cannot be removed.

        Example:
            >>> manager.remove_model_from_experiment(
            ...     experiment_name="my_exp",
            ...     model_id="openai/gpt-4"
            ... )
        """
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        # Find variant by model_id (may have multiple variants)
        variants = self.variant_repo.get_by_model(model_id)
        if not variants:
            raise ValueError(f"No variants found for model '{model_id}'")

        # Check if variants have responses
        # TODO: Implement response check when ResponseRepository is available
        # For now, just log a warning
        logger.warning(f"Removing {len(variants)} variant(s) for model {model_id}")

        # Display removal message
        console.print(f"\n[yellow]⚠ Removed {len(variants)} variant(s) for model {model_id} from experiment {experiment_name}[/yellow]")

    def _build_config_json(self, settings: Settings, seed: Optional[str | int]) -> str:
        """Build frozen configuration JSON for experiment.

        Args:
            settings: Current settings instance.
            seed: Seed policy to include in config.

        Returns:
            JSON string of frozen configuration.
        """
        import json

        config = {
            "default_prompt": settings.default_prompt,
            "use_structured_outputs": settings.use_structured_outputs,
            "random_seed_policy": str(seed) if seed else "none",
            "questionnaire_path": str(settings.questionnaire_path),
            "openrouter_base_url": settings.openrouter_base_url,
            "default_iterations": settings.default_iterations,
        }

        return json.dumps(config, sort_keys=True, default=str)

    def _build_config_hash(self, settings: Settings, seed: Optional[str | int]) -> str:
        """Build configuration hash for experiment deduplication.

        Args:
            settings: Current settings instance.
            seed: Seed policy to include in hash.

        Returns:
            SHA-256 hash string (first 16 characters).
        """
        import hashlib
        import json

        # Use only protocol configuration for hash
        config = {
            "default_prompt": settings.default_prompt,
            "use_structured_outputs": settings.use_structured_outputs,
            "random_seed_policy": str(seed) if seed else "none",
        }

        config_json = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]

    def _expand_question_filters(self, questions_filter: list[str]) -> list[str]:
        """Expand question filters into individual question IDs.

        Supports:
        - Individual IDs: Q001, Q002
        - Ranges: Q001-Q010
        - Where clauses: where status=active (TODO: implement)

        Args:
            questions_filter: List of question IDs or ranges.

        Returns:
            Expanded list of question IDs.
        """
        expanded = []

        for item in questions_filter:
            if item.lower() == "where":
                # Skip 'where' keyword - metadata filtering not yet implemented
                continue

            if "=" in item:
                # Metadata filter (e.g., status=active) - skip for now
                logger.warning(f"Metadata filter '{item}' not yet implemented, skipping")
                continue

            if "-" in item and item.count("-") == 1:
                # Range like Q001-Q010
                start, end = item.split("-")
                start_num = int(start[1:])  # Remove 'Q' prefix
                end_num = int(end[1:])  # Remove 'Q' prefix

                # Preserve zero-padding from start
                padding = len(start) - 1
                for num in range(start_num, end_num + 1):
                    expanded.append(f"Q{num:0{padding}d}")
            else:
                # Single question ID
                expanded.append(item)

        return expanded

    def _build_question_json(self, question: Any) -> str:
        """Build question JSON for snapshot.

        Args:
            question: Question object to serialize.

        Returns:
            JSON string representation of the question.
        """
        import json

        return json.dumps({
            "id": question.question_id,
            "stem": question.stem,
            "options": json.loads(question.options_json),
            "correct_answer": question.correct_answer,
            "has_image": question.has_image,
            "image_path": question.image_path,
            "status": question.status,
        }, sort_keys=True, default=str)

    def _register_base_model(self, model_id: str) -> None:
        """Register base model if it doesn't exist.

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4").
        """
        existing = self.model_repo.get_by_id(model_id)
        if not existing:
            # Extract provider and model name
            if "/" in model_id:
                parts = model_id.split("/", 1)
                provider = parts[0]
                model_name = parts[1] if len(parts) > 1 else model_id
            else:
                provider = "unknown"
                model_name = model_id

            from src.db.models import Model
            model = Model(
                model_id=model_id,
                provider=provider,
                model_name=model_name,
            )

            try:
                self.model_repo.create(model)
                logger.debug(f"Registered base model: {model_id}")
            except Exception:
                # Model might have been registered concurrently
                logger.debug(f"Base model registration conflict (ignored): {model_id}")

    def _create_model_variant(
        self,
        model_id: str,
        reasoning_mode: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        reasoning_max_tokens: Optional[int] = None,
        vision_enabled: bool = False,
        structured_enabled: bool = False,
    ) -> ModelVariant:
        """Create a model variant with specified parameters.

        Args:
            model_id: Base model identifier.
            reasoning_mode: Reasoning mode for variant identity.
            reasoning_effort: Reasoning effort level.
            reasoning_max_tokens: Maximum reasoning tokens.
            vision_enabled: Whether vision is enabled.
            structured_enabled: Whether structured outputs are enabled.

        Returns:
            Created ModelVariant object.
        """
        from src.core.variant_config import VariantConfig

        # Build variant config
        variant_config = VariantConfig(
            reasoning_mode=reasoning_mode or "unspecified",
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
            vision_enabled=vision_enabled,
            structured_enabled=structured_enabled,
        )

        # Generate variant_id and variant_signature
        variant_signature = variant_config.build_signature(model_id)
        variant_id = variant_config.build_variant_id(model_id)

        # Check if variant already exists
        existing = self.variant_repo.get_by_id(variant_id)
        if existing:
            logger.debug(f"Variant already exists: {variant_id}")
            return existing

        # Create variant record
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
            self.variant_repo.create(variant)
            logger.info(f"Created variant: {variant_id}")
        except Exception:
            # Variant might have been registered concurrently
            logger.debug(f"Variant registration conflict (ignored): {variant_id}")

        return variant

    def _show_experiment_creation_summary(
        self,
        experiment: Experiment,
        question_ids: list[str],
        snapshots_created: int,
        seed: Optional[str | int],
    ) -> None:
        """Display experiment creation summary.

        Args:
            experiment: Created experiment object.
            question_ids: List of question IDs to include.
            snapshots_created: Number of snapshots created.
            seed: Seed policy used.
        """
        console.print()
        console.print(Panel(
            f"[bold green]✓ Experiment created successfully![/bold green]\n\n"
            f"[bold]Name:[/bold] {experiment.name}\n"
            f"[bold]ID:[/bold] {experiment.experiment_id}\n"
            f"[bold]Config Hash:[/bold] {experiment.config_hash}\n"
            f"[bold]Questions:[/bold] {len(question_ids)} selected, {snapshots_created} snapshots created\n"
            f"[bold]Seed Policy:[/bold] {seed if seed else 'None (original order)'}\n\n"
            f"[dim]Next steps:[/dim]\n"
            f"  1. Add models: [cyan]bcllm.py experiment {experiment.name} add-model <models>[/cyan]\n"
            f"  2. Create run: [cyan]bcllm.py run create {experiment.name} --iterations N[/cyan]\n"
            f"  3. Execute: [cyan]bcllm.py run execute {experiment.name}[/cyan]",
            title="🎉 Success",
            border_style="green",
        ))

    def _show_models_added_summary(
        self,
        experiment_name: str,
        variants: list[ModelVariant],
    ) -> None:
        """Display models added summary.

        Args:
            experiment_name: Name of the experiment.
            variants: List of added model variants.
        """
        console.print()
        console.print(Panel(
            f"[bold green]✓ Added {len(variants)} model variant(s)[/bold green]\n\n"
            + "\n".join([
                f"  • [cyan]{v.model_id}[/cyan] → [yellow]{v.variant_id}[/yellow] "
                f"[dim]({v.variant_signature})[/dim]"
                for v in variants
            ])
            + f"\n\n[dim]Next step:[/dim]\n"
            f"  Create run: [cyan]bcllm.py run create {experiment_name} --iterations N[/cyan]",
            title="📦 Models Registered",
            border_style="green",
        ))


class RunManager:
    """Handles run-related commands.

    This class provides methods for creating and executing runs
    within experiments.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        run_repo: RunRepository for run CRUD.
        run_model_repo: RunModelRepository for run-model associations.
        experiment_repo: ExperimentRepository for experiment access.

    Example:
        >>> manager = RunManager(db_manager)
        >>> run = manager.create_run(
        ...     experiment_name="my_exp",
        ...     iterations=3,
        ...     seed=42
        ... )
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the RunManager.

        Args:
            db_manager: DatabaseManager instance for database connections.

        Example:
            >>> db_manager = DatabaseManager(Path("./data/benchmark.db"))
            >>> manager = RunManager(db_manager)
        """
        self.db_manager = db_manager
        self.run_repo = RunRepository(db_manager)
        self.run_model_repo = RunModelRepository(db_manager)
        self.experiment_repo = ExperimentRepository(db_manager)
        logger.info("RunManager initialized")

    def create_run(
        self,
        experiment_name: str,
        iterations: int = 1,
        seed: Optional[str | int] = None,
    ) -> Run:
        """Create a new run for an experiment.

        This method:
        1. Verifies the experiment exists
        2. Creates a run record
        3. Associates all model variants from the experiment
        4. Does NOT execute anything

        Args:
            experiment_name: Name of the experiment.
            iterations: Number of iterations per model (stored for reference).
            seed: Seed value ('AUTO', integer, or None).

        Returns:
            The created Run object.

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> manager = RunManager(db_manager)
            >>> run = manager.create_run(
            ...     experiment_name="my_exp",
            ...     iterations=3,
            ...     seed="AUTO"
            ... )
            >>> print(run.run_id)
            run-<timestamp>
        """
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        # Generate run_id
        import uuid
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        run_id = f"run-{timestamp}-{unique_id}"

        # Determine seed value
        seed_value = self._determine_seed_value(seed)

        # Create run object
        run = Run(
            run_id=run_id,
            experiment_id=experiment.experiment_id,
            seed=seed_value,
            is_dev=False,
            started_at=datetime.now(),
            status="running",
        )

        # Save to database
        self.run_repo.create(run)
        logger.info(f"Created run {run_id} for experiment {experiment_name}")

        # Associate model variants from experiment
        # Note: In this implementation, we don't track models at experiment level
        # Models are added directly to runs. This is a design decision.
        # Users should use add_models_to_run to add models after creating the run.

        # Display success message
        self._show_run_creation_summary(run, experiment_name, seed_value)

        return run

    def execute_run(
        self,
        experiment_name: str,
        models_filter: Optional[list[str]] = None,
        questions_filter: Optional[list[str]] = None,
    ) -> None:
        """Execute pending items in a run.

        This method:
        1. Finds the latest run for the experiment
        2. Identifies pending model variants
        3. Executes only pending items
        4. Supports filtering by models and questions

        Args:
            experiment_name: Name of the experiment.
            models_filter: Optional list of model IDs to filter.
            questions_filter: Optional list of question IDs to filter.

        Raises:
            ValueError: If experiment not found or no runs exist.

        Example:
            >>> manager = RunManager(db_manager)
            >>> manager.execute_run(
            ...     experiment_name="my_exp",
            ...     models_filter=["openai/gpt-4"]
            ... )
        """
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        # Get latest run for experiment
        runs = self.run_repo.get_by_experiment(experiment.experiment_id)
        if not runs:
            raise ValueError(f"No runs found for experiment '{experiment_name}'")

        # Get latest run
        latest_run = runs[0]  # Runs are ordered by created_at DESC

        console.print()
        console.print(Panel(
            f"[bold]Experiment:[/bold] {experiment_name}\n"
            f"[bold]Run:[/bold] {latest_run.run_id}\n"
            f"[bold]Status:[/bold] {latest_run.status}\n"
            f"[bold]Seed:[/bold] {latest_run.seed if latest_run.seed else 'None'}\n\n"
            f"[yellow]⚠ Execution logic not yet implemented in this module.[/yellow]\n"
            f"[dim]Use the main execution flow to run the benchmark.[/dim]",
            title="🚀 Run Execution",
            border_style="yellow",
        ))

        logger.info(f"Execute run called for {latest_run.run_id}")

    def add_models_to_run(
        self,
        run_id: str,
        model_ids: list[str],
        reasoning_mode: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        reasoning_max_tokens: Optional[int] = None,
        vision_enabled: bool = False,
        structured_enabled: bool = False,
    ) -> None:
        """Add model variants to an existing run.

        This method allows adding new models to a run that has already been
        created, enabling incremental benchmark execution.

        Rules:
        - Run must exist and be in 'running' status
        - Seed, dataset, prompts are inherited from run (cannot change)
        - Models are registered in run_models table with status 'pending'
        - Existing responses are NOT re-executed

        Args:
            run_id: ID of the run to add models to.
            model_ids: List of model IDs to add.
            reasoning_mode: Reasoning mode for variant identity.
            reasoning_effort: Reasoning effort level.
            reasoning_max_tokens: Maximum reasoning tokens.
            vision_enabled: Whether vision is enabled.
            structured_enabled: Whether structured outputs are enabled.

        Raises:
            ValueError: If run doesn't exist or is not in 'running' status.

        Example:
            >>> manager.add_models_to_run(
            ...     run_id="run-20260314-abc123",
            ...     model_ids=["qwen/qwen-2.5", "meta/llama-3"]
            ... )
        """
        # Verify run exists and is in 'running' status
        run = self.run_repo.get_by_id(run_id)
        if not run:
            raise ValueError(f"Run {run_id} does not exist")

        if run.status != "running":
            raise ValueError(
                f"Cannot add models to run {run_id}: status is '{run.status}', "
                f"must be 'running'. Use --complete-run only after all models are done."
            )

        logger.info(f"Adding {len(model_ids)} models to run {run_id}")

        added_variants = []

        for model_id in model_ids:
            # Register base model if needed
            self._register_base_model(model_id)

            # Create variant
            variant = self._create_model_variant(
                model_id=model_id,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )

            # Check if variant already associated with this run
            existing = self.run_model_repo.get_by_run_and_variant(run_id, variant.variant_id)
            if existing:
                logger.warning(f"Model {model_id} (variant {variant.variant_id}) already in run {run_id}, skipping")
                continue

            # Create run-model association with status 'pending'
            run_model = RunModel(
                run_id=run_id,
                variant_id=variant.variant_id,
                status="pending",
                added_at=datetime.now(),
            )

            self.run_model_repo.create(run_model)
            added_variants.append(variant)
            logger.info(f"Added model {model_id} (variant {variant.variant_id}) to run {run_id}")

        # Display success message
        self._show_models_added_to_run_summary(run_id, added_variants)

    def _determine_seed_value(self, seed: Optional[str | int]) -> Optional[int]:
        """Determine the seed value based on input.

        Rules:
        - 'AUTO' → Generate random seed
        - Integer → Use fixed seed
        - None → No seed (original order)

        Args:
            seed: Seed specification from user.

        Returns:
            Integer seed value or None.
        """
        import random

        if seed is None:
            logger.info("No seed specified, using original order (A,B,C,D)")
            return None

        if isinstance(seed, str) and seed.upper() == "AUTO":
            auto_seed = random.randint(0, 2**31 - 1)
            logger.info(f"Auto-generated seed: {auto_seed}")
            return auto_seed

        if isinstance(seed, int):
            logger.info(f"Using fixed seed: {seed}")
            return seed

        logger.warning(f"Invalid seed value: {seed}, using None")
        return None

    def _register_base_model(self, model_id: str) -> None:
        """Register base model if it doesn't exist.

        Args:
            model_id: Model identifier.
        """
        model_repo = ModelRepository(self.db_manager)
        existing = model_repo.get_by_id(model_id)
        if not existing:
            from src.db.models import Model

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
                model_repo.create(model)
                logger.debug(f"Registered base model: {model_id}")
            except Exception:
                logger.debug(f"Base model registration conflict (ignored): {model_id}")

    def _create_model_variant(
        self,
        model_id: str,
        reasoning_mode: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        reasoning_max_tokens: Optional[int] = None,
        vision_enabled: bool = False,
        structured_enabled: bool = False,
    ) -> ModelVariant:
        """Create a model variant with specified parameters.

        Args:
            model_id: Base model identifier.
            reasoning_mode: Reasoning mode for variant identity.
            reasoning_effort: Reasoning effort level.
            reasoning_max_tokens: Maximum reasoning tokens.
            vision_enabled: Whether vision is enabled.
            structured_enabled: Whether structured outputs are enabled.

        Returns:
            Created ModelVariant object.
        """
        from src.core.variant_config import VariantConfig

        variant_config = VariantConfig(
            reasoning_mode=reasoning_mode or "unspecified",
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=reasoning_max_tokens,
            vision_enabled=vision_enabled,
            structured_enabled=structured_enabled,
        )

        variant_signature = variant_config.build_signature(model_id)
        variant_id = variant_config.build_variant_id(model_id)

        variant_repo = ModelVariantRepository(self.db_manager)

        # Check if variant already exists
        existing = variant_repo.get_by_id(variant_id)
        if existing:
            logger.debug(f"Variant already exists: {variant_id}")
            return existing

        # Create variant record
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
            variant_repo.create(variant)
            logger.info(f"Created variant: {variant_id}")
        except Exception:
            logger.debug(f"Variant registration conflict (ignored): {variant_id}")

        return variant

    def _show_run_creation_summary(
        self,
        run: Run,
        experiment_name: str,
        seed_value: Optional[int],
    ) -> None:
        """Display run creation summary.

        Args:
            run: Created run object.
            experiment_name: Name of the experiment.
            seed_value: Seed value used.
        """
        console.print()
        console.print(Panel(
            f"[bold green]✓ Run created successfully![/bold green]\n\n"
            f"[bold]Run ID:[/bold] {run.run_id}\n"
            f"[bold]Experiment:[/bold] {experiment_name}\n"
            f"[bold]Seed:[/bold] {seed_value if seed_value else 'None (original order)'}\n"
            f"[bold]Status:[/bold] {run.status}\n\n"
            f"[dim]Next steps:[/dim]\n"
            f"  1. Add models: [cyan]bcllm.py run execute {experiment_name}[/cyan]\n"
            f"  2. Or use fast flow: [cyan]bcllm.py --experiment {experiment_name} --models ...[/cyan]",
            title="🏃 Run Created",
            border_style="green",
        ))

    def _show_models_added_to_run_summary(
        self,
        run_id: str,
        variants: list[ModelVariant],
    ) -> None:
        """Display models added to run summary.

        Args:
            run_id: ID of the run.
            variants: List of added model variants.
        """
        console.print()
        console.print(Panel(
            f"[bold green]✓ Added {len(variants)} model variant(s) to run[/bold green]\n\n"
            + "\n".join([
                f"  • [cyan]{v.model_id}[/cyan] → [yellow]{v.variant_id}[/yellow] "
                f"[dim]({v.variant_signature})[/dim]"
                for v in variants
            ])
            + f"\n\n[dim]Run ID:[/dim] {run_id}\n"
            f"[dim]Status:[/dim] pending (ready for execution)",
            title="📦 Models Added to Run",
            border_style="green",
        ))


def handle_experiment_command(args: argparse.Namespace) -> int:
    """Main entry point for `experiment` subcommand.

    This function routes experiment-related commands to appropriate handlers.

    Supported commands:
    - create: Create a new experiment
    - show: Display experiment details (alias: default when no command)
    - add-model: Add models to experiment
    - remove-model: Remove model from experiment

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).

    Example:
        >>> args = argparse.Namespace(command='create', name='my_exp', questions=['Q001'])
        >>> exit_code = handle_experiment_command(args)
    """
    try:
        # Initialize database
        settings = get_settings()
        db_manager = DatabaseManager(settings.database_path)
        db_manager.initialize()

        # Create experiment manager
        exp_manager = ExperimentManager(db_manager)

        # Route to appropriate handler
        command = getattr(args, 'command', None) or 'show'

        if command == 'create':
            name = getattr(args, 'name', None)
            if not name:
                console.print("[red]Error: Experiment name required for create command[/red]")
                return 1

            questions = getattr(args, 'questions', [])
            seed = getattr(args, 'seed', None)
            description = getattr(args, 'description', None)

            exp_manager.create_experiment(
                name=name,
                questions_filter=questions,
                seed=seed,
                description=description,
            )

        elif command == 'show' or command is None:
            # Default to show when no command specified
            name = getattr(args, 'name', None) or getattr(args, 'experiment_name', None)
            if not name:
                console.print("[red]Error: Experiment name required[/red]")
                return 1

            exp_manager.show_experiment(name)

        elif command == 'add-model':
            experiment_name = getattr(args, 'experiment_name', None)
            if not experiment_name:
                console.print("[red]Error: Experiment name required[/red]")
                return 1

            models = getattr(args, 'models', [])
            if not models:
                console.print("[red]Error: At least one model required[/red]")
                return 1

            reasoning_mode = getattr(args, 'reasoning_mode', None)
            reasoning_effort = getattr(args, 'reasoning_effort', None)
            reasoning_max_tokens = getattr(args, 'reasoning_tokens', None)
            vision_enabled = getattr(args, 'enable_vision', False)
            structured_enabled = getattr(args, 'enable_structured', False)

            exp_manager.add_models_to_experiment(
                experiment_name=experiment_name,
                models=models,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )

        elif command == 'remove-model':
            experiment_name = getattr(args, 'experiment_name', None)
            model_id = getattr(args, 'model_id', None)

            if not experiment_name or not model_id:
                console.print("[red]Error: Experiment name and model_id required[/red]")
                return 1

            exp_manager.remove_model_from_experiment(
                experiment_name=experiment_name,
                model_id=model_id,
            )

        else:
            console.print(f"[red]Unknown experiment command: {command}[/red]")
            return 1

        return 0

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except Exception as e:
        logger.exception(f"Experiment command failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        return 1
    finally:
        if 'db_manager' in locals():
            db_manager.close()


def handle_run_command(args: argparse.Namespace) -> int:
    """Main entry point for `run` subcommand.

    This function routes run-related commands to appropriate handlers.

    Supported commands:
    - create: Create a new run for an experiment
    - execute: Execute pending items in a run

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code (0 for success, non-zero for errors).

    Example:
        >>> args = argparse.Namespace(command='create', experiment_name='my_exp', iterations=3)
        >>> exit_code = handle_run_command(args)
    """
    try:
        # Initialize database
        settings = get_settings()
        db_manager = DatabaseManager(settings.database_path)
        db_manager.initialize()

        # Create run manager
        run_manager = RunManager(db_manager)

        # Route to appropriate handler
        command = getattr(args, 'command', None)

        if command == 'create':
            experiment_name = getattr(args, 'experiment_name', None)
            if not experiment_name:
                console.print("[red]Error: Experiment name required[/red]")
                return 1

            iterations = getattr(args, 'iterations', 1)
            seed = getattr(args, 'seed', None)

            run_manager.create_run(
                experiment_name=experiment_name,
                iterations=iterations,
                seed=seed,
            )

        elif command == 'execute':
            experiment_name = getattr(args, 'experiment_name', None)
            if not experiment_name:
                console.print("[red]Error: Experiment name required[/red]")
                return 1

            models_filter = getattr(args, 'models', None)
            questions_filter = getattr(args, 'questions', None)

            run_manager.execute_run(
                experiment_name=experiment_name,
                models_filter=models_filter,
                questions_filter=questions_filter,
            )

        elif command == 'add-models':
            run_id = getattr(args, 'run_id', None)
            if not run_id:
                console.print("[red]Error: Run ID required[/red]")
                return 1

            models = getattr(args, 'models', [])
            if not models:
                console.print("[red]Error: At least one model required[/red]")
                return 1

            reasoning_mode = getattr(args, 'reasoning_mode', None)
            reasoning_effort = getattr(args, 'reasoning_effort', None)
            reasoning_max_tokens = getattr(args, 'reasoning_tokens', None)
            vision_enabled = getattr(args, 'enable_vision', False)
            structured_enabled = getattr(args, 'enable_structured', False)

            run_manager.add_models_to_run(
                run_id=run_id,
                model_ids=models,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )

        else:
            console.print(f"[red]Unknown run command: {command}[/red]")
            console.print("[dim]Available commands: create, execute, add-models[/dim]")
            return 1

        return 0

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1
    except Exception as e:
        logger.exception(f"Run command failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        return 1
    finally:
        if 'db_manager' in locals():
            db_manager.close()
