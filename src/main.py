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
from pathlib import Path
from typing import Any, Optional

from src.cli.cli import CLIParser, parse_arguments
from src.cli.output_formatter import ConsoleFormatter, OutputFormatter, create_formatter
from src.cli.statistics import StatisticsCalculator
from src.core.randomizer import AnswerRandomizer
from src.core.run_manager import RunManager
from src.db.schema import DatabaseManager
from src.utils.config import get_settings
from src.utils.logging_config import LoggingConfig, setup_logging, log_initialization_summary

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

    def __init__(self, args: Optional[Any] = None) -> None:
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
        """Apply CLI reasoning arguments to settings."""
        if self.args.reasoning_effort:
            self.settings.reasoning_effort = self.args.reasoning_effort
            logger.info(f"Set reasoning_effort from CLI: {self.args.reasoning_effort}")

        if self.args.reasoning_tokens:
            self.settings.reasoning_max_tokens = self.args.reasoning_tokens
            logger.info(f"Set reasoning_max_tokens from CLI: {self.args.reasoning_tokens}")

        if self.args.reasoning_exclude:
            self.settings.reasoning_exclude = self.args.reasoning_exclude
            logger.info(f"Set reasoning_exclude from CLI: {self.args.reasoning_exclude}")

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
            # Handle manual review commands
            if self.args.review_experiment:
                return self._handle_review_experiment()
            if self.args.review_run:
                return self._handle_review_run()
            if self.args.review_all:
                return self._handle_review_all()

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

            # Set random seed if provided
            if self.args.seed:
                random.seed(self.args.seed)
                logger.info(f"Random seed set to {self.args.seed}")

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

    def _validate_config(self) -> bool:
        """Validate the configuration.

        Returns:
            True if configuration is valid, False otherwise.
        """
        # Check if models are specified
        if not self.args.models:
            print("Error: At least one model must be specified with --models", file=sys.stderr)
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
        """Log the initialization summary with all execution context."""
        # Get question IDs (will be loaded later, but we can log the filter)
        question_ids = self.args.questions if self.args.questions else ["All questions"]
        
        log_initialization_summary(
            logger=logger,
            execution_mode=self.settings.execution_mode.value,
            experiment_name=self.settings.experiment_name,
            persist_data=self.settings.should_persist_data,
            config_frozen=self.settings.is_config_frozen,
            config_hash=self.settings.get_config_hash() if self.settings.is_config_frozen else None,
            seed=self.args.seed,
            models=self.args.models,
            questions=question_ids,  # type: ignore
            system_prompt=self.settings.system_prompt,
        )

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
            logger.info(f"Run initialized: {run.run_id}")

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

    def _build_iteration_config(
        self, 
        run: Optional, 
        model_id: str, 
        actual_model_id: str, 
        iteration_num: int
    ) -> dict:
        """Build configuration for a single iteration.

        Args:
            run: Run object or None.
            model_id: Original model ID.
            actual_model_id: Actual model ID from API.
            iteration_num: Iteration number (1-based).

        Returns:
            Dictionary with randomizer, model_kwargs, and reasoning_config.
        """
        from src.core.randomizer import AnswerRandomizer

        # Calculate seed
        if self.args.seed is not None:
            if isinstance(self.args.seed, int):
                base_seed = self.args.seed
                logger.info(f"  Using fixed seed {base_seed} from CLI")
            else:
                base_seed = None
        elif self.settings.random_seed == "AUTO":
            if run:
                base_seed = hash(run.run_id) % (2**31)
                logger.info(f"  Using AUTO seed {base_seed} (from run_id hash)")
            else:
                base_seed = 42
                logger.info(f"  Using fallback seed {base_seed}")
        elif self.settings.random_seed is not None:
            base_seed = self.settings.random_seed
            logger.info(f"  Using fixed seed {base_seed} from .env")
        else:
            base_seed = None
            logger.info("  Randomization disabled (answers in original A,B,C,D order)")

        # Vary seed per iteration if requested
        if self.args.vary_seed and base_seed is not None:
            randomizer_seed = (base_seed + (iteration_num * 1000)) % (2**31)
            logger.info(f"  Using seed {randomizer_seed} for iteration {iteration_num} (base: {base_seed})")
        elif base_seed is not None:
            randomizer_seed = base_seed
        else:
            randomizer_seed = None

        # Create randomizer
        randomizer = AnswerRandomizer(run_id=randomizer_seed) if randomizer_seed is not None else None

        # Build model kwargs
        model_kwargs = {}
        if self.settings.model_max_tokens is not None:
            model_kwargs["max_tokens"] = self.settings.model_max_tokens
        if self.settings.model_temperature is not None:
            model_kwargs["temperature"] = self.settings.model_temperature
        if self.settings.model_top_p is not None:
            model_kwargs["top_p"] = self.settings.model_top_p
        if self.settings.model_top_k is not None:
            model_kwargs["top_k"] = self.settings.model_top_k
        if self.settings.model_repeat_penalty is not None:
            model_kwargs["repeat_penalty"] = self.settings.model_repeat_penalty

        # Build reasoning config
        reasoning_config = None
        if any([
            self.settings.reasoning_effort is not None,
            self.settings.reasoning_max_tokens is not None,
            self.settings.reasoning_exclude is not None,
            self.settings.reasoning_enabled is not None
        ]):
            reasoning_config = {}

            if self.settings.reasoning_effort is not None:
                reasoning_config["effort"] = self.settings.reasoning_effort
            if self.settings.reasoning_max_tokens is not None:
                reasoning_config["max_tokens"] = self.settings.reasoning_max_tokens
            if self.settings.reasoning_exclude is not None:
                reasoning_config["exclude"] = self.settings.reasoning_exclude
            if self.settings.reasoning_enabled is not None:
                reasoning_config["enabled"] = self.settings.reasoning_enabled

            logger.info(f"Using reasoning config: {reasoning_config}")

        return {
            "randomizer": randomizer,
            "model_kwargs": model_kwargs,
            "reasoning_config": reasoning_config,
        }

    def _execute_single_iteration(
        self,
        questions: list,
        run: Optional,
        model_id: str,
        actual_model_id: str,
        iteration_num: int,
        iteration_config: dict,
        client,
    ) -> dict:
        """Execute a single iteration.

        Args:
            questions: List of Question objects.
            run: Run object or None.
            model_id: Original model ID.
            actual_model_id: Actual model ID from API.
            iteration_num: Iteration number (1-based).
            iteration_config: Configuration from _build_iteration_config().
            client: OpenRouterClient instance.

        Returns:
            Dictionary with iteration results.
        """
        from src.core.iteration_executor import IterationExecutor

        executor = IterationExecutor(
            db_manager=self.db_manager,
            api_client=client,
            randomizer=iteration_config["randomizer"],
            run_id=run.run_id if run else "",
            model_id=actual_model_id,
            iteration_number=iteration_num,
            experiment_id=run.experiment_id if run else "",
            model_kwargs=iteration_config["model_kwargs"],
            use_structured_outputs=self.settings.use_structured_outputs,
            reasoning_config=iteration_config["reasoning_config"],
            settings=self.settings,
        )

        result = executor.execute_iteration(questions)
        logger.info(
            f"  Iteration {iteration_num} completed: "
            f"{result['completed_questions']}/{result['total_questions']} questions, "
            f"{result['errors']} errors"
        )

        return result

    def _execute_all_models_and_iterations(
        self, 
        questions: list, 
        run: Optional
    ) -> list:
        """Orchestrate execution across all models and iterations.

        ⚠️ This function is purely orchestrator - delegates all logic to helpers.

        Args:
            questions: List of Question objects.
            run: Run object or None.

        Returns:
            List of iteration results.
        """
        from src.api.client import OpenRouterClient

        all_results = []
        client = OpenRouterClient(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )

        for model_id in self.args.models:
            logger.info(f"Starting benchmark for model: {model_id}")

            # Fetch model info
            actual_model_id, model_info = asyncio.run(self._fetch_model_info(client, model_id))

            # Register actual model if different
            if self.run_manager and getattr(self.run_manager, '_register_model', None) and actual_model_id != model_id:
                self.run_manager._register_model(actual_model_id)
                logger.debug(f"Registered actual model: {actual_model_id}")

            for iteration_num in range(1, self.args.iterations + 1):
                logger.info(f"  Starting iteration {iteration_num} for {model_id}")

                # Build configuration
                iteration_config = self._build_iteration_config(
                    run, model_id, actual_model_id, iteration_num
                )

                # Execute iteration
                result = self._execute_single_iteration(
                    questions, run, model_id, actual_model_id,
                    iteration_num, iteration_config, client
                )

                all_results.append(result)

        return all_results

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
            all_results: List of iteration results.
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
            has_errors = any(r.get("errors", 0) > 0 for r in all_results)
            final_status = "failed" if has_errors else "completed"
            self.run_manager.update_run_status(run.run_id, final_status)

        logger.info("Benchmark execution completed")
        return results

    def _execute_benchmark(self) -> dict[str, Any]:
        """Execute the benchmark test.

        Returns:
            Dictionary containing execution results and statistics.
        """
        logger.info("Starting benchmark execution")

        # Execute benchmark using extracted helpers
        questions = self._load_and_filter_questions()
        if not questions:
            return {}

        run = self._initialize_run(questions)
        all_results = self._execute_all_models_and_iterations(questions, run)
        return self._compile_final_results(all_results, run, questions)

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
                "model_id": r.model_id,
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
                "model_id": e.model_id,
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
