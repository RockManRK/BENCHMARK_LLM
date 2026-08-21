"""Tests for --remove-experiment (disabled) and --remove-run (soft delete
via status='removed').

Context: --remove-experiment was completely unreachable before this
session (Mode.INVALID routing gap — see test_mode_matrix.py's
TestModeInvalidIsValidForHelpListReview). Fixing that routing gap made it
reachable for the first time and exposed that its implementation
(ExperimentRepository.delete(), a hard cascading delete per
src/db/schema.py's ON DELETE CASCADE) conflicts with
docs/contracts/immutability.md ("Question Snapshots ... Cannot be
deleted") and docs/contracts/configuration-hierarchy.md ("Model variant
configuration is frozen at creation"). Disabled rather than shipped,
pending a product decision — see docs/status/known-issues.md.

--remove-run had the same class of problem (hard delete of a frozen Run.
config) and is fixed here: it now sets status='removed' instead, reusing
the mutable-exception the immutability contract already grants Run.status
("Execution lifecycle tracking"), rather than deleting the row.

Self-contained (sqlite3(':memory:') + create_schema() + direct repository
calls, valid current Experiment/Run dataclass fields) rather than reusing
tests/unit/cli/test_bcllm_experiment.py's / test_bcllm_run.py's shared
fixtures, which fail before reaching any assertion for an unrelated,
pre-existing reason (Experiment(system_prompt=...) — a stale kwarg no
longer on the dataclass).
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from src.db.models import Experiment, ModelVariant, Run
from src.db.repository import ExperimentRepository, RunRepository, VariantRepository
from src.db.schema import create_schema


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    create_schema(c)
    return c


def _make_experiment(conn, name: str = "exp1") -> Experiment:
    exp = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description=None,
        config_json=json.dumps({}),
        config_hash="deadbeef",
    )
    ExperimentRepository(conn).save(exp)
    return exp


def _make_run(conn, experiment_id: str) -> Run:
    run = Run(
        run_id=f"run_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment_id,
        config=json.dumps({"RANDOMIZATION_SEED": None}),
        status="pending",
        duration=0,
    )
    RunRepository(conn).save(run, {"RANDOMIZATION_SEED": None})
    return run


class _Args:
    """Minimal stand-in for argparse.Namespace with just the attributes
    each handler reads."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestRemoveExperimentDisabled:
    def test_returns_exit_code_1(self, conn):
        from src.cli.bcllm_experiment import handle_remove_experiment

        exp = _make_experiment(conn)
        exit_code = handle_remove_experiment(_Args(remove_experiment=exp.name), conn)

        assert exit_code == 1

    def test_does_not_touch_the_database(self, conn):
        from src.cli.bcllm_experiment import handle_remove_experiment

        exp = _make_experiment(conn)
        handle_remove_experiment(_Args(remove_experiment=exp.name), conn)

        row = conn.execute(
            "SELECT COUNT(*) c FROM experiments WHERE experiment_id = ?", (exp.experiment_id,)
        ).fetchone()
        assert row["c"] == 1

    def test_never_queries_the_repository(self, conn, monkeypatch):
        """Guards against a future edit reintroducing the lookup-then-delete
        pattern: the whole point is 1 always, with zero DB access."""
        from src.cli.bcllm_experiment import handle_remove_experiment

        def _boom(*a, **kw):
            raise AssertionError("handle_remove_experiment must not touch the database at all")

        monkeypatch.setattr(ExperimentRepository, "get_by_name", _boom)
        monkeypatch.setattr(ExperimentRepository, "delete", _boom)

        exit_code = handle_remove_experiment(_Args(remove_experiment="anything"), conn)
        assert exit_code == 1


class TestRemoveRunSoftDelete:
    def test_sets_status_removed(self, conn):
        from src.cli.bcllm_run import handle_remove_run

        exp = _make_experiment(conn)
        run = _make_run(conn, exp.experiment_id)

        exit_code = handle_remove_run(exp.name, run.run_id, conn)

        assert exit_code == 0
        row = conn.execute("SELECT status FROM runs WHERE run_id = ?", (run.run_id,)).fetchone()
        assert row["status"] == "removed"

    def test_row_and_config_survive(self, conn):
        """The point of a soft delete: the frozen config stays legible,
        not just the row's existence."""
        from src.cli.bcllm_run import handle_remove_run

        exp = _make_experiment(conn)
        run = _make_run(conn, exp.experiment_id)

        handle_remove_run(exp.name, run.run_id, conn)

        row = conn.execute("SELECT config FROM runs WHERE run_id = ?", (run.run_id,)).fetchone()
        assert row is not None
        assert json.loads(row["config"]) == {"RANDOMIZATION_SEED": None}

    def test_removed_run_excluded_from_executable_runs(self, conn):
        """Planner._get_runs() only selects status IN ('pending', 'failed',
        'partial_failed') — 'removed' must never appear in that set."""
        from src.cli.bcllm_run import handle_remove_run
        from src.core.planner import Planner

        exp = _make_experiment(conn)
        run = _make_run(conn, exp.experiment_id)
        handle_remove_run(exp.name, run.run_id, conn)

        planner = Planner(db_connection=conn)
        remaining = planner._get_runs(exp.experiment_id)
        assert run.run_id not in [r["run_id"] for r in remaining]

    def test_removed_run_excluded_even_when_explicitly_targeted_by_id(self, conn):
        """Regression for a real bug caught by essence-guardian review,
        2026-08-17: `bcllm --execute --run <id>` passes run_ids=[id]
        straight into Planner._get_runs(), whose run_ids-not-None branch
        previously had NO status filter at all — so explicitly targeting
        a removed run's ID would include it in the plan, execute it, and
        let RunFinalizer silently overwrite status='removed' with a
        computed outcome, reactivating a run the user had just removed.
        This is the case the earlier, single-path
        test_removed_run_excluded_from_executable_runs (default run_ids=None)
        did not cover — that's exactly how the bug slipped through."""
        from src.cli.bcllm_run import handle_remove_run
        from src.core.planner import Planner

        exp = _make_experiment(conn)
        run = _make_run(conn, exp.experiment_id)
        handle_remove_run(exp.name, run.run_id, conn)

        planner = Planner(db_connection=conn)
        remaining = planner._get_runs(exp.experiment_id, run_ids=[run.run_id])
        assert remaining == [], (
            "explicitly requesting a removed run's id must still exclude it, "
            "not just the default (no-run_ids) listing path"
        )

    def test_run_not_found_still_errors(self, conn):
        from src.cli.bcllm_run import handle_remove_run

        exp = _make_experiment(conn)
        exit_code = handle_remove_run(exp.name, "run_doesnotexist", conn)
        assert exit_code == 1

    def test_status_check_constraint_accepts_removed(self, conn):
        """Directly pins the schema.py CHECK constraint change — a
        constraint typo would make this raise IntegrityError instead."""
        exp = _make_experiment(conn)
        run = _make_run(conn, exp.experiment_id)

        conn.execute("UPDATE runs SET status = 'removed' WHERE run_id = ?", (run.run_id,))
        conn.commit()  # would raise sqlite3.IntegrityError if the CHECK rejected it
