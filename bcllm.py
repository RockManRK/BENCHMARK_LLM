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


def _handle_composite_flow(argv: list[str], mode: Mode, module_name: str) -> bool:
    """Handle composite flow: CREATE + ADD_*.
    
    If --create-experiment is present with one or more --add-* actions:
    1. Create the experiment FIRST
    2. Execute ALL --add-* actions in sequence (model -> questions -> run)
    3. Propagate context to each action
    
    Args:
        argv: Raw command-line arguments.
        mode: Resolved CLI mode.
        module_name: Resolved module name (last action in sequence).
        
    Returns:
        True if composite flow was handled, False otherwise.
    """
    # Check if this is a composite flow
    has_create = has_flag(argv, "--create-experiment")
    has_add_action = any(has_flag(argv, flag) for flag in ADD_ACTION_FLAGS)
    
    if not (has_create and has_add_action):
        return False  # Not a composite flow

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
                # Continue to execute actions on existing experiment
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

        # Execute ALL --add-* actions in sequence
        _execute_all_add_actions(argv, experiment_name, conn, logger)
        
        return True  # Composite flow handled

    finally:
        conn.close()


def _execute_all_add_actions(argv: list[str], experiment_name: str, conn, logger) -> None:
    """Execute all --add-* actions in sequence.
    
    Execution order: model -> questions -> run
    
    Args:
        argv: Raw command-line arguments.
        experiment_name: Name of the experiment.
        conn: Database connection.
        logger: Logger instance.
    """
    add_actions = [flag for flag in ADD_ACTION_FLAGS if has_flag(argv, flag)]
    
    if not add_actions:
        return
    
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
        
        _execute_single_action(action_flag, action_argv, conn, logger)

def _execute_single_action(action_flag: str, argv: list[str], conn, logger) -> None:
    """Execute a single --add-* action.
    
    Args:
        action_flag: The action flag (--add-model, --add-questions, or --add-run).
        argv: Command-line arguments for this action (should only contain relevant flags).
        conn: Database connection.
        logger: Logger instance.
    """
    from src.core.mode import Mode
    
    if action_flag == "--add-model":
        from src.cli import bcllm_model
        # Parse and execute
        parser = bcllm_model.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        bcllm_model.handle_add_model(args, conn)
        
    elif action_flag in ("--add-questions", "--questions"):
        from src.cli import bcllm_questions
        # Parse and execute
        parser = bcllm_questions.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        bcllm_questions.handle_add_questions(args, conn)
        
    elif action_flag == "--add-run":
        from src.cli import bcllm_run
        # Parse and execute
        parser = bcllm_run.create_parser()
        args = parser.parse_args(argv[1:])  # Skip script name
        bcllm_run.handle_add_run(args, conn)
    
    logger.info(f"COMPOSITE_FLOW | action={action_flag} completed")


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
    if _handle_composite_flow(argv if argv is not None else sys.argv, mode, module_name):
        return 0  # Composite flow handled successfully

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
