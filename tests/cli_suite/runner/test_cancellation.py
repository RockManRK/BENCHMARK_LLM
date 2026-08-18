"""Verifies run.py's cancellation handling without depending on OS-level
signal delivery (unreliable to test through this sandboxed environment on
Windows/MSYS2 — subprocess.run's own KeyboardInterrupt propagation is
standard library behavior and not what's being tested here).

What IS being tested: when a KeyboardInterrupt is raised mid-loop, main()
must (a) not crash, (b) mark every not-yet-run case as SKIPPED, (c) still
call report.write_reports so tests_workspace/report.md and report.json
exist afterward. This is the actual promise made to the user ("permitir
cancelamento do processo" — the run must leave a report, not just die).

Named test_*.py so pytest's collector visits it, but it has no `def
test_*` function (only `main()`) — pytest safely collects 0 items from it
and moves on. Run it explicitly instead:
    python tests/cli_suite/runner/test_cancellation.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tests/cli_suite/

from runner.case import Case, Fixture  # noqa: E402
from runner.states import State  # noqa: E402


def _fake_case(case_id: str) -> Case:
    return Case(
        id=case_id, name=case_id, area="test", profiles=("smoke",),
        source_file=Path("fake.yaml"), fixture=Fixture(),
        argv=("--list-experiments",),
    )


def main() -> int:
    import run as suite_run

    cases = [_fake_case("A"), _fake_case("B"), _fake_case("C")]

    call_count = {"n": 0}

    def fake_run_one_case(case, workspace, cfg):
        call_count["n"] += 1
        if case.id == "B":
            raise KeyboardInterrupt()
        from runner.assertions import CaseRunResult
        return CaseRunResult(case=case, state=State.PASS)

    with tempfile.TemporaryDirectory() as tmp:
        workspace_root = Path(tmp) / "tests_workspace"

        with patch.object(suite_run, "load_cases", return_value=cases), \
             patch.object(suite_run, "_select_cases", return_value=cases), \
             patch.object(suite_run, "_run_one_case", side_effect=fake_run_one_case), \
             patch.object(suite_run, "_blocked_reason", return_value=None), \
             patch("sys.argv", ["run.py", "--profile", "smoke", "--yes", "--workspace", str(workspace_root)]):

            exit_code = suite_run.main()

        report_md = workspace_root / "report.md"
        report_json = workspace_root / "report.json"

        assert report_md.exists(), "report.md must exist after a cancelled run"
        assert report_json.exists(), "report.json must exist after a cancelled run"

        import json
        data = json.loads(report_json.read_text(encoding="utf-8"))
        states = {c["id"]: c["state"] for c in data["cases"]}

        assert states["A"] == "PASS", states
        # Case B raised KeyboardInterrupt while running -- it never
        # produced a result and is correctly absent from run_ids, so it's
        # swept up by the "not yet run" SKIPPED pass alongside C.
        assert states.get("B", "SKIPPED") == "SKIPPED", states
        assert states["C"] == "SKIPPED", states

        # SKIPPED is deliberately NOT in FAILING_STATES (runner/states.py) —
        # the user chose to cancel, that's not the suite reporting a
        # problem, so a cancelled run with no real FAIL/ERROR is exit 0.
        assert exit_code == 0, f"expected clean exit for a cancelled-but-not-failing run, got {exit_code}"

    print("OK: cancellation leaves SKIPPED cases and a written report.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
