---
type: normative
audience: ai
last-validated: 2026-08-18
status: active
---

# Interaction Contracts

**Scope:** Event emission, rendering boundaries, UI behavior  
**Status:** 🟡 Partially defined — Section 2 (CLI Output Boundaries) is now
normative, established by ADR-002 as part of the CLI Typer/Rich
migration's Fase 1. Sections 1, 3, and 4 remain placeholders and are
**not** resolved by this update — see the note at the end of each.

---

## Contract Statement

This document defines the invariants for:
- Rendering boundaries (what components are responsible for what UI) — **CLI
  output boundaries are defined below (Section 2)**; Review UI boundaries
  remain open (Section 1)
- Event emission boundaries (what components emit what events) — **remains
  open** (Section 3)
- UI behavior guarantees (consistency, state management) — **partially
  covered** by Section 2 for the CLI; Review UI state guarantees remain
  open (Section 1)

---

## Current State

### 1. Review UI Boundaries

**Still a placeholder.** Deliberately deferred — the CLI Typer/Rich
migration plan scopes Fase 1 to CLI Output Boundaries only (Section 2)
and revisits Review UI Boundaries no earlier than the Fase 4 `review`
migration milestone, or sooner if a human prioritizes it explicitly. The
"Known Constraints" list below (from the original placeholder) is
observational, not yet normative — do not treat it as a contract until
this section is filled in.

- What is the Review UI responsible for?
- What does it delegate to other components?
- What are the UI state invariants? (e.g., undo history, batch classification)
- How does it interact with the database? (read-only? write review fields?)

### 2. CLI Output Boundaries — NORMATIVE

Established by ADR-002
(`docs/architecture/adr/adr-002-cli-presentation.md`). Applies to every
`bcllm` command, present and future, regardless of implementation
(argparse today, Typer after the migration).

**stdout carries results, and only results.** Every normal-path,
successful-or-handled-error output goes to stdout: what was requested,
what was created/changed, identifiers, effective configuration relevant
to the action, counts of affected entities, and — when applicable — a
useful next step. Machine-readable output (`--output json`, once
implemented) is stdout-only and MUST be free of ANSI escape codes and
free of any log line, regardless of terminal or `--no-color` state.

**stderr carries diagnostics, and only diagnostics.** Error messages,
warnings, and technical log lines (via `src/utils/logging_config.py`,
whose console handler already targets stderr — see
`docs/contracts/data-auditability.md`'s logging section) go to stderr.
Never mix a log line into stdout, and never put a result the user asked
for onto stderr. `--quiet` (once implemented) may reduce stdout verbosity
but MUST NOT suppress stderr — errors are always visible.

**Exit codes are stable and meaningful:**
- `0` — success, including "no pending work" no-op successes.
- `1` — domain/validation error (experiment not found, invalid spec,
  contract violation caught explicitly, etc.).
- `2` — usage error (missing/invalid argument, unknown flag). This is
  argparse's own convention today and MUST be preserved by the Typer
  migration (Click/Typer use the same `2` for usage errors, so this is a
  continuation, not a new rule).
- `130` — interrupted by `Ctrl-C` during `--execute` (already the
  behavior of `bcllm_execute.main`). Any future long-running command that
  can be interrupted must follow the same convention rather than
  inventing a new code.

No other exit code may be introduced without updating this contract.

**`--output json` (planned, not yet implemented — see
`docs/status/known-issues.md` on the current dead `--output` flags):**
when implemented, JSON output must be stable field names, valid JSON on
its own (no leading/trailing prose), and never interleaved with stderr
content on the same stream. It is a separate rendering of the same
result data that stdout's console form already carries — not a separate
code path with different information.

**No-color / non-interactive terminals:** when `NO_COLOR` is set, or
stdout is not a TTY (`sys.stdout.isatty()` is `False` — e.g. piped,
redirected, or run under `tests/cli_suite`'s subprocess capture), Rich
color and interactive elements (progress bars, live displays) are
disabled. The underlying text content and structure do not change —
only the styling. This must hold for both the current console output and
any future Rich-based renderer (Fase 6 of the CLI migration plan).

**Explicitly out of scope for this section** (not normative yet, and not
inferred from it): the *visual* design of console output (tables, panels,
color palette, theme) — that is Fase 6 of the CLI migration plan, a
presentation-layer decision, not an interaction contract. This section
constrains *which stream* and *what exit code*, not *how it looks*.

### 3. Event Emission

**Still a placeholder.** Current state, recorded so this isn't silently
assumed either way: **no event system exists today.** The CLI produces
structured results (console text, and — once implemented — JSON) and
technical logs (Section 4); it does not emit or subscribe to discrete
events. If a future feature introduces one (e.g. progress events for
`--execute`'s Fase 6 `Progress`/`Live` display), it must be added here
explicitly, not inferred from the presentation work that motivated it.

- What events are emitted during execution?
- What is the event schema?
- What components subscribe to what events?

### 4. Logging Boundaries

**Still a placeholder as a fully worked-out section**, but the load-bearing
rule already exists and is now cross-referenced normatively from Section
2: technical logs go through `src/utils/logging_config.py` and its
console handler targets stderr, never stdout (see
`docs/contracts/data-auditability.md` — "Logs are treated as scientific
data" — for the full logging philosophy: crash-safe, include
experiment/run/model/question identifiers, never expose secrets, and
per-experiment log separation stays manual, not automated). What remains
open here specifically is per-component granularity (which module logs
at which level) — not attempted in this pass.

- What components are responsible for logging?
- What log levels are used when?
- What information is included in logs?

---

## Known Constraints — Review UI (from existing code)

Scoped to Section 1 (Review UI Boundaries), which remains a placeholder —
these are observations, not yet normative.

From reviewing `src/review/review_ui.py` and related code:

1. **Review UI reads from database** — Loads pending responses for review
2. **Review UI writes review fields** — Updates `manual_answer`, `review_status`, `reviewed_at`
3. **Review UI supports undo** — Can revert last classification
4. **Review UI supports batch operations** — Can classify multiple items at once
5. **Review UI is terminal-based** — Uses Rich library for TUI
6. **Review UI does not modify original data** — Only adds review annotations

---

## Next Steps

1. ~~Define CLI output invariants (stdout/stderr/exit codes/JSON/no-color)~~
   — done, Section 2, ADR-002.
2. Review existing review UI implementation and define Section 1's
   invariants — deferred to the `review` migration milestone.
3. Document UI state management rules (Review UI undo/batch state).
4. Define event emission schema, if/when an event system is introduced.
5. Establish logging boundaries per component (which module logs what,
   at which level).

---

**Sections 1, 3, and 4 remain placeholders and MUST be completed before
the specific UI-related work they gate begins** — Review UI changes for
Section 1, any event-emitting feature for Section 3, per-component
logging changes for Section 4. Section 2 no longer gates CLI
output/presentation work: it is normative as of ADR-002 and is exactly
what unblocks the CLI Typer/Rich migration's Fase 2 onward.
