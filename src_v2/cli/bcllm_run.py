#!/usr/bin/env python3
"""Run lifecycle management CLI.

This module provides CLI commands for managing runs within experiments:
- Create new runs (--add-run)
- List runs in an experiment (--list-runs)
- Show run details (--run)
- Remove runs (--remove-run)

Usage:
    bcllm_run.py --experiment <name> --add-run [--seed N] [--system_prompt P] [--user_prompt P]
    bcllm_run.py --experiment <name> --list-runs
    bcllm_run.py --experiment <name> --run <run_id>
    bcllm_run.py --experiment <name> --remove-run <run_id>

Exit Codes:
    0: Success
    1: Validation error (not found, precondition failed, invalid input)
"""

import argparse
import hashlib
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.db.models import Run
from src_v2.db.repository import ExperimentRepository, RunRepository


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
        "--add-run",
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
    group.add_argument(
        "--remove-run",
        metavar="RUN_ID",
        help="Remove run (soft delete)",
    )

    parser.add_argument(
        "--seed",
        type=str,
        metavar="N",
        help="Random seed for answer shuffling (AUTO, number, or empty for None)",
    )

    parser.add_argument(
        "--system_prompt",
        metavar="PROMPT",
        help="Custom system prompt (inherits from experiment if not specified)",
    )

    parser.add_argument(
        "--user_prompt",
        metavar="PROMPT",
        help="Custom user prompt (inherits from experiment if not specified)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    return parser


def generate_seed(run_name: str, experiment_id: str) -> int:
    """Generate a deterministic seed based on run identifier.

    Args:
        run_name: Run identifier string.
        experiment_id: Parent experiment ID for additional entropy.

    Returns:
        A deterministic integer seed derived from run name and experiment ID.
    """
    combined = f"{experiment_id}:{run_name}"
    hash_bytes = hashlib.sha256(combined.encode('utf-8')).digest()
    seed = int.from_bytes(hash_bytes[:8], byteorder='big')
    return seed % (2**31)


def parse_seed_value(seed_arg: str, run_id: str, experiment_id: str) -> int | None:
    """Parse seed argument value.

    Args:
        seed_arg: Seed argument string (AUTO, empty, or number).
        run_id: Run ID for AUTO generation.
        experiment_id: Experiment ID for AUTO generation.

    Returns:
        Integer seed value or None for empty/unset.

    Raises:
        ValueError: If seed format is invalid.
    """
    if not seed_arg or seed_arg.strip() == "":
        return None

    if seed_arg.upper() == "AUTO":
        return generate_seed(run_id, experiment_id)

    try:
        return int(seed_arg)
    except ValueError:
        raise ValueError(f"Invalid seed value: {seed_arg}. Use AUTO, empty, or a number.")


def handle_add_run(args, conn) -> int:
    """Handle --add-run command.

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
    run_repo = RunRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    seed_value = None
    if args.seed is not None:
        try:
            seed_value = parse_seed_value(args.seed, run_id, experiment.experiment_id)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    system_prompt = args.system_prompt if args.system_prompt else experiment.system_prompt
    user_prompt = args.user_prompt if args.user_prompt else experiment.user_prompt

    run = Run(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        seed=seed_value,
        status="pending",
    )

    run_repo.save(run, system_prompt, user_prompt)
    seed_display = str(run.seed) if run.seed else "None"
    print(f"✓ Run created for '{experiment.name}' (ID: {run.run_id}, Seed: {seed_display})")
    print(f"  System Prompt: {'Custom' if args.system_prompt else 'Inherited from experiment'}")
    print(f"  User Prompt: {'Custom' if args.user_prompt else 'Inherited from experiment'}")
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

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    runs = run_repo.list_by_experiment(experiment.experiment_id)

    if not runs:
        print(f"No runs in experiment '{experiment.name}'.")
        return 0

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

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    run = run_repo.get_by_id(args.run)
    if not run:
        print(f"Error: Run not found: {args.run}", file=sys.stderr)
        return 1

    if run.experiment_id != experiment.experiment_id:
        print(f"Error: Run '{args.run}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    run_with_prompts = run_repo.get_by_id_with_prompts(args.run)

    print(f"Run: {run.run_id}")
    print(f"  Experiment: {experiment.name}")
    print(f"  Seed: {run.seed if run.seed else 'None'}")
    print(f"  Status: {run.status}")
    print(f"  Started: {run.started_at if run.started_at else 'Not started'}")
    print(f"  Finished: {run.finished_at if run.finished_at else 'Not finished'}")
    if run_with_prompts:
        print(f"  System Prompt: {run_with_prompts.get('system_prompt', '(none)')}")
        print(f"  User Prompt: {run_with_prompts.get('user_prompt', '(none)')}")

    return 0


def handle_remove_run(args, conn) -> int:
    """Handle --remove-run command (soft delete).

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).

    Notes:
        - Soft delete: sets is_active = FALSE
        - Does not delete historical response/error data
        - Prevents future execution of this run
    """
    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    run = run_repo.get_by_id(args.remove_run)
    if not run:
        print(f"Error: Run not found: {args.remove_run}", file=sys.stderr)
        return 1

    if run.experiment_id != experiment.experiment_id:
        print(f"Error: Run '{args.remove_run}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    run_repo.deactivate(run.run_id)
    print(f"✓ Run '{run.run_id}' removed (soft delete - historical data preserved)")
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
        if args.add_run:
            return handle_add_run(args, conn)
        elif args.list_runs:
            return handle_list_runs(args, conn)
        elif args.run:
            return handle_show_run(args, conn)
        elif args.remove_run:
            return handle_remove_run(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
