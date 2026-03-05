"""Main entry point for benchmark_llm project.

This module provides the main entry point for the benchmark tool,
wiring together CLI argument parsing, execution engine, statistics
calculation, and output formatting.
"""

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
from src.utils.logging_config import LoggingConfig, setup_logging

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
            # Validate configuration
            if not self._validate_config():
                return 1

            # Initialize database
            self._init_database()

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

        # Log test mode
        if self.args.test_mode:
            print("⚠️  TEST MODE: Results will not be saved to the main database")
            logger.info("Running in test mode with in-memory database")

        logger.info("Configuration validated")
        return True

    def _init_database(self) -> None:
        """Initialize the database connection and schema."""
        if self.args.test_mode:
            # Use in-memory database for testing
            from pathlib import Path
            self.settings.database_path = Path(":memory:")
            logger.info("Using in-memory database for test mode")

        # Ensure data directory exists (skip for in-memory)
        if str(self.settings.database_path) != ":memory:":
            self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_manager = DatabaseManager(self.settings.database_path)
        self.db_manager.initialize()
        self.run_manager = RunManager(self.db_manager)

        logger.info(f"Database initialized at {self.settings.database_path}")

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

                # Create iteration executor
                executor = IterationExecutor(
                    db_manager=self.db_manager,
                    api_client=client,
                    randomizer=randomizer,
                    run_id=run.run_id if run else "",
                    model_id=model_id,
                    iteration_number=iteration_num,
                    model_kwargs=model_kwargs,
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
        # Convert results to format expected by StatisticsCalculator
        responses = results.get("responses", [])
        errors = results.get("errors", [])

        # Calculate statistics
        calculator = StatisticsCalculator(responses, errors)

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
