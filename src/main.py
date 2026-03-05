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
from src.utils.logging_config import setup_logging

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

        # Setup logging
        setup_logging(self.settings)

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

        logger.info("Configuration validated")
        return True

    def _init_database(self) -> None:
        """Initialize the database connection and schema."""
        # Ensure data directory exists
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_manager = DatabaseManager(self.settings.database_path)
        self.db_manager.initialize()
        self.run_manager = RunManager(self.db_manager)

        logger.info(f"Database initialized at {self.settings.database_path}")

    def _execute_benchmark(self) -> dict[str, Any]:
        """Execute the benchmark test.

        Returns:
            Dictionary containing execution results and statistics.

        Note:
            This is a placeholder that will be connected to the full
            execution engine when Phases 5-6 are complete.
        """
        logger.info("Starting benchmark execution")

        # Initialize run
        config = {
            "models": self.args.models,
            "iterations": self.args.iterations,
            "questions": self.args.questions,
            "seed": self.args.seed,
        }

        if self.run_manager:
            run = self.run_manager.initialize_run(config)
            logger.info(f"Run initialized: {run.run_id}")

        # Placeholder for full execution
        # In the complete implementation, this would:
        # 1. Load questions from JSON
        # 2. Filter questions based on args.questions
        # 3. For each model:
        #    a. For each iteration:
        #       - Execute all questions
        #       - Store responses in database
        # 4. Return execution results

        # Simulated results for now
        results = {
            "status": "completed",
            "models_tested": self.args.models,
            "iterations": self.args.iterations,
            "total_questions": 0,
            "responses": [],
            "errors": [],
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
