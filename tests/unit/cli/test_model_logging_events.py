"""Tests for the MODEL_ADDED structured logging event as wired into
bcllm_model.py's add_model_action (Checkpoint C2 map applied
incrementally, marco 4B second slice, 2026-08-20) — the specific gap the
user called out for this slice: MODEL_ADDED already existed and was
already wired into bcllm_experiment.py's _add_models_at_creation (marco
4A), but NOT into this module's own --add-model path.

Also confirms no double-emission: bcllm.py's real composite flow
(--create-experiment + --add-model, via _handle_composite_flow) calls
src.cli.bcllm_model.run_add_model directly (see
bcllm.py::_execute_action_request) — NOT
bcllm_experiment.py::_add_models_at_creation, which is unreachable from
the actual `bcllm.py` entry point once --add-model is present (module
resolution routes to bcllm_model, not bcllm_experiment, whenever any
ADD_ACTION_FLAGS flag is set — see src/core/module_resolver.py). So the
composite flow emits exactly one MODEL_ADDED event per model added, from
this module's add_model_action, same as standalone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "mlog_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_experiment(conn, name="exp_mlog"):
    from src.db.repository import ExperimentRepository
    from src.db.models import Experiment
    import uuid

    repo = ExperimentRepository(conn)
    experiment = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
        name=name,
        config_json="{}",
        config_hash="deadbeef",
    )
    repo.save(experiment)
    return experiment


class TestModelAddedEventStandalone:
    def test_run_add_model_emits_event_on_success(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_model import run_add_model

        conn = get_database_connection()
        experiment = _make_experiment(conn)

        exit_code = run_add_model(
            ["--experiment", experiment.name, "--add-model", "openai/gpt-4"], conn=conn,
        )
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "model_added"]
        assert len(added) == 1
        assert added[0]["experiment"] == experiment.name
        assert added[0]["model_id"] == "openai/gpt-4"
        assert "variant_signature" in added[0]

    def test_run_add_model_does_not_emit_on_failure(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_model import run_add_model

        conn = get_database_connection()
        exit_code = run_add_model(
            ["--experiment", "nonexistent_experiment", "--add-model", "openai/gpt-4"], conn=conn,
        )
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "model_added"]
        assert len(added) == 0

    def test_run_add_model_does_not_emit_on_duplicate(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_model import run_add_model

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        run_add_model(["--experiment", experiment.name, "--add-model", "openai/gpt-4"], conn=conn)

        events_after_first = len(
            [e for e in _read_jsonl(tmp_path) if e["event_name"] == "model_added"]
        )
        exit_code = run_add_model(
            ["--experiment", experiment.name, "--add-model", "openai/gpt-4"], conn=conn,
        )
        conn.close()

        assert exit_code == 1
        added = [e for e in _read_jsonl(tmp_path) if e["event_name"] == "model_added"]
        assert len(added) == events_after_first == 1


class TestModelAddedEventComposite:
    def test_composite_flow_emits_exactly_one_event_per_model(self, tmp_path):
        """The real bcllm.py entry point for --create-experiment +
        --add-model — proves the live composite path emits via THIS
        module's add_model_action (not the unreachable-in-practice
        bcllm_experiment.py::_add_models_at_creation), and exactly once."""
        import bcllm
        from src.core.mode import Mode

        argv = [
            "bcllm.py", "--create-experiment", "exp_mlog_composite",
            "--add-model", "openai/gpt-4",
        ]
        handled, exit_code = bcllm._handle_composite_flow(argv, Mode.CREATE, "bcllm_model")

        assert handled is True
        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "model_added"]
        assert len(added) == 1
        assert added[0]["experiment"] == "exp_mlog_composite"
        assert added[0]["model_id"] == "openai/gpt-4"
