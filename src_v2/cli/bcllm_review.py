#!/usr/bin/env python3
"""CLI entry point for manual review interface.

This module provides the --review-experiment command for reviewing
LLM responses that need manual classification.

Usage:
    bcllm --review-experiment <experiment_name>
    bcllm --review-all

Exit Codes:
    0: Success
    1: Error (experiment not found, database error, etc.)
"""

import argparse
import sys

from src_v2.cli.database import get_database_connection
from src_v2.review.review_ui import ReviewUI


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for review commands.

    Returns:
        ArgumentParser configured with review commands.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_review.py",
        description="Manual review interface for LLM responses",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--review-experiment",
        metavar="NAME",
        help="Start review interface for an experiment",
    )
    group.add_argument(
        "--review-all",
        action="store_true",
        help="Start review interface for all pending responses",
    )

    return parser


def handle_review_experiment(args, conn) -> int:
    """Handle --review-experiment command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    experiment_name = args.review_experiment

    if not experiment_name or not experiment_name.strip():
        print("Error: Experiment name cannot be empty.", file=sys.stderr)
        return 1

    try:
        ui = ReviewUI(conn)
        ui.start_review_by_experiment(experiment_name)
        return 0
    except KeyboardInterrupt:
        print("\n\n[yellow]Review interrupted by user.[/yellow]")
        return 0
    except Exception as e:
        print(f"Error during review: {e}", file=sys.stderr)
        return 1


def handle_review_all(args, conn) -> int:
    """Handle --review-all command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        ui = ReviewUI(conn)
        ui.start_review_all()
        return 0
    except KeyboardInterrupt:
        print("\n\n[yellow]Review interrupted by user.[/yellow]")
        return 0
    except Exception as e:
        print(f"Error during review: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = create_parser()
    args = parser.parse_args()

    conn = get_database_connection()

    try:
        if args.review_experiment:
            return handle_review_experiment(args, conn)
        elif args.review_all:
            return handle_review_all(args, conn)
        else:
            parser.print_help()
            return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
