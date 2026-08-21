"""Tests for KeyboardInterrupt handling and COMMAND_INTERRUPTED logging
(Checkpoint C, closes the crash-safety gap found in the investigation:
only bcllm_execute.py previously caught Ctrl-C; the other 8 CLI modules
let it propagate as a raw traceback).

`TestBcllmReviewKeyboardInterrupt` covers the Checkpoint C revalidation
fix (2026-08-20): `bcllm_review.py`'s `--review-experiment`/`--review-all`
handlers previously caught KeyboardInterrupt but returned exit code 0
(not 130), used builtin `print()` with literal (unrendered) Rich markup
on stdout (not stderr), and emitted no structured event at all — see
`docs/status/known-issues.md`.

Isolation: DATABASE_PATH/LOG_FILE_PATH redirected to tmp_path, dotenv
neutralized — see tests/unit/cli/test_composite_flow_rollback.py's
_isolated_env docstring for why this exact pattern is needed.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "kbi_test.db"))
    monkeypatch.setenv("LOG_FILE_PATH", str(tmp_path / "test.log"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("QUESTIONS_DATASET_PATH", raising=False)
    yield


def _read_jsonl(tmp_path):
    jsonl_path = tmp_path / "test.jsonl"
    if not jsonl_path.exists():
        return []
    return [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestBcllmMainKeyboardInterrupt:
    def test_route_to_v2_interrupt_returns_130(self, tmp_path, monkeypatch):
        import bcllm

        monkeypatch.setattr("sys.argv", ["bcllm", "--list-experiments"])

        with patch("bcllm.route_to_v2", side_effect=KeyboardInterrupt):
            exit_code = bcllm.main()

        assert exit_code == 130

    def test_interrupt_emits_command_interrupted_event(self, tmp_path, monkeypatch):
        import bcllm

        monkeypatch.setattr("sys.argv", ["bcllm", "--list-experiments"])

        with patch("bcllm.route_to_v2", side_effect=KeyboardInterrupt):
            bcllm.main()

        events = _read_jsonl(tmp_path)
        interrupted = [e for e in events if e["event_name"] == "command_interrupted"]
        assert len(interrupted) == 1

    def test_interrupted_event_carries_same_operation_id_as_command_start(self, tmp_path, monkeypatch):
        import bcllm

        monkeypatch.setattr("sys.argv", ["bcllm", "--list-experiments"])

        with patch("bcllm.route_to_v2", side_effect=KeyboardInterrupt):
            bcllm.main()

        events = _read_jsonl(tmp_path)
        starts = [e for e in events if e["event_name"] == "command_start"]
        interrupted = [e for e in events if e["event_name"] == "command_interrupted"]
        assert len(starts) == 1
        assert starts[0]["operation_id"] == interrupted[0]["operation_id"]

    def test_no_command_end_emitted_when_interrupted(self, tmp_path, monkeypatch):
        """COMMAND_END represents a normal, non-interrupted completion —
        an interrupted invocation must not also emit COMMAND_END."""
        import bcllm

        monkeypatch.setattr("sys.argv", ["bcllm", "--list-experiments"])

        with patch("bcllm.route_to_v2", side_effect=KeyboardInterrupt):
            bcllm.main()

        events = _read_jsonl(tmp_path)
        ends = [e for e in events if e["event_name"] == "command_end"]
        assert len(ends) == 0


class TestBcllmExecuteKeyboardInterrupt:
    """bcllm_execute.main() relies on its caller (bcllm.py's main()) having
    already called setup_logging() — mirror that explicitly here so the
    JSONL sink points at this test's own tmp_path, not whatever the
    process-wide `benchmark_llm.jsonl` logger last had configured."""

    def _setup_logging_for(self, tmp_path):
        from pathlib import Path
        from src.utils.logging_config import setup_logging, LoggingConfig

        setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))

    def test_handle_execute_interrupt_returns_130(self, tmp_path, monkeypatch):
        from src.cli import bcllm_execute
        from src.core.mode import Mode

        self._setup_logging_for(tmp_path)
        monkeypatch.setattr("sys.argv", ["bcllm", "--experiment", "x", "--execute"])

        with patch.object(bcllm_execute, "handle_execute", side_effect=KeyboardInterrupt):
            exit_code = bcllm_execute.main(Mode.EXECUTE, operation_id="op_test_kbi")

        assert exit_code == 130

    def test_handle_execute_interrupt_emits_command_interrupted_with_operation_id(self, tmp_path, monkeypatch):
        from src.cli import bcllm_execute
        from src.core.mode import Mode

        self._setup_logging_for(tmp_path)
        monkeypatch.setattr("sys.argv", ["bcllm", "--experiment", "x", "--execute"])

        with patch.object(bcllm_execute, "handle_execute", side_effect=KeyboardInterrupt):
            bcllm_execute.main(Mode.EXECUTE, operation_id="op_test_kbi")

        events = _read_jsonl(tmp_path)
        interrupted = [e for e in events if e["event_name"] == "command_interrupted"]
        assert len(interrupted) == 1
        assert interrupted[0]["operation_id"] == "op_test_kbi"
        assert interrupted[0]["command"] == "execute"


class TestBcllmReviewKeyboardInterrupt:
    """--review-experiment and --review-all: each has its own handler
    (`handle_review_experiment`/`handle_review_all`) that catches
    KeyboardInterrupt around the ReviewUI call directly, rather than at
    `main()` level like bcllm_execute.py — the fix targets both."""

    def _setup_logging_for(self, tmp_path):
        from pathlib import Path
        from src.utils.logging_config import setup_logging, LoggingConfig

        setup_logging(LoggingConfig(log_file_path=Path(tmp_path / "test.log")))

    def _fake_conn(self):
        from unittest.mock import MagicMock
        return MagicMock()

    # --- --review-experiment ---

    def test_review_experiment_interrupt_returns_130(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment="exp_x", review_all=False)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            exit_code = bcllm_review.handle_review_experiment(args, conn, operation_id="op_rev1")

        assert exit_code == 130

    def test_review_experiment_interrupt_stderr_has_message_no_rich_markup(self, tmp_path, monkeypatch, capsys):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment="exp_x", review_all=False)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_experiment(args, conn, operation_id="op_rev1")

        captured = capsys.readouterr()
        assert "interrupted" in captured.err.lower()
        assert "[yellow]" not in captured.err
        assert "[/yellow]" not in captured.err

    def test_review_experiment_interrupt_stdout_has_no_error_message(self, tmp_path, monkeypatch, capsys):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment="exp_x", review_all=False)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_experiment(args, conn, operation_id="op_rev1")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_review_experiment_interrupt_emits_command_interrupted_with_operation_id(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment="exp_x", review_all=False)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_experiment(args, conn, operation_id="op_rev1")

        events = _read_jsonl(tmp_path)
        interrupted = [e for e in events if e["event_name"] == "command_interrupted"]
        assert len(interrupted) == 1
        assert interrupted[0]["operation_id"] == "op_rev1"
        assert interrupted[0]["command"] == "review_experiment"

    def test_review_experiment_interrupt_no_traceback_raised(self, tmp_path, monkeypatch):
        """The handler must swallow KeyboardInterrupt itself — it must
        never propagate out as an unhandled exception/traceback."""
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment="exp_x", review_all=False)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            # No pytest.raises here — a re-raised KeyboardInterrupt would
            # fail this test by propagating out of the call below.
            bcllm_review.handle_review_experiment(args, conn, operation_id="op_rev1")

    def test_review_experiment_interrupt_via_main_closes_connection(self, tmp_path, monkeypatch):
        """Exercise the real main() -> handle_review_experiment() path so
        the finally: conn.close() in main() is genuinely under test."""
        from src.cli import bcllm_review
        from src.core.mode import Mode

        self._setup_logging_for(tmp_path)
        monkeypatch.setattr("sys.argv", ["bcllm", "--review-experiment", "exp_x"])
        fake_conn = self._fake_conn()
        monkeypatch.setattr(bcllm_review, "get_database_connection", lambda: fake_conn)

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_by_experiment.side_effect = KeyboardInterrupt
            exit_code = bcllm_review.main(Mode.INVALID, operation_id="op_rev1")

        assert exit_code == 130
        fake_conn.close.assert_called_once()

    # --- --review-all ---

    def test_review_all_interrupt_returns_130(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            exit_code = bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

        assert exit_code == 130

    def test_review_all_interrupt_stderr_has_message_no_rich_markup(self, tmp_path, monkeypatch, capsys):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

        captured = capsys.readouterr()
        assert "interrupted" in captured.err.lower()
        assert "[yellow]" not in captured.err
        assert "[/yellow]" not in captured.err

    def test_review_all_interrupt_stdout_has_no_error_message(self, tmp_path, monkeypatch, capsys):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_review_all_interrupt_emits_command_interrupted_with_operation_id(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

        events = _read_jsonl(tmp_path)
        interrupted = [e for e in events if e["event_name"] == "command_interrupted"]
        assert len(interrupted) == 1
        assert interrupted[0]["operation_id"] == "op_rev2"
        assert interrupted[0]["command"] == "review_all"

    def test_review_all_interrupt_no_traceback_raised(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

    def test_review_all_interrupt_via_main_closes_connection(self, tmp_path, monkeypatch):
        from src.cli import bcllm_review
        from src.core.mode import Mode

        self._setup_logging_for(tmp_path)
        monkeypatch.setattr("sys.argv", ["bcllm", "--review-all"])
        fake_conn = self._fake_conn()
        monkeypatch.setattr(bcllm_review, "get_database_connection", lambda: fake_conn)

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            exit_code = bcllm_review.main(Mode.INVALID, operation_id="op_rev2")

        assert exit_code == 130
        fake_conn.close.assert_called_once()

    def test_review_all_interrupt_no_new_writes_via_connection(self, tmp_path, monkeypatch):
        """The interrupt handler itself must not trigger any new DB write
        — no commit/execute call on the connection from the handler path
        (ReviewUI's own incremental saves, if any occurred before the
        interrupt, are a ReviewUI concern, not this handler's)."""
        from src.cli import bcllm_review

        self._setup_logging_for(tmp_path)
        args = argparse_namespace(review_experiment=None, review_all=True)
        conn = self._fake_conn()

        with patch.object(bcllm_review, "ReviewUI") as MockUI:
            MockUI.return_value.start_review_all.side_effect = KeyboardInterrupt
            bcllm_review.handle_review_all(args, conn, operation_id="op_rev2")

        conn.commit.assert_not_called()
        conn.execute.assert_not_called()


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)
