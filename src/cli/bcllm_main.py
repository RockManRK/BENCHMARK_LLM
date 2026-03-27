#!/usr/bin/env python3
"""Main CLI entry point — routes to src/main.py for experiment commands.

After Phase 1 consolidation, this module routes experiment commands
to the unified src/main.py entry point.
"""

import argparse
import sys


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
    
    # Additional arguments needed by src/main.py
    parser.add_argument("--questions", "-q", nargs="*", help="Select questions by numeric position")
    parser.add_argument("--where", nargs="*", default=[], help="Include filter (status=valid)")
    parser.add_argument("--exclude", nargs="*", default=[], help="Exclude filter")
    parser.add_argument("--seed", "-s", help="Random seed (AUTO, number, or None)")
    parser.add_argument("--description", help="Experiment description")
    parser.add_argument("--reasoning-effort", help="Reasoning effort level")
    parser.add_argument("--enable-vision", action="store_true", help="Enable vision")
    parser.add_argument("--enable-structured", action="store_true", help="Enable structured outputs")
    parser.add_argument("--iterations", "-i", type=int, default=1, help="Number of iterations")
    parser.add_argument("--export-results", metavar="RUN_ID", help="Export run results")
    parser.add_argument("--add-to-run", metavar="RUN_ID", help="Add models to run")
    parser.add_argument("--complete-run", metavar="RUN_ID", help="Complete run")

    return parser


def main() -> int:
    """Main entry point — routes to src/main.py for experiment commands."""
    parser = create_parser()
    args = parser.parse_args()
    
    # If --create-experiment is provided, route to src/main.py
    if args.create_experiment:
        from src.main import BenchmarkRunner
        runner = BenchmarkRunner(args)
        return runner.run()
    
    # For other experiment commands (--experiment, --list-experiments, --remove-experiment)
    # also route to src/main.py
    if args.experiment or args.list_experiments or args.remove_experiment:
        from src.main import BenchmarkRunner
        runner = BenchmarkRunner(args)
        return runner.run()
    
    # Otherwise just show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
