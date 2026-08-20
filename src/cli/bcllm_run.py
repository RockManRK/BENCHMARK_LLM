#!/usr/bin/env python3
"""Run lifecycle management CLI.

This module provides CLI commands for managing runs within experiments:
- Create new runs (--add-run)
- List runs in an experiment (--list-runs)
- Show run details (--run)
- Remove runs (--remove-run)

Usage:
    bcllm_run.py --experiment <name> --add-run [--randomization-seed N] [--system_prompt P] [--user_prompt P]
    bcllm_run.py --experiment <name> --list-runs
    bcllm_run.py --experiment <name> --run <run_id>
    bcllm_run.py --experiment <name> --remove-run <run_id>

Exit Codes:
    0: Success
    1: Validation error (not found, precondition failed, invalid input)
    2: Usage error (bad/unrecognized argument, FORBIDDEN system-default
       value, invalid --randomization-seed value)

--randomization-seed controls ONLY AnswerRandomizer (the order options are
presented to the model in) — see docs/status/seed-vocabulary-separation-investigation.md.
It is unrelated to Model Seed (sent to the API for inference), which is a
model_variant-level concern, not a Run-level one, and does not exist as a
CLI flag on this module.

--add-run's single-action pipeline (argv -> parse/normalize/validate ->
AddRunRequest -> add_run_action -> AddRunResult) is used identically by
main() (standalone) and bcllm.py's composite --create-experiment flow —
see run_add_run()'s docstring and docs/status/known-issues.md ("same
action, same path" invariant).
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass

from src.core.mode import Mode
from src.cli.database import get_database_connection
from src.core.argv_utils import parse_args_normalized, has_flag, NonExitingArgumentParser, ParserExit
from src.core.special_config_values import ForceSystemDefault
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
        NonExitingArgumentParser configured with all run commands — see
        src/core/argv_utils.py for why this is NOT a plain
        argparse.ArgumentParser: --add-run can run inside bcllm.py's
        composite flow, where an uncontrolled sys.exit() (argparse's
        default for both --help and any usage error) would skip the
        composite flow's experiment rollback.
    """
    parser = NonExitingArgumentParser(
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
        "--randomization-seed",
        type=str,
        metavar="N",
        help="Randomization Seed for answer option shuffling (AUTO, number, "
             "or empty for None) — controls AnswerRandomizer only, never sent to the API",
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


# Explicit opt-in classification for system-default recognition — see
# src/core/special_config_values.py::normalize_special_config_values and
# docs/contracts/system-default-semantics.md for the full SUPPORTED/
# FORBIDDEN/NOT_APPLICABLE contract this implements.
SYSTEM_DEFAULT_SUPPORTED = {
    'randomization_seed', 'system_prompt', 'user_prompt',
}
SYSTEM_DEFAULT_FORBIDDEN = {
    'experiment', 'run', 'remove_run',
}


@dataclass(frozen=True)
class AddRunRequest:
    """Structured input for add_run_action — built by run_add_run() from
    parsed+normalized CLI args, never argv or argparse.Namespace directly.
    Field names mirror the CLI dest names 1:1 so this can be passed
    straight into ConfigResolver.build_run_config_dict() (which reads
    fields via getattr, duck-typed)."""
    experiment: str
    randomization_seed: str | ForceSystemDefault | None = None
    system_prompt: str | ForceSystemDefault | None = None
    user_prompt: str | ForceSystemDefault | None = None


@dataclass(frozen=True)
class AddRunResult:
    """Structured output from add_run_action.

    exit_code: 0 success, 1 operational/domain error (not found), 2 usage
        error (invalid --randomization-seed value — text that isn't an
        integer, 'AUTO', or system-default; see
        ConfigResolver.parse_randomization_seed_strict, which raises
        instead of silently becoming None).
    """
    exit_code: int
    error: str | None = None
    run_id: str | None = None
    randomization_seed_display: str | None = None


def add_run_action(request: AddRunRequest, conn, *, commit: bool = True) -> AddRunResult:
    """The shared --add-run action: precondition checks, config
    resolution, and the DB write. Pure — no argv/Namespace, no print(),
    no sys.exit(). Used identically by the standalone and composite
    adapters (see run_add_run).

    commit: whether the DB write commits immediately (default). The
        composite flow (bcllm.py) passes False to participate in its
        src.db.unit_of_work.UnitOfWork scope — see
        docs/status/composite-flow-unit-of-work-design.md."""
    from src.core.config_resolver import ConfigResolver

    exp_repo = ExperimentRepository(conn)
    run_repo = RunRepository(conn)

    experiment = exp_repo.get_by_name(request.experiment)
    if not experiment:
        return AddRunResult(exit_code=1, error=f"Experiment not found: {request.experiment}")

    resolver = ConfigResolver()
    resolver.load_env()

    run_id = f"run_{uuid.uuid4().hex[:8]}"

    try:
        config_dict = resolver.build_run_config_dict(request, experiment, run_id=run_id)
    except ValueError as e:
        # Invalid --randomization-seed text. Usage error, not operational
        # — the user typed something the CLI doesn't accept, same class
        # as a bad argparse choice/type.
        return AddRunResult(exit_code=2, error=str(e))

    run = Run(
        run_id=run_id,
        experiment_id=experiment.experiment_id,
        config=json.dumps(config_dict),
        status="pending",
    )

    run_repo.save(run, config_dict, commit=commit)
    randomization_seed_display = (
        str(config_dict.get('RANDOMIZATION_SEED'))
        if config_dict.get('RANDOMIZATION_SEED') is not None else "None"
    )
    return AddRunResult(exit_code=0, run_id=run.run_id, randomization_seed_display=randomization_seed_display)


def parse_add_run_request(argv: list[str]) -> AddRunRequest:
    """Pure: argv -> parse/normalize/validate -> AddRunRequest. No
    database connection is opened. Raises ParserExit(status) for any
    usage error, including an invalid --randomization-seed's FORMAT
    (int/AUTO/empty vs. garbage — knowable from the string alone,
    checked here even though ConfigResolver.build_run_config_dict,
    called later inside add_run_action, also validates it as part of
    actually resolving the value, which genuinely does need the
    experiment/connection for AUTO generation and experiment-config
    inheritance).

    Shared by run_add_run (standalone) and bcllm.py's composite flow,
    which calls this for every requested --add-* action BEFORE opening a
    database connection or acquiring the composite flow's transaction
    lock — see docs/status/composite-flow-unit-of-work-design.md point 3.
    """
    parser = create_parser()
    try:
        args = parse_args_normalized(
            parser, argv,
            supported=SYSTEM_DEFAULT_SUPPORTED,
            forbidden=SYSTEM_DEFAULT_FORBIDDEN,
        )
        if isinstance(args.randomization_seed, str):
            from src.core.config_resolver import parse_randomization_seed_strict
            parse_randomization_seed_strict(args.randomization_seed)
    except (argparse.ArgumentError, ValueError) as e:
        parser.error(str(e))  # raises ParserExit(2, ...)

    return AddRunRequest(
        experiment=args.experiment,
        randomization_seed=args.randomization_seed,
        system_prompt=args.system_prompt,
        user_prompt=args.user_prompt,
    )


def run_add_run(
    argv: list[str] | None = None, conn=None, *,
    commit: bool = True, request: AddRunRequest | None = None,
) -> int:
    """Single entry point for the --add-run action: parsing, system-
    default normalization/classification, request construction, dispatch
    to add_run_action, and result presentation (printing) — used
    identically by main() (standalone, real sys.argv) and bcllm.py's
    composite flow. Both go through this exact same code, so a fix here
    applies to both callers automatically — no divergent duplicate logic
    to keep in sync.

    Never lets argparse's own sys.exit() escape (create_parser() returns
    a NonExitingArgumentParser) — always returns an exit code.

    A usage error NEVER opens a database connection: when `conn` is not
    supplied, get_database_connection() is only called AFTER parsing
    succeeds, never before.

    Args:
        argv: Argument strings for THIS action only (no program name).
            Ignored if `request` is given directly.
        conn: An already-open connection to reuse — the composite flow
            passes its own, shared across multiple actions in one
            invocation, and this function does NOT close it. When None
            (standalone), this function opens (after a successful parse)
            and closes its own connection.
        commit: Passed straight to add_run_action — see its docstring.
        request: A pre-parsed AddRunRequest. When given, `argv` is
            ignored entirely and no parsing happens here — used by the
            composite flow, which pre-parses every requested action's
            argv (via parse_add_run_request) before ever opening a
            connection, then calls this function only for its DB-facing
            half (dispatch + printing), reusing this exact same code
            path rather than duplicating it.

    Returns:
        0 success, 1 operational/domain error, 2 usage error.
    """
    if request is None:
        try:
            request = parse_add_run_request(argv)
        except ParserExit as e:
            return e.status

    owns_conn = conn is None
    if owns_conn:
        conn = get_database_connection()
    try:
        result = add_run_action(request, conn, commit=commit)

        if result.exit_code == 0:
            print(f"✓ Run created for '{request.experiment}' (ID: {result.run_id}, Randomization Seed: {result.randomization_seed_display})")
            print(f"  System Prompt: {'Custom' if request.system_prompt else 'Inherited from experiment/.env'}")
            print(f"  User Prompt: {'Custom' if request.user_prompt else 'Inherited from experiment/.env'}")
        else:
            print(f"Error: {result.error}", file=sys.stderr)

        return result.exit_code
    finally:
        if owns_conn:
            conn.close()


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

    print(f"Runs in experiment: {experiment.name}")
    print(f"{'ID':<25} {'Randomization Seed':<20} {'Status':<18}")
    print("-" * 65)
    for r in runs:
        config = json.loads(r.config) if r.config else {}
        randomization_seed_display = (
            str(config.get('RANDOMIZATION_SEED'))
            if config.get('RANDOMIZATION_SEED') is not None else "None"
        )
        print(f"{r.run_id:<25} {randomization_seed_display:<20} {r.status:<18}")

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

    config = json.loads(run.config) if run.config else {}

    print(f"Run: {run.run_id}")
    print(f"  Experiment: {experiment.name}")
    print(f"  Config:")
    print(f"    randomization_seed: {config.get('RANDOMIZATION_SEED', 'None')}")
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
        Exit code (0 for success, 1 for error, 2 for usage error).
    """
    _validate_expected_mode(mode)
    argv = sys.argv[1:]

    # --add-run delegates to the exact same single-action pipeline the
    # composite flow uses (see run_add_run's docstring) — peeked via
    # has_flag before parsing, mirroring how bcllm.py's composite flow
    # already decides which action to run.
    if has_flag(argv, '--add-run'):
        return run_add_run(argv)

    # --list-runs / --run / --remove-run have no composite-flow
    # counterpart — parsed and dispatched directly, same shape as before,
    # just adapted to NonExitingArgumentParser.
    parser = create_parser()
    try:
        try:
            args = parse_args_normalized(
                parser, argv,
                supported=SYSTEM_DEFAULT_SUPPORTED,
                forbidden=SYSTEM_DEFAULT_FORBIDDEN,
            )
        except (argparse.ArgumentError, ValueError) as e:
            parser.error(str(e))
    except ParserExit as e:
        if e.status != 0:
            return e.status
        return 0  # --help or other clean parser exit

    conn = get_database_connection()

    try:
        if args.list_runs:
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
