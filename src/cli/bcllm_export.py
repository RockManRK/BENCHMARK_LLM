#!/usr/bin/env python3
"""CLI command for exporting benchmark results.

This module provides read-only export functionality for external analysis
and auditing. It outputs deterministic, reproducible JSON for a given run.

Usage:
    bcllm --experiment <name> --run <run_id> --export
    bcllm --experiment <name> --run <run_id> --export --output-file results.json

Exit Codes:
    0: Success
    1: Validation error (experiment/run not found, mismatch, etc.)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import sqlite3

from src.cli.database import get_database_connection
from src.core.export_service import ExportService
from src.utils.logging_config import get_logger, setup_logging, LoggingConfig
from src.core.mode import Mode
import os

_logger = get_logger('cli.export')


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    """
    VALID_MODES = [Mode.EXECUTE, Mode.EXPORT, Mode.INVALID]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for export command.

    Returns:
        ArgumentParser configured with all export command options.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_export.py",
        description="Export benchmark results for external analysis and auditing.",
    )
    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )
    parser.add_argument(
        "--run",
        required=True,
        metavar="RUN_ID",
        help="Run ID to export",
    )
    parser.add_argument(
        "--output-file",
        metavar="PATH",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (default: json)",
    )
    
    # Accept --export flag but ignore it (already processed by mode resolver)
    parser.add_argument(
        "--export",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    
    return parser


def handle_export(args, conn: sqlite3.Connection, mode: Mode) -> int:
    """Handle export command.

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.
        mode: The CLI mode for validation.

    Returns:
        Exit code (0 for success, 1 for error).

    Validation:
        - Experiment must exist
        - Run must exist
        - Run must belong to experiment

    Logs:
        - EXPORT_COMMAND_START: When command begins
        - EXPORT_ERROR: When validation fails
        - EXPORT_WRITTEN: When file output is written
        - EXPORT_COMPLETE: When export finishes
    """
    _logger.info(
        f"EXPORT_COMMAND_START | experiment={args.experiment} | run={args.run}"
    )
    
    from src.db.repository import ExperimentRepository, RunRepository
    
    exp_repo = ExperimentRepository(conn)
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        _logger.error(f"EXPORT_ERROR | experiment={args.experiment} | error=Experiment not found")
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1
    
    run_repo = RunRepository(conn)
    run = run_repo.get_by_id(args.run)
    if not run:
        _logger.error(f"EXPORT_ERROR | run={args.run} | error=Run not found")
        print(f"Error: Run not found: {args.run}", file=sys.stderr)
        return 1
    
    if run.experiment_id != experiment.experiment_id:
        _logger.error(
            f"EXPORT_ERROR | run={args.run} | experiment={args.experiment} | "
            f"error=Run does not belong to experiment"
        )
        print(
            f"Error: Run '{args.run}' does not belong to experiment '{args.experiment}'.",
            file=sys.stderr
        )
        return 1
    
    export_service = ExportService(conn)
    result = export_service.export_run(args.run)
    
    output_data = result.to_json()
    
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_data)
        _logger.info(
            f"EXPORT_WRITTEN | run={args.run} | file={args.output_file} | "
            f"responses={result.total_responses} | errors={result.total_errors}"
        )
        print(f"Exported {result.total_responses} responses and {result.total_errors} errors to {args.output_file}")
    else:
        print(output_data)
        _logger.info(
            f"EXPORT_COMPLETE | run={args.run} | responses={result.total_responses} | "
            f"errors={result.total_errors} | output=stdout"
        )
    
    return 0


def main(mode: Mode) -> int:
    """Main entry point for export command.

    Args:
        mode: The CLI mode (EXECUTE or INVALID).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    
    parser = create_parser()
    args = parser.parse_args()
    
    conn = get_database_connection()
    try:
        return handle_export(args, conn, mode)
    finally:
        conn.close()


if __name__ == "__main__":
    # Direct execution is not supported - this module must be called from bcllm.py
    # which provides the mode argument.
    print(
        "Error: This module cannot be run directly. Use:\n"
        "  bcllm --experiment <name> --run <run_id> --export",
        file=sys.stderr
    )
    sys.exit(1)
