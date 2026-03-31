#!/usr/bin/env python3
"""Execution entry point CLI.

This module provides the CLI command for executing benchmark runs:
- Orchestrates Planner → ExecutionEngine → ResultWriter flow
- Validates experiment and run existence
- Supports filters: --run, --questions, --models
- Supports retry policy configuration
- Handles partial executions (pending items only)
- Reports execution summary

Usage:
    bcllm_execute.py --experiment <name> --execute
    bcllm_execute.py --experiment <name> --execute --run <run_id>
    bcllm_execute.py --experiment <name> --execute --questions Q001 Q005
    bcllm_execute.py --experiment <name> --execute --models var_xyz789
    bcllm_execute.py --experiment <name> --execute --retry-policy max_attempts=5,backoff=linear

Exit Codes:
    0: Success
    1: Validation error (not found, invalid input, execution failure)

Orchestration Flow:
    1. Validate experiment exists
    2. Validate run exists and belongs to experiment (if --run specified)
    3. Validate filters are valid (if specified)
    4. Planner.build_plan() → ExecutionPlan (with filters)
    5. Check if plan has work to do
    6. ExecutionEngine.execute() → ExecutionResult list
    7. ResultWriter.write_results() → WriteReport
    8. Print summary to console

CRITICAL: This module is ORCHESTRATION ONLY.
- No domain logic (retries, error handling in Engine)
- No inference (all validation is explicit)
- No mutable state (delegates to ResultWriter)
"""

import argparse
import sys
import re
import os
from typing import Any

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.db.repository import ExperimentRepository, RunRepository, VariantRepository, SnapshotRepository
from src.core.planner import Planner, PlannerValidationError
from src.core.execution_engine import ExecutionEngine
from src.core.result_writer import ResultWriter
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.core.execution_plan import RetryPolicy
from src.api.client import OpenRouterClient
from src.utils.logging_config import get_logger


def _validate_expected_mode(mode: Mode) -> None:
    """Validate that received mode matches expected mode for this module.

    Args:
        mode: The CLI mode passed from dispatcher.

    Raises:
        SystemExit: If mode is invalid for this module.
    """
    VALID_MODES = [Mode.EXECUTE]

    if mode not in VALID_MODES:
        print(
            f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, got '{mode.value}'.\n"
            f"This indicates a dispatcher bug. Please report this issue.",
            file=sys.stderr
        )
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for execute command.

    Returns:
        ArgumentParser configured with execute command arguments.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_execute.py",
        description="Execute benchmark runs with optional filters",
    )

    parser.add_argument(
        "--experiment",
        required=True,
        metavar="NAME",
        help="Experiment name",
    )
    parser.add_argument(
        "--run",
        metavar="RUN_ID",
        help="Specific run ID to execute (default: all pending runs)",
    )
    parser.add_argument(
        "--questions",
        metavar="Q_ID",
        nargs="+",
        help="Specific question IDs to execute (e.g., Q001 Q005 or Q001-Q010 for range)",
    )
    parser.add_argument(
        "--models",
        metavar="VAR_ID",
        nargs="+",
        help="Specific model variant IDs to execute",
    )
    parser.add_argument(
        "--retry-policy",
        metavar="CONFIG",
        help="Retry policy configuration (e.g., 'max_attempts=5,backoff=linear')",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the run(s)",
    )

    return parser


def parse_retry_policy(config_str: str) -> RetryPolicy:
    """Parse retry policy configuration string.

    Args:
        config_str: Configuration string in format 'key=value,key=value'

    Returns:
        RetryPolicy instance with specified configuration

    Example:
        >>> policy = parse_retry_policy("max_attempts=5,backoff=linear")
        >>> policy.max_attempts
        5
        >>> policy.backoff
        'linear'
    """
    kwargs: dict[str, Any] = {}

    if not config_str:
        return RetryPolicy()

    pairs = config_str.split(",")
    for pair in pairs:
        if "=" not in pair:
            continue

        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key == "max_attempts":
            kwargs["max_attempts"] = int(value)
        elif key == "backoff":
            if value not in ("exponential", "linear", "constant"):
                raise ValueError(f"Invalid backoff strategy: {value}")
            kwargs["backoff"] = value
        elif key == "retry_on":
            # retry_on is a comma-separated list within the value
            kwargs["retry_on"] = tuple(v.strip() for v in value.split("|"))

    return RetryPolicy(**kwargs)


def parse_question_ids(question_specs: list[str]) -> list[str]:
    """Parse question ID specifications (supports ranges).

    Args:
        question_specs: List of question IDs or ranges (e.g., ["Q001", "Q005-Q010"])

    Returns:
        Expanded list of question IDs

    Example:
        >>> parse_question_ids(["Q001", "Q005-Q007"])
        ['Q001', 'Q005', 'Q006', 'Q007']
    """
    question_ids = []

    for spec in question_specs:
        if "-" in spec:
            # Range specification (e.g., Q001-Q010)
            match = re.match(r"([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)", spec)
            if match:
                prefix_start, num_start, prefix_end, num_end = match.groups()
                if prefix_start != prefix_end:
                    raise ValueError(f"Invalid range: {spec} (prefix mismatch)")

                start = int(num_start)
                end = int(num_end)

                for num in range(start, end + 1):
                    question_ids.append(f"{prefix_start}{num:0{len(num_start)}d}")
            else:
                raise ValueError(f"Invalid question range: {spec}")
        else:
            # Single question ID
            question_ids.append(spec)

    return question_ids


def validate_filters(conn, experiment_id: str, run_id: str | None, question_ids: list[str] | None, model_variant_ids: list[str] | None) -> list[str]:
    """Validate that specified filters exist.

    Args:
        conn: Database connection
        experiment_id: Experiment identifier
        run_id: Optional run ID filter
        question_ids: Optional question ID filters
        model_variant_ids: Optional model variant ID filters

    Returns:
        List of validation error messages (empty if all valid)
    """
    errors = []

    # Validate run exists
    if run_id:
        run_repo = RunRepository(conn)
        run = run_repo.get_by_id(run_id)
        if not run:
            errors.append(f"Run not found: {run_id}")
        elif run.experiment_id != experiment_id:
            errors.append(f"Run '{run_id}' does not belong to this experiment")

    # Validate question IDs exist in experiment
    if question_ids:
        snapshot_repo = SnapshotRepository(conn)
        snapshots = snapshot_repo.list_by_experiment(experiment_id)
        existing_question_ids = {s.json_question_id for s in snapshots}

        for qid in question_ids:
            if qid not in existing_question_ids:
                errors.append(f"Question not found in experiment: {qid}")

    # Validate model variant IDs exist in experiment
    if model_variant_ids:
        variant_repo = VariantRepository(conn)
        variants = variant_repo.list_by_experiment(experiment_id, active_only=True)
        existing_variant_ids = {v.variant_id for v in variants}

        for vid in model_variant_ids:
            if vid not in existing_variant_ids:
                errors.append(f"Model variant not found in experiment: {vid}")

    return errors


def handle_execute(args, conn) -> int:
    """Handle --execute command with filters. ORCHESTRATION ONLY.

    This function orchestrates the execution flow:
    1. Validate experiment exists
    2. Validate run exists and belongs to experiment (if --run specified)
    3. Validate filters are valid (if specified)
    4. Build execution plan via Planner (with filters)
    5. Check if plan has work to do
    6. Execute plan via ExecutionEngine
    7. Write results via ResultWriter
    8. Print summary

    Args:
        args: Parsed command-line arguments.
        conn: Database connection.

    Returns:
        Exit code (0 for success, 1 for error).

    Orchestration Constraints:
        - No domain logic (retries in ExecutionEngine)
        - No inference (explicit validation only)
        - No mutable state (delegates to ResultWriter)
    """
    logger = get_logger('cli.execute')

    # Initialize repositories
    exp_repo = ExperimentRepository(conn)

    # Validate experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        logger.error(f"EXECUTE_ERROR | experiment={args.experiment} | error=Experiment not found")
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    experiment_id = experiment.experiment_id
    run_id = args.run

    logger.info(f"EXECUTE_START | experiment={args.experiment} | run={run_id if run_id else 'all'} | experiment_id={experiment_id}")

    # Parse filters
    question_ids = None
    model_variant_ids = None

    if args.questions:
        try:
            question_ids = parse_question_ids(args.questions)
        except ValueError as e:
            logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error=Invalid question specification: {e}")
            print(f"Error: Invalid question specification: {e}", file=sys.stderr)
            return 1

    if args.models:
        model_variant_ids = args.models

    # Validate filters
    validation_errors = validate_filters(conn, experiment_id, run_id, question_ids, model_variant_ids)
    if validation_errors:
        for error in validation_errors:
            logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error={error}")
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # Parse retry policy
    retry_policy = RetryPolicy()
    if args.retry_policy:
        try:
            retry_policy = parse_retry_policy(args.retry_policy)
        except (ValueError, TypeError) as e:
            logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error=Invalid retry policy: {e}")
            print(f"Error: Invalid retry policy: {e}", file=sys.stderr)
            return 1

    try:
        # ORCHESTRATION: Planner → ExecutionEngine → ResultWriter

        # Step 1: Build execution plan with filters
        planner = Planner(conn)
        plan = planner.build_plan(
            args.experiment,
            run_ids=[run_id] if run_id else None,
            question_ids=question_ids,
            model_variant_ids=model_variant_ids,
            retry_policy=retry_policy,
        )

        # Validate plan has work to do
        total_items = sum(len(run.items) for run in plan.runs)
        if not plan.runs or total_items == 0:
            logger.info(f"PLAN_LOADED | experiment={experiment_id} | run={run_id if run_id else 'all'} | items=0 | status=no_pending_work")
            print("No pending items to execute. All items completed.", file=sys.stderr)
            return 0

        logger.info(f"PLAN_LOADED | experiment={experiment_id} | run={run_id if run_id else 'all'} | items={total_items}")

        # Step 2: Execute plan (pure execution, no DB)
        debug_enabled = os.getenv("OPENROUTER_DEBUG_ENABLED", "false").lower() == "true"
        api_client = OpenRouterClient(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            debug_enabled=debug_enabled,
        )
        randomizer = AnswerRandomizer(seed=plan.runs[0].seed_effective if plan.runs[0].seed_effective else 42)
        parser = AnswerParser()

        engine = ExecutionEngine(api_client, randomizer, parser)
        results = engine.execute(plan)

        # Step 3: Write results to DB
        writer = ResultWriter(conn)
        report = writer.write_results(results)

        # Calculate totals
        succeeded = report.responses_written
        failed = report.errors_written
        total = succeeded + failed

        logger.info(f"EXECUTE_COMPLETE | run={run_id if run_id else 'all'} | experiment={experiment_id} | total={total} | succeeded={succeeded} | failed={failed}")

        # Print summary (user-facing output stays as print)
        print(f"✓ Execution completed")
        print(f"  Runs executed: {len(report.runs_updated)}")
        print(f"  Success: {report.responses_written}")
        print(f"  Failed: {report.errors_written}")
        print(f"  Skipped (already existed): {report.responses_skipped}")
        if report.runs_updated:
            for run_id_item, status in report.runs_updated:
                print(f"  Run {run_id_item} status: {status}")

        return 0

    except PlannerValidationError as e:
        logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error=PlannerValidationError: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error=Missing configuration: {e}")
        print(f"Error: Missing required configuration: {e}", file=sys.stderr)
        print("Hint: Check that OPENROUTER_API_KEY is set in your system environment variables.", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"EXECUTE_ERROR | experiment={experiment_id} | error=Unexpected error: {e}")
        print(f"Error: Execution failed: {e}", file=sys.stderr)
        print("Hint: Ensure OPENROUTER_API_KEY is set and all required configuration is present.", file=sys.stderr)
        return 1


def main(mode: Mode) -> int:
    """Main entry point.
    
    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).
        
    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    parser = create_parser()
    args = parser.parse_args()

    conn = get_database_connection()

    try:
        if args.execute:
            return handle_execute(args, conn)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.", file=sys.stderr)
        return 130
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
