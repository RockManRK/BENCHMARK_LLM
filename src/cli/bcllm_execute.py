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
    bcllm_execute.py --experiment <name> --execute --questions 1,3,10-20
    bcllm_execute.py --experiment <name> --execute --models var_xyz789,var_abc
    bcllm_execute.py --experiment <name> --execute --retry-policy max_attempts=5,backoff=linear

--questions/--models syntax changed 2026-08-21 (CLI migration marco 4C,
user decision — see src/cli/commands/execute.py's module docstring for
the full reasoning and docs/status/known-issues.md for the decision
record): argparse's `nargs="+"` (space-separated, one flag occurrence)
has no Click/Typer equivalent, so both flags moved to a single
comma-separated value. --questions now also selects by 1-based POSITION
in the dataset, not the source dataset's own question ID — the old
`Q001` format is removed entirely, no alias.

Exit Codes:
    0: Success
    1: Validation error (not found, invalid input, execution failure)
    2: Usage error (malformed --questions/--models specification)

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

import sys
import os
import logging
from typing import Any

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import ParserExit
from src.cli.commands.execute import parse_execute_argv, ExecuteParsedArgs
from src.db.repository import ExperimentRepository, RunRepository, VariantRepository, SnapshotRepository
from src.core.planner import Planner, PlannerValidationError
from src.core.async_orchestrator import AsyncOrchestrator
from src.core.execution_plan import RetryPolicy
from src.api.client import OpenRouterClient
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event


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


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements. --experiment/--run
# are FORBIDDEN identity selectors, consistent with every other module —
# this classification did not exist before the marco 4C Typer conversion
# (2026-08-21): the pre-conversion argparse version called plain
# parser.parse_args() with zero system-default handling of any kind, so
# `bcllm --experiment system-default --execute` previously produced a
# confusing "Experiment not found: system-default" instead of an honest
# usage error — see docs/status/known-issues.md. --questions/--models/
# --retry-policy/--execute are NOT_APPLICABLE (no inheritance/creation-time
# default concept — pure per-invocation runtime values). Kept as a
# module-level constant for cross-module consistency checks
# (tests/unit/cli/test_system_default_classification_consistency.py) — no
# longer consumed by parsing directly: src/cli/commands/execute.py's
# _execute_command declares the same classification via its per-option
# callbacks.
SYSTEM_DEFAULT_FORBIDDEN = {
    'experiment', 'run',
}


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


def validate_filters(
    conn, experiment_id: str, run_id: str | None,
    question_positions: list[int] | None, model_variant_ids: list[str] | None,
) -> list[str]:
    """Validate that specified filters exist.

    Args:
        conn: Database connection
        experiment_id: Experiment identifier
        run_id: Optional run ID filter
        question_positions: Optional 1-based question_position filters
            (format already validated by src/cli/commands/execute.py's
            parse_question_position_spec — this only checks EXISTENCE in
            this experiment's snapshots)
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

    # Validate question positions exist in experiment
    if question_positions:
        snapshot_repo = SnapshotRepository(conn)
        snapshots = snapshot_repo.list_by_experiment(experiment_id)
        existing_positions = {s.question_position for s in snapshots}

        for position in question_positions:
            if position not in existing_positions:
                errors.append(f"Question position not found in experiment: {position}")

    # Validate model variant IDs exist in experiment
    if model_variant_ids:
        # Fixed 2026-08-21 (marco 4C): this called
        # list_by_experiment(experiment_id, active_only=True), a keyword
        # VariantRepository.list_by_experiment never accepted (there is
        # no "active"/soft-delete concept on model_variants — see
        # docs/contracts/immutability.md) — every real --execute --models
        # invocation raised TypeError, undetected because the pre-existing
        # test file mocked around the real repository call entirely. See
        # docs/status/known-issues.md.
        variant_repo = VariantRepository(conn)
        variants = variant_repo.list_by_experiment(experiment_id)
        existing_variant_ids = {v.variant_id for v in variants}

        for vid in model_variant_ids:
            if vid not in existing_variant_ids:
                errors.append(f"Model variant not found in experiment: {vid}")

    return errors


def handle_execute(args: ExecuteParsedArgs, conn, operation_id: str | None = None) -> int:
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
        emit_event(
            logger, Event.EXECUTE_ERROR, level=logging.ERROR,
            operation_id=operation_id, experiment=args.experiment,
            error="Experiment not found",
        )
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    experiment_id = experiment.experiment_id
    run_id = args.run

    emit_event(
        logger, Event.EXECUTE_START, operation_id=operation_id,
        experiment=args.experiment, run=run_id if run_id else "all",
        experiment_id=experiment_id,
    )

    # Filters are already parsed AND format-validated by
    # src/cli/commands/execute.py's Typer command (exit 2 for a malformed
    # --questions/--models spec, before this function is ever called) —
    # args.questions is a list[int] of 1-based positions, args.models a
    # list[str] of literal variant identifiers, both already resolved.
    question_positions = args.questions
    model_variant_ids = args.models

    # Validate filters exist in this experiment (domain-level, exit 1 —
    # distinct from the exit-2 format validation above)
    validation_errors = validate_filters(conn, experiment_id, run_id, question_positions, model_variant_ids)
    if validation_errors:
        for error in validation_errors:
            emit_event(
                logger, Event.EXECUTE_ERROR, level=logging.ERROR,
                operation_id=operation_id, experiment=args.experiment,
                experiment_id=experiment_id, error=error,
            )
            print(f"Error: {error}", file=sys.stderr)
        return 1

    # Parse retry policy
    retry_policy = RetryPolicy()
    if args.retry_policy:
        try:
            retry_policy = parse_retry_policy(args.retry_policy)
        except (ValueError, TypeError) as e:
            emit_event(
                logger, Event.EXECUTE_ERROR, level=logging.ERROR,
                operation_id=operation_id, experiment=args.experiment,
                experiment_id=experiment_id, error=f"Invalid retry policy: {e}",
            )
            print(f"Error: Invalid retry policy: {e}", file=sys.stderr)
            return 1

    try:
        # ORCHESTRATION: Planner → ExecutionEngine → ResultWriter

        # Step 1: Build execution plan with filters
        planner = Planner(conn)
        plan = planner.build_plan(
            args.experiment,
            run_ids=[run_id] if run_id else None,
            question_ids=question_positions,
            model_variant_ids=model_variant_ids,
            retry_policy=retry_policy,
            operation_id=operation_id,
        )

        # Validate plan has work to do. Planner.build_plan() already
        # emits Event.PLAN_LOADED/PLAN_BUILD_COMPLETE (with
        # experiment/models/questions/runs/total_items fields, including
        # the total_items=0 case) — no redundant manual log line needed
        # here, only the user-facing print() for the empty case.
        total_items = sum(len(run.items) for run in plan.runs)
        if not plan.runs or total_items == 0:
            print("No pending items to execute. All items completed.", file=sys.stderr)
            return 0

        # Step 2: Execute plan via AsyncOrchestrator
        debug_enabled = os.getenv("OPENROUTER_DEBUG_ENABLED", "false").lower() == "true"
        logger.info(f"OPENROUTER_DEBUG_ENABLED={debug_enabled} (from env: {os.getenv('OPENROUTER_DEBUG_ENABLED', 'NOT_SET')})")
        api_client = OpenRouterClient(
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            debug_enabled=debug_enabled,
        )
        # Randomization is explicitly enabled only when the run's
        # Randomization Seed is set. None means randomization OFF. No fallback.
        randomizer = AnswerRandomizer(seed=plan.runs[0].randomization_seed_effective)
        parser = AnswerParser()

        orchestrator = AsyncOrchestrator(
            api_client=api_client,
            db_connection=conn,
            randomizer=randomizer,
            parser=parser,
            logger=logger,
            max_concurrency=int(os.environ.get("BCLLM_MAX_CONCURRENCY", "1")),
        )

        results = orchestrator.execute(plan)

        # Calculate totals from orchestrator results (already in DB)
        succeeded = sum(1 for r in results if r.status == 'success')
        failed = sum(1 for r in results if r.status == 'failure')
        total = succeeded + failed

        emit_event(
            logger, Event.EXECUTE_COMPLETE, operation_id=operation_id,
            run=run_id if run_id else "all", experiment=args.experiment,
            experiment_id=experiment_id, total=total, succeeded=succeeded, failed=failed,
        )

        # Print summary (user-facing output stays as print)
        print(f"✓ Execution completed")
        print(f"  Runs executed: {len(plan.runs)}")
        print(f"  Success: {succeeded}")
        print(f"  Failed: {failed}")
        print(f"  Total: {total}")
        for run_item in plan.runs:
            print(f"  Run {run_item.run_id} items: {len(run_item.items)}")

        return 0

    except PlannerValidationError as e:
        emit_event(
            logger, Event.EXECUTE_ERROR, level=logging.ERROR,
            operation_id=operation_id, experiment=args.experiment,
            experiment_id=experiment_id, error=f"PlannerValidationError: {e}",
        )
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        emit_event(
            logger, Event.EXECUTE_ERROR, level=logging.ERROR,
            operation_id=operation_id, experiment=args.experiment,
            experiment_id=experiment_id, error=f"Missing configuration: {e}",
        )
        print(f"Error: Missing required configuration: {e}", file=sys.stderr)
        print("Hint: Check that OPENROUTER_API_KEY is set in your system environment variables.", file=sys.stderr)
        return 1
    except Exception as e:
        emit_event(
            logger, Event.EXECUTE_ERROR, level=logging.ERROR,
            operation_id=operation_id, experiment=args.experiment,
            experiment_id=experiment_id, error=f"Unexpected error: {e}",
        )
        print(f"Error: Execution failed: {e}", file=sys.stderr)
        print("Hint: Ensure OPENROUTER_API_KEY is set and all required configuration is present.", file=sys.stderr)
        return 1


def main(mode: Mode, operation_id: str | None = None) -> int:
    """Main entry point.

    Args:
        mode: The CLI mode (CREATE, MODIFY, EXECUTE, INVALID).
        operation_id: Correlation ID for the CLI invocation (logging only) —
            threaded into Planner.build_plan() so every event emitted while
            executing this plan (Planner, ExecutionEngine, AsyncOrchestrator,
            RetryHandler, ResultWriter, OpenRouterClient) shares it. See
            docs/status/checkpoint-c-logging-observability-design.md, §4.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    _validate_expected_mode(mode)
    argv = sys.argv[1:]

    try:
        args = parse_execute_argv(argv)
    except ParserExit as e:
        if e.status != 0:
            return e.status
        return 0  # --help or other clean parser exit

    conn = get_database_connection()

    try:
        if args.execute:
            return handle_execute(args, conn, operation_id=operation_id)
        else:
            # Reachable: --execute is a plain optional boolean (no mutex
            # group in the argparse original either — this module has
            # exactly one action, and running `bcllm --experiment X`
            # without it falls through here, matching the pre-Typer
            # behavior exactly).
            print("Error: no valid execute action specified. Use --execute.", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        emit_event(get_logger('cli.execute'), Event.COMMAND_INTERRUPTED, operation_id=operation_id, command="execute")
        print("\nExecution interrupted by user.", file=sys.stderr)
        return 130
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
