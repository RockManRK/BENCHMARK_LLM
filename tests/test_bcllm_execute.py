"""Unit tests for bcllm_execute CLI module.

Tests cover:
- Retry policy parsing (unchanged by the marco 4C Typer conversion)
- Filter validation against the REAL schema (validate_filters)
- handle_execute orchestration, using the real ExecuteParsedArgs type

Rewritten 2026-08-21 (CLI migration marco 4C, second slice): the
pre-conversion version of this file hand-rolled its own CREATE TABLE
statements with a schema shape that had already drifted from
src/db/schema.py (e.g. question_snapshots.question_id, which has never
existed — the real columns are json_question_id/question_position; runs
had its own seed/system_prompt/user_prompt columns instead of the real
config JSON blob). Every test here now uses the real create_schema()
instead, so a future schema change is actually caught here rather than
silently validated against a fictional shape. --questions'
--questions/--models parsing (nargs="+" -> comma-separated grammar) moved
to src/cli/commands/execute.py — see tests/unit/cli/test_commands_execute.py
for that grammar's own dedicated coverage; this file only exercises the
DB-level existence checks (validate_filters) and handle_execute's
orchestration, which are unaffected by the parsing-layer syntax change
beyond the parameter shape (list[int] positions instead of list[str] IDs).
"""

import json
import sqlite3
import uuid

import pytest

from src.cli.bcllm_execute import (
    parse_retry_policy,
    validate_filters,
    handle_execute,
)
from src.cli.commands.execute import ExecuteParsedArgs
from src.core.execution_plan import RetryPolicy
from src.db.schema import create_schema
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository
from src.db.models import Experiment, ModelVariant, QuestionSnapshot, Run


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _make_experiment(conn, name: str = "test_exp", config: dict | None = None) -> Experiment:
    exp = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}", name=name, description=None,
        config_json=json.dumps(config or {}), config_hash="deadbeef",
    )
    ExperimentRepository(conn).save(exp)
    return exp


def _make_variant(conn, experiment_id: str, variant_id: str = "var-001", model_id: str = "openai/gpt-4") -> ModelVariant:
    variant = ModelVariant(
        variant_id=variant_id, experiment_id=experiment_id, model_id=model_id,
        variant_signature=f"sig-{variant_id}", config="{}",
    )
    VariantRepository(conn).save(variant)
    return variant


def _make_snapshot(conn, experiment_id: str, position: int, json_question_id: str = "Q001") -> QuestionSnapshot:
    payload = json.dumps({"stem": "test", "options": ["A", "B"], "answer_key": "A"})
    snapshot = QuestionSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}", experiment_id=experiment_id,
        json_question_id=f"{json_question_id}{position}", question_position=position,
        question_payload=payload,
    )
    SnapshotRepository(conn).save(snapshot)
    return snapshot


def _make_run(conn, experiment_id: str, run_id: str = "run-001", status: str = "pending", randomization_seed=None) -> Run:
    run = Run(
        run_id=run_id, experiment_id=experiment_id,
        config=json.dumps({"RANDOMIZATION_SEED": randomization_seed}), status=status,
    )
    RunRepository(conn).save(run, {"RANDOMIZATION_SEED": randomization_seed})
    return run


class TestParseRetryPolicy:
    """Test retry policy parsing. Unchanged by the marco 4C conversion."""

    def test_empty_config_returns_default(self):
        policy = parse_retry_policy("")
        assert policy.max_attempts == 3
        assert policy.backoff == "exponential"

    def test_none_config_returns_default(self):
        policy = parse_retry_policy(None)
        assert policy.max_attempts == 3
        assert policy.backoff == "exponential"

    def test_parse_max_attempts(self):
        policy = parse_retry_policy("max_attempts=5")
        assert policy.max_attempts == 5

    def test_parse_backoff_exponential(self):
        policy = parse_retry_policy("backoff=exponential")
        assert policy.backoff == "exponential"

    def test_parse_backoff_linear(self):
        policy = parse_retry_policy("backoff=linear")
        assert policy.backoff == "linear"

    def test_parse_backoff_constant(self):
        policy = parse_retry_policy("backoff=constant")
        assert policy.backoff == "constant"

    def test_parse_invalid_backoff_raises_error(self):
        with pytest.raises(ValueError, match="Invalid backoff"):
            parse_retry_policy("backoff=invalid")

    def test_parse_combined_config(self):
        policy = parse_retry_policy("max_attempts=5,backoff=linear")
        assert policy.max_attempts == 5
        assert policy.backoff == "linear"

    def test_parse_retry_on(self):
        policy = parse_retry_policy("retry_on=timeout|http_5xx")
        assert policy.retry_on == ("timeout", "http_5xx")


class TestValidateFilters:
    """Test filter validation against the real schema — question_ids are
    now 1-based question_position values, not json_question_id strings."""

    @pytest.fixture
    def db(self):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id, "var-001", "openai/gpt-4")
        _make_variant(conn, exp.experiment_id, "var-002", "anthropic/claude")
        _make_snapshot(conn, exp.experiment_id, 1)
        _make_snapshot(conn, exp.experiment_id, 2)
        _make_run(conn, exp.experiment_id, "run-001", status="pending")
        _make_run(conn, exp.experiment_id, "run-002", status="completed")
        yield conn, exp
        conn.close()

    def test_valid_filters_return_empty_errors(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, "run-001", [1], ["var-001"])
        assert errors == []

    def test_invalid_run_id(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, "run-invalid", None, None)
        assert len(errors) == 1
        assert "Run not found" in errors[0]

    def test_run_wrong_experiment(self, db):
        conn, exp = db
        other_exp = _make_experiment(conn, "other_exp")
        _make_run(conn, other_exp.experiment_id, "run-003", status="pending")

        errors = validate_filters(conn, exp.experiment_id, "run-003", None, None)
        assert len(errors) == 1
        assert "does not belong" in errors[0]

    def test_invalid_question_position(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, None, [999], None)
        assert len(errors) == 1
        assert "Question position not found" in errors[0]
        assert "999" in errors[0]

    def test_valid_question_positions_no_error(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, None, [1, 2], None)
        assert errors == []

    def test_invalid_model_variant_id(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, None, None, ["var-999"])
        assert len(errors) == 1
        assert "Model variant not found" in errors[0]

    def test_multiple_validation_errors(self, db):
        conn, exp = db
        errors = validate_filters(conn, exp.experiment_id, "run-invalid", [999], ["var-999"])
        assert len(errors) == 3


class TestHandleExecute:
    """Test execute command handler against the real schema."""

    def _args(self, experiment, run=None, questions=None, models=None, retry_policy=None):
        return ExecuteParsedArgs(
            experiment=experiment, run=run, questions=questions,
            models=models, retry_policy=retry_policy, execute=True,
        )

    def test_experiment_not_found(self):
        conn = _make_conn()
        args = self._args("nonexistent")

        result = handle_execute(args, conn)
        conn.close()

        assert result == 1

    def test_no_pending_items_message(self, capsys):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id)
        _make_snapshot(conn, exp.experiment_id, 1)
        _make_run(conn, exp.experiment_id, "run-001", status="completed")

        args = self._args("test_exp")
        result = handle_execute(args, conn)
        conn.close()

        assert result == 0
        captured = capsys.readouterr()
        assert "No pending items to execute" in captured.err

    def test_invalid_question_position_filter_returns_1(self):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id)
        _make_snapshot(conn, exp.experiment_id, 1)
        _make_run(conn, exp.experiment_id, "run-001")

        args = self._args("test_exp", questions=[999])
        result = handle_execute(args, conn)
        conn.close()

        assert result == 1

    def test_invalid_model_filter_returns_1(self):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id)
        _make_snapshot(conn, exp.experiment_id, 1)
        _make_run(conn, exp.experiment_id, "run-001")

        args = self._args("test_exp", models=["var-does-not-exist"])
        result = handle_execute(args, conn)
        conn.close()

        assert result == 1

    def test_invalid_run_filter_returns_1(self):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id)
        _make_snapshot(conn, exp.experiment_id, 1)

        args = self._args("test_exp", run="run-does-not-exist")
        result = handle_execute(args, conn)
        conn.close()

        assert result == 1

    def test_invalid_retry_policy_returns_1(self):
        conn = _make_conn()
        exp = _make_experiment(conn, "test_exp")
        _make_variant(conn, exp.experiment_id)
        _make_snapshot(conn, exp.experiment_id, 1)
        _make_run(conn, exp.experiment_id, "run-001")

        args = self._args("test_exp", retry_policy="backoff=not-a-real-strategy")
        result = handle_execute(args, conn)
        conn.close()

        assert result == 1
