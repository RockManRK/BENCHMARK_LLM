---
type: status
audience: ai
last-validated: 2026-08-20
status: proposed
---

# CLI Output Classification (Checkpoint C → C2 handoff map)

## Purpose and scope

This document is the print()-classification map required before Checkpoint
C2 (CLI output migration). It does **not** change any code. It reads every
`src/cli/*.py` module plus root `bcllm.py` in full and classifies every
`print()` call site by:

- **Category**: `resultado` (the requested result/data) · `diagnóstico`
  (informational, not the result, not an error) · `erro de uso` (invalid
  input / precondition failure) · `progresso` (per-item feedback during a
  longer operation) · `evento auditável` (represents, or should represent,
  a state change worth a structured log event).
- **Destination** C2 should assign: `stdout` (kept as terminal result) ·
  `stderr` (kept as terminal diagnostic/error) · `evento de log` (should
  additionally/instead go through `emit_event`) · `somente terminal`
  (cosmetic, no log needed) · `remoção por redundância` (drop — a
  logger call or another print already covers it).

This is the artifact Checkpoint C's user decision (2026-08-19, question 3)
requires: "**Não adote a regra simplista de copiar toda saída do terminal
para o arquivo de log. Para cada mensagem humana, o log deve
preferencialmente receber o evento estruturado correspondente, com campos
auditáveis, e não apenas a mesma string.**" Every row below that recommends
`evento de log` names a *field-based* event (existing or new), never "log
the same string."

## Method and count reconciliation

Every file in scope (`bcllm_experiment.py`, `bcllm_model.py`,
`bcllm_questions.py`, `bcllm_run.py`, `bcllm_execute.py`, `bcllm_export.py`,
`bcllm_review.py`, `bcllm_provider.py`, `bcllm_main.py`, root `bcllm.py`)
was read in full, not grepped-and-guessed. A `print\(` grep over
`src/cli/**` + `bcllm.py` returns **169** matches, but 6 of those are
**false positives** — occurrences of the literal substring `print(` inside
docstrings, not real calls:

| File | Line | Text matched | Why it's not a call |
|---|---|---|---|
| `bcllm_questions.py` | 349 | `print()-based handler produced them...` | docstring |
| `bcllm_questions.py` | 363 | `no print(), no sys.exit()` | docstring |
| `bcllm_run.py` | 196 | `no print(), no sys.exit()` | docstring |
| `bcllm_model.py` | 252 | `matching the historical multi-print() messages` | docstring |
| `bcllm_model.py` | 264 | `print(), no sys.exit()` | docstring |
| `src/cli/presentation/console.py` | 17 | `` `.print(...)` (or similar) produces output `` | docstring |

169 − 6 = 163 candidates, and one more must come out: `src/cli/
presentation/errors.py:66` calls `error_console.print(...)` — the Rich
`Console` object's `.print()` method, not the builtin `print()`. It's a
real, non-docstring call (so it's not one of the 6 above), but it isn't a
builtin `print()` call either, so it does not belong in this document's
count. It belongs to the future Typer/Rich presentation layer
(`src/cli/presentation/`, not yet wired into any live command) and is
listed separately in its own section below.

169 − 6 (docstring) − 1 (non-builtin) = **162 real builtin `print()`
calls** — one below the ~163 the design doc estimated mid-investigation;
the earlier 169 figure quoted at that point was the raw, unfiltered grep
count with neither exclusion applied.

Per-file breakdown of the 162:

| File | Real print() calls |
|---|---|
| `bcllm_experiment.py` | 53 |
| `bcllm_run.py` | 25 |
| `bcllm_execute.py` | 18 |
| `bcllm_provider.py` | 15 |
| `bcllm_model.py` | 13 |
| `bcllm_questions.py` | 13 |
| `bcllm.py` (root) | 11 |
| `bcllm_export.py` | 7 |
| `bcllm_review.py` | 6 |
| `bcllm_main.py` | 1 |
| **Total** | **162** |

## Cross-module shared pattern: dispatcher-bug guard

Eight of the nine `src/cli` modules (all except `bcllm_provider.py`, which
has its own near-identical variant) open with an identical
`_validate_expected_mode()` guard:

```python
print(
    f"Error: {__name__} expected one of {[m.value for m in VALID_MODES]} mode, "
    f"got '{mode.value}'.\nThis indicates a dispatcher bug. Please report this issue.",
    file=sys.stderr,
)
sys.exit(1)
```

Occurrences: `bcllm_experiment.py:53`, `bcllm_model.py:65`,
`bcllm_questions.py:66`, `bcllm_run.py:70`, `bcllm_execute.py:71`,
`bcllm_review.py:36`, `bcllm_main.py:22`, `bcllm_provider.py:42` (same
message, different `VALID_MODES` phrasing).

- **Category**: `diagnóstico` — technically an unreachable-in-practice
  internal-invariant guard (a dispatcher bug, not a user mistake), never
  observed to fire against real `mode_matrix` validation.
- **Destination**: `stderr` (keep) **+ `evento de log`**. No event exists
  for this today — recommend a new `DISPATCHER_MODE_MISMATCH` constant in
  `Event` (CRITICAL/ERROR tier, MINIMAL profile, always-on per the "never
  disable minimal lifecycle/critical signals" rule) so this class of bug
  leaves an audit trail even when nobody is watching the terminal. Since
  `sys.exit(1)` follows immediately, this is also the one place in the CLI
  layer where a `print()` is followed by a raw `sys.exit()` rather than a
  `return` — C2 should decide whether that stays or is unified with the
  rest of the exit-code contract (`src/cli/presentation/errors.py`).

This pattern is **not repeated per-module below** — each module's table
starts after this line.

## `bcllm_experiment.py` (53 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 338 | `Error: Experiment name cannot be empty.` | erro de uso | stderr | Pure input validation, no DB touched. |
| 343–346 | `--vision` invalid value + 3 hint lines | erro de uso | stderr | 4 prints, one logical message — C2 should consolidate to one multi-line print or one Rich panel. |
| 350–353 | `--structured` invalid value + 3 hint lines | erro de uso | stderr | Same shape as above. |
| 357–358 | `--provider-lock` invalid value + hint | erro de uso | stderr | |
| 365 | `Error: {e}` (from `_create_experiment_with_config`, e.g. "already exists") | erro de uso | stderr | Redundant with `logger.error(f"EXPERIMENT_CREATE | ... | error=Already exists")` at line 289 — that logger call should become `emit_event` with `Event.EXPERIMENT_CREATE_FAILED` (new) or reuse an error-tier event; print stays for the user-facing message. |
| **368** | `✓ Experiment '{name}' created (ID: {id})` | **resultado / evento auditável** | stdout **+ evento de log** | High priority — `Event.EXPERIMENT_CREATED` already exists in `log_events.py` (NORMAL tier) but is **not yet wired to any `emit_event` call** anywhere in the codebase; only the old unstructured `logger.info(f"EXPERIMENT_CREATED | name=... | experiment_id=...")` at line 319 covers it. C2 should replace that `logger.info` with `emit_event(logger, Event.EXPERIMENT_CREATED, experiment_id=..., name=...)`. |
| 436–437 | Invalid model ID + expected-format hint | erro de uso | stderr | |
| 446 | `Error: Variant '...' already exists...` | erro de uso / evento auditável | stderr | Duplicate-variant attempts are audit-relevant (someone tried to add a config that already exists) — recommend `Event.MODEL_ADD_DUPLICATE` (new, DETAILED) alongside the print. |
| **458** | `✓ Model variant '...' added` | **resultado / evento auditável** | stdout **+ evento de log** | Same gap as line 368: `Event.MODEL_ADDED` exists, unused. This is the `--create-experiment --add-model` composite path, distinct from `bcllm_model.py`'s standalone path (see below) — both need the same event. |
| 492–496 | `QUESTIONS_DATASET_PATH` set to `system-default` (rejected) + hint | erro de uso | stderr | Config-validation error, no DB touched. |
| 500–503 | `QUESTIONS_DATASET_PATH not set` | erro de uso | stderr | |
| 512 | `Error loading question dataset: {e}` | erro de uso / diagnóstico | stderr | Could be a corrupt dataset file — arguably worth `Event.DATASET_LOAD_FAILED` (new) at DETAILED for later debugging, since this failure has no other trace anywhere. |
| 526–530 | Invalid question spec + 3 format hint lines | erro de uso | stderr | |
| **536** | `Using DEFAULT_QUESTIONS from .env: {value}` | diagnóstico | **evento de log** (move off stdout) | This is an inheritance decision, not a result — belongs with `Event.INHERITANCE_DECISION` (DETAILED tier, already exists and is wired for `resolve_randomization_seed_for_run`; C2 should extend the same pattern here) rather than unconditional stdout noise. |
| 540 | Invalid `DEFAULT_QUESTIONS` spec | erro de uso | stderr | |
| 562, 570 | `--where` filter parse error / invalid `QUESTIONS_STATUS_ADD` | erro de uso | stderr | |
| 580, 588 | `--exclude` filter parse error / invalid `QUESTIONS_STATUS_EXCLUDE` | erro de uso | stderr | |
| 598 | `(N questions filtered out)` | diagnóstico | stdout | Low priority; harmless summary line, keep as-is. |
| 603 | `Warning: No questions selected for snapshotting.` | diagnóstico | stderr | Already correctly on stderr (it's a WARNING, not a result). |
| 615 | `Error: Question missing internal_id: {id}` | erro de uso / diagnóstico | stderr | Indicates a dataset integrity problem, not user input — candidate for a DETAILED-tier event too. |
| **635** | `✓ Added question {id} (position {pos})` (per-item, inside loop) | progresso | stdout, **candidate for reduction** | With large `--add-questions 1-500` this is 500 lines of stdout noise. C2 should keep the line but consider gating it behind `--verbose`/an output-level flag, or dropping to the summary-only line (638) plus a DEBUG-tier log event per item — not a MINIMAL/NORMAL terminal print. |
| 638 | `Summary: {N} added` | resultado | stdout | Keep — this is the actual result of the command. |
| 640 | `Skipped {N} existing snapshot(s)` | resultado | stdout | Keep. |
| 662 | `Error: Experiment not found: {name}` | erro de uso | stderr | Redundant with `logger.error(f"EXPERIMENT_SHOW | ...")` above it — same consolidation note as line 365. |
| 669–675 | `--experiment` show: 7 lines (name/ID/description/config block) | resultado | stdout | This is the entire `--experiment <name>` command's output — no redundancy, all 7 lines are distinct fields of the result. C2 may reformat as a single Rich table, but nothing here is droppable. |
| 696 | `No experiments found.` | resultado | stdout | Empty-result case, still a result. |
| 700–701 | List header + separator line | resultado | somente terminal | Purely cosmetic formatting for the table below — no log needed, would never map to a structured field. |
| 703 | Per-experiment row (loop) | resultado | stdout | |
| **734–743** | `--remove-experiment` disabled (deliberate, see docstring) | erro de uso / evento auditável | stderr **+ evento de log** | No log call exists for this today at all. An attempted (and refused) destructive action is exactly the kind of thing `docs/contracts/data-auditability.md` cares about — recommend `Event.REMOVE_EXPERIMENT_REFUSED` (new, NORMAL) so refusal attempts are traceable. |
| **770–778** | `--provider-lock` modify on existing experiment disabled | erro de uso / evento auditável | stderr **+ evento de log** | Same reasoning as above — recommend `Event.MODIFY_EXPERIMENT_REFUSED` (new, NORMAL), or a shared `Event.MUTATION_REFUSED(reason=...)` covering both this and line 734 (preferred — one event, one field distinguishing the two refusal reasons, keeps the vocabulary small). |

## `bcllm_model.py` (13 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 421 | `✓ Model variant '...' added to experiment '...'` (standalone `--add-model`) | resultado / evento auditável | stdout **+ evento de log** | Same `Event.MODEL_ADDED` gap as `bcllm_experiment.py:458` — `add_model_action()` is the single shared implementation (used by both standalone and composite flow per the module's own docstring), so wiring `emit_event(Event.MODEL_ADDED, ...)` **inside `add_model_action`** (not in the two call sites) closes both gaps with one change. |
| 423 | `Error: {result.error}` | erro de uso | stderr | Domain error from `add_model_action` (not found / invalid ID / duplicate) — currently has zero log trace anywhere; `add_model_action` itself never logs. Recommend an ERROR-tier event at the same central point as the 421 fix. |
| 470 | `Error: Experiment not found` (`--list-models`) | erro de uso | stderr | Pure lookup failure, no state changed — logging optional/DEBUG only. |
| 476 | `No models in experiment '...'` | resultado | stdout | Empty-result case. |
| 480–482 | List header, column header, separator | resultado | stdout / somente terminal | Header lines are cosmetic (somente terminal); 480 (`Models in experiment: {name}`) is a result-framing line, keep on stdout. |
| 487 | Per-variant row (loop) | resultado | stdout | |
| 508 | `Error: Experiment not found` (`--remove-model`) | erro de uso | stderr | |
| 514 | `Error: Variant not found` | erro de uso | stderr | |
| 519 | `Error: Variant '...' is not in experiment '...'` | erro de uso | stderr | |
| **523** | `✓ Model '...' removed from '...'` | **resultado / evento auditável** | stdout **+ evento de log** | Highest-priority gap in this file: model *removal* has **zero** log trace anywhere today — not even an unstructured `logger.info`, unlike creation paths. Recommend a new `Event.MODEL_REMOVED` (NORMAL tier) — there is no existing unused constant for this one (unlike `MODEL_ADDED`/`EXPERIMENT_CREATED`), so `log_events.py` needs a genuinely new addition here, not just wiring an existing constant. |

## `bcllm_questions.py` (13 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 594 | `messages` loop — reprints every message `add_questions_action` accumulated (progress lines, filter-count line, summary line) | mixed (progresso + resultado, decided per-message at source) | stdout | This single `print(line)` at the *presentation* layer reprints a list built by the *pure* `add_questions_action`. The real classification work belongs to how that list is built (mirrors `bcllm_experiment.py`'s inline equivalents: per-item `✓ Added question...` = progresso, filtered-count = diagnóstico, final summary = resultado) — C2 should classify at the message-construction site, not here, and consider making `add_questions_action` emit structured events directly (it already returns a `messages: tuple[str, ...]` field purpose-built for stdout, decoupled from logging — a good precedent to extend with a parallel `events: tuple[...]` if C2 wants that pattern generalized). |
| 596 | `Error: {result.error}` | erro de uso | stderr | |
| 619 | `Error: Experiment not found` (`--list-questions`) | erro de uso | stderr | |
| 625 | `No questions in experiment '...'` | resultado | stdout | |
| 628–630 | List header, column header, separator | resultado / somente terminal | stdout | Same shape as `bcllm_model.py`. |
| 635 | Per-snapshot row (loop) | resultado | stdout | |
| 655 | `Error: Experiment not found` (`--remove-question`) | erro de uso | stderr | |
| 660 | `Error: Snapshot not found` | erro de uso | stderr | |
| 664 | `Error: Snapshot '...' is not in experiment '...'` | erro de uso | stderr | |
| **668** | `✓ Question '...' removed from '...'` | **resultado / evento auditável** | stdout **+ evento de log** | Same gap class as `bcllm_model.py:523` — question-snapshot removal has zero log trace. `QUESTIONS_ADDED` exists as an unused constant for the *add* path (see `add_questions_action`'s internal `messages`, not currently emitting any event either — see row above) but there is no removal counterpart; recommend a new `Event.QUESTION_REMOVED` (NORMAL). |

## `bcllm_run.py` (25 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 330–332 | `✓ Run created...` + System/User Prompt inherited/custom lines | resultado / evento auditável | stdout **+ evento de log** | `Event.RUN_CREATED` exists, unused — same wiring gap as `EXPERIMENT_CREATED`/`MODEL_ADDED`. Best done centrally inside `add_run_action`, mirroring the `bcllm_model.py:421` recommendation, so both standalone and (future) composite paths inherit it automatically. |
| 334 | `Error: {result.error}` | erro de uso | stderr | Covers both "experiment not found" and the usage-error branch (invalid `--randomization-seed` text, exit code 2) — `add_run_action` has no logging today for either. |
| 357 | `Error: Experiment not found` (`--list-runs`) | erro de uso | stderr | |
| 363 | `No runs in experiment '...'` | resultado | stdout | |
| 366–368 | List header, column header, separator | resultado / somente terminal | stdout | |
| 375 | Per-run row (loop) | resultado | stdout | |
| 395 | `Error: Experiment not found` (`--run <id>`, show) | erro de uso | stderr | |
| 400 | `Error: Run not found` | erro de uso | stderr | |
| 404 | `Error: Run '...' is not in experiment '...'` | erro de uso | stderr | |
| 409–415 | `--run <id>` show: 7 lines (ID/experiment/config block/status) | resultado | stdout | Full result of the show command, same shape as `bcllm_experiment.py:669-675`. |
| 458 | `Error: Experiment not found` (`--remove-run`) | erro de uso | stderr | |
| 463 | `Error: Run not found` | erro de uso | stderr | |
| 467 | `Error: Run '...' is not in experiment '...'` | erro de uso | stderr | |
| **471** | `✓ Run '...' removed` | **resultado / evento auditável** | stdout **+ evento de log** | Soft-delete (`status='removed'`, see the function's own extensive docstring on why hard-delete was replaced) — a lifecycle-changing write with zero log trace. Recommend `Event.RUN_REMOVED` (new — no existing unused constant covers this; `RUN_START`/`RUN_COMPLETE` are execution-lifecycle, not CRUD-lifecycle, so they don't overload cleanly onto this). |

## `bcllm_execute.py` (18 calls)

This module is the **most heavily instrumented** of the nine — it already
has real `logger.info`/`logger.error` calls at nearly every branch
(`EXECUTE_START`, `EXECUTE_ERROR`, `PLAN_LOADED`, `EXECUTE_COMPLETE`), but
**all of them are old-style unstructured `logger.*` pipe-delimited strings,
not `emit_event`** — a gap distinct from, but adjacent to, the print()
classification below. Flagging it here since several rows recommend
reusing these exact log points.

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 289 | `Error: Experiment not found` | erro de uso | stderr | Already paired with `logger.error(f"EXECUTE_ERROR | ...")` at line 288 — that should migrate to `emit_event` (existing `Event.EXECUTE_ERROR`-shaped constant, or reuse `PLAN_VALIDATION_ERROR`), not a new print destination. |
| 306 | `Error: Invalid question specification: {e}` | erro de uso | stderr | Paired with `logger.error` above it — same migration note. |
| 317 | Per-validation-error loop (`Error: {error}`) | erro de uso | stderr | Paired 1:1 with a `logger.error` inside the same loop — already logged, just not structured. |
| 327 | `Error: Invalid retry policy: {e}` | erro de uso | stderr | Paired with `logger.error` above it. |
| 348 | `No pending items to execute. All items completed.` | resultado | stderr | Interesting existing quirk: this is a *success* result (nothing to do), but is printed to **stderr**, not stdout — inconsistent with every other "empty result" message in the CLI (e.g. `bcllm_run.py:363`'s `No runs...` goes to stdout). C2 should decide whether to correct this to stdout or leave it (it does return exit code 0, so scripts checking exit code are unaffected either way; only output-stream-based tooling would notice). |
| 384–388, 390 | `✓ Execution completed` + Runs/Success/Failed/Total summary + per-run item counts (loop) | resultado / evento auditável | stdout **+ evento de log** | Directly duplicates data already in the paired `logger.info(f"EXECUTE_COMPLETE | ...")` at line 381 — migrating that logger call to `emit_event` with fields (`succeeded`, `failed`, `total`, `runs_executed`) gives the audit trail without touching these prints. |
| 396 | `Error: {e}` (`PlannerValidationError`) | erro de uso | stderr | Paired with `logger.error` above it. |
| 400–401 | `Error: Missing required configuration` + hint | erro de uso | stderr | Paired with `logger.error` above it. |
| 405–406 | `Error: Execution failed: {e}` + hint | erro de uso / diagnóstico | stderr | Paired with `logger.error(f"... Unexpected error: {e}")` — this is the module's catch-all `except Exception`; per the crash-safety principle this should also capture `exc_info=True` in the underlying logger call (currently does not), separate from the print/log-destination question. |
| 438 | `\nExecution interrupted by user.` | diagnóstico | stderr | Already paired with `emit_event(..., Event.COMMAND_INTERRUPTED, ...)` at line 437 — this row is **already correctly migrated** (Checkpoint C's own KeyboardInterrupt work); listed here only for completeness of the 163-call inventory. |

## `bcllm_export.py` (7 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 45 | Dispatcher-bug guard variant (own copy, not the shared 8-module one — see note) | diagnóstico | stderr | Nearly identical to the shared pattern but written independently in this file; same `evento de log` recommendation applies (`DISPATCHER_MODE_MISMATCH`). |
| 129 | `Error: Experiment not found` | erro de uso | stderr | Paired with `_logger.error(f"EXPORT_ERROR | ...")` above it — old-style, not `emit_event`; same migration note as `bcllm_execute.py`. |
| 136 | `Error: Run not found` | erro de uso | stderr | Paired with `_logger.error`. |
| 144–147 | `Error: Run '...' does not belong to experiment '...'` | erro de uso | stderr | Paired with `_logger.error`. |
| 164 | `Exported {N} responses and {N} errors to {file}` | resultado / evento auditável | stdout **+ evento de log** | Paired with `_logger.info(f"EXPORT_WRITTEN | ...")` — already logged (old-style); good migration candidate since the fields (`run`, `file`, `responses`, `errors`) are already enumerated in the log message, just not structured. |
| 166 | `print(output_data)` (the exported JSON itself, to stdout) | resultado | stdout | This **is** the command's actual output when `--output-file` is omitted — never touch this one; it's piped/redirected by users (`bcllm ... --export > out.json`). Any future logging must never write to stdout here. |
| 199 | `Error: This module cannot be run directly...` (`if __name__ == "__main__"` guard) | erro de uso | stderr | Only fires under direct `python src/cli/bcllm_export.py` invocation, never through the real `bcllm` entry point — no logger exists yet at this point in that path (nothing has called `setup_logging()`). Lowest priority in this file. |

## `bcllm_review.py` (6 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 36 | Dispatcher-bug guard (shared pattern) | diagnóstico | stderr | See cross-module section above. |
| 83 | `Error: Experiment name cannot be empty.` | erro de uso | stderr | |
| 91, 113 | `Review interrupted by user.` (×2, one per handler: `--review-experiment` and `--review-all`) | diagnóstico | stderr | KeyboardInterrupt handling — this module's own catch, separate from `bcllm.py`'s new outer catch and from `bcllm_execute.py`'s. Recommend the same `Event.COMMAND_INTERRUPTED` treatment C2 already establishes for the other two, for consistency — currently this is the **one remaining KeyboardInterrupt handler in the CLI layer with zero log trace**. |
| 94, 116 | `Error during review: {e}` (×2, one per handler) | erro de uso / diagnóstico | stderr | Catch-all `except Exception` around the interactive Rich TUI (`ReviewUI`) — no logger call at all in this module currently (it has no `_logger`/`get_logger` import). Lowest priority of the file's gaps since the review UI is itself interactive/manual, but still worth an ERROR-tier event for audit completeness. |

## `bcllm_provider.py` (15 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 42 | Dispatcher-bug guard (own copy, MODIFY-specific wording) | diagnóstico | stderr | Same as the shared pattern, independently written. |
| 105 | `Error: Experiment not found` | erro de uso | stderr | This module has **no logger at all** — zero `logging`/`get_logger` import anywhere in the file, the only one of the nine CLI modules with that gap. |
| 115–122 | `Warning: PROVIDER_LOCK is not enabled...` + explanatory line | diagnóstico | stderr | |
| 128 | `No model variants found in experiment '...'` | resultado | stdout | |
| 134 | `Error: OPENROUTER_API_KEY not set in environment` | erro de uso | stderr | |
| 171 | `Warning: {resolution.warning}` (per-variant fallback warning, loop) | diagnóstico | stderr | |
| **183–186** | Provider Resolution Report header + Resolved/Skipped/Failed counts | **resultado / evento auditável** | stdout **+ evento de log** | This command mutates `PROVIDER` in every resolved variant's `config_json` — a real config-affecting write with **zero** log trace anywhere in the file. Highest-priority gap in this module; recommend a new `Event.PROVIDERS_RESOLVED` (NORMAL) with `resolved_count`/`skipped_count`/`failed_count`/`experiment_id` fields, emitted once after the resolution loop — plus per-variant DETAILED-tier events (`Event.PROVIDER_RESOLVED`/`PROVIDER_RESOLUTION_FAILED`, both new) if per-item granularity is wanted later. Since the whole module currently imports no logger, this is a slightly larger C2 unit of work than the equivalent gap in other modules. |
| 189, 192 | "Resolved providers:" header + per-resolved-variant line (loop) | resultado | stdout | |
| 195, 197 | "Failed:" header + per-failed-variant line (loop) | resultado / diagnóstico | stdout | Arguably should be stderr (these are failures), but they're part of the same structured report as the successes above — recommend keeping on stdout for report cohesion, add the event coverage from the 183–186 row instead of splitting the stream. |

## `bcllm_main.py` (1 call)

| Line | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 22 | Dispatcher-bug guard (shared pattern) | diagnóstico | stderr | See cross-module section above. This module otherwise only calls `parser.parse_args()` for `--help` display — no other print() exists. |

## `bcllm.py` (root, 11 calls)

| Line(s) | Snippet | Category | Destination | Notes |
|---|---|---|---|---|
| 297–301 | `_handle_composite_flow`: "Composite flow requires experiment name" | erro de uso | stderr | Pure precondition, before any connection/logger setup — cannot log yet at this point (no `setup_logging()` call has happened). Correctly terminal-only as-is. |
| 311–316 | `--add-questions` without `QUESTIONS_DATASET_PATH` | erro de uso | stderr | Same pre-logging-setup constraint as above. |
| 319–324 | Missing `OPENROUTER_API_KEY` | erro de uso | stderr | Same constraint. |
| 421 | `Error: {e}` (genuine experiment-creation `ValueError`, non-"already exists" branch) | erro de uso | stderr | Inside the `UnitOfWork` block, logger IS available here — currently has no matching `emit_event`/`logger.error` call at all, unlike the sibling `IntegrityError`/generic-`Exception` branches in the same function which do emit `Event.COMPOSITE_FLOW`. Gap: this specific branch should also call `emit_event(logger, Event.COMPOSITE_FLOW, level=logging.ERROR, ...)` for consistency with its neighbors. |
| 490–494 | Generic "unexpected failure" message (the `except Exception` catch-all) | diagnóstico | stderr | **Already correctly paired** with `emit_event(..., Event.COMPOSITE_FLOW, level=logging.ERROR, ...)` and `logger.error(..., exc_info=True)` immediately above (lines 482–489) — deliberately generic per the function's own docstring ("An unexpected exception is NEVER shown to the user with its own text"). No change needed; listed for completeness. |
| 564 | `Error: Unknown v2 module: {module_name}` (`route_to_v2`'s else-branch) | diagnóstico | stderr | Unreachable in practice (same class as the dispatcher-bug guard) — no event exists; low priority given it mirrors the shared pattern's `DISPATCHER_MODE_MISMATCH` recommendation, could reuse the same constant. |
| 585 | `Error: Composite flow requires experiment name.` (`_route_action_module_with_experiment`) | erro de uso | stderr | Logger is available at this point (unlike the 297 case, which runs earlier) — recommend pairing with the same event as line 421's neighbors for consistency, though this branch is effectively unreachable (guarded upstream by the same check at line 296). |
| 628 | `Error: Unexpected module: {module_name}` | diagnóstico | stderr | Same "should never happen" class as line 564. |
| 670 | `Error: No valid command found. Use --help for usage.` (`main()`, before `setup_logging()` runs) | erro de uso | stderr | Runs before logging is initialized in this function — cannot log without reordering `setup_logging()` earlier, which is a real (small) design question for C2, not just a classification note. |
| 688 | `str(e)` (`ModeMatrixError`) | erro de uso | stderr | Logger IS available at this point (`setup_logging()` already ran at line 678) but this branch has no `emit_event` call — gap: should pair with a new `Event.MODE_MATRIX_VALIDATION_FAILED` (NORMAL) or reuse `Event.MODE_ROUTING` with an `error` field. |
| 706 | `\nInterrupted by user.` | diagnóstico | stderr | **Already correctly paired** with `emit_event(..., Event.COMMAND_INTERRUPTED, ...)` at line 705 — part of Checkpoint C's own KeyboardInterrupt work. No change needed. |

## `parser.print_help()` — out of scope, flagged for awareness

Every module's `main()` falls through to `parser.print_help()` (not a
literal `print()` call — `argparse.ArgumentParser`'s own method — so it is
**not** part of the 163-call count above). It appears in
`bcllm_experiment.py:830`, `bcllm_model.py:574`, `bcllm_questions.py:717`,
`bcllm_run.py:522`, `bcllm_provider.py:226`, `bcllm_main.py:94`
(`parser.parse_args()`, which prints help/errors internally on `--help`/
usage errors), plus every module's `--help` handling via argparse
internals. Category: `ajuda`. C2 does not need to migrate this — it is
subsumed by the Typer/Click migration itself (Fase 4), which replaces
argparse's help system wholesale; listed here only so C2's inventory
doesn't silently miss it when scoping each command-group migration.

## `src/cli/presentation/` layer (pre-existing scaffolding, not yet wired in)

Two files exist ahead of the Typer migration and are not part of any live
command path today:

- **`console.py`**: defines `console` (stdout) / `error_console` (stderr)
  Rich `Console` singletons. Zero real print() calls (its one `print\(`
  grep match is the docstring false positive noted in the count
  reconciliation above). Nothing to classify.
- **`errors.py`**: defines `run_command()`, the future exit-code-contract
  wrapper (`docs/contracts/interaction-contracts.md` Section 2: 0/1/2/130).
  Contains one real call, `error_console.print("\n[warning]Interrupted.
  [/warning]")` at line 66 — the `KeyboardInterrupt` handler for whichever
  future Typer command gets wrapped in `run_command`. Category:
  `diagnóstico`. Destination: `stderr` (via Rich, already correct) **+
  evento de log** — once a real command uses `run_command`, this handler
  should also call `emit_event(..., Event.COMMAND_INTERRUPTED, ...)`,
  mirroring exactly what `bcllm.py`'s own `KeyboardInterrupt` catch and
  `bcllm_execute.py`'s already do. Not counted in the 163 since it's not
  builtin `print()` and not yet reachable from any command — C2 should
  pick this up automatically as each command group migrates to Typer and
  starts using `run_command`, not as a separate action.

## Summary

**Confirmed count**: 162 real builtin `print()` calls across the 9
`src/cli` command modules + root `bcllm.py` — one below the design doc's
mid-investigation ~163 estimate once both the 6 docstring false positives
and the 1 non-builtin `error_console.print()` call are excluded (see
Method section above). That non-builtin call exists in the not-yet-live
`presentation/errors.py` and is covered in its own section, not in this
count.

**By category** (162 total, tallied per individual call site, including
each line inside a grouped table row — e.g. the 4 calls spanning
`bcllm_experiment.py:343-346` count as 4, not 1):

| Category | Count |
|---|---|
| erro de uso | 76 |
| resultado | 63 |
| diagnóstico | 22 |
| progresso | 1 (bcllm_experiment.py:635 — see note; most "progress-shaped" lines in bcllm_questions.py are folded into its single `messages` loop, row above, tallied there as resultado for simplicity) |
| ajuda | 0 (excluded — see `parser.print_help()` section) |
| **Total** | **162** |

Per-file category breakdown, for auditability of the totals above:

| File | diagnóstico | erro de uso | resultado | progresso | Total |
|---|---|---|---|---|---|
| `bcllm_experiment.py` | 4 | 33 | 15 | 1 | 53 |
| `bcllm_model.py` | 1 | 5 | 7 | 0 | 13 |
| `bcllm_questions.py` | 1 | 5 | 7 | 0 | 13 |
| `bcllm_run.py` | 1 | 8 | 16 | 0 | 25 |
| `bcllm_execute.py` | 2 | 9 | 7 | 0 | 18 |
| `bcllm_export.py` | 1 | 4 | 2 | 0 | 7 |
| `bcllm_review.py` | 3 | 3 | 0 | 0 | 6 |
| `bcllm_provider.py` | 4 | 2 | 9 | 0 | 15 |
| `bcllm_main.py` | 1 | 0 | 0 | 0 | 1 |
| `bcllm.py` (root) | 4 | 7 | 0 | 0 | 11 |
| **Total** | **22** | **76** | **63** | **1** | **162** |

**By recommended destination**:

- The large majority (`erro de uso` + most `diagnóstico`) stay **stderr**,
  unchanged in stream, though several are flagged above as candidates for
  consolidating multi-line messages into one call during C2's actual
  migration (a Typer/Rich-migration concern, not a logging concern).
- All `resultado` rows stay **stdout**, unchanged in stream.
- **Zero** rows are recommended for `remoção por redundância` outright —
  every print() found serves a real, non-duplicated purpose. (Some
  *logger* calls are redundant with prints in the sense of saying the same
  thing in two formats — e.g. `bcllm_execute.py`'s old-style
  `logger.info`/`logger.error` calls paired with prints — but the fix
  there is migrating the *logger* call to `emit_event`, not deleting the
  print.)
- **Priority list of `evento auditável` gaps** (state-changing operations
  with no structured event today — these are the highest-value C2 targets,
  ranked by how "silent" the gap currently is):

  1. `bcllm_model.py:523` — model removal, **zero** log trace (not even
     old-style). New `Event.MODEL_REMOVED` needed.
  2. `bcllm_questions.py:668` — question-snapshot removal, **zero** log
     trace. New `Event.QUESTION_REMOVED` needed.
  3. `bcllm_run.py:471` — run soft-removal, **zero** log trace. New
     `Event.RUN_REMOVED` needed.
  4. `bcllm_provider.py:183-186` — provider resolution (mutates
     `config_json`), **zero** log trace, and the module has **no logger
     import at all**. New `Event.PROVIDERS_RESOLVED` (+ optionally
     per-item events) needed.
  5. `bcllm_experiment.py:734` / `:770` — refused destructive/mutating
     commands (`--remove-experiment`, `--provider-lock` on existing
     experiment), **zero** log trace of the refusal itself. New
     `Event.MUTATION_REFUSED` (shared, reason-field) recommended.
  6. `bcllm_experiment.py:368`, `bcllm_experiment.py:458`,
     `bcllm_model.py:421`, `bcllm_run.py:330` — creation/add confirmations
     where the **`Event` constant already exists** (`EXPERIMENT_CREATED`,
     `MODEL_ADDED`, `RUN_CREATED`) but is simply never called — pure
     wiring work, no new vocabulary needed, lowest implementation risk of
     the six.

## C2 execution note

Per the user's 2026-08-19 decision, Checkpoint C2 executes the actual
migration **by CLI command group**, aligned with each group's own Typer
migration milestone, to avoid rework in argparse code about to be
replaced:

- **Experiments** (`bcllm_experiment.py`) → Typer Fase 4A/4B (per the
  standing migration plan naming — confirm exact phase letter against
  `docs/status/known-issues.md`/the CLI migration plan doc at whatever
  point C2 begins, since Checkpoint C ran concurrently with that plan and
  phase labels may have shifted).
- **Models** (`bcllm_model.py`) and **Questions** (`bcllm_questions.py`) →
  same or adjacent phase, given their tight coupling to Experiments via
  the composite flow (`bcllm.py::_handle_composite_flow`).
- **Runs** (`bcllm_run.py`) → own phase, shares the composite-flow
  coupling above.
- **Execute** (`bcllm_execute.py`) → already the most-instrumented module;
  C2's main work here is migrating the old-style `logger.info`/
  `logger.error` calls to `emit_event` (flagged throughout its table
  above) rather than touching prints, which are mostly already correctly
  classified as `resultado`/`erro de uso`.
- **Export** (`bcllm_export.py`) → straightforward; the one hard
  constraint is line 166 (`print(output_data)`) must never be touched —
  it is piped/redirected output, not diagnostic.
- **Review** (`bcllm_review.py`) → lowest priority; interactive Rich TUI,
  self-contained, no logger today.
- **Provider** (`bcllm_provider.py`) → needs a logger added from scratch
  (currently has none) alongside its print migration — slightly larger
  unit than the others.
- **Main help** (`bcllm_main.py`) and **root `bcllm.py`** → covered
  incidentally as part of whichever phase touches top-level dispatch;
  `bcllm.py`'s dispatch logic (`route_to_v2`, `_handle_composite_flow`) is
  already mostly on `emit_event` from Checkpoint C itself — only the
  handful of gaps listed in its table above remain.

This document does not implement any of the above. It is the map C2 reads
from when it begins.
