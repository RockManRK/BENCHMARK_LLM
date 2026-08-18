"""Evaluates a Case's `expect` and `db` blocks against a CommandResult,
producing the case's final State.

Output-assertion policy (kept from the draft spec, and correct: there is no
normative contract for CLI output format — docs/contracts/interaction-contracts.md
is an explicit placeholder — so this suite asserts exit code + essential
terms, never full sentences, and never couples to exact wording).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .case import Case
from .dbcheck import AssertionOutcome
from .executor import CommandResult
from .states import State

_TRACEBACK_MARKER = "Traceback (most recent call last):"


@dataclass
class CaseRunResult:
    case: Case
    state: State
    reasons: list[str] = field(default_factory=list)
    setup_results: list[CommandResult] = field(default_factory=list)
    command_result: CommandResult | None = None
    db_assertion_outcomes: list[AssertionOutcome] = field(default_factory=list)
    changed_tables: list[str] = field(default_factory=list)
    integrity_issues: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    # The argv actually executed, with {ns}/captured placeholders already
    # substituted — distinct from case.resolved_argv(), which (called
    # with no captured values) would show a literal unsubstituted
    # "{run_id}"-style placeholder for any case using setup: capture.
    resolved_argv: list[str] = field(default_factory=list)


def evaluate(
    case: Case,
    command_result: CommandResult,
    db_outcomes: list[AssertionOutcome],
    changed_tables: list[str],
    integrity_issues: list[str],
    resolved_argv: list[str] | None = None,
) -> CaseRunResult:
    reasons: list[str] = []
    ok = True

    resolved_argv = resolved_argv if resolved_argv is not None else case.resolved_argv()

    if command_result.timed_out:
        return CaseRunResult(
            case=case,
            state=State.ERROR,
            reasons=[f"command timed out after {case.timeout}s"],
            command_result=command_result,
            resolved_argv=resolved_argv,
        )

    expect = case.expect

    if command_result.exit_code != expect.exit_code:
        ok = False
        reasons.append(
            f"exit_code: expected {expect.exit_code}, got {command_result.exit_code}"
        )

    if expect.no_traceback and _TRACEBACK_MARKER in command_result.stderr:
        ok = False
        reasons.append("unexpected Python traceback in stderr")

    for term in expect.stdout_contains:
        if term not in command_result.stdout:
            ok = False
            reasons.append(f"stdout missing expected term: {term!r}")

    for term in expect.stderr_contains:
        if term not in command_result.stderr:
            ok = False
            reasons.append(f"stderr missing expected term: {term!r}")

    for term in expect.stdout_not_contains:
        if term in command_result.stdout:
            ok = False
            reasons.append(f"stdout contains forbidden term: {term!r}")

    for outcome in db_outcomes:
        if not outcome.passed:
            ok = False
            reasons.append(
                f"db assertion failed: {outcome.assertion.query!r} "
                f"expected {outcome.assertion.equals!r}, got {outcome.actual!r}"
            )

    forbidden_changes = [t for t in changed_tables if t in case.db.unchanged_tables]
    if forbidden_changes:
        ok = False
        reasons.append(f"tables expected unchanged but changed: {forbidden_changes}")

    if integrity_issues:
        ok = False
        reasons.append(f"database integrity issues: {integrity_issues}")

    state = _resolve_state(case, ok)

    return CaseRunResult(
        case=case,
        state=state,
        reasons=reasons,
        command_result=command_result,
        db_assertion_outcomes=db_outcomes,
        changed_tables=changed_tables,
        integrity_issues=integrity_issues,
        duration_s=command_result.duration_s,
        resolved_argv=resolved_argv,
    )


def _resolve_state(case: Case, ok: bool) -> State:
    """A case with `known_issue` set describes, in its own `expect:` block,
    the CURRENT (broken) behavior of a known bug — e.g. `--list-experiments`
    is expected to exit 1 today because of the Mode.INVALID routing gap
    (see docs/status/known-issues.md).

    - `ok=True`  -> the command matched that documented-broken behavior
                    -> the bug is still present -> EXPECTED_FAILURE.
    - `ok=False` -> behavior no longer matches the documented bug
                    -> something changed (maybe fixed!) -> UNEXPECTED_PASS,
                       which needs a human to look and, if it's genuinely
                       fixed, remove known_issue and promote the case.

    A case WITHOUT `known_issue` uses ordinary PASS/FAIL.
    """
    if case.known_issue is not None:
        return State.EXPECTED_FAILURE if ok else State.UNEXPECTED_PASS
    return State.PASS if ok else State.FAIL
