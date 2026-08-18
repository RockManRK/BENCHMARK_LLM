#!/usr/bin/env python3
"""CLI entry point — dispatches exclusively to src.

This module implements the CLI Module Resolution Contract:
- Orchestrates composite flows (CREATE + ADD_*)
- Creates experiment ONCE before action execution
- Propagates experiment context to action modules
- Action modules NEVER create experiments
"""
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.core.mode import Mode
from src.core.mode_resolver import resolve_mode
from src.core.module_resolver import resolve_module, has_flag, ADD_ACTION_FLAGS
from src.core.mode_matrix import validate_mode_matrix, ModeMatrixError
from src.utils.logging_config import setup_logging, LoggingConfig

# Load .env file at application startup
# This ensures all environment variables are available for CLI modules
load_dotenv(".env", override=True)


def _extract_experiment_name(argv: list[str]) -> str | None:
    """Extract experiment name from argv.
    
    Supports:
    - --create-experiment NAME
    - --create-experiment=NAME
    - --experiment NAME
    - --experiment=NAME
    
    Args:
        argv: Raw command-line arguments.
        
    Returns:
        Experiment name if found, None otherwise.
    """
    args = argv[1:] if len(argv) > 0 else []
    
    for i, arg in enumerate(args):
        # Handle --create-experiment=NAME or --experiment=NAME
        if "=" in arg:
            flag, value = arg.split("=", 1)
            if flag in ("--create-experiment", "--experiment"):
                return value.strip()
        # Handle --create-experiment NAME or --experiment NAME
        elif arg in ("--create-experiment", "--experiment"):
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                return args[i + 1].strip()
    
    return None


def _handle_composite_flow(argv: list[str], mode: Mode, module_name: str) -> tuple[bool, int]:
    """Handle composite flow: CREATE + ADD_*.

    If --create-experiment is present with one or more --add-* actions:
    1. Create the experiment FIRST
    2. Execute --add-* actions in sequence (model -> questions -> run),
       stopping at the first one that fails
    3. Propagate context to each action
    4. If any action failed AND this invocation is the one that created
       the experiment (not a pre-existing one found via TOCTOU handling),
       roll back: delete the experiment and anything the earlier,
       successful actions created for it, so a failed composite command
       never leaves a partially-configured experiment behind — see
       docs/status/known-issues.md ("Composite --create-experiment +
       --add-questions is not atomic").

    Args:
        argv: Raw command-line arguments.
        mode: Resolved CLI mode.
        module_name: Resolved module name (last action in sequence).

    Returns:
        (handled, exit_code). handled=False means this wasn't a composite
        flow at all (caller should fall through to normal routing).
        handled=True means it was handled; exit_code is 0 on full success,
        non-zero if any --add-* action failed (and, when applicable, was
        rolled back).
    """
    # Check if this is a composite flow
    has_create = has_flag(argv, "--create-experiment")
    has_add_action = any(has_flag(argv, flag) for flag in ADD_ACTION_FLAGS)

    if not (has_create and has_add_action):
        return False, 0  # Not a composite flow

    # Extract experiment name
    experiment_name = _extract_experiment_name(argv)
    if not experiment_name:
        print(
            "Error: Composite flow requires experiment name.\n"
            "Usage: bcllm --create-experiment <name> --add-model <model_id>",
            file=sys.stderr
        )
        sys.exit(1)

    # =========================================================================
    # PRECONDITION VALIDATION (BEFORE creating experiment)
    # =========================================================================
    # Validate prerequisites to avoid creating partially configured experiments.
    # This does NOT block ADD_* actions - only validates that required
    # configuration exists for the benchmark system to function.
    # =========================================================================
    
    # Validate: QUESTIONS_DATASET_PATH required if --add-questions is present
    has_add_questions = has_flag(argv, "--add-questions") or has_flag(argv, "--questions")
    if has_add_questions:
        questions_path = os.getenv("QUESTIONS_DATASET_PATH")
        if not questions_path:
            print(
                "Error: --add-questions requires QUESTIONS_DATASET_PATH in .env\n"
                "Hint: Add QUESTIONS_DATASET_PATH=./data/questions.json to your .env file",
                file=sys.stderr
            )
            sys.exit(1)
        
        logger = setup_logging(LoggingConfig(
            log_file_path=Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        ))
        logger.info(f"PRECONDITION | QUESTIONS_DATASET_PATH validated: {questions_path}")
    
    # Validate: OPENROUTER_API_KEY always required for benchmark system
    # This is a system-level prerequisite, not action-specific
    if not os.getenv("OPENROUTER_API_KEY"):
        print(
            "Error: OPENROUTER_API_KEY must be set in environment\n"
            "Hint: Set it via system environment variable (not in .env for security)",
            file=sys.stderr
        )
        sys.exit(1)
    
    # =========================================================================
    # END PRECONDITION VALIDATION
    # =========================================================================

    # Create the experiment BEFORE dispatching to action module
    # This ensures the action module can assume the experiment exists
    from src.cli.database import get_database_connection
    from src.cli.bcllm_experiment import _create_experiment_with_config, create_parser
    from src.core.argv_utils import parse_args_normalized

    logger = setup_logging(LoggingConfig(
        log_file_path=Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO")
    ))

    logger.info(f"COMPOSITE_FLOW | creating experiment={experiment_name} before action={module_name}")

    conn = get_database_connection()
    # Only roll back an experiment THIS invocation created — never one
    # found pre-existing via the TOCTOU handling below, which belongs to
    # whatever process actually created it.
    experiment_created_by_us = True
    try:
        # Filter argv to only include experiment creation flags
        # Remove --add-* flags as they will be handled separately
        create_argv = ['bcllm', '--create-experiment', experiment_name]
        
        skip_next = False
        for i, arg in enumerate(argv[1:], 1):
            if skip_next:
                skip_next = False
                continue
            
            if arg == '--create-experiment':
                skip_next = True
                continue
            
            if arg.startswith('--create-experiment='):
                continue
            
            # Skip ADD_* flags (handled later)
            if arg in ADD_ACTION_FLAGS:
                continue
            
            # Add other config flags
            if arg.startswith('--') and arg not in ('--execute',):
                create_argv.append(arg)
                if '=' not in arg and i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                    create_argv.append(argv[i + 1])
                    skip_next = True
        
        # Parse filtered CLI args
        parser = create_parser()
        args = parse_args_normalized(parser, create_argv[1:])

        # Use shared experiment creation function to ensure consistency
        # Pass original CLI args so ConfigResolver can apply .env defaults
        # following CLI > .env > NULL priority chain
        #
        # TOCTOU Protection:
        # Wrap in try/except to handle concurrent experiment creation.
        # If two processes run the same composite command simultaneously,
        # both might pass the existence check in _create_experiment_with_config,
        # but only one will succeed in the INSERT. The other will catch
        # IntegrityError (DB-level) or ValueError (app-level check) and handle gracefully.
        try:
            _create_experiment_with_config(experiment_name, args, conn, logger)
        except ValueError as e:
            # Application-level check caught existing experiment
            # This can happen in TOCTOU scenario where another process created it first
            if "already exists" in str(e):
                logger.info(
                    f"COMPOSITE_FLOW | experiment already exists (concurrent)={experiment_name}"
                )
                # Continue to execute actions on existing experiment.
                # It's not ours to roll back if an action fails below.
                experiment_created_by_us = False
            else:
                # Re-raise if it's a different ValueError
                raise
        except sqlite3.IntegrityError as e:
            # Check if it's a unique constraint violation on experiment name
            error_msg = str(e).lower()
            if "unique constraint failed" in error_msg and "experiment.name" in error_msg:
                # Another process created it first - this is expected in concurrent scenarios
                # Fetch the existing experiment to confirm it exists
                from src.cli.database import get_database_connection
                from src.db.repository import ExperimentRepository

                check_conn = get_database_connection()
                try:
                    exp_repo = ExperimentRepository(check_conn)
                    existing = exp_repo.get_by_name(experiment_name)
                    if existing:
                        logger.info(
                            f"COMPOSITE_FLOW | experiment already exists (concurrent)={experiment_name} | "
                            f"experiment_id={existing.experiment_id}"
                        )
                        # Continue to execute actions on existing experiment
                    else:
                        # This shouldn't happen - re-raise
                        raise
                finally:
                    check_conn.close()

            # Re-raise if it's a different integrity error
            raise

        # Execute --add-* actions in sequence, stopping at the first failure
        action_exit_code = _execute_all_add_actions(argv, experiment_name, conn, logger)

        if action_exit_code != 0 and experiment_created_by_us:
            _rollback_created_experiment(conn, experiment_name, logger)

        return True, action_exit_code  # Composite flow handled

    finally:
        conn.close()


def _rollback_created_experiment(conn: sqlite3.Connection, experiment_name: str, logger) -> None:
    """Delete an experiment (and anything created for it) after a failed
    --add-* action during composite --create-experiment flow.

    Only ever called on an experiment THIS invocation just created (the
    experiment_created_by_us guard in _handle_composite_flow) — never on
    one found pre-existing via TOCTOU handling.

    Why explicit DELETEs instead of a transaction rollback: each handler
    (handle_add_model/handle_add_questions/handle_add_run, and the
    ExperimentRepository save that created the experiment itself) commits
    its own writes immediately after saving — that's the existing
    convention throughout src/db/repository.py, unrelated to this fix. By
    the time a later action fails, everything an earlier successful
    action wrote is already durably committed; there is no open
    transaction left for conn.rollback() to undo. Changing every handler
    to defer commits until the whole composite flow finishes would also
    change the commit behavior of standalone (non-composite) --add-*
    invocations, a much larger and riskier change than this task asked
    for — so this rolls back by deleting the specific rows instead.

    Note: src/db/schema.py (the actual runtime schema — src/db/schema.sql
    is a separate, stale reference copy, do not trust it) DOES declare ON
    DELETE CASCADE from model_variants/question_snapshots/runs to
    experiments, so exp_repo.delete(experiment_id) alone would already
    remove them. The explicit DELETEs here are redundant with that
    cascade, not a workaround for its absence — kept for clarity and as a
    belt-and-suspenders measure, not because cascade is missing.

    Composite flow can only run --add-model/--add-questions/--add-run
    (ADD_ACTION_FLAGS never includes --execute), so only
    question_snapshots, model_variants, and runs should reference the
    experiment at this point — no responses/errors rows should exist yet.
    That assumption is verified below rather than trusted, and this is
    the part that actually matters: responses/errors reference
    runs/model_variants/question_snapshots WITHOUT cascade, so if this
    assumption is ever violated (e.g. ADD_ACTION_FLAGS grows to include
    something that can produce responses), a plain cascade-delete of the
    experiment would either silently orphan those rows or fail outright
    depending on order — this check refuses to delete anything and logs
    loudly instead, rather than risk either.

    See docs/status/known-issues.md ("--remove-experiment does a real,
    undocumented hard cascading delete") for the broader discovery this
    surfaced: unlike this function (new experiment only, no responses/
    errors possible yet), the existing --remove-experiment CLI command
    can hard-delete an arbitrary experiment's snapshots/variants/runs at
    any time, which is a live tension with docs/contracts/immutability.md
    and was flagged to the user rather than resolved here.
    """
    from src.db.repository import ExperimentRepository

    exp_repo = ExperimentRepository(conn)
    experiment = exp_repo.get_by_name(experiment_name)
    if experiment is None:
        # Nothing to roll back (e.g. the create step itself never
        # committed a row before the first --add-* action ran).
        return

    experiment_id = experiment.experiment_id
    cursor = conn.cursor()

    orphan_responses = cursor.execute(
        """
        SELECT COUNT(*) FROM responses resp
        JOIN runs r ON r.run_id = resp.run_id
        WHERE r.experiment_id = ?
        """,
        (experiment_id,),
    ).fetchone()[0]
    orphan_errors = cursor.execute(
        """
        SELECT COUNT(*) FROM errors err
        JOIN runs r ON r.run_id = err.run_id
        WHERE r.experiment_id = ?
        """,
        (experiment_id,),
    ).fetchone()[0]
    if orphan_responses or orphan_errors:
        logger.error(
            f"COMPOSITE_FLOW_ROLLBACK_ABORTED | experiment={experiment_name} | "
            f"experiment_id={experiment_id} | responses={orphan_responses} | errors={orphan_errors} | "
            f"reason=unexpected_responses_or_errors_present_refusing_to_delete_experiment"
        )
        return

    cursor.execute("DELETE FROM question_snapshots WHERE experiment_id = ?", (experiment_id,))
    cursor.execute("DELETE FROM model_variants WHERE experiment_id = ?", (experiment_id,))
    cursor.execute("DELETE FROM runs WHERE experiment_id = ?", (experiment_id,))
    conn.commit()

    exp_repo.delete(experiment_id)

    fk_issues = cursor.execute("PRAGMA foreign_key_check").fetchall()
    if fk_issues:
        # Should be unreachable given the orphan check above, but this is
        # a rollback path — verify rather than assume.
        logger.error(
            f"COMPOSITE_FLOW_ROLLBACK_INTEGRITY_WARNING | experiment={experiment_name} | "
            f"experiment_id={experiment_id} | foreign_key_issues={fk_issues}"
        )

    logger.info(
        f"COMPOSITE_FLOW_ROLLBACK | experiment={experiment_name} | experiment_id={experiment_id} | "
        f"reason=add_action_failed"
    )


def _execute_all_add_actions(argv: list[str], experiment_name: str, conn, logger) -> int:
    """Execute --add-* actions in sequence, stopping at the first failure.

    Execution order: model -> questions -> run

    Args:
        argv: Raw command-line arguments.
        experiment_name: Name of the experiment.
        conn: Database connection.
        logger: Logger instance.

    Returns:
        0 if every action succeeded (or there were none to run); the
        failing action's exit code otherwise. Actions after the first
        failure are NOT executed — the caller (_handle_composite_flow)
        rolls back on a non-zero result.
    """
    add_actions = [flag for flag in ADD_ACTION_FLAGS if has_flag(argv, flag)]

    if not add_actions:
        return 0

    logger.info(f"COMPOSITE_FLOW | executing actions={add_actions} in sequence")
    
    for action_flag in add_actions:
        logger.info(f"COMPOSITE_FLOW | executing action={action_flag}")
        
        # Build filtered argv for this action
        action_argv = ["bcllm", "--experiment", experiment_name]
        
        # Define relevant flags for each action
        relevant_flags = {
            "--add-model": [
                "--reasoning", "--max-tokens", "--reasoning-tokens",
                "--temperature", "--top-p", "--top-k", "--repeat-penalty",
                "--vision", "--structured", "--url", "--provider"
            ],
            "--add-questions": [
                "--where", "--exclude", "--source-file"
            ],
            "--add-run": [
                "--seed", "--system-prompt", "--user-prompt"
            ]
        }
        
        action_relevant = relevant_flags.get(action_flag, [])
        
        skip_next = False
        for i, arg in enumerate(argv[1:], 1):
            if skip_next:
                skip_next = False
                continue
            
            if arg == '--create-experiment':
                skip_next = True
                continue

            if arg.startswith('--create-experiment='):
                continue

            # Special handling for CURRENT --add-* flag only (capture its value)
            if action_flag == '--add-model' and arg == '--add-model' and i + 1 < len(argv):
                action_argv.append('--add-model')
                action_argv.append(argv[i + 1])
                skip_next = True
                continue

            if action_flag in ('--add-questions', '--questions') and arg in ('--add-questions', '--questions') and i + 1 < len(argv):
                action_argv.append(arg)
                action_argv.append(argv[i + 1])
                skip_next = True
                continue

            if action_flag == '--add-run' and arg == '--add-run':
                action_argv.append('--add-run')
                continue

            if arg in ADD_ACTION_FLAGS:
                continue

            is_relevant = any(arg == flag or arg.startswith(f'{flag}=') for flag in action_relevant)
            if is_relevant:
                action_argv.append(arg)
                if '=' not in arg and i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                    action_argv.append(argv[i + 1])
                    skip_next = True
        
        exit_code = _execute_single_action(action_flag, action_argv, conn, logger)
        if exit_code != 0:
            logger.info(
                f"COMPOSITE_FLOW | action={action_flag} failed with exit_code={exit_code}; "
                f"stopping remaining actions"
            )
            return exit_code

    return 0


def _execute_single_action(action_flag: str, argv: list[str], conn, logger) -> int:
    """Execute a single --add-* action.

    Args:
        action_flag: The action flag (--add-model, --add-questions, or --add-run).
        argv: Command-line arguments for this action (should only contain relevant flags).
        conn: Database connection.
        logger: Logger instance.

    Returns:
        The action handler's exit code (0 for success, 1 for error).
    """
    if action_flag == "--add-model":
        from src.cli import bcllm_model
        # Parse and execute
        parser = bcllm_model.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        exit_code = bcllm_model.handle_add_model(args, conn)

    elif action_flag in ("--add-questions", "--questions"):
        from src.cli import bcllm_questions
        # Parse and execute
        parser = bcllm_questions.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        exit_code = bcllm_questions.handle_add_questions(args, conn)

    elif action_flag == "--add-run":
        from src.cli import bcllm_run
        # Parse and execute
        parser = bcllm_run.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        exit_code = bcllm_run.handle_add_run(args, conn)

    else:
        logger.error(f"COMPOSITE_FLOW | unknown action_flag={action_flag}")
        return 1

    logger.info(f"COMPOSITE_FLOW | action={action_flag} completed with exit_code={exit_code}")
    return exit_code


def route_to_v2(module_name: str, mode: Mode, argv: list[str] | None = None) -> int:
    """Route to src.cli module and return exit code.
    
    Orchestrates composite flows:
    - If CREATE + ADD_*: creates experiment FIRST, then dispatches to action module
    
    Args:
        module_name: Name of the v2 CLI module to route to.
        mode: The resolved CLI mode (CREATE, MODIFY, EXECUTE, EXPORT, INVALID).
        argv: Raw command-line arguments (for composite flow detection).
              If None, uses sys.argv.

    Returns:
        Exit code from the v2 module (0 for success, 1 for error).
    """
    # Handle composite flow: create experiment BEFORE dispatching
    # If composite flow was handled, all actions were executed - don't delegate again
    handled, composite_exit_code = _handle_composite_flow(
        argv if argv is not None else sys.argv, mode, module_name
    )
    if handled:
        return composite_exit_code

    from src.cli import (
        bcllm_experiment,
        bcllm_model,
        bcllm_questions,
        bcllm_run,
        bcllm_execute,
        bcllm_review,
        bcllm_export,
        bcllm_main,
        bcllm_provider,
    )

    if module_name == "bcllm_main":
        return bcllm_main.main(mode)
    elif module_name == "bcllm_experiment":
        return bcllm_experiment.main(mode)
    elif module_name in ("bcllm_model", "bcllm_questions", "bcllm_run"):
        # For action modules in CREATE mode, inject --experiment argument
        # The experiment was just created by _handle_composite_flow
        return _route_action_module_with_experiment(module_name, mode, argv if argv is not None else sys.argv)
    elif module_name == "bcllm_execute":
        return bcllm_execute.main(mode)
    elif module_name == "bcllm_review":
        return bcllm_review.main(mode)
    elif module_name == "bcllm_export":
        return bcllm_export.main(mode)
    elif module_name == "bcllm_provider":
        return bcllm_provider.main(mode)
    else:
        print(f"Error: Unknown v2 module: {module_name}", file=sys.stderr)
        return 1


def _route_action_module_with_experiment(module_name: str, mode: Mode, argv: list[str]) -> int:
    """Route to action module with experiment name injected.
    
    For composite flows (CREATE + ADD_*), the experiment is created first,
    then we need to inject --experiment into the arguments for the action module.
    
    Args:
        module_name: Target module name.
        mode: CLI mode.
        argv: Original command-line arguments.
        
    Returns:
        Exit code from module.
    """
    # Extract experiment name from argv
    experiment_name = _extract_experiment_name(argv)
    if not experiment_name:
        print("Error: Composite flow requires experiment name.", file=sys.stderr)
        return 1
    
    # Build modified argv for action module:
    # 1. Remove --create-experiment and its value
    # 2. Add --experiment <name> at the beginning
    modified_argv = ["bcllm"]  # Start with script name
    
    # Add --experiment <name> first
    modified_argv.extend(["--experiment", experiment_name])
    
    # Add remaining arguments, skipping --create-experiment and its value
    skip_next = False
    for i, arg in enumerate(argv[1:], 1):  # Skip script name
        if skip_next:
            skip_next = False
            continue
        
        if arg == "--create-experiment":
            skip_next = True  # Skip the value after --create-experiment
            continue
        
        if arg.startswith("--create-experiment="):
            continue  # Skip --create-experiment=VALUE format
        
        modified_argv.append(arg)
    
    # Save original argv and replace with modified version
    original_argv = sys.argv
    sys.argv = modified_argv
    
    try:
        # Import and call the appropriate module
        if module_name == "bcllm_model":
            from src.cli import bcllm_model
            return bcllm_model.main(mode)
        elif module_name == "bcllm_questions":
            from src.cli import bcllm_questions
            return bcllm_questions.main(mode)
        elif module_name == "bcllm_run":
            from src.cli import bcllm_run
            return bcllm_run.main(mode)
        else:
            print(f"Error: Unexpected module: {module_name}", file=sys.stderr)
            return 1
    finally:
        # Restore original argv
        sys.argv = original_argv


def main() -> int:
    """Main entry point — routes with explicit MODE × MODULE validation.
    
    Orchestrates composite flows:
    1. Resolve MODE and MODULE
    2. If CREATE + ADD_*: create experiment FIRST
    3. Validate MODE × MATRIX
    4. Dispatch to module

    Returns:
        Exit code (0 for success, 1 for error).
    """
    mode = resolve_mode(sys.argv)
    module = resolve_module(sys.argv)

    if module is None:
        if "--help" in sys.argv or "-h" in sys.argv:
            module = "bcllm_main"
        else:
            print("Error: No valid command found. Use --help for usage.", file=sys.stderr)
            return 1

    log_config = LoggingConfig(
        log_file_path=Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO")
    )
    logger = setup_logging(log_config)

    logger.info(f"APPLICATION_START | version=2.0 | mode={mode.value}")

    try:
        validate_mode_matrix(mode, module)
    except ModeMatrixError as e:
        print(str(e), file=sys.stderr)
        return 1

    logger.info(f"MODE_ROUTING | mode={mode.value} | matrix={module}")

    return route_to_v2(module, mode, sys.argv)


if __name__ == "__main__":
    sys.exit(main())
