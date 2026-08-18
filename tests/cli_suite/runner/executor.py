"""Subprocess execution of bcllm.py commands.

Deliberately no shell=True (argv is always a real list, so arguments with
spaces survive intact) and no dependency on PATH — the real Python
interpreter (sys.executable) and the real repo's bcllm.py are invoked
directly. This is the seam that makes "cancel the whole run with Ctrl+C"
safe: each case is one child process, killed outright on interrupt rather
than trusting a shell to propagate the signal.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .workspace import REPO_ROOT

BCLLM_PY = REPO_ROOT / "bcllm.py"


@dataclass
class CommandResult:
    argv: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool


def run_bcllm(argv: list[str], cwd: Path, timeout: int) -> CommandResult:
    """Run one `python bcllm.py <argv>` invocation and capture everything.

    Never raises on the child's own failure (non-zero exit, traceback) —
    that is expected data for the caller to assert on. Only raises
    KeyboardInterrupt through unmodified, so Ctrl+C during a run still
    aborts immediately.
    """
    full_argv = [sys.executable, str(BCLLM_PY), *argv]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            full_argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        duration = time.monotonic() - started
        return CommandResult(
            argv=argv,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_s=duration,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as e:
        duration = time.monotonic() - started
        return CommandResult(
            argv=argv,
            exit_code=None,
            stdout=(e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""),
            stderr=(e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or ""),
            duration_s=duration,
            timed_out=True,
        )
    # KeyboardInterrupt intentionally NOT caught here: subprocess.run
    # propagates it after terminating the child, and run.py's top-level
    # loop is what turns that into SKIPPED for remaining cases.
