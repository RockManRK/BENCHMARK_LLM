import re
from pathlib import Path

from setuptools import setup, find_packages

# The distributed `bcllm` CLI package's true runtime dependencies — a
# curated subset of requirements.in (which also lists test-only tools:
# pytest, pytest-asyncio, pytest-mock, responses, PyYAML — those must
# NEVER end up in install_requires, or `pip install -e .` would pull test
# tooling into every install). This is the ONLY place that subset is
# named; the version constraint for each is never re-typed here — it is
# read directly out of requirements.in below, so a bound change there
# (e.g. bumping typer's upper bound) never needs a second manual edit.
_RUNTIME_PACKAGE_NAMES = {
    "httpx", "pydantic", "pydantic-settings", "pillow", "python-dotenv",
    "rich", "typer",
}


def _read_runtime_requirements() -> list[str]:
    """Derive install_requires from requirements.in — the single
    canonical source of direct dependencies (2026-08-20 dependency
    hygiene pass, docs/status/known-issues.md). Filters to
    _RUNTIME_PACKAGE_NAMES only; requirements.in's test-only entries
    (pytest, PyYAML, ...) are intentionally excluded here."""
    req_path = Path(__file__).parent / "requirements.in"
    result = []
    for line in req_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if match and match.group(1).lower() in _RUNTIME_PACKAGE_NAMES:
            result.append(line)
    return result


setup(
    name="benchmark_llm",
    version="2.0.0",
    packages=find_packages(),
    # bcllm.py (the real CLI entry point — see QWEN.md/CLAUDE.md) lives at
    # the repo root, not inside a package `find_packages()` would pick up
    # on its own.
    py_modules=["bcllm"],
    entry_points={
        "console_scripts": [
            # Was "src.cli.bcllm_main:main" until 2026-08-18 — that
            # main() requires a `mode: Mode` positional argument
            # (src/cli/bcllm_main.py) that a console_script wrapper never
            # supplies, so the installed `bcllm` command raised
            # TypeError on every invocation. Was "bcllm:main" until the
            # Unit-of-Work checkpoint moved .env loading out of module
            # import time and into bcllm.py::cli_main() (called only from
            # a real entry point, never from a bare import) — pointing
            # here at plain `main()` would have silently skipped .env
            # loading entirely for the installed console script.
            # bcllm.py::cli_main() is the one place both real entry
            # points (this, and `python bcllm.py`'s own
            # `if __name__ == "__main__"` block) share. See
            # docs/status/composite-flow-unit-of-work-design.md and
            # docs/status/known-issues.md.
            "bcllm=bcllm:cli_main",
        ],
    },
    install_requires=_read_runtime_requirements(),
    # Python >=3.14 required (user decision, 2026-08-21): the project
    # prioritizes its real, currently-running environment (3.14.2) over
    # backward compatibility with 3.10-3.13 — no version matrix is tested
    # or supported. See docs/status/known-issues.md.
    python_requires=">=3.14",
)
