---
type: status
audience: ai
last-validated: 2026-08-20
status: approved-implementing
---

# Design: Checkpoint C — Logging, Observability, Auditability Operacional

**Status: approved, implementation in progress.** All three open
questions in §12 are resolved (`.env`-only `LOG_PROFILE`, unconditional
TRACE chunk logging, `print()` migration split into this checkpoint's
architecture + classification map vs. a separate, not-yet-started
Checkpoint C2 that executes the actual migration by CLI command group
alongside the Typer milestones). This document presents the full
inventory of the current logging implementation, the gaps against the
Checkpoint C requirements (including what capabilities existed in the
legacy/V2-design phase but were never carried forward), and the approved
architecture (depth profiles, event schema, redaction policy, OpenRouter
debug reconciliation, crash-safety/concurrency plan, retention).

---

## 0. Principles (restated, unchanged)

Three responsibilities stay separate:

1. **Database** — authoritative source for configuration, request,
   response, and results (`responses.request_json`, `raw_response`,
   `raw_response_consolidated`, `config_json`, `config`).
2. **Logs** — chronological trail of execution, diagnosis, decisions, and
   correlation. Never a substitute for the DB columns above.
3. **OpenRouter debug/upstream echo** — additional evidence of the
   transformed body forwarded to the provider. Never substitutes the
   original request; both stay distinguishable (already the case as of
   Checkpoint B — see §5).

---

## 1. Inventory of the current implementation

### 1.1 `src/utils/logging_config.py` (the only logging module that exists)

- **Init:** `setup_logging(config)` is called exactly twice in the
  codebase, both in `bcllm.py` — once inside the composite
  `--create-experiment` flow (`bcllm.py:312`) and once in the main
  dispatch path (`bcllm.py:619`). The two call sites are mutually
  exclusive branches of the same invocation, so there is no real
  double-init risk today, but nothing enforces that structurally.
- **Handlers:** two, both wrapped to flush on every `emit()` —
  `FlushingRotatingFileHandler` (file, `DEBUG`+, 10MB/5 backups,
  `RotatingFileHandler` under the hood) and `FlushingStreamHandler`
  (console, `INFO`+). **`FlushingStreamHandler()` is constructed with no
  stream argument, so it defaults to `sys.stderr`** (`logging_config.py:180`,
  Python's own `StreamHandler` default) — console log output already
  goes to stderr today, not stdout. This is a real, useful fact: it means
  the existing log stream and CLI result output (`print()`, mostly to
  stdout) are already physically separated at the OS-stream level, even
  though nothing enforces or documents this on the logging side.
- **Format:** single plain-text formatter,
  `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"` — no JSON
  formatter exists anywhere.
- **Levels:** the 5 stdlib levels (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`),
  validated in `LoggingConfig.validate()`. No concept beyond this.
- **Config sources:** `LOG_LEVEL` and `LOG_FILE_PATH` env vars
  (`logging_config.py:122-138`), both present in `.env`/`.env.example`.
  **No CLI flag exists anywhere** (`--verbose`/`--debug`/`--log-level`) —
  confirmed via repo-wide grep across `src/cli/*.py`, zero matches.
- **"Structured logging":** `get_structured_logger()` (`logging_config.py:210`)
  is a **bare alias** for `get_logger()` — "provided for backward
  compatibility", per its own docstring — there is no JSON output path,
  no structured formatter, nothing. The module's own top-level docstring
  claims "Structured, machine-parseable format" (`logging_config.py:10`);
  this is presently **not true** — the format is plain text, human-only.
  This is a real, pre-existing overclaim in the code's own self-description.
- **Rotation:** size-based only (`RotatingFileHandler`, 10MB, 5 backups).
  No time-based rotation, no per-experiment/per-run file separation.

### 1.2 Existing (informal) log event convention

An `EVENT_NAME | key=value | key=value | ...` convention already exists,
consistently, across most of `src/core/` and `src/api/` — this is
valuable raw material, not a blank slate:

| Module | Events found (file:line) |
|---|---|
| `execution_engine.py` | `EXECUTION_START`/`EXECUTION_COMPLETE` (269, 281), `PROGRESS_MILESTONE` (351), `ITEM_START`/`ITEM_FAILED`/`ITEM_COMPLETE` (392, 402, 793, 739), `PROVIDER_LOCKED` (558), `REASONING_CONFLICT` (564), `MODEL_ERROR` (659), `NO_CONTENT` (666), `VISION_ENABLED`/`VISION_DISABLED` (968, 979) |
| `planner.py` | `PLAN_BUILD_START`/`PLAN_LOADED`/`PLAN_BUILD_COMPLETE` (157, 197, 210), `PLAN_VALIDATION_ERROR` (237, 265, 293, 348), `PLAN_SKIP_EXECUTED` (752 — **idempotency skip already logged**, at `DEBUG`) |
| `async_orchestrator.py` | `ORCHESTRATOR_START`/`ORCHESTRATOR_COMPLETE` (153, 201), `PROGRESS_MILESTONE` (378), plus two un-prefixed free-text lines: `"Writer task failed during cleanup"` (214, via `.exception()`) and `"Abort detected..."` (248, 356) |
| `retry.py` | `RETRY_START`/`RETRY_SUCCESS`/`RETRY_ATTEMPT`/`RETRY_NON_RETRYABLE`/`RETRY_EXHAUSTED` (142, 155, 167, 181, 205, 220, 230) — **already logs attempt number, max_attempts, backoff delay, error_type, error message** on every attempt |
| `client.py` | `API_REQUEST`/`API_RESPONSE` (248, 308), `DEBUG_ENABLED`/`DEBUG_DISABLED` (254, 256), `API_ERROR` (four call sites: 319, 326, 333, 368) |
| `run_finalizer.py` | `RUN_FINALIZED` (151) |
| `async_writer.py` | `WRITE_OK`/`WRITE_FAIL`/`WRITE_RETRY` (146, 155, 187) |
| `result_writer.py` | `WRITE_COMPLETE`/`WRITE_SKIP_IDEMPOTENT` (274, 277, 335), `WRITE_ERROR` (421) |
| `bcllm.py` | `PRECONDITION`, `COMPOSITE_FLOW` (317-318), `APPLICATION_START`, `MODE_ROUTING` (621, 629) — the closest thing to a top-level lifecycle trail that exists today |

**Modules with ZERO logging** (confirmed via direct grep, no `logger`/
`get_logger` reference at all): `src/db/repository.py`,
`src/review/review_ui.py`, `src/core/config_resolver.py`. Configuration
resolution decisions (inheritance, `system-default`, `AUTO` resolution)
and every DB write are currently **completely silent** — this is the
single largest gap against the DETAILED-profile requirement
("configuração resolvida e sua provenance", "decisões de
herança/system-default").

### 1.3 `print()` usage

153 occurrences across `src/cli/*.py` + 10 in `bcllm.py` (163 total).
Overwhelmingly **user-facing CLI result/error output** (what an
experiment was created, what a run's status is, error messages for
`--add-model`/`--create-experiment`/etc.) — not diagnostic logging.
Distribution: `bcllm_experiment.py` (53), `bcllm_run.py` (25),
`bcllm_execute.py` (18), `bcllm_provider.py` (15), `bcllm_model.py` (14),
`bcllm_questions.py` (14), `bcllm_export.py` (7), `bcllm_review.py` (6),
`bcllm_main.py` (1).

**Critical gap:** none of these 163 `print()` calls ever reach the log
file. What the user actually saw on their terminal (a creation
confirmation, an error message, a validation failure) has **no
corresponding record** in `logs/benchmark.log` today — the log file and
the terminal transcript are two disjoint records of the same invocation.

### 1.4 stdout vs. stderr

- Console log handler → `sys.stderr` (confirmed, §1.1).
- `print()` calls are **inconsistent**: many pass `file=sys.stderr`
  explicitly for errors (e.g. `bcllm.py:300`, `:306`, `:612`, `:626`),
  but most result-confirmation prints are bare `print(...)` → stdout by
  default. This roughly matches the stdout=result/stderr=diagnostic
  intent already declared (informally) elsewhere in the Typer-migration
  plan's `interaction-contracts.md` groundwork, but it is **not
  formalized, not enforced, and not tested** at the logging layer.

### 1.5 Correlation / operation_id

**Does not exist anywhere.** Confirmed via repo-wide grep for
`operation_id`, `correlation_id`, `trace_id` — zero matches in `src/`.
There is currently no way to extract "every log line produced by this
one CLI invocation" other than timestamp proximity in the shared log
file. This is the single largest structural gap for the requirement in
§4.

### 1.6 Flush / crash-safety

Both handlers flush on every `emit()` (`logging_config.py:31-38`,
`:48-55`) — this part of the crash-safety story is **already solid** at
the line level: a log line that was written is durable immediately, no
buffering window to lose on a crash.

**Gap:** only `bcllm_execute.py`'s `main()` catches `KeyboardInterrupt`
and returns exit 130 (confirmed — the other 8 CLI modules do not; this
exact gap is already documented in `src/cli/presentation/errors.py`'s own
module docstring as a known, pre-existing issue from before this
checkpoint, not something this investigation is newly discovering). **No
code path anywhere logs an explicit "interrupted" event** — a Ctrl-C
during any command produces either a raw traceback (7/8 CLI modules) or a
silent exit 130 (`bcllm_execute.py`) with nothing written to the log file
recording that an interruption happened.

### 1.7 Concurrency

`AsyncOrchestrator` runs concurrent `asyncio` tasks within a single OS
thread/process — not multi-threaded, not multi-process. Python's stdlib
`logging.Handler` holds an internal lock (`Handler.lock`) around
`emit()`, and — more fundamentally — a single `logger.info(...)` call is
a synchronous, non-`await`-ing operation that runs to completion before
any other coroutine gets control back (no `await` point inside a log
call). So **line-level interleaving of log records is not a real risk
under this concurrency model**, even without the handler lock. This
should be stated explicitly and verified with a real concurrent test
(§8), not just asserted from first principles — worth verifying because
"async" often gets conflated with "needs its own locking," and this
codebase's model doesn't.

### 1.8 Redaction

**Does not exist.** Zero matches for `redact`/`sanitize`/`mask` anywhere
in `src/`. Direct read of every logging call in `client.py` (the module
that has access to `self.api_key` and constructs `headers=`) confirms
**nothing today logs the API key, the `Authorization` header, or any
other credential** — the current state is not violated, but there is no
systematic guard preventing a future change from doing so (e.g. someone
adding a debug line that logs `headers` wholesale). This is a "safe by
absence of the behavior," not "safe by policy" — exactly the gap a
redaction policy closes.

### 1.9 Retries and failures (`src/core/retry.py`, read in full)

Already logs, on every attempt: `RETRY_START` (max_attempts),
`RETRY_ATTEMPT` (attempt number, `max_attempts`, backoff delay formatted
to 2 decimals, the error message), `RETRY_SUCCESS` (attempt count),
`RETRY_NON_RETRYABLE` (attempt, `error_type`), `RETRY_EXHAUSTED` (total
attempts, last error message). The `log_context` string passed in from
`execution_engine.py:706` is `f"run={item.run_id}|variant={item.variant_id}|snapshot={item.snapshot_id}"`
— i.e. retries are already correlated to run/variant/snapshot, just not
to a top-level operation_id (which doesn't exist yet at all, §1.5).

### 1.10 Payload / response / chunk logging

**Not duplicated into logs today.** Only summary fields (model, token
counts, cost, latency, `finish_reason`) appear in `API_RESPONSE`/
`ITEM_COMPLETE` lines. The full request payload, full response body, and
raw SSE chunks are **never** written to the log file — they live only in
`responses.request_json`/`raw_response`/`raw_response_consolidated`
(DB columns). This is good hygiene already (no duplication risk between
log and DB today) but means the TRACE profile's "payload canônico
redigido" / "upstream echo redigido" is a genuinely new capability, not
something merely disabled.

### 1.11 Cost / tokens / provider / latency

Confirmed present today: `client.py:308-309` (`API_RESPONSE` —
`latency_ms`, `tokens` (`total_tokens`, prompt+completion), `finish_reason`,
not cost); `execution_engine.py:739-740` (`ITEM_COMPLETE` — `latency`,
`tokens`, `cost`). Provider appears at `PROVIDER_LOCKED`
(`execution_engine.py:558-560`) when resolved, but the *effective*
provider actually used (as reported back by OpenRouter in the response,
distinct from the *requested* one) is **not** currently logged anywhere
— only persisted in `raw_response`/`raw_response_consolidated`
(`consolidate_streaming_response` already extracts a top-level
`"provider"` field, confirmed in Checkpoint B's investigation). Worth
carrying into a log line for NORMAL-profile "provider solicitado e
efetivo quando disponível," per the user's explicit requirement.

### 1.12 Documentation vs. code

`docs/reference/module-structure.md`'s one-line description
("Logging setup (file + console, rotation)") is accurate as far as it
goes but does not mention the absence of real structured/JSON output —
minor, not a contradiction. The more substantive divergence is
**internal to the code itself**: `logging_config.py`'s own module
docstring claims "Structured, machine-parseable format" (line 10) when
the actual format is plain text — this should be corrected as part of
this checkpoint regardless of which architecture is approved, since it's
presently false.

### 1.13 What Checkpoint B already solved (do not re-litigate here)

Per the prior checkpoint (`docs/status/model-seed-checkpoint-b-design.md`):
the single canonical payload (`build_chat_completion_payload`) already
guarantees `request_json` and the real HTTP body are identical by
construction; `OPENROUTER_DEBUG_ENABLED` already flows through that same
canonical payload (§5 here reconciles the *logging* angle on top of
that, not the payload-fidelity angle, which is closed); secrets are
already confirmed absent from `request_json`/the JSON body (they live
only in `httpx`'s `headers=`); prompt/config immutability documentation
was already corrected. Checkpoint C does not need to re-solve any of
this — only extend it into the logging layer.

### 1.15 Legacy (V1) and "to-be" (V2 design) capability comparison

Per the explicit request to identify which capabilities of the previous
version still exist and which were never carried forward. Two archived
sources ground this: the legacy implementation
(`Arquivos_Mortos/src_legacy/utils/logging_config.py`) and the V2 "to-be"
design doc (`docs/.archive/pre-restructure/architecture/to-be/02-logging-system-architecture.md`).
**Note on stale docs:** `docs/Nao_Apagar-Temporarios_do_Usuario/v2-current/02-logging-system.md`
and `docs/architecture/gap-reports/02-logging-system-gap.md` both assert
"V2 has NO logging system, 0 logging imports" — true when written, **false
today**: `src/utils/logging_config.py` exists and is wired in. Both docs
are stale snapshots, not current state; flagged for correction in §10.2.

| Capability | Legacy (V1) | V2 "to-be" design | Current (`logging_config.py`) |
|---|---|---|---|
| Rotating file handler, flush-per-write | ✅ | ✅ kept | ✅ identical, same defaults |
| Console handler, INFO+ only | ✅ | ✅ kept | ✅ |
| `LOG_LEVEL`/`LOG_FILE_PATH` env config | ✅ | ✅ kept | ✅ |
| Hierarchical component loggers | ✅ | ✅ kept | ✅ (`get_logger`) |
| **`log_initialization_summary()`** (fixed-width execution-context header logged at startup) | ✅ | ✅ kept, example call shown in the to-be doc | ❌ **does not exist in the current module at all** |
| Progress milestones (25/50/75/100%) | ✅ | ✅ kept | ⚠️ exists (`execution_engine.py`'s `PROGRESS_MILESTONE`), but as an ad-hoc event in a core module, not through `logging_config.py` as a first-class capability |
| Structured `EVENT | k=v | k=v` convention | ❌ (V1 used free-form sentences) | not explicitly specified | ✅ de facto exists (§1.2), but uncentralized |
| JSON/structured machine-parseable format | ❌ | 📋 proposed as new (`LOG_FORMAT=json` env toggle) | ❌ not implemented (§1.1) |
| Context injection (`ContextFilter`, auto experiment_id/run_id on every line) | ❌ | 📋 proposed as new | ❌ not implemented — context is manual, per-message |
| Per-module log levels (`LOG_LEVEL_SRC_API=DEBUG`, etc.) | ❌ | 📋 proposed as new | ❌ not implemented |
| Correlation/operation IDs | ❌ | ❌ not proposed either | ❌ genuinely new ground, no precedent |
| Depth/verbosity profiles (MINIMAL/NORMAL/DETAILED/TRACE) | ❌ | ❌ not proposed either | ❌ genuinely new ground, no precedent |
| Redaction of secrets | ❌ | ❌ not addressed either | ❌ genuinely new ground, no precedent |

**What this means concretely:** two legacy/proposed capabilities are worth
reclaiming as part of this checkpoint even though the user didn't name
them explicitly — `log_initialization_summary()` (a one-time
execution-context header at command start, which overlaps naturally with
the new `COMMAND_START` event in §2's MINIMAL profile — proposing to fold
it into that event rather than resurrect it as a separate function, since
building it as its own thing again would duplicate what `COMMAND_START`
already needs to carry) and context injection via a `logging.Filter`
(worth adopting as the mechanism that threads `operation_id` through
every line automatically, §4, rather than requiring every call site to
pass it manually). Three capabilities — correlation IDs, depth profiles,
redaction — have **no historical precedent in this codebase at all**; they
are new ground, which matches the user's request treating them as the
core of this checkpoint rather than as gaps in something that used to
exist.

### 1.16 Additional known-issues.md findings (cross-referenced)

- **"⚠️ Logging Context Consistency"** (Technical Debt section) is a
  standing, still-open entry: "Context format varies across modules... No
  structured logging schema (e.g., JSON logs)... Suggested Fix:
  Standardize log context format across all modules." This checkpoint's
  centralized `event_name` vocabulary + JSONL schema (§3) is precisely
  that suggested fix — this entry should be moved to Resolved Issues once
  implemented and verified, not left standing alongside a new
  architecture that already addresses it.
- **"✅ Logging System Implementation"** (Resolved Issues, dated 2026-04,
  pre-documentation-restructure) has no regression-test citation or
  verification baseline, unlike every current-era Resolved Issues entry
  in that file. Once this checkpoint's own Resolved Issues entry is
  written, this older entry should be superseded/cross-referenced rather
  than left as an unverified, free-standing claim.

### 1.17 Gaps summary (what §2-11 below need to build)

| Requirement | Current state |
|---|---|
| `operation_id`/correlation across a CLI invocation | **0% — does not exist** |
| Structured JSONL output | **0% — `get_structured_logger` is a bare alias, no JSON formatter** |
| Depth profiles (MINIMAL/NORMAL/DETAILED/TRACE) | **0% — only the 5 stdlib levels, no profile concept** |
| Centralized, stable `event_name` vocabulary | **~40% — an informal `EVENT \| k=v` convention exists in 8 modules, but scattered as free-text f-strings, no single source of truth, 3 core modules have zero logging** |
| Redaction policy | **0% — safe today by absence of the behavior, not by policy** |
| CLI result output reaching the log file | **0% — 163 `print()` calls, all outside the logger** |
| Retry/failure detail (attempt, delay, error) | **Already present** (`retry.py`) — reuse as-is |
| Idempotency-skip logging | **Already present** (`PLAN_SKIP_EXECUTED`, `WRITE_SKIP_IDEMPOTENT`) — reuse as-is |
| Crash-safe flush | **Already present** (both handlers flush per line) — reuse as-is |
| `KeyboardInterrupt` handling + logging | **Partial** — 1/8 CLI modules catches it (exit 130), 0/8 log an interrupted event |
| Payload/debug fidelity in the DB | **Already solved** (Checkpoint B) — extend into logs, don't rebuild |

---

## 2. Depth profiles

### Design approach

Profiles are **cumulative** (`NORMAL` ⊇ `MINIMAL`, etc., as the user
specified) and control **which events are emitted**, not the stdlib
`logging` level directly — though each profile has a natural default
stdlib-level floor, kept separate as two independently-configurable
knobs (see §2.5) so a profile can still be raised/lowered without
changing what data the event carries.

**Hard constraint honored:** lifecycle start/end, warnings, and errors
are **never gated by profile** — they emit at every profile, including
MINIMAL. Profiles only ever *add* detail on top of that floor; nothing
in DETAILED/TRACE can be used to suppress a MINIMAL-mandatory signal.
This is enforced structurally in §3 (event schema), not by convention.

### MINIMAL

- `COMMAND_START` / `COMMAND_END` — `operation_id`, `command` (the
  action, e.g. `add-model`, `execute`), `exit_code`, `experiment_id`/
  `experiment_name` and `run_id` when applicable, a one-line summary.
- All `WARNING`+ events, always, regardless of their "natural" profile
  (a DETAILED-tagged event that happens to be a warning still surfaces
  at MINIMAL — see §3's severity-floor rule).

### NORMAL (MINIMAL +)

- Entity lifecycle: `EXPERIMENT_CREATED`, `MODEL_ADDED`, `RUN_CREATED`,
  `QUESTIONS_ADDED`, etc. (one event per `--add-*`/creation action).
- `PLAN_BUILD_START`/`PLAN_LOADED`/`PLAN_BUILD_COMPLETE` (already exist,
  reused verbatim).
- `RUN_START`/`RUN_COMPLETE`, `VARIANT_START`/`VARIANT_COMPLETE` (new —
  today only per-*item* start/complete exists, not per-run/per-variant
  rollups distinct from the existing `EXECUTION_START`/`COMPLETE`).
- `ITEM_START`/`ITEM_COMPLETE`/`ITEM_FAILED`, `RETRY_ATTEMPT`/
  `RETRY_EXHAUSTED` (already exist, reused verbatim).
- `PROVIDER_REQUESTED`/`PROVIDER_EFFECTIVE` (new — closes the §1.11 gap:
  requested vs. actually-used provider, when the response reports one).
- `tokens`, `cost`, `duration_ms` on completion events (already exist on
  `ITEM_COMPLETE`, extended to `RUN_COMPLETE` as an aggregate).

### DETAILED (NORMAL +)

- `CONFIG_RESOLVED` — one event per resolved configuration value at
  Experiment/Run/Model-Variant creation, with its provenance (`source`:
  `cli`/`env`/`experiment`/`system_default`) — **new**, closes the
  `config_resolver.py`-has-zero-logging gap (§1.2). Not one line per
  field (too noisy) — one event per creation action, carrying a compact
  `resolved: {KEY: {value, source}, ...}` map.
  as many fields as are relevant to that config resolution result.
- `INHERITANCE_DECISION` / `SYSTEM_DEFAULT_APPLIED` — explicit event when
  a value breaks inheritance via `system-default`, or when `AUTO` is
  resolved to a concrete Randomization Seed at Run creation.
- Planner counts: total variants/snapshots/runs/items considered,
  already computed for `PLAN_LOADED` (`planner.py:197-198`) — extend
  that event's fields rather than add a new one.
- `PLAN_SKIP_EXECUTED` / `WRITE_SKIP_IDEMPOTENT` (already exist, reused
  verbatim — this is exactly the "skip por idempotência" requirement).
- `request_json`'s **fingerprint** (a short hash, not the payload
  itself — see §3.3) on each attempt.
- `PARSE_DECISION` — parser confidence/selected-answer decision (new,
  currently invisible outside the DB).
- `RANDOMIZATION_APPLIED` — seed used, whether shuffling occurred (new;
  today only visible via the persisted `option_letter_map`).
- Full retry/finalization detail (already present, reused).

### TRACE (DETAILED +)

- The canonical request **payload itself, redacted** (not fingerprinted)
  — same object `request_json` is derived from, passed through the
  redaction policy (§6) before being logged.
- Response/debug metadata relevant fields, and the **upstream echo**
  (`debug.echo_upstream_body`), redacted.
- SSE chunks/events, when needed for forensic debugging of a specific
  failure (opt-in detail, not unconditionally dumped every attempt —
  see open question in §12).
- Intermediate parsing results (raw regex/pattern matches before the
  final `selected_answer`/confidence decision).
- Sufficient internal detail for forensic investigation — this is the
  only profile allowed to be this verbose, and it is never the default
  (see §9's retention discussion — TRACE logs are large and short-lived
  by design).

### 2.5 Two independent knobs, not one

`LOG_LEVEL` (stdlib severity: what threshold a handler emits at) and the
new `LOG_PROFILE` (MINIMAL/NORMAL/DETAILED/TRACE: which events exist at
all) are **orthogonal**, matching how `OPENROUTER_DEBUG` must stay
distinct from both (§5). A `WARNING` fires regardless of profile; a
DETAILED-only event fires only if `LOG_PROFILE >= DETAILED`, and then
still respects `LOG_LEVEL` for whether it's actually written (a
DETAILED-profile event logged at `DEBUG` severity is silent if
`LOG_LEVEL=INFO`, profile aside). Proposed default: `LOG_PROFILE=NORMAL`,
`LOG_LEVEL=INFO` (unchanged from today).

---

## 3. Event schema and vocabulary

### 3.1 Centralized event names

A new module, `src/utils/log_events.py`, defines every `event_name` as a
named constant (e.g. `class Event: EXECUTION_START = "execution_start"`,
or a plain `Enum` — exact shape is an implementation detail for the
approved-step phase, not a design decision needed now). No module is
allowed to construct an event name as an ad-hoc string literal anymore —
existing free-text names (`EXECUTION_START`, `RETRY_ATTEMPT`, etc.) are
migrated into this module verbatim (same names, now centralized) rather
than renamed, to avoid an unnecessary second rename on top of Checkpoints
A/B's already-large diffs.

### 3.2 Two derived outputs from one event

Every log call goes through **one** internal emission function that
produces:
1. **Human line** — today's existing plain-text format, unchanged in
   spirit (`EVENT | k=v | k=v`), still readable in a terminal/editor.
2. **JSONL line** — one JSON object per line, written to a **separate**
   file (not interleaved with the human file — simpler to reason about
   and to grep with `jq`/`json.loads` per line without a mixed-format
   parser). Field set per §3.3.

This mirrors the "single canonical construction, two destinations"
discipline already established for the request payload in Checkpoint B
— same principle, applied to log events instead of API payloads: one
internal event object, two serializations, never two independent
constructions.

### 3.3 Per-event-family schema (not all fields on all events)

Common envelope (present on every JSONL event, human line has an
equivalent compact rendering):

```json
{
  "timestamp": "2026-08-20T14:03:11.482391Z",
  "level": "INFO",
  "event_name": "item_complete",
  "operation_id": "op_3f9a2b1c",
  "schema_version": 1
}
```

Family-specific fields (added on top of the envelope, only where
applicable — never forced to `null` for irrelevant families):

| Family | Extra fields |
|---|---|
| Command lifecycle | `command`, `exit_code`, `experiment_id`, `experiment_name` |
| Entity creation | `experiment_id`, `run_id`, `variant_id`, `snapshot_id` (whichever was created) |
| Plan/execution | `experiment_id`, `run_id`, `variant_id`, `snapshot_id`, `question_id`, `attempt_number` |
| API call | `provider` (requested/effective), `model_id`, `duration_ms`, `outcome` |
| Result | `response_id`/`error_id`, `outcome`, token/cost fields when available |
| Retry | `attempt_number`, `max_attempts`, `delay_ms`, `error_type` |
| Config resolution (DETAILED) | `resolved` (map of key → `{value, source}`) |
| Payload (TRACE only) | `payload_fingerprint` always; full redacted `payload`/`debug_echo` only at TRACE |

`schema_version` is a flat integer on every JSONL line (not a file-level
header) — see §9 for why (log files rotate/split; a version needs to
travel with each line, not live only at the top of a file that might get
truncated).

### 3.4 Severity floor rule (structural, not conventional)

The emission function itself refuses to suppress `WARNING`/`ERROR`/
`CRITICAL` regardless of the caller's declared profile tag — the
profile check only applies to events tagged `INFO`/`DEBUG`. This is
implemented as a single `if severity >= WARNING or profile_allows(tag): emit()`
guard in the one shared emission path, not repeated per call site — so
"can this be silenced" is answered once, centrally, satisfying "Não
permita desativar warnings, erros críticos... sem apresentar antes a
justificativa" structurally rather than by code review discipline alone.

---

## 4. `operation_id` / correlation design

- Generated **once per CLI invocation**, at the very start of `bcllm.py`
  (`cli_main()`/`main()`, before argument parsing) — short, opaque,
  collision-resistant (e.g. `op_` + 8 hex chars from `uuid4`, matching
  the existing `exp_`/`run_`/`var_`/`snap_` ID style already used
  throughout `src/db/`).
- Passed down explicitly (no global/contextvar magic, matching this
  project's established anti-global-state convention from
  `logging_config.py`'s own stated principle "No global logger state") —
  threaded through the same call chain that already carries
  experiment/run/variant identifiers, not a new parallel mechanism.
- Every event emitted during that invocation carries it. A `--execute`
  spanning many concurrent items/retries still shares one
  `operation_id` — this is what makes "find everything from this one
  command" possible for the first time.
- Does **not** replace `experiment_id`/`run_id`/etc. — it's the
  invocation-level correlator; the entity IDs remain the
  execution-level/data-level correlators. Both are needed together (an
  `operation_id` answers "what happened during this command run"; a
  `run_id` answers "what happened to this Run," possibly across several
  `--execute` invocations resuming it).

---

## 5. OpenRouter debug vs. `LOG_LEVEL` — reconciliation

**These are already two independent configurations in the code**
(`OPENROUTER_DEBUG_ENABLED` → `OpenRouterClient.debug_enabled` vs.
`LOG_LEVEL` → stdlib logger threshold) — confirmed via direct read, they
never share a code path today. The remaining question this checkpoint
answers is whether `OPENROUTER_DEBUG_ENABLED`'s *effect on the payload*
is adequately auditable, and whether the *logging layer* should surface
anything about it beyond what Checkpoint B already guarantees at the DB
level.

### 5.1 Already satisfied by Checkpoint B (not re-litigated)

- `debug_enabled` flows through the ONE canonical
  `build_chat_completion_payload(..., debug_enabled=...)` call —
  `request_json` always accurately reflects whether `debug` was
  requested, because there is no second payload construction left to
  diverge from it.
- **Identical configuration → identical request**, already proven by
  `tests/unit/core/test_request_fidelity.py::TestRepeatedAttemptFidelity`
  (two independent runs with the same `ModelConfig` produce byte-identical
  payloads) — this is exactly the "configuração idêntica deve continuar
  produzindo request idêntico" requirement, already covered by an
  existing, passing test. No new test needed for this specific claim;
  cited here as evidence, not re-proposed.
- The upstream echo (response-side) is already kept structurally
  distinct from `request_json` (request-side) — two different DB columns,
  confirmed by `test_request_fidelity.py::TestUpstreamEchoDistinctFromRequestJson`.

### 5.2 Evidence reused from the Checkpoint B smoke test (not re-run — artifacts sufficient)

Full raw artifact:
`debug_smoke_test_raw.json` (session scratchpad, 2 real calls against
`google/gemini-2.5-flash-lite` via `google-ai-studio`, `MODEL_SEED=42`,
`temperature=0`, `max_tokens=8`). Re-verified against the raw JSON for
this checkpoint (not re-run — the user's own instruction was to reuse
artifacts if sufficient, and they are):

| Compared | `debug=false` | `debug=true` | Difference |
|---|---|---|---|
| Payload sent | 7 keys (`model`, `messages`, `stream`, `max_tokens`, `temperature`, `seed`, `provider`) | Same 7 keys **+** `debug: {echo_upstream_body: true}` | Exactly one added key, nothing else |
| Tokens | `prompt_tokens=37`, `completion_tokens=1` | Identical | None |
| Cost | `4.059e-06` | Identical | None |
| Provider (response) | `"Google AI Studio"` | Identical | None |
| Streaming events | 3 chunks | 4 chunks (one extra: the debug chunk, `choices: []`) | +1 chunk, response-side only |
| `MODEL_SEED` forwarded | n/a (not requested) | `42` appeared inside `echo_upstream_body.generationConfig.seed` | Confirms forwarding; **no field anywhere confirms the provider honored it** |
| Metadata (`id`, `object`, `created`, `model`) | Present | Present, identical | None |

**Conclusion, unchanged from Checkpoint B, restated for this checkpoint's
record:** `debug` adds exactly one thing — the upstream-transformed
request echo. It does not gate cost/tokens/provider (already available
without it). It never confirms a seed was *honored*, only *forwarded*.

### 5.3 What this checkpoint adds on top: logging-layer surfacing

- **`LOG_PROFILE=TRACE`** is the only profile that logs the redacted
  debug echo as an actual log line (§2's TRACE definition) — at
  MINIMAL/NORMAL/DETAILED, the fact that debug was requested is visible
  only via the `payload_fingerprint`-bearing event already logging
  whether the request payload's key set included `debug` (a boolean,
  not the echo content) — i.e. DETAILED can answer "was debug on for
  this attempt" without paying TRACE's verbosity cost.
- **Scope rule (the "regra normativa clara de escopo" the user
  requested):** `OPENROUTER_DEBUG_ENABLED` is a per-`OpenRouterClient`-
  instance, per-process setting (constructor argument, read once at
  process start from the env var) — it is **not** stored in
  `experiment.config_json`/`run.config`/`variant.config`, and therefore
  is **not** part of the frozen configuration hierarchy those entities
  guarantee. This is a deliberate, existing design choice (confirmed in
  Checkpoint B, unchanged here): debug mode is an operational/diagnostic
  toggle for a given `--execute` invocation, not an experimental
  variable — same category as `LOG_LEVEL`/`LOG_FILE_PATH`, not the same
  category as `MODEL_SEED`/`RANDOMIZATION_SEED`. Two experiments/runs
  with identical frozen config can be executed once with debug on and
  once with debug off — this does not violate immutability, because
  debug never was, and is not proposed to become, part of what those
  entities freeze. This should be stated explicitly in
  `docs/contracts/system-default-semantics.md` or
  `configuration-hierarchy.md` (§10) so it stops being tribal knowledge.

### 5.4 Default: proposal, awaiting decision (not changed here)

**Recommendation: keep default OFF**, unchanged from Checkpoint B's
already-approved recommendation — reasons unchanged (OpenRouter's own
"not for production" guidance; provider-specific echo shape would
produce structurally inconsistent audit data across a multi-provider
benchmark if defaulted on). This checkpoint does not reopen that
decision; it only adds the logging-layer visibility in §5.3 on top of
it. Flagging again here only because the user's message explicitly
asked the question to be answered again in this checkpoint's context —
the answer is the same, for the same reasons, now with the added
TRACE-profile logging story.

---

## 6. Redaction policy

### 6.1 Central chokepoint

One function, `src/utils/redaction.py::redact(obj)`, applied **inside
the single emission path** (§3.2) before either the human line or the
JSONL line is constructed — never at the call site, never optionally.
No log call anywhere bypasses it. This mirrors the "one canonical
construction" discipline used for the request payload and for events
themselves — redaction is not a per-caller responsibility.

### 6.2 What gets redacted

Recursive, structure-preserving redaction (dict keys, nested dicts,
lists, and string scanning for patterns) covering, at minimum:
- Known secret-shaped keys, case-insensitive: `api_key`, `apikey`,
  `authorization`, `cookie`, `set-cookie`, `token`, `secret`,
  `password`, `x-api-key`.
- `Authorization: Bearer ...` and similar header-value patterns found
  inside strings (not just dict keys) — covers a secret accidentally
  interpolated into a free-text message, not only structured dicts.
- Credentials embedded in URLs (`https://user:pass@host/...`).
- Exception string representations (`str(exc)`) are passed through the
  same function before being interpolated into a log message — an
  `httpx`/`sqlite3` exception message could theoretically echo a
  connection string or header.

### 6.3 What must never change

Redaction applies **only** to what is about to be written to a log
handler. It never touches: the in-memory objects being logged (the
caller's own `payload`/`response` variables are passed by value into the
redaction function, which returns a new redacted copy — never mutates
in place), and never touches anything persisted to the database (DB
columns are written from the original, non-redacted objects, matching
the existing separation already established in Checkpoint B between
`request_json` and log output).

---

## 7. Fidelity and immutability (mostly inherited from Checkpoint B, restated for completeness)

- The one canonical payload continues to be both serialized into
  `request_json` and handed to transport, unmodified — Checkpoint C adds
  nothing new here except: logs record a `payload_fingerprint` (a short
  hash, e.g. first 12 hex chars of SHA-256 over the canonical JSON
  string) at DETAILED+, so a log line can be correlated back to the
  exact DB row's `request_json` without re-logging the full payload at
  every level below TRACE.
- Experiment/Run/Model Variant configuration remains frozen — unchanged,
  Checkpoint C's `CONFIG_RESOLVED` event (§2, DETAILED) is a **read-only
  observation** of the resolution that already happened in
  `ConfigResolver`, emitted once at creation time — it does not
  introduce a new mutation path or a new place configuration could
  drift from what's frozen in `config_json`/`config`.
- System Prompt / User Prompt immutability for both Experiment and Run —
  already corrected in `docs/contracts/immutability.md` (Checkpoint B).
  Re-audited in §10's doc list below to confirm no regression and to
  catch any doc this checkpoint's own changes might touch.

---

## 8. Crash-safety and concurrency — investigation results and test plan

### 8.1 What already holds (verified by reading the code, not assumed)

- Per-line flush on both handlers (§1.6) — a written line survives a
  crash immediately after `emit()` returns.
- `logging.Handler.lock` + no `await` inside a synchronous `logger.*()`
  call means concurrent `asyncio` tasks cannot interleave partial lines
  under this system's single-process, single-thread-for-logging model
  (§1.7) — this needs a real test (below), not just this argument, since
  it's exactly the kind of claim worth verifying rather than trusting.
- `ResponseRepository`/`ResultWriter`'s incremental-write, idempotent
  persistence policy is **not touched** by this checkpoint (explicit
  user instruction) — logging failures must never be able to affect it.

### 8.2 Gaps to close

- No `operation_id`-tagged "interrupted" event exists anywhere (§1.6) —
  new `COMMAND_INTERRUPTED` event, emitted by whichever mechanism ends
  up wrapping `KeyboardInterrupt` (today only `bcllm_execute.py`; the
  Typer migration's `run_command()` in `src/cli/presentation/errors.py`
  is the eventual home for the other 7 modules — Checkpoint C's logging
  call belongs inside that existing exit-130 path, not a new one, to
  avoid a second competing interrupt-handling mechanism).
- No test today proves a log handler failure (disk full, permission
  denied, file can't open) doesn't crash or corrupt the *execution*
  itself — needs an explicit test asserting execution completes (and
  the DB write happens) even if the logging handler raises.

### 8.3 Test plan (see also §10)

- Concurrent-task log-line integrity: run N concurrent simulated items
  through the real logging setup writing to a real temp file, assert
  every line in the file is valid (parses as one complete
  human/JSONL line each, none truncated/merged).
- Flush-on-crash: write a line, kill the process (or simulate via a
  handler that raises after `emit()`'s `super().emit()` but verify the
  flush already happened), confirm the line is on disk.
- `KeyboardInterrupt` mid-execution: confirm exit 130, confirm
  `COMMAND_INTERRUPTED` is the last event, confirm no DB row is left in
  an inconsistent state (this last part is `ResultWriter`'s existing
  contract, only asserted here, not re-implemented).
- Disk-full / permission-denied on the log file: confirm this raises a
  **visible, exit-non-zero, non-silent** error rather than being
  swallowed, but does **not** cause a duplicate execution/write on
  retry (ties directly to the idempotency contract — a logging failure
  must never look like "the item wasn't attempted" to the resume logic).
- Rotation during an active run: confirm no line is lost/split across
  the rotation boundary (`RotatingFileHandler`'s own rotation is atomic
  per-line since it only rotates between `emit()` calls, but this should
  be verified with a real test, not assumed from reading stdlib source).

---

## 9. Retention and organization

- **Location:** unchanged root (`LOG_FILE_PATH`, default
  `./logs/benchmark.log`) for the human-readable file; a sibling JSONL
  file at a deterministic, derived name (e.g. `./logs/benchmark.jsonl`,
  or a per-`LOG_FILE_PATH`-stem `.jsonl` sibling) — not a second,
  independently-configured path, to avoid the two ever pointing at
  different directories by accident.
- **Global vs. per-experiment:** propose staying **global by default**
  (one running log across all invocations, as today) — per-experiment
  files would require inventing a new file-naming/rotation scheme this
  checkpoint doesn't need, when `operation_id`/`experiment_id` fields on
  every JSONL line already make "find everything for experiment X"
  a `grep`/`jq` filter over the global JSONL file, not a filesystem
  problem. Revisit only if real usage shows the global file becomes
  unwieldy — not solved speculatively now.
- **Rotation/retention:** keep the existing size-based rotation
  (10MB/5 backups) as the default; add compression of rotated backups
  as an **opt-in** (`.gz` via `RotatingFileHandler`'s own rotator hook)
  rather than default-on, since compressed rotated files can't be
  `tail -f`'d or grepped directly without decompression first.
- **No destructive cleanup policy** is proposed or implemented — matches
  the explicit instruction. Retention beyond the rotation backup count
  is left to the user's own OS-level log management, same as today.
- **Schema version:** carried per-JSONL-line (§3.3), not file-level —
  survives rotation/truncation naturally.
- **Locating logs for an entity:** `grep operation_id=... ` on the human
  file, or `jq 'select(.experiment_id=="...")' ` on the JSONL file — no
  new index/lookup structure proposed; the DB remains the place to look
  up IDs in the first place (a response row already has `run_id`/
  `variant_id`/`snapshot_id` — the JSONL file is filtered by those same
  values, not a separate ID space).

---

## 10. Tests and documentation audit

### 10.1 Tests (see also §8.3)

- One test per depth profile — confirms MINIMAL emits only its floor,
  NORMAL/DETAILED/TRACE are each strictly cumulative (every event a
  lower profile emits, a higher profile also emits, plus its own additions).
- Schema tests — every event family's required/optional field set
  matches §3.3, `schema_version` present on every JSONL line.
- `operation_id` — same value across every event in one simulated
  invocation; different value across two separate invocations.
- stdout/stderr — confirm log lines never appear on stdout (console
  handler stays on stderr, already true — pin it with a test so a
  future change can't silently flip it).
- `payload_fingerprint` — same canonical payload → same fingerprint;
  changing one field → different fingerprint.
- `OPENROUTER_DEBUG` on/off — TRACE-profile log line presence/absence of
  the redacted echo, matching §5.3's scope rule; reuses
  `test_request_fidelity.py`'s existing debug on/off cases as the
  payload-side half of this proof, adds the logging-side half new.
- Redaction — parametrized over: a secret in a flat string, a secret in
  a nested dict, a secret in a header dict, a secret in a URL, a secret
  inside an exception's `str()`, a secret inside a payload passed to
  TRACE, a secret inside an upstream echo. Assert redacted output never
  contains the literal secret value; assert the original in-memory
  object and the DB-persisted value are untouched (not redacted there).
- Concurrency / crash / rotation / handler-failure — per §8.3.
- `request_json` == payload sent — already covered by Checkpoint B's
  `test_request_fidelity.py`; add one assertion there (or a thin new
  test) that a `payload_fingerprint` logged for that same attempt
  matches a fingerprint independently computed from `request_json`.
- No response duplication — reuse/extend the existing idempotency tests
  (`test_execution_contract.py`) with a logging layer active, confirming
  logging doesn't introduce a second write path.
- `MODEL_SEED` / `RANDOMIZATION_SEED` logged separately — a log-line
  version of `test_seed_independence.py`'s DB-level proof: confirm the
  two never appear under the same field name or in the same event in a
  way that could be confused (e.g. no event has a bare `"seed"` field
  that could be either).
- Frozen prompts — a test asserting no code path logs a "prompt updated"
  event for an existing Experiment/Run (there is no such path today; this
  pins that absence, matching Checkpoint B's own precedent of testing
  a negative/absence claim, not just positive behavior).
- Logs don't mutate scientific data — a test that runs an item with
  every profile from MINIMAL to TRACE and asserts the persisted
  `ExecutionResult`/DB row is byte-identical regardless of profile.

### 10.2 Documentation audit (found during this investigation, to fix during implementation)

- `docs/contracts/data-auditability.md` — needs a new subsection
  parallel to Checkpoint B's "Request Fidelity and the Debug Echo"
  section, extended to cover logs: logs are a *third* record, distinct
  from `request_json` and `raw_response`, never a substitute for either
  (the user's own §0 principle, formalized in the contract doc, not
  just this design doc).
- `docs/contracts/determinism.md` — note that `payload_fingerprint` in
  logs is derived from the same deterministic payload construction
  already covered there; no new determinism claim, just a cross-reference.
- `docs/contracts/idempotency.md` — needs the explicit statement that
  logging failures must never be interpreted by the resume logic as "not
  yet attempted" (closes §8.2's gap at the contract level, not just the
  test level).
- `docs/contracts/immutability.md` — re-audit only (already corrected in
  Checkpoint B); confirm this checkpoint's `CONFIG_RESOLVED` event
  doesn't introduce any doc claim implying config becomes re-visitable
  because it's now logged.
- `docs/contracts/interaction-contracts.md` — this is the doc the Typer
  migration plan already flagged as needing its "CLI Output Boundaries"
  section (stdout/stderr policy) completed at Fase 1 of that migration.
  Checkpoint C's stdout/stderr findings (§1.4) are directly relevant
  evidence for that future section, but formalizing it is that
  migration's job, not this checkpoint's — cross-reference only, do not
  duplicate the decision here.
- `docs/reference/configuration-reference.md` — add `LOG_PROFILE`
  (new) alongside the existing `LOG_LEVEL`/`LOG_FILE_PATH` rows; add
  `OPENROUTER_DEBUG_ENABLED` (exists in code, **currently undocumented
  in `.env.example` and this reference doc** — a real, pre-existing gap
  found during this investigation, unrelated to anything new proposed
  here).
- `docs/reference/cli-commands.md` — no CLI flags exist for logging
  today (confirmed §1.1); if this checkpoint's implementation phase adds
  any (e.g. `--log-profile` override), document them there — not decided
  in this design pass (see §12 open question).
- `docs/reference/module-structure.md` — update `logging_config.py`'s
  one-line description once the module is split
  (`logging_config.py`/`log_events.py`/`redaction.py`), and add the new
  files.
- `logging_config.py`'s own module docstring — fix the "Structured,
  machine-parseable format" overclaim (§1.1) regardless of which parts
  of this design get approved; it's presently false about the *current*
  code, separate from what Checkpoint C might add.
- `docs/status/known-issues.md` — move "⚠️ Logging Context Consistency"
  (Technical Debt) to Resolved Issues once implemented and verified
  (§1.16); cross-reference or supersede the unverified 2026-04 "✅ Logging
  System Implementation" Resolved Issues entry, which cites no
  regression test or baseline, unlike every current-era entry in that
  file.
- `docs/Nao_Apagar-Temporarios_do_Usuario/v2-current/02-logging-system.md`
  and `docs/architecture/gap-reports/02-logging-system-gap.md` — both
  assert "V2 has NO logging system" (§1.15), stale since
  `src/utils/logging_config.py` now exists; the second one lives outside
  the user-notes archive so is more likely to be mistaken for current —
  worth a corrective note or archiving alongside the other stale
  gap-reports, decided during implementation, not here.

---

## 11. Affected files (implementation phase — not created yet)

**New:**
- `src/utils/log_events.py` — centralized event name vocabulary + event
  schema dataclasses/builders
- `src/utils/redaction.py` — central redaction policy
- `src/utils/log_emitter.py` — the one shared emission function producing
  both human + JSONL output, profile-gated, redaction-applied
- `docs/status/cli-output-classification.md` — the `print()` inventory +
  classification map (Checkpoint C2's handoff artifact; no code changes
  to any `print()` call site in this checkpoint)

**Modified (logging call sites gain `operation_id` threading +
profile tags; no behavioral change to what currently logs, only
additive):**
- `src/utils/logging_config.py` (fix docstring overclaim; wire the new
  JSONL handler alongside the existing two; add `LOG_PROFILE` config)
- `src/core/execution_engine.py`, `src/core/planner.py`,
  `src/core/async_orchestrator.py`, `src/core/retry.py`,
  `src/core/run_finalizer.py`, `src/core/async_writer.py`,
  `src/core/result_writer.py`, `src/api/client.py`
- `src/core/config_resolver.py` (currently zero logging — gains
  `CONFIG_RESOLVED`/`INHERITANCE_DECISION` at DETAILED)
- `src/db/repository.py` (currently zero logging — evaluate case-by-case
  whether write-level logging belongs here or stays at the
  `ResultWriter`/`AsyncWriter` layer that already logs `WRITE_*` events,
  to avoid double-logging the same write)
- `bcllm.py` (`operation_id` generation, `COMMAND_START`/`COMMAND_END`)
- `src/cli/presentation/errors.py` (`COMMAND_INTERRUPTED` inside the
  existing `run_command()` KeyboardInterrupt path)
- `.env`, `.env.example` (`LOG_PROFILE`, document `OPENROUTER_DEBUG_ENABLED`)

**Explicitly NOT modified:** `src/core/result_writer.py`'s/
`src/db/repository.py`'s incremental-write/idempotency policy (only
logging is added around it, per explicit instruction); the request
payload construction (`src/api/request_payload.py`, Checkpoint B,
untouched).

---

## 12. Risks, impact estimate, and open questions

### Risks

- **Scope size:** this is the largest surface-area checkpoint so far
  (touches nearly every `src/core/`+`src/api/` module, plus a new
  cross-cutting concern). Proposed mitigation: implement in the small
  steps below, each independently testable and revertible, not as one
  large diff.
- **Performance:** per-event redaction + dual serialization (human +
  JSONL) adds CPU work per log call. At NORMAL/DETAILED this is
  negligible (a handful of events per item); at TRACE, redacting a full
  payload every attempt is real but bounded work, and TRACE is opt-in,
  not default.
- **163 `print()` calls:** migrating CLI result output to reach the log
  file is the single largest mechanical change in this area — split into
  a separate Checkpoint C2 (decided; see "Open questions — resolved"
  below). Checkpoint C only produces the inventory/classification map.

### Open questions — resolved

1. **CLI flag for profile override: NO, `.env`-only for now.** Decided —
   `LOG_PROFILE` follows `LOG_LEVEL`'s existing precedent (no CLI
   override). No `--log-profile`/`--verbose`/`--quiet` flag is added in
   this checkpoint.
2. **TRACE-level chunk logging: log unconditionally.** Decided — TRACE
   means TRACE; no secondary flag layered on top of it.
3. **`print()` migration scope: split into Checkpoint C and a new,
   separate Checkpoint C2 — decided, with a specific division of labor:**
   - **Checkpoint C** (this one) builds the full architecture — profiles,
     structured events, `operation_id`/correlation, redaction, JSONL,
     crash-safety, the OpenRouter debug scope rule, and **one central
     event-emission API** — and additionally produces a **complete
     inventory and classification of all 163 `print()` call sites** as
     this checkpoint's deliverable. It does **not** migrate them.
   - **The classification is explicitly not "copy the string to the log
     file."** Each `print()` is classified by *what it represents*, not
     mechanically mirrored: **resultado** (stdout, unchanged — a result
     the user asked for) / **diagnóstico** (stderr, and — where it
     represents a decision or outcome worth auditing, not just a
     human-readable echo — a corresponding *structured* log event with
     real fields, not the same string) / **erro de uso** (stderr, usage
     error, exit 2 — argparse already owns most of these) /
     **progresso** (stdout during `--execute`, and a `PROGRESS_MILESTONE`-
     style structured event, which already exists) / **ajuda** (stdout,
     `--help` output, no log event — not diagnostically interesting) /
     **evento auditável** (the print IS effectively logging today,
     misplaced — becomes a real structured event, and the print may or
     may not survive depending on whether the terminal-facing message is
     still needed once the event exists).
   - **Checkpoint C2** (separate, future, not started) executes the
     actual migration using this checkpoint's classification map and
     event API, organized **by CLI command group**, and — explicitly —
     timed to land alongside each group's own Typer migration milestone
     (Fase 4A/4B/4C/4D) rather than reworking `argparse`-based code that
     the Typer migration will replace anyway. This avoids the exact kind
     of throwaway work the project has been careful to avoid in prior
     checkpoints.

### Implementation steps (Checkpoint C only — C2 is separate and not started)

1. `src/utils/log_events.py` + `src/utils/redaction.py`, unit-tested in
   isolation, no wiring into existing modules yet.
2. `logging_config.py` extended: `LOG_PROFILE` config, JSONL handler
   added alongside the existing two, docstring overclaim fixed. Existing
   human-readable output unchanged (regression-tested against the exact
   current format).
3. `src/utils/log_emitter.py` — the one central event-emission API
   (profile-gated, redaction-applied, human+JSONL dual output).
4. `operation_id` generation in `bcllm.py` + `COMMAND_START`/`COMMAND_END`
   + `COMMAND_INTERRUPTED` (closes §8.2's gap).
5. Migrate existing event call sites (§1.2's table) to the new centralized
   vocabulary + profile tags via the emitter, module by module, verifying
   each module's existing tests still pass before moving to the next.
6. New DETAILED-tier `CONFIG_RESOLVED`/`INHERITANCE_DECISION` events in
   `config_resolver.py` (closes the zero-logging gap there).
7. TRACE-tier payload/echo/chunk logging, redaction-gated.
8. **`print()` inventory and classification map** — a new document
   (`docs/status/cli-output-classification.md` or similar), covering all
   163 call sites per the classification scheme above — the handoff
   artifact for Checkpoint C2. No `print()` call site is edited.
9. Full test suite from §10.1, then pytest + cli_suite + Essence Guardian,
   per the closing instruction, before presenting Checkpoint C as
   complete and proposing Checkpoint C2 as a distinct, separately-approved
   next checkpoint.

---

## Summary — what's being asked for approval

Sections 1-9 above constitute the full proposed architecture (profiles,
event schema, `operation_id`, OpenRouter debug reconciliation, redaction,
crash-safety plan, retention). Section 11 is the affected-files scope.
Section 12 has three open questions needing your decision, plus the
proposed 8-step implementation order. No code has been changed. Awaiting
your decisions and overall approval before implementing.
