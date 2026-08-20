"""Regression tests for item 1 (docs/status/known-issues.md's "system-default
gap in bcllm_questions.py"), implemented in CLI Typer migration Fase 4
marco 4A. Covers the 8 points the user explicitly asked to validate
separately before proceeding with 4A:

1. --add-questions system-default
2. --where system-default
3. --exclude system-default
4. multiple concrete filters repeating the flag (AND-combined, no error)
5. system-default combined with a concrete filter -> exit code 2
6. equivalence between the standalone and composite flows
7. no .env consultation for --where/--exclude in the standalone
   (post-creation) flow
8. no persistent write before a usage error

Updated 2026-08-19 (same-action-same-path checkpoint,
docs/status/known-issues.md): `handle_add_questions` was retired in favor
of `add_questions_action(request: AddQuestionsRequest, conn)`, called
through the single `run_add_questions()` adapter by both main() and
bcllm.py's composite flow. main() no longer raises SystemExit for a usage
error — NonExitingArgumentParser makes it return the exit code instead
(see src/core/argv_utils.py) — tests that used to expect
`pytest.raises(SystemExit)` now call main() directly and assert its
return value.

Isolation: hermetic, in-memory SQLite + a tmp_path dataset file. No real
.env/production DB touched — QUESTIONS_DATASET_PATH is always supplied
either via --source-file (standalone) or monkeypatch.setenv (composite,
matching tests/unit/cli/test_question_snapshot_equivalence.py's approach).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest

from src.core.mode import Mode
from src.core.special_config_values import FORCE_SYSTEM_DEFAULT
from src.db.models import Experiment
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.db.schema import create_schema


DATASET_CONTENT = {
    "questions": [
        {
            "id": "Q001",
            "stem": "Question 1?",
            "options": {"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
            "answer_key": "A",
            "assets": [],
            "meta": {"status": "valid"},
        },
        {
            "id": "Q002",
            "stem": "Question 2?",
            "options": {"A": "a2", "B": "b2", "C": "c2", "D": "d2"},
            "answer_key": "B",
            "assets": [],
            "meta": {"status": "annulled"},
        },
        {
            "id": "Q003",
            "stem": "Question 3?",
            "options": {"A": "a3", "B": "b3", "C": "c3", "D": "d3"},
            "answer_key": "C",
            "assets": [],
            "meta": {"status": "valid"},
        },
    ]
}


class _Args:
    """Stand-in for bcllm_experiment.py's argparse.Namespace — that
    module's _create_question_snapshots wasn't touched by the request/
    result refactor (only the 3 composite-eligible actions were)."""

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


def _snapshot_ids(conn, experiment_id: str) -> set[str]:
    return {s.json_question_id for s in SnapshotRepository(conn).list_by_experiment(experiment_id)}


# =============================================================================
# 1. --add-questions system-default (standalone)
# =============================================================================

class TestAddQuestionsSystemDefault:
    def test_standalone_selects_all_questions(self, dataset_path):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        request = AddQuestionsRequest(
            experiment="exp1", source_file=dataset_path,
            add_questions=FORCE_SYSTEM_DEFAULT, where=[], exclude=[],
        )

        result = add_questions_action(request, conn)

        assert result.exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}

    def test_composite_selects_all_questions_ignoring_default_questions_env(self, dataset_path, monkeypatch):
        from src.cli.bcllm_experiment import _create_question_snapshots

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
        monkeypatch.setenv("DEFAULT_QUESTIONS", "Q001")  # would select only Q001 if consulted
        monkeypatch.delenv("QUESTIONS_STATUS_ADD", raising=False)
        monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        args = _Args(add_questions=FORCE_SYSTEM_DEFAULT, where=[], exclude=[])

        exit_code = _create_question_snapshots(args, exp, conn)

        assert exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}


# =============================================================================
# 2 & 3. --where / --exclude system-default (both flows)
# =============================================================================

class TestWhereExcludeSystemDefault:
    def test_standalone_where_system_default_applies_no_filter(self, dataset_path):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        request = AddQuestionsRequest(
            experiment="exp1", source_file=dataset_path,
            add_questions="Q001,Q002,Q003", where=FORCE_SYSTEM_DEFAULT, exclude=[],
        )

        result = add_questions_action(request, conn)

        assert result.exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}

    def test_standalone_exclude_system_default_applies_no_filter(self, dataset_path):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        request = AddQuestionsRequest(
            experiment="exp1", source_file=dataset_path,
            add_questions="Q001,Q002,Q003", where=[], exclude=FORCE_SYSTEM_DEFAULT,
        )

        result = add_questions_action(request, conn)

        assert result.exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}

    def test_composite_where_system_default_ignores_env_status_add(self, dataset_path, monkeypatch):
        """Bootstrap case: --where system-default must skip the
        QUESTIONS_STATUS_ADD .env fallback entirely, not just apply an
        empty concrete filter."""
        from src.cli.bcllm_experiment import _create_question_snapshots

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
        monkeypatch.delenv("DEFAULT_QUESTIONS", raising=False)
        monkeypatch.setenv("QUESTIONS_STATUS_ADD", "status=valid")  # would drop Q002 if consulted
        monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        args = _Args(add_questions=None, where=FORCE_SYSTEM_DEFAULT, exclude=[])

        exit_code = _create_question_snapshots(args, exp, conn)

        assert exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}

    def test_composite_where_not_provided_still_uses_env_fallback(self, dataset_path, monkeypatch):
        """Non-regression: the ([] not-provided) case must still consult
        .env — only explicit system-default skips it."""
        from src.cli.bcllm_experiment import _create_question_snapshots

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
        monkeypatch.delenv("DEFAULT_QUESTIONS", raising=False)
        monkeypatch.setenv("QUESTIONS_STATUS_ADD", "status=valid")
        monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        args = _Args(add_questions=None, where=[], exclude=[])

        exit_code = _create_question_snapshots(args, exp, conn)

        assert exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q003"}  # Q002 (annulled) filtered out


# =============================================================================
# 4. Multiple concrete filters repeating the flag (AND-combined, no error)
# =============================================================================

class TestMultipleConcreteFiltersAllowed:
    def test_standalone_multiple_where_and_combined(self, dataset_path):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        request = AddQuestionsRequest(
            experiment="exp1", source_file=dataset_path,
            add_questions="Q001,Q002,Q003",
            where=["status=valid", "status=valid"],  # both concrete, repeated flag, AND-combined
            exclude=[],
        )

        result = add_questions_action(request, conn)

        assert result.exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q003"}


# =============================================================================
# 5. system-default combined with a concrete filter -> exit code 2
# =============================================================================

class TestContradictionExitsWithCode2:
    def test_main_returns_2_on_where_contradiction(self, monkeypatch, dataset_path):
        import sys
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "exp1", "--source-file", dataset_path,
            "--add-questions", "Q001", "--where", "system-default", "--where", "status=valid",
        ])

        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_main_returns_2_on_exclude_contradiction(self, monkeypatch, dataset_path):
        import sys
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "exp1", "--source-file", dataset_path,
            "--add-questions", "Q001", "--exclude", "status=annulled", "--exclude", "system-default",
        ])

        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()


# =============================================================================
# 6. Equivalence between standalone and composite flows
# =============================================================================

class TestStandaloneCompositeEquivalence:
    def test_add_questions_system_default_equivalent(self, dataset_path, monkeypatch):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest
        from src.cli.bcllm_experiment import _create_question_snapshots

        conn_standalone = _make_conn()
        exp_standalone = _make_experiment(conn_standalone, "standalone-exp")
        request_standalone = AddQuestionsRequest(
            experiment="standalone-exp", source_file=dataset_path,
            add_questions=FORCE_SYSTEM_DEFAULT, where=[], exclude=[],
        )
        assert add_questions_action(request_standalone, conn_standalone).exit_code == 0

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
        monkeypatch.delenv("DEFAULT_QUESTIONS", raising=False)
        monkeypatch.delenv("QUESTIONS_STATUS_ADD", raising=False)
        monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)
        conn_composite = _make_conn()
        exp_composite = _make_experiment(conn_composite, "composite-exp")
        args_composite = _Args(add_questions=FORCE_SYSTEM_DEFAULT, where=[], exclude=[])
        assert _create_question_snapshots(args_composite, exp_composite, conn_composite) == 0

        assert _snapshot_ids(conn_standalone, exp_standalone.experiment_id) == _snapshot_ids(conn_composite, exp_composite.experiment_id)

    def test_where_concrete_filter_equivalent(self, dataset_path, monkeypatch):
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest
        from src.cli.bcllm_experiment import _create_question_snapshots

        conn_standalone = _make_conn()
        exp_standalone = _make_experiment(conn_standalone, "standalone-exp")
        request_standalone = AddQuestionsRequest(
            experiment="standalone-exp", source_file=dataset_path,
            add_questions="Q001,Q002,Q003", where=["status=valid"], exclude=[],
        )
        assert add_questions_action(request_standalone, conn_standalone).exit_code == 0

        monkeypatch.setenv("QUESTIONS_DATASET_PATH", dataset_path)
        monkeypatch.delenv("DEFAULT_QUESTIONS", raising=False)
        monkeypatch.delenv("QUESTIONS_STATUS_ADD", raising=False)
        monkeypatch.delenv("QUESTIONS_STATUS_EXCLUDE", raising=False)
        conn_composite = _make_conn()
        exp_composite = _make_experiment(conn_composite, "composite-exp")
        args_composite = _Args(add_questions=FORCE_SYSTEM_DEFAULT, where=["status=valid"], exclude=[])
        assert _create_question_snapshots(args_composite, exp_composite, conn_composite) == 0

        assert _snapshot_ids(conn_standalone, exp_standalone.experiment_id) == {"Q001", "Q003"}
        assert _snapshot_ids(conn_standalone, exp_standalone.experiment_id) == _snapshot_ids(conn_composite, exp_composite.experiment_id)

    def test_run_add_questions_adapter_equivalent_standalone_vs_composite_argv(self, dataset_path, monkeypatch):
        """The strongest form of equivalence: the SAME adapter
        (run_add_questions), called once with a 'standalone-shaped' argv
        and once with a 'composite-shaped' synthetic argv (mirroring
        exactly what bcllm.py's _execute_all_add_actions builds), must
        produce identical results — since it is, in fact, the exact same
        function either way."""
        from src.cli.bcllm_questions import run_add_questions

        conn_a = _make_conn()
        exp_a = _make_experiment(conn_a, "expA")
        code_a = run_add_questions(
            ["--experiment", "expA", "--source-file", dataset_path, "--add-questions", "system-default"],
            conn_a,
        )

        conn_b = _make_conn()
        exp_b = _make_experiment(conn_b, "expB")
        # Mirrors bcllm.py::_execute_all_add_actions's synthetic argv shape
        code_b = run_add_questions(
            ["bcllm", "--experiment", "expB", "--add-questions", "system-default", "--source-file", dataset_path][1:],
            conn_b,
        )

        assert code_a == code_b == 0
        assert _snapshot_ids(conn_a, exp_a.experiment_id) == _snapshot_ids(conn_b, exp_b.experiment_id)


# =============================================================================
# 7. No .env consultation for --where/--exclude in the standalone flow
# =============================================================================

class TestStandaloneNeverConsultsEnvForWhereExclude:
    def test_where_not_provided_ignores_questions_status_add_env(self, dataset_path, monkeypatch):
        """Unlike the composite (bootstrap) flow, the standalone flow has
        no QUESTIONS_STATUS_ADD .env fallback at all — confirm setting it
        has zero effect when --where is simply omitted ([])."""
        from src.cli.bcllm_questions import add_questions_action, AddQuestionsRequest

        monkeypatch.setenv("QUESTIONS_STATUS_ADD", "status=valid")  # would drop Q002 if consulted
        monkeypatch.setenv("QUESTIONS_STATUS_EXCLUDE", "status=annulled")

        conn = _make_conn()
        exp = _make_experiment(conn, "exp1")
        request = AddQuestionsRequest(
            experiment="exp1", source_file=dataset_path,
            add_questions="Q001,Q002,Q003", where=[], exclude=[],
        )

        result = add_questions_action(request, conn)

        assert result.exit_code == 0
        assert _snapshot_ids(conn, exp.experiment_id) == {"Q001", "Q002", "Q003"}


# =============================================================================
# 8. No persistent write before a usage error
# =============================================================================

class TestNoWriteBeforeUsageError:
    def test_forbidden_source_file_rejected_before_db_connection(self, monkeypatch, dataset_path):
        import sys
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "exp1",
            "--add-questions", "Q001", "--source-file", "system-default",
        ])

        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_forbidden_experiment_rejected_before_db_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "system-default", "--add-questions", "Q001",
        ])

        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_help_returns_0_without_unexpected_termination(self, monkeypatch):
        """--help must not raise SystemExit through main() — it's now
        caught by ParserExit and translated into a clean return value,
        same as any other parser-level outcome. Regression for the
        original, incomplete version of this fix (overriding only
        error(), not exit()) — see src/core/argv_utils.py."""
        import sys
        from src.cli import bcllm_questions

        monkeypatch.setattr(sys, "argv", ["bcllm_questions.py", "--help"])

        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 0
            mock_conn.assert_not_called()
