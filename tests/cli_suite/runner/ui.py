"""Rich-based live progress panel for the CLI test suite.

rich is already a project dependency (requirements.txt), used elsewhere by
src/review/review_ui.py.
"""

from __future__ import annotations

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .assertions import CaseRunResult
from .case import Case
from .states import State

_STATE_STYLE = {
    State.PASS: "green",
    State.FAIL: "bold red",
    State.PARTIAL: "yellow",
    State.EXPECTED_FAILURE: "dim yellow",
    State.UNEXPECTED_PASS: "bold magenta",
    State.BLOCKED: "cyan",
    State.NOT_IMPLEMENTED: "grey58",
    State.PENDING_SPEC: "grey58",
    State.SKIPPED: "grey58",
    State.ERROR: "bold red on white",
}


class SuitePanel:
    def __init__(self, total_cases: int, profile: str) -> None:
        self.console = Console()
        self.total = total_cases
        self.profile = profile
        self.counts: dict[State, int] = {s: 0 for s in State}
        self.current_case: str = ""
        self.last_failure: str = ""
        self._live: Live | None = None

    def __enter__(self) -> "SuitePanel":
        self._live = Live(self._render(), console=self.console, refresh_per_second=8)
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        if self._live:
            self._live.update(self._render())
            self._live.__exit__(*exc)

    def start_case(self, case: Case) -> None:
        self.current_case = f"{case.id} — {case.name}"
        self._refresh()

    def finish_case(self, result: CaseRunResult) -> None:
        self.counts[result.state] += 1
        if result.state.value in ("FAIL", "ERROR", "UNEXPECTED_PASS"):
            self.last_failure = f"{result.case.id}: {'; '.join(result.reasons) or result.state.value}"
        self._refresh()

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        # Previously: a bare Table with the progress text stuffed into its
        # .caption. Rich constrains a caption to the table's OWN rendered
        # width, which is only as wide as "State"/"Count" need — so
        # "running: <experiment name>" wrapped into a narrow, multi-line
        # mess. Fix: put the state table and the status lines as separate
        # renderables inside one Panel, which sizes to the full console
        # width instead of the table's width.
        done = sum(self.counts.values())

        table = Table(box=box.SIMPLE_HEAVY, expand=False)
        table.add_column("State")
        table.add_column("Count", justify="right")
        for state in State:
            if self.counts[state]:
                table.add_row(Text(state.value, style=_STATE_STYLE[state]), str(self.counts[state]))

        running_line = Text.from_markup(f"[bold]running:[/bold] {self.current_case or '(starting…)'}")
        failure_line = Text.from_markup(f"[bold]last failure:[/bold] {self.last_failure or '(none)'}")

        body = Group(table, Text(""), running_line, failure_line)

        return Panel(
            body,
            title=f"bcllm CLI test suite — profile: {self.profile}  ({done}/{self.total})",
            title_align="left",
            border_style="cyan",
        )


def print_final_summary(console: Console, results: list[CaseRunResult], report_md_path, report_json_path) -> None:
    # Only show columns for states that actually occurred — with all 10
    # State columns always present, most runs show 8+ empty columns and
    # the ones that matter get truncated headers ("EXP…", "PAR…") to fit.
    present_states = [s for s in State if any(r.state == s for r in results)]

    table = Table(title="Final results by area")
    table.add_column("Area")
    for state in present_states:
        table.add_column(Text(state.value, style=_STATE_STYLE[state]), justify="right")

    areas: dict[str, dict[State, int]] = {}
    for r in results:
        areas.setdefault(r.case.area, {s: 0 for s in State})
        areas[r.case.area][r.state] += 1

    for area, counts in sorted(areas.items()):
        table.add_row(area, *[str(counts[s]) if counts[s] else "" for s in present_states])

    console.print(table)

    from .report import sanitize  # local import: keep report.py UI-free

    detail = Table(title="Every case", show_lines=False)
    detail.add_column("ID", no_wrap=True)
    detail.add_column("State", no_wrap=True)
    detail.add_column("Command", overflow="fold")

    for r in results:
        command = f"python bcllm.py {sanitize(' '.join(r.resolved_argv or r.case.resolved_argv()))}" if r.case.argv else "—"
        detail.add_row(
            r.case.id,
            Text(r.state.value, style=_STATE_STYLE[r.state]),
            command,
        )

    console.print(detail)
    console.print(f"Report: [bold]{report_md_path}[/bold]")
    console.print(f"JSON:   [bold]{report_json_path}[/bold]")
