#!/usr/bin/env python3
"""Experiment lifecycle management CLI.

This module provides CLI commands for managing experiments:
- Create new experiments
- Show experiment details
- List all experiments
- Remove experiments (soft delete)

Usage:
    bcllm_experiment.py --create-experiment <name>
    bcllm_experiment.py --experiment <name>
    bcllm_experiment.py --list-experiments
    bcllm_experiment.py --remove-experiment <name>

Exit Codes:
    0: Success
    1: Validation error (not found, collision, invalid input)
"""

import argparse
import sys
import uuid

from src_v2.cli.database import get_database_connection
from src_v2.db.repository import ExperimentRepository
from src_v2.db.models import Experiment


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for experiment commands.

    Returns:
        ArgumentParser configured with all experiment commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_experiment.py",
        description="Experiment lifecycle management",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--create-experiment",
        metavar="NAME",
        help="Create new experiment",
    )
    group.add_argument(
        "--experiment",
        metavar="NAME",
        help="Show experiment details",
    )
    group.add_argument(
        "--list-experiments",
        action="store_true",
        help="List all experiments",
    )
    group.add_argument(
        "--remove-experiment",
        metavar="NAME",
        help="Remove experiment (soft delete)",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "csv", "markdown"],
        default="console",
        help="Output format",
    )

    return parser


def handle_create_experiment(args, conn) -> int:
    """Handle --create-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.create_experiment

    # Validate name is not empty
    if not name or not name.strip():
        print("Error: Experiment name cannot be empty.", file=sys.stderr)
        return 1

    # Check for name collision
    existing = repo.get_by_name(name)
    if existing:
        print(f"Error: Experiment already exists: {name}", file=sys.stderr)
        return 1

    # Create experiment with defaults
    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description="",
        config_json="{}",
        config_hash="",
        system_prompt="You are a helpful assistant.",
        user_prompt="Answer the following question.",
    )

    repo.save(experiment)
    print(f"✓ Experiment '{experiment.name}' created (ID: {experiment.experiment_id})")
    return 0


def handle_show_experiment(args, conn) -> int:
    """Handle --experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.experiment
    experiment = repo.get_by_name(name)

    if not experiment:
        print(f"Error: Experiment not found: {name}", file=sys.stderr)
        return 1

    # Print experiment details
    print(f"Experiment: {experiment.name}")
    print(f"  ID: {experiment.experiment_id}")
    print(f"  Description: {experiment.description or '(none)'}")
    print(f"  System Prompt: {experiment.system_prompt}")
    print(f"  User Prompt: {experiment.user_prompt}")
    print(f"  Active: {'Yes' if experiment.is_active else 'No'}")

    return 0


def handle_list_experiments(args, conn) -> int:
    """Handle --list-experiments command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    experiments = repo.list_all(active_only=True)

    if not experiments:
        print("No experiments found.")
        return 0

    # Print table
    print(f"{'Name':<30} {'ID':<20} {'Active':<8}")
    print("-" * 60)
    for exp in experiments:
        status = "Yes" if exp.is_active else "No"
        print(f"{exp.name:<30} {exp.experiment_id:<20} {status:<8}")

    return 0


def handle_remove_experiment(args, conn) -> int:
    """Handle --remove-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    repo = ExperimentRepository(conn)
    name = args.remove_experiment
    experiment = repo.get_by_name(name)

    if not experiment:
        print(f"Error: Experiment not found: {name}", file=sys.stderr)
        return 1

    repo.deactivate(experiment.experiment_id)
    print(f"✓ Experiment '{experiment.name}' removed")
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
        if args.create_experiment:
            return handle_create_experiment(args, conn)
        elif args.experiment:
            return handle_show_experiment(args, conn)
        elif args.list_experiments:
            return handle_list_experiments(args, conn)
        elif args.remove_experiment:
            return handle_remove_experiment(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()
