"""CLI argument parsing and profile definitions for the suite runner."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from .workspace import DEFAULT_WORKSPACE

PROFILES = (
    "smoke",
    "cli-unit",
    "contracts",
    "integration-mock",
    "regression",
    "full",
)


@dataclass
class SuiteConfig:
    profile: str
    yes: bool
    keep: bool
    enable_openrouter: bool
    enable_llamacpp: bool
    openrouter_model_id: str | None
    llamacpp_url: str | None
    compare_path: Path | None
    workspace: Path
    cases_dir: Path
    dataset_fixtures_dir: Path


def parse_args(argv: list[str] | None = None) -> SuiteConfig:
    parser = argparse.ArgumentParser(
        prog="tests/cli_suite/run.py",
        description="Runs the bcllm CLI automated test suite against a sandbox workspace.",
    )
    parser.add_argument("--profile", choices=PROFILES, default="smoke",
                         help="Which case profile to run (default: smoke).")
    parser.add_argument("--yes", action="store_true",
                         help="Don't ask for confirmation before wiping an existing workspace.")
    parser.add_argument("--keep", action="store_true",
                         help="Don't wipe the existing workspace at all; reuse it.")
    parser.add_argument("--openrouter", action="store_true",
                         help="Enable cases tagged requires: [openrouter] (needs a real "
                              "OPENROUTER_API_KEY and --openrouter-model-id).")
    parser.add_argument("--openrouter-model-id", default=None,
                         help="Cheap model id to use for --openrouter smoke cases. "
                              "No default is guessed — cases stay BLOCKED without it.")
    parser.add_argument("--llamacpp", action="store_true",
                         help="Enable cases tagged requires: [llamacpp].")
    parser.add_argument("--llamacpp-url", default=None,
                         help="Base URL of a running llama.cpp-compatible server. "
                              "Health-checked before use; cases stay BLOCKED if unreachable.")
    parser.add_argument("--compare", default=None, type=Path,
                         help="Path to a previous report.json to diff case states against.")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE, type=Path,
                         help="Sandbox workspace directory (default: <repo>/tests_workspace).")

    ns = parser.parse_args(argv)

    here = Path(__file__).resolve().parent.parent  # tests/cli_suite/

    return SuiteConfig(
        profile=ns.profile,
        yes=ns.yes,
        keep=ns.keep,
        enable_openrouter=ns.openrouter,
        enable_llamacpp=ns.llamacpp,
        openrouter_model_id=ns.openrouter_model_id,
        llamacpp_url=ns.llamacpp_url,
        compare_path=ns.compare,
        workspace=ns.workspace,
        cases_dir=here / "cases",
        dataset_fixtures_dir=here / "fixtures" / "datasets",
    )
