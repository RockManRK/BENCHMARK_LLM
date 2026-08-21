"""Tests for the EXECUTE_START/EXECUTE_COMPLETE/EXECUTE_ERROR structured
logging events as wired into bcllm_execute.py's handle_execute
(Checkpoint C2 map applied incrementally, marco 4C second slice,
2026-08-21) — migrates this module's own old-style
logger.info()/logger.error() pipe-delimited f-strings to emit_event, per
docs/status/cli-output-classification.md's documented gap. The redundant
manual "PLAN_LOADED | ..." log line was removed entirely rather than
migrated — Planner.build_plan() already emits Event.PLAN_LOADED/
PLAN_BUILD_COMPLETE with the same information (experiment/models/
questions/runs/total_items), confirmed by reading src/core/planner.py
directly.

Also covers a same-day Guardian finding: every event's `experiment` field
must consistently carry the human-readable name (never the UUID) once the
experiment is resolved, with `experiment_id` as the separate field for the
ID — see the regression assertions in TestExecuteErrorEvent and
TestExecuteCompleteEvent.

Isolation: hermetic, in-memory SQLite via the real create_schema(). No
real .env/production DB or OpenRouter API touched — AsyncOrchestrator.execute
is monkeypatched for the one test needing a "successful execution"
outcome, avoiding a real async/API pipeline just to prove event wiring.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "elog_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_experiment(conn, name="exp_elog"):
    from src.db.repository import ExperimentRepository
    from src.db.models import Experiment
    import uuid

    repo = ExperimentRepository(conn)
    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}", name=name,
        config_json="{}", config_hash="deadbeef",
    )
    repo.save(experiment)
    return experiment


def _make_variant(conn, experiment_id, variant_id="var-001"):
    from src.db.repository import VariantRepository
    from src.db.models import ModelVariant

    variant = ModelVariant(
        variant_id=variant_id, experiment_id=experiment_id, model_id="test/success",
        variant_signature=f"sig-{variant_id}", config="{}",
    )
    VariantRepository(conn).save(variant)
    return variant


def _make_snapshot(conn, experiment_id, position=1):
    from src.db.repository import SnapshotRepository
    from src.db.models import QuestionSnapshot
    import uuid

    payload = json.dumps({"stem": "test", "options": ["A", "B"], "answer_key": "A"})
    snapshot = QuestionSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}", experiment_id=experiment_id,
        json_question_id=f"Q{position:03d}", question_position=position,
        question_payload=payload,
    )
    SnapshotRepository(conn).save(snapshot)
    return snapshot


def _make_run(conn, experiment_id, run_id="run-001", status="pending"):
    from src.db.repository import RunRepository
    from src.db.models import Run

    run = Run(
        run_id=run_id, experiment_id=experiment_id, status=status,
        config=json.dumps({"RANDOMIZATION_SEED": None}),
    )
    RunRepository(conn).save(run, {"RANDOMIZATION_SEED": None})
    return run


def _args(experiment, **overrides):
    from src.cli.commands.execute import ExecuteParsedArgs

    defaults = dict(experiment=experiment, run=None, questions=None, models=None, retry_policy=None, execute=True)
    defaults.update(overrides)
    return ExecuteParsedArgs(**defaults)


class TestExecuteErrorEvent:
    def test_emits_on_experiment_not_found(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_execute import handle_execute

        conn = get_database_connection()
        exit_code = handle_execute(_args("nonexistent"), conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        errors = [e for e in events if e["event_name"] == "execute_error"]
        assert len(errors) == 1
        assert errors[0]["experiment"] == "nonexistent"
        assert "not found" in errors[0]["error"].lower()

    def test_emits_on_validation_error(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_execute import handle_execute

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        _make_variant(conn, experiment.experiment_id)
        _make_snapshot(conn, experiment.experiment_id, position=1)
        _make_run(conn, experiment.experiment_id)

        exit_code = handle_execute(_args(experiment.name, questions=[999]), conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        errors = [e for e in events if e["event_name"] == "execute_error"]
        assert len(errors) == 1
        assert "999" in errors[0]["error"]
        # Regression (Guardian finding, 2026-08-21): once the experiment is
        # resolved, every subsequent event's `experiment` field must carry
        # the same human-readable name EXECUTE_START used — not the UUID —
        # with `experiment_id` as the separate, consistently-present field
        # for the ID. Before the fix, this post-resolution EXECUTE_ERROR
        # populated `experiment` with the UUID instead.
        assert errors[0]["experiment"] == experiment.name
        assert errors[0]["experiment_id"] == experiment.experiment_id


class TestExecuteStartEvent:
    def test_emits_after_experiment_found_even_with_no_pending_work(self, tmp_path):
        """EXECUTE_START fires as soon as the experiment is resolved,
        before Planner/AsyncOrchestrator ever run — proven here via the
        no-pending-work early-return path, which needs no execution
        pipeline mocking at all."""
        from src.cli.database import get_database_connection
        from src.cli.bcllm_execute import handle_execute

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        _make_variant(conn, experiment.experiment_id)
        _make_snapshot(conn, experiment.experiment_id, position=1)
        _make_run(conn, experiment.experiment_id, status="completed")

        exit_code = handle_execute(_args(experiment.name), conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        starts = [e for e in events if e["event_name"] == "execute_start"]
        assert len(starts) == 1
        assert starts[0]["experiment"] == experiment.name
        assert starts[0]["run"] == "all"
        # No EXECUTE_COMPLETE — the run never reached the orchestrator.
        completes = [e for e in events if e["event_name"] == "execute_complete"]
        assert len(completes) == 0


class TestExecuteCompleteEvent:
    def test_emits_with_correct_totals_on_success(self, tmp_path, monkeypatch):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_execute import handle_execute
        from src.core.async_orchestrator import AsyncOrchestrator
        from src.core.execution_engine import ExecutionResult

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        _make_variant(conn, experiment.experiment_id)
        _make_snapshot(conn, experiment.experiment_id, position=1)
        _make_run(conn, experiment.experiment_id, status="pending")

        fake_result = ExecutionResult(
            item_id="item-1", run_id="run-001", variant_id="var-001",
            snapshot_id="snap-1", question_id="Q001", status="success",
            response_text="ok", selected_answer="A", parse_confidence="clear",
            latency_ms=10, input_tokens=1, response_tokens=1,
            error_type=None, error_message=None, attempt_count=1,
            reasoning_tokens=None, cost=0.0, effective_tokens=2,
            raw_response=None, started_at=datetime.now(), finished_at=datetime.now(),
            finish_reason="stop", randomization_enabled=False, randomization_seed=None,
            options_presented=["A", "B"], correct_option_presented="A",
            option_letter_map={"A": "A", "B": "B"},
        )
        monkeypatch.setattr(AsyncOrchestrator, "execute", lambda self, plan: [fake_result])

        exit_code = handle_execute(_args(experiment.name), conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        completes = [e for e in events if e["event_name"] == "execute_complete"]
        assert len(completes) == 1
        assert completes[0]["total"] == 1
        assert completes[0]["succeeded"] == 1
        assert completes[0]["failed"] == 0
        # Regression (Guardian finding, 2026-08-21): see the matching
        # assertion in TestExecuteErrorEvent.test_emits_on_validation_error.
        assert completes[0]["experiment"] == experiment.name
        assert completes[0]["experiment_id"] == experiment.experiment_id
