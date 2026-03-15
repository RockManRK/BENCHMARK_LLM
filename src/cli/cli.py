"""CLI module for benchmark_llm project.

This module provides command-line argument parsing functionality
for the benchmark tool using argparse.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from src.utils.config import ExecutionMode


class CLIParser:
    """Command-line argument parser for benchmark_llm.

    This class encapsulates argparse configuration and provides
    a clean interface for parsing command-line arguments.

    Attributes:
        parser: The underlying argparse.ArgumentParser instance.

    Example:
        >>> parser = CLIParser()
        >>> args = parser.parse(["--models", "gpt-4", "--iterations", "3"])
        >>> print(args.models)
        ['gpt-4']
    """

    def __init__(self) -> None:
        """Initialize the CLI parser with all argument definitions.

        Configures argparse with all supported command-line options
        for the benchmark tool.

        Example:
            >>> parser = CLIParser()
            >>> assert parser.parser is not None
        """
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Create and configure the argument parser.

        Returns:
            Configured ArgumentParser instance with all arguments defined.
        """
        parser = argparse.ArgumentParser(
            prog="benchmark_llm",
            description="LLM Benchmark Tool - Evaluate and compare LLM performance",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Create experiment (freeze config, create snapshots)
  %(prog)s --create-experiment my_exp --questions Q001-Q010 --seed AUTO

  # View experiment details
  %(prog)s --experiment my_exp

  # Add models to experiment
  %(prog)s --experiment my_exp --add-model openai/gpt-4 --add-model anthropic/claude-3

  # Remove model from experiment
  %(prog)s --experiment my_exp --remove-model openai/gpt-4

  # Create run (without executing)
  %(prog)s --experiment my_exp --create-run --iterations 3 --seed 42

  # Execute run (only pending items)
  %(prog)s --experiment my_exp --run
  %(prog)s --experiment my_exp --run --models openai/gpt-4 --questions Q001-Q50

  # Basic benchmark (fast flow)
  %(prog)s --models gpt-4 claude-3 --iterations 3

  # With question filtering
  %(prog)s --models gpt-4 --questions Q001-Q010 --output json

  # With random seed (3 modes: empty=A,B,C,D order, AUTO=unique per run, 42=fixed)
  %(prog)s --models Qwen --questions Q001 --seed 42

  # With metadata filtering
  %(prog)s --models gpt-4 --where status=valid has_image=false

  # Reasoning models (Qwen, o1) with high max-tokens
  %(prog)s --models Qwen --max-tokens 16384 --temperature 0.0

  # Structured outputs (set USE_STRUCTURED_OUTPUTS=true in .env)
  %(prog)s --models gpt-4o --questions Q001

Incremental Flow (add models to existing run):
  # Day 1: Create run with 3 models
  %(prog)s --models gpt-4 claude-3 gemini --iterations 3

  # Day 2: Add 2 more models
  %(prog)s --add-to-run run-20260314-abc --add-models qwen-2.5 llama-3

  # Day 3: Re-execute run (only pending models)
  %(prog)s --run-id run-20260314-abc --iterations 3
  # → Completed models are automatically skipped

  # Complete run (no more models can be added)
  %(prog)s --complete-run run-20260314-abc
            """,
        )

        # Experiment management flags (NEW CLI paradigm)
        # Note: --experiment flag already exists below for backward compatibility

        parser.add_argument(
            "--create-experiment",
            type=str,
            metavar="NAME",
            help="Create a new experiment with the specified name. Use with --questions and --seed.",
        )

        parser.add_argument(
            "--add-model",
            action="append",
            dest="add_models",
            metavar="MODEL",
            help="Add a model to the experiment. Can be specified multiple times. Use with --experiment.",
        )

        parser.add_argument(
            "--remove-model",
            type=str,
            metavar="MODEL_ID",
            help="Remove a model from the experiment. Use with --experiment. Use '?' for interactive mode.",
        )

        parser.add_argument(
            "--create-run",
            action="store_true",
            help="Create a new run for the experiment. Use with --experiment, --iterations, and --seed.",
        )

        parser.add_argument(
            "--run",
            action="store_true",
            dest="execute_run",
            help="Execute the experiment run. Use with --experiment. Supports --models and --questions for filtering.",
        )

        # Model selection
        parser.add_argument(
            "--models",
            "-m",
            nargs="+",
            type=str,
            required=False,
            help="List of model IDs to benchmark (e.g., gpt-4 claude-3 gemini-pro)",
        )

        # Run ID for re-execution
        parser.add_argument(
            "--run-id",
            type=str,
            metavar="RUN_ID",
            help="Re-execute a specific run by ID. When provided, models are loaded from the run_models table instead of --models. Only models with status 'pending' or 'running' will be executed.",
        )

        # Iteration count
        parser.add_argument(
            "--iterations",
            "-i",
            type=int,
            default=1,
            help="Number of test iterations per model (default: 1)",
        )

        # Question filtering
        parser.add_argument(
            "--questions",
            "-q",
            nargs="+",
            type=str,
            required=False,
            help="Filter questions by ID or range (e.g., Q001 or Q001-Q010)",
        )

        # Question metadata filtering
        parser.add_argument(
            "--where",
            nargs="+",
            type=str,
            required=False,
            default=[],
            help="Filter questions by metadata (e.g., --where status=valid has_image=false)",
        )

        parser.add_argument(
            "--exclude",
            nargs="+",
            type=str,
            required=False,
            default=[],
            help="Exclude questions by metadata (e.g., --exclude status=annulled has_image=true)",
        )

        # Configuration file
        parser.add_argument(
            "--config",
            "-c",
            type=Path,
            required=False,
            help="Path to configuration file (YAML or JSON)",
        )

        # Output format
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            choices=["console", "json", "csv", "markdown"],
            default="console",
            help="Output format for results (default: console)",
        )

        # Output file
        parser.add_argument(
            "--output-file",
            "-f",
            type=Path,
            required=False,
            help="Path to output file for results",
        )

        # Random seed
        def seed_type(value: str) -> int | str:
            """Convert seed argument to int or string."""
            if value.upper() == "AUTO":
                return "AUTO"
            try:
                return int(value)
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid seed value: {value}. Use integer or AUTO.")

        parser.add_argument(
            "--seed",
            "-s",
            type=seed_type,
            required=False,
            help="Random seed for reproducible answer randomization. "
                 "Three modes: (1) Empty/None = no randomization (A,B,C,D order), "
                 "(2) AUTO = automatic seed per run (hash of run_id), "
                 "(3) Integer = fixed seed for reproducibility. "
                 "CLI --seed takes precedence over RANDOM_SEED in .env.",
        )

        # Verbose mode
        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output with detailed progress",
        )

        # Dry run mode
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate configuration without executing benchmark",
        )

        # Execution mode
        parser.add_argument(
            "--mode",
            type=str,
            choices=["test", "dev", "experiment"],
            default=None,
            help="Execution mode: test (no persistence, in-memory DB), "
                 "dev (default, full persistence), "
                 "experiment (frozen config with hash, requires --experiment)",
        )

        # Experiment name
        parser.add_argument(
            "--experiment",
            type=str,
            required=False,
            help="Name of the experiment. Creates a frozen experiment with immutable "
                 "configuration hash. All runs are linked to the experiment ID for "
                 "reproducibility. Configuration changes create a new experiment.",
        )

        # Test mode (backward compatibility - alias for --mode test)
        parser.add_argument(
            "--test-mode",
            action="store_true",
            help="Run in test mode without saving results (alias for --mode test)",
        )

        # Vary seed per iteration
        parser.add_argument(
            "--vary-seed",
            action="store_true",
            help="Use a different seed for each iteration (for consistency testing)",
        )

        # Model generation parameters
        parser.add_argument(
            "--temperature",
            type=float,
            help="Temperature for model generation. Lower = more deterministic, "
                 "higher = more creative. Leave blank in .env for model default.",
        )
        parser.add_argument(
            "--max-tokens",
            type=int,
            help="Maximum tokens for model generation. Critical for reasoning models "
                 "(Qwen, o1): set to 16384 or higher. llama.cpp defaults to 100 tokens "
                 "(insufficient for reasoning). Leave blank in .env for model default.",
        )
        parser.add_argument(
            "--top-p",
            type=float,
            help="Top-p (nucleus) sampling parameter. Alternative to temperature. "
                 "Leave blank in .env for model default.",
        )
        parser.add_argument(
            "--top-k",
            type=int,
            help="Top-k sampling parameter. Limits token selection. "
                 "Leave blank in .env for model default.",
        )
        parser.add_argument(
            "--repeat-penalty",
            type=float,
            help="Repeat penalty parameter. Reduces repetitive output. "
                 "Leave blank in .env for model default.",
        )

        # Reasoning parameters (OpenRouter standard)
        # Simplified: Only --reasoning-effort is exposed to users
        def reasoning_effort_type(value: str) -> str:
            """Validate reasoning effort parameter with human-readable error."""
            valid = {"xhigh", "high", "medium", "low", "minimal", "none"}
            if value.lower() not in valid:
                raise argparse.ArgumentTypeError(
                    f"Invalid reasoning effort. Use one of: {', '.join(valid)}"
                )
            return value.lower()

        parser.add_argument(
            "--reasoning-effort",
            type=reasoning_effort_type,
            default=None,
            help="Reasoning effort level for models that support reasoning (o1, o3, "
                 "Claude, Gemini, etc.). Higher effort = more thorough reasoning but "
                 "more tokens and time. Use 'none' to explicitly disable reasoning. "
                 "If not specified, the system does NOT send any reasoning configuration, "
                 "allowing the model to use its default behavior.",
        )

        # Note: --reasoning-mode, --reasoning-tokens, and --reasoning-exclude
        # have been removed to simplify the CLI. Reasoning is now configured
        # exclusively via --reasoning-effort.

        parser.add_argument(
            "--enable-vision",
            action="store_true",
            default=None,
            help="Enable vision for model variant (send images with questions). "
                 "Part of variant identity.",
        )

        parser.add_argument(
            "--enable-structured",
            action="store_true",
            default=None,
            help="Enable structured outputs (JSON schema) for model variant. "
                 "Part of variant identity. Falls back to traditional if not supported.",
        )

        # Add models to existing run
        parser.add_argument(
            "--add-to-run",
            type=str,
            metavar="RUN_ID",
            help="Add models to an existing run (run must be in 'running' status). "
                 "Use with --add-models to specify which models to add.",
        )

        parser.add_argument(
            "--add-models",
            "-a",
            nargs="+",
            type=str,
            required=False,
            help="Models to add to an existing run (use with --add-to-run). "
                 "Example: --add-to-run run-123 --add-models qwen/2.5 llama-3",
        )

        parser.add_argument(
            "--complete-run",
            type=str,
            metavar="RUN_ID",
            help="Mark a run as completed. No more models can be added after this.",
        )

        # Manual review commands
        parser.add_argument(
            "--review-run",
            type=str,
            metavar="RUN_ID",
            help="Start manual review interface for a specific run (e.g., run-001)",
        )

        parser.add_argument(
            "--review-experiment",
            type=str,
            metavar="EXPERIMENT_ID",
            help="Start manual review interface for a specific experiment (e.g., exp-001)",
        )

        parser.add_argument(
            "--review-all",
            action="store_true",
            help="Start manual review interface for ALL pending responses across all experiments and runs",
        )

        return parser

    def parse(self, args: Optional[list[str]] = None) -> argparse.Namespace:
        """Parse command-line arguments.

        Args:
            args: List of argument strings to parse. If None, uses sys.argv[1:].

        Returns:
            Parsed arguments as a Namespace object.

        Raises:
            SystemExit: If invalid arguments are provided.
            ValueError: If iterations is less than 1.

        Example:
            >>> parser = CLIParser()
            >>> args = parser.parse(["--models", "gpt-4", "--iterations", "3"])
            >>> args.models
            ['gpt-4']
            >>> args.iterations
            3
        """
        parsed_args = self.parser.parse_args(args)

        # Validate iterations
        if parsed_args.iterations < 1:
            self.parser.error("--iterations must be at least 1")

        # Validate conceptual conflicts (creation vs operation)
        self._validate_conceptual_conflicts(parsed_args)

        # Post-process execution mode
        # --test-mode is an alias for --mode test (backward compatibility)
        parsed_args = self._normalize_execution_mode(parsed_args)

        # Post-process question ranges (e.g., Q001-Q010)
        if parsed_args.questions:
            parsed_args.questions = self._expand_question_ranges(parsed_args.questions)

        return parsed_args

    def _validate_conceptual_conflicts(self, args: argparse.Namespace) -> None:
        """Validate that creation and operation commands are not mixed.

        Conceptual model:
        - Creation commands (--create-experiment) are OUTSIDE context
        - Operation commands (--add-model, --create-run, etc.) require --experiment context
        - Cannot be in a context that doesn't exist yet

        Args:
            args: Parsed arguments namespace.

        Raises:
            SystemExit: If conceptual conflict is detected.
        """
        # Rule 1: --create-experiment cannot be used with --experiment
        if args.create_experiment and args.experiment:
            self.parser.error(
                "--create-experiment cannot be used with --experiment. "
                "First create the experiment, then use --experiment for operations."
            )

        # Rule 2: Operation commands require --experiment context
        operation_flags = [
            ('add_models', '--add-model'),
            ('remove_model', '--remove-model'),
            ('create_run', '--create-run'),
            ('execute_run', '--run'),
        ]

        for attr, flag_name in operation_flags:
            if hasattr(args, attr) and getattr(args, attr):
                if not args.experiment:
                    self.parser.error(
                        f"{flag_name} requires --experiment <name>. "
                        f"Example: --experiment my_exp {flag_name}"
                    )

        # Rule 3: --create-experiment does NOT require --questions
        # Default behavior: use ALL questions if not specified
        # This follows the principle: "What would a user expect if they don't set anything?"
        # Answer: All questions, in original order (no randomization)

    def _normalize_execution_mode(
        self, args: argparse.Namespace
    ) -> argparse.Namespace:
        """Normalize execution mode from CLI arguments.

        Handles the following logic:
        - If --test-mode is set, set mode to 'test' (backward compatibility)
        - If --mode is not set and --test-mode is not set, default to 'dev'
        - If --experiment is provided without --mode experiment, raise error

        Args:
            args: Parsed arguments namespace.

        Returns:
            Modified namespace with normalized execution_mode field.
        """
        # Determine execution mode
        if args.test_mode:
            # --test-mode has highest precedence
            execution_mode = "test"
            if args.experiment:
                print("Warning: --test-mode has precedence. --experiment will be ignored.", file=sys.stderr)
        elif args.experiment:
            # --experiment forces experiment mode
            execution_mode = "experiment"
            if args.mode and args.mode != "experiment":
                print(f"Warning: --experiment forces EXPERIMENT MODE. Ignoring --mode {args.mode}", file=sys.stderr)
        elif args.mode:
            execution_mode = args.mode
        else:
            # Default to dev mode
            execution_mode = "dev"

        # Validate experiment mode requirements
        if execution_mode == "experiment" and not args.experiment:
            self.parser.error(
                "--experiment is required when using --mode experiment"
            )

        # Set normalized execution_mode
        args.execution_mode = execution_mode
        args.experiment_name = args.experiment if args.experiment else None

        return args

    def _parse_metadata_filters(self, metadata_args: list[str]) -> dict:
        """Parse metadata filter arguments into a dictionary.

        Converts list of key=value strings into a dictionary with proper type conversion.

        Args:
            metadata_args: List of metadata filters in format "key=value".

        Returns:
            Dictionary with metadata key-value pairs.

        Example:
            >>> parser = CLIParser()
            >>> parser._parse_metadata_filters(["status=valid", "has_image=false"])
            {'status': 'valid', 'has_image': False}
        """
        metadata = {}
        for item in metadata_args:
            if "=" not in item:
                logger.warning(f"Invalid metadata filter '{item}', expected key=value format")
                continue

            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Type conversion
            if value.lower() == "true":
                metadata[key] = True
            elif value.lower() == "false":
                metadata[key] = False
            else:
                # Try integer
                try:
                    metadata[key] = int(value)
                except ValueError:
                    # Try float
                    try:
                        metadata[key] = float(value)
                    except ValueError:
                        # Keep as string
                        metadata[key] = value

        return metadata

    def _expand_question_ranges(self, questions: list[str]) -> list[str]:
        """Expand question ranges into individual question IDs.

        Converts range notation like "Q001-Q010" into a list of
        individual question IDs ["Q001", "Q002", ..., "Q010"].

        Args:
            questions: List of question IDs or ranges.

        Returns:
            Expanded list of individual question IDs.

        Example:
            >>> parser = CLIParser()
            >>> parser._expand_question_ranges(["Q001-Q003"])
            ['Q001', 'Q002', 'Q003']
        """
        expanded: list[str] = []

        for question in questions:
            if "-" in question and question.count("-") == 1:
                # This is a range like Q001-Q010
                start, end = question.split("-")
                start_num = int(start[1:])  # Remove 'Q' prefix
                end_num = int(end[1:])  # Remove 'Q' prefix

                # Generate all question IDs in range
                for num in range(start_num, end_num + 1):
                    # Preserve zero-padding from start
                    padding = len(start) - 1
                    expanded.append(f"Q{num:0{padding}d}")
            else:
                # Single question ID
                expanded.append(question)

        return expanded


def parse_arguments(args: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments using default parser.

    Convenience function for parsing arguments without creating
    a CLIParser instance directly.

    Args:
        args: List of argument strings to parse. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments as a Namespace object.

    Example:
        >>> # Simulating: python -m benchmark_llm --models gpt-4
        >>> args = parse_arguments(["--models", "gpt-4"])
        >>> args.models
        ['gpt-4']
    """
    parser = CLIParser()
    return parser.parse(args)


def main() -> int:
    """Main entry point for CLI parsing.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    try:
        args = parse_arguments()
        print(f"Parsed arguments: {args}")
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as e:
        print(f"Error parsing arguments: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
