"""Main entry point for benchmark_llm project.

This module provides the main entry point for the benchmark tool,
wiring together CLI argument parsing, execution engine, statistics
calculation, and output formatting.
"""

import asyncio
import json
import logging
import random
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path
from typing import Optional

from src.cli.cli import CLIParser, parse_arguments
from src.cli.output_formatter import ConsoleFormatter, OutputFormatter, create_formatter
from src.cli.statistics import StatisticsCalculator
from src.core.randomizer import AnswerRandomizer
from src.core.run_manager import RunManager
from src.db.schema import DatabaseManager
from src.utils.config import get_settings
from src.utils.logging_config import LoggingConfig, setup_logging, log_initialization_summary
from rich.console import Console

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Main orchestrator for benchmark execution.

    This class coordinates all components of the benchmark tool:
    - CLI argument parsing
    - Configuration loading
    - Database initialization
    - Test execution
    - Statistics calculation
    - Output formatting

    Attributes:
        args: Parsed command-line arguments.
        settings: Application settings from environment.
        db_manager: Database manager instance.
        run_manager: Run manager for benchmark lifecycle.

    Example:
        >>> runner = BenchmarkRunner()
        >>> runner.run()
    """

    def __init__(self, args: Optional[Namespace] = None) -> None:
        """Initialize the benchmark runner.

        Args:
            args: Optional pre-parsed arguments. If None, parses
                 command-line arguments.

        Example:
            >>> runner = BenchmarkRunner()
            >>> runner.run()
        """
        self.args = args or parse_arguments()
        self.settings = get_settings()
        self.db_manager: Optional[DatabaseManager] = None
        self.run_manager: Optional[RunManager] = None

        # Setup logging with LoggingConfig
        log_config = LoggingConfig(
            log_file_path=self.settings.log_file_path,
            log_level=self.settings.log_level,
        )
        setup_logging(log_config)

        logger.info("BenchmarkRunner initialized")
        logger.debug(f"Arguments: {self.args}")
        
        # Apply CLI args to settings
        self._apply_cli_reasoning_args()
        self._apply_cli_generation_args()

    def _apply_cli_reasoning_args(self) -> None:
        """Apply CLI reasoning arguments to settings.
        
        Simplified: Only --reasoning-effort is now supported.
        - reasoning_effort: Set directly; 'none' means disable reasoning
        - If not specified, no reasoning config is sent to API (model default)
        """
        if self.args.reasoning_effort:
            self.settings.reasoning_effort = self.args.reasoning_effort
            logger.info(f"Set reasoning_effort from CLI: {self.args.reasoning_effort}")

        if hasattr(self.args, 'enable_vision') and self.args.enable_vision:
            self.settings.enable_vision = True
            logger.info(f"Set enable_vision from CLI: True")

        if hasattr(self.args, 'enable_structured') and self.args.enable_structured:
            self.settings.enable_structured = True
            logger.info(f"Set enable_structured from CLI: True")

    def _apply_cli_generation_args(self) -> None:
        """Apply CLI generation arguments to settings."""
        if getattr(self.args, "temperature", None) is not None:
            self.settings.model_temperature = self.args.temperature
            logger.info(f"Set model_temperature from CLI: {self.args.temperature}")
            
        if getattr(self.args, "max_tokens", None) is not None:
            self.settings.model_max_tokens = self.args.max_tokens
            logger.info(f"Set model_max_tokens from CLI: {self.args.max_tokens}")
            
        if getattr(self.args, "top_p", None) is not None:
            self.settings.model_top_p = self.args.top_p
            logger.info(f"Set model_top_p from CLI: {self.args.top_p}")
            
        if getattr(self.args, "top_k", None) is not None:
            self.settings.model_top_k = self.args.top_k
            logger.info(f"Set model_top_k from CLI: {self.args.top_k}")
            
        if getattr(self.args, "repeat_penalty", None) is not None:
            self.settings.model_repeat_penalty = self.args.repeat_penalty
            logger.info(f"Set model_repeat_penalty from CLI: {self.args.repeat_penalty}")

    def _apply_execution_mode(self) -> None:
        """Apply execution mode from CLI to settings.

        This method configures settings based on the execution mode:
        - TEST: in-memory DB, no persistence
        - DEV: default DB, full persistence
        - EXPERIMENT: default DB, frozen configuration
        """
        # Set execution mode from CLI
        if hasattr(self.args, 'execution_mode'):
            from src.utils.config import ExecutionMode
            self.settings.execution_mode = ExecutionMode(self.args.execution_mode)
        
        # Set experiment name if provided
        if hasattr(self.args, 'experiment_name') and self.args.experiment_name:
            self.settings.experiment_name = self.args.experiment_name
        
        # Apply mode-specific presets
        if self.settings.is_test_mode:
            # Test mode: in-memory database
            self.settings.database_path = Path(":memory:")
            logger.info("TEST MODE: Using in-memory database, no persistence")
        elif self.settings.is_experiment_mode:
            logger.info(f"EXPERIMENT MODE: Configuration frozen (hash={self.settings.get_config_hash()})")
        else:
            logger.info("DEV MODE: Full persistence enabled")

    def _handle_review_experiment(self) -> int:
        """Handle manual review for an experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.review_ui import ReviewUI

            # Initialize database
            self._init_database()

            # Create review UI and start review
            ui = ReviewUI(self.db_manager)
            ui.start_review_by_experiment(self.args.review_experiment)

            return 0
        except Exception as e:
            logger.exception(f"Review failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def _handle_review_run(self) -> int:
        """Handle manual review for a run.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.review_ui import ReviewUI

            # Initialize database
            self._init_database()

            # Create review UI and start review
            ui = ReviewUI(self.db_manager)
            ui.start_review_by_run(self.args.review_run)

            return 0
        except Exception as e:
            logger.exception(f"Review failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def _handle_review_all(self) -> int:
        """Handle manual review for all pending responses.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.review_ui import ReviewUI

            # Initialize database
            self._init_database()

            # Create review UI and start review
            ui = ReviewUI(self.db_manager)
            ui.start_review_all()

            return 0
        except Exception as e:
            logger.exception(f"Review failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def run(self) -> int:
        """Execute the benchmark.

        Main entry point that orchestrates the entire benchmark process.

        Returns:
            Exit code (0 for success, non-zero for errors).

        Example:
            >>> runner = BenchmarkRunner()
            >>> exit_code = runner.run()
        """
        try:
            # Handle experiment management flags (NEW CLI paradigm)
            if hasattr(self.args, 'create_experiment') and self.args.create_experiment:
                return self._handle_create_experiment()
            if hasattr(self.args, 'experiment') and self.args.experiment:
                return self._handle_experiment_context()

            # Handle manual review commands
            if self.args.review_experiment:
                return self._handle_review_experiment()
            if self.args.review_run:
                return self._handle_review_run()
            if self.args.review_all:
                return self._handle_review_all()

            # Handle add-models-to-run command
            if self.args.add_to_run:
                return self._handle_add_models_to_run()

            # Handle complete-run command
            if self.args.complete_run:
                return self._handle_complete_run()

            # Apply execution mode presets
            self._apply_execution_mode()

            # Validate configuration
            if not self._validate_config():
                return 1

            # Initialize database
            self._init_database()

            # Log initialization summary
            self._log_initialization()

            # Handle dry run
            if self.args.dry_run:
                logger.info("Dry run mode - validation only")
                print("Configuration validated successfully (dry run)")
                return 0

            # Execute benchmark
            results = self._execute_benchmark()

            # Calculate and display statistics
            self._display_results(results)

            return 0

        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user")
            print("\nBenchmark interrupted by user")
            return 130
        except Exception as e:
            logger.exception(f"Benchmark failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def _handle_create_experiment(self) -> int:
        """Handle --create-experiment flag.

        Creates a new experiment with frozen configuration and question snapshots.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import ExperimentManager
            from src.utils.config_hierarchy import format_config_summary, resolve_with_feedback, ConfigSource

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create experiment manager
            exp_manager = ExperimentManager(db_manager)

            # Get arguments
            name = self.args.create_experiment
            
            # CRITICAL: Validate questions dataset path
            # The JSON dataset is the SOURCE OF TRUTH for questions
            if not settings.questions_dataset_path.exists():
                console = Console()
                console.print(f"[yellow]⚠ WARNING: Questions dataset not found at {settings.questions_dataset_path}[/yellow]")
                console.print("[dim]Set QUESTIONS_DATASET_PATH in .env to specify the correct path.[/dim]")
            
            # Resolve questions with hierarchy: CLI > .env > default (all from JSON)
            cli_questions = self.args.questions if self.args.questions else None
            
            # If CLI questions not provided, check for DEFAULT_QUESTIONS in .env
            if cli_questions is None:
                env_questions = settings.default_questions if hasattr(settings, 'default_questions') and settings.default_questions else None
            else:
                env_questions = None
                
            default_questions = None  # None means "all questions from JSON"
            
            questions, questions_msg = resolve_with_feedback(
                cli_value=cli_questions,
                env_value=env_questions,
                default_value=default_questions,
                config_name="Questions",
                cli_flag_name="--questions",
            )
            
            # Convert questions string to list (handle ranges like "Q001-Q005")
            if questions and isinstance(questions, str):
                # Parse questions string (could be "Q001,Q002" or "Q001-Q005")
                from src.cli.cli import CLIParser
                parser = CLIParser()
                questions = parser._expand_question_ranges([questions])
            
            # Convert None to empty list (means "all questions from JSON")
            # This is the default behavior: use ALL questions from JSON if nothing specified
            if questions is None:
                questions = []
                # Only show feedback if not already set by resolve_with_feedback
                if questions_msg is None:
                    questions_msg = "Questions: using all available questions from dataset (default)"
            
            # Resolve seed with hierarchy: CLI > .env > default (None)
            cli_seed = self.args.seed if hasattr(self.args, 'seed') and self.args.seed else None
            env_seed = settings.random_seed if hasattr(settings, 'random_seed') else None
            default_seed = None
            
            seed, seed_msg = resolve_with_feedback(
                cli_value=cli_seed,
                env_value=env_seed,
                default_value=default_seed,
                config_name="Seed",
                cli_flag_name="--seed",
            )
            
            description = self.args.description if hasattr(self.args, 'description') else None

            # Create experiment
            exp_manager.create_experiment(
                name=name,
                questions_filter=questions,
                seed=seed,
                description=description,
            )

            # Show configuration summary (feedback for assumed values)
            config_messages = [questions_msg, seed_msg]
            format_config_summary(config_messages, title="Configuration")

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Create experiment failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_experiment_context(self) -> int:
        """Handle --experiment flag (context for other operations).

        Routes to appropriate handler based on additional flags:
        - --experiment NAME (alone) → show experiment
        - --experiment NAME --add-model → add models
        - --experiment NAME --add-questions → add questions (evolution)
        - --experiment NAME --remove-model → remove model
        - --experiment NAME --create-run → create run
        - --experiment NAME --run → execute run

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            experiment_name = self.args.experiment

            # Route based on action flags
            if hasattr(self.args, 'add_questions') and self.args.add_questions:
                return self._handle_add_questions_to_experiment(experiment_name)
            elif hasattr(self.args, 'add_models') and self.args.add_models:
                return self._handle_add_models_to_experiment(experiment_name)
            elif hasattr(self.args, 'remove_model') and self.args.remove_model:
                return self._handle_remove_model_from_experiment(experiment_name)
            elif hasattr(self.args, 'create_run') and self.args.create_run:
                return self._handle_create_run(experiment_name)
            elif hasattr(self.args, 'execute_run') and self.args.execute_run:
                return self._handle_execute_run(experiment_name)
            else:
                # Default: show experiment details
                return self._handle_show_experiment(experiment_name)

        except Exception as e:
            logger.exception(f"Experiment context handler failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1

    def _handle_show_experiment(self, experiment_name: str) -> int:
        """Show experiment details.

        Args:
            experiment_name: Name of the experiment to show.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import ExperimentManager

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create experiment manager
            exp_manager = ExperimentManager(db_manager)

            # Show experiment
            exp_manager.show_experiment(experiment_name)

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Show experiment failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_add_questions_to_experiment(self, experiment_name: str) -> int:
        """Handle --add-questions flag (experiment evolution).

        This command adds new questions to an existing experiment.
        
        PRINCIPLES:
        - Experiments can EVOLVE
        - Runs are IMMUTABLE
        - Past is NEVER altered
        
        BEHAVIOR:
        - Existing snapshots are NOT recreated
        - New snapshots are created ONLY for new questions
        - Existing runs continue using their original question set
        - Future runs will use the updated question set
        
        Args:
            experiment_name: Name of the experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import ExperimentManager

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create experiment manager
            exp_manager = ExperimentManager(db_manager)

            # Get questions to add
            questions_to_add = self.args.add_questions
            
            # Add questions to experiment
            exp_manager.add_questions_to_experiment(
                experiment_name=experiment_name,
                questions=questions_to_add,
            )

            # Show feedback
            console = Console()
            console.print(f"\n[green]✓ Questions added to experiment '{experiment_name}'[/green]")
            console.print("[dim]Note: Existing runs are NOT affected. Only future runs will use the new questions.[/dim]")

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Add questions failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_add_models_to_experiment(self, experiment_name: str) -> int:
        """Add models to experiment.

        Args:
            experiment_name: Name of the experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import ExperimentManager

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create experiment manager
            exp_manager = ExperimentManager(db_manager)

            # Get models from --add-model flags
            models = self.args.add_models

            # Get variant parameters
            # Simplified: Only reasoning_effort is now supported
            reasoning_effort = getattr(self.args, 'reasoning_effort', None)
            vision_enabled = getattr(self.args, 'enable_vision', False)
            structured_enabled = getattr(self.args, 'enable_structured', False)

            # Add models
            exp_manager.add_models_to_experiment(
                experiment_name=experiment_name,
                models=models,
                reasoning_mode=None,  # Removed - use reasoning_effort only
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=None,  # Removed
                vision_enabled=vision_enabled,
                structured_enabled=structured_enabled,
            )
            
            logger.info(f"Models added successfully to experiment {experiment_name}")

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Add models to experiment failed: {e}")
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_remove_model_from_experiment(self, experiment_name: str) -> int:
        """Remove model from experiment.

        Args:
            experiment_name: Name of the experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import ExperimentManager

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create experiment manager
            exp_manager = ExperimentManager(db_manager)

            # Remove model
            model_id = self.args.remove_model
            
            # Handle missing argument
            if not model_id:
                console = Console()
                console.print("[red]Error: --remove-model requires an argument.[/red]")
                console.print("[dim]Use --remove-model <ids> or --remove-model ? for assisted mode.[/dim]")
                return 1
            
            exp_manager.remove_model_from_experiment(
                experiment_name=experiment_name,
                model_id=model_id,
            )

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Remove model from experiment failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_create_run(self, experiment_name: str) -> int:
        """Create a new run for experiment.

        Args:
            experiment_name: Name of the experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import RunManager as ExRunManager
            from src.utils.config_hierarchy import format_config_summary, resolve_with_feedback

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create run manager
            run_manager = ExRunManager(db_manager)

            # Get parameters
            iterations = getattr(self.args, 'iterations', 1)
            
            # Resolve seed with hierarchy: CLI > .env > default (None)
            cli_seed = getattr(self.args, 'seed', None)
            env_seed = settings.random_seed if hasattr(settings, 'random_seed') else None
            default_seed = None
            
            seed, seed_msg = resolve_with_feedback(
                cli_value=cli_seed,
                env_value=env_seed,
                default_value=default_seed,
                config_name="Seed",
                cli_flag_name="--seed",
            )

            # Create run
            run_manager.create_run(
                experiment_name=experiment_name,
                iterations=iterations,
                seed=seed,
            )

            # Show configuration summary (feedback for assumed values)
            config_messages = [seed_msg]
            format_config_summary(config_messages, title="Configuration")

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Create run failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_execute_run(self, experiment_name: str) -> int:
        """Execute experiment run.

        Args:
            experiment_name: Name of the experiment.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            from src.cli.experiment_commands import RunManager as ExRunManager

            # Initialize database
            settings = get_settings()
            db_manager = DatabaseManager(settings.database_path)
            db_manager.initialize()

            # Create run manager
            run_manager = ExRunManager(db_manager)

            # Get filters
            models_filter = getattr(self.args, 'models', None)
            questions_filter = getattr(self.args, 'questions', None)

            # Execute run
            run_manager.execute_run(
                experiment_name=experiment_name,
                models_filter=models_filter,
                questions_filter=questions_filter,
            )

            return 0

        except ValueError as e:
            console = Console()
            console.print(f"[red]Error: {e}[/red]")
            return 1
        except Exception as e:
            logger.exception(f"Execute run failed: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            if 'db_manager' in locals():
                db_manager.close()

    def _handle_add_models_to_run(self) -> int:
        """Handle adding models to an existing run.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            # Validate arguments
            if not self.args.add_models:
                print(
                    "Error: --add-models is required when using --add-to-run",
                    file=sys.stderr,
                )
                return 1

            # Initialize database
            self._init_database()

            # Create run manager
            run_manager = RunManager(self.db_manager, self.settings)

            # Add models to run
            run_id = self.args.add_to_run
            model_ids = self.args.add_models

            print(f"Adding {len(model_ids)} models to run {run_id}...")
            logger.info(f"Adding models {model_ids} to run {run_id}")

            run_manager.add_models_to_run(run_id, model_ids)

            print(f"Successfully added {len(model_ids)} models to run {run_id}")
            print("\nModels added:")
            for model_id in model_ids:
                print(f"  - {model_id}")

            print("\nTo execute the new models, run the benchmark again with the same parameters.")
            print("The system will automatically skip questions already answered by these models.")

            return 0

        except ValueError as e:
            logger.error(f"Failed to add models: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except Exception as e:
            logger.exception(f"Failed to add models: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def _handle_complete_run(self) -> int:
        """Handle marking a run as completed.

        Returns:
            Exit code (0 for success, non-zero for errors).
        """
        try:
            # Initialize database
            self._init_database()

            # Get run manager
            run_manager = RunManager(self.db_manager, self.settings)

            # Complete the run
            run_id = self.args.complete_run

            print(f"Marking run {run_id} as completed...")
            logger.info(f"Completing run {run_id}")

            run = run_manager.get_run_by_id(run_id)
            if run is None:
                print(f"Error: Run {run_id} not found", file=sys.stderr)
                return 1

            # Update run status
            run_manager.update_run_status(run_id, "completed")

            # Also mark all pending models as completed
            from src.db.repository import RunModelRepository
            run_model_repo = RunModelRepository(self.db_manager)

            for run_model in run_model_repo.get_by_run(run_id):
                if run_model.status == "pending":
                    run_manager.complete_run_model(run_id, run_model.variant_id)

            print(f"Run {run_id} marked as completed")
            print("\nNo more models can be added to this run.")

            return 0

        except Exception as e:
            logger.exception(f"Failed to complete run: {e}")
            print(f"Error: {e}", file=sys.stderr)
            return 1
        finally:
            self._cleanup()

    def _validate_config(self) -> bool:
        """Validate the configuration.

        Returns:
            True if configuration is valid, False otherwise.
        """
        # Check if models are specified (--run-id or --models)
        has_run_id = hasattr(self.args, 'run_id') and self.args.run_id
        if not self.args.models and not has_run_id:
            print("Error: At least one model must be specified with --models, or use --run-id to re-execute a run.", file=sys.stderr)
            return False

        # Check API key if not in dry-run mode
        if not self.args.dry_run and not self.settings.is_api_configured:
            print(
                "Error: OpenRouter API key not configured. "
                "Set OPENROUTER_API_KEY environment variable.",
                file=sys.stderr,
            )
            return False

        # Validate iterations
        if self.args.iterations < 1:
            print("Error: Iterations must be at least 1", file=sys.stderr)
            return False

        # Validate experiment mode requirements
        if self.settings.is_experiment_mode and not self.settings.experiment_name:
            print(
                "Error: Experiment name is required for experiment mode. "
                "Use --experiment <name> to specify the experiment.",
                file=sys.stderr,
            )
            return False

        # Log mode-specific messages
        if self.settings.is_test_mode:
            print("⚠️  TEST MODE: Results will not be persisted")
            logger.info("Running in test mode with in-memory database")
        elif self.settings.is_experiment_mode:
            print(f"🧪 EXPERIMENT MODE: {self.settings.experiment_name}")
            logger.info(f"Running in experiment mode: {self.settings.experiment_name}")

        logger.info("Configuration validated")
        return True

    def _init_database(self) -> None:
        """Initialize the database connection and schema.

        Database path is already set by _apply_execution_mode() based on mode.
        """
        # Ensure data directory exists (skip for in-memory)
        if str(self.settings.database_path) != ":memory:":
            self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_manager = DatabaseManager(self.settings.database_path)
        self.db_manager.initialize()
        self.run_manager = RunManager(self.db_manager, self.settings)

        logger.info(f"Database initialized at {self.settings.database_path}")

    def _log_initialization(self) -> None:
        """Log the initialization summary with all execution context.
        
        This log shows the CONFIGURED seed policy (from CLI/env), not the
        actual run seed. The actual run seed is logged separately after
        the run is created by RunManager.
        
        See also: _log_run_creation() for actual seed used.
        """
        # Get question IDs (will be loaded later, but we can log the filter)
        question_ids = self.args.questions if self.args.questions else ["All questions"]

        # Determine seed policy for display
        seed_policy = self._get_seed_policy_display()

        log_initialization_summary(
            logger=logger,
            execution_mode=self.settings.execution_mode.value,
            experiment_name=self.settings.experiment_name,
            persist_data=self.settings.should_persist_data,
            config_frozen=self.settings.is_config_frozen,
            config_hash=self.settings.get_config_hash() if self.settings.is_config_frozen else None,
            seed=seed_policy,  # Show policy, not actual seed value
            models=self.args.models,
            questions=question_ids,  # type: ignore
            system_prompt=self.settings.system_prompt,
        )

    def _get_seed_policy_display(self) -> str:
        """Get seed policy display string for initialization log.
        
        Returns:
            String describing seed policy: "AUTO", "FIXED", "CLI", or "NONE"
        """
        if self.args.seed is not None:
            return f"CLI ({self.args.seed})"
        elif self.settings.random_seed == "AUTO":
            return "AUTO (generated per run)"
        elif isinstance(self.settings.random_seed, int):
            return f"FIXED ({self.settings.random_seed})"
        else:
            return "NONE (original A,B,C,D order)"

    def _log_run_creation(self, run) -> None:
        """Log run creation with actual seed used.
        
        This provides the definitive record of which seed was actually
        used for this specific run, as stored in the database.
        
        Args:
            run: Run object with seed value.
        """
        if run and run.seed is not None:
            logger.info(f"Run {run.run_id} created with seed={run.seed} (from database)")
        else:
            logger.info(f"Run {run.run_id} created with no seed (original A,B,C,D order)")

    def _load_and_filter_questions(self) -> list:
        """Load questions from JSON and apply all filters.

        Returns:
            List of filtered and persisted Question objects.
        """
        from src.core.loader import QuestionLoader
        from src.core.filter import QuestionFilter
        from src.cli.cli import CLIParser
        from src.db.repository import QuestionRepository
        import sqlite3

        # Step 1: Load questions from JSON
        loader = QuestionLoader(str(self.settings.questionnaire_path))
        questions = loader.load()
        logger.info(f"Loaded {len(questions)} questions from {self.settings.questionnaire_path}")

        # Step 2: Filter by IDs
        if self.args.questions:
            filter_obj = QuestionFilter(questions)
            filter_obj.by_ids(self.args.questions)
            questions = filter_obj.get_results()
            logger.info(f"Filtered by IDs to {len(questions)} questions")

            if not questions:
                logger.error(f"No questions found matching filter: {self.args.questions}")
                print(f"Error: No questions found matching filter: {self.args.questions}", file=sys.stderr)
                return []

        # Step 3: Filter by metadata
        if hasattr(self.args, 'where') and self.args.where:
            cli_parser = CLIParser()
            metadata_filters = cli_parser._parse_metadata_filters(self.args.where)

            filter_obj = QuestionFilter(questions)
            filter_obj.by_metadata(**metadata_filters)
            questions = filter_obj.get_results()
            logger.info(f"Filtered by metadata {self.args.where} to {len(questions)} questions")

            if not questions:
                logger.error(f"No questions found matching metadata filter: {self.args.where}")
                print(f"Error: No questions found matching metadata filter: {self.args.where}", file=sys.stderr)
                return []

        # Step 4: Exclude by metadata
        if hasattr(self.args, 'exclude') and self.args.exclude:
            cli_parser = CLIParser()
            exclude_filters = cli_parser._parse_metadata_filters(self.args.exclude)

            filter_obj = QuestionFilter(questions)
            filter_obj.exclude_by_metadata(**exclude_filters)
            questions = filter_obj.get_results()
            logger.info(f"Excluded by metadata {self.args.exclude}, {len(questions)} questions remaining")

            if not questions:
                logger.error(f"No questions remaining after exclusion filter: {self.args.exclude}")
                print(f"Error: No questions remaining after exclusion filter: {self.args.exclude}", file=sys.stderr)
                return []

        # Persist questions to database
        question_repo = QuestionRepository(self.db_manager)
        logger.info(f"Persisting {len(questions)} questions to database")

        for q in questions:
            try:
                question_repo.create(q)
            except sqlite3.IntegrityError:
                logger.debug(f"Question {q.question_id} already in database")

        logger.info("Questions persisted successfully")
        return questions

    def _initialize_run(self, questions: list) -> Optional:
        """Initialize run with configuration.

        Args:
            questions: List of Question objects.

        Returns:
            Run object or None if RunManager not available.
        """
        config = {
            "models": self.args.models,
            "iterations": self.args.iterations,
            "questions": [q.question_id for q in questions],
            "seed": self.args.seed,
            "vary_seed": self.args.vary_seed,
            "test_mode": self.args.test_mode,
            "questionnaire": str(self.settings.questionnaire_path),
        }

        run = None
        if self.run_manager:
            run = self.run_manager.initialize_run(config)
            self._log_run_creation(run)

        return run

    async def _fetch_model_info(self, client, model_id: str) -> tuple[str, dict]:
        """Fetch actual model info from API.

        Args:
            client: OpenRouterClient instance.
            model_id: Model ID to fetch info for.

        Returns:
            Tuple of (actual_model_id, model_info_dict).
        """
        actual_model_id = model_id
        model_info = {}

        try:
            model_info = await client.get_model_info(model_id)
            actual_model_id = model_info.get("id", model_id)
            logger.info(f"Model {model_id} resolved to {actual_model_id}")

            meta = model_info.get("meta", {})
            if meta:
                n_params = meta.get("n_params", "N/A")
                size = meta.get("size", "N/A")
                n_ctx_train = meta.get("n_ctx_train", "N/A")
                logger.info(f"Model metadata: n_params={n_params}, size={size}, n_ctx_train={n_ctx_train}")
        except Exception as e:
            logger.warning(f"Could not fetch model info for {model_id}: {e}")
            logger.info(f"Using provided model name: {model_id}")

        return actual_model_id, model_info

    def _compile_final_results(
        self,
        all_results: list,
        run: Optional,
        questions: list,
    ) -> dict:
        """Compile final results and update run status.

        ⚠️ SIDE-EFFECTS:
        - Updates run status in database via RunManager.update_run_status()
        - Marks run as 'failed' if any iteration had errors

        Args:
            all_results: List of ExecutionResult objects.
            run: Run object or None.
            questions: List of Question objects (for total_questions count).

        Returns:
            Dictionary with aggregated results and metadata.
        """
        results = {
            "status": "completed",
            "models_tested": self.args.models,
            "iterations": self.args.iterations,
            "total_questions": len(questions),
            "results": all_results,
            "run_id": run.run_id if run else None,
        }

        if self.run_manager and run:
            # ExecutionResult has 'errors' attribute, not dict
            has_errors = any(r.errors > 0 for r in all_results)
            final_status = "failed" if has_errors else "completed"
            self.run_manager.update_run_status(run.run_id, final_status)

        logger.info("Benchmark execution completed")
        return results

    def _execute_benchmark(self) -> dict[str, Any]:
        """Execute the benchmark test using ExecutionEngine.

        Returns:
            Dictionary containing execution results and statistics.
        """
        from src.api.client import OpenRouterClient
        from src.core.execution_engine import ExecutionEngine, QuestionWithContext
        from src.core.randomizer import AnswerRandomizer

        logger.info("Starting benchmark execution")

        # Load questions
        questions = self._load_and_filter_questions()
        if not questions:
            return {}

        # Initialize run
        run = self._initialize_run(questions)
        if not run:
            return {}

        # Create ExecutionEngine with db_manager for persistence
        api_client = OpenRouterClient(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )
        randomizer = AnswerRandomizer(self.settings.random_seed)
        
        engine = ExecutionEngine(
            api_client=api_client,
            randomizer=randomizer,
            settings=self.settings,
            db_manager=self.db_manager,  # Enable persistence
        )

        # Wrap questions with snapshot_id=None (direct flow has no snapshots)
        questions_with_context = [QuestionWithContext(question=q, snapshot_id=None) for q in questions]

        # Get model variants from CLI
        # For direct flow, we create variants on-the-fly based on model_id
        from src.db.repository import ModelVariantRepository
        from src.db.models import ModelVariant
        from src.core.variant_config import VariantConfig
        
        variant_repo = ModelVariantRepository(self.db_manager)
        model_variants = []
        
        for model_id in self.args.models:
            logger.debug(f"Processing model: {model_id}")
            
            # Build variant config from settings
            variant_config = VariantConfig(
                reasoning_mode=self.settings.reasoning_mode if self.settings else "unspecified",
                reasoning_effort=self.settings.reasoning_effort if self.settings else None,
                reasoning_max_tokens=self.settings.reasoning_max_tokens if self.settings else None,
                vision_enabled=self.settings.enable_vision if self.settings else False,
                structured_enabled=self.settings.enable_structured if self.settings else False,
            )
            variant_id = variant_config.build_variant_id(model_id)
            logger.debug(f"Built variant_id: {variant_id} for model {model_id}")
            
            # Create variant if not exists
            existing = variant_repo.get_by_id(variant_id)
            logger.debug(f"Existing variant: {existing}")
            
            if not existing:
                logger.info(f"Creating new variant: {variant_id}")
                variant = ModelVariant(
                    variant_id=variant_id,
                    model_id=model_id,
                    reasoning_mode=variant_config.reasoning_mode,
                    reasoning_effort=variant_config.reasoning_effort,
                    reasoning_max_tokens=variant_config.reasoning_max_tokens,
                    vision_enabled=variant_config.vision_enabled,
                    structured_enabled=variant_config.structured_enabled,
                    variant_signature=variant_config.build_signature(model_id),
                )
                try:
                    variant_repo.create(variant)
                    logger.info(f"Created variant: {variant_id}")
                    existing = variant
                except Exception as e:
                    logger.warning(f"Failed to create variant: {e}")
                    # Might have been created concurrently
                    existing = variant_repo.get_by_id(variant_id)
            
            if existing:
                model_variants.append(existing)
                logger.info(f"Added variant to execution: {existing.variant_id}")
            else:
                logger.error(f"Failed to get or create variant: {variant_id}")

        # Execute using ExecutionEngine
        results = engine.execute(
            model_variants=model_variants,
            questions=questions_with_context,
            iterations=self.args.iterations,
            run_id=run.run_id,
            experiment_id=run.experiment_id if run.experiment_id else "",
        )

        # Compile final results
        return self._compile_final_results(results, run, questions)

    def _display_results(self, results: dict[str, Any]) -> None:
        """Calculate and display benchmark results.

        Args:
            results: Dictionary containing execution results.
        """
        # Fetch responses and errors from database
        from src.db.repository import ResponseRepository
        
        response_repo = ResponseRepository(self.db_manager)
        
        # Get all responses for this run
        run_id = results.get("run_id", "")
        responses = response_repo.get_by_run(run_id) if run_id else []
        
        # Convert to format expected by StatisticsCalculator
        responses_data = [
            {
                "model_id": r.variant_id,
                "is_correct": r.is_correct,
                "latency_ms": r.latency_ms,
                "input_tokens": r.input_tokens,
                "response_tokens": r.response_tokens,
                "status": r.status,
            }
            for r in responses
        ]

        # Get errors for this run
        from src.db.repository import ErrorRepository
        error_repo = ErrorRepository(self.db_manager)
        errors = error_repo.get_by_run(run_id) if run_id else []

        errors_data = [
            {
                "model_id": e.variant_id,
                "error_type": e.error_type,
                "error_message": e.error_message
            }
            for e in errors
        ]

        # Calculate statistics
        calculator = StatisticsCalculator(responses_data, errors_data)

        # Get statistics for all models
        all_stats = calculator.get_all_statistics()

        if not all_stats:
            print("No results to display")
            return

        # Create formatter based on output format
        formatter = create_formatter(self.args.output)

        # Display based on format
        if self.args.output == "console":
            if isinstance(formatter, ConsoleFormatter):
                formatter.display_table(all_stats)
                formatter.display_summary(all_stats)
        else:
            # Export to file or stdout
            if self.args.output_file:
                formatter.export_to_file(all_stats, str(self.args.output_file), self.args.output)
                print(f"Results exported to {self.args.output_file}")
            else:
                # Output to stdout
                if self.args.output == "json":
                    print(formatter.to_json(all_stats))
                elif self.args.output == "csv":
                    print(formatter.to_csv(all_stats), end="")
                elif self.args.output == "markdown":
                    print(formatter.to_markdown(all_stats))

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self.db_manager:
            self.db_manager.close()
            logger.debug("Database connection closed")


def main() -> int:
    """Main entry point for benchmark_llm.

    Returns:
        Exit code (0 for success, non-zero for errors).

    Example:
        $ python -m benchmark_llm --models gpt-4 claude-3 --iterations 3
    """
    runner = BenchmarkRunner()
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
