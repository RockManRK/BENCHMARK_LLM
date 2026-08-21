"""Tests for QUESTIONS_ADDED / QUESTION_REMOVED structured logging events
(Checkpoint C2 map applied incrementally to bcllm_questions.py, marco 4A,
2026-08-20) — both events were previously unwired (QUESTIONS_ADDED) or
nonexistent (QUESTION_REMOVED), per
docs/status/cli-output-classification.md's priority list.
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


def _make_snapshot(conn, experiment_id, question_id="Q001"):
    from src.db.repository import SnapshotRepository
    from src.db.models import QuestionSnapshot
    import uuid

    repo = SnapshotRepository(conn)
    snapshot = QuestionSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment_id,
        json_question_id=question_id,
        question_position=1,
        question_payload=json.dumps({"stem": "test", "options": {}, "answer_key": "A"}),
    )
    repo.save(snapshot)
    return snapshot


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


class TestQuestionRemovedEvent:
    def test_handle_remove_question_emits_event_on_success(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_questions import handle_remove_question

        conn = get_database_connection()
        experiment = _make_experiment(conn)
        snapshot = _make_snapshot(conn, experiment.experiment_id)

        exit_code = handle_remove_question(experiment.name, snapshot.snapshot_id, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        removed = [e for e in events if e["event_name"] == "question_removed"]
        assert len(removed) == 1
        assert removed[0]["experiment"] == experiment.name
        assert removed[0]["snapshot_id"] == snapshot.snapshot_id
        assert removed[0]["question_id"] == snapshot.json_question_id

    def test_handle_remove_question_does_not_emit_when_not_found(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.bcllm_questions import handle_remove_question

        conn = get_database_connection()
        experiment = _make_experiment(conn)

        exit_code = handle_remove_question(experiment.name, "snap_doesnotexist", conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        removed = [e for e in events if e["event_name"] == "question_removed"]
        assert len(removed) == 0


def _write_dataset(tmp_path) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({
        "questions": [
            {"id": "1", "stem": "Q1?", "options": {"A": "x", "B": "y"}, "answer_key": "A"},
        ]
    }), encoding="utf-8")
    return path
