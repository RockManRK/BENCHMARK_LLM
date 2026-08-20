"""Regression tests for the "same action, same path" architecture fix
(docs/status/known-issues.md), covering the categories from the user's
point 7 that test_bcllm_model_system_default.py does not already exercise
for bcllm_model.py's --add-model:

- help returns 0 through main(), no unexpected termination, no DB connection
- no persistent connection/write before a usage error (FORBIDDEN --url,
  invalid --reasoning choice)
- no system-default string ever persisted (--vision/--reasoning
  'system-default' must resolve to None in the stored config, never the
  literal string)
- equivalence between the standalone-shaped and composite-shaped argv,
  calling the exact same run_add_model() adapter both times

See tests/unit/cli/test_questions_system_default.py for the sibling
coverage of bcllm_questions.py and tests/unit/cli/test_bcllm_run_same_action_same_path.py
for bcllm_run.py.

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
from src.db.repository import ExperimentRepository, VariantRepository
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
        from src.cli import bcllm_model

        monkeypatch.setattr(sys, "argv", ["bcllm_model.py", "--help"])

        with patch("src.cli.bcllm_model.get_database_connection") as mock_conn:
            exit_code = bcllm_model.main(Mode.MODIFY)
            assert exit_code == 0
            mock_conn.assert_not_called()


# =============================================================================
# No connection/write before a usage error
# =============================================================================

class TestNoWriteBeforeUsageError:
    def test_forbidden_url_system_default_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_model

        monkeypatch.setattr(sys, "argv", [
            "bcllm_model.py", "--experiment", "exp1",
            "--add-model", "openai/gpt-4", "--url", "system-default",
        ])

        with patch("src.cli.bcllm_model.get_database_connection") as mock_conn:
            exit_code = bcllm_model.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_invalid_reasoning_choice_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_model

        monkeypatch.setattr(sys, "argv", [
            "bcllm_model.py", "--experiment", "exp1",
            "--add-model", "openai/gpt-4", "--reasoning", "garbage-value",
        ])

        with patch("src.cli.bcllm_model.get_database_connection") as mock_conn:
            exit_code = bcllm_model.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_forbidden_experiment_system_default_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_model

        monkeypatch.setattr(sys, "argv", [
            "bcllm_model.py", "--experiment", "system-default", "--add-model", "openai/gpt-4",
        ])

        with patch("src.cli.bcllm_model.get_database_connection") as mock_conn:
            exit_code = bcllm_model.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()


# =============================================================================
# No system-default string ever persisted
# =============================================================================

class TestNoSystemDefaultStringPersisted:
    def test_vision_system_default_persists_as_none_not_literal_string(self):
        from src.cli.bcllm_model import add_model_action, AddModelRequest

        conn = _make_conn()
        _make_experiment(conn, "exp1")
        request = AddModelRequest(experiment="exp1", add_model="openai/gpt-4", vision=FORCE_SYSTEM_DEFAULT)

        result = add_model_action(request, conn)

        assert result.exit_code == 0
        variant = VariantRepository(conn).get_by_id(result.variant_id)
        config = json.loads(variant.config)
        assert config["MODEL_VISION"] is None
        assert "system-default" not in variant.config

    def test_reasoning_system_default_persists_as_none_not_literal_string(self):
        from src.cli.bcllm_model import add_model_action, AddModelRequest

        conn = _make_conn()
        _make_experiment(conn, "exp1")
        request = AddModelRequest(experiment="exp1", add_model="openai/gpt-4", reasoning=FORCE_SYSTEM_DEFAULT)

        result = add_model_action(request, conn)

        assert result.exit_code == 0
        variant = VariantRepository(conn).get_by_id(result.variant_id)
        config = json.loads(variant.config)
        assert config["MODEL_REASONING_EFFORT"] is None
        assert "system-default" not in variant.config

    def test_provider_system_default_persists_as_none_not_literal_string(self):
        from src.cli.bcllm_model import add_model_action, AddModelRequest

        conn = _make_conn()
        _make_experiment(conn, "exp1")
        request = AddModelRequest(experiment="exp1", add_model="openai/gpt-4", provider=FORCE_SYSTEM_DEFAULT)

        result = add_model_action(request, conn)

        assert result.exit_code == 0
        variant = VariantRepository(conn).get_by_id(result.variant_id)
        config = json.loads(variant.config)
        assert config["PROVIDER"] is None
        assert "system-default" not in variant.config


# =============================================================================
# Equivalence between standalone-shaped and composite-shaped argv
# =============================================================================

class TestStandaloneCompositeEquivalence:
    def test_run_add_model_adapter_equivalent_standalone_vs_composite_argv(self):
        """The strongest form of equivalence: the SAME adapter
        (run_add_model), called once with a 'standalone-shaped' argv and
        once with a 'composite-shaped' synthetic argv (mirroring exactly
        what bcllm.py's _execute_all_add_actions builds), must produce
        identical persisted config — since it is, in fact, the exact same
        function either way."""
        from src.cli.bcllm_model import run_add_model

        conn_a = _make_conn()
        _make_experiment(conn_a, "expA")
        code_a = run_add_model(
            ["--experiment", "expA", "--add-model", "openai/gpt-4", "--reasoning", "high"],
            conn_a,
        )

        conn_b = _make_conn()
        _make_experiment(conn_b, "expB")
        # Mirrors bcllm.py::_execute_all_add_actions's synthetic argv shape
        code_b = run_add_model(
            ["bcllm", "--experiment", "expB", "--add-model", "openai/gpt-4", "--reasoning", "high"][1:],
            conn_b,
        )

        assert code_a == code_b == 0

        variants_a = VariantRepository(conn_a).list_by_experiment(
            ExperimentRepository(conn_a).get_by_name("expA").experiment_id
        )
        variants_b = VariantRepository(conn_b).list_by_experiment(
            ExperimentRepository(conn_b).get_by_name("expB").experiment_id
        )
        assert len(variants_a) == len(variants_b) == 1
        assert json.loads(variants_a[0].config) == json.loads(variants_b[0].config)

    def test_run_add_model_adapter_equivalent_on_forbidden_usage_error(self):
        """Same adapter, same rejection: a FORBIDDEN system-default on
        --url is rejected identically (exit 2, no DB write) regardless of
        which shape of argv it's called with."""
        from src.cli.bcllm_model import run_add_model

        conn_a = _make_conn()
        _make_experiment(conn_a, "expA")
        code_a = run_add_model(
            ["--experiment", "expA", "--add-model", "openai/gpt-4", "--url", "system-default"],
            conn_a,
        )

        conn_b = _make_conn()
        _make_experiment(conn_b, "expB")
        code_b = run_add_model(
            ["bcllm", "--experiment", "expB", "--add-model", "openai/gpt-4", "--url", "system-default"][1:],
            conn_b,
        )

        assert code_a == code_b == 2
        assert VariantRepository(conn_a).list_by_experiment(
            ExperimentRepository(conn_a).get_by_name("expA").experiment_id
        ) == []
        assert VariantRepository(conn_b).list_by_experiment(
            ExperimentRepository(conn_b).get_by_name("expB").experiment_id
        ) == []
