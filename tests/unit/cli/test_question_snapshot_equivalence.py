"""Equivalence tests: both real CLI entry points that snapshot questions
must produce the identical `question_payload` for the same source question.

Context (docs/status/known-issues.md, "double-wrapped meta field"): before
this fix, `src/cli/bcllm_experiment.py::_create_question_snapshots`
(composite flow: `--create-experiment X --add-questions ...`) and
`src/cli/bcllm_questions.py::handle_add_questions` (standalone flow:
`--experiment X --add-questions ...`) built the snapshot payload
independently and diverged — the composite flow double-wrapped `meta`.
Both now call the single canonical `build_question_snapshot_payload`
(src/core/question_loader.py). These tests invoke both real code paths
directly (no subprocess) and compare their output byte-for-byte.

Updated 2026-08-19 (same-action-same-path checkpoint,
docs/status/known-issues.md): `handle_add_questions` was retired in favor
of `add_questions_action(request: AddQuestionsRequest, conn)` — the
standalone side of this equivalence test now calls that directly.

Isolation: no real .env/production DB is touched. `_create_question_snapshots`
reads QUESTIONS_DATASET_PATH from os.environ via ConfigResolver.load_env()
(which only snapshots os.environ — it does NOT call load_dotenv() itself;
that happens once, only in bcllm.py's real entry point, never in a pytest
process). monkeypatch.setenv/delenv here are therefore safe and hermetic.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from src.db.models import Experiment
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.db.schema import create_schema


DATASET_CONTENT = {
    "questions": [
        {
            "id": "Q001",
            "stem": "Questão sobre hipertensão arterial sistêmica (HAS)?",
            "options": {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
            "answer_key": "B",
            "assets": ["data/assets/image_Q001.png"],
            "meta": {"has_table": False, "has_image": True, "status": "valid", "notes": ""},
        }
    ]
}


class _Args:
    """Minimal stand-in for argparse.Namespace with just the attributes
    each handler reads (same pattern as tests/unit/cli/test_remove_commands.py)."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


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


@pytest.fixture
def dataset_path(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(DATASET_CONTENT), encoding="utf-8")
    return str(path)


def test_composite_and_standalone_flows_produce_equivalent_payload(dataset_path, monkeypatch):
    from src.cli.bcllm_experiment import _create_question_snapshots
    from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

    # --- Composite flow: --create-experiment X --add-questions ... ---
    monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
    monkeypatch.delenv("DEFAULT_QUESTIONS", raising=False)
    monkeypatch.delenv("QUESTIONS_STATUS_ADD", raising=False)
    monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)

    conn_composite = _make_conn()
    exp_composite = _make_experiment(conn_composite, "composite-exp")
    args_composite = _Args(add_questions="Q001", where=None, exclude=None)

    exit_code_composite = _create_question_snapshots(args_composite, exp_composite, conn_composite)
    assert exit_code_composite == 0

    # --- Standalone flow: --experiment X --add-questions ... ---
    conn_standalone = _make_conn()
    exp_standalone = _make_experiment(conn_standalone, "standalone-exp")
    request_standalone = AddQuestionsRequest(
        experiment="standalone-exp",
        source_file=dataset_path,
        add_questions="Q001",
        where=[],
        exclude=[],
    )

    result_standalone = add_questions_action(request_standalone, conn_standalone)
    assert result_standalone.exit_code == 0

    # --- Compare resulting payloads ---
    snapshot_composite = SnapshotRepository(conn_composite).get_by_experiment_and_question(
        exp_composite.experiment_id, "Q001"
    )
    snapshot_standalone = SnapshotRepository(conn_standalone).get_by_experiment_and_question(
        exp_standalone.experiment_id, "Q001"
    )

    assert snapshot_composite is not None
    assert snapshot_standalone is not None

    payload_composite = json.loads(snapshot_composite.question_payload)
    payload_standalone = json.loads(snapshot_standalone.question_payload)

    # 1. Payload equivalent across both flows.
    assert payload_composite == payload_standalone

    # 2. meta.has_image directly accessible (no unwrapping needed).
    assert payload_composite["meta"]["has_image"] is True
    assert payload_standalone["meta"]["has_image"] is True

    # 4. No meta.meta double-wrap in either flow.
    assert "meta" not in payload_composite["meta"]
    assert "meta" not in payload_standalone["meta"]

    # ensure_ascii=False contract: accented characters preserved literally
    # in the serialized JSON stored on disk/DB for both flows.
    assert "Questão" in snapshot_composite.question_payload
    assert "hipertensão" in snapshot_composite.question_payload
    assert "Questão" in snapshot_standalone.question_payload
    assert "hipertensão" in snapshot_standalone.question_payload

    conn_composite.close()
    conn_standalone.close()
