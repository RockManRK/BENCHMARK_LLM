"""Tests for src.cli.database.get_database_path DATABASE_PATH override.

Verifies:
- Without DATABASE_PATH set, the historical default (./data/bcllm.db
  relative to the project root) is preserved unchanged.
- With DATABASE_PATH set (relative or absolute), the CLI resolves to that
  path instead, and creates the parent directory if missing.
- This is the seam the CLI test suite uses to redirect the database at an
  isolated sandbox without copying source code (see docs/tests/).
"""

import os
from pathlib import Path

import pytest

from src.cli.database import get_database_path


@pytest.fixture(autouse=True)
def _clean_database_path_env(monkeypatch):
    """Ensure DATABASE_PATH never leaks between tests."""
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    yield


class TestGetDatabasePathDefault:
    def test_default_path_unchanged_when_env_unset(self):
        path = get_database_path()

        assert path.name == "bcllm.db"
        assert path.parent.name == "data"
        # Anchored to the project root, not the CWD.
        project_root = Path(__file__).parent.parent.parent.parent
        assert path == project_root / "data" / "bcllm.db"


class TestGetDatabasePathOverride:
    def test_relative_override_resolved_against_project_root(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DATABASE_PATH", "./_clitest_scratch/sandbox.db")

        path = get_database_path()

        project_root = Path(__file__).parent.parent.parent.parent
        assert path == project_root / "_clitest_scratch" / "sandbox.db"
        assert path.parent.is_dir()  # created

        # Cleanup: don't leave scratch dirs behind in the real repo.
        path.parent.rmdir()

    def test_absolute_override_used_verbatim(self, tmp_path, monkeypatch):
        target = tmp_path / "nested" / "clitest.db"
        monkeypatch.setenv("DATABASE_PATH", str(target))

        path = get_database_path()

        assert path == target
        assert path.parent.is_dir()  # created

    def test_override_creates_missing_parent_directory(self, tmp_path, monkeypatch):
        target = tmp_path / "does" / "not" / "exist" / "bcllm.db"
        monkeypatch.setenv("DATABASE_PATH", str(target))
        assert not target.parent.exists()

        path = get_database_path()

        assert path == target
        assert target.parent.is_dir()

    def test_override_is_isolated_from_default(self, tmp_path, monkeypatch):
        """Sandbox DB path must never equal the production default."""
        target = tmp_path / "sandbox.db"
        monkeypatch.setenv("DATABASE_PATH", str(target))

        path = get_database_path()

        project_root = Path(__file__).parent.parent.parent.parent
        assert path != project_root / "data" / "bcllm.db"
