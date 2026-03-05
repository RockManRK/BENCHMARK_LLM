"""CLI module for benchmark_llm project.

This module provides command-line argument parsing functionality
for the benchmark tool using argparse.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional


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
  %(prog)s --models gpt-4 claude-3 --iterations 3
  %(prog)s --models gpt-4 --questions Q001-Q010 --output json
  %(prog)s --config config.yaml --verbose
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
            help="Random seed for reproducible answer randomization",
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

        # Test mode
        parser.add_argument(
            "--test-mode",
            action="store_true",
            help="Run in test mode without saving results to the main database",
        )

        # Vary seed per iteration
        parser.add_argument(
            "--vary-seed",
            action="store_true",
            help="Use a different seed for each iteration (for consistency testing)",
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

        # Post-process question ranges (e.g., Q001-Q010)
        if parsed_args.questions:
            parsed_args.questions = self._expand_question_ranges(parsed_args.questions)

        return parsed_args

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
