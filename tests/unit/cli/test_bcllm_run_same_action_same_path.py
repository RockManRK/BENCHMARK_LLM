"""Regression tests for the "same action, same path" architecture fix
(docs/status/known-issues.md), covering the categories from the user's
point 7 for bcllm_run.py's --add-run:

- help returns 0 through main(), no unexpected termination, no DB connection
- no persistent connection/write before a usage error (FORBIDDEN
  --experiment/--run values, invalid --randomization-seed text)
- no system-default string ever persisted (--randomization-seed/
  --system-prompt 'system-default' must resolve to None in the stored
  config, never the literal string)
- equivalence between the standalone-shaped and composite-shaped argv,
  calling the exact same run_add_run() adapter both times
- invalid --randomization-seed specifically: exit 2, no connection opened

See tests/unit/cli/test_questions_system_default.py for the sibling
coverage of bcllm_questions.py and
tests/unit/cli/test_bcllm_model_same_action_same_path.py for bcllm_model.py.

Isolation: hermetic, in-memory SQLite. No real .env/production DB touched.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest

from src.core.mode import Mode
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.db.models import Experiment
from src.db.repository import ExperimentRepository, RunRepository
from src.db.schema import create_schema


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _make_experiment(conn, name: str) -> Experiment:
    exp = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        description=None,
        config_json=json.dumps({}),
        config_hash="deadbeef",
    )
    ExperimentRepository(conn).save(exp)
    return exp


# =============================================================================
# Help returns 0 without unexpected termination
# =============================================================================

class TestHelpReturnsZeroWithoutUnexpectedTermination:
    def test_help_returns_0_no_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_run

        monkeypatch.setattr(sys, "argv", ["bcllm_run.py", "--help"])

        with patch("src.cli.bcllm_run.get_database_connection") as mock_conn:
            exit_code = bcllm_run.main(Mode.MODIFY)
            assert exit_code == 0
            mock_conn.assert_not_called()


# =============================================================================
# No connection/write before a usage error
# =============================================================================

class TestNoWriteBeforeUsageError:
    def test_invalid_randomization_seed_text_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_run

        monkeypatch.setattr(sys, "argv", [
            "bcllm_run.py", "--experiment", "exp1", "--add-run", "--randomization-seed", "not-a-number",
        ])

        with patch("src.cli.bcllm_run.get_database_connection") as mock_conn:
            exit_code = bcllm_run.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_forbidden_experiment_system_default_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_run

        monkeypatch.setattr(sys, "argv", [
            "bcllm_run.py", "--experiment", "system-default", "--add-run",
        ])

        with patch("src.cli.bcllm_run.get_database_connection") as mock_conn:
            exit_code = bcllm_run.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()


# =============================================================================
# No system-default string ever persisted
# =============================================================================

class TestNoSystemDefaultStringPersisted:
    def test_randomization_seed_system_default_persists_as_none_not_literal_string(self):
        from src.cli.bcllm_run import add_run_action, AddRunRequest

        conn = _make_conn()
        _make_experiment(conn, "exp1")
        request = AddRunRequest(experiment="exp1", randomization_seed=FORCE_SYSTEM_DEFAULT)

        result = add_run_action(request, conn)

        assert result.exit_code == 0
        run = RunRepository(conn).get_by_id(result.run_id)
        config = json.loads(run.config)
        assert config["RANDOMIZATION_SEED"] is None
        assert "system-default" not in run.config

    def test_system_prompt_system_default_persists_as_none_not_literal_string(self):
        from src.cli.bcllm_run import add_run_action, AddRunRequest

        conn = _make_conn()
        _make_experiment(conn, "exp1")
        request = AddRunRequest(experiment="exp1", system_prompt=FORCE_SYSTEM_DEFAULT)

        result = add_run_action(request, conn)

        assert result.exit_code == 0
        run = RunRepository(conn).get_by_id(result.run_id)
        config = json.loads(run.config)
        assert config["SYSTEM_PROMPT"] is None
        assert "system-default" not in run.config


# =============================================================================
# Equivalence between standalone-shaped and composite-shaped argv
# =============================================================================

class TestStandaloneCompositeEquivalence:
    def test_run_add_run_adapter_equivalent_standalone_vs_composite_argv(self):
        """The strongest form of equivalence: the SAME adapter
        (run_add_run), called once with a 'standalone-shaped' argv and
        once with a 'composite-shaped' synthetic argv (mirroring exactly
        what bcllm.py's _execute_all_add_actions builds), must produce
        identical persisted config — since it is, in fact, the exact same
        function either way."""
        from src.cli.bcllm_run import run_add_run

        conn_a = _make_conn()
        _make_experiment(conn_a, "expA")
        code_a = run_add_run(
            ["--experiment", "expA", "--add-run", "--randomization-seed", "42"],
            conn_a,
        )

        conn_b = _make_conn()
        _make_experiment(conn_b, "expB")
        # Mirrors bcllm.py::_execute_all_add_actions's synthetic argv shape
        code_b = run_add_run(
            ["bcllm", "--experiment", "expB", "--add-run", "--randomization-seed", "42"][1:],
            conn_b,
        )

        assert code_a == code_b == 0

        runs_a = RunRepository(conn_a).list_by_experiment(
            ExperimentRepository(conn_a).get_by_name("expA").experiment_id
        )
        runs_b = RunRepository(conn_b).list_by_experiment(
            ExperimentRepository(conn_b).get_by_name("expB").experiment_id
        )
        assert len(runs_a) == len(runs_b) == 1
        assert json.loads(runs_a[0].config) == json.loads(runs_b[0].config) == {
            "RANDOMIZATION_SEED": 42, "SYSTEM_PROMPT": None, "USER_PROMPT": None,
        }

    def test_run_add_run_adapter_equivalent_on_invalid_randomization_seed_usage_error(self):
        """Same adapter, same rejection: an unparseable --seed is rejected
        identically (exit 2, no DB write) regardless of which shape of
        argv it's called with."""
        from src.cli.bcllm_run import run_add_run

        conn_a = _make_conn()
        _make_experiment(conn_a, "expA")
        code_a = run_add_run(
            ["--experiment", "expA", "--add-run", "--randomization-seed", "garbage"],
            conn_a,
        )

        conn_b = _make_conn()
        _make_experiment(conn_b, "expB")
        code_b = run_add_run(
            ["bcllm", "--experiment", "expB", "--add-run", "--randomization-seed", "garbage"][1:],
            conn_b,
        )

        assert code_a == code_b == 2
        assert RunRepository(conn_a).list_by_experiment(
            ExperimentRepository(conn_a).get_by_name("expA").experiment_id
        ) == []
        assert RunRepository(conn_b).list_by_experiment(
            ExperimentRepository(conn_b).get_by_name("expB").experiment_id
        ) == []
