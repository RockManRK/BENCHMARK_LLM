"""Cross-checks src/cli/*.py argparse flags against the flags exercised by
the case YAML files.

This is what makes "add a command, remove a command" cheap to keep in sync:
the report tells you directly which real CLI flags have no case yet, and
which case flags no longer exist in the CLI (drift in either direction),
plus flags that are declared but never read by any src/ code (dead flags —
already known: --output on 4 parsers, see docs/status/known-issues.md
candidates and the exploration that fed this plan).
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass

from .case import Case
from .workspace import REPO_ROOT

# The suite runs bcllm.py as a subprocess (see executor.py) and never
# imports src/ into its own process for that — this is the one exception,
# introspecting argparse parsers to build the flag-coverage report, so the
# repo root needs to be importable here.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CLI_MODULES = [
    "src.cli.bcllm_experiment",
    "src.cli.bcllm_model",
    "src.cli.bcllm_questions",
    "src.cli.bcllm_run",
    "src.cli.bcllm_execute",
    "src.cli.bcllm_export",
    "src.cli.bcllm_review",
    "src.cli.bcllm_provider",
]


@dataclass
class CoverageReport:
    cli_flags: set[str]
    exercised_flags: set[str]

    @property
    def uncovered(self) -> set[str]:
        return self.cli_flags - self.exercised_flags

    @property
    def stale_in_yaml(self) -> set[str]:
        """Flags used by cases but not declared by any current parser —
        the case is exercising a flag that no longer exists."""
        return self.exercised_flags - self.cli_flags


def discover_cli_flags() -> set[str]:
    flags: set[str] = set()
    for module_name in CLI_MODULES:
        module = importlib.import_module(module_name)
        if not hasattr(module, "create_parser"):
            continue
        parser = module.create_parser()
        for action in parser._actions:
            flags.update(o for o in action.option_strings if o.startswith("--"))
    return flags


def flags_exercised_by_cases(cases: list[Case]) -> set[str]:
    flags: set[str] = set()
    for case in cases:
        for token in list(case.argv) + [t for step in case.setup for t in step.argv]:
            if isinstance(token, str) and token.startswith("--"):
                flags.add(token.split("=", 1)[0])
    return flags


def build_coverage_report(cases: list[Case]) -> CoverageReport:
    return CoverageReport(
        cli_flags=discover_cli_flags(),
        exercised_flags=flags_exercised_by_cases(cases),
    )
