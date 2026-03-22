#!/usr/bin/env python3
"""Execution entry point CLI.

This module provides the CLI command for executing benchmark runs:
- Orchestrates Planner → ExecutionEngine → ResultWriter flow
- Validates experiment and run existence
- Reports execution summary

Usage:
    bcllm_execute.py --experiment <name> --run <run_id> --execute

Exit Codes:
    0: Success
    1: Validation error (not found, invalid input, execution failure)

Orchestration Flow:
    1. Validate experiment exists
    2. Validate run exists and belongs to experiment
    3. Validate run is in pending status
    4. Planner.build_plan() → ExecutionPlan
    5. ExecutionEngine.execute() → ExecutionResult list
    6. ResultWriter.write_results() → WriteReport
    7. Print summary to console

CRITICAL: This module is ORCHESTRATION ONLY.
- No domain logic (retries, error handling in Engine)
- No inference (all validation is explicit)
- No mutable state (delegates to ResultWriter)
"""

import argparse
import sys

from src_v2.cli.database import get_database_connection
from src_v2.db.repository import ExperimentRepository, RunRepository
from src_v2.core.planner import Planner, PlannerValidationError
from src_v2.core.execution_engine import ExecutionEngine
from src_v2.core.result_writer import ResultWriter
from src_v2.core.randomizer import AnswerRandomizer
from src_v2.core.answer_parser import AnswerParser


# Placeholder for API client (to be implemented in Phase 8)
class OpenRouterClient:
    """Placeholder for OpenRouterClient.

    This is a stub that will be replaced with the real implementation
    from src_v2.api.client in Phase 8.
    """

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1") -> None:
        """Initialize with API credentials."""
        self.api_key = api_key
        self.base_url = base_url

    async def chat_completion(self, model_id: str, messages: list[dict], **kwargs):
        """Call OpenRouter chat completion API."""
        # Placeholder - will be implemented in Phase 8
        raise NotImplementedError("OpenRouterClient is not yet implemented")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for execute command.

    Returns:
        ArgumentParser configured with execute command arguments.
    """
    parser = argparse.ArgumentParser(
        prog="bcllm_execute.py",
        description="Execute benchmark runs",
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
        help="Run ID to execute",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the run",
    )

    return parser


def handle_execute(args, conn) -> int:
    """Handle --execute command. ORCHESTRATION ONLY.

    This function orchestrates the execution flow:
    1. Validate experiment exists
    2. Validate run exists and belongs to experiment
    3. Validate run is in pending status
    4. Build execution plan via Planner
    5. Execute plan via ExecutionEngine
    6. Write results via ResultWriter
    7. Print summary

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
    # Initialize repositories
    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    # Validate experiment exists
    experiment = exp_repo.get_by_name(args.experiment)
    if not experiment:
        print(f"Error: Experiment not found: {args.experiment}", file=sys.stderr)
        return 1

    # Validate run exists
    run = run_repo.get_by_id(args.run)
    if not run:
        print(f"Error: Run not found: {args.run}", file=sys.stderr)
        return 1

    # Validate run belongs to experiment
    if run.experiment_id != experiment.experiment_id:
        print(f"Error: Run '{args.run}' is not in experiment '{args.experiment}'", file=sys.stderr)
        return 1

    # Validate run is pending
    if run.status != "pending":
        print(f"Error: Run '{args.run}' is not pending (status: {run.status}). Only pending runs can be executed.", file=sys.stderr)
        return 1

    try:
        # ORCHESTRATION: Planner → ExecutionEngine → ResultWriter

        # Step 1: Build execution plan
        planner = Planner(conn)
        plan = planner.build_plan(args.experiment, run_ids=[args.run])

        # Validate plan has work to do
        if not plan.runs or not plan.runs[0].items:
            print(f"Error: Nothing to execute for run '{args.run}'.", file=sys.stderr)
            return 1

        # Step 2: Execute plan (pure execution, no DB)
        # Note: API key would come from environment in production
        api_client = OpenRouterClient(api_key="test-key")
        randomizer = AnswerRandomizer(seed=plan.runs[0].seed_effective)
        parser = AnswerParser()

        engine = ExecutionEngine(api_client, randomizer, parser)
        results = engine.execute(plan)

        # Step 3: Write results to DB
        writer = ResultWriter(conn)
        report = writer.write_results(results)

        # Print summary
        print(f"✓ Execution completed for run '{args.run}'")
        print(f"  Success: {report.responses_written}")
        print(f"  Failed: {report.errors_written}")
        print(f"  Skipped: {report.responses_skipped}")
        if report.runs_updated:
            print(f"  Run status updated to: {report.runs_updated[0][1]}")

        return 0

    except PlannerValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Execution failed: {e}", file=sys.stderr)
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
