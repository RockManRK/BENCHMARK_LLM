#!/usr/bin/env python3
"""Run lifecycle management CLI.

This module provides CLI commands for managing runs within experiments:
- Create new runs
- List runs in an experiment
- Show run details

Usage:
    bcllm_run.py --experiment <name> --create-run [--seed N]
    bcllm_run.py --experiment <name> --list-runs
    bcllm_run.py --experiment <name> --run <run_id>

Exit Codes:
    0: Success
    1: Validation error (not found, precondition failed, invalid input)
"""

import argparse
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.db.models import Run
from src_v2.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for run commands.

    Returns:
        ArgumentParser configured with all run commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_run.py",
        description="Run lifecycle management",
    )

    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--create-run",
        action="store_true",
        help="Create new run",
    )
    group.add_argument(
        "--list-runs",
        action="store_true",
        help="List all runs in experiment",
    )
    group.add_argument(
        "--run",
        metavar="RUN_ID",
        help="Show run details",
    )

    parser.add_argument(
        "--seed",
        type=int,
        metavar="N",
        help="Random seed for answer shuffling (default: None)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    return parser


def handle_create_run(args, conn) -> int:
    """Handle --create-run command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).

    Preconditions:
        - Experiment must exist
        - Experiment must have at least one active model variant
        - Experiment must have at least one active question snapshot
    """
    exp_repo = ExperimentRepository(conn)
    var_repo = VariantRepository(conn)
    snap_repo = SnapshotRepository(conn)
    run_repo = RunRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Check experiment has models
    variants = var_repo.list_by_experiment(experiment.experiment_id, active_only=True)
    if not variants:
        print(f"Error: Experiment '{experiment.name}' has no models. Add models first:", file=sys.stderr)
        print(f"  bcllm_model.py --experiment {experiment.name} --add-model <model_id>", file=sys.stderr)
        return 1

    # Check experiment has snapshots
    snapshots = snap_repo.list_by_experiment(experiment.experiment_id, active_only=True)
    if not snapshots:
        print(f"Error: Experiment '{experiment.name}' has no questions. Add questions first:", file=sys.stderr)
        print(f"  bcllm_questions.py --experiment {experiment.name} --add-questions <spec>", file=sys.stderr)
        return 1

    # Create run
    run = Run(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment.experiment_id,
        seed=args.seed,
        status="pending",
    )

    run_repo.save(run)
    seed_display = str(run.seed) if run.seed else "None"
    print(f"✓ Run created for '{experiment.name}' (ID: {run.run_id}, Seed: {seed_display})")
    return 0


def handle_list_runs(args, conn) -> int:
    """Handle --list-runs command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    runs = run_repo.list_by_experiment(experiment.experiment_id)

    if not runs:
        print(f"No runs in experiment '{experiment.name}'.")
        return 0

    # Print table
    print(f"Runs in experiment: {experiment.name}")
    print(f"{'ID':<25} {'Seed':<10} {'Status':<18} {'Started':<22} {'Finished':<22}")
    print("-" * 100)
    for r in runs:
        started = r.started_at[:19] if r.started_at else "-"
        finished = r.finished_at[:19] if r.finished_at else "-"
        seed_display = str(r.seed) if r.seed else "None"
        print(f"{r.run_id:<25} {seed_display:<10} {r.status:<18} {started:<22} {finished:<22}")

    return 0


def handle_show_run(args, conn) -> int:
    """Handle --run command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    # Check experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Check run exists
    run = run_repo.get_by_id(args.run)
    if not run:
        print(f"Error: Run not found: {args.run}", file=sys.stderr)
        return 1

    # Check run belongs to experiment
    if run.experiment_id != experiment.experiment_id:
        print(f"Error: Run '{args.run}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    # Print run details
    print(f"Run: {run.run_id}")
    print(f"  Experiment: {experiment.name}")
    print(f"  Seed: {run.seed if run.seed else 'None'}")
    print(f"  Status: {run.status}")
    print(f"  Started: {run.started_at if run.started_at else 'Not started'}")
    print(f"  Finished: {run.finished_at if run.finished_at else 'Not finished'}")

    return 0


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args()

    conn = get_database_connection()

    try:
        if args.create_run:
            return handle_create_run(args, conn)
        elif args.list_runs:
            return handle_list_runs(args, conn)
        elif args.run:
            return handle_show_run(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
