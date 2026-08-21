"""Tests for EXPERIMENT_CREATED / MODEL_ADDED / MUTATION_REFUSED
structured logging events (Checkpoint C2 map applied incrementally to
bcllm_experiment.py, marco 4A, 2026-08-20) — EXPERIMENT_CREATED existed
but only as an old-style unstructured logger.info() call; MODEL_ADDED
existed but was never wired at all in this module's creation-time path;
MUTATION_REFUSED is new.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.utils.logging_config import LoggingConfig, setup_logging


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "elog_test.db"))
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


@pytest.fixture
def dataset_path(tmp_path, monkeypatch):
    """handle_create_experiment always attempts question-snapshot
    creation as its final step — needs a valid QUESTIONS_DATASET_PATH,
    matching the pattern already used in test_questions_system_default.py."""
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps({
        "questions": [{"id": "Q001", "stem": "Q1?", "options": {"A": "a", "B": "b"}, "answer_key": "A"}]
    }), encoding="utf-8")
    monkeypatch.setenv("QUESTIONS_DATASET_PATH", str(path))
    return str(path)


class TestExperimentCreatedEvent:
    def test_create_experiment_emits_event(self, tmp_path, dataset_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_create_experiment

        conn = get_database_connection()
        args = parse_experiment_argv(["--create-experiment", "exp_elog"])
        exit_code = handle_create_experiment(args, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        created = [e for e in events if e["event_name"] == "experiment_created"]
        assert len(created) == 1
        assert created[0]["name"] == "exp_elog"
        assert "experiment_id" in created[0]

    def test_duplicate_experiment_does_not_emit(self, tmp_path, dataset_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_create_experiment

        conn = get_database_connection()
        args = parse_experiment_argv(["--create-experiment", "exp_dup"])
        assert handle_create_experiment(args, conn) == 0

        exit_code = handle_create_experiment(args, conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        created = [e for e in events if e["event_name"] == "experiment_created"]
        assert len(created) == 1  # only the first call


class TestModelAddedEvent:
    def test_add_model_at_creation_emits_event(self, tmp_path, dataset_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_create_experiment

        conn = get_database_connection()
        args = parse_experiment_argv([
            "--create-experiment", "exp_model_added", "--add-model", "test/success",
        ])
        exit_code = handle_create_experiment(args, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "model_added"]
        assert len(added) == 1
        assert added[0]["experiment"] == "exp_model_added"
        assert added[0]["model_id"] == "test/success"

    def test_no_add_model_flag_emits_nothing(self, tmp_path, dataset_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_create_experiment

        conn = get_database_connection()
        args = parse_experiment_argv(["--create-experiment", "exp_no_model"])
        exit_code = handle_create_experiment(args, conn)
        conn.close()

        assert exit_code == 0
        events = _read_jsonl(tmp_path)
        added = [e for e in events if e["event_name"] == "model_added"]
        assert len(added) == 0


class TestMutationRefusedEvent:
    def test_remove_experiment_refused_emits_event(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_remove_experiment

        conn = get_database_connection()
        args = parse_experiment_argv(["--remove-experiment", "exp_removeme"])
        exit_code = handle_remove_experiment(args, conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        refused = [e for e in events if e["event_name"] == "mutation_refused"]
        assert len(refused) == 1
        assert refused[0]["experiment"] == "exp_removeme"
        assert refused[0]["reason"] == "remove_experiment_disabled"

    def test_provider_lock_modify_refused_emits_event(self, tmp_path):
        from src.cli.database import get_database_connection
        from src.cli.commands.experiment import parse_experiment_argv
        from src.cli.bcllm_experiment import handle_modify_provider_lock

        conn = get_database_connection()
        args = parse_experiment_argv(["--experiment", "exp_lockme", "--provider-lock", "true"])
        exit_code = handle_modify_provider_lock(args, conn)
        conn.close()

        assert exit_code == 1
        events = _read_jsonl(tmp_path)
        refused = [e for e in events if e["event_name"] == "mutation_refused"]
        assert len(refused) == 1
        assert refused[0]["experiment"] == "exp_lockme"
        assert refused[0]["reason"] == "provider_lock_modify_disabled"
