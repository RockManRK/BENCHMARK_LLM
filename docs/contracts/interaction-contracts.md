---
type: normative
audience: ai
last-validated: 2026-08-20
status: active
---

# Interaction Contracts

**Scope:** Event emission, rendering boundaries, UI behavior  
**Status:** 🟡 Partially defined — Section 2 (CLI Output Boundaries) is
normative, established by ADR-002 as part of the CLI Typer/Rich
migration's Fase 1. **Section 4 (Logging Boundaries) is now normative as
of Checkpoint C** (`docs/status/checkpoint-c-logging-observability-design.md`)
— see below. Sections 1 and 3 remain placeholders — see the note at the
end of each.

---

## Contract Statement

This document defines the invariants for:
- Rendering boundaries (what components are responsible for what UI) — **CLI
  output boundaries are defined below (Section 2)**; Review UI boundaries
  remain open (Section 1)
- Event emission boundaries (what components emit what events) — **remains
  open as a pub/sub event system (Section 3)**; a related but distinct
  capability — a centralized, structured *logging* event vocabulary — is
  now normative under Section 4, not to be confused with this section
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

**Still a placeholder as a pub/sub system.** Current state, recorded so
this isn't silently assumed either way: **no publish/subscribe event
system exists today** — nothing in this codebase subscribes to an event
emitted by another component to drive its own behavior. If a future
feature introduces one (e.g. progress events for `--execute`'s Fase 6
`Progress`/`Live` display driving a UI independent of the log stream), it
must be added here explicitly, not inferred from the presentation work
that motivated it, and not assumed to already exist just because
Section 4's structured *logging* events (below) sound similar — they are
not the same mechanism. Logging events are one-way (component → log
sink), never consumed by another component to change its own behavior;
a real event system would be two-way (publisher → subscriber(s) that act
on it). This distinction matters precisely because it would be easy to
conflate them now that Section 4 exists.

- What events are emitted during execution, for a subscriber (not a
  log sink) to consume?
- What is the event schema for that system, if introduced?
- What components subscribe to what events?

### 4. Logging Boundaries — NORMATIVE (Checkpoint C)

Established by the Checkpoint C investigation and design
(`docs/status/checkpoint-c-logging-observability-design.md`) and its
implementation. Applies to every logging call site in `src/`.

**The load-bearing stream rule** (already cross-referenced from Section 2,
now made precise): technical logs go through
`src/utils/logging_config.py`; the console handler targets stderr, never
stdout (`FlushingStreamHandler()`'s default). The structured JSONL stream
(`src/utils/log_emitter.py`) writes to its own sibling file
(`<LOG_FILE_PATH stem>.jsonl`), never to stdout, stderr, or interleaved
with the human-readable file.

**One emission path.** Every structured log event — anything with a
stable `event_name` — is emitted through
`src.utils.log_emitter.emit_event`, never constructed ad hoc at the call
site. `event_name` values are constants from
`src.utils.log_events.Event`; no module may build one as a string
literal. This is what keeps the vocabulary centralized rather than
scattered (closing the gap the Checkpoint C investigation found: an
informal `EVENT | k=v` convention existed in 8 modules before this
checkpoint, each hand-writing its own strings).

**Two derived outputs from one event, never two constructions.** Every
`emit_event` call produces a human-readable line (unchanged in spirit
from the pre-Checkpoint-C format) and a JSONL line, from the *same*
in-memory field set — mirroring the "single canonical construction, two
destinations" discipline Checkpoint B established for the API request
payload. No log call site builds its own JSON.

**Depth profiles gate INFO/DEBUG events only.** `LOG_PROFILE`
(MINIMAL/NORMAL/DETAILED/TRACE, cumulative, `.env`-only — no CLI
override, matching `LOG_LEVEL`'s existing precedent) controls which
`INFO`/`DEBUG`-severity events are eligible to emit at all.
**`WARNING`/`ERROR`/`CRITICAL` events are NEVER suppressed by profile,
under any configuration** — this is enforced structurally, once, inside
`emit_event`'s severity-floor check, not left to per-call-site
discipline. `LOG_LEVEL` (stdlib severity threshold) and `LOG_PROFILE`
(which events exist) are orthogonal knobs — see
`docs/reference/configuration-reference.md`.

**`operation_id` correlates one CLI invocation.** Generated once per
invocation in `bcllm.py`'s `main()`, before dispatch, and threaded
explicitly through the call chain (no global/contextvar state — matching
`logging_config.py`'s own "No global logger state" principle) down
through the Planner → AsyncOrchestrator → ExecutionEngine → RetryHandler
→ OpenRouterClient → ResultWriter pipeline for `--execute`, and emitted
on every command's `COMMAND_START`/`COMMAND_END`/`COMMAND_INTERRUPTED`
regardless of which of the 9 CLI modules handles it. Distinct from
`experiment_id`/`run_id`/etc. (the data-level correlators) — both are
carried together on relevant events, answering different questions
("what happened during this command" vs. "what happened to this Run").

**Redaction is unconditional.** `src.utils.redaction.redact` runs inside
`emit_event`, before either output is constructed, on every field, for
every event, at every profile including TRACE. No call site can opt out.
Covers secret-shaped dict keys (`api_key`, `authorization`, `token`,
`secret`, `password`, etc.), `Bearer` tokens embedded in strings,
credentials in URLs, and secret-shaped `key=value` fragments inside
exception messages — recursively through dicts/lists/tuples. Redaction
produces a new, redacted copy for the log output only; it never mutates
the caller's in-memory object and never touches anything persisted to
the database (see `docs/contracts/data-auditability.md` §4b — logs are a
*third*, distinct record from `request_json`/`raw_response`, never a
substitute for either).

**Logging failures never break execution.** `emit_event` catches any
exception raised during redaction, serialization, or handler I/O,
attempts a best-effort fallback log line, and never propagates — a
logging bug must never surface as an execution failure, a lost DB write,
or something a resume/retry path could mistake for "not yet attempted"
(ties to `docs/contracts/idempotency.md`).

**Which components log, and at what depth:**
- MINIMAL: command lifecycle only (`COMMAND_START`/`COMMAND_END`/
  `COMMAND_INTERRUPTED`) plus any `WARNING`+ event, everywhere.
- NORMAL (default): entity lifecycle, Plan/Run/Item/Retry/API-call/write
  events — the pre-existing `EVENT | k=v` convention, now centralized.
- DETAILED: `ConfigResolver`'s previously-silent resolution decisions
  (`CONFIG_RESOLVED`, `INHERITANCE_DECISION`, `SYSTEM_DEFAULT_APPLIED`),
  idempotency skips, parse/randomization decisions.
- TRACE: the canonical request payload itself (redacted), the OpenRouter
  debug/upstream-echo (redacted, kept structurally distinct from
  `request_json` — never merged into it), raw SSE chunks.

Full per-family JSONL schema, exact event catalog, and the OpenRouter
`debug` vs. `LOG_LEVEL` scope rule (two independent, never-conflated
configurations — `OPENROUTER_DEBUG_ENABLED` is operational/per-process,
not part of the frozen Experiment/Run/Model-Variant configuration
hierarchy): see
`docs/status/checkpoint-c-logging-observability-design.md`.

**Explicitly out of scope for this section** (deferred to the separate,
not-yet-started Checkpoint C2): migrating the 163 existing `print()`
call sites in `src/cli/*.py`/`bcllm.py` to also reach the log
file/stream — see `docs/status/cli-output-classification.md` for the
classification map. This section governs the logging layer itself, which
is complete; it does not retroactively require every CLI print to become
a log event.

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
4. Define event emission schema, if/when a pub/sub event system is
   introduced (Section 3) — distinct from the structured logging events
   below, which are done.
5. ~~Establish logging boundaries per component (which module logs what,
   at which level)~~ — done, Section 4, Checkpoint C.

---

**Sections 1 and 3 remain placeholders and MUST be completed before the
specific work they gate begins** — Review UI changes for Section 1, any
pub/sub-event-emitting feature for Section 3. Section 2 no longer gates
CLI output/presentation work (normative as of ADR-002); Section 4 no
longer gates per-component logging work (normative as of Checkpoint C).
