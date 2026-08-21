"""Regression tests for bcllm_provider.py's main() — same class of
coverage as test_bcllm_model_same_action_same_path.py/
test_bcllm_run_same_action_same_path.py's sibling files: help returns 0
without opening a DB connection, and a usage error (FORBIDDEN
--experiment system-default) never opens a DB connection either.
bcllm_provider.py has no composite-flow counterpart (--resolve-providers
is not in ADD_ACTION_FLAGS), so there is no standalone/composite
equivalence to prove here — this module has exactly one entry point.

Isolation: mocks get_database_connection directly; no real .env/DB touched.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from src.core.mode import Mode


class TestHelpReturnsZeroWithoutUnexpectedTermination:
    def test_help_returns_0_no_db_connection(self, monkeypatch):
        from src.cli import bcllm_provider

        monkeypatch.setattr(sys, "argv", ["bcllm_provider.py", "--help"])

        with patch("src.cli.bcllm_provider.get_database_connection") as mock_conn:
            exit_code = bcllm_provider.main(Mode.MODIFY)
            assert exit_code == 0
            mock_conn.assert_not_called()


class TestNoWriteBeforeUsageError:
    def test_forbidden_experiment_system_default_rejected_before_db_connection(self, monkeypatch):
        from src.cli import bcllm_provider

        monkeypatch.setattr(sys, "argv", [
            "bcllm_provider.py", "--experiment", "system-default", "--resolve-providers",
        ])

        with patch("src.cli.bcllm_provider.get_database_connection") as mock_conn:
            exit_code = bcllm_provider.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()

    def test_missing_experiment_rejected_before_db_connection(self, monkeypatch):
        from src.cli import bcllm_provider

        monkeypatch.setattr(sys, "argv", ["bcllm_provider.py", "--resolve-providers"])

        with patch("src.cli.bcllm_provider.get_database_connection") as mock_conn:
            exit_code = bcllm_provider.main(Mode.MODIFY)
            assert exit_code == 2
            mock_conn.assert_not_called()
