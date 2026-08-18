"""Sandbox workspace lifecycle for the CLI test suite.

Design (see plan Context / Fase 1):
- The CLI is run against the REAL bcllm.py + src/ tree (never a copy).
  Isolation comes from Seam (a) — src/cli/database.py honors the
  DATABASE_PATH environment variable — plus per-case working directories
  that carry their own generated .env.
- One shared database and one shared log file for the whole suite run
  (tests_workspace/data/bcllm_test.db, tests_workspace/logs/benchmark.log),
  matching the "single auditable DB/log" requirement, EXCEPT for the
  handful of cases that declare fixture.database: fresh|absent|corrupt,
  which get their own scratch file so "empty/corrupt database" scenarios
  are still testable.
- The workspace is wiped at the start of a run (with confirmation, unless
  --yes) and left on disk afterward for manual inspection. The runner never
  writes outside its own root — enforced by _assert_inside().
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from . import env_presets
from .case import Case

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE = REPO_ROOT / "tests_workspace"


class WorkspaceSafetyError(Exception):
    """Raised if an operation would touch anything outside the sandbox."""


@dataclass
class CaseEnv:
    """Resolved per-case execution environment."""

    cwd: Path
    db_path: Path
    env_file: Path


class Workspace:
    def __init__(self, root: Path = DEFAULT_WORKSPACE, stub_base_url: str = "") -> None:
        self.root = root.resolve()
        self.stub_base_url = stub_base_url
        self._assert_inside(self.root)

    # -- paths -----------------------------------------------------------

    @property
    def db_path(self) -> Path:
        return self.root / "data" / "bcllm_test.db"

    @property
    def log_path(self) -> Path:
        return self.root / "logs" / "benchmark.log"

    @property
    def scratch_dir(self) -> Path:
        return self.root / "scratch"

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def case_env_dir(self) -> Path:
        return self.root / "case_env"

    @property
    def report_md_path(self) -> Path:
        return self.root / "report.md"

    @property
    def report_json_path(self) -> Path:
        return self.root / "report.json"

    # -- safety ------------------------------------------------------------

    def _assert_inside(self, path: Path) -> None:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            if resolved != self.root:
                raise WorkspaceSafetyError(
                    f"Refusing to touch path outside the sandbox: {resolved} (root: {self.root})"
                )

    def _assert_never_production_db(self, path: Path) -> None:
        production_db = (REPO_ROOT / "data" / "bcllm.db").resolve()
        if path.resolve() == production_db:
            raise WorkspaceSafetyError(
                "Refusing to point a test case at the production database "
                f"({production_db}). This must never happen."
            )

    # -- lifecycle ---------------------------------------------------------

    def exists(self) -> bool:
        return self.root.exists()

    def wipe(self) -> None:
        """Delete the workspace, retrying through the classic Windows
        failure mode where a synced folder (OneDrive, in this repo's case)
        transiently locks a file or leaves it read-only right after a
        previous run wrote it — a plain shutil.rmtree() intermittently
        raises PermissionError here even though nothing is actually still
        open."""
        self._assert_inside(self.root)
        if not self.root.exists():
            return

        def _on_error(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except OSError:
                raise

        last_error: OSError | None = None
        for attempt in range(5):
            try:
                shutil.rmtree(self.root, onexc=_on_error)
                return
            except OSError as e:
                last_error = e
                time.sleep(0.5 * (attempt + 1))

        raise WorkspaceSafetyError(
            f"Could not wipe workspace {self.root} after retries "
            f"(likely a sync client holding a lock): {last_error}"
        )

    def create(self) -> None:
        for d in (self.root, self.root / "data", self.root / "logs",
                  self.scratch_dir, self.artifacts_dir, self.case_env_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- per-case environment ------------------------------------------

    def prepare_case_env(self, case: Case, dataset_fixtures_dir: Path) -> CaseEnv:
        """Create the case's working directory and .env file, and resolve
        which database file it should use."""
        case_dir = self.case_env_dir / case.namespace
        case_dir.mkdir(parents=True, exist_ok=True)
        self._assert_inside(case_dir)

        db_path = self._resolve_case_db_path(case)
        self._assert_inside(db_path) if case.fixture.database != "absent" else None
        self._assert_never_production_db(db_path)

        dataset_path = dataset_fixtures_dir / f"{case.fixture.dataset}.json"

        env_content = env_presets.render(
            case.fixture.env,
            base_url=self.stub_base_url,
            dataset_path=str(dataset_path),
        )
        env_content += f"DATABASE_PATH={db_path}\n"
        env_content += f"LOG_FILE_PATH={self.log_path}\n"

        if "openrouter" in case.requires:
            # Let the real OPENROUTER_API_KEY (system env var) pass through
            # instead of the fake key baked into the preset — this case is
            # meant to hit the real API.
            env_content = "\n".join(
                line for line in env_content.splitlines()
                if not line.startswith("OPENROUTER_API_KEY=")
            ) + "\n"

        env_file = case_dir / ".env"
        env_file.write_text(env_content, encoding="utf-8")

        return CaseEnv(cwd=case_dir, db_path=db_path, env_file=env_file)

    def _resolve_case_db_path(self, case: Case) -> Path:
        mode = case.fixture.database
        if mode == "shared":
            return self.db_path
        if mode == "fresh":
            return self.scratch_dir / f"{case.namespace}_fresh.db"
        if mode == "absent":
            # A path that must not exist yet; the case's whole point is to
            # exercise the CLI's own "database doesn't exist -> creates it"
            # behavior. Never pre-create it.
            p = self.scratch_dir / f"{case.namespace}_absent.db"
            if p.exists():
                p.unlink()
            return p
        if mode == "corrupt":
            p = self.scratch_dir / f"{case.namespace}_corrupt.db"
            p.write_bytes(b"not a sqlite database, deliberately corrupt")
            return p
        raise ValueError(f"Unknown fixture.database mode: {mode!r}")

    # -- inspection (used by the runner and by dbcheck.py) -----------------

    def connect_readonly(self, db_path: Path | None = None) -> sqlite3.Connection:
        target = db_path or self.db_path
        self._assert_inside(target)
        uri = f"file:{target.as_posix()}?mode=ro"
        return sqlite3.connect(uri, uri=True)
