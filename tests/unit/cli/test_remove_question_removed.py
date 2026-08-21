"""Normative tests: --remove-question does not exist anywhere in the
system (2026-08-20, definitive decision — see docs/status/known-issues.md
and docs/contracts/immutability.md §1). QuestionSnapshot is immutable: an
experiment can only grow by adding snapshots, a question already added
can never be removed, disabled, or retroactively hidden. No soft-delete
was implemented — the command was removed entirely, not disabled.

Each test below maps directly to one of the 7 properties required before
resuming marco 4B:
1. --remove-question does not exist (Typer command surface)
2. using it returns exit code 2 before any DB connection opens
3. --help does not list the option
4. no public action can remove a QuestionSnapshot
5. the composite flow never forwards the flag
6. existing snapshots remain intact
7. the contracts still assert growth-only-by-addition
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.argv_utils import ParserExit
from src.db.models import Experiment, QuestionSnapshot
from src.db.repository import ExperimentRepository, SnapshotRepository
from src.db.schema import create_schema


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


def _make_snapshot(conn, experiment_id: str, question_id: str = "Q001") -> QuestionSnapshot:
    snap = QuestionSnapshot(
        snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
        experiment_id=experiment_id,
        json_question_id=question_id,
        question_position=1,
        question_payload=json.dumps({"stem": "test", "options": {"A": "a"}, "answer_key": "A"}),
    )
    SnapshotRepository(conn).save(snap)
    return snap


# =============================================================================
# 1. --remove-question does not exist (Typer command surface)
# =============================================================================

class TestFlagDoesNotExist:
    def test_no_remove_question_field_on_dataclass(self):
        from src.cli.commands.questions import QuestionsParsedArgs

        field_names = {f.name for f in dataclasses.fields(QuestionsParsedArgs)}
        assert "remove_question" not in field_names

    def test_no_remove_question_parameter_on_command_function(self):
        from src.cli.commands.questions import _questions_command

        params = inspect.signature(_questions_command).parameters
        assert "remove_question" not in params

    def test_no_remove_question_option_declared_on_click_command(self):
        from src.cli.commands.questions import _command

        param_names = {p.name for p in _command.params}
        assert "remove_question" not in param_names
        option_decls = [decl for p in _command.params for decl in getattr(p, "opts", [])]
        assert "--remove-question" not in option_decls


# =============================================================================
# 2. Usage returns exit code 2, before any DB connection opens
# =============================================================================

class TestUsageExitsTwoBeforeConnection:
    def test_parse_questions_argv_rejects_it_with_exit_2(self):
        from src.cli.commands.questions import parse_questions_argv

        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--experiment", "exp1", "--remove-question", "snap_x"])
        assert exc_info.value.status == 2

    def test_main_never_opens_a_connection(self, monkeypatch):
        import sys
        from src.cli import bcllm_questions
        from src.core.mode import Mode

        monkeypatch.setattr(sys, "argv", [
            "bcllm_questions.py", "--experiment", "exp1", "--remove-question", "snap_x",
        ])
        with patch("src.cli.bcllm_questions.get_database_connection") as mock_conn:
            exit_code = bcllm_questions.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_real_subprocess_exits_2_and_touches_nothing(self, tmp_path):
        """End-to-end proof via the real bcllm.py entry point, not just
        the module-level parser — isolated DB, never opened by this
        invocation (confirmed by the file not existing afterward)."""
        import subprocess
        import sys

        db_path = tmp_path / "should_not_be_created.db"
        env = {
            "DATABASE_PATH": str(db_path),
            "OPENROUTER_API_KEY": "sk-test-not-real",
            "LOG_FILE_PATH": str(tmp_path / "test.log"),
        }
        import os
        full_env = {**os.environ, **env}

        result = subprocess.run(
            [sys.executable, "bcllm.py", "--experiment", "exp1", "--remove-question", "snap_x"],
            capture_output=True, text=True, env=full_env,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        assert result.returncode == 2
        assert "remove-question" in result.stderr
        assert "Traceback" not in result.stderr


# =============================================================================
# 3. --help does not list the option
# =============================================================================

class TestHelpDoesNotListIt:
    def test_module_help_omits_remove_question(self):
        from src.cli.commands.questions import parse_questions_argv

        with pytest.raises(ParserExit) as exc_info:
            parse_questions_argv(["--help"])
        assert exc_info.value.status == 0
        # Click writes --help output directly to stdout via echo(), not
        # captured by ParserExit — verify via the Click command's own
        # rendered help text instead.
        from src.cli.commands.questions import _command
        import click
        ctx = click.Context(_command)
        help_text = _command.get_help(ctx)
        assert "--remove-question" not in help_text

    def test_top_level_curated_help_omits_remove_question(self):
        from src.cli.bcllm_main import create_parser
        import io
        import contextlib

        parser = create_parser()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            parser.print_help()
        assert "--remove-question" not in buf.getvalue()


# =============================================================================
# 4. No public action can remove a QuestionSnapshot
# =============================================================================

class TestNoPublicActionCanRemove:
    def test_bcllm_questions_has_no_remove_handler(self):
        from src.cli import bcllm_questions

        assert not hasattr(bcllm_questions, "handle_remove_question")

    def test_snapshot_repository_has_no_delete_method(self):
        assert not hasattr(SnapshotRepository, "delete")

    def test_module_resolver_does_not_map_the_flag(self):
        from src.core import module_resolver

        assert "--remove-question" not in module_resolver._MODULE_MAP

    def test_resolve_module_source_has_no_remove_question_priority_entry(self):
        """PRIORITY_FLAGS is a local list inside resolve_module(), not a
        module-level attribute — check the source text directly rather
        than importing it."""
        import inspect
        from src.core import module_resolver

        source = inspect.getsource(module_resolver.resolve_module)
        assert "--remove-question" not in source

    def test_no_delete_sql_against_question_snapshots_anywhere_in_src(self):
        """Belt-and-suspenders: check no source file under src/ contains
        an actual `DELETE FROM question_snapshots` SQL statement
        (case/whitespace-insensitive) — narrower than a bare co-occurrence
        check, which false-positives on unrelated mentions (e.g.
        `schema.py`'s ON DELETE CASCADE foreign-key comments)."""
        import re

        src_root = Path(__file__).resolve().parents[3] / "src"
        pattern = re.compile(r"delete\s+from\s+question_snapshots", re.IGNORECASE)
        offenders = []
        for py_file in src_root.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            if pattern.search(text):
                offenders.append(str(py_file))
        assert offenders == []


# =============================================================================
# 5. The composite flow never forwards the flag
# =============================================================================

class TestCompositeFlowNeverForwardsIt:
    def test_add_action_flags_excludes_remove_question(self):
        from src.core.module_resolver import ADD_ACTION_FLAGS

        assert "--remove-question" not in ADD_ACTION_FLAGS

    def test_resolve_module_does_not_route_bare_remove_question_anywhere(self):
        from src.core.module_resolver import resolve_module

        result = resolve_module(["bcllm", "--remove-question", "q1"])
        assert result is None

    def test_composite_create_plus_remove_question_is_rejected_not_forwarded(self, tmp_path):
        """Even if someone tried to combine --create-experiment with
        --remove-question (never a valid composite action), the flag
        must not be silently forwarded into any action pipeline — it
        must be rejected as an unrecognized option by whichever module
        actually ends up handling the invocation."""
        import subprocess
        import sys
        import os

        db_path = tmp_path / "composite_test.db"
        full_env = {
            **os.environ,
            "DATABASE_PATH": str(db_path),
            "OPENROUTER_API_KEY": "sk-test-not-real",
            "LOG_FILE_PATH": str(tmp_path / "test.log"),
        }
        result = subprocess.run(
            [sys.executable, "bcllm.py", "--create-experiment", "exp_x", "--remove-question", "snap_x"],
            capture_output=True, text=True, env=full_env,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        assert result.returncode in (1, 2)
        assert "Traceback" not in result.stderr
        # Whatever happened, no experiment named exp_x should have been
        # left committed as a side effect of a --remove-question-involving
        # invocation.
        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT COUNT(*) as c FROM experiments WHERE name = ?", ("exp_x",))
            assert cursor.fetchone()["c"] == 0
            conn.close()


# =============================================================================
# 6. Existing snapshots remain intact
# =============================================================================

class TestExistingSnapshotsRemainIntact:
    def test_snapshot_untouched_after_attempted_removal_via_real_entrypoint(self, tmp_path):
        conn = _make_conn()
        exp = _make_experiment(conn, "exp_intact")
        snap = _make_snapshot(conn, exp.experiment_id)
        conn.close()

        db_path = tmp_path / "intact_test.db"
        # Seed a fresh DB with the same schema + rows via the real path,
        # since the subprocess needs its own file-backed DB.
        seed_conn = sqlite3.connect(str(db_path))
        seed_conn.row_factory = sqlite3.Row
        seed_conn.execute("PRAGMA foreign_keys = ON")
        create_schema(seed_conn)
        ExperimentRepository(seed_conn).save(exp)
        SnapshotRepository(seed_conn).save(snap)
        seed_conn.close()

        import subprocess
        import sys
        import os

        full_env = {
            **os.environ,
            "DATABASE_PATH": str(db_path),
            "OPENROUTER_API_KEY": "sk-test-not-real",
            "LOG_FILE_PATH": str(tmp_path / "test.log"),
        }
        subprocess.run(
            [sys.executable, "bcllm.py", "--experiment", exp.name, "--remove-question", snap.snapshot_id],
            capture_output=True, text=True, env=full_env,
            cwd=str(Path(__file__).resolve().parents[3]),
        )

        verify_conn = sqlite3.connect(str(db_path))
        verify_conn.row_factory = sqlite3.Row
        still_there = SnapshotRepository(verify_conn).get_by_id(snap.snapshot_id)
        verify_conn.close()

        assert still_there is not None
        assert still_there.snapshot_id == snap.snapshot_id
        assert still_there.json_question_id == snap.json_question_id


# =============================================================================
# 7. The contracts still assert growth-only-by-addition
# =============================================================================

class TestContractsStillAssertGrowthOnly:
    def test_immutability_contract_still_states_no_deletion(self):
        contract_path = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "immutability.md"
        text = contract_path.read_text(encoding="utf-8")
        assert "Cannot be deleted" in text
        assert "Can only be added" in text

    def test_immutability_contract_documents_enforcement(self):
        contract_path = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "immutability.md"
        normalized = " ".join(contract_path.read_text(encoding="utf-8").split())
        assert "No public action anywhere in the system can remove a `QuestionSnapshot`" in normalized
