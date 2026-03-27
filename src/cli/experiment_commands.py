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
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.db.models import Experiment, ModelVariant, Run
from src.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
)
from src.db.schema import create_schema
from src.cli.database import get_database_connection, get_database_path
from src.utils.config import Settings, get_settings
from src.core.config_resolver import ConfigResolver

logger = logging.getLogger(__name__)
console = Console()


class DatabaseManager:
    """Simple database manager wrapper for backward compatibility.
    
    This class provides a consistent interface for database operations.
    """
    
    def __init__(self, db_path):
        """Initialize with database path."""
        self.db_path = db_path
        self.conn = None
    
    def initialize(self):
        """Initialize database connection and schema."""
        import sqlite3
        from pathlib import Path
        
        # Create data directory if needed
        db_path = Path(self.db_path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        
        # Initialize schema
        create_schema(self.conn)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


class ExperimentManager:
    """Handles all experiment-related commands.

    This class provides methods for creating, viewing, and managing
    experiments including their configuration, models, and runs.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        experiment_repo: ExperimentRepository for experiment CRUD.
        variant_repo: VariantRepository for variant management.
        snapshot_repo: SnapshotRepository for snapshot creation.
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
        self.experiment_repo = ExperimentRepository(db_manager.conn)
        self.variant_repo = VariantRepository(db_manager.conn)
        self.snapshot_repo = SnapshotRepository(db_manager.conn)
        logger.info("ExperimentManager initialized")

    def create_experiment(
        self,
        name: str,
        questions_spec: Optional[str] = None,
        where_filters: Optional[list[str]] = None,
        exclude_filters: Optional[list[str]] = None,
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
            questions_spec: Question position specification (e.g., "1-10", "1 5 10", None for all).
            where_filters: List of inclusion filters (e.g., ["status=valid"]).
            exclude_filters: List of exclusion filters (e.g., ["status=annulled"]).
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
            ...     questions_spec="1-10",
            ...     where_filters=["status=valid"],
            ...     seed="AUTO"
            ... )
            >>> print(experiment.experiment_id)
            exp-<uuid>
        """
        # === VALIDATION PHASE ===
        
        # 1. Empty experiment name
        if not name or not name.strip():
            raise ValueError("Experiment name cannot be empty")
        
        name = name.strip()
        
        # 2. Duplicate experiment name
        existing = self.experiment_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Experiment '{name}' already exists")
        
        # 3. Validate filter syntax (before loading dataset)
        if where_filters:
            for f in where_filters:
                try:
                    self._parse_filter(f)
                except ValueError as e:
                    raise ValueError(f"Invalid --where filter '{f}': {e}")
        
        if exclude_filters:
            for f in exclude_filters:
                try:
                    self._parse_filter(f)
                except ValueError as e:
                    raise ValueError(f"Invalid --exclude filter '{f}': {e}")
        
        # === END VALIDATION PHASE ===

        # Get settings for config hash
        settings = get_settings()

        # Validate dataset path exists (7. Dataset existence)
        if not settings.questionnaire_path.exists():
            raise ValueError(f"Questions dataset not found at {settings.questionnaire_path}. Set QUESTIONS_DATASET_PATH in .env.")

        # Generate experiment_id
        import uuid
        experiment_id = f"exp_{uuid.uuid4().hex[:8]}"

        # Create experiment with frozen configuration
        config_json = self._build_config_json(settings, seed)
        config_hash = self._build_config_hash(settings, seed)

        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            config_json=config_json,
            config_hash=config_hash,
            description=description or f"Experiment created on {datetime.now().isoformat()}",
        )

        self.experiment_repo.save(experiment)
        created = self.experiment_repo.get_by_id(experiment_id)
        logger.info(f"Created experiment: {created.name} (hash={config_hash})")

        # Create question snapshots
        # CRITICAL: Load questions from JSON dataset (SOURCE OF TRUTH)
        # Questions are NOT persisted to a separate table - only as snapshots
        from src.core.loader import QuestionLoader

        # Step 1: Load ALL questions from JSON dataset (source of truth)
        loader = QuestionLoader(str(settings.questionnaire_path))
        all_questions = loader.load()
        total_count = len(all_questions)
        
        # Validate dataset has questions (no placeholders)
        if total_count == 0:
            raise ValueError(f"Questions dataset is empty or contains no valid questions: {settings.questionnaire_path}")

        # Step 2: Assign internal IDs (positions) to questions
        questions_with_positions = []
        for idx, q in enumerate(all_questions, start=1):
            questions_with_positions.append({
                'internal_id': idx,
                'question_id': q.question_id,
                'stem': q.stem,
                'options': json.loads(q.options_json),
                'correct_answer': q.correct_answer,
                'has_image': q.has_image,
                'image_path': q.image_path,
                'status': q.status,
            })

        # Step 3: Determine which positions to snapshot
        if questions_spec is None:
            # No specification - use all positions
            positions = list(range(1, total_count + 1))
            logger.info(f"No questions specified, using all {len(positions)} available questions")
        else:
            # Parse position specification
            positions = self._parse_question_positions(questions_spec, total_count)
            logger.info(f"Parsed question positions: {positions}")

        # Step 4: Apply filters
        parsed_where = []
        parsed_exclude = []
        
        if where_filters:
            for f in where_filters:
                parsed_where.append(self._parse_filter(f))
        
        if exclude_filters:
            for f in exclude_filters:
                parsed_exclude.append(self._parse_filter(f))

        if parsed_where or parsed_exclude:
            positions = self._filter_questions_by_position(
                positions, questions_with_positions, parsed_where, parsed_exclude
            )
            logger.info(f"After filtering: {len(positions)} positions remain")
            
            # Validate that at least one question remains after filtering
            if len(positions) == 0:
                raise ValueError("No questions match the specified filters")

        # Step 5: Build question lookup by position
        question_lookup = {q['internal_id']: q for q in questions_with_positions}

        # Step 6: Create question snapshots
        snapshots_created = 0

        for position in positions:
            question = question_lookup.get(position)
            if not question:
                logger.warning(f"Question at position {position} not found in dataset, skipping")
                continue

            # Build question JSON for snapshot
            question_json = self._build_question_json_from_dict(question)

            # Create snapshot (idempotent - won't duplicate)
            self.snapshot_repo.create_if_not_exists(
                experiment_id=created.experiment_id,
                question_id=question['question_id'],
                question_payload=question_json,
                question_position=position,  # Store numeric position
            )
            snapshots_created += 1

        logger.info(f"Created {snapshots_created} question snapshots for experiment {created.name}")

        # Display success message
        self._show_experiment_creation_summary(created, positions, snapshots_created, seed)

        return created

    def _build_question_json_from_dict(self, question: dict) -> str:
        """Build question JSON for snapshot from dictionary.

        Args:
            question: Question dictionary with keys: question_id, stem, options, etc.

        Returns:
            JSON string representation of the question.
        """
        import json

        return json.dumps({
            "id": question['question_id'],
            "stem": question['stem'],
            "options": question['options'],
            "correct_answer": question['correct_answer'],
            "has_image": question['has_image'],
            "image_path": question['image_path'],
            "status": question['status'],
        }, sort_keys=True, default=str)

    def add_questions_to_experiment(
        self,
        experiment_name: str,
        questions: list[str],
    ) -> None:
        """Add questions to an existing experiment (experiment evolution).

        This method creates snapshots for NEW questions only.
        Existing snapshots are NEVER recreated (immutability principle).

        PRINCIPLES:
        - Experiments can EVOLVE
        - Runs are IMMUTABLE
        - Past is NEVER altered
        - Snapshots are created only once per (experiment_id, question_id)

        Args:
            experiment_name: Name of the experiment.
            questions: List of question IDs or ranges to add (e.g., ["Q021-Q040"]).

        Raises:
            ValueError: If experiment not found.

        Example:
            >>> manager.add_questions_to_experiment(
            ...     experiment_name="my_exp",
            ...     questions=["Q021-Q040"]
            ... )
        """
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        # Expand question filters
        question_ids = self._expand_question_filters([questions] if isinstance(questions, str) else questions)
        logger.info(f"Adding {len(question_ids)} questions to experiment {experiment_name}")

        # Get settings for snapshot creation
        settings = get_settings()

        # Load questions from JSON dataset (SOURCE OF TRUTH)
        from src.core.loader import QuestionLoader
        loader = QuestionLoader(str(settings.questionnaire_path))
        all_questions = loader.load()
        question_lookup = {q.question_id: q for q in all_questions}

        # Create question snapshots (only for NEW questions)
        # The create_if_not_exists method ensures existing snapshots are NOT recreated
        existing_snapshot_count = len(self.snapshot_repo.get_by_experiment(experiment.experiment_id))

        for question_id in question_ids:
            question = question_lookup.get(question_id)
            if not question:
                logger.warning(f"Question {question_id} not found in dataset, skipping")
                continue

            # Build question JSON for snapshot
            question_json = self._build_question_json(question)

            # Create snapshot (idempotent - won't duplicate)
            # If snapshot already exists, returns existing snapshot_id
            self.snapshot_repo.create_if_not_exists(
                experiment_id=experiment.experiment_id,
                question_id=question_id,
                question_payload=question_json,
            )

        # Get total snapshots after operation
        all_snapshots = self.snapshot_repo.get_by_experiment(experiment.experiment_id)
        new_snapshots_count = len(all_snapshots) - existing_snapshot_count
        
        logger.info(f"Snapshot operation completed for experiment {experiment_name}: {new_snapshots_count} new snapshots created")

        # Display success message
        console.print()
        console.print(Panel(
            f"[bold green]✓ Questions added to experiment[/bold green]\n\n"
            f"[bold]Experiment:[/bold] {experiment_name}\n"
            f"[bold]Questions requested:[/bold] {len(question_ids)}\n"
            f"[bold]New snapshots created:[/bold] {new_snapshots_count}\n"
            f"[bold]Total snapshots in experiment:[/bold] {len(all_snapshots)}\n\n"
            f"[dim]Principle: Experiments can evolve, runs are immutable.[/dim]\n"
            f"[dim]Existing runs continue using their original question set.[/dim]\n"
            f"[dim]Future runs will use the updated question set.[/dim]",
            title="📈 Experiment Evolution",
            border_style="green",
        ))

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

        # Display configured models
        self._show_experiment_models(experiment.experiment_id)

    def _show_experiment_models(self, experiment_id: str) -> None:
        """Display all model variants (global, not experiment-specific).

        Note: In TO-BE architecture, variants are GLOBAL.

        Args:
            experiment_id: ID of the experiment (unused).
        """
        console.print("\n[bold]Model Variants (Global):[/bold]")

        # Get all variants (global, not experiment-specific)
        variants = self.variant_repo.get_all()

        if not variants:
            console.print("  [dim]No model variants configured[/dim]")
            return

        # Display variants
        console.print(f"  {len(variants)} variant(s) configured:\n")

        for idx, variant in enumerate(variants, start=1):
            # Build model info string
            info_parts = []
            if variant.reasoning_effort:
                info_parts.append(f"reasoning={variant.reasoning_effort}")
            elif variant.reasoning_mode == "off":
                info_parts.append("reasoning=off")
            if variant.vision_enabled:
                info_parts.append("vision")
            if variant.structured_output:
                info_parts.append("structured")

            info_str = f" ({', '.join(info_parts)})" if info_parts else ""
            console.print(f"  [cyan][{idx}][/cyan] {variant.model_id} → {variant.variant_id}{info_str}")

    def _show_all_experiment_models(self, experiment_id: str) -> None:
        """Display all model variants (for UX after add-model).

        Note: In TO-BE architecture, variants are GLOBAL.

        Args:
            experiment_id: ID of the experiment (unused).
        """
        variants = self.variant_repo.get_all()

        if not variants:
            return

        console.print("\n[bold]Model Variants Available:[/bold]")
        for idx, variant in enumerate(variants, start=1):
            info_parts = []
            if variant.reasoning_effort:
                info_parts.append(f"reasoning={variant.reasoning_effort}")
            elif variant.reasoning_mode == "off":
                info_parts.append("reasoning=off")
            if variant.vision_enabled:
                info_parts.append("vision")
            if variant.structured_output:
                info_parts.append("structured")

            info_str = f" ({', '.join(info_parts)})" if info_parts else ""
            console.print(f"  [cyan][{idx}][/cyan] {variant.model_id}{info_str}")

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
            ValueError: If experiment not found or invalid model/boolean values.

        Example:
            >>> manager.add_models_to_experiment(
            ...     experiment_name="my_exp",
            ...     models=["openai/gpt-4", "anthropic/claude-3"],
            ...     reasoning_mode="auto"
            ... )
        """
        # === VALIDATION PHASE ===
        
        # 4. Boolean value validation (vision/structured)
        # Note: vision_enabled and structured_enabled are already bool type from argparse
        # This validation is for programmatic calls or future CLI extensions
        
        # 5. Model ID format validation
        for model_id in models:
            if not self._validate_model_id(model_id):
                raise ValueError(f"Invalid model ID format: {model_id}. Expected: provider/model-name (e.g., openai/gpt-4)")
        
        # === END VALIDATION PHASE ===
        
        # Verify experiment exists
        experiment = self.experiment_repo.get_by_name(experiment_name)
        if not experiment:
            raise ValueError(f"Experiment '{experiment_name}' not found")

        logger.info(f"Adding {len(models)} models to experiment {experiment_name}")

        added_variants = []

        for model_id in models:
            # Create variant with specified parameters
            # Note: model_id is just a string identifier in model_variants table
            # No separate base model registration needed in TO-BE architecture
            variant = self._create_model_variant(
                model_id=model_id,
                reasoning_mode=reasoning_mode,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )

            # Note: In TO-BE architecture, variants are GLOBAL (not tied to experiments)
            # Variants are filtered at execution time via --models flag
            # No association table needed

            added_variants.append(variant)
            logger.info(f"Registered variant: {variant.variant_id} for model {model_id}")

        # Display success message with full model list
        self._show_models_added_summary(experiment_name, added_variants)

    def remove_model_from_experiment(
        self,
        experiment_name: str,
        model_id: str,
    ) -> None:
        """Remove a model variant from an experiment.

        Note: In TO-BE architecture, variants are GLOBAL and not associated with experiments.
        This command is deprecated - variant filtering happens at execution time via --models flag.

        Args:
            experiment_name: Name of the experiment.
            model_id: Model ID (ignored in TO-BE architecture).

        Raises:
            ValueError: Always raises - this operation is not supported.
        """
        raise ValueError(
            "Removing models from experiments is not supported in TO-BE architecture. "
            "Variants are global and filtered at execution time via --models flag. "
            "Example: bcllm.py --experiment NAME --run --models openai/gpt-4"
        )

    def _remove_model_interactive(self, experiment_name: str, experiment_id: str) -> None:
        """Interactive mode for removing models.

        Args:
            experiment_name: Name of the experiment.
            experiment_id: ID of the experiment.
        """
        # Get all models from experiment_models (NEW - direct association)
        variants = self.exp_model_repo.get_by_experiment(experiment_id)

        if not variants:
            console.print("\n[yellow]⚠ No models configured.[/yellow]")
            return

        # Display models with index
        console.print()
        console.print(Panel(
            "[bold]Select models to remove:[/bold]\n\n"
            + "\n".join([
                f"  [cyan][{idx}][/cyan] {variant.model_id}" +
                (f" [dim](reasoning={variant.reasoning_effort})[/dim]" if variant.reasoning_effort else "") +
                (f" [dim](reasoning=off)[/dim]" if variant.reasoning_mode == "off" and not variant.reasoning_effort else "")
                for idx, variant in enumerate(variants, start=1)
            ])
            + "\n\n[dim]Select models to remove:[/dim]\n"
            "  [bold]Single:[/bold] 3\n"
            "  [bold]Multiple:[/bold] 1,3,4\n"
            "  [bold]Range:[/bold] 1-4\n"
            "  [bold]Cancel:[/bold] q or Ctrl+C",
            title="🗑️  Remove Models",
            border_style="yellow",
        ))

        # Read user input
        try:
            user_input = input("\nSelect models to remove: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled.[/dim]")
            return

        # Handle cancel
        if user_input.lower() in ('q', 'quit', 'cancel', 'c'):
            console.print("\n[dim]Cancelled.[/dim]")
            return

        # Parse input
        indices_to_remove = self._parse_model_indices(user_input, len(variants))

        if not indices_to_remove:
            console.print("\n[red]✗ No valid models selected.[/red]")
            return

        # Get variants to remove
        variants_to_remove = [variants[i - 1] for i in indices_to_remove]

        # Show what will be removed
        console.print(f"\n[yellow]⚠ About to remove {len(variants_to_remove)} variant(s):[/yellow]")
        for variant in variants_to_remove:
            console.print(f"  • {variant.model_id}")

        # Confirm
        try:
            confirm = input("\nConfirm removal? (y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Cancelled.[/dim]")
            return

        if confirm != 'y':
            console.print("\n[dim]Cancelled.[/dim]")
            return

        # Remove variants from experiment
        removed_count = 0
        for variant in variants_to_remove:
            if self.exp_model_repo.remove_variant(experiment_id, variant.variant_id):
                removed_count += 1

        console.print(f"\n[green]✓ Removed {removed_count} model variant(s) from experiment.[/green]")

    def _parse_model_indices(self, user_input: str, total_count: int) -> list[int]:
        """Parse user input for model selection (returns indices).

        Args:
            user_input: User's selection input (e.g., "1,3,4" or "1-4").
            total_count: Total number of models available.

        Returns:
            List of indices (1-based) to remove.
        """
        selected_indices = []

        # Split by comma
        parts = user_input.replace(' ', '').split(',')

        for part in parts:
            if '-' in part and part.count('-') == 1:
                # Range: 1-4
                try:
                    start, end = part.split('-')
                    start_num = int(start)
                    end_num = int(end)
                    for num in range(start_num, min(end_num + 1, total_count + 1)):
                        if 1 <= num <= total_count:
                            selected_indices.append(num)
                except ValueError:
                    continue
            else:
                # Single number
                try:
                    num = int(part)
                    if 1 <= num <= total_count:
                        selected_indices.append(num)
                except ValueError:
                    continue

        # Remove duplicates while preserving order
        seen = set()
        unique_indices = []
        for idx in selected_indices:
            if idx not in seen:
                seen.add(idx)
                unique_indices.append(idx)

        return unique_indices

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
            reasoning_effort: Reasoning effort level ('none' means disable reasoning).
            reasoning_max_tokens: Maximum reasoning tokens.
            vision_enabled: Whether vision is enabled.
            structured_enabled: Whether structured outputs are enabled.

        Returns:
            Created ModelVariant object.
        """
        from src.core.variant_config import VariantConfig

        # Normalize reasoning_effort: 'none' means disable reasoning (mode='off')
        if reasoning_effort == 'none':
            reasoning_mode = "off"
            reasoning_effort = None
        elif reasoning_effort is not None:
            # If reasoning_effort is specified, mode should be 'effort'
            reasoning_mode = "effort"

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

        # Check if variant already exists BEFORE trying to create
        existing = self.variant_repo.get_by_id(variant_id)
        if existing:
            logger.info(f"Variant already exists: {variant_id}")
            return existing

        # Create variant record
        # Note: reasoning_max_tokens is NOT persisted - it's execution-time only
        # Only max_output_tokens (total output limit) is part of variant identity
        variant = ModelVariant(
            variant_id=variant_id,
            model_id=model_id,
            reasoning_mode=variant_config.reasoning_mode,
            reasoning_effort=variant_config.reasoning_effort,
            # max_output_tokens is NOT set here - it's a separate parameter if needed
            vision_enabled=variant_config.vision_enabled,
            structured_output=variant_config.structured_enabled,  # Note: ModelVariant uses structured_output
            variant_signature=variant_signature,
        )

        self.variant_repo.create(variant)
        logger.info(f"Created variant: {variant_id}")

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
            f"[bold]Questions:[/bold] {f'{len(question_ids)} selected, {snapshots_created} snapshots created' if question_ids else 'Will be resolved when creating a run'}\n"
            f"[bold]Seed Policy:[/bold] {seed if seed else 'None (original order)'}\n\n"
            f"[dim]Next steps:[/dim]\n"
            f"  1. Add models: [cyan]bcllm.py --experiment {experiment.name} --add-model <model>[/cyan]\n"
            f"  2. Create run: [cyan]bcllm.py --experiment {experiment.name} --create-run --iterations N[/cyan]\n"
            f"  3. Execute: [cyan]bcllm.py --experiment {experiment.name} --run[/cyan]",
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

    @staticmethod
    def _parse_filter(filter_str: str) -> tuple[str, str]:
        """Parse a filter string into field and value.

        Args:
            filter_str: Filter in format "field=value".

        Returns:
            Tuple of (field, value).

        Raises:
            ValueError: If filter format is invalid.
        """
        if '=' not in filter_str:
            raise ValueError(f"Invalid filter format: {filter_str} (expected field=value)")

        field, value = filter_str.split('=', 1)
        return field.strip(), value.strip()

    @staticmethod
    def _get_nested_field(obj: dict, field_path: str) -> str | None:
        """Get a nested field from a dictionary.

        Supports three access patterns:
        1. Direct field: obj['status']
        2. Dot notation: obj['meta']['status'] for field_path='meta.status'
        3. Recursive search: searches through nested dicts for field_path='status'

        Args:
            obj: Dictionary to search.
            field_path: Field path (e.g., "status" or "meta.status").

        Returns:
            Field value as string, or None if not found.
        """
        if '.' in field_path:
            parts = field_path.split('.')
            current = obj
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return str(current) if current is not None else None

        if field_path in obj:
            return str(obj[field_path]) if obj[field_path] is not None else None

        for key, value in obj.items():
            if key == field_path:
                return str(value) if value is not None else None
            if isinstance(value, dict):
                result = ExperimentManager._get_nested_field(value, field_path)
                if result is not None:
                    return result

        return None

    @staticmethod
    def _matches_filters(
        question: dict,
        include_filters: list[tuple[str, str]] | None = None,
        exclude_filters: list[tuple[str, str]] | None = None,
    ) -> bool:
        """Check if a question matches the given filters.

        Args:
            question: Question data dictionary.
            include_filters: List of (field, value) pairs for inclusion.
            exclude_filters: List of (field, value) pairs for exclusion.

        Returns:
            True if question passes all filters, False otherwise.
        """
        if exclude_filters:
            for field, value in exclude_filters:
                if ExperimentManager._get_nested_field(question, field) == value:
                    return False

        if include_filters:
            for field, value in include_filters:
                if ExperimentManager._get_nested_field(question, field) != value:
                    return False

        return True

    @staticmethod
    def _filter_questions_by_position(
        positions: list[int],
        questions: list[dict],
        include_filters: list[tuple[str, str]] | None = None,
        exclude_filters: list[tuple[str, str]] | None = None,
    ) -> list[int]:
        """Filter question positions based on inclusion and exclusion criteria.

        Args:
            positions: List of question positions to filter.
            questions: List of question data dictionaries (with internal_id/position).
            include_filters: List of (field, value) pairs for inclusion.
            exclude_filters: List of (field, value) pairs for exclusion.

        Returns:
            Filtered list of question positions.
        """
        # Build index by position
        questions_index = {q.get('internal_id'): q for q in questions if q.get('internal_id') is not None}
        
        filtered = []
        for pos in positions:
            if pos not in questions_index:
                continue
            
            question = questions_index[pos]
            if ExperimentManager._matches_filters(question, include_filters, exclude_filters):
                filtered.append(pos)
        
        return filtered

    @staticmethod
    def _parse_question_positions(spec: str, total_count: int) -> list[int]:
        """Parse question position specification into list of positions.

        Supports:
        - Individual positions: "1", "5", "10"
        - Ranges: "1-10" (positions 1 through 10)
        - Comma-separated: "1, 3, 5"
        - Mixed: "1, 3-5, 10"

        Args:
            spec: Position specification string.
            total_count: Total number of questions in dataset (for range validation).

        Returns:
            List of validated positions (1-indexed).

        Raises:
            ValueError: If specification format is invalid.
        """
        positions = []
        
        # Split by comma first (handles "1, 3, 5" format)
        parts = spec.split(',')
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if '-' in part and part.count('-') == 1:
                # Range: 1-10
                try:
                    start, end = part.split('-')
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    if start_num < 1 or end_num > total_count:
                        raise ValueError(f"Range {start_num}-{end_num} out of bounds (1-{total_count})")
                    if start_num > end_num:
                        raise ValueError(f"Invalid range: start ({start_num}) > end ({end_num})")
                    for num in range(start_num, end_num + 1):
                        positions.append(num)
                except ValueError as e:
                    if "invalid literal" in str(e):
                        raise ValueError(f"Invalid range format: {part} (expected start-end)")
                    raise
            else:
                # Single number
                try:
                    num = int(part)
                    if num < 1 or num > total_count:
                        raise ValueError(f"Position {num} out of bounds (1-{total_count})")
                    positions.append(num)
                except ValueError as e:
                    if "invalid literal" in str(e):
                        raise ValueError(f"Invalid position format: {part} (expected integer)")
                    raise
        
        # Remove duplicates while preserving order
        seen = set()
        unique_positions = []
        for pos in positions:
            if pos not in seen:
                seen.add(pos)
                unique_positions.append(pos)
        
        return unique_positions

    @staticmethod
    def _validate_bool_value(value: str | None) -> bool:
        """Validate boolean CLI value.

        Args:
            value: String value to validate.

        Returns:
            True if valid (case-insensitive true/false/null), False otherwise.
        """
        if value is None:
            return True
        normalized = value.lower()
        return normalized in ('true', 'false', 'null')

    @staticmethod
    def _validate_model_id(model_id: str) -> bool:
        """Validate model ID format.

        Args:
            model_id: Model ID to validate.

        Returns:
            True if valid format (provider/model-name), False otherwise.
        """
        if not model_id or '/' not in model_id:
            return False
        
        parts = model_id.split('/')
        if len(parts) != 2:
            return False
        
        provider, model = parts
        if not provider.strip() or not model.strip():
            return False
        
        return True


class RunManager:
    """Handles run-related commands.

    This class provides methods for creating and executing runs
    within experiments.

    Attributes:
        db_manager: DatabaseManager instance for database operations.
        run_repo: RunRepository for run CRUD.
        experiment_repo: ExperimentRepository for experiment access.
        variant_repo: ModelVariantRepository for variant access.

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
        self.experiment_repo = ExperimentRepository(db_manager)
        self.variant_repo = ModelVariantRepository(db_manager)
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

        # Determine seed value with source information
        seed_value, seed_source = self._determine_seed_value(seed)

        # Create run object
        run = Run(
            run_id=run_id,
            experiment_id=experiment.experiment_id,
            seed=seed_value,
            started_at=datetime.now(),
            status="running",
        )

        # Save to database
        self.run_repo.create(run)
        logger.info(f"Created run {run_id} for experiment {experiment_name}")

        # Note: In TO-BE architecture, variants are NOT associated with runs at creation time.
        # Variant filtering happens at execution time via --models flag.
        # The Planner resolves which variants to execute based on the model_filter parameter.

        # Display success message
        self._show_run_creation_summary(run, experiment_name, seed_value, seed_source)

        return run

    def execute_run(
        self,
        experiment_name: str,
        models_filter: Optional[list[str]] = None,
        questions_filter: Optional[list[str]] = None,
    ) -> None:
        """DEPRECATED: Execution is now ONLY via BenchmarkRunner.

        This method is intentionally disabled.
        All execution MUST go through:
        BenchmarkRunner._handle_execute_run() → Planner → ExecutionEngine → ResultWriter
        """
        raise NotImplementedError(
            "execute_run() is deprecated. "
            "Execution must go through BenchmarkRunner._handle_execute_run(). "
            "See: Planner → ExecutionEngine → ResultWriter"
        )

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

        Note: This method is DEPRECATED in TO-BE architecture.
        Run-model associations are no longer used.
        Models are filtered at execution time via --models flag.

        Args:
            run_id: ID of the run to add models to.
            model_ids: List of model IDs to add.

        Raises:
            NotImplementedError: Always raised - method is deprecated.
        """
        raise NotImplementedError(
            "add_models_to_run is deprecated in TO-BE architecture. "
            "Models are filtered at execution time via --models flag."
        )

    def _determine_seed_value(self, seed: Optional[str | int]) -> tuple[Optional[int], str]:
        """Determine the seed value based on input.

        Rules:
        - 'AUTO' → Generate random seed
        - Integer → Use fixed seed
        - None → No seed (original order)

        Args:
            seed: Seed specification from user.

        Returns:
            Tuple of (integer seed value or None, source description).
        """
        import random

        if seed is None:
            logger.info("No seed specified, using original order (A,B,C,D)")
            return None, "using default (off)"

        if isinstance(seed, str) and seed.upper() == "AUTO":
            auto_seed = random.randint(0, 2**31 - 1)
            logger.info(f"Auto-generated seed: {auto_seed}")
            return auto_seed, "auto-generated"

        if isinstance(seed, int):
            logger.info(f"Using fixed seed: {seed}")
            return seed, f"fixed ({seed})"

        logger.warning(f"Invalid seed value: {seed}, using None")
        return None, "using default (off)"

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
        seed_source: str = "",
    ) -> None:
        """Display run creation summary.

        Args:
            run: Created run object.
            experiment_name: Name of the experiment.
            seed_value: Seed value used.
            seed_source: Source of the seed value (for feedback).
        """
        seed_display = f"{seed_value} ({seed_source})" if seed_value else f"None ({seed_source})"
        
        console.print()
        console.print(Panel(
            f"[bold green]✓ Run created successfully![/bold green]\n\n"
            f"[bold]Run ID:[/bold] {run.run_id}\n"
            f"[bold]Experiment:[/bold] {experiment_name}\n"
            f"[bold]Seed:[/bold] {seed_display}\n"
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
        exp_command = getattr(args, 'exp_command', None) or 'show'

        if exp_command == 'create':
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

        elif exp_command == 'show' or exp_command is None:
            # Default to show when no command specified
            name = getattr(args, 'name', None) or getattr(args, 'experiment_name', None)
            if not name:
                console.print("[red]Error: Experiment name required[/red]")
                return 1

            exp_manager.show_experiment(name)

        elif exp_command == 'add-model':
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

        elif exp_command == 'remove-model':
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
            console.print(f"[red]Unknown experiment command: {exp_command}[/red]")
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
        run_command = getattr(args, 'run_command', None)

        if run_command == 'create':
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

        elif run_command == 'execute':
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

        elif run_command == 'add-models':
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
            console.print(f"[red]Unknown run command: {run_command}[/red]")
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
