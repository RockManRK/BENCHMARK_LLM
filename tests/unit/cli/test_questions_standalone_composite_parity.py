"""Expanded standalone/composite parity proof for bcllm_questions.py's
Typer conversion (marco 4A, 2026-08-20), requested explicitly before
proceeding to bcllm_experiment.py. Unlike
tests/unit/cli/test_questions_system_default.py (which mostly calls
add_questions_action/_create_question_snapshots directly with hand-built
AddQuestionsRequest/_Args), every test here goes through REAL argv and
the actual entry points main()/run_add_questions()/parse_add_questions_request()
use in production — i.e. through src/cli/commands/questions.py's Typer
command, the single canonical parser, for both flows.

Covers, specifically:
1. system-default (both flows, real argv)
2. multiple --where/--exclude repeated flags (both flows, real argv)
3. system-default + concrete filter contradiction, exit 2 (both flows,
   including the composite PRE-PARSE phase — bcllm.py never even reaches
   this point via subprocess in a unit test, so this proves
   parse_add_questions_request's own contract in isolation)
4. --add-questions/--questions alias equivalence (identical persisted
   snapshot IDs from otherwise-identical argv)
5. usage error before any DB connection (composite pre-parse phase)
6. rollback: NOT duplicated here — already proven by
   tests/unit/cli/test_composite_flow_rollback.py::TestFailureAtDifferentPointsInTheSequence::test_add_questions_failure_after_model_already_written
   (real UnitOfWork, real 'null' literal usage error during
   parse_add_questions_request, confirms everything written so far in
   the composite transaction is rolled back) — verified passing
   (2026-08-20) as part of this same check.
7. persisted-result equality: full payload comparison (not just ID sets)
   already proven by test_question_snapshot_equivalence.py; extended
   here for the alias case specifically.

Isolation: hermetic in-memory SQLite + tmp_path dataset, matching the
existing sibling test files' pattern. No real .env/DB touched.
"""

from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.core.argv_utils import ParserExit
from src.db.models import Experiment
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.db.schema import create_schema


DATASET_CONTENT = {
    "questions": [
        {"id": "Q001", "stem": "Q1?", "options": {"A": "a", "B": "b"}, "answer_key": "A", "meta": {"status": "valid"}},
        {"id": "Q002", "stem": "Q2?", "options": {"A": "a", "B": "b"}, "answer_key": "B", "meta": {"status": "annulled"}},
        {"id": "Q003", "stem": "Q3?", "options": {"A": "a", "B": "b"}, "answer_key": "C", "meta": {"status": "valid"}},
    ]
}


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    create_schema(conn)
    return conn


def _make_experiment(conn, name: str) -> Experiment:
    exp = Experiment(
        experiment_id=f"exp_{uuid.uuid4().hex[:8]}", name=name, description=None,
        config_json=json.dumps({}), config_hash="deadbeef",
    )
    ExperimentRepository(conn).save(exp)
    return exp


@pytest.fixture
def dataset_path(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(DATASET_CONTENT), encoding="utf-8")
    return str(path)


def _snapshot_ids(conn, experiment_id: str) -> set[str]:
    return {s.json_question_id for s in SnapshotRepository(conn).list_by_experiment(experiment_id)}


def _payloads_by_qid(conn, experiment_id: str) -> dict[str, dict]:
    return {
        s.json_question_id: json.loads(s.question_payload)
        for s in SnapshotRepository(conn).list_by_experiment(experiment_id)
    }


class TestSystemDefaultBothFlowsRealArgv:
    def test_standalone_real_argv(self, dataset_path):
        from src.cli.bcllm_questions import run_add_questions

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_sd_standalone")
        code = run_add_questions(
            ["--experiment", exp.name, "--source-file", dataset_path, "--add-questions", "system-default"],
            conn,
        )
        assert code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}

    def test_composite_shaped_argv(self, dataset_path):
        """Mirrors exactly the argv shape bcllm.py::_build_action_argv
        constructs for the composite flow: ["bcllm", "--experiment",
        name, "--add-questions", value, ...other relevant flags]."""
        from src.cli.bcllm_questions import run_add_questions

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_sd_composite")
        action_argv = ["bcllm", "--experiment", exp.name, "--add-questions", "system-default", "--source-file", dataset_path]
        code = run_add_questions(action_argv[1:], conn)
        assert code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}


class TestMultipleWhereExcludeBothFlowsRealArgv:
    def test_standalone_repeated_where(self, dataset_path):
        from src.cli.bcllm_questions import run_add_questions

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_multi_standalone")
        code = run_add_questions(
            [
                "--experiment", exp.name, "--source-file", dataset_path,
                "--add-questions", "Q001,Q002,Q003",
                "--where", "status=valid", "--where", "status=valid",
            ],
            conn,
        )
        assert code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q003"}

    def test_composite_shaped_repeated_where_and_exclude(self, dataset_path):
        from src.cli.bcllm_questions import run_add_questions

        conn = _make_conn()
        exp = _make_experiment(conn, "exp_multi_composite")
        action_argv = [
            "bcllm", "--experiment", exp.name, "--add-questions", "Q001,Q002,Q003",
            "--source-file", dataset_path,
            "--where", "status=valid", "--exclude", "status=annulled",
        ]
        code = run_add_questions(action_argv[1:], conn)
        assert code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q003"}


class TestContradictionBothFlowsRealArgv:
    def test_standalone_via_main(self, monkeypatch, dataset_path):
        import sys
        from unittest.mock import patch
        from src.core.mode import Mode
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "exp1", "--source-file", dataset_path,
            "--add-questions", "Q001", "--where", "system-default", "--where", "status=valid",
        ])
        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_composite_pre_parse_phase_raises_before_any_connection(self, dataset_path):
        """Exercises parse_add_questions_request directly — this IS what
        bcllm.py's composite pre-parse phase calls, before opening any
        connection or acquiring the UnitOfWork lock (see
        docs/status/composite-flow-unit-of-work-design.md point 3)."""
        from src.cli.bcllm_questions import parse_add_questions_request

        action_argv = [
            "--experiment", "exp1", "--add-questions", "Q001",
            "--source-file", dataset_path,
            "--where", "system-default", "--where", "status=valid",
        ]
        with pytest.raises(ParserExit) as exc_info:
            parse_add_questions_request(action_argv)
        assert exc_info.value.status == 2


class TestAliasEquivalence:
    def test_add_questions_and_questions_alias_produce_identical_result(self, dataset_path):
        from src.cli.bcllm_questions import run_add_questions

        conn_a = _make_conn()
        exp_a = _make_experiment(conn_a, "exp_alias_a")
        code_a = run_add_questions(
            ["--experiment", exp_a.name, "--source-file", dataset_path, "--add-questions", "Q001,Q002"],
            conn_a,
        )

        conn_b = _make_conn()
        exp_b = _make_experiment(conn_b, "exp_alias_b")
        code_b = run_add_questions(
            ["--experiment", exp_b.name, "--source-file", dataset_path, "--questions", "Q001,Q002"],
            conn_b,
        )

        assert code_a == code_b == 0
        assert _snapshot_ids(conn_a, exp_a.experiment_id) == _snapshot_ids(conn_b, exp_b.experiment_id) == {"Q001", "Q002"}

        # Full payload equality, not just which IDs were added (item 7).
        payloads_a = _payloads_by_qid(conn_a, exp_a.experiment_id)
        payloads_b = _payloads_by_qid(conn_b, exp_b.experiment_id)
        assert payloads_a["Q001"] == payloads_b["Q001"]
        assert payloads_a["Q002"] == payloads_b["Q002"]

    def test_alias_and_canonical_flag_produce_identical_parsed_request(self, dataset_path):
        """Same alias equivalence, one level lower — proves the two
        spellings resolve to the identical AddQuestionsRequest before any
        DB action runs at all."""
        from src.cli.bcllm_questions import parse_add_questions_request

        req_canonical = parse_add_questions_request(
            ["--experiment", "exp1", "--source-file", dataset_path, "--add-questions", "Q001,Q002"]
        )
        req_alias = parse_add_questions_request(
            ["--experiment", "exp1", "--source-file", dataset_path, "--questions", "Q001,Q002"]
        )
        assert req_canonical == req_alias


class TestUsageErrorBeforeConnectionCompositePhase:
    def test_forbidden_experiment_in_composite_shaped_argv_never_connects(self, dataset_path):
        from src.cli.bcllm_questions import parse_add_questions_request

        with pytest.raises(ParserExit) as exc_info:
            parse_add_questions_request([
                "--experiment", "system-default", "--add-questions", "Q001", "--source-file", dataset_path,
            ])
        assert exc_info.value.status == 2

    def test_deprecated_null_in_composite_shaped_argv_never_connects(self, dataset_path):
        from src.cli.bcllm_questions import parse_add_questions_request

        with pytest.raises(ParserExit) as exc_info:
            parse_add_questions_request([
                "--experiment", "exp1", "--add-questions", "null", "--source-file", dataset_path,
            ])
        assert exc_info.value.status == 2
