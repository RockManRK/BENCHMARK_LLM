"""Main entry point for benchmark_llm project.

This module provides the main entry point for the benchmark tool,
wiring together CLI argument parsing, execution engine, statistics
calculation, and output formatting.
"""

import asyncio
import logging
import random
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
        
        # Apply CLI reasoning args to settings
        self._apply_cli_reasoning_args()

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

    def _execute_benchmark(self) -> dict[str, Any]:
        """Execute the benchmark test.

        Returns:
            Dictionary containing execution results and statistics.
        """
        logger.info("Starting benchmark execution")

        # Step 1: Load questions from JSON
        from src.core.loader import QuestionLoader
        
        loader = QuestionLoader(str(self.settings.questionnaire_path))
        questions = loader.load()
        logger.info(f"Loaded {len(questions)} questions from {self.settings.questionnaire_path}")

        # Step 2: Filter questions if --questions argument provided
        if self.args.questions:
            from src.core.filter import QuestionFilter
            
            filter_obj = QuestionFilter(questions)
            filter_obj.by_ids(self.args.questions)
            questions = filter_obj.get_results()
            logger.info(f"Filtered to {len(questions)} questions")

        # Step 3: Initialize run
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

        # Step 4: Execute benchmark for each model and iteration
        from src.api.client import OpenRouterClient
        from src.core.randomizer import AnswerRandomizer
        from src.core.iteration_executor import IterationExecutor

        all_results = []

        client = OpenRouterClient(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )

        for model_id in self.args.models:
            logger.info(f"Starting benchmark for model: {model_id}")

            # Fetch actual model name and metadata from API
            actual_model_id = model_id  # Fallback to provided name
            model_info = {}
            try:
                # Fetch actual model info using asyncio
                async def fetch_model_info():
                    return await client.get_model_info(model_id)

                model_info = asyncio.run(fetch_model_info())
                actual_model_id = model_info.get("id", model_id)
                logger.info(f"Model {model_id} resolved to {actual_model_id}")
                
                # Log model metadata if available
                meta = model_info.get("meta", {})
                if meta:
                    n_params = meta.get("n_params", "N/A")
                    size = meta.get("size", "N/A")
                    n_ctx_train = meta.get("n_ctx_train", "N/A")
                    logger.info(f"Model metadata: n_params={n_params}, size={size}, n_ctx_train={n_ctx_train}")
            except Exception as e:
                logger.warning(f"Could not fetch model info for {model_id}: {e}")
                logger.info(f"Using provided model name: {model_id}")

            # Save model to database with metadata
            if self.run_manager:
                try:
                    from src.db.repository import ModelRepository
                    
                    model_repo = ModelRepository(self.db_manager)
                    
                    # Extract metadata fields
                    meta = model_info.get("meta", {})
                    context_length = model_info.get("context_length")
                    max_completion_tokens = model_info.get("max_completion_tokens")
                    
                    # Determine provider from owned_by or use 'unknown'
                    owned_by = model_info.get("owned_by", "unknown")
                    
                    # Create or update model record
                    model_repo.create(
                        model_id=actual_model_id,
                        model_name=model_info.get("id", model_id),
                        provider=owned_by,
                        metadata=meta if meta else {},
                        context_length=context_length,
                        max_completion_tokens=max_completion_tokens,
                    )
                    logger.info(f"Model {actual_model_id} saved to database")
                except Exception as e:
                    logger.warning(f"Could not save model to database: {e}")

            for iteration_num in range(1, self.args.iterations + 1):
                logger.info(f"  Starting iteration {iteration_num} for {model_id}")

                # Create randomizer with seed (use args.seed for reproducibility, or hash of run_id)
                if self.args.seed:
                    base_seed = self.args.seed
                elif run:
                    # Hash the run_id to get a reproducible int seed
                    base_seed = hash(run.run_id) % (2**31)
                else:
                    base_seed = 42

                # Vary seed per iteration if requested
                if self.args.vary_seed:
                    # Use different seed for each iteration
                    randomizer_seed = (base_seed + (iteration_num * 1000)) % (2**31)
                    logger.info(f"  Using seed {randomizer_seed} for iteration {iteration_num} (base: {base_seed})")
                else:
                    randomizer_seed = base_seed

                randomizer = AnswerRandomizer(run_id=randomizer_seed)

                # Build model kwargs from settings (only include non-None values)
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

                # Build reasoning config from settings
                reasoning_config = None
                if any([
                    self.settings.reasoning_effort,
                    self.settings.reasoning_max_tokens,
                    self.settings.reasoning_exclude,
                    self.settings.reasoning_enabled
                ]):
                    reasoning_config = {}
                    
                    if self.settings.reasoning_effort:
                        reasoning_config["effort"] = self.settings.reasoning_effort
                    if self.settings.reasoning_max_tokens:
                        reasoning_config["max_tokens"] = self.settings.reasoning_max_tokens
                    if self.settings.reasoning_exclude:
                        reasoning_config["exclude"] = self.settings.reasoning_exclude
                    if self.settings.reasoning_enabled:
                        reasoning_config["enabled"] = self.settings.reasoning_enabled
                    
                    logger.info(f"Using reasoning config: {reasoning_config}")

                # Create iteration executor
                executor = IterationExecutor(
                    db_manager=self.db_manager,
                    api_client=client,
                    randomizer=randomizer,
                    run_id=run.run_id if run else "",
                    model_id=actual_model_id,  # Use actual model ID from API
                    iteration_number=iteration_num,
                    model_kwargs=model_kwargs,
                    use_structured_outputs=self.settings.use_structured_outputs,
                    reasoning_config=reasoning_config,
                    settings=self.settings,
                )
                
                # Execute iteration
                result = executor.execute_iteration(questions)
                all_results.append(result)
                
                logger.info(
                    f"  Iteration {iteration_num} completed: "
                    f"{result['completed_questions']}/{result['total_questions']} questions, "
                    f"{result['errors']} errors"
                )

        # Step 5: Compile and return results
        results = {
            "status": "completed",
            "models_tested": self.args.models,
            "iterations": self.args.iterations,
            "total_questions": len(questions),
            "results": all_results,
            "run_id": run.run_id if run else None,
        }

        logger.info("Benchmark execution completed")
        return results

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
                "output_tokens": r.output_tokens,
                "status": "success",
            }
            for r in responses
        ]
        
        # Errors are not tracked separately in test mode
        errors_data = []

        # Calculate statistics
        calculator = StatisticsCalculator(responses_data, errors_data)

        # Get statistics for all models
        all_stats = calculator.get_all_statistics()

        if not all_stats:
            print("No results to display")
            return

        # Create formatter based on output format
        formatter = create_formatter(self.args.output_format)

        # Display based on format
        if self.args.output_format == "console":
            if isinstance(formatter, ConsoleFormatter):
                formatter.display_table(all_stats)
                formatter.display_summary(all_stats)
        else:
            # Export to file or stdout
            if self.args.output_file:
                formatter.export_to_file(all_stats, str(self.args.output_file), self.args.output_format)
                print(f"Results exported to {self.args.output_file}")
            else:
                # Output to stdout
                if self.args.output_format == "json":
                    print(formatter.to_json(all_stats))
                elif self.args.output_format == "csv":
                    print(formatter.to_csv(all_stats), end="")
                elif self.args.output_format == "markdown":
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
