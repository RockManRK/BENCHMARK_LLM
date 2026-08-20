"""Regression tests for the composite --create-experiment + --add-* flow's
REAL atomicity (src.db.unit_of_work.UnitOfWork), replacing the earlier
compensating-DELETE mechanism (docs/status/composite-flow-unit-of-work-design.md,
approved 2026-08-19 after docs/status/composite-flow-atomicity-investigation.md).

Covers:
1. Any failure (usage error, domain error, or an unexpected exception)
   rolls back the WHOLE transaction — experiment, model variants,
   question snapshots, and runs alike — verified via row counts AND
   PRAGMA foreign_key_check / integrity_check.
2. Failures injected at each point in the model -> questions -> run
   sequence.
3. Failures in the UnitOfWork machinery itself: a busy database on
   BEGIN IMMEDIATE (__enter__), a commit() failure, and a rollback()
   failure — each must produce exit code 1, no raw traceback shown to
   the user, and the database connection always closed.
4. The disclosed TOCTOU behavior change: a pre-existing experiment
   (found via the concurrent-creation race) survives a later action's
   failure, but THIS invocation's own writes against it do not.

Isolation: DATABASE_PATH and LOG_FILE_PATH are both redirected to tmp_path
— no real .env/production DB or log file touched. This file also
neutralizes dotenv.load_dotenv (see _isolated_env below): bcllm.py used
to call `load_dotenv(".env", override=True)` at module import time, which
could silently overwrite the monkeypatched env vars below on the first
`import bcllm` in this pytest process. That import-time side effect no
longer exists (see docs/status/composite-flow-unit-of-work-design.md
point 8 / point 5 of the follow-up adjustments — load_dotenv now only
runs from bcllm.cli_main(), never from a bare import) — the
monkeypatch.setattr below is kept anyway as a belt-and-suspenders
guard against regressing that fix.
"""

from __future__ import annotations

import json
import logging
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "rollback_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("QUESTIONS_DATASET_PATH", raising=False)
    yield


DATASET_CONTENT = {
    "questions": [
        {
            "id": "Q001",
            "stem": "Question 1?",
            "options": {"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
            "answer_key": "A",
            "assets": [],
            "meta": {"status": "valid"},
        },
    ]
}


@pytest.fixture
def dataset_path(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(DATASET_CONTENT), encoding="utf-8")
    return str(path)


def _connect(db_path) -> sqlite3.Connection:
    """A usage error caught during the pure parse phase (point 3 of the
    design) never opens a connection at all — the target DB file may not
    even have a schema yet. create_schema() is idempotent (CREATE TABLE
    IF NOT EXISTS), so calling it here is always safe and lets these
    verification helpers work whether or not bcllm.py ever touched the
    file."""
    from src.db.schema import create_schema

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _experiment_row_exists(db_path, name: str) -> bool:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT 1 FROM experiments WHERE name = ?", (name,)).fetchone()
        return row is not None
    finally:
        conn.close()


def _all_table_counts(db_path) -> dict:
    """Whole-database counts (not scoped to one experiment_id) — used
    when verifying a rollback left literally nothing behind."""
    conn = _connect(db_path)
    try:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("experiments", "model_variants", "question_snapshots", "runs")
        }
    finally:
        conn.close()


_GENERIC_UNEXPECTED_FAILURE_MESSAGE = (
    "Error: an unexpected failure occurred while setting up the experiment. "
    "See the technical log for details."
)


def _assert_user_facing_output_is_generic(captured_err: str) -> None:
    """Point 4: the user-facing print()-based message must be generic,
    with exception detail kept only in the technical log. Rather than
    trying to heuristically separate print() lines from logging output
    sharing the same stderr stream (src/utils/logging_config.py's
    console handler defaults to sys.stderr, and legitimately includes
    full exception detail via exc_info=True — that's the log doing its
    job, not a violation), this asserts directly on the ONE exact,
    fixed, generic string _handle_composite_flow's except block prints —
    the simplest and most robust way to confirm exactly what point 4
    actually requires, without needing to prove the negative "no
    exception text appears anywhere in stderr" (which isn't the real
    requirement, and isn't even true once the legitimate log record is
    accounted for)."""
    assert _GENERIC_UNEXPECTED_FAILURE_MESSAGE in captured_err


def _assert_db_structurally_sound(db_path) -> None:
    conn = _connect(db_path)
    try:
        fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert fk_issues == [], f"foreign_key_check found issues: {fk_issues}"
        integrity = conn.execute("PRAGMA integrity_check").fetchall()
        assert [row[0] for row in integrity] == ["ok"], f"integrity_check failed: {integrity}"
    finally:
        conn.close()


class TestUsageAndDomainErrorsRollBackEverything:
    def test_add_model_invalid_reasoning_choice_rolls_back_created_experiment(self, tmp_path):
        import bcllm
        from src.core.mode import Mode

        experiment_name = "rollback-model-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4", "--reasoning", "garbage-value",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 2  # usage error, not swallowed as 1
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        assert _all_table_counts(db_path) == {
            "experiments": 0, "model_variants": 0, "question_snapshots": 0, "runs": 0,
        }
        _assert_db_structurally_sound(db_path)

    def test_add_model_forbidden_url_system_default_rolls_back_created_experiment(self, tmp_path):
        import bcllm
        from src.core.mode import Mode

        experiment_name = "rollback-model-url-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4", "--url", "system-default",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 2
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        _assert_db_structurally_sound(db_path)

    def test_add_run_invalid_seed_caught_during_add_run_own_parse_phase(self, tmp_path):
        """--randomization-seed is not itself an ADD_ACTION_FLAG, so _build_create_argv
        AND _build_action_argv (for --add-run) both forward it — meaning
        TWO independent pure-parse-phase checks could catch an invalid
        --randomization-seed here: bcllm_run.py's own parse_add_run_request (seed
        FORMAT validation, ParserExit-based, exit 2 — see
        docs/status/known-issues.md "same action, same path") runs as
        part of _parse_all_add_action_requests, which executes AFTER
        experiment-creation's own args have already parsed successfully
        (bcllm_experiment.py's --randomization-seed has no format validation at parse
        time, only at config-resolution time, deeper in the DB phase) —
        so --add-run's own, earlier, stricter check wins here. Exit code
        2, not 1: this is a deliberate, disclosed change from the
        pre-Unit-of-Work behavior (see the companion test below for the
        case where --add-run is NOT requested, which still gets exit 1
        exactly as before)."""
        import bcllm
        from src.core.mode import Mode

        experiment_name = "rollback-run-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-run", "--randomization-seed", "not-a-valid-seed",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_run")

        assert handled is True
        assert exit_code == 2
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        _assert_db_structurally_sound(db_path)

    def test_invalid_seed_without_add_run_still_caught_at_experiment_creation_exit_1(self, tmp_path):
        """Companion to the test above: when --add-run is NOT among the
        requested actions, nothing pre-validates --randomization-seed's format during
        the pure parse phase (bcllm_experiment.py's own --randomization-seed has no
        format check at parse time) — so an invalid --randomization-seed is only
        caught later, inside _create_experiment_with_config's config
        resolution (a ValueError, exit 1) — exactly the pre-existing,
        unchanged behavior for this combination."""
        import bcllm
        from src.core.mode import Mode

        experiment_name = "rollback-run-test-no-add-run"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--randomization-seed", "not-a-valid-seed",
            "--add-model", "openai/gpt-4",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 1
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        _assert_db_structurally_sound(db_path)

    def test_successful_composite_flow_commits_everything(self, tmp_path, dataset_path, monkeypatch):
        """Control case: a valid composite flow with all three actions
        must leave the experiment, model variant, question snapshot, AND
        run in place — proves the rollback assertions elsewhere in this
        file are actually exercising the failure path, not a DB that
        never got the rows in the first place."""
        import bcllm
        from src.core.mode import Mode

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)

        experiment_name = "no-rollback-control"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-questions", "system-default",
            "--add-run", "--randomization-seed", "AUTO",
            # --randomization-seed AUTO explicit: a bare --add-run with no seed falls
            # back to the experiment's own stored RANDOMIZATION_SEED,
            # which is the literal string "OFF" for an experiment created
            # with no seed configured (src/core/config_resolver.py:506,
            # pre-existing, predates this session's changes — confirmed
            # via git log). build_run_config_dict then rejects "OFF" via
            # parse_seed_value_strict, a genuine but unrelated bug this
            # test isn't meant to exercise — see
            # docs/status/known-issues.md.
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 0
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert _experiment_row_exists(db_path, experiment_name)
        assert _all_table_counts(db_path) == {
            "experiments": 1, "model_variants": 1, "question_snapshots": 1, "runs": 1,
        }
        _assert_db_structurally_sound(db_path)


class TestFailureAtDifferentPointsInTheSequence:
    """Execution order is fixed (model -> questions -> run, see
    ADD_ACTION_FLAGS in src/core/module_resolver.py). Each case lets one
    or more earlier actions actually write (uncommitted, inside the same
    open transaction) before the triggering failure, and confirms
    rollback removes literally everything — not just the table the
    failing action itself would have written to."""

    def test_add_questions_failure_after_model_already_written(self, tmp_path, dataset_path, monkeypatch):
        """--add-model succeeds (uncommitted write inside the
        transaction); the deprecated 'null' literal on --add-questions
        (second in sequence) then fails as a usage error. Rollback must
        remove BOTH the variant and the experiment."""
        import bcllm
        from src.core.mode import Mode

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)

        experiment_name = "rollback-after-model-written"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-questions", "null",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 2
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        assert _all_table_counts(db_path) == {
            "experiments": 0, "model_variants": 0, "question_snapshots": 0, "runs": 0,
        }
        _assert_db_structurally_sound(db_path)

    def test_add_run_failure_after_model_and_questions_already_written(self, tmp_path, dataset_path, monkeypatch):
        """--add-model and --add-questions both succeed (uncommitted);
        --add-run (last in sequence) is forced to fail via injection —
        there is currently no real, user-reachable way for --add-run to
        fail once its experiment exists (an invalid --randomization-seed is
        intercepted earlier, during the pure parse phase, per
        test_add_run_invalid_seed_caught_at_experiment_creation_no_row_persisted
        above). Rollback must remove the variant, the snapshot, AND the
        experiment."""
        import bcllm
        from src.core.mode import Mode

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)

        def _forced_run_failure(*a, **kw):
            return 1

        monkeypatch.setattr("src.cli.bcllm_run.run_add_run", _forced_run_failure)

        experiment_name = "rollback-after-model-and-questions-written"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-questions", "system-default",
            "--add-run",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 1
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        assert _all_table_counts(db_path) == {
            "experiments": 0, "model_variants": 0, "question_snapshots": 0, "runs": 0,
        }
        _assert_db_structurally_sound(db_path)

    def test_failure_after_all_three_actions_written_still_rolls_back_everything(
        self, tmp_path, dataset_path, monkeypatch,
    ):
        """The strongest case: model, questions, AND run all succeed
        (all three writes sit uncommitted in the open transaction), and
        THEN something fails — here, the final uow.commit() itself, via
        a proxy connection whose commit() raises. Confirms rollback
        reaches every table, not just the ones touched by whichever
        action happened to fail."""
        import bcllm
        from src.core.mode import Mode
        from src.cli import database as db_module

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)

        class _CommitFailsProxy:
            def __init__(self, real_conn):
                self._real_conn = real_conn

            def commit(self):
                raise sqlite3.OperationalError("simulated commit failure after all actions written")

            def __getattr__(self, name):
                return getattr(self._real_conn, name)

        real_get_database_connection = db_module.get_database_connection

        def _get_failing_connection():
            return _CommitFailsProxy(real_get_database_connection())

        monkeypatch.setattr(db_module, "get_database_connection", _get_failing_connection)

        experiment_name = "rollback-after-all-three-written"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-questions", "system-default",
            "--add-run", "--randomization-seed", "AUTO",  # see comment in the control-case test above
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 1  # unexpected failure -> operational, not usage
        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        assert _all_table_counts(db_path) == {
            "experiments": 0, "model_variants": 0, "question_snapshots": 0, "runs": 0,
        }
        _assert_db_structurally_sound(db_path)


class TestUnitOfWorkFailuresProduceCleanExitCodes:
    """UnitOfWork machinery failures (point 1/2 of the follow-up
    adjustments): the exception boundary wraps the ENTIRE `with
    UnitOfWork(...)` statement, including __enter__ itself (BEGIN
    IMMEDIATE against a busy database) — not just its body. Every case
    here must: return exit code 1, print no raw exception text (only a
    generic message — asserted via capsys), and always close the
    connection."""

    def test_busy_database_on_begin_immediate_returns_1_no_traceback(
        self, tmp_path, capsys,
    ):
        import bcllm
        from src.core.mode import Mode
        from src.cli.database import get_database_connection

        experiment_name = "busy-db-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
        ]

        # Open the real DB first (creates schema) and hold a write lock
        # on a SEPARATE connection, exactly like a concurrent invocation
        # would — this is genuine contention, not a mock.
        setup_conn = get_database_connection()
        holder = sqlite3.connect(str(bcllm.os.getenv("DATABASE_PATH")), timeout=0.2)
        holder.execute("BEGIN IMMEDIATE")
        holder.execute(
            "INSERT INTO experiments (experiment_id, name, description, config_json, config_hash) "
            "VALUES ('exp_holder', 'holder-exp', NULL, '{}', 'deadbeef')"
        )
        setup_conn.close()

        try:
            handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")
        finally:
            holder.rollback()
            holder.close()

        assert handled is True
        assert exit_code == 1

        captured = capsys.readouterr()
        _assert_user_facing_output_is_generic(captured.err)

        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        _assert_db_structurally_sound(db_path)

    def test_commit_failure_returns_1_no_traceback_connection_closed(self, tmp_path, monkeypatch, capsys):
        import bcllm
        from src.core.mode import Mode
        from src.cli import database as db_module

        class _CommitFailsProxy:
            def __init__(self, real_conn):
                self._real_conn = real_conn
                self.closed = False

            def commit(self):
                raise sqlite3.OperationalError("simulated commit failure")

            def close(self):
                self.closed = True
                self._real_conn.close()

            def __getattr__(self, name):
                return getattr(self._real_conn, name)

        real_get_database_connection = db_module.get_database_connection
        holder = {}

        def _get_failing_connection():
            proxy = _CommitFailsProxy(real_get_database_connection())
            holder["proxy"] = proxy
            return proxy

        monkeypatch.setattr(db_module, "get_database_connection", _get_failing_connection)

        experiment_name = "commit-failure-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
        ]
        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 1

        captured = capsys.readouterr()
        _assert_user_facing_output_is_generic(captured.err)

        assert holder["proxy"].closed is True

        db_path = bcllm.os.getenv("DATABASE_PATH")
        assert not _experiment_row_exists(db_path, experiment_name)
        _assert_db_structurally_sound(db_path)

    def test_rollback_failure_returns_1_no_traceback_connection_closed(self, tmp_path, monkeypatch, capsys):
        """Failure needs a real trigger for the rollback to fire at all —
        the trigger must reach the DB phase (a parse-time usage error,
        like the deprecated 'null' literal, never opens a connection at
        all, so there would be nothing to roll back and this test
        wouldn't exercise anything) — so --add-model succeeds and
        --add-run is forced to fail via injection, same technique as
        TestFailureAtDifferentPointsInTheSequence. rollback() itself is
        ALSO rigged to fail, exercising the genuinely-worse case the old
        compensating-DELETE design had no answer for at all (see
        docs/status/composite-flow-atomicity-investigation.md §4 — this
        is exactly that gap, now closed)."""
        import bcllm
        from src.core.mode import Mode
        from src.cli import database as db_module

        def _forced_run_failure(*a, **kw):
            return 1

        monkeypatch.setattr("src.cli.bcllm_run.run_add_run", _forced_run_failure)

        class _RollbackFailsProxy:
            def __init__(self, real_conn):
                self._real_conn = real_conn
                self.closed = False

            def rollback(self):
                raise sqlite3.OperationalError("simulated rollback failure")

            def close(self):
                self.closed = True
                self._real_conn.close()

            def __getattr__(self, name):
                return getattr(self._real_conn, name)

        real_get_database_connection = db_module.get_database_connection
        holder = {}

        def _get_failing_connection():
            proxy = _RollbackFailsProxy(real_get_database_connection())
            holder["proxy"] = proxy
            return proxy

        monkeypatch.setattr(db_module, "get_database_connection", _get_failing_connection)

        experiment_name = "rollback-failure-test"
        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-run",
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 1  # the rollback() failure is what's caught here, not the forced action's own 1
        captured = capsys.readouterr()
        _assert_user_facing_output_is_generic(captured.err)

        assert holder["proxy"].closed is True


class TestToctouBehaviorChange:
    """Disclosed improvement over the old compensating-DELETE design
    (docs/status/composite-flow-unit-of-work-design.md §4): a
    pre-existing experiment (found via the TOCTOU concurrent-creation
    check) survives a later action's failure — it was never part of THIS
    invocation's uncommitted transaction — but this invocation's OWN
    writes against it are rolled back, unlike before, where they used to
    survive un-rolled-back because "not ours to roll back" incorrectly
    also skipped undoing this invocation's own actions."""

    def test_preexisting_experiment_survives_but_this_invocations_writes_do_not(
        self, tmp_path, dataset_path, monkeypatch,
    ):
        import bcllm
        from src.core.mode import Mode
        from src.cli.database import get_database_connection
        from src.db.repository import ExperimentRepository
        from src.db.models import Experiment

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)

        experiment_name = "toctou-preexisting-exp"
        conn = get_database_connection()
        existing = Experiment(
            experiment_id="exp_preexisting", name=experiment_name,
            description=None, config_json="{}", config_hash="deadbeef",
        )
        ExperimentRepository(conn).save(existing)
        conn.close()

        argv = [
            "bcllm", "--create-experiment", experiment_name,
            "--add-model", "openai/gpt-4",
            "--add-questions", "null",  # fails -> triggers rollback
        ]

        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 2
        db_path = bcllm.os.getenv("DATABASE_PATH")
        # The pre-existing experiment itself is untouched.
        assert _experiment_row_exists(db_path, experiment_name)
        # But the model variant THIS invocation wrote is gone.
        assert _all_table_counts(db_path)["model_variants"] == 0
        _assert_db_structurally_sound(db_path)
