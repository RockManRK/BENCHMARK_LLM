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
import json
import sys
import uuid

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import parse_args_normalized
from src.db.models import Run
from src.db.repository import ExperimentRepository, RunRepository


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    
    Note:
        Mode.INVALID is not accepted. It represents "no valid mode detected"
        and should be caught by dispatcher validation before reaching this module.
        Accepting Mode.INVALID here would mask dispatcher bugs.
    """
    # ACCEPT Mode.CREATE for composite flows (--create-experiment + --add-run)
    # The orchestration layer (bcllm.py) creates the experiment before dispatching.
    # Also accept Mode.EXECUTE for run-specific execution commands.
    # Mode.INVALID is explicitly excluded - it indicates a dispatcher resolution failure.
    VALID_MODES = [Mode.CREATE, Mode.MODIFY, Mode.EXECUTE]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


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
        "--system-prompt",
        metavar="PROMPT",
        help="Custom system prompt (inherits from experiment if not specified)",
    )

    parser.add_argument(
        "--user-prompt",
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
    from src.core.config_resolver import ConfigResolver

    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    resolver = ConfigResolver()
    resolver.load_env()

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    config_dict = resolver.build_run_config_dict(args, experiment, run_id=run_id)

    run = Run(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        config=json.dumps(config_dict),
        status="pending",
    )

    run_repo.save(run, config_dict)
    seed_display = str(config_dict.get('RUN_RESPONSES_SEED')) if config_dict.get('RUN_RESPONSES_SEED') is not None else "None"
    print(f"✓ Run created for '{experiment.name}' (ID: {run.run_id}, Seed: {seed_display})")
    print(f"  System Prompt: {'Custom' if args.system_prompt else 'Inherited from experiment/.env'}")
    print(f"  User Prompt: {'Custom' if args.user_prompt else 'Inherited from experiment/.env'}")
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

    import json
    print(f"Runs in experiment: {experiment.name}")
    print(f"{'ID':<25} {'Seed':<10} {'Status':<18}")
    print("-" * 55)
    for r in runs:
        config = json.loads(r.config) if r.config else {}
        seed_display = str(config.get('RUN_RESPONSES_SEED')) if config.get('RUN_RESPONSES_SEED') is not None else "None"
        print(f"{r.run_id:<25} {seed_display:<10} {r.status:<18}")

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

    import json
    config = json.loads(run.config) if run.config else {}

    print(f"Run: {run.run_id}")
    print(f"  Experiment: {experiment.name}")
    print(f"  Config:")
    print(f"    seed: {config.get('RUN_RESPONSES_SEED', 'None')}")
    print(f"    system_prompt: {config.get('SYSTEM_PROMPT', 'None')}")
    print(f"    user_prompt: {config.get('USER_PROMPT', 'None')}")
    print(f"  Status: {run.status}")

    return 0


def handle_remove_run(args, conn) -> int:
    """Handle --remove-run command.

    Soft delete: sets status='removed' rather than deleting the row.
    Previously this hard-deleted the run (src/db/repository.py's
    RunRepository.delete()), which — because responses/errors reference
    run_id without ON DELETE CASCADE (src/db/schema.py) — would fail with
    a foreign key error on any run that already had results, and
    succeeded silently (destroying the run's frozen config, seed, and
    prompts) on any run that didn't. Neither outcome matches
    docs/contracts/configuration-hierarchy.md's "Run configuration is
    frozen at creation; never changes" combined with
    docs/contracts/immutability.md's documented mutable exception for
    Run ("status, duration ... Execution lifecycle tracking") — that
    exception is exactly the seam this now uses: 'removed' is a new,
    valid status value (src/db/schema.py's CHECK constraint), and the run
    row and its config stay. Planner._get_runs() excludes 'removed' in
    BOTH of its branches (the default listing, and the run_ids-not-None
    branch used by `--execute --run <id>`) — the latter needed its own
    explicit `status != 'removed'` fix, since it originally had no status
    filter at all and would happily reactivate a removed run if someone
    named its id directly. See docs/status/known-issues.md for how that
    was caught (an essence-guardian review, after an earlier version of
    this docstring wrongly assumed checking the default branch was
    enough).

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

    run = run_repo.get_by_id(args.remove_run)
    if not run:
        print(f"Error: Run not found: {args.remove_run}", file=sys.stderr)
        return 1

    if run.experiment_id != experiment.experiment_id:
        print(f"Error: Run '{args.remove_run}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    run_repo.update_status(run.run_id, "removed")
    print(f"✓ Run '{run.run_id}' removed")
    return 0


def main(mode: Mode) -> int:
    """Main entry point.

    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    parser = create_parser()
    args = parse_args_normalized(parser)

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
