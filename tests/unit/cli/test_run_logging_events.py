"""Tests for RUN_CREATED / RUN_REMOVED structured logging events
(Checkpoint C2 map applied incrementally to bcllm_run.py, marco 4B first
slice, 2026-08-20) — RUN_CREATED existed but was never wired anywhere;
RUN_REMOVED is new.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "rlog_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_experiment(conn, name="exp_rlog"):
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


class TestRunCreatedEvent:
    def test_run_add_run_emits_event_on_success(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_run import run_add_run

        conn = get_database_connection()
        experiment = _make_experiment(conn)

        exit_code = run_add_run(["--experiment", experiment.name, "--add-run"], conn=conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        created = [e for e in events if e["event_name"] == "run_created"]
        assert len(created) == 1
        assert created[0]["experiment"] == experiment.name
        assert "run_id" in created[0]

    def test_run_add_run_does_not_emit_on_failure(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_run import run_add_run

        conn = get_database_connection()
        exit_code = run_add_run(["--experiment", "nonexistent_experiment", "--add-run"], conn=conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        created = [e for e in events if e["event_name"] == "run_created"]
        assert len(created) == 0


class TestRunRemovedEvent:
    def test_handle_remove_run_emits_event_on_success(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_run import run_add_run, handle_remove_run

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        run_add_run(["--experiment", experiment.name, "--add-run"], conn=conn)

        from src.db.repository import RunRepository
        run = RunRepository(conn).list_by_experiment(experiment.experiment_id)[0]

        exit_code = handle_remove_run(experiment.name, run.run_id, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        removed = [e for e in events if e["event_name"] == "run_removed"]
        assert len(removed) == 1
        assert removed[0]["experiment"] == experiment.name
        assert removed[0]["run_id"] == run.run_id

    def test_handle_remove_run_does_not_emit_when_not_found(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_run import handle_remove_run

        conn = get_database_connection()
        experiment = _make_experiment(conn)

        exit_code = handle_remove_run(experiment.name, "run_doesnotexist", conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        removed = [e for e in events if e["event_name"] == "run_removed"]
        assert len(removed) == 0
