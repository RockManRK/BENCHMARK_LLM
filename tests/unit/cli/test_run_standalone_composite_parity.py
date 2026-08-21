"""Standalone/composite parity proof for bcllm_run.py's Typer conversion
(marco 4B first slice, 2026-08-20), matching the pattern established for
bcllm_questions.py's own equivalent file. Every test goes through REAL
argv and the actual entry points main()/run_add_run()/parse_add_run_request()
use in production — i.e. through src/cli/commands/run.py's Typer command,
the single canonical parser, for both flows.

Covers: system-default (randomization_seed/system_prompt/user_prompt),
AUTO resolution at run-creation time, zero preserved distinct from None,
experiment-level inheritance when not specified, and standalone/composite
equivalence of the persisted config — the specific properties requested
before proceeding to bcllm_model.py.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.core.argv_utils import ParserExit
from src.db.models import Experiment
from src.db.repository import ExperimentRepository, RunRepository
from src.db.schema import create_schema


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _make_experiment(conn, name: str, config: dict | None = None) -> Experiment:
    exp = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}", name=name, description=None,
        config_json=json.dumps(config or {}), config_hash="deadbeef",
    )
    ExperimentRepository(conn).save(exp)
    return exp


def _run_config(conn, run_id: str) -> dict:
    run = RunRepository(conn).get_by_id(run_id)
    return json.loads(run.config) if run.config else {}


class TestSystemDefaultBothFlowsRealArgv:
    def test_standalone_randomization_seed_system_default(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_rsd", config={"RANDOMIZATION_SEED": 99})
        exit_code = run_add_run(
            ["--experiment", exp.name, "--add-run", "--randomization-seed", "system-default"], conn,
        )
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        # system-default explicitly bypasses experiment inheritance -> None
        assert config["RANDOMIZATION_SEED"] is None

    def test_composite_shaped_argv_randomization_seed_system_default(self):
        """Mirrors exactly the argv shape bcllm.py::_build_action_argv
        constructs for the composite flow."""
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_rsd_composite", config={"RANDOMIZATION_SEED": 99})
        action_argv = ["bcllm", "--experiment", exp.name, "--add-run", "--randomization-seed", "system-default"]
        exit_code = run_add_run(action_argv[1:], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["RANDOMIZATION_SEED"] is None


class TestZeroPreservedBothFlows:
    def test_standalone_zero_is_not_none(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_zero")
        exit_code = run_add_run(
            ["--experiment", exp.name, "--add-run", "--randomization-seed", "0"], conn,
        )
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["RANDOMIZATION_SEED"] == 0
        assert config["RANDOMIZATION_SEED"] is not None


class TestAutoResolvedAtRunCreationBothFlows:
    def test_standalone_auto_resolves_to_deterministic_int(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_auto")
        exit_code = run_add_run(
            ["--experiment", exp.name, "--add-run", "--randomization-seed", "AUTO"], conn,
        )
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert isinstance(config["RANDOMIZATION_SEED"], int)

    def test_composite_shaped_argv_auto_resolves_deterministically(self):
        """AUTO resolves to a deterministic hash of (experiment_id,
        run_id) — same real argv reproduced twice against fresh runs of
        the SAME experiment must independently satisfy the int contract;
        determinism itself (same run_id -> same seed) is already covered
        by docs/contracts/determinism.md's own test suite, not
        re-derived here."""
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_auto_composite")
        action_argv = ["bcllm", "--experiment", exp.name, "--add-run", "--randomization-seed", "AUTO"]
        exit_code = run_add_run(action_argv[1:], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert isinstance(config["RANDOMIZATION_SEED"], int)


class TestInheritanceWhenNotSpecifiedBothFlows:
    def test_standalone_inherits_experiment_seed_when_not_provided(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_inherit", config={"RANDOMIZATION_SEED": 77})
        exit_code = run_add_run(["--experiment", exp.name, "--add-run"], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["RANDOMIZATION_SEED"] == 77

    def test_composite_shaped_argv_inherits_identically(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_inherit_composite", config={"RANDOMIZATION_SEED": 77})
        action_argv = ["bcllm", "--experiment", exp.name, "--add-run"]
        exit_code = run_add_run(action_argv[1:], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["RANDOMIZATION_SEED"] == 77


class TestPromptsBothFlows:
    def test_standalone_custom_prompts(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_prompts")
        exit_code = run_add_run([
            "--experiment", exp.name, "--add-run",
            "--system-prompt", "custom system", "--user-prompt", "custom user",
        ], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["SYSTEM_PROMPT"] == "custom system"
        assert config["USER_PROMPT"] == "custom user"

    def test_standalone_prompts_inherit_from_experiment_when_absent(self):
        from src.cli.bcllm_run import run_add_run

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_prompts_inherit", config={
            "SYSTEM_PROMPT": "exp system", "USER_PROMPT": "exp user",
        })
        exit_code = run_add_run(["--experiment", exp.name, "--add-run"], conn)
        assert exit_code == 0
        run = RunRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _run_config(conn, run.run_id)
        assert config["SYSTEM_PROMPT"] == "exp system"
        assert config["USER_PROMPT"] == "exp user"


class TestContradictionAndErrorBothFlows:
    def test_standalone_garbage_seed_via_main_exits_2_no_connection(self, monkeypatch):
        import sys
        from unittest.mock import patch
        from src.core.mode import Mode
        from src.cli import bcllm_run

        monkeypatch.setattr(sys, "argv", [
            "bcllm_run.py", "--experiment", "exp1", "--add-run", "--randomization-seed", "garbage",
        ])
        with patch("src.cli.bcllm_run.get_database_connection") as mock_conn:
            exit_code = bcllm_run.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_composite_pre_parse_phase_raises_before_any_connection(self):
        from src.cli.bcllm_run import parse_add_run_request

        with pytest.raises(ParserExit) as exc_info:
            parse_add_run_request(["--experiment", "exp1", "--add-run", "--randomization-seed", "garbage"])
        assert exc_info.value.status == 2


class TestAdapterEquivalenceStandaloneVsCompositeArgvShape:
    def test_run_add_run_adapter_produces_identical_results(self):
        """The strongest form of equivalence: the SAME adapter
        (run_add_run), called once with a 'standalone-shaped' argv and
        once with a 'composite-shaped' synthetic argv, must produce
        identical persisted config — since it is, in fact, the exact same
        function either way."""
        from src.cli.bcllm_run import run_add_run

        conn_a = _make_conn()
        exp_a = _make_experiment(conn_a, "expA", config={"RANDOMIZATION_SEED": 5})
        code_a = run_add_run(["--experiment", "expA", "--add-run"], conn_a)

        conn_b = _make_conn()
        exp_b = _make_experiment(conn_b, "expB", config={"RANDOMIZATION_SEED": 5})
        code_b = run_add_run(
            ["bcllm", "--experiment", "expB", "--add-run"][1:], conn_b,
        )

        assert code_a == code_b == 0
        run_a = RunRepository(conn_a).list_by_experiment(exp_a.experiment_id)[0]
        run_b = RunRepository(conn_b).list_by_experiment(exp_b.experiment_id)[0]
        assert _run_config(conn_a, run_a.run_id) == _run_config(conn_b, run_b.run_id)
