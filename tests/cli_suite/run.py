#!/usr/bin/env python3
"""Entry point for the bcllm CLI automated test suite.

    python tests/cli_suite/run.py --profile smoke
    python tests/cli_suite/run.py --profile cli-unit --yes
    python tests/cli_suite/run.py --profile full --openrouter --openrouter-model-id <cheap-model-id>

See the plan / docs/tests/ for the design rationale. Summary: runs the
REAL bcllm.py against a sandbox workspace (tests_workspace/, wiped and
recreated at the start of each run unless --keep), using one shared SQLite
database and one shared log file for the whole run, plus a local HTTP stub
standing in for OpenRouter so --execute cases are free, deterministic, and
offline by default.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import traceback
from datetime import datetime, timezone

from rich.console import Console

from runner import dbcheck, report, stub_server
from runner.assertions import CaseRunResult, evaluate
from runner.case import Case, CaseValidationError, load_cases
from runner.config import SuiteConfig, parse_args
from runner.coverage import build_coverage_report
from runner.executor import run_bcllm
from runner.states import FAILING_STATES, State
from runner.ui import SuitePanel, print_final_summary
from runner.workspace import Workspace

console = Console()


def _select_cases(cases: list[Case], profile: str) -> list[Case]:
    if profile == "full":
        return cases
    return [c for c in cases if profile in c.profiles]


def _confirm_wipe(workspace: Workspace, cfg: SuiteConfig) -> bool:
    if not workspace.exists():
        return True
    if cfg.keep:
        return False
    if cfg.yes:
        return True
    # Rich's console.input() parses [..] as markup by default, which
    # silently swallows a literal "[y/N]" (it's not a recognized style
    # name, so it renders as nothing rather than raising) — escape it.
    answer = console.input(
        f"[yellow]Sandbox workspace already exists at {workspace.root}. "
        rf"Wipe it and start fresh? \[y/N][/yellow] "
    )
    return answer.strip().lower() in ("y", "yes")


def _blocked_reason(case: Case, cfg: SuiteConfig, llamacpp_healthy: bool | None) -> str | None:
    if "openrouter" in case.requires:
        if not cfg.enable_openrouter:
            return "requires openrouter, but --openrouter not passed"
        if not cfg.openrouter_model_id:
            return "requires openrouter, but no --openrouter-model-id configured"
    if "llamacpp" in case.requires:
        if not cfg.enable_llamacpp:
            return "requires llamacpp, but --llamacpp not passed"
        if not cfg.llamacpp_url:
            return "requires llamacpp, but no --llamacpp-url configured"
        if llamacpp_healthy is False:
            return f"llamacpp server at {cfg.llamacpp_url} did not respond to health check"
    return None


def _check_llamacpp_health(url: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:  # noqa: S310
            return resp.status < 500
    except Exception:
        return False


def _blank_result(case: Case, state: State, reason: str) -> CaseRunResult:
    # Best-effort argv for display (no captured values available at this
    # point — a case that fails during its own setup, before any capture
    # runs, would show the raw {placeholder} uninterpolated, which is
    # still more useful than nothing for diagnosing the failure).
    return CaseRunResult(case=case, state=state, reasons=[reason], resolved_argv=case.resolved_argv())


def _run_one_case(case: Case, workspace: Workspace, cfg: SuiteConfig) -> CaseRunResult:
    if "not_implemented" in case.tags:
        return _blank_result(case, State.NOT_IMPLEMENTED, "tagged not_implemented")
    if "pending_spec" in case.tags:
        return _blank_result(case, State.PENDING_SPEC, "tagged pending_spec; expectation not yet defined")

    case_env = workspace.prepare_case_env(case, cfg.dataset_fixtures_dir)

    # Values a setup step captures from its own stdout (e.g. a run_id an
    # --add-run just printed), available as {name} in every later setup
    # step, the main command, and db assertions — see case.py's SetupStep.
    captured: dict[str, str] = {}

    setup_results = []
    for step in case.setup:
        setup_argv = case.resolved_setup_step(step, captured)
        res = run_bcllm(setup_argv, cwd=case_env.cwd, timeout=case.timeout)
        setup_results.append(res)
        if res.exit_code != 0:
            result = _blank_result(
                case, State.ERROR,
                f"setup command failed (exit {res.exit_code}): {' '.join(setup_argv)}",
            )
            result.setup_results = setup_results
            return result

        for name, pattern in step.capture.items():
            match = re.search(pattern, res.stdout)
            if not match:
                result = _blank_result(
                    case, State.ERROR,
                    f"setup capture {name!r} pattern {pattern!r} not found in stdout of: {' '.join(setup_argv)}",
                )
                result.setup_results = setup_results
                return result
            captured[name] = match.group(1)

    db_exists_before = case_env.db_path.exists()
    fingerprints_before = None
    if db_exists_before and case.db.unchanged_tables:
        try:
            with workspace.connect_readonly(case_env.db_path) as conn:
                fingerprints_before = dbcheck.fingerprint_tables(conn, tuple(case.db.unchanged_tables))
        except sqlite3.Error:
            fingerprints_before = None

    resolved_argv = case.resolved_argv(captured)
    command_result = run_bcllm(resolved_argv, cwd=case_env.cwd, timeout=case.timeout)

    db_outcomes = []
    changed_tables: list[str] = []
    integrity_issues: list[str] = []
    if case_env.db_path.exists():
        try:
            with workspace.connect_readonly(case_env.db_path) as conn:
                db_outcomes = [
                    dbcheck.run_assertion(conn, a) for a in case.resolved_db_assertions(captured)
                ]
                if case.db.unchanged_tables:
                    fingerprints_after = dbcheck.fingerprint_tables(conn, tuple(case.db.unchanged_tables))
                    if fingerprints_before is not None:
                        changed_tables = dbcheck.diff_fingerprints(fingerprints_before, fingerprints_after)
                integrity_issues = dbcheck.integrity_issues(conn)
        except sqlite3.Error as e:
            integrity_issues = [f"could not inspect database: {e}"]

    result = evaluate(case, command_result, db_outcomes, changed_tables, integrity_issues, resolved_argv)
    result.setup_results = setup_results
    return result


def _write_artifacts(workspace: Workspace, result: CaseRunResult) -> None:
    case_dir = workspace.artifacts_dir / result.case.id
    case_dir.mkdir(parents=True, exist_ok=True)

    (case_dir / "cmd.txt").write_text(
        report.sanitize(" ".join(result.resolved_argv or result.case.resolved_argv())), encoding="utf-8"
    )
    if result.command_result:
        (case_dir / "stdout.txt").write_text(report.sanitize(result.command_result.stdout), encoding="utf-8")
        (case_dir / "stderr.txt").write_text(report.sanitize(result.command_result.stderr), encoding="utf-8")
    (case_dir / "result.json").write_text(json.dumps({
        "state": result.state.value,
        "reasons": result.reasons,
        "changed_tables": result.changed_tables,
        "integrity_issues": result.integrity_issues,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    cfg = parse_args()

    try:
        cases = load_cases(cfg.cases_dir)
    except CaseValidationError as e:
        console.print(f"[bold red]Case validation error:[/bold red] {e}")
        return 1

    selected = _select_cases(cases, cfg.profile)
    if not selected:
        console.print(f"[yellow]No cases match profile {cfg.profile!r}. Nothing to run.[/yellow]")
        return 0

    workspace = Workspace(root=cfg.workspace)

    if _confirm_wipe(workspace, cfg):
        workspace.wipe()
    workspace.create()

    stub = stub_server.start_stub_server()
    workspace.stub_base_url = stub.base_url

    llamacpp_healthy = _check_llamacpp_health(cfg.llamacpp_url) if cfg.llamacpp_url else None

    started_at = datetime.now(timezone.utc)
    results: list[CaseRunResult] = []

    try:
        with SuitePanel(total_cases=len(selected), profile=cfg.profile) as panel:
            for case in selected:
                panel.start_case(case)

                blocked_reason = _blocked_reason(case, cfg, llamacpp_healthy)
                if blocked_reason:
                    result = _blank_result(case, State.BLOCKED, blocked_reason)
                else:
                    try:
                        result = _run_one_case(case, workspace, cfg)
                    except Exception:  # noqa: BLE001 - one bad case must not kill the run
                        result = _blank_result(
                            case, State.ERROR,
                            f"runner-internal exception: {traceback.format_exc(limit=3)}",
                        )

                results.append(result)
                _write_artifacts(workspace, result)
                panel.finish_case(result)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted — marking remaining cases as SKIPPED and writing report.[/yellow]")
        run_ids = {r.case.id for r in results}
        for case in selected:
            if case.id not in run_ids:
                results.append(_blank_result(case, State.SKIPPED, "run cancelled (Ctrl+C)"))
    finally:
        stub_server.dump_requests_log(stub, workspace.root / "stub_requests.json")
        stub.stop()

    data = report.write_reports(
        results, cfg.profile, started_at,
        json_path=workspace.report_json_path, md_path=workspace.report_md_path,
    )

    if cfg.compare_path and cfg.compare_path.exists():
        previous = json.loads(cfg.compare_path.read_text(encoding="utf-8"))
        diffs = report.compare(previous, data)
        console.print("\n[bold]Compared to previous run:[/bold]")
        if diffs:
            for line in diffs:
                console.print(f"  {line}")
        else:
            console.print("  no case changed state")

    coverage = build_coverage_report(cases)
    if coverage.uncovered:
        console.print(f"\n[yellow]{len(coverage.uncovered)} CLI flag(s) with no test case:[/yellow] "
                       f"{sorted(coverage.uncovered)}")
    if coverage.stale_in_yaml:
        console.print(f"[red]{len(coverage.stale_in_yaml)} flag(s) used in cases but no longer in the CLI:[/red] "
                       f"{sorted(coverage.stale_in_yaml)}")

    print_final_summary(console, results, workspace.report_md_path, workspace.report_json_path)

    failing = [r for r in results if r.state in FAILING_STATES]
    return 1 if failing else 0


if __name__ == "__main__":
    # Python automatically puts this script's own directory (tests/cli_suite/)
    # at sys.path[0] when run directly, which is what makes `from runner
    # import ...` above resolve — no manual sys.path manipulation needed.
    sys.exit(main())
