"""Markdown + JSON report generation.

report.json is the machine-readable artifact (diffable across runs via
`--compare`, consumable by an AI reviewing what changed). report.md is the
human-readable summary. Both are written into the shared workspace so a
suite run leaves exactly one of each behind for later inspection, per the
suite's design goal.
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .assertions import CaseRunResult
from .states import FAILING_STATES, State

# Redact anything that looks like a secret before it ever reaches disk.
_SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-_\.]{8,}", re.IGNORECASE),
    re.compile(r"(sk-or-[A-Za-z0-9\-_]{8,})"),  # OpenRouter-style keys
    re.compile(r"(OPENROUTER_API_KEY\s*=\s*)\S+"),
    re.compile(r"(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9\-_\.]{8,}", re.IGNORECASE),
]


def sanitize(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "***REDACTED***", text)
    return text


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def build_report_data(results: list[CaseRunResult], profile: str, started_at: datetime) -> dict:
    by_state: dict[str, int] = {}
    for r in results:
        by_state[r.state.value] = by_state.get(r.state.value, 0) + 1

    cases_json = []
    for r in results:
        cmd = r.command_result
        cases_json.append({
            "id": r.case.id,
            "name": r.case.name,
            "area": r.case.area,
            "priority": r.case.priority,
            "tags": list(r.case.tags),
            "state": r.state.value,
            "reasons": r.reasons,
            "duration_s": round(r.duration_s, 3),
            "argv": sanitize(" ".join(r.resolved_argv or r.case.resolved_argv())),
            "exit_code": cmd.exit_code if cmd else None,
            "known_issue": asdict(r.case.known_issue) if r.case.known_issue else None,
            "db_assertions": [
                {
                    "query": o.assertion.query,
                    "expected": o.assertion.equals,
                    "actual": o.actual,
                    "passed": o.passed,
                }
                for o in r.db_assertion_outcomes
            ],
            "changed_tables": r.changed_tables,
            "integrity_issues": r.integrity_issues,
        })

    return {
        "suite": "bcllm-cli-suite",
        "profile": profile,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "totals": {
            "cases": len(results),
            "by_state": by_state,
        },
        "cases": cases_json,
    }


def write_json(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_markdown(data: dict, results: list[CaseRunResult], path: Path) -> None:
    lines = [
        "# BCLLM CLI Test Suite Report",
        "",
        f"- Profile: `{data['profile']}`",
        f"- Commit: `{data['commit']}`",
        f"- Python: {data['python_version']} | Platform: {data['platform']}",
        f"- Started: {data['started_at']}",
        f"- Finished: {data['finished_at']}",
        "",
        "## Summary",
        "",
        "| State | Count |",
        "|---|---|",
    ]
    for state in State:
        count = data["totals"]["by_state"].get(state.value, 0)
        if count:
            lines.append(f"| {state.value} | {count} |")
    lines.append(f"| **TOTAL** | **{data['totals']['cases']}** |")
    lines.append("")

    lines.append("## By area")
    lines.append("")
    areas: dict[str, dict[str, int]] = {}
    for r in results:
        areas.setdefault(r.case.area, {})
        areas[r.case.area][r.state.value] = areas[r.case.area].get(r.state.value, 0) + 1
    present_states = [s for s in State if data["totals"]["by_state"].get(s.value, 0)]
    lines.append("| Area | " + " | ".join(s.value for s in present_states) + " |")
    lines.append("|---|" + "---|" * len(present_states))
    for area, counts in sorted(areas.items()):
        row = " | ".join(str(counts.get(s.value, "")) for s in present_states)
        lines.append(f"| {area} | {row} |")
    lines.append("")

    lines.append("## All cases")
    lines.append("")
    lines.append("| ID | State | Duration | Command |")
    lines.append("|---|---|---|---|")
    for r in results:
        duration = f"{r.duration_s:.2f}s" if r.command_result else "—"
        command = f"python bcllm.py {sanitize(' '.join(r.resolved_argv or r.case.resolved_argv()))}" if r.case.argv else "—"
        lines.append(f"| {r.case.id} | {r.state.value} | {duration} | `{command}` |")
    lines.append("")

    needs_attention = [r for r in results if r.state in FAILING_STATES]
    if needs_attention:
        lines.append("## Needs attention")
        lines.append("")
        for r in needs_attention:
            lines.append(f"### {r.case.id} — {r.case.name} — **{r.state.value}**")
            lines.append("")
            lines.append(f"- Area: {r.case.area} | Priority: {r.case.priority}")
            lines.append(f"- Command: `{sanitize(' '.join(r.resolved_argv or r.case.resolved_argv()))}`")
            if r.command_result:
                lines.append(f"- Exit code: {r.command_result.exit_code} | Duration: {r.duration_s:.2f}s")
            if r.reasons:
                lines.append("- Reasons:")
                for reason in r.reasons:
                    lines.append(f"  - {sanitize(reason)}")
            lines.append(f"- Artifacts: `artifacts/{r.case.id}/`")
            lines.append("")
    else:
        lines.append("## Needs attention")
        lines.append("")
        lines.append("Nothing — all cases PASS or EXPECTED_FAILURE.")
        lines.append("")

    blocked = [r for r in results if r.state in (State.BLOCKED, State.SKIPPED, State.NOT_IMPLEMENTED, State.PENDING_SPEC)]
    if blocked:
        lines.append("## Blocked / skipped / not implemented / pending spec")
        lines.append("")
        for r in blocked:
            lines.append(f"- **{r.case.id}** ({r.state.value}): {r.case.name} — {'; '.join(r.reasons) or 'n/a'}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_reports(results: list[CaseRunResult], profile: str, started_at: datetime,
                   json_path: Path, md_path: Path) -> dict:
    data = build_report_data(results, profile, started_at)
    write_json(data, json_path)
    write_markdown(data, results, md_path)
    return data


def compare(previous: dict, current: dict) -> list[str]:
    """Returns human-readable lines describing state changes per case id."""
    prev_by_id = {c["id"]: c["state"] for c in previous.get("cases", [])}
    curr_by_id = {c["id"]: c["state"] for c in current.get("cases", [])}

    lines = []
    for case_id in sorted(set(prev_by_id) | set(curr_by_id)):
        before = prev_by_id.get(case_id, "(new)")
        after = curr_by_id.get(case_id, "(removed)")
        if before != after:
            lines.append(f"{case_id}: {before} -> {after}")
    return lines
