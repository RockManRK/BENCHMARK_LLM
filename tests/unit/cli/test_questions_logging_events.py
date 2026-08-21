"""Tests for QUESTIONS_ADDED structured logging events (Checkpoint C2 map
applied incrementally to bcllm_questions.py, marco 4A, 2026-08-20) — the
event was previously unwired, per
docs/status/cli-output-classification.md's priority list.

QUESTION_REMOVED (and handle_remove_question, and --remove-question
itself) existed briefly and was removed the same day — QuestionSnapshot
is immutable, an experiment can only grow by adding snapshots. See
docs/status/known-issues.md and
tests/unit/cli/test_remove_question_removed.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "qlog_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("QUESTIONS_DATASET_PATH", raising=False)
    setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _make_experiment(conn, name="exp_qlog"):
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


class TestQuestionsAddedEvent:
    def test_run_add_questions_emits_questions_added_on_success(self, tmp_path, monkeypatch):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_questions import run_add_questions

        conn = get_database_connection()
        experiment = _make_experiment(conn)

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", str(_write_dataset(tmp_path)))

        exit_code = run_add_questions(
            ["--experiment", experiment.name, "--add-questions", "1"], conn=conn,
        )
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "questions_added"]
        assert len(added) == 1
        assert added[0]["experiment"] == experiment.name
        assert added[0]["added_count"] == 1

    def test_run_add_questions_does_not_emit_on_failure(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_questions import run_add_questions

        conn = get_database_connection()
        exit_code = run_add_questions(
            ["--experiment", "nonexistent_experiment", "--add-questions", "1"], conn=conn,
        )
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "questions_added"]
        assert len(added) == 0


def _write_dataset(tmp_path) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({
        "questions": [
            {"id": "1", "stem": "Q1?", "options": {"A": "x", "B": "y"}, "answer_key": "A"},
        ]
    }), encoding="utf-8")
    return path
