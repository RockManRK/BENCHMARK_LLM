"""Regression tests for bcllm_execute.py's main() — same class of
coverage as the sibling *_same_action_same_path.py files for the other
marco 4B/4C modules: help returns 0 without opening a DB connection, and
usage errors (FORBIDDEN --experiment system-default, malformed
--questions spec) never open a DB connection either. bcllm_execute.py
has no composite-flow counterpart (--execute is not in ADD_ACTION_FLAGS),
so there is no standalone/composite equivalence to prove here.

Isolation: mocks get_database_connection directly; no real .env/DB touched.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from src.core.mode import Mode


class TestHelpReturnsZeroWithoutUnexpectedTermination:
    def test_help_returns_0_no_db_connection(self, monkeypatch):
        from src.cli import bcllm_execute

        monkeypatch.setattr(sys, "argv", ["bcllm_execute.py", "--help"])

        with patch("src.cli.bcllm_execute.get_database_connection") as mock_conn:
            exit_code = bcllm_execute.main(Mode.EXECUTE)
            assert exit_code == 0
            mock_conn.assert_not_called()


class TestNoWriteBeforeUsageError:
    def test_forbidden_experiment_system_default_rejected_before_db_connection(self, monkeypatch):
        from src.cli import bcllm_execute

        monkeypatch.setattr(sys, "argv", [
            "bcllm_execute.py", "--experiment", "system-default", "--execute",
        ])

        with patch("src.cli.bcllm_execute.get_database_connection") as mock_conn:
            exit_code = bcllm_execute.main(Mode.EXECUTE)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_malformed_questions_spec_rejected_before_db_connection(self, monkeypatch):
        from src.cli import bcllm_execute

        monkeypatch.setattr(sys, "argv", [
            "bcllm_execute.py", "--experiment", "exp1", "--execute", "--questions", "0",
        ])

        with patch("src.cli.bcllm_execute.get_database_connection") as mock_conn:
            exit_code = bcllm_execute.main(Mode.EXECUTE)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_malformed_models_spec_rejected_before_db_connection(self, monkeypatch):
        from src.cli import bcllm_execute

        monkeypatch.setattr(sys, "argv", [
            "bcllm_execute.py", "--experiment", "exp1", "--execute", "--models", "var-a,,var-b",
        ])

        with patch("src.cli.bcllm_execute.get_database_connection") as mock_conn:
            exit_code = bcllm_execute.main(Mode.EXECUTE)
            assert exit_code == 2
            mock_conn.assert_not_called()
