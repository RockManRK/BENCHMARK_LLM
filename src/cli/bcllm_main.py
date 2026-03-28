#!/usr/bin/env python3
"""Main CLI help and entry point."""

import argparse
import sys

from src.core.mode import Mode


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    """
    VALID_MODES = [Mode.INVALID]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create main argument parser with all TO-BE commands."""
    parser = argparse.ArgumentParser(
        prog="bcllm",
        description="Benchmark LLM — Reproducible, experiment-driven LLM benchmarking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  bcllm --create-experiment my_exp
  bcllm --experiment my_exp --add-model google/gemini-3.1-flash-lite-preview
  bcllm --experiment my_exp --add-questions 1-10
  bcllm --experiment my_exp --add-run
  bcllm --experiment my_exp --execute

Commands:
  Experiments: --create-experiment, --experiment, --list-experiments, --remove-experiment
  Models:      --add-model, --list-models, --remove-model
  Questions:   --add-questions, --list-questions, --remove-question
  Runs:        --create-run, --list-runs, --run, --remove-run
  Execution:   --execute
  Review:      --review-experiment, --review-all
        """,
    )

    # Add all TO-BE commands as optional arguments for help display
    parser.add_argument("--create-experiment", metavar="NAME", help="Create new experiment")
    parser.add_argument("--experiment", metavar="NAME", help="Show experiment details")
    parser.add_argument("--list-experiments", action="store_true", help="List all experiments")
    parser.add_argument("--remove-experiment", metavar="NAME", help="Remove experiment")
    
    parser.add_argument("--add-model", metavar="MODEL_ID", help="Add model to experiment")
    parser.add_argument("--list-models", action="store_true", help="List models in experiment")
    parser.add_argument("--remove-model", metavar="MODEL_ID", help="Remove model from experiment")
    
    parser.add_argument("--add-questions", metavar="SPEC", nargs="*", help="Add questions to experiment")
    parser.add_argument("--list-questions", action="store_true", help="List questions in experiment")
    parser.add_argument("--remove-question", metavar="SNAPSHOT_ID", help="Remove question snapshot")
    
    parser.add_argument("--create-run", action="store_true", help="Create run in experiment")
    parser.add_argument("--list-runs", action="store_true", help="List runs in experiment")
    parser.add_argument("--run", metavar="RUN_ID", help="Show run details")
    parser.add_argument("--remove-run", metavar="RUN_ID", help="Remove run")
    
    parser.add_argument("--execute", action="store_true", help="Execute experiment")
    parser.add_argument("--review-experiment", metavar="NAME", help="Review experiment results")
    parser.add_argument("--review-all", action="store_true", help="Review all pending items")
    
    return parser


def main(mode: Mode) -> int:
    """Main entry point.
    
    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    parser = create_parser()
    parser.parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())
