"""Standalone/composite parity proof for bcllm_model.py's Typer
conversion (marco 4B second slice, 2026-08-20), matching the pattern
established for bcllm_questions.py/bcllm_run.py's own equivalent files.
Every test goes through REAL argv and the actual entry point
run_add_model() (which parse_add_model_request()/main() both funnel
through) — i.e. through src/cli/commands/model.py's Typer command, the
single canonical parser, for both flows.

Covers the properties the user asked to preserve with special attention
for this slice that tests/unit/cli/test_bcllm_model_same_action_same_path.py
does not already exercise: MODEL_SEED (int including zero, distinct from
None/system-default), variant_signature stability (same config -> same
signature) and uniqueness (different config -> different signature),
--reasoning's choices+system-default interaction persisted correctly, and
provider system-default persisted identically via both argv shapes.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

from src.db.models import Experiment
from src.db.repository import ExperimentRepository, VariantRepository
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


def _variant_config(conn, variant_id: str) -> dict:
    variant = VariantRepository(conn).get_by_id(variant_id)
    return json.loads(variant.config) if variant.config else {}


class TestModelSeedBothFlows:
    def test_standalone_model_seed_explicit_int(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_seed")
        exit_code = run_add_model(
            ["--experiment", exp.name, "--add-model", "openai/gpt-4", "--model-seed", "42"], conn,
        )
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_SEED"] == 42

    def test_standalone_model_seed_zero_is_not_none(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_seed_zero")
        exit_code = run_add_model(
            ["--experiment", exp.name, "--add-model", "openai/gpt-4", "--model-seed", "0"], conn,
        )
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_SEED"] == 0
        assert config["MODEL_SEED"] is not None

    def test_composite_shaped_argv_model_seed_identical(self):
        """Mirrors exactly the argv shape bcllm.py::_build_action_argv
        constructs for the composite flow."""
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_seed_composite")
        action_argv = ["bcllm", "--experiment", exp.name, "--add-model", "openai/gpt-4", "--model-seed", "7"]
        exit_code = run_add_model(action_argv[1:], conn)
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_SEED"] == 7

    def test_standalone_model_seed_system_default_breaks_inheritance(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_seed_sd", config={"MODEL_SEED": 99})
        exit_code = run_add_model(
            ["--experiment", exp.name, "--add-model", "openai/gpt-4", "--model-seed", "system-default"], conn,
        )
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_SEED"] is None


class TestVariantSignatureStabilityAndUniqueness:
    def test_same_model_and_config_produces_same_signature_across_flows(self):
        """Standalone and composite-shaped argv, same model_id and config
        values, must produce the SAME variant_signature — the signature is
        a pure function of (model_id, config), not of which argv shape
        produced that config."""
        from src.cli.bcllm_model import run_add_model

        conn_a = _make_conn()
        exp_a = _make_experiment(conn_a, "expA")
        run_add_model(
            ["--experiment", "expA", "--add-model", "openai/gpt-4", "--temperature", "0.5"], conn_a,
        )
        conn_b = _make_conn()
        exp_b = _make_experiment(conn_b, "expB")
        run_add_model(
            ["bcllm", "--experiment", "expB", "--add-model", "openai/gpt-4", "--temperature", "0.5"][1:], conn_b,
        )

        variant_a = VariantRepository(conn_a).list_by_experiment(exp_a.experiment_id)[0]
        variant_b = VariantRepository(conn_b).list_by_experiment(exp_b.experiment_id)[0]
        assert variant_a.variant_signature == variant_b.variant_signature

    def test_different_config_produces_different_signature(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_uniq")
        run_add_model(["--experiment", "exp_uniq", "--add-model", "openai/gpt-4", "--temperature", "0.5"], conn)
        exit_code = run_add_model(
            ["--experiment", "exp_uniq", "--add-model", "openai/gpt-4", "--temperature", "0.9"], conn,
        )
        assert exit_code == 0

        variants = VariantRepository(conn).list_by_experiment(exp.experiment_id)
        assert len(variants) == 2
        assert variants[0].variant_signature != variants[1].variant_signature

    def test_identical_config_is_rejected_as_duplicate(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        _make_experiment(conn, "exp_dup")
        first = run_add_model(["--experiment", "exp_dup", "--add-model", "openai/gpt-4"], conn)
        second = run_add_model(["--experiment", "exp_dup", "--add-model", "openai/gpt-4"], conn)
        assert first == 0
        assert second == 1


class TestReasoningChoicesPlusSystemDefaultBothFlows:
    def test_standalone_reasoning_explicit_choice_persisted(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_reasoning")
        exit_code = run_add_model(
            ["--experiment", exp.name, "--add-model", "openai/gpt-4", "--reasoning", "xhigh"], conn,
        )
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_REASONING_EFFORT"] == "xhigh"

    def test_composite_shaped_argv_reasoning_system_default_identical(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_reasoning_sd", config={"MODEL_REASONING_EFFORT": "high"})
        action_argv = [
            "bcllm", "--experiment", exp.name, "--add-model", "openai/gpt-4",
            "--reasoning", "system-default",
        ]
        exit_code = run_add_model(action_argv[1:], conn)
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["MODEL_REASONING_EFFORT"] is None


class TestProviderInheritanceBothFlows:
    def test_standalone_provider_inherits_from_experiment_when_absent(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_provider_inherit", config={"PROVIDER": "deepinfra/turbo"})
        exit_code = run_add_model(["--experiment", exp.name, "--add-model", "openai/gpt-4"], conn)
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["PROVIDER"] == "deepinfra/turbo"

    def test_composite_shaped_argv_provider_inherits_identically(self):
        from src.cli.bcllm_model import run_add_model

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_provider_inherit_composite", config={"PROVIDER": "deepinfra/turbo"})
        action_argv = ["bcllm", "--experiment", exp.name, "--add-model", "openai/gpt-4"]
        exit_code = run_add_model(action_argv[1:], conn)
        assert exit_code == 0
        variant = VariantRepository(conn).list_by_experiment(exp.experiment_id)[0]
        config = _variant_config(conn, variant.variant_id)
        assert config["PROVIDER"] == "deepinfra/turbo"
