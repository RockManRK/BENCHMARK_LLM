#!/usr/bin/env python3
"""CLI entry point — dispatches exclusively to src.

This module implements the CLI Module Resolution Contract:
- Orchestrates composite flows (CREATE + ADD_*)
- Creates experiment ONCE before action execution
- Propagates experiment context to action modules
- Action modules NEVER create experiments
"""
import logging
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.core.mode import Mode
from src.core.mode_resolver import resolve_mode
from src.core.module_resolver import resolve_module, has_flag, ADD_ACTION_FLAGS
from src.core.mode_matrix import validate_mode_matrix, ModeMatrixError
from src.core.argv_utils import ParserExit
from src.db.unit_of_work import UnitOfWork
from src.utils.logging_config import setup_logging, LoggingConfig
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event


def _bootstrap_environment() -> None:
    """Load .env into the process environment.

    Must be called exactly once, only from this module's real CLI
    entry points below (direct `python bcllm.py` execution, and the
    installed console script — both call cli_main(), see setup.py) —
    NEVER at import time. Importing bcllm.py (tests, tooling, any
    programmatic caller) must have zero side effects: it must never
    silently overwrite an environment the caller already prepared (e.g.
    via monkeypatch/os.environ), which `override=True` would otherwise
    do unconditionally. See docs/status/known-issues.md and
    docs/status/composite-flow-unit-of-work-design.md point 8/5.
    """
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


def _build_create_argv(argv: list[str], experiment_name: str) -> list[str]:
    """Build the filtered argv used to parse experiment-creation-time
    flags (everything except the ADD_* actions themselves) — pure, no
    I/O. Extracted unchanged from the original inline block so the
    pre-connection parse phase (_handle_composite_flow) and nothing else
    depends on this exact filtering logic."""
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

        # Skip ADD_* flags (handled separately)
        if arg in ADD_ACTION_FLAGS:
            continue

        # Add other config flags
        if arg.startswith('--') and arg not in ('--execute',):
            create_argv.append(arg)
            if '=' not in arg and i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                create_argv.append(argv[i + 1])
                skip_next = True

    return create_argv


# Relevant flags forwarded to each action's own filtered argv — see
# _build_action_argv. "--questions" is a true alias of "--add-questions"
# (see module_resolver.ADD_ACTION_FLAGS) and must forward the same
# relevant flags, or a composite flow using the alias would silently
# drop --where/--exclude/--source-file.
_ACTION_RELEVANT_FLAGS = {
    "--add-model": [
        "--reasoning", "--max-tokens", "--reasoning-tokens",
        "--max-reasoning",
        "--temperature", "--top-p", "--top-k", "--repeat-penalty",
        "--vision", "--structured", "--url", "--provider", "--model-seed",
    ],
    "--add-questions": ["--where", "--exclude", "--source-file"],
    "--questions": ["--where", "--exclude", "--source-file"],
    "--add-run": ["--randomization-seed", "--system-prompt", "--user-prompt"],
}


def _build_action_argv(action_flag: str, argv: list[str], experiment_name: str) -> list[str]:
    """Build the filtered argv for a single --add-* action — pure, no
    I/O. Extracted unchanged from the original _execute_all_add_actions
    inner loop body."""
    action_argv = ["bcllm", "--experiment", experiment_name]
    action_relevant = _ACTION_RELEVANT_FLAGS.get(action_flag, [])

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

    return action_argv


def _parse_all_add_action_requests(argv: list[str], experiment_name: str) -> list[tuple[str, object]]:
    """Pure: for every requested --add-* action, in the fixed execution
    order (model -> questions -> run, per ADD_ACTION_FLAGS), build its
    filtered argv (_build_action_argv) and parse it into a structured
    Request object via that module's parse_add_*_request() function. No
    database connection is opened anywhere in this function.

    Raises ParserExit(status) on the FIRST usage error encountered across
    ANY requested action — per
    docs/status/composite-flow-unit-of-work-design.md point 3, the
    composite flow must not open a connection (or acquire its
    transaction lock) at all if any requested action would fail to
    parse.
    """
    from src.cli import bcllm_model, bcllm_questions, bcllm_run

    add_actions = [flag for flag in ADD_ACTION_FLAGS if has_flag(argv, flag)]
    parsed: list[tuple[str, object]] = []

    for action_flag in add_actions:
        action_argv = _build_action_argv(action_flag, argv, experiment_name)
        if action_flag == "--add-model":
            request = bcllm_model.parse_add_model_request(action_argv[1:])
        elif action_flag in ("--add-questions", "--questions"):
            request = bcllm_questions.parse_add_questions_request(action_argv[1:])
        elif action_flag == "--add-run":
            request = bcllm_run.parse_add_run_request(action_argv[1:])
        else:  # pragma: no cover - unreachable given ADD_ACTION_FLAGS
            continue
        parsed.append((action_flag, request))

    return parsed


def _execute_action_request(
    action_flag: str, request: object, conn, logger, *, commit: bool,
    operation_id: str | None = None,
) -> int:
    """Dispatch an already-parsed Request to its module's run_add_*()
    (the DB-facing half: dispatch to the shared action + printing) —
    reusing the exact same code path standalone uses (run_add_model /
    run_add_questions / run_add_run), just supplying a pre-parsed
    `request` instead of `argv` so no re-parsing (and no pre-connection
    work) happens here. See each module's run_add_*() docstring."""
    if action_flag == "--add-model":
        from src.cli import bcllm_model
        exit_code = bcllm_model.run_add_model(conn=conn, commit=commit, request=request)
    elif action_flag in ("--add-questions", "--questions"):
        from src.cli import bcllm_questions
        exit_code = bcllm_questions.run_add_questions(conn=conn, commit=commit, request=request)
    elif action_flag == "--add-run":
        from src.cli import bcllm_run
        exit_code = bcllm_run.run_add_run(conn=conn, commit=commit, request=request)
    else:
        emit_event(
            logger, Event.COMPOSITE_FLOW, level=logging.ERROR, operation_id=operation_id,
            error=f"unknown action_flag={action_flag}",
        )
        return 1

    emit_event(
        logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
        action=action_flag, exit_code=exit_code,
    )
    return exit_code


def _handle_composite_flow(
    argv: list[str], mode: Mode, module_name: str, operation_id: str | None = None,
) -> tuple[bool, int]:
    """Handle composite flow: CREATE + ADD_*, with real atomicity.

    If --create-experiment is present with one or more --add-* actions:
    1. PURE PARSE PHASE (no connection, no lock): parse and normalize
       the experiment-creation flags AND every requested --add-*
       action's flags. Any usage error anywhere in this phase returns
       immediately — no database connection is ever opened for a usage
       error. See docs/status/composite-flow-unit-of-work-design.md
       point 3 for exactly which validations are, and are not, pure
       enough to live in this phase.
    2. DB PHASE: open one connection, wrap experiment creation + every
       requested action in a single src.db.unit_of_work.UnitOfWork
       (BEGIN IMMEDIATE). Every participating write passes commit=False.
       On full success, uow.commit() is called once. On any action
       failure (non-zero exit code, no exception) or any unexpected
       exception (including one raised by UnitOfWork.__enter__ itself,
       e.g. a busy-database timeout on BEGIN IMMEDIATE), nothing is
       committed and the whole transaction rolls back — the experiment
       row itself included, not just the --add-* actions' rows. No
       compensating DELETEs exist anymore; see
       docs/status/composite-flow-unit-of-work-design.md.
    3. An unexpected exception is NEVER shown to the user with its own
       text — a generic message is printed to stderr; full details
       (via exc_info) go only to the technical log.

    Args:
        argv: Raw command-line arguments.
        mode: Resolved CLI mode.
        module_name: Resolved module name (last action in sequence).

    Returns:
        (handled, exit_code). handled=False means this wasn't a composite
        flow at all (caller should fall through to normal routing).
        handled=True means it was handled; exit_code is 0 on full success,
        non-zero if any --add-* action failed (rolled back) or an
        unexpected failure occurred (also rolled back, exit code 1).
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
    # PRECONDITION VALIDATION (pure env/config checks, no DB, no lock)
    # =========================================================================
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

    if not os.getenv("OPENROUTER_API_KEY"):
        print(
            "Error: OPENROUTER_API_KEY must be set in environment\n"
            "Hint: Set it via system environment variable (not in .env for security)",
            file=sys.stderr
        )
        sys.exit(1)

    logger = setup_logging(LoggingConfig(
        log_file_path=Path(os.getenv("LOG_FILE_PATH", "./logs/benchmark.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_profile=os.getenv("LOG_PROFILE", "NORMAL"),
    ))
    if has_add_questions:
        emit_event(
            logger, Event.PRECONDITION, operation_id=operation_id,
            check="QUESTIONS_DATASET_PATH", value=questions_path,
        )
    emit_event(
        logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
        experiment=experiment_name, action=module_name,
    )

    # =========================================================================
    # PURE PARSE PHASE — no connection, no lock. Every usage error across
    # BOTH experiment-creation flags AND every requested --add-* action is
    # detected here, before get_database_connection() is ever called.
    #
    # What is NOT pre-validated here, and why (see
    # docs/status/composite-flow-unit-of-work-design.md point 3 for the
    # full enumeration): experiment "already exists" (needs a DB read);
    # the TOCTOU concurrent-creation race (needs the real INSERT
    # attempt); each action's experiment lookup, config-inheritance
    # resolution, and duplicate/dedup checks (all need the experiment's
    # committed config_json / existing rows). Experiment-level seed/
    # prompt config resolution (pure) stays bundled inside
    # _create_experiment_with_config alongside its DB-dependent existence
    # check — not split further in this pass (small, deliberate
    # simplification: that function is also the standalone
    # --create-experiment path's canonical implementation, and splitting
    # it has a larger blast radius than the win of pre-validating an
    # already-rare invalid-seed-at-creation-time case).
    # =========================================================================
    from src.cli.bcllm_experiment import _create_experiment_with_config
    from src.cli.commands.experiment import parse_experiment_argv

    create_argv = _build_create_argv(argv, experiment_name)
    try:
        create_args = parse_experiment_argv(create_argv[1:])
    except ParserExit as e:
        return True, e.status

    try:
        add_action_requests = _parse_all_add_action_requests(argv, experiment_name)
    except ParserExit as e:
        return True, e.status

    # =========================================================================
    # DB PHASE — connection opened, transaction acquired only now.
    # =========================================================================
    from src.cli.database import get_database_connection

    conn = get_database_connection()
    try:
        try:
            with UnitOfWork(conn, immediate=True) as uow:
                # Only used for a clearer log message below — no rollback
                # decision depends on this flag anymore: a real
                # conn.rollback() only ever undoes what THIS transaction
                # left uncommitted, which is automatically "what this
                # invocation did," whether or not the experiment already
                # existed.
                experiment_created_by_us = True

                # TOCTOU Protection: two processes racing the same
                # composite command might both pass the existence check
                # inside _create_experiment_with_config, but only one
                # succeeds at the INSERT. The other catches IntegrityError
                # (DB-level) or ValueError (app-level check) and handles
                # it gracefully. Confirmed empirically: a UNIQUE-constraint
                # IntegrityError does NOT poison the surrounding SQLite
                # transaction — statements after it on the same
                # connection/transaction still work normally.
                try:
                    _create_experiment_with_config(
                        experiment_name, create_args, conn, logger, commit=False,
                    )
                    uow.assert_active()
                except ValueError as e:
                    if "already exists" in str(e):
                        emit_event(
                            logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
                            experiment=experiment_name, note="already_exists_concurrent",
                        )
                        experiment_created_by_us = False
                    else:
                        # Genuine validation failure at experiment-creation
                        # time (e.g. an invalid --randomization-seed value). Nothing was
                        # created yet (the INSERT itself is what raised) —
                        # uow rolls back on exit (commit() never reached).
                        print(f"Error: {e}", file=sys.stderr)
                        return True, 1
                except sqlite3.IntegrityError as e:
                    error_msg = str(e).lower()
                    if "unique constraint failed" in error_msg and "experiment.name" in error_msg:
                        # Another process created it first — fetch the
                        # existing experiment (via a SEPARATE connection;
                        # reads are never blocked by our open BEGIN
                        # IMMEDIATE transaction, confirmed empirically) to
                        # confirm it exists.
                        from src.db.repository import ExperimentRepository

                        check_conn = get_database_connection()
                        try:
                            exp_repo = ExperimentRepository(check_conn)
                            existing = exp_repo.get_by_name(experiment_name)
                            if existing:
                                emit_event(
                                    logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
                                    experiment=experiment_name, experiment_id=existing.experiment_id,
                                    note="already_exists_concurrent",
                                )
                                experiment_created_by_us = False
                            else:
                                raise
                        finally:
                            check_conn.close()
                    else:
                        raise

                # Execute --add-* actions in the pre-parsed order,
                # stopping at the first failure.
                for action_flag, request in add_action_requests:
                    emit_event(logger, Event.COMPOSITE_FLOW, operation_id=operation_id, action=action_flag)
                    exit_code = _execute_action_request(
                        action_flag, request, conn, logger, commit=False, operation_id=operation_id,
                    )
                    if exit_code != 0:
                        emit_event(
                            logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
                            action=action_flag, exit_code=exit_code, note="stopping_and_rolling_back",
                        )
                        return True, exit_code  # uow rolls back on exit
                    uow.assert_active()

                uow.commit()
                emit_event(
                    logger, Event.COMPOSITE_FLOW, operation_id=operation_id,
                    experiment=experiment_name, created_by_us=experiment_created_by_us,
                    note="committed",
                )
                return True, 0
        except Exception as e:
            # Never show the user raw exception text — this can be
            # anything from a busy-database timeout on BEGIN IMMEDIATE
            # (UnitOfWork.__enter__), to a commit()/rollback() failure, to
            # a genuine bug. uow still rolls back for every one of those
            # (the "commit() never reached" default) except the
            # BEGIN IMMEDIATE case itself, where no transaction was ever
            # opened, so there is nothing to roll back. Operational
            # error, not a usage error: exit code 1.
            emit_event(
                logger, Event.COMPOSITE_FLOW, level=logging.ERROR, operation_id=operation_id,
                experiment=experiment_name, error=repr(e), note="unexpected_failure_rolled_back",
            )
            logger.error(
                f"COMPOSITE_FLOW | unexpected failure, rolled back | experiment={experiment_name} | {e!r}",
                exc_info=True,
            )
            print(
                "Error: an unexpected failure occurred while setting up the experiment. "
                "See the technical log for details.",
                file=sys.stderr,
            )
            return True, 1
    finally:
        conn.close()


def route_to_v2(
    module_name: str,
    mode: Mode,
    argv: list[str] | None = None,
    operation_id: str | None = None,
) -> int:
    """Route to src.cli module and return exit code.

    Orchestrates composite flows:
    - If CREATE + ADD_*: creates experiment FIRST, then dispatches to action module

    Args:
        module_name: Name of the v2 CLI module to route to.
        mode: The resolved CLI mode (CREATE, MODIFY, EXECUTE, EXPORT, INVALID).
        argv: Raw command-line arguments (for composite flow detection).
              If None, uses sys.argv.
        operation_id: Correlation ID for this CLI invocation (logging only).
              Currently only threaded into bcllm_execute (the deep
              Planner->ExecutionEngine->AsyncOrchestrator pipeline benefits
              most from per-item/per-retry correlation); the other modules
              are still covered by this invocation's own COMMAND_START/
              COMMAND_END in main() below. See
              docs/status/checkpoint-c-logging-observability-design.md, §4.

    Returns:
        Exit code from the v2 module (0 for success, 1 for error).
    """
    # Handle composite flow: create experiment BEFORE dispatching
    # If composite flow was handled, all actions were executed - don't delegate again
    handled, composite_exit_code = _handle_composite_flow(
        argv if argv is not None else sys.argv, mode, module_name, operation_id=operation_id,
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
        return bcllm_execute.main(mode, operation_id=operation_id)
    elif module_name == "bcllm_review":
        return bcllm_review.main(mode, operation_id=operation_id)
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

    Generates one operation_id per invocation (§4 of
    docs/status/checkpoint-c-logging-observability-design.md) and emits
    COMMAND_START/COMMAND_END around the entire dispatch — the one
    correlator every event from this invocation shares, regardless of
    which of the 9 CLI modules ends up handling it. Also closes the
    KeyboardInterrupt gap found during Checkpoint C's investigation: 7 of
    the 9 modules previously let Ctrl-C propagate as a raw traceback. The
    other 2 (bcllm_execute.py, bcllm_review.py) already had their own
    ad-hoc handlers — bcllm_execute's returned exit 130 correctly;
    bcllm_review's returned exit 0 and was fixed separately (2026-08-20)
    to also return 130. Both of those modules' own handlers still fire
    first and are never reached by this outer catch, which is the
    uniform fallback for the remaining 7.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    import uuid

    operation_id = f"op_{uuid.uuid4().hex[:8]}"

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
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_profile=os.getenv("LOG_PROFILE", "NORMAL"),
    )
    logger = setup_logging(log_config)

    emit_event(
        logger, Event.APPLICATION_START, operation_id=operation_id,
        version="2.0", mode=mode.value,
    )

    try:
        validate_mode_matrix(mode, module)
    except ModeMatrixError as e:
        print(str(e), file=sys.stderr)
        return 1

    emit_event(
        logger, Event.MODE_ROUTING, operation_id=operation_id,
        mode=mode.value, module=module,
    )

    command = mode.value
    emit_event(
        logger, Event.COMMAND_START, operation_id=operation_id,
        command=command, module=module,
    )

    try:
        exit_code = route_to_v2(module, mode, sys.argv, operation_id=operation_id)
    except KeyboardInterrupt:
        emit_event(logger, Event.COMMAND_INTERRUPTED, operation_id=operation_id, command=command)
        print("\nInterrupted by user.", file=sys.stderr)
        return 130

    emit_event(
        logger, Event.COMMAND_END, operation_id=operation_id,
        command=command, exit_code=exit_code,
    )

    return exit_code


def cli_main() -> int:
    """The real CLI entry point, shared by direct execution
    (`python bcllm.py ...`, below) and the installed console script
    (see setup.py's console_scripts, which points here) — the ONE place
    _bootstrap_environment() is called. Importing this module never
    triggers it."""
    _bootstrap_environment()
    return main()


if __name__ == "__main__":
    sys.exit(cli_main())
