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
  # Basic benchmark
  %(prog)s --models gpt-4 claude-3 --iterations 3

  # With question filtering
  %(prog)s --models gpt-4 --questions Q001-Q010 --output json

  # With random seed (3 modes: empty=A,B,C,D order, AUTO=unique per run, 42=fixed)
  %(prog)s --models Qwen --questions Q001 --seed 42

  # Create frozen experiment (immutable config)
  %(prog)s --experiment my-experiment --models Qwen --questions Q001

  # With metadata filtering
  %(prog)s --models gpt-4 --where status=valid has_image=false

  # Reasoning models (Qwen, o1) with high max-tokens
  %(prog)s --models Qwen --max-tokens 16384 --temperature 0.0

  # Structured outputs (set USE_STRUCTURED_OUTPUTS=true in .env)
  %(prog)s --models gpt-4o --questions Q001
            """,
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
        parser.add_argument(
            "--seed",
            "-s",
            type=int,
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
        parser.add_argument(
            "--reasoning-effort",
            type=str,
            choices=["xhigh", "high", "medium", "low", "minimal", "none"],
            help="Reasoning effort level for models that support reasoning (o1, o3, "
                 "Claude, Gemini, etc.). Higher effort = more thorough reasoning but "
                 "more tokens and time.",
        )

        parser.add_argument(
            "--reasoning-tokens",
            type=int,
            help="Maximum tokens for reasoning. Controls how much the model can "
                 "'think' before answering. Leave blank in .env for model default.",
        )

        parser.add_argument(
            "--reasoning-exclude",
            action="store_true",
            help="Exclude reasoning from response text. Model uses reasoning internally "
                 "but only returns the final answer. Useful for cleaner output.",
        )

        # Model variant parameters (identity-defining)
        parser.add_argument(
            "--reasoning-mode",
            type=str,
            choices=["off", "auto", "effort", "budget", "unspecified"],
            default=None,
            help="Reasoning mode for model variant identity. "
                 "'unspecified' = do not send reasoning field (use model default, NOT synonymous with auto/off). "
                 "'auto' = use model's default reasoning behavior. "
                 "'off' = explicitly disable reasoning. "
                 "'effort' = use specific reasoning effort (requires --reasoning-effort). "
                 "'budget' = limit reasoning tokens (requires --reasoning-tokens).",
        )

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

        # Post-process execution mode
        # --test-mode is an alias for --mode test (backward compatibility)
        parsed_args = self._normalize_execution_mode(parsed_args)

        # Post-process question ranges (e.g., Q001-Q010)
        if parsed_args.questions:
            parsed_args.questions = self._expand_question_ranges(parsed_args.questions)

        return parsed_args

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
