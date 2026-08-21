---
type: status
audience: both
last-validated: 2026-08-20
status: active
---

# Known Issues and Technical Debt

**Purpose:** Bugs, technical debt, and design limitations  
**Scope:** Items requiring attention

---

## Bugs

### ℹ️ [Partially resolved] No CI pipeline exercises Python tests

**Severity:** Low-Medium (not a functional bug — a process gap)
**Status:** The dependency-reproducibility half of this gap (no lockfile, no audit tool) is **resolved** — see the Resolved Issues entry below ("Dependency hygiene pass: pip-tools lockfile, single source of truth, pip-audit"). This entry now tracks only what remains: **no CI pipeline runs `pytest`/`cli_suite` at all.** The only workflows in `.github/workflows/` (`qwen-dispatch.yml`, `qwen-invoke.yml`, `qwen-review.yml`, `qwen-scheduled-triage.yml`, `qwen-triage.yml`) are unrelated to this project's own Python dependencies or tests. All verification in this project (Checkpoints A/B/C, the CLI Typer migration) has been manual/local — a regression is only caught if someone runs the suite by hand.
**Discovered:** 2026-08-20, during marco 4A's dependency verification.
**Suggested Fix:** Not proposed here — explicitly deferred. The user directed (2026-08-20) that this stage stay small and not include standing up CI: "Não crie ainda um pipeline CI amplo. Registre a ausência de CI como tarefa futura." A future checkpoint should design this deliberately (what triggers a run, which profile of `cli_suite`, whether `OPENROUTER_API_KEY`-gated cases are ever exercised in CI or stay local-only) rather than bolting on a minimal workflow now.
**Effort:** Not evaluated — out of scope until prioritized.
**Dependencies:** None technically; deliberately deferred.

### ✅ [Moved to Resolved Issues] An experiment created with no `--seed` stored the literal string `"OFF"`, which `--add-run`'s inheritance then rejected

Found 2026-08-19 during the Unit-of-Work checkpoint (recorded, not fixed there — out of scope). Fully resolved 2026-08-20 as part of the seed vocabulary separation checkpoint, which retired all textual sentinels (`"OFF"`/`"NULL"`/`"NONE"`/`""`) outright rather than teaching `build_run_config_dict` to also recognize them. See the Resolved Issues entry below ("Randomization Seed vocabulary separated from Model Seed...") for the complete fix and regression coverage. Left as a pointer here rather than deleted, matching the convention used for the `system-default` entry above.

### ✅ [Moved to Resolved Issues] `system-default` was not normalized/handled correctly for 3 flags in `bcllm_questions.py`

Investigated 2026-08-18 (deferred), foundation fixed 2026-08-19 (vocabulary/mechanism), fully implemented and tested 2026-08-19 (CLI Typer migration Fase 4 marco 4A). See the Resolved Issues entry below ("`--add-questions`/`--where`/`--exclude` system-default implemented in `bcllm_questions.py`") for the complete fix, target semantics, and regression coverage. Left as a pointer here rather than deleted so a top-to-bottom scan of "Bugs" doesn't need git history to learn this was found and fixed in the same investigation thread.

---

### ℹ️ `--retry-policy` is documented as removed but is still a live, functional CLI flag

**Severity:** Low (documentation drift, not a functional bug — CLAUDE.md's source-of-truth rule says code wins over docs here)
**Impact:** None to end users — `--retry-policy max_attempts=5,backoff=linear` on `--execute` works exactly as it always has. The impact is only that two docs actively say otherwise: `docs/reference/cli-commands.md` ("Retry Policy: Retry is configured via `.env` only... Retry policy cannot be overridden via CLI") and the archived `docs/.archive/pre-restructure/architecture/to-be/comandos_simples.md` ("Configuração não vai mais existir. Configuração de retry-policy agora será apenas por `.env`.").
**Description:** `src/cli/bcllm_execute.py` still declares `--retry-policy`, parses it with `parse_retry_policy()`, and wires the result into the execution plan (`args.retry_policy` → `retry_policy=retry_policy` around line 320-338) — fully functional, not a dead flag like `--output`.
**Discovered:** 2026-08-17, while adding CLI test suite coverage for `--execute`'s flags.
**Suggested Fix:** Either remove `--retry-policy` from `bcllm_execute.py` to match the documented intent, or correct `cli-commands.md` to describe the actual (CLI-overridable) behavior. Not decided here — a product call about which is actually wanted.
**Effort:** Small either way.
**Dependencies:** None technically; decision-blocked.

---

### ℹ️ Current CLI output has not been audited against the new `interaction-contracts.md` Section 2 (CLI Output Boundaries)

**Severity:** Low (no confirmed violation — this is a tracked absence of an audit, not a bug)
**Impact:** None confirmed yet. `docs/contracts/interaction-contracts.md` Section 2 (added 2026-08-18, ADR-002) states the stdout-carries-results/stderr-carries-diagnostics rule "applies to every `bcllm` command, present and future... argparse today" — i.e. it claims to already describe the current implementation, not just the post-Typer-migration one. That claim has not been verified: `src/cli/*.py` has 184 `print()` calls (stable count), and a meaningful minority do not pass `file=sys.stderr`. The exact split is deliberately **not** stated as a number here — three independent quick counts during this same session (a simple-grep pass, and two Essence Guardian passes) each produced a different figure for "how many lack `file=sys.stderr`" (98, 71, and 88), because multi-line `print(...)` calls put `file=sys.stderr` on a different line than `print(`, which a naive single-line grep miscounts in both directions. A real audit needs to parse each call, not grep it. Nobody has checked whether every `print()` without `file=sys.stderr` is genuinely a "result" (per the new contract) rather than a diagnostic that should have gone to stderr.
**Description:** Flagged by the Essence Guardian review of ADR-002 (2026-08-18): declaring the section normative for the current CLI without an accompanying compliance pass risks the same doc/code drift this file already tracks elsewhere in the project's history.
**Discovered:** 2026-08-18, Essence Guardian review of ADR-002 / `interaction-contracts.md`.
**Suggested Fix:** As each CLI group is migrated to Typer (Fase 4 of the CLI migration plan, marks 4A–4D), audit that group's `print()` calls against Section 2 and correct any stdout/stderr misplacement found — do not assume compliance, verify it group by group rather than as one large pass.

---

### ✅ [Moved to Resolved Issues] `bcllm_review.py`'s `KeyboardInterrupt` handling contradicted the `interaction-contracts.md` §2 exit-code convention and produced zero audit trail

Fully resolved 2026-08-20, same day it was found by the Essence Guardian's Checkpoint C review. See the Resolved Issues entry below ("`bcllm_review.py` KeyboardInterrupt handling brought into line with `interaction-contracts.md` §2") for the complete fix and regression coverage. Left as a pointer here rather than deleted, matching the convention used for the entries above.

### 🟡 `--resolve-providers` ignores a variant's `BASE_URL`, always hits real OpenRouter

**Severity:** Medium
**Impact:** `--resolve-providers` cannot be pointed at a local stub or llama.cpp-style endpoint — it always calls production OpenRouter (`https://openrouter.ai/api/v1`) regardless of a variant's configured `--url`, unlike execution (`--execute`), which was fixed to honor `BASE_URL` this session (see Resolved Issues below).
**Description:** `src/api/provider_resolver.py::ProviderResolver.__init__` accepts a `base_url` parameter (default `https://openrouter.ai/api/v1`), but `src/cli/bcllm_provider.py::handle_resolve_providers` constructs it as `ProviderResolver(api_key)` — never passing a variant's `BASE_URL`. This is the same class of gap as the already-fixed execution-path bug, but in a separate code path (`bcllm_provider.py` → `ProviderResolver` directly, not through `Planner`/`ExecutionEngine`/`ModelConfig`), so fixing one did not fix the other.
**Discovered:** 2026-08-17, while adding CLI test suite coverage for `--resolve-providers` — it can't be exercised against the suite's local HTTP stub, so the corresponding case (`tests/cli_suite/cases/provider.yaml::PR-001`) is tagged `requires: [openrouter]` and stays `BLOCKED` by default instead of silently passing.
**Suggested Fix:** Resolve `BASE_URL` the same way `Planner._build_model_config()` does (from the variant's config, falling back to the experiment default) and pass it into `ProviderResolver(api_key, base_url=...)`.
**Effort:** Small.
**Dependencies:** None.

---

### 🔴 `--remove-question` performs a real hard delete, contradicting its own "soft delete" docstring and the immutability contract

**Severity:** Medium (contract tension, not yet acted on — flagged per `CLAUDE.md`'s rule: document and wait, don't silently pick a side)
**Impact:** `bcllm --experiment X --remove-question <snapshot_id>` permanently removes the row from `question_snapshots` via `SnapshotRepository.delete()` (`src/db/repository.py:346-356`, unconditional `DELETE FROM question_snapshots WHERE snapshot_id = ?`, `conn.commit()`). No soft-delete mechanism exists for this table (no `status`/`deleted_at` column). This directly contradicts `docs/contracts/immutability.md` §1 ("Question Snapshots ... **Cannot be deleted** — Even if the source dataset changes, snapshots remain") and `bcllm_questions.py`'s own module docstring, which claims "Remove question snapshots (**soft delete**)" (line 7) — the claim has been wrong since before this session; not introduced by any recent change.
**Discovered:** 2026-08-20, flagged by the Essence Guardian's marco 4A review, triggered by that marco adding a new `Event.QUESTION_REMOVED` structured-logging event to this exact code path — the removal was already possible and already violated the contract; the new event only makes it more visible in the audit trail, which is why the Guardian caught it now rather than it being a new problem.
**Precedent:** This is the same class of tension already found and resolved for `--remove-experiment` (hard cascading delete, disabled entirely) and `--provider-lock` on an existing experiment (config rewrite, disabled entirely) — see the Resolved Issues entries below. `--remove-question` was not covered by that earlier pass.
**Suggested Fix (not applied — awaiting a decision, same as the two precedents above):** Either (a) disable `--remove-question` the same way `--remove-experiment` was disabled, pending a real soft-delete design (new column, migration path — see `docs/architecture/adr/adr-003-pre-production-data-scope.md` for what's allowed pre-production), or (b) if soft-delete is wanted for real, design and implement it now rather than continuing to document a "soft delete" that isn't one. Not decided here.
**Effort:** Small for option (a); medium for option (b) (schema change + migration consideration).
**Dependencies:** None technically; decision-blocked.

---

### ℹ️ `PR-001` case ID pre-dates this session's `tests/cli_suite/cases/provider.yaml` — was referenced in docs, never actually existed as a file until now

**Severity:** Low (documentation drift, no actual ID collision — confirmed only one `PR-001` exists on disk)
**Impact:** The `--resolve-providers ignores BASE_URL` entry below (discovered 2026-08-17) references `tests/cli_suite/cases/provider.yaml::PR-001` as an existing, `requires: [openrouter]`-tagged, `BLOCKED`-by-default case — but `tests/cli_suite/cases/provider.yaml` did not exist anywhere in the repo before 2026-08-20 (confirmed via `Glob` before creating it). The `PR-001` that exists now (created this session, marco 4A's black-box FORBIDDEN case — see the Resolved Issues entry for "CLI Typer migration marco 4A") is a **different** case: a pure argument-parsing rejection test (`--experiment system-default --resolve-providers` → exit 2), never reaching the network, not tagged `requires: [openrouter]`.
**Discovered:** 2026-08-20, while documenting the immutability entry above and cross-checking adjacent `known-issues.md` content.
**Suggested Fix:** When the `--resolve-providers`/`BASE_URL` bug below is eventually fixed and given real test coverage, that case should use a different ID (`PR-002` or similar) to avoid implying it's the same case this entry originally described. Not fixed here — no actual collision exists today, so nothing is broken, just a dangling cross-reference.
**Effort:** Trivial, whenever the BASE_URL bug is worked.
**Dependencies:** None.

---

### 🔴 Review UI is deliberately deferred — not a routing bug; not being fixed piecemeal

**Status (2026-08-20, explicit product decision by RockManRK):** Review UI
is **partially implemented, not ready for use, and deliberately deferred**
until the rest of the system's components are complete. This is not
neglect and not a "todo" — it's a scoping decision. No further piecemeal
fixes to `review_ui.py`/`bcllm_review.py` are planned until it is
resumed; when resumed, it gets **one dedicated, complete review**
(architecture, queries, persistence, UX, audit, tests, and contracts
together), not a sequence of small patches. The single exception already
made was the 2026-08-20 KeyboardInterrupt/exit-code-130 fix (see Resolved
Issues below), which the user explicitly requested despite the deferral —
that does not reopen the rest.

**Confirmed, tracked limitations (kept documented, not resolved):**

1. **Invalid query — `responses.created_at` does not exist.**
   `src/review/review_ui.py` (two call sites: `get_pending_by_experiment`
   line 160/169/192, used by `start_review_by_experiment`; and
   `start_review_all` line 557/566/589) selects `r.created_at` where `r`
   aliases the `responses` table. `responses` has no `created_at` column
   (`src/db/schema.sql:200-235`) — it has `started_at`/`finished_at`
   instead. **Impact:** `--review-experiment` and `--review-all` reach the
   review module (routing is confirmed working, not the blocker — see
   Resolved Issues below and `docs/status/implementation-status.md`,
   "Manual Review") but immediately fail with `Error during review: no
   such column: r.created_at`, exit code 1, as soon as there is any
   `review_status='needs_review'` row to process. **Reproduction:** `bcllm
   --review-all` (or `--review-experiment <name>` once that experiment has
   pending items). Originally confirmed 2026-08-17; re-confirmed live
   2026-08-20 via real subprocess execution against an isolated,
   freshly-created empty schema, with structured logs (`COMMAND_START`/
   `COMMAND_END` correlated by `operation_id`) independently confirming
   the dispatcher/routing is not at fault.
   **CLI-suite visible symptom:** `tests/cli_suite/cases/review.yaml`
   case `RV-001` ("`--review-all` alcança o módulo mas falha em coluna
   inexistente (bug confirmado)") is tagged `EXPECTED_FAILURE` and must
   **stay** `EXPECTED_FAILURE` — not silently marked PASS/fixed — until
   the dedicated future review resolves the underlying query.

2. **Wrong exit code on experiment-not-found.**
   `start_review_by_experiment` (`src/review/review_ui.py:458-460`) prints
   an error and returns `None` (does not raise) when the experiment name
   doesn't exist, so `handle_review_experiment`
   (`src/cli/bcllm_review.py`) always returns exit code `0` regardless of
   whether the experiment was found — `bcllm --review-experiment
   nonexistent_name` prints "Experimento não encontrado" but reports
   success via its exit code. Reproduced live 2026-08-20.

3. **Any further limitation found during future investigation** should be
   added as a new numbered item here, under this same entry — not spun
   out into a separate ad-hoc fix or a new standalone issue, per the
   deferral decision above.

**Suggested Fix (deferred, not to be acted on individually):** (1) Decide
whether the intended sort/display field is `started_at` or `finished_at`,
then update both query sites and the `ReviewItem` construction that reads
`row["created_at"]`. (2) Make `start_review_by_experiment` signal "not
found" distinctly (e.g. raise or return a sentinel) so
`handle_review_experiment` can return exit code `1`. Both require
touching `ReviewUI` itself and are explicitly bundled into the future
dedicated Review UI review described above — do not fix in isolation.
**Effort:** Small for the two items above once the `created_at`
replacement field is decided; the larger unknown is the full
classify/undo/skip/save flow, which has never been validated end-to-end
against real pending data (blocked by item 1 for as long as the bug has
existed) — that validation is part of the deferred dedicated review, not
a quick patch.
**Dependencies:** None technically; decision-blocked on which timestamp
field is correct, and deliberately not scheduled until the dedicated
review.

---

### 🟡 TOCTOU handling for a concurrent `--create-experiment` race always re-raises, contradicting its own comment

**Severity:** Low (narrow race window: two processes creating the SAME experiment name at the exact same time)
**Impact:** `bcllm.py::_handle_composite_flow`'s `except sqlite3.IntegrityError` branch looks up the concurrently-created experiment, logs `"experiment already exists (concurrent)"`, and its comment says "Continue to execute actions on existing experiment" — but the `raise` that follows is at the same indentation as the `except` body, not inside the `if "unique constraint failed"...` block, so it unconditionally re-raises regardless of which branch ran. The concurrent-creation recovery this code appears to implement never actually happens; the process crashes with an unhandled traceback instead.
**Discovered:** 2026-08-17, while implementing the composite-flow atomicity fix below (not touched by that fix — this is a different exception path, `sqlite3.IntegrityError` vs. the `ValueError` "already exists" branch a few lines above, which works correctly).
**Suggested Fix:** Move the final `raise` inside the `if` block's `else` clause (only re-raise when `existing` is `None`, i.e. the row genuinely isn't there for some other reason).
**Effort:** Small.
**Dependencies:** None.

---

### ⚠️ `src/db/schema.sql` has drifted from `src/db/schema.py` (the real, executed schema)

**Severity:** Low (documentation-only drift, but actively misleading — I cited `schema.sql` as authoritative earlier in this same document, in an entry now corrected below)
**Impact:** `src/db/schema.py` is what `create_schema()` actually runs; `src/db/schema.sql` is a separate, hand-maintained reference copy that no longer matches it — most importantly, `schema.py` declares `ON DELETE CASCADE` from `model_variants`/`question_snapshots`/`runs` to `experiments` (lines 43, 59, 75); `schema.sql` does not. An earlier version of this document (2026-08-17, same session) cited `schema.sql` and concluded `ExperimentRepository.delete()`'s "will be deleted via CASCADE" docstring was wrong — it wasn't; `schema.sql` was the stale source. Caught by an essence-guardian review that read `schema.py` directly.
**Suggested Fix:** Regenerate `schema.sql` from `schema.py` (or delete it and point readers at `schema.py` directly) so there's one source of truth for the schema, matching `CLAUDE.md`'s "if documentation and code disagree, code wins" rule — `schema.sql` is documentation, `schema.py` is code.
**Effort:** Small.
**Dependencies:** None.

---

### 🔴 No Other Critical Bugs Currently Known

If you encounter a bug, please add it to this document with:
- Description
- Reproduction steps
- Impact assessment
- Suggested fix

---

## Technical Debt

### ⚠️ Composite `--create-experiment` + `--add-*` rollback is compensatory, not transactional

**Status:** investigated 2026-08-19, not implemented — full write-up in `docs/status/composite-flow-atomicity-investigation.md`.
**Description:** `_rollback_created_experiment` (`bcllm.py`) cleans up a failed composite flow via explicit `DELETE`s + re-deletion of the experiment row, not a real SQLite transaction rollback — every repository `save()`/`update_status()`/`delete()` commits immediately (11 independent call sites in `src/db/repository.py`), so by the time a later `--add-*` action fails, everything earlier actions wrote is already durably committed; there is nothing left for `conn.rollback()` to undo.
**Investigated, not decided:** (1) repositories/actions could join a future Unit-of-Work only via a commit-suppression seam, never a blanket removal of internal commits — a bare `SAVEPOINT` wrapper around the composite flow, left otherwise untouched, does **not** work, since any inner `conn.commit()` ends the whole transaction regardless of an open savepoint (confirmed, not assumed). (2) `ResponseRepository`'s per-write commits (used by `--execute`/`ResultWriter`) must **never** be included in any such refactor — deferring those would break `docs/contracts/idempotency.md`'s crash-safe partial-resume guarantee, forcing expensive LLM-call re-execution after a crash. (3) A real transaction wrapping just the composite CREATE flow is a bounded, plausible refactor (not the whole system), with one unmeasured risk: transaction hold time on `--add-questions` against a large dataset. (4) If the compensation itself fails partway through — confirmed via injection — a failure *before* its first internal commit is safe (nothing durable, DB ends up as if rollback was never attempted); a failure *between* its two commit points (child-table deletes vs. the experiment-row delete) leaves a real, silently-wrong "empty shell" experiment behind, uncaught, with the original action's real exit code lost. The database itself is never physically corrupted either way (`PRAGMA foreign_key_check`/`integrity_check` both clean, confirmed).
**Regression coverage added:** `tests/unit/cli/test_composite_flow_rollback.py` — failures injected after only `--add-model` persisted, after `--add-model`+`--add-questions` persisted, and (via a direct unit test of `_rollback_created_experiment`, since `--add-run` is last in the sequence and no real invocation can fail "after" it) with all three entity tables already populated; both compensation-failure windows from point (4) above, each PRAGMA-verified.
**Side finding while writing these tests:** a real test-isolation bug (`bcllm.py`'s module-import-time `load_dotenv(".env", override=True)` silently clobbering a test's `monkeypatch.setenv("DATABASE_PATH", ...)` on the first `import bcllm` in a pytest process) had let ~213 synthetic test-generated experiment rows accumulate in the real, gitignored `data/bcllm.db` across past sessions — harmless (gitignored, pre-production, no real research data, per `adr-003-pre-production-data-scope.md`) but a real violation of this project's isolated-diagnostics rule. Fixed in the test file; not cleaned up in the DB itself (out of scope for this investigation).
**Recommendation (not a decision):** treat the compensating-delete mechanism as definitive-for-now, transitory-in-principle — revisit only if the transaction-hold-time question turns out to be a non-issue, or a real (not theoretical) empty-shell-experiment incident occurs. **No transactional refactor has been implemented** — explicitly deferred pending direction on scope.

### ⚠️ Review UI Limitations

**Severity:** Medium  
**Impact:** Review UX could be significantly improved  
**Description:**
- Review UI is currently single-language only
- No batch classification (one at a time only)
- Single-level undo (no history)
- No progress persistence across sessions (quit and resume loses position)

**Suggested Fix:** Refactor review UI with:
- Language selection (PT/EN)
- Batch mode for multiple items
- Undo history stack
- Session state persistence

**Effort:** Medium  
**Dependencies:** Review UI refactor

---

### ⚠️ Export Format Limitations

**Severity:** Low  
**Impact:** Analysis requires JSON parsing; no spreadsheet-friendly format  
**Description:**
- Export currently JSON-only
- No CSV export for spreadsheet analysis
- No customizable export schema

**Suggested Fix:** Add CSV export service with configurable columns

**Effort:** Small  
**Dependencies:** Export service extension

---

### ⚠️ Documentation Drift Risk

**Severity:** Medium  
**Impact:** Documentation may become outdated as code evolves  
**Description:**
- Documentation was comprehensively restructured (this document set)
- Without disciplined updates, docs will drift from code
- No automated validation that docs match implementation

**Suggested Fix:**
- Establish documentation update protocol
- Schedule periodic audits (quarterly recommended)
- Consider automated validation tooling (future enhancement)

**Effort:** Ongoing  
**Dependencies:** Process discipline

---

### ✅ [Moved to Resolved Issues] Logging Context Consistency

Fully resolved 2026-08-20 as part of Checkpoint C (Logging, Observability, and Operational Auditability). See the Resolved Issues entry below ("Checkpoint C — Logging, Observability, and Operational Auditability") for the complete fix: a centralized `event_name` vocabulary (`src/utils/log_events.py`), a single emission path (`emit_event()`) producing an identical structured schema across every module, and `operation_id` correlation threaded through the `--execute` pipeline. Left as a pointer here rather than deleted, matching the convention used for the entries above.

---

## Design Limitations

### ℹ️ Sequential-by-Default Execution

**Impact:** Large experiments may take hours  
**Description:**
- Default concurrency is 1 (sequential)
- Parallel execution is supported but requires explicit configuration
- Users may not realize parallelism is available

**Mitigation:** Document parallel configuration in user guide  
**Future:** Consider sensible default concurrency

---

### ℹ️ SQLite Limitations

**Impact:** Single-user, local-only storage  
**Description:**
- SQLite is single-writer by design
- No concurrent multi-user access
- No remote access without file sharing

**Rationale:** System is designed as single-user research tool  
**Future:** If multi-user needed, consider database migration (major change)

---

### ℹ️ No Built-In Analytics

**Impact:** Analysis requires external tools  
**Description:**
- System collects data but doesn't analyze it
- No built-in charts, statistics, or comparisons
- Export enables downstream analysis

**Rationale:** Data collection is the core responsibility; analysis is downstream  
**Future:** Analytics may be added as separate module or external tooling

---

## Resolved Issues

### ✅ Parallel Execution Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** AsyncOrchestrator with semaphore-based concurrency implemented  
**Impact:** Large experiments can run in parallel with configurable concurrency

### ✅ Retry Safety Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** Centralized retry handler with exponential/linear backoff implemented  
**Impact:** Transient API failures are handled gracefully

### ✅ Logging System Implementation (superseded — see Checkpoint C below)

**Resolved:** 2026-04 (prior to documentation restructure)
**Description:** Configurable logging with file rotation and crash-safety implemented
**Impact:** System behavior is observable and debuggable
**Note (2026-08-20):** This 2026-04 entry predates the documentation
restructure and was never re-verified against the code in this
repository — treat its date/description as unconfirmed history, not
current fact. The claims that are true today (rotation, crash-safety)
are re-verified and superseded by the Checkpoint C entry below, which
also closes the gaps this entry never covered (structured/JSONL output,
depth profiles, redaction, correlation IDs, TRACE-tier payload/echo
visibility).

### ✅ Checkpoint C — Logging, Observability, and Operational Auditability

**Resolved:** 2026-08-20
**Description:** Full logging architecture built on top of the prior
ad-hoc `logger.info()`/`logger.debug()` calls: a centralized, stable
`event_name` vocabulary (`src/utils/log_events.py`, `Event` class); four
cumulative depth profiles (`LogProfile.MINIMAL`/`NORMAL`/`DETAILED`/
`TRACE`, `.env`-only via `LOG_PROFILE`, `WARNING`+ events never
suppressed at any profile); a single emission path (`emit_event()` in
`src/utils/log_emitter.py`) producing two derived outputs — a
human-readable line and a JSONL structured record (`benchmark_llm.jsonl`,
`schema_version: 1`) — from one construction, never two independently
drifting ones; unconditional central redaction (`src/utils/redaction.py`)
of secret-shaped keys, `Bearer` tokens, URL credentials, and
inline-`key=value` fragments in exception text, applied before every
handler at every profile including `TRACE`; `operation_id` correlation
generated once per CLI invocation and threaded explicitly (no
globals/contextvars) through the entire `--execute` pipeline (Planner →
ExecutionPlan → AsyncOrchestrator → ExecutionEngine → RetryHandler →
OpenRouterClient → ResultWriter → RunFinalizer → AsyncWriter); new
`CONFIG_RESOLVED`/`INHERITANCE_DECISION`/`SYSTEM_DEFAULT_APPLIED` events
closing `config_resolver.py`'s previous zero-logging gap; TRACE-tier
`REQUEST_PAYLOAD_TRACE`/`UPSTREAM_ECHO_TRACE`/`STREAM_CHUNK_TRACE`
events, empirically proven distinct and non-overwriting (per
`docs/contracts/data-auditability.md` §4c); uniform `KeyboardInterrupt`
handling closing a gap in 7 of 9 CLI modules that previously let Ctrl-C
propagate as a raw traceback (`COMMAND_INTERRUPTED` event, one outer
catch in `bcllm.py`'s `main()`); crash-safety, concurrency (200
concurrent asyncio tasks, no line interleaving/truncation), and rotation
behavior empirically tested, not just asserted.
**Impact:** System behavior is observable, debuggable, and auditable at
the operational level, distinct from and complementary to the database's
authoritative scientific record (`docs/contracts/data-auditability.md`
§4c) — closes the "Logging Context Consistency" issue above. print()
CLI-output migration is explicitly deferred to a separate future
Checkpoint C2 (see `docs/status/cli-output-classification.md` for the
classification map); this checkpoint delivers the event-emission
infrastructure C2 will migrate onto, not the migration itself.
**Verification:** 104 new tests across 10 new test files (event
vocabulary, redaction, emitter, profile/JSONL config, operation_id
threading through ExecutionEngine/Client/ConfigResolver, TRACE-tier
logging, KeyboardInterrupt handling, concurrency/crash-safety/rotation);
full `pytest` suite re-run after every module migration with zero
regressions; real end-to-end `--execute` run inspected in the produced
JSONL output, confirming 19 correlated events sharing one `operation_id`
from `command_start` through `command_end`.
**Docs updated:** `docs/contracts/interaction-contracts.md` §4 (now
normative), `docs/contracts/data-auditability.md` (Logging and Audit
Trail section, new §4c), `docs/contracts/idempotency.md` (logging
failures never imply "not attempted"), `docs/contracts/determinism.md`
§7 (TRACE payload logging, no separate fingerprint field exists),
`docs/contracts/immutability.md` (`CONFIG_RESOLVED` is observational,
not a new mutation path), `docs/reference/configuration-reference.md`
(`LOG_PROFILE`, `OPENROUTER_DEBUG_ENABLED`), `docs/reference/module-structure.md`
(`log_events.py`, `log_emitter.py`, `redaction.py`).

### ✅ `bcllm_review.py` KeyboardInterrupt handling brought into line with `interaction-contracts.md` §2

**Resolved:** 2026-08-20
**Description:** `handle_review_experiment`/`handle_review_all`
(`src/cli/bcllm_review.py`) each caught `KeyboardInterrupt` around their
`ReviewUI` call but returned exit code `0` (success), printed a message
via builtin `print()` containing literal, unrendered Rich markup
(`"[yellow]Review interrupted by user.[/yellow]"`) to stdout instead of
stderr, and emitted no structured event — so `bcllm.py`'s Checkpoint C
outer `KeyboardInterrupt` catch never fired for these two commands and
review-session interruptions had zero `operation_id`-correlated trail,
unlike every other command. Found by the Essence Guardian's Checkpoint C
review (2026-08-20). Fixed by mirroring `bcllm_execute.py`'s established
pattern at the point where it was already caught (no restructuring of
where the catch lives): both handlers now return `130`, print a plain
(no-markup) message to `stderr`, and call
`emit_event(get_logger("cli.review"), Event.COMMAND_INTERRUPTED,
operation_id=operation_id, command="review_experiment"|"review_all")`.
`operation_id` is now threaded through `bcllm_review.main()` →
`handle_review_experiment`/`handle_review_all`, and `bcllm.py`'s
`route_to_v2` now passes it through on the `bcllm_review` dispatch (it
already did for `bcllm_execute`). Connection closure (`finally:
conn.close()` in `main()`) was already unconditional and required no
change; no traceback is raised (the exception is fully caught, a normal
int is returned) and no new persistence is triggered by the interrupt
handler itself.
**Impact:** `--review-experiment`/`--review-all` now follow the same
exit-code-130 / stderr / structured-event convention as every other
interruptible command, closing the "Logging Context Consistency"-adjacent
gap the Guardian flagged. This is independent of, and does not fix, the
separate `responses.created_at` SQL bug and exit-code-on-not-found bug
documented above ("Review UI is deliberately deferred") — those remain
open and deliberately unfixed until Review UI's dedicated future review.
**Verification:** 13 new tests in
`tests/unit/cli/test_keyboard_interrupt_logging.py::TestBcllmReviewKeyboardInterrupt`
(exit code 130, stderr message present with no Rich markup leaking
through, stdout has no error text, `COMMAND_INTERRUPTED` event present
with correct `operation_id`/`command` fields, no traceback propagates,
connection closed via the real `main()` path, no new `commit`/`execute`
calls triggered by the interrupt handler) — all passing, plus the full
existing suite re-run with zero regressions.

### ✅ `param_types.py` (Typer callbacks) was missing two equivalents of `special_config_values.py` (argparse), found by marco 4A's pre-conversion equivalence check

**Resolved:** 2026-08-20
**Description:** Before writing any Typer command for marco 4A, a targeted equivalence check compared every behavior of `src/core/special_config_values.py` (argparse) against `src/cli/param_types.py` (its Typer-callback counterpart, scaffolded in Fase 2 but never exercised). Confirmed equivalent: int (including `0`, distinct from `None`/`FORCE_SYSTEM_DEFAULT`), float, string (`'none'` preserved as a literal, not special-cased), `'system-default'` → `FORCE_SYSTEM_DEFAULT`, deprecated `'null'` rejected, invalid value → exit code 2 (proven empirically via a real `typer.Typer` app + `CliRunner`, not assumed from framework docs), absence → `None`. Two real gaps found: (1) no Typer equivalent of `normalize_filter_list_or_system_default` (`--where`/`--exclude` list handling, including the system-default-combined-with-a-concrete-filter contradiction check) — both `bcllm_experiment.py` and `bcllm_questions.py` need this for marco 4A; (2) no Typer equivalent of `normalize_special_config_values`'s FORBIDDEN branch (structural/identity flags — `--experiment`, `--url`, `--create-experiment`, etc. — that must explicitly reject `'system-default'`/`'null'` rather than silently accepting either as the literal value).
**Fix:** Added `typer_filter_list_or_system_default` and `typer_reject_special_values` to `src/cli/param_types.py`, matching the argparse versions' behavior and message text exactly (Typer's `BadParameter` in place of `argparse.ArgumentTypeError`/`ArgumentError`).
**Verification:** `tests/unit/cli/test_param_types.py`, 42 tests covering the full equivalence checklist above plus 8 tests proving exit-code-2 via real `CliRunner` invocations of a synthetic Typer app using all five callbacks together. Full suite re-run: 48 failed / 1222 passed / 18 skipped / 39 errors — same baseline, +42 new tests, zero regressions.
**Impact:** `param_types.py` is now a verified, complete Typer-side equivalent of `special_config_values.py` for both marco 4A modules — the actual Typer command conversion can proceed without re-deriving this foundation mid-conversion.
**Follow-up gotcha found during actual conversion (same day, `bcllm_questions.py`):** `typer_filter_list_or_system_default` cannot be wired as `callback=` on a `list[str]`-typed `typer.Option` — Typer generates its own post-callback list convertor (`typer.main.generate_list_convertor`) for any `list[str]` parameter, which runs AFTER a Click-level callback and unconditionally calls `len()` on the result, and collapses an explicit `[]` back to `None`. Both break the instant the callback returns something other than a plain list (i.e. exactly when it does its job — returning `FORCE_SYSTEM_DEFAULT` or normalizing absence to `[]`). The 42-test equivalence check above didn't catch this because its integration test asserted only exit codes, never the actual resolved value of a successful `--where system-default`/absent-`--where` invocation. Fixed by declaring `--where`/`--exclude` as plain `list[str]` options with no callback, and calling `typer_filter_list_or_system_default` explicitly inside the command function body instead — see `src/cli/commands/questions.py::_questions_command` and the corrected docstring on `typer_filter_list_or_system_default` itself. Regression tests added directly to `test_param_types.py` (`test_where_absent_resolves_to_empty_list_not_none`, `test_where_system_default_alone_resolves_to_sentinel_not_crash`) so this integration gap can't silently reopen. This pattern (Click-level callback for scalar transforms, function-body call for list-shape-changing transforms) applies to any future `list[str]`+system-default flag, including `bcllm_experiment.py`'s own `--where`/`--exclude`.

### ✅ `typer`/`rich` had no upper version bound; `click` risked being misdeclared as a direct dependency

**Resolved:** 2026-08-20
**Description:** Marco 4A's pre-`bcllm_experiment.py` checkpoint required verifying real environment dependency versions before continuing. Confirmed: `typer==0.27.1` (the latest verified stable release), `rich==14.3.3` — both resolved correctly, but `requirements.txt`/`setup.py` declared them as floating `rich>=13.0.0`/`typer>=0.27.1` with no upper bound, so a future `pip install` could silently resolve an untested major version. Also confirmed `click` is **not** a separate installed package in this environment (`pip show click` → not found) — Typer 0.27+ fully vendors it internally as `typer._click`, and `pip show typer`'s own `Requires:` line lists no `click` — so no `click` version line was added (would be actively misleading, not corresponding to any installed package).
**Fix:** Bounded both declarations: `rich>=13.0.0,<15.0.0` (allows the verified 14.3.x line, blocks an untested future major), `typer>=0.27.1,<0.28.0` (tight — Typer is still pre-1.0, where minor bumps may break per semver convention). These bounds now live in `requirements.in` (the canonical source — see the entry below); `requirements.txt` itself was superseded the same day by a `pip-compile`-generated exact-pin lockfile, so this bound is what constrains what the lockfile is allowed to resolve to, not the final installed version itself.
**Impact:** A fresh `pip install -r requirements.in`/`pip install -e .` resolves within the same major.minor lineage this project has actually been tested against, without pinning to a single exact version.
**Not fixed by this change:** the broader lockfile/audit gap — closed the same day, see the entry below.

### ✅ Dependency hygiene pass: `pip-tools` lockfile, single source of truth, `pip-audit`

**Resolved:** 2026-08-20
**Description:** Before starting `bcllm_experiment.py`'s Typer conversion, a full dependency-hygiene pass was requested: reproducible Python version documentation, a real pip-tools lockfile (not `pip freeze`), a single canonical source for direct dependencies (`setup.py` and `requirements.txt` had been two independently hand-edited lists), a vulnerability audit, and a clean-environment rebuild proving all of the above actually works — without standing up CI (explicitly deferred, see the entry above).

**Python version:** Running/tested this session: **3.14.2**. Declared minimum in `setup.py`: `python_requires=">=3.10"`. No evidence in this project of the 3.10 floor itself having been exercised (only 3.14.2 has real test-run evidence) — the floor is a declared compatibility claim, not a verified one; flagged here rather than silently presented as tested.

**Typer:** Kept at `0.27.1` (the latest verified stable release) — confirmed identical in a completely clean venv built from the compiled lockfile (see below), not just the pre-existing dev `.venv`.

**Rich:** Environment was `14.3.3`; researched `14.3.4` and `15.0.0` directly against the real changelog (`raw.githubusercontent.com/Textualize/rich/master/CHANGELOG.md`) rather than assumption:
- `14.3.4` (2026-04-11): import-time/lazy-loading improvement and a link-id-generation change — **no breaking changes**.
- `15.0.0` (2026-04-12): **breaking change is dropping Python 3.8 support**, plus minor fixes (`print(end=...)` on empty print, `Text.from_ansi` newline handling, `FileProxy.isatty` proxying, Markdown table inline code). Since this project already requires `python_requires=">=3.10"`, the only breaking change in 15.0.0 has **zero impact here**.
- Not auto-upgraded. `pip-compile` (below) naturally resolved to `14.3.4` (latest patch satisfying the existing `<15.0.0` bound) — adopted, since it carries no breaking changes and is exactly what the existing approved bound already permits. **Widening the bound to allow `15.0.0` was not done** — that's a deliberate scope decision the bound author should make explicitly, even though the analysis above suggests it would be safe for this project specifically.

**Lockfile / single source of truth:**
- `requirements.in` (new) is now the **single canonical source** of direct runtime+test dependencies, hand-edited.
- `requirements.txt` is now **machine-generated** via `pip-compile requirements.in` (pip-tools) — every direct AND transitive dependency pinned to an exact version. Never hand-edited again; regenerate via `pip install -r requirements-dev.txt && pip-compile requirements.in --output-file requirements.txt`.
- `setup.py` no longer hand-duplicates a second version-constraint list: `_read_runtime_requirements()` reads `requirements.in` directly and filters to the curated subset of packages that are true runtime dependencies of the distributed CLI (`httpx`, `pydantic`, `pydantic-settings`, `Pillow`, `python-dotenv`, `rich`, `typer` — test-only tools like `pytest`/`PyYAML` are correctly excluded from `install_requires`). Verified via `python setup.py egg_info` — `requires.txt` output matches exactly.
- `requirements-dev.txt` (new) holds dev-only tooling (`pip-tools`, `pip-audit`) — never a runtime dependency, never read by `setup.py`.
- Confirmed empirically, not just by inspection: `pip-compile`'s full resolved dependency tree (`requirements.txt`) contains **no `click` entry anywhere** — independent confirmation (beyond the earlier `pip show typer` check) that Typer's vendored `_click` means this project has zero real dependency on the separate `click` package.

**`pip-audit` findings (no `--fix` applied automatically, per instruction):**
- Against the **existing dev `.venv`** (stale, never refreshed): **39 known vulnerabilities across 8 packages** (`idna`, `pillow`, `pip`, `pydantic-settings`, `pygments`, `pytest`, `requests`, `urllib3`) — all because the environment was resolved against older availability windows (e.g. `pillow==12.1.1` vs. the lockfile's `12.3.0`, `pytest==9.0.2` vs. `9.1.1`, `urllib3==2.6.3` vs. `2.7.0`).
- Against the **compiled `requirements.txt`**: **zero known vulnerabilities**. No manual per-package fix was needed — adopting the fresh lockfile (below) resolves all 39 findings as a side effect of normal version freshness, not a deliberate security patch.

**Clean-environment verification:** Built a fresh venv (outside the repo, scratchpad-isolated) from `requirements.txt` alone. Confirmed: resolved versions match the lockfile exactly (`typer==0.27.1`, `rich==14.3.4`, `httpx==0.28.1`, `pydantic==2.13.4`, `Pillow==12.3.0`, `pytest==9.1.1`, `PyYAML==6.0.3`); `import bcllm`/`import src.cli.bcllm_questions`/`import src.cli.commands.questions` all succeed; full `pytest` — **48 failed / 1262 passed / 18 skipped / 39 errors**, byte-identical to the dev `.venv`'s baseline; full `cli_suite --profile full` — **58 cases, 57 PASS + 1 EXPECTED_FAILURE**, byte-identical.
**Impact:** Any future `pip install -r requirements.txt` reproduces this exact, tested dependency set — no more floating resolution. Vulnerability posture visible and current (zero known CVEs in the lockfile as of 2026-08-20). No CI was created — explicitly out of scope for this pass.
**Not fixed by this change:** the CI gap itself — see the entry above.
**Follow-up (same day):** the dev `.venv` was then synced to the lockfile (`pip install -r requirements.txt`) and re-audited — found `pip` itself (the installer, not a project dependency) at a vulnerable version (4 CVEs); upgraded via `pip install --upgrade pip`. Final state: `pip-audit` clean against the dev `.venv`, full `pytest` (48 failed/1262 passed/18 skipped/39 errors) and `cli_suite --profile full` (57 PASS + 1 EXPECTED_FAILURE) both re-confirmed byte-identical to every prior baseline.

### ✅ CLI Typer migration marco 4A — `bcllm_questions.py` and `bcllm_experiment.py` converted from argparse

**Resolved:** 2026-08-20
**Description:** Completes marco 4A of the CLI Typer migration plan (`docs/architecture/adr/adr-002-cli-presentation.md`). Both modules' `create_parser()` (argparse) removed entirely, replaced by real `typer.Typer` command definitions in `src/cli/commands/questions.py` and `src/cli/commands/experiment.py` — every flag mirrored 1:1 (names, types, choices, special values), invoked programmatically via `.main(standalone_mode=False)`, never exposed as a public Typer subcommand tree. External CLI syntax is completely unchanged.
- **`bcllm_questions.py`:** `bcllm.py`'s composite dispatcher needed **zero changes** — the module was already decoupled via `parse_add_questions_request`/`run_add_questions`/`add_questions_action` (a request-based pipeline, not `argparse.Namespace`-coupled), so swapping only that function's internals sufficed. `handle_list_questions`/`handle_remove_question` converted to typed params instead of `Namespace`.
- **`bcllm_experiment.py`:** `bcllm.py`'s composite pre-parse phase (`_handle_composite_flow`) DID need a small fix — it imported `create_parser as create_experiment_parser` directly; now imports `parse_experiment_argv` from the new Typer command module instead. `_create_experiment_with_config`/`_add_models_at_creation`/`_create_question_snapshots`/`handle_create_experiment` deliberately left unchanged internally — they access `args` via `getattr(args, 'field', default)` throughout (`ConfigResolver.build_experiment_config_dict`/`build_model_config_dict`), which works identically against the new `ExperimentParsedArgs` frozen dataclass as it did against `argparse.Namespace`, since field names match exactly — a genuine "substitua Namespace por requests tipados sem alterar comportamento."
- **Real gap found during conversion**, not hypothetical: `typer_filter_list_or_system_default` cannot be wired as `callback=` on a `list[str]`-typed `typer.Option` — Typer's own post-callback list convertor breaks on a non-list return (`FORCE_SYSTEM_DEFAULT`) and silently collapses an explicit `[]` back to `None`. Fixed by calling it explicitly inside each command's function body instead (both `commands/questions.py` and `commands/experiment.py`) — documented as the required pattern directly in `typer_filter_list_or_system_default`'s own docstring so it isn't rediscovered per module.
- **Mutually exclusive + required groups** (argparse's `add_mutually_exclusive_group(required=True)`) have no Click/Typer declarative equivalent — reimplemented as an explicit count-based check inside each command body, raising `typer.BadParameter` (→ exit 2), verified to treat `--questions`/`--add-questions` as the same group member (alias, not a distinct action).
- **`tests/unit/cli/test_system_default_classification_consistency.py`** — the Fase 0 gate's deferred ADAPTAR item — fixed now that `bcllm_experiment.py` joined the Typer side: added a test-infrastructure-only `declared_dests(mod_name, mod)` helper resolving either `parser._actions` (argparse, still `bcllm_model.py`/`bcllm_run.py`/`bcllm_provider.py`) or `_command.params` (Typer, now `bcllm_questions`/`bcllm_experiment` — introspected via `src.cli.commands.<name>`). Never exposed outside the test file.
- **C2 logging map applied incrementally** (per the earlier decision to migrate print()→structured-events alongside each module's own Typer conversion, not all at once): `Event.QUESTIONS_ADDED`/`Event.QUESTION_REMOVED` (new) wired in `bcllm_questions.py`; `Event.EXPERIMENT_CREATED` (existed, was old-style `logger.info`, now `emit_event`), `Event.MODEL_ADDED` (existed, was never wired for the creation-time path), `Event.MUTATION_REFUSED` (new, shared by `--remove-experiment` and `--provider-lock`-on-existing refusals, `reason` field distinguishes which) all wired in `bcllm_experiment.py`.
**Verification:** 175 new tests across this slice (`test_param_types.py` +2 regression, `test_commands_questions.py` 30, `test_questions_logging_events.py` 4, `test_questions_standalone_composite_parity.py` 10, `test_commands_experiment.py` 32, `test_experiment_logging_events.py` 6, plus every pre-existing test file that imports either module re-run and confirmed passing unchanged — 231 tests across 10 files in one targeted pass). `pytest` final: **48 failed / 1301 passed / 18 skipped / 39 errors** — same pre-existing baseline throughout every step, zero regressions. `cli_suite --profile full`: **58 cases, 57 PASS + 1 EXPECTED_FAILURE** (5 new black-box FORBIDDEN cases added this checkpoint) — stable throughout, including CE-001..CE-013 and AQ-001..AQ-011 green at every intermediate step. Environment: **Python 3.14.2** (effectively validated version — see the dependency hygiene entry above for why the declared `>=3.10` floor itself is unverified), **Typer 0.27.1**, **Rich 14.3.4**.
**Impact:** Marco 4A complete. `bcllm_model.py`, `bcllm_run.py`, `bcllm_provider.py`, `bcllm_execute.py`, `bcllm_review.py`, `bcllm_export.py` remain argparse-based, scheduled for marcos 4B/4C/4D.
**Pre-4B diff audit (2026-08-20, same day):** a short full-diff review of marco 4A, requested before opening 4B, found and fixed 3 real issues:
1. **Latent `NameError` in `bcllm_experiment.py::_create_experiment_with_config`'s type hint** — `args: argparse.Namespace` referenced `argparse` after the module's `import argparse` was removed. Silent at import time (Python 3.14's deferred/lazy annotation evaluation, PEP 649) but would raise on any `inspect.signature()`/`typing.get_type_hints()` call. Fixed: hint changed to `ExperimentParsedArgs` (the real type now flowing through). Verified absent project-wide by calling `inspect.signature()` on every function in `bcllm_experiment.py`, `bcllm_questions.py`, `bcllm.py`, and both new `commands/*.py` modules — zero errors.
2. **Stale architecture-doc description** — `docs/status/composite-flow-unit-of-work-design.md` still described the composite pre-parse phase as using `bcllm_experiment.create_parser()`; updated in place with a dated note pointing at `parse_experiment_argv`, rest of the section (the two-phase architecture itself) unaffected and left as-is.
3. **2 untested code paths** — invalid `--output` choice (e.g. `--output bogus`) was never asserted to still exit 2 in either new Typer command's test file, despite being explicitly declared with `choices`-equivalent `Enum` validation; added one test per module (both pass).
No duplicate flag declarations, no other dead imports, no other undocumented behavioral changes found — `--help` combined with other flags routing oddly through `module_resolver.py`'s always-highest-priority `--help` → `bcllm_main` interception (confirmed via a real subprocess) is pre-existing dispatcher behavior, untouched by and unrelated to this marco.

### ✅ ProviderResolver Double ``/api/v1/`` URL Bug

**Resolved:** 2026-05-04
**Description:** ``ProviderResolver._fetch_endpoints()`` constructed the OpenRouter endpoints URL with a doubled ``/api/v1/`` path segment (``https://openrouter.ai/api/v1/api/v1/models/{id}/endpoints``) because ``base_url`` already included ``/api/v1`` and the method appended it again.
**Reproduction:** Running ``--resolve-providers`` failed with ``Expecting value: line 1 column 1 (char 0)`` because the malformed URL returned an HTML page instead of JSON.
**Fix:** Changed ``_fetch_endpoints`` URL construction from ``{base_url}/api/v1/models/{id}/endpoints`` to ``{base_url}/models/{id}/endpoints``. Updated corresponding unit test assertion.
**Impact:** ``--resolve-providers`` command now works correctly; provider resolution returns valid endpoint data.

### ✅ `BASE_URL` / `--url` resolved and persisted but never reached the API client

**Resolved:** 2026-08-17
**Description:** `ConfigResolver` resolved `BASE_URL` from CLI `--url` / experiment default and persisted it into `model_variants.config`, but `Planner._build_model_config()` never read it back into `ModelConfig`, and `bcllm_execute.py` constructed `OpenRouterClient` without a `base_url`. Every `--execute` call went to the client's hardcoded default (`https://openrouter.ai/api/v1`) regardless of a variant's configured `--url`.
**Reproduction (pre-fix):** `bcllm --experiment X --add-model Y --url http://localhost:8080/v1` then `--execute` — the request was sent to `openrouter.ai`, not `localhost:8080`.
**Fix:** Added `ModelConfig.base_url` (`src/core/execution_plan.py`); `Planner._build_model_config()` now reads `config.get("BASE_URL")`; `OpenRouterClient.chat_completion()` (`src/api/client.py`) accepts a per-call `base_url` override; `ExecutionEngine` passes `model_config.base_url` through. No behavior change for variants without an explicit `BASE_URL` (falls back to the client's default, same as before).
**Impact:** `--url` is now honored at execution time. This is also the seam that makes a local HTTP stub (for the CLI test suite, `docs/tests/`) and a future llama.cpp client viable — see `docs/status/implementation-status.md`'s "local model serving" entry.
**Related, NOT fixed by this change:** see "`variant_signature` omits `BASE_URL`" above — two variants differing only by URL still collide on creation.
**Caveat:** no field records the actual endpoint used per historical `responses` row; experiments/variants created before this fix with a non-default `BASE_URL` have responses whose recorded config doesn't match what was actually sent. This is a data-provenance gap for historical rows only, not something to retroactively repair.

### ✅ `DATABASE_PATH` declared in `.env` but silently ignored

**Resolved:** 2026-08-17
**Description:** `.env` declared `DATABASE_PATH`, and `config_resolver.py` documented it as a "SYSTEM key resolved at runtime", but `src/cli/database.py::get_database_path()` always returned the hardcoded `<repo>/data/bcllm.db` regardless of the environment. The `.env` value itself also pointed at a file that never existed (`./data/benchmark.db` vs. the real `./data/bcllm.db`).
**Fix:** `get_database_path()` now honors `DATABASE_PATH` when set (relative paths resolved against the project root, absolute paths used as-is), falling back to the original hardcoded default when unset. `.env` and `.env.example` corrected to `./data/bcllm.db`.
**Impact:** the database location can now be redirected (e.g. by the CLI test suite, to run against an isolated sandbox) without copying source code.

### ✅ `Mode.INVALID` had no valid module in the mode/module matrix

**Resolved:** 2026-08-17
**Description:** `src/core/mode_matrix.py`'s `_VALID_COMBINATIONS` had zero entries for `Mode.INVALID`, but `resolve_mode()` (`src/core/mode_resolver.py`) resolves `--help`, `--list-experiments`, `--remove-experiment`, `--review-experiment`, and `--review-all` to `Mode.INVALID` (none of them set CREATE/MODIFY/EXECUTE/EXPORT). `validate_mode_matrix()` rejected all five before any module logic ran, even though every target module's own `_validate_expected_mode()` already listed `Mode.INVALID` as expected — the gap was entirely in the matrix, isolated and low-risk to close.
**Fix:** Added `(Mode.INVALID, "bcllm_main")`, `(Mode.INVALID, "bcllm_experiment")`, `(Mode.INVALID, "bcllm_review")` to `_VALID_COMBINATIONS`. Regression coverage: `tests/unit/core/test_mode_matrix.py::TestModeInvalidIsValidForHelpListReview`.
**Impact:** `--help` and `--list-experiments` now work correctly. `--review-experiment`/`--review-all` now reach the review module for the first time, which immediately exposed a second, previously-invisible bug — see "Review UI queries a non-existent `responses.created_at` column" above. That one is NOT fixed by this change. **`--remove-experiment` also now reaches its module logic for the first time, and this is a bigger deal than the other three:** it performs a real, hard, cascading delete of the experiment's snapshots/variants/runs, with no soft-delete anywhere in the schema, in tension with `docs/contracts/immutability.md`'s explicit "cannot be deleted" language — see "`--remove-experiment` performs a real, undocumented hard cascading delete" above (still-open Bug, NOT fixed, flagged to the user). This module-level fix could not distinguish `--remove-experiment` from the other three legitimate fixes sharing the same `(Mode.INVALID, "bcllm_experiment")` matrix entry — `mode_matrix.py` gates by `(mode, module)`, not by individual flag.
**Verification:** `tests/cli_suite/cases/experiment.yaml::CE-003` (list-experiments) and `CE-004` (--help) updated from `known_issue`/`EXPECTED_FAILURE` to normal `PASS` expectations.

### ✅ `variant_signature` omitted `BASE_URL` and `MODEL_REPEAT_PENALTY`

**Resolved:** 2026-08-17 (user decision: fix now, no migration of existing rows)
**Description:** `src/utils/variant_signature.py::SIGNATURE_FIELD_ORDER` covered 8 of the variant's 10 config keys; `BASE_URL` and `MODEL_REPEAT_PENALTY` were both missing, so two variants differing only by `--url` or only by `--repeat-penalty` hashed to the same signature and the second `--add-model` was rejected as a duplicate (`UNIQUE(experiment_id, variant_signature)`). `MODEL_REPEAT_PENALTY` was first observed missing in `docs/.archive/pre-restructure/architecture/to-be/testes.md` (AM2/AM5, pre-restructure); both re-confirmed present 2026-08-17 while building the CLI test suite.
**Checked before fixing:** whether OpenRouter's own provider-routing semantics (`docs/Manuais_Diversos/openrouterdocs/provider_routing.md`) had any bearing on this — they don't. That document covers the `provider` object (`order`, `only`, `sort`, etc. — which upstream provider OpenRouter fans a request out to), which is a separate, already-signature-covered concept (`PROVIDER`/`'provider'` was already in `SIGNATURE_FIELD_ORDER`). `BASE_URL` is which HTTP server the client itself talks to (OpenRouter, a local llama.cpp server, a test stub) and never appears anywhere in OpenRouter's request/routing docs — confirmed via full-text search, zero mentions.
**Fix:** Added `MODEL_REPEAT_PENALTY` and `BASE_URL` to `SIGNATURE_FIELD_ORDER` (`src/utils/variant_signature.py`). Deliberately NOT migrated: variants created before this fix keep their old (already-persisted) `variant_signature` value, exactly as immutable snapshots already do elsewhere in this system — only newly-created variants use the corrected field list. This was an explicit user decision, weighing the (contained) risk of a stale-signature collision on an old row against the larger risk of a migration script recomputing identity for historical, already-referenced data.
**Impact:** `--add-model <id> --url <different-url>` and `--add-model <id> --repeat-penalty <value>` now correctly create a new, distinct variant instead of being rejected as a duplicate. Regression coverage: `tests/cli_suite/cases/model.yaml::AM-004` (repeat_penalty) and `AM-005` (url); `tests/test_variant_signature.py` (pre-existing suite, all 29 cases still pass unmodified).
**Not fixed by this change:** the "Review UI is deliberately deferred" entry above (the `responses.created_at` bug) is unrelated.

### ✅ Composite `--create-experiment` + `--add-*` was not atomic, and reported exit 0 on internal failure

**Resolved:** 2026-08-17 (user decision: roll back the experiment on any action failure, rather than keep it with a corrected exit code)
**Description:** `bcllm.py::_handle_composite_flow` created the experiment first, then called `_execute_all_add_actions` → `_execute_single_action`, which discarded each `--add-*` handler's real exit code; `route_to_v2` then `return 0` unconditionally whenever `_handle_composite_flow` reported it had handled the command, regardless of whether any action actually failed. `bcllm --create-experiment X --add-questions <invalid-spec>` created experiment `X` anyway, printed an error to stderr, and exited 0 — a caller checking the exit code saw success.
**Reproduction (pre-fix):** `bcllm --create-experiment diag --add-questions null` — stderr showed `Error: Invalid question specification: ...`, but the process exited 0 and the `diag` experiment row existed with zero question snapshots. First observed in `docs/.archive/pre-restructure/architecture/to-be/testes.md` (TESTE_CE_NULL1, pre-restructure); re-confirmed present 2026-08-17.
**Fix:** `handle_add_model`/`handle_add_questions`/`handle_add_run`'s real exit codes now propagate through `_execute_single_action` → `_execute_all_add_actions` (which now stops at the first failing action instead of running the rest) → `_handle_composite_flow` → `route_to_v2`. On a non-zero result, and only when THIS invocation is the one that created the experiment (never a pre-existing one found via the TOCTOU handling a few lines above — see the separate TOCTOU bug noted above, which this fix does not touch or depend on), `_rollback_created_experiment` deletes it. Rollback deletes child rows (`question_snapshots`, `model_variants`, `runs`) with explicit SQL — redundant with `schema.py`'s `ON DELETE CASCADE` on those same foreign keys (see the schema drift entry above; the original version of this entry incorrectly said the schema had no cascade, based on the stale `schema.sql` reference copy), kept for clarity rather than because cascade is missing — and refuses to proceed (logs an error, deletes nothing) if it ever finds `responses`/`errors` rows already referencing the experiment (those do NOT cascade), which should be structurally impossible today since composite flow can only run `--add-model`/`--add-questions`/`--add-run`, never `--execute`; this is a coherence check for if that ever changes, not code reachable now. A multi-action case (`--add-model` succeeds, `--add-questions` fails) is covered, not just the single-action case, since rollback needs to undo an earlier successful action's row too, not just stop at the experiment row.
**Impact:** A failed composite command now reports the real failing exit code and leaves no partial experiment behind. Regression coverage: `tests/cli_suite/cases/questions.yaml::AQ-003` (single failing action) and `AQ-004` (successful `--add-model` rolled back after a later `--add-questions` failure, including an orphaned-row check via `PRAGMA foreign_key_check` that every case in the suite already runs automatically). This is scoped to an experiment THIS invocation just created — it is unrelated to the separate `--remove-experiment` issue below.
**Not fixed by this change:** the TOCTOU `sqlite3.IntegrityError` bug noted above; the `schema.sql` drift noted above.

### ✅ `--remove-experiment` performed a real, undocumented hard cascading delete — tension with the immutability contract

**Resolved:** 2026-08-17 (user decision: disable `--remove-experiment` entirely for now; keep `--remove-model` as a hard delete since it never destroys actual results, thanks to the FK protection below; fix `--remove-run` to a true soft delete)
**Description:** `bcllm --remove-experiment <name>` called `ExperimentRepository.delete()`, a plain `DELETE FROM experiments WHERE experiment_id = ?`. Combined with `PRAGMA foreign_keys = ON` (`src/cli/database.py`) and `schema.py`'s `ON DELETE CASCADE` (see the schema drift entry above), this hard-deleted every `question_snapshots`, `model_variants`, and `runs` row for that experiment — permanently, with no soft-delete mechanism anywhere in the schema (`src/db/schema.py`'s own header states, as a deliberate design choice: *"NO soft delete (is_active removed from all tables)"*). Note `responses`/`errors` never cascade (no `ON DELETE CASCADE` on those foreign keys) — an experiment with real results already couldn't be removed at all (the delete would fail with a foreign key error); the gap was specifically for experiments *without* results yet, still a real immutability violation for their snapshots.
**Contract conflict:** `docs/contracts/immutability.md` (normative, "This contract is non-negotiable") states question snapshots "**Cannot be deleted** — Even if the source dataset changes, snapshots remain". `docs/contracts/configuration-hierarchy.md` states "Model variant configuration is frozen at creation" and "Run configuration is frozen at creation; never changes". The old `docs/reference/cli-commands.md` also independently described `--remove-experiment` as "soft delete; historical data preserved" — the actual code did neither.
**Why this mattered now:** `--remove-experiment` was **completely unreachable** before this session's `Mode.INVALID` routing fix above — `resolve_mode()` sends it to `Mode.INVALID`, and `bcllm_experiment` had no valid matrix entry for that mode until this session added one (to fix `--help`/`--list-experiments`/etc., which share the same module — `mode_matrix.py` gates by `(mode, module)`, not by individual flag, so the fix could not distinguish them). Fixing the routing gap made this pre-existing, contract-violating hard delete reachable via the CLI for the first time. `--remove-model` and `--remove-run` were already reachable before this session (they resolve through `Mode.MODIFY` via `--experiment`, unaffected by the routing fix).
**Discovered:** 2026-08-17, by an essence-guardian review of the `Mode.INVALID` mode_matrix fix, which caught the reactivation and the contract tension that the original task description hadn't anticipated — flagged to the user rather than resolved unilaterally, per this project's contract-verification workflow.
**Fix:** Three separate decisions, all made by the user:
1. `--remove-experiment` (`src/cli/bcllm_experiment.py::handle_remove_experiment`) now always prints an explanation and returns 1, touching nothing — disabled until a future planning pass decides the right removal semantics.
2. `--remove-model` is left as a hard delete, unchanged — accepted as-is because the FK protection already guarantees it can never destroy actual `responses`/`errors`, only ever removing a variant with no results yet (its own config row does not survive, but that was judged an acceptable trade-off, distinct from snapshot/run immutability).
3. `--remove-run` (`src/cli/bcllm_run.py::handle_remove_run`) now sets `status='removed'` instead of deleting the row — a genuine soft delete, reusing the mutable-exception the immutability contract already grants `Run.status` ("Execution lifecycle tracking"), rather than a new column. `src/db/schema.py`'s `CHECK` constraint on `runs.status` was extended to accept `'removed'`. `src/core/run_finalizer.py`'s docstring (previously an absolute "NO other code may update runs.status") was narrowed to clarify it owns *execution-outcome* status derivation specifically; a user-initiated `status='removed'` transition is a separate, administrative, out-of-band concern, analogous to how the Review UI mutates `Response.review_status`/`manual_answer` without conflicting with `ResultWriter`'s ownership of the original response data.
   **A follow-up bug in this same fix, caught by a third essence-guardian review, not by me:** the first version of this fix only verified that `Planner._get_runs()`'s DEFAULT query (`run_ids=None`, used by plain `--execute`) excludes `'removed'` runs, and I wrote "verified, not just assumed" in this document on the strength of that one check. `_get_runs()` has a SECOND branch, used by `--execute --run <id>` (explicitly naming a run), which had **no status filter at all** — so `bcllm --execute --run <removed-run-id>` would include the removed run in the plan, execute it, and let `RunFinalizer` silently overwrite `status='removed'` with a real execution outcome, **reactivating a run the user had just removed**. Fixed by adding `AND status != 'removed'` to that branch too (`src/core/planner.py::Planner._get_runs()`). Regression coverage added specifically for this path: `tests/unit/cli/test_remove_commands.py::test_removed_run_excluded_even_when_explicitly_targeted_by_id` (calls `_get_runs(experiment_id, run_ids=[...])` directly — the earlier test only exercised the no-`run_ids` call), plus a full end-to-end subprocess verification (`--create-run` → `--remove-run` → `--execute --run <that-id>` → confirm `status` is still `'removed'` and zero `responses` rows were created). Lesson: "the query excludes X" needs to be checked against every branch that builds the query, not just the default one — a one-code-path check does not earn the word "verified."
**Impact:** `--remove-experiment` is honest about being unavailable instead of silently violating a normative contract. `--remove-run` is now a true soft delete — usable even on a run with existing results, which the old hard-delete implementation could never do (it would hit the same FK protection and fail). `--remove-model`'s behavior is unchanged, now accurately documented. `docs/reference/cli-commands.md` corrected for all three commands.
**Regression coverage:** `tests/unit/cli/test_remove_commands.py` — `handle_remove_experiment` always returns 1 and never touches the database (an explicit `monkeypatch` guard asserts it doesn't even call `ExperimentRepository`); `handle_remove_run` sets status, preserves the run's config, is excluded from `Planner._get_runs()`, and the schema's `CHECK` constraint genuinely accepts `'removed'` (not just assumed from reading the constraint text). Also verified end-to-end via a real `bcllm.py` subprocess against an isolated database (not the shared `tests/cli_suite/` fixtures — this needed a fresh run to soft-delete and re-verify against `--execute`, which the existing case corpus doesn't set up yet).
**Not fixed by this change:** whether `--remove-model` should eventually also become a true soft delete is explicitly deferred, not decided against — it would need a new column (or another reused mutable field) on `model_variants`, which has none available today.

### ✅ `--questions` (alias of `--add-questions`) was silently swallowed by `--experiment`'s show-path

**Resolved:** 2026-08-18 (CLI Typer migration, Fase 3 — "correções prévias e alinhamento contratual")
**Description:** `src/core/module_resolver.py::ADD_ACTION_FLAGS` listed `--add-questions` but not its true alias `--questions` (same `dest=add_questions` group in `src/cli/bcllm_questions.py`), so `bcllm --experiment X --questions "1-5"` matched `--experiment` in `PRIORITY_FLAGS` and routed to `bcllm_experiment`'s show-path instead of `bcllm_questions` — the filter/add spec was discarded with no error.
**Fix:** Added `"--questions"` to `ADD_ACTION_FLAGS`. Also added a `"--questions"` entry to `bcllm.py`'s composite-flow `relevant_flags` dict (mirroring `--add-questions`'s `--where`/`--exclude`/`--source-file`) — without it, a composite `--create-experiment X --questions "1-3" --where ...` would have routed correctly but then silently dropped the filter flags during the composite sub-action rebuild.
**Impact:** `--questions` now behaves identically to `--add-questions` in every context, standalone and composite.
**Classification:** Bug funcional (dispatcher routing gap), not a contract violation.

### ✅ `--max-reasoning` silently dropped in the composite `--create-experiment --add-model` flow

**Resolved:** 2026-08-18 (Fase 3)
**Description:** `bcllm.py`'s composite-flow `relevant_flags["--add-model"]` list (used to rebuild the sub-action's argv) included `--reasoning-tokens` but not `--max-reasoning` — both resolve to the same config key (`MODEL_MAX_TOKENS_REASONING`, see `config_resolver.py`), but a user who used `--max-reasoning` specifically in a composite command had it silently dropped.
**Fix:** Added `--max-reasoning` to that list.
**Classification:** Bug funcional.

### ✅ `_add_models_at_creation` built a fabricated `args` object, silently discarding every model CLI flag

**Resolved:** 2026-08-18 (Fase 3)
**Description:** `src/cli/bcllm_experiment.py::_add_models_at_creation` called `resolver.build_model_config_dict(type('Args', (), {'experiment': experiment})(), experiment)` — a dummy object with only an `.experiment` attribute — instead of the real, already-parsed `args` its caller (`handle_create_experiment`) had available. Every `getattr(cli_args, 'reasoning', None)`-style lookup inside `build_model_config_dict` therefore returned `None`, silently discarding `--reasoning`/`--temperature`/`--top-p`/`--top-k`/`--repeat-penalty`/`--vision`/`--structured`/`--url`/`--max-reasoning`/`--reasoning-tokens` for any model added this way.
**Fix:** `_add_models_at_creation` now takes `args` (the real Namespace) instead of a pre-extracted `models: list[str]`, and passes it straight through to `build_model_config_dict`.
**Important caveat found while fixing this — not something to assume is "live" without checking:** `bcllm.py::route_to_v2` calls `_handle_composite_flow` first, unconditionally, whenever both `--create-experiment` and any `ADD_ACTION_FLAGS` member (which includes `--add-model`) are present in argv — which is *every* case where `handle_create_experiment`'s own `if args.add_model:` branch could possibly be reached with a non-empty value. In the real `python bcllm.py` entry point, that branch (and therefore this bug) is **unreachable today** — the composite flow's own `_execute_single_action` → `bcllm_model.handle_add_model` path (which never had this bug) handles it instead. This fix is still correct and worth keeping (defensive, and `bcllm_experiment.main()` can in principle be invoked directly, bypassing the composite router), but it is not something a user could have hit through normal CLI usage. Flagged, not further investigated, to avoid silently expanding this phase's scope.
**Related, newly found, NOT investigated further:** whether the composite path itself correctly handles *multiple* `--add-model` flags in one `--create-experiment` command (`bcllm_model.py`'s own `--add-model` is a single-value `store`, not `append`, so only the last of several composite `--add-model` values might survive) was not checked — a candidate for a future item, not decided or fixed here.
**Classification:** Bug funcional (confirmed latent/dead-code today, not reachable via normal CLI usage).

### ✅ TOCTOU `IntegrityError` handler always re-raised, contradicting its own "continue on existing experiment" comment

**Resolved:** 2026-08-18 (Fase 3)
**Description:** `bcllm.py::_handle_composite_flow`'s `except sqlite3.IntegrityError` block had its final `raise` at the same indentation as the `if "unique constraint failed"...` check above it, so it ran unconditionally — even in the legitimate concurrent-creation branch (existing experiment found, logged, meant to continue), the original `IntegrityError` was re-raised anyway, crashing the composite flow instead of continuing against the already-existing experiment.
**Fix:** Moved the `raise` into an explicit `else` branch, so it only fires when the integrity error is NOT the expected unique-constraint-on-name case.
**Classification:** Bug funcional (indentation/control-flow bug).

### ✅ Deprecated `'null'` literal raised an uncaught `argparse.ArgumentError` traceback instead of a clean usage error

**Resolved:** 2026-08-18 (Fase 3)
**Description:** `parse_args_normalized()` → `normalize_nulls_explicit()` (`src/core/null_semantics.py`) raises `argparse.ArgumentError` for the deprecated `'null'` literal, but this happens *after* `parser.parse_args()` already returned — outside argparse's own exception handling — so any of the 4 CLI modules calling `parse_args_normalized(parser)` directly (`bcllm_experiment.py`, `bcllm_model.py`, `bcllm_run.py`, `bcllm_provider.py`) let it propagate as a raw, uncaught traceback to the user instead of a clean `usage:` message and exit code 2.
**First attempt (reverted):** Initially fixed by making `parse_args_normalized()` itself catch the exception and call `parser.error()`. This broke `tests/integration/test_cli_null_semantics.py` (8 tests) and `tests/unit/core/test_null_normalization.py::test_null_in_parse_args_normalized` — they call `parse_args_normalized`/`normalize_nulls_explicit` directly and assert `pytest.raises(argparse.ArgumentError, ...)`, an intentional, tested contract for direct/unit callers. Caught by running the full suite before/after, per this phase's own process; reverted immediately, `parse_args_normalized`'s docstring updated to document why it does NOT catch this itself.
**Actual fix:** Each of the 4 `main()` call sites now wraps `parse_args_normalized(parser)` in `try/except argparse.ArgumentError: parser.error(str(e))` — argparse's own usage-error mechanism (prints `usage:` + message to stderr, exits 2), identical to how every other invalid argument on that same parser is already reported. `parse_args_normalized()` itself is unchanged.
**Regression coverage:** `tests/cli_suite/cases/experiment.yaml::CE-008` (new) — `--create-experiment X --seed null` exits 2, `stderr_contains: ["deprecated"]`, `no_traceback: true`, and confirms zero rows written.
**Classification:** Bug funcional (missing exception handling at the CLI entry points, not in the shared utility).

### ✅ `handle_modify_provider_lock` rewrote a frozen experiment's `config_json`/`config_hash`

**Resolved:** 2026-08-18 (Fase 3, item 8 — direct user decision, not a unilateral call)
**Description:** `bcllm --experiment X --provider-lock true|false|system-default` (`src/cli/bcllm_experiment.py::handle_modify_provider_lock`) rewrote an already-created experiment's `config_json` (just the `PROVIDER_LOCK` key) and recomputed `config_hash` to match — the only "update experiment" mutation path anywhere in the system. This directly contradicts `docs/contracts/immutability.md` ("Once an entity ... is created, its configuration is frozen") and `configuration-hierarchy.md`.
**Decision:** Asked the user whether this was an intentional exception (like `Run.status`) needing formalization, or a genuine violation needing correction. Answer: a design mistake, not an intentional exception — "Mantendo a imutabilidade definida do sistema" (keep the system's defined immutability).
**Fix:** `handle_modify_provider_lock` now always prints an explanation and returns 1, touching nothing — mirrors `handle_remove_experiment`'s already-established disabled-command convention exactly. `--provider-lock` still works normally at `--create-experiment` time (unaffected); to change it for an existing experiment, create a new one.
**Regression coverage:** `tests/cli_suite/cases/experiment.yaml::CE-009` — confirms exit 1, `stderr_contains: ["disabled"]`, and `config_json`'s `PROVIDER_LOCK` unchanged from its creation-time value.
**Classification:** Confirmed contract violation (immutability), corrected per explicit user decision — not formalized as an exception.

### ✅ `setup.py`'s `console_scripts` entry point was broken

**Resolved:** 2026-08-18 (Fase 3)
**Description:** `entry_points={"console_scripts": ["bcllm=src.cli.bcllm_main:main"]}` pointed at `bcllm_main.main(mode: Mode)`, which requires a positional `mode` argument a console-script wrapper never supplies — every invocation of an installed `bcllm` command would raise `TypeError`. The actual, working entry point has always been `python bcllm.py` (`bcllm.py::main()`, no arguments), which `setup.py` never referenced at all; `bcllm.py` also wasn't declared as a distributable module (`find_packages()` only discovers packages under `src/`, not the root-level `bcllm.py` file).
**Fix:** `entry_points` now points at `bcllm:main`; added `py_modules=["bcllm"]` so the root module is actually included in the distribution.
**Impact:** Packaging-metadata-only — `python bcllm.py` (the way this project is actually run and tested throughout `docs/`) was never affected either way.
**Classification:** Packaging.

### ✅ Composite-path question snapshots had a double-wrapped `meta` field — `has_image` silently always read `False`

**Resolved:** 2026-08-19 (Fase 3, item 5 — user decision: fix now, treat as a high-severity functional bug with auditability impact, not deferred like item 1)
**Description:** Two independent code paths built `question_snapshots.question_payload` with diverging shapes:
- **Composite** (`bcllm --create-experiment X --add-questions ...`) → `src/cli/bcllm_experiment.py::_create_question_snapshots`.
- **Standalone** (`bcllm --experiment X --add-questions ...`) → `src/cli/bcllm_questions.py::handle_add_questions`.

Both call `QuestionLoader.assign_internal_ids()` first, which adds `internal_id` (1-based file position — what `--add-questions "1-3"` specs refer to) and `source_id` (the dataset's own `id`/`question_id` field, e.g. `"Q001"` — what `question_snapshots.json_question_id` stores in both paths, consistently) to each question dict.

The composite path built `meta` via `{k: v for k, v in question.items() if k not in (...)}` — a dict comprehension over the ENTIRE question dict, excluding everything **except** `meta` itself (the exclusion tuple `('stem', 'options', 'answer_key', 'id', 'source_id', 'question_id', 'internal_id', 'assets')` was missing `'meta'`). The original `meta` object survived the filter as a *value under the key `"meta"`*, producing `{"meta": {"has_table": false, "has_image": false, "status": "valid", "notes": ""}}` — double-wrapped, one extra nesting level — instead of the flat shape the standalone path (`meta = question_data.get("meta", {})`, taken verbatim) correctly produced. Confirmed empirically, not just by reading code, running both real code paths against `tests/cli_suite/fixtures/datasets/dataset_small_valid.json`'s `Q001`.

**Impact confirmed via grep across all of `src/`:** `src/core/planner.py`'s `_build_items` — the one consumer that matters, feeding directly into execution — reads `payload_data.get("meta", {}).get("has_image", False)`. For composite-path snapshots, `payload_data["meta"]` was `{"meta": {...}}`, so `.get("has_image", False)` found no such key at that level and silently returned the default `False`, regardless of the dataset's real value. Verified against real fixtures with genuine `"has_image": true` questions (`tests/cli_suite/fixtures/datasets/dataset_filters.json`, `dataset_missing_image.json`) — a vision-enabled question added via the composite path would never have been recognized as having an image, silently defeating vision execution for that experiment. Every other consumer checked (`execution_engine.py`, `async_orchestrator.py`, `review_ui.py`, `bcllm_questions.py::handle_list_questions`, `result_writer.py`) reads only `stem`/`options`/`answer_key`/`assets`, identical in both paths — unaffected. Nothing hashes or text-compares `question_payload` (`SnapshotRepository.get_by_experiment_and_question` queries by the `experiment_id`/`json_question_id` columns, never payload text; `config_hash` covers only `experiments.config_json`), so the pre-fix `ensure_ascii=True` (composite) vs. `ensure_ascii=False` (standalone) divergence was confirmed cosmetic only — audit-readability, not correctness or dedup.
**Fix:** Added a single canonical `build_question_snapshot_payload(question)` function (`src/core/question_loader.py`), used by both `_create_question_snapshots` and `handle_add_questions` — no more independent payload construction. `meta` is taken **verbatim** from `question.get('meta', {}) or {}`, never reconstructed from "whatever fields are left over" (that reconstruction is exactly what caused the double-wrap). Both call sites now serialize with `json.dumps(payload, ensure_ascii=False)` consistently (previously only the standalone path did). `internal_id`/`source_id` are kept as top-level payload keys in both paths (self-contained origin traceability), matching the composite path's pre-existing behavior rather than the standalone path's omission of them. **Existing, already-persisted snapshots are untouched** — this only changes what NEW snapshots look like going forward; no migration was performed (would violate immutability of already-persisted data).
**Regression coverage:**
- `tests/unit/core/test_question_snapshot_payload.py` (12 tests) — `build_question_snapshot_payload` in isolation: meta preserved at exactly one level with no `meta.meta`, `meta.has_image` directly accessible, options dict→list normalization (and list passthrough), `internal_id`/`source_id` preserved (including the absent-`source_id`→`None` case), `assets`/`stem`/`answer_key` preserved verbatim, `ensure_ascii=False` serialization preserves accented characters, and an explicit proof that an old, already-persisted double-wrapped snapshot is read back byte-identical (no silent migration).
- `tests/unit/core/test_planner.py::test_planner_recognizes_vision_question_via_canonical_payload_builder` — a snapshot built via the canonical function end-to-end through `Planner.build_plan()` is correctly recognized as a vision question (`has_image=True`, `image_path` from `assets[0]`).
- `tests/unit/cli/test_question_snapshot_equivalence.py::test_composite_and_standalone_flows_produce_equivalent_payload` — invokes both real handler functions directly (`_create_question_snapshots` and `handle_add_questions`, no subprocess) against the same source question and asserts byte-identical resulting payloads, including the `meta.has_image` and no-`meta.meta` assertions and `ensure_ascii=False` accent preservation in the persisted JSON.
- Full post-fix verification run 2026-08-19 per explicit user instruction: `python tests/cli_suite/run.py --profile full --yes` — 34 PASS + 1 EXPECTED_FAILURE, unchanged from the pre-fix baseline; `pytest` on `test_planner.py`, `test_question_snapshot_payload.py`, `test_question_snapshot_equivalence.py`, `test_execution_plan.py`, `test_repository.py`, `test_schema.py`, `test_export_service.py` — 98 passed, 3 pre-existing unrelated skips; full-suite `pytest` — 886 passed (872 baseline + 14 new), 48 failed (unchanged from baseline), 18 skipped (unchanged), 39 errors (41 baseline minus 2). **The 41→39 change is a counting artifact, not a fix:** the two fewer errors are `test_error_collector.py` and `test_model_capabilities.py`, both still-broken pending-decision collection failures (see "🔴 No Other Critical Bugs" note and the earlier session's decision to leave them as-is), which this run explicitly excluded via `--ignore` to get a clean comparison against the Fase-0 baseline. They were not touched, fixed, or otherwise affected by this change — running unfiltered `pytest` still shows both, unchanged, as collection errors. Zero regression either way.
**Classification:** Confirmed functional bug (the `meta` double-wrap, high severity — real feature silently broken, auditability impact), fixed by eliminating the underlying integration/duplication issue (two independent payload-building implementations unified into one) and correcting the cosmetic `ensure_ascii` inconsistency along the way.
**Essence Guardian review (2026-08-19):** 4/5 relevant contracts Aligned/PASS (immutability, determinism, idempotency, configuration-hierarchy); one `data-auditability` Warning about pre-fix composite-flow snapshots potentially still being silently affected on resume/re-execution — resolved per `docs/architecture/adr/adr-003-pre-production-data-scope.md` (no real data exists yet for this to apply to). Full detail: `docs/essence-guardian-log/guardian_memory.md` entry [14].

### ✅ `system-default` vocabulary renamed and eligibility mechanism redesigned; `_is_nullable_arg`'s blanket sweep and `bcllm_model.py`'s 7 numeric flags (+`--reasoning`) fixed

**Resolved:** 2026-08-19 (dedicated change, approved after a controlled vocabulary audit and an explicit 3-category classification review — see the audit exchange earlier this session)
**Description:** Three related problems, fixed together because the first two shared a root cause and the vocabulary rename was their natural vehicle:

1. **Vocabulary was misleading.** `src/core/null_semantics.py` and its `nullable_*`/`normalize_nulls_explicit` names implied the module handles "null" — it never produces a usable null; the `'null'` literal is always rejected. What it actually recognizes is the `system-default` special value.
2. **`_is_nullable_arg`'s eligibility heuristic was too broad.** Any optional argparse argument with `default=None`/`required=False` was treated as eligible for `system-default` normalization, with no distinction between configuration values (`--seed`, `--temperature`, ...) and identity/structural flags (`--run`, `--remove-run`, `--remove-experiment`, `--remove-model`, `--create-experiment`, `--experiment`, `--url`, ...). Confirmed by direct execution: `--run system-default` silently became the falsy `FORCE_SYSTEM_DEFAULT` sentinel, so `elif args.run:` never fired and the command fell through to help output (exit 1) instead of any honest error; same for the other flags listed.
3. **`bcllm_model.py`'s 7 numeric flags (`--max-reasoning`, `--max-tokens`, `--repeat-penalty`, `--temperature`, `--top-k`, `--top-p`, `--reasoning-tokens`) used plain `type=int`/`type=float`**, not the special-value-aware parser `bcllm_experiment.py` already used correctly for the identically-named flags — so `system-default` failed outright with a generic "invalid int/float value" error (exit 2) before ever reaching normalization. `--reasoning` (a `choices=[...]` flag on the same module) had the same class of bug: `'system-default'` simply wasn't in the choices list.

**Fix:**
- **Rename** (not mechanical — `None`, the `'none'` literal, the deprecated `'null'` literal, and `'AUTO'` were each individually re-verified to keep their distinct behavior): `src/core/null_semantics.py` → `src/core/special_config_values.py`; `nullable_int/float/str` → `parse_int/float/str_or_system_default`; `normalize_nulls_explicit` → `normalize_special_config_values`; `typer_nullable_int/float/str` (`src/cli/param_types.py`) → `typer_int/float/str_or_system_default`. `parse_args_normalized` (`src/core/argv_utils.py`) keeps its name. Dead duplicates `argv_utils.py::normalize_nulls`/`_is_nullable_arg` (identical to the real functions, exercised only by their own tests, zero production consumers — confirmed by grep before deleting) removed; their test coverage migrated to target the real functions directly.
- **Eligibility redesigned as explicit opt-in, three categories** (`docs/contracts/system-default-semantics.md`, fully rewritten): **SUPPORTED** (`system-default` has real semantics, normalized to the sentinel), **FORBIDDEN** (recognized specifically so it can be explicitly rejected with a usage error, exit code 2 — not silently accepted, and not silently treated as a literal identifier either), **NOT_APPLICABLE** (not a configuration value, never inspected). `normalize_special_config_values(args, parser, supported: set[str], forbidden: set[str])` replaces the old heuristic; each CLI module now declares its own `SYSTEM_DEFAULT_SUPPORTED`/`SYSTEM_DEFAULT_FORBIDDEN` dest-name sets next to `create_parser()` (`bcllm_experiment.py`, `bcllm_model.py`, `bcllm_run.py`) and passes them to `parse_args_normalized`. `--url` and `--source-file` are classified **FORBIDDEN** (not eligible, per explicit product decision) — `--source-file`'s classification had been an open pending decision in this same document; now resolved. `--provider` is classified **SUPPORTED**, confirmed already correctly handled by `config_resolver.py::_resolve_cli_or_experiment` (no behavior change needed there, only explicit registration so it isn't dropped by the mechanism redesign). `--provider-lock` is also SUPPORTED, unchanged.
- **`bcllm_model.py`'s 7 numeric flags** now use `parse_int_or_system_default`/`parse_float_or_system_default`, matching `bcllm_experiment.py`. **`--reasoning`** gained `"system-default"` as an explicit `choices` entry (registered SUPPORTED) — same semantics as every other model-parameter flag: breaks inheritance, parameter not sent in the API request.
- **Intentional behavior change:** `--url system-default` moves from a manually-checked, `handle_create_experiment`/`handle_add_model`-level rejection (exit code 1) to a FORBIDDEN, parse-time rejection (exit code 2) — the manual checks (dead code once FORBIDDEN intercepts earlier) were removed from both `bcllm_experiment.py` and `bcllm_model.py`.
- **`--provider`/`--provider-lock` interaction documented precisely** in `system-default-semantics.md` (new "Provider and Provider-Lock Semantics" section), confirmed by reading `planner.py`/`execution_engine.py`/`config_resolver.py` directly rather than assumed: `--provider` explicit fixes the variant's provider regardless of `--provider-lock`; `--provider-lock true` is a completeness *validation* gate (`Planner._validate_provider_lock`, called unconditionally in `build_plan()`) requiring every variant to have a resolved provider before execution is allowed — it does NOT itself control payload construction; the actual request-payload lock (`provider: {"only": [slug], "allow_fallbacks": False}`, confirmed to use `only`+`allow_fallbacks`, never `order` alone) is driven purely by whether a variant's `PROVIDER` happens to be set, independent of the lock flag's value.
**Regression coverage:**
- `tests/integration/test_cli_special_config_values.py` (renamed/rewritten from `test_cli_null_semantics.py`) and `tests/unit/core/test_special_config_values_normalization.py` (renamed/rewritten from `test_null_normalization.py`) — SUPPORTED/FORBIDDEN/NOT_APPLICABLE behavior via the real mechanism, including an explicit regression test inverting the old (buggy) assertion that `--create-experiment system-default` should silently normalize.
- `tests/unit/cli/test_presentation_foundation.py` — `typer_*_or_system_default` renamed in place, same coverage.
- `tests/unit/cli/test_bcllm_model_system_default.py` (new, 45 tests) — all 8 flags (7 numeric + `--reasoning`) × {explicit valid value, `system-default`, deprecated `null` rejected, invalid value rejected}; `--reasoning`'s inheritance from experiment config at the `ConfigResolver` layer (explicit value / inherited value / system-default-breaks-inheritance); `--url`'s new FORBIDDEN/exit-2 behavior; `--provider`'s continued-correct behavior after the eligibility-mechanism change.
- `tests/cli_suite/cases/model.yaml::AM-008` (all 8 flags succeed with `system-default` end-to-end, DB confirms `None`/not-sent), `AM-009` (`--url system-default` real exit code 2); `tests/cli_suite/cases/run.yaml::RN-008` (`--run system-default` real exit code 2); `tests/cli_suite/cases/experiment.yaml::CE-010` (`--url system-default` exit 2), `CE-011` (`--create-experiment system-default` exit 2 — the exact scenario the blanket-sweep bug produced).
- Full verification 2026-08-19: `python tests/cli_suite/run.py --profile full --yes` — 39 PASS + 1 EXPECTED_FAILURE (34 baseline + 5 new cases; one transient "attempt to write a readonly database" failure on the first run was confirmed to be an environmental flake, not a code issue, by a clean immediate re-run reproducing 100% pass); full-suite `pytest` (excluding the two pre-existing pending-decision collection errors) — 908 passed (886 baseline + 22 net new, after accounting for the deleted/rewritten test files), 48 failed (unchanged from baseline), 18 skipped (unchanged), 39 errors (unchanged) — zero regression.
**Classification:** Two confirmed functional bugs (the blanket-sweep misclassification, and `bcllm_model.py`'s 7+1 flags failing outright) fixed together with a vocabulary/documentation cleanup (the rename) and one closely-related, previously-undocumented contract gap resolved (`--source-file`'s FORBIDDEN classification, `--provider`/`--provider-lock`/`--max-reasoning` added to the normative table).
**Essence Guardian review (2026-08-19, entry [15]):** found two real Warnings, both fixed same day. (1) Configuration hierarchy: `--experiment` was classified FORBIDDEN in `bcllm_experiment.py` but left unclassified (NOT_APPLICABLE) in `bcllm_model.py`/`bcllm_run.py`/`bcllm_provider.py` — `required=True` had already protected those three from the old blanket-sweep bug, but the broader "identity selectors reject `system-default` explicitly" principle this whole fix is built on applies uniformly, not only where the old bug happened to bite. Fixed: `'experiment'` added to all three modules' `SYSTEM_DEFAULT_FORBIDDEN` sets (`bcllm_provider.py` gained a classification for the first time); `system-default-semantics.md`'s FORBIDDEN table corrected; regression coverage added (`tests/unit/cli/test_experiment_flag_forbidden_consistency.py`, `tests/cli_suite/cases/model.yaml::AM-010`). (2) Mandatory documentation rule: `docs/reference/module-structure.md` (2 occurrences) and `system-default-semantics.md`'s own "Implementation:" line still cited `null_semantics.py` post-rename — both corrected, plus `CLAUDE.md`'s module-layout list (same stale reference, outside the Guardian's own edit scope). Re-verified after fixes: `pytest` 913 passed (908 + 5 new), 48 failed/18 skipped/39 errors all unchanged from the pre-Guardian-fix baseline; `cli_suite --profile full` 40 PASS + 1 EXPECTED_FAILURE (39 baseline + 1 new case).

### ✅ `--add-questions`/`--where`/`--exclude` system-default implemented in `bcllm_questions.py` (item 1, CLI Typer migration Fase 4 marco 4A)

**Resolved:** 2026-08-19 (marco 4A — the foundation from the dedicated system-default change above made this possible; the flag-level wiring itself was deferred until now, per the original 2026-08-18 decision)
**Description:** The 3-flag gap registered above (`--add-questions`/`--questions`, `--where`, `--exclude` on `bcllm_questions.py`) is now fully implemented, on both the standalone (`--experiment X --add-questions ...`) and composite (`--create-experiment X --add-questions ...`) flows:
- **`--add-questions`/`--questions` `system-default`:** `bcllm_questions.py::handle_add_questions` gained the missing `if args.add_questions is FORCE_SYSTEM_DEFAULT: <select all questions>` branch (previously absent entirely — the sentinel is falsy, so it fell straight into "No valid question IDs found in spec", exit 1). No `.env` fallback applies in this flow (the mutex group always requires an explicit `--add-questions` value here, unlike the composite flow's optional `DEFAULT_QUESTIONS` fallback) — `system-default` simply means "all questions," unconditionally.
- **`--where`/`--exclude` `system-default`:** new shared function `src/core/special_config_values.py::normalize_filter_list_or_system_default(values: list[str] | None)` — the list-aware counterpart to the scalar `normalize_special_config_values`, needed because `action="append"` values are lists Typer/Click callbacks receive whole, not per-item. Rules: not provided → `[]`; exactly one value `'system-default'` → `FORCE_SYSTEM_DEFAULT`; exactly one value `'null'` → rejected (deprecated); more than one value including `'system-default'` (repeated or combined with a concrete filter) → rejected as a contradiction; otherwise → the concrete filter list, unchanged (repeating `--where`/`--exclude` for multiple AND-combined conditions remains explicitly allowed, never an error). Called once in each module's `main()`, right after `parse_args_normalized()`, raising a plain `ValueError` that both modules catch the same way as `argparse.ArgumentError` (`parser.error(str(e))` — exit code 2, before `get_database_connection()` is ever called).
- **Bootstrap vs. post-creation, implemented as the two registered cases:** `bcllm_experiment.py::_create_question_snapshots` now branches `if args.where is FORCE_SYSTEM_DEFAULT: include_filters = []` (explicit, skips the `QUESTIONS_STATUS_ADD` `.env` fallback) vs. `elif args.where: <use it>` vs. `else: <.env fallback>` (only the true "not provided" case reaches `.env` — checked explicitly, since `FORCE_SYSTEM_DEFAULT` is also falsy and could otherwise collapse into the same branch by accident). `bcllm_questions.py::handle_add_questions` needed no equivalent branching — it never had an `.env` fallback for `--where`/`--exclude` to begin with, so the existing `if args.where: ... ` structure already produces the correct "no filter" result for both "not provided" and "system-default" without any special-casing.
- **`--source-file` FORBIDDEN**, implemented: added to `bcllm_questions.py`'s new `SYSTEM_DEFAULT_FORBIDDEN` set (alongside `experiment`, `remove_question`) — `system-default`/`null` now rejected with the standard exit-2 message.
- **Dispatch bug fixed as part of this wiring:** `bcllm_questions.py::main()`'s mode dispatch used `if args.add_questions:` (truthy) — since `FORCE_SYSTEM_DEFAULT` is falsy, `--add-questions system-default` would have silently fallen through to the `else: parser.print_help(); return 1` branch instead of ever reaching `handle_add_questions`. Changed to `if args.add_questions is not None:`.
- `bcllm_questions.py` now calls `parse_args_normalized()` for the first time (previously plain `parser.parse_args()`), with `SYSTEM_DEFAULT_SUPPORTED = {'add_questions'}`.
**Regression coverage — the 8 points explicitly requested before starting marco 4A, each validated separately:**
1. `tests/unit/cli/test_questions_system_default.py::TestAddQuestionsSystemDefault` — `--add-questions system-default` in both flows.
2. `TestWhereExcludeSystemDefault` (`test_standalone_where_system_default_applies_no_filter`, `test_composite_where_system_default_ignores_env_status_add`) — `--where system-default`.
3. Same class, `test_standalone_exclude_system_default_applies_no_filter` — `--exclude system-default`.
4. `TestMultipleConcreteFiltersAllowed::test_standalone_multiple_where_and_combined` — repeated concrete `--where`, AND-combined, no error.
5. `TestContradictionExitsWithCode2` (both `--where` and `--exclude`) — real `main()` invocation, `pytest.raises(SystemExit)` with `.code == 2`, plus `tests/cli_suite/cases/questions.yaml::AQ-008` (real subprocess).
6. `TestStandaloneCompositeEquivalence` (`--add-questions system-default` and a concrete `--where` filter) — both flows invoked directly, resulting snapshot sets compared for equality.
7. `TestStandaloneNeverConsultsEnvForWhereExclude` — `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` set via `monkeypatch.setenv` to values that WOULD change the result if consulted; confirmed zero effect in the standalone flow. `test_composite_where_not_provided_still_uses_env_fallback` is the paired non-regression check: the composite flow's `.env` fallback still works when the flag is genuinely absent (only `system-default` explicitly bypasses it).
8. `TestNoWriteBeforeUsageError` — `get_database_connection` mocked, asserted `not_called()` when a FORBIDDEN/contradiction rejection fires; `SystemExit.code == 2` confirmed in the same test.
- `tests/unit/core/test_normalize_filter_list.py` (14 tests) — the shared function in isolation: not-provided, system-default alone (case-insensitive), concrete filters (single and multiple, unchanged), deprecated `null` rejected, contradiction rejected (system-default + concrete, either order; system-default repeated, case-insensitive).
- `tests/cli_suite/cases/questions.yaml::AQ-007` (`--add-questions system-default` standalone, real subprocess, DB count confirms all 10 dataset questions added), `AQ-008` (`--where system-default` + concrete filter, exit 2, `unchanged_tables: [question_snapshots]`), `AQ-009` (`--source-file system-default`, exit 2), `AQ-010` (`--where system-default --exclude system-default` at bootstrap against a new `env_questions_status_filters` preset — `QUESTIONS_STATUS_ADD=status=valid`/`QUESTIONS_STATUS_EXCLUDE=status=annulled` set in `.env`, all 9 `dataset_filters` questions added despite the `.env` filters being in place, proving the bypass works end-to-end through a real process, not just at the unit level).
- New `tests/cli_suite/runner/env_presets.py::env_questions_status_filters` preset added for AQ-010 (no existing preset set `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` — an earlier version of this document incorrectly referenced `env_full` for this purpose; corrected here after actually checking).
- Full verification 2026-08-19: `python tests/cli_suite/run.py --profile full --yes` — 44 PASS + 1 EXPECTED_FAILURE (40 baseline + 4 new cases); full-suite `pytest` — 944 passed (916 baseline + 28 new: 14 + 14), 48 failed/18 skipped/39 errors all unchanged — zero regression.
**Classification:** Confirmed functional bug (missing sentinel-handling logic + a dispatch truthy-check bug, both silently misrouting a legitimately-documented CLI value), fixed per the already-registered target semantics — no new product decisions made in this pass, only implementation of what was already decided 2026-08-19.

### ✅ Composite `--add-*` flow bypassed `parse_args_normalized` entirely, using a separate un-normalized parser/dispatch path from standalone ("same action, same path")

**Resolved:** 2026-08-19 (dedicated checkpoint, separate from and prerequisite to the Typer conversion — implemented per explicit approval of a 4-part architectural fix)
**Description:** `bcllm.py::_execute_single_action` (the composite `--create-experiment` + `--add-*` flow) built its own `create_parser().parse_args(argv[1:])` per action and called the module's old `handle_add_model`/`handle_add_questions`/`handle_add_run` directly — a structurally separate code path from standalone's `main()`, which already went through `parse_args_normalized` + SUPPORTED/FORBIDDEN classification. Two parallel pipelines existed for the same action. Concrete failures confirmed by direct execution before the fix:
1. `--url system-default` via composite `--add-model` was silently **persisted as the literal string `"system-default"`** in `model_variants.config` — composite's raw parse never produced the `FORCE_SYSTEM_DEFAULT` sentinel, so even the (already-removed) manual `args.url is FORCE_SYSTEM_DEFAULT` check inside the old handler could never fire. The worst-case manifestation of the bug: a config value that looks like a real, resolvable string all the way through execution.
2. `--add-questions system-default` / `--vision system-default` via composite failed outright instead of applying system-default semantics, because the un-normalized parser never produced the sentinel for those flags either.
3. Any argparse-level usage error inside a composite sub-action (e.g. `--reasoning garbage-value`) called `sys.exit()` directly (plain `argparse.ArgumentParser`'s own behavior), unwinding straight past `_handle_composite_flow`'s rollback logic and leaving the just-created experiment permanently un-rolled-back — confirmed via isolated execution: the experiment row survived process exit.

**Fix — 4 parts, all approved together:**
1. **`NonExitingArgumentParser`/`ParserExit`** (`src/core/argv_utils.py`): an `argparse.ArgumentParser` subclass overriding only `exit()` (not `error()` — `error()` already calls `self.exit(2, ...)` internally, so overriding `exit()` alone catches both `error()` and `--help`'s direct `parser.exit()` call at one control point). `ParserExit(status, message)` carries the exit code argparse itself decided; the message is already printed to stderr before the exception is raised. Every module's `create_parser()` now returns this subclass instead of a plain `ArgumentParser`. Exit-code convention made explicit: help/clean parser exit → 0; usage error → 2; operational/domain error → 1 (unchanged, decided inside each action, never by the parser).
2. **Request/Result dataclasses per action**: `AddModelRequest`/`AddModelResult` (`bcllm_model.py`), `AddQuestionsRequest`/`AddQuestionsResult` (`bcllm_questions.py`), `AddRunRequest`/`AddRunResult` (`bcllm_run.py`) — pure structured objects. The paired `add_model_action`/`add_questions_action`/`add_run_action(request, conn) -> *Result` functions take no argv/`Namespace`, call no `print()`, raise no `SystemExit`. Flow: `argv → parse/normalize/validate → structured request → shared action → structured result`.
3. **One shared adapter per action**, used identically by both callers: `run_add_model`/`run_add_questions`/`run_add_run(argv, conn=None) -> int`. When `conn=None` (standalone, called from each module's `main()`), the adapter opens its own connection **only after parsing succeeds** and closes it itself. When `conn` is passed (composite, from `bcllm.py::_execute_single_action`), the adapter reuses the shared connection and does not close it — this is the single mechanism that satisfies both "same adapter/action for both callers" and "a usage error never opens a database connection." `handle_add_model`/`handle_add_questions`/`handle_add_run` (the old, standalone-only handlers) are deleted — there is no longer a second implementation to keep in sync.
4. **`bcllm.py::_execute_single_action`** now delegates to `bcllm_model.run_add_model`/`bcllm_questions.run_add_questions`/`bcllm_run.run_add_run` instead of building its own parser+dispatch inline. Because `run_add_*` never lets argparse's `sys.exit()` escape, a usage error mid composite sub-action now returns a normal exit code exactly like a domain-level error already did — `_handle_composite_flow`'s existing rollback (`_rollback_created_experiment`, compensating `DELETE`s — see the "not atomic" entry above for why this isn't a SQLite transaction/SAVEPOINT: `src/db/repository.py` commits once per `save()`/`update_status()`/`delete()`, 11 independent call sites confirmed by grep, so there is no open transaction left to roll back by the time a later action fails) now fires correctly for usage errors too, not just domain errors.

**A second-order bug this exposed and fixed in the same pass — seed parsing:** three independent, buggy implementations of seed-string parsing existed (`resolve_seed`, `resolve_seed_for_run` — confirmed dead code, zero callers, fixed anyway for consistency — and `build_run_config_dict`'s inline closure), all silently swallowing unparseable text into `None` instead of reporting an error. Unified into one shared `parse_seed_value_strict(value: str | int | None) -> int | str | None` (`src/core/config_resolver.py`): `system-default` → `None` (deliberate, no fallback); `'AUTO'` (case-insensitive) → kept as the literal `'AUTO'` marker for later resolution; a plain `int` is passed through unchanged (needed for a real caller that sets `args.seed` to a raw `int`); `0` and negative integers are valid; any other text raises `ValueError` — never silently coerced to `None`. Wired through both reachable call sites (`resolve_seed` via `bcllm_experiment.py`, `build_run_config_dict` via `bcllm_run.py`). `run_add_run`'s adapter validates seed **format** (the string-shape check) before opening a connection, even though `add_run_action` (via `build_run_config_dict`) also validates it later as part of actually resolving the value (`AUTO` generation, experiment-config inheritance — both genuinely need the connection) — the early check exists specifically so an invalid `--seed` never opens a connection, matching every other usage error, not because the later check became redundant.
A further second-order bug the seed fix itself exposed: `_handle_composite_flow`'s own experiment-creation step (`--create-experiment ... --seed <bad>`, composite) only caught `ValueError` for the pre-existing TOCTOU "already exists" case and re-raised everything else — meaning an invalid `--seed` at experiment-creation time (which previously could never raise, since it silently became `None`) produced an **uncaught traceback**. Fixed with an `else` branch that prints the error and returns exit code 1 (matching standalone `handle_create_experiment`'s convention for the same error — this is the pre-existing `--create-experiment` validation pathway, not one of the 3 new single-action adapters, so it does not use `ParserExit`/exit 2). Nothing is persisted in this case: the raise happens during config-dict resolution, before the experiment `INSERT`.

**Transactional protection investigated, not implemented (explicit gate — user asked to see the evidence before any implementation):** `src/db/repository.py` has 11 independent `conn.commit()` calls, one per `save()`/`update_status()`/`delete()` — confirmed by grep. A real SQLite `SAVEPOINT` wrapper around the whole composite flow would require removing all of them (a larger, separate refactor changing commit behavior for every standalone `--add-*` invocation too, not just composite) — not attempted here. The compensating-`DELETE` rollback (pre-existing, unchanged by this fix) remains the mechanism.

**Regression coverage:**
- `tests/unit/cli/test_bcllm_model_same_action_same_path.py`, `test_bcllm_run_same_action_same_path.py` (new): help returns 0 with no DB connection; FORBIDDEN/invalid-choice usage errors rejected before any connection is opened; `system-default` on every SUPPORTED flag persists as `None` in the stored config, never the literal string; the same `run_add_model`/`run_add_run` adapter, called with a standalone-shaped argv and a composite-shaped synthetic argv, produces identical persisted config (success case) and identical rejection (usage-error case).
- `tests/unit/cli/test_composite_flow_rollback.py` (new): calls `bcllm._handle_composite_flow` directly (isolated `DATABASE_PATH`/`LOG_FILE_PATH` via `tmp_path`, no real `.env`/DB touched) — an argparse-level usage error mid `--add-model` (invalid `--reasoning` choice, and separately `--url system-default`) rolls back the just-created experiment (row confirmed absent afterward), exit code 2 propagated correctly; a bad `--seed` on `--add-run` is caught earlier, at experiment-creation time (documented above), exit code 1, nothing persisted; a control case confirms a successful composite flow does **not** roll back, proving the failure-path assertions are exercising the actual rollback branch.
- `tests/unit/cli/test_questions_system_default.py` and `test_question_snapshot_equivalence.py` updated to call `add_questions_action(AddQuestionsRequest(...), conn)` directly instead of the deleted `handle_add_questions`; `test_bcllm_model_system_default.py` updated to expect `ParserExit` instead of `SystemExit` for the 16 parametrized parser-error cases (`NonExitingArgumentParser` no longer lets those escape as bare `SystemExit`).
- `tests/cli_suite/cases/questions.yaml::AQ-003`/`AQ-004` — **expectations updated, not the code**: these composite `--add-questions null` cases previously asserted exit code 1 and the old domain-level `"Error: Invalid question specification"` message, which was itself the pre-fix bug (composite bypassing normalization, so the deprecated-`'null'` rejection that standalone already applied never fired for composite). Confirmed standalone `--experiment X --add-questions null` already returned exit 2 with argparse's own deprecated-literal message before this fix — composite now matches it, per the "same adapter, same action" invariant this whole entry implements. Not a new semantic decision: the atomicity assertion these two cases actually exist to test (experiment row count, and — for AQ-004 — model-variant row count, both 0 after rollback) is unchanged and still passes; only the exit code/message expectation moved to match the now-consistent behavior.
- Full verification 2026-08-19: `python tests/cli_suite/run.py --profile full --yes` — 44 PASS + 1 EXPECTED_FAILURE (unchanged from the marco-4A baseline, after the AQ-003/AQ-004 expectation update above); full-suite `pytest -q --ignore=tests/test_error_collector.py --ignore=tests/test_model_capabilities.py` — 966 passed (944 baseline + 22 new), 48 failed / 18 skipped / 39 errors, all three counts byte-identical to the pre-fix baseline — zero regression.
**Classification:** Confirmed architectural bug (two independent implementations of the same action, silently diverging) with one severe concrete manifestation (silent literal-string persistence of `"system-default"`) and two second-order bugs it exposed once fixed (seed parsing, the TOCTOU `ValueError` handler's re-raise). Fixed per explicit, itemized user approval — see the plan/checkpoint history for the exact 8-point specification this satisfies. Separated from, and a prerequisite to, the still-not-started Typer conversion (`argparse.ArgumentParser` → `typer.Typer`/`click.Command`), per explicit instruction to keep the two efforts distinct.

### ✅ Composite `--create-experiment` + `--add-*` rollback is now a real SQLite transaction, not a compensating delete

**Resolved:** 2026-08-19, as a checkpoint separate from the Typer conversion — full design and rationale in `docs/status/composite-flow-unit-of-work-design.md`; the preceding investigation (options, tradeoffs, performance/contention measurements) is in `docs/status/composite-flow-atomicity-investigation.md`.
**Description:** The compensating-DELETE mechanism (`_rollback_created_experiment`, ~100 lines, itself only added earlier the same day as part of the "same action, same path" fix above) has been replaced with a real transaction: `src/db/unit_of_work.py::UnitOfWork` wraps experiment creation + every requested `--add-*` action in one `BEGIN IMMEDIATE` … `COMMIT`/`ROLLBACK`, restricted permanently to `Experiment`/`ModelVariant`/`QuestionSnapshot`/`Run` creation — never `ResponseRepository`/`ResultWriter`/`--execute` (deferring those commits would break `docs/contracts/idempotency.md`'s crash-safe partial-resume guarantee).
**Design highlights** (full detail in the design doc's "Adjustments incorporated" section):
- **Explicit participation, no global/contextvar/connection-inference:** exactly 4 repository `save()` methods gained a `commit: bool = True` keyword-only parameter; every other caller is unaffected by default.
- **Fail-safe by default:** `UnitOfWork` rolls back on `__exit__` unless `.commit()` was explicitly called — matches the composite flow's control flow, where "this sequence failed" is a returned exit code, not a raised exception.
- **`assert_active()` guard:** raises if the transaction closed out from under the unit of work (a future action forgetting `commit=False`), checked after every participating write and inside `commit()` itself.
- **Pure parse phase before any connection:** every requested action's argv is now fully parsed (via 3 new pure functions, `parse_add_model_request`/`parse_add_questions_request`/`parse_add_run_request`) *before* `get_database_connection()` is ever called — this also surfaced and fixed a parallel gap `bcllm_experiment.py::create_parser()` had (still a plain `argparse.ArgumentParser`, unlike the other 3 modules — converted to `NonExitingArgumentParser` here).
- **Outer exception boundary wraps the entire `with UnitOfWork(...)` statement**, not just its body — a failure in `__enter__` itself (a busy-database timeout on `BEGIN IMMEDIATE`) cannot skip it, since Python never calls `__exit__` if `__enter__` raises. Any unexpected exception (busy database, a failed `commit()`, a failed `rollback()`) now produces exit code 1 and a generic user-facing message, never a raw traceback — closing the exact gap `composite-flow-atomicity-investigation.md` §4 found and left open.
- **`_rollback_created_experiment` deleted entirely.** The TOCTOU concurrent-creation race handling is unchanged in shape, just nested inside the transaction (confirmed empirically: a `UNIQUE`-constraint `IntegrityError` does not poison the surrounding SQLite transaction).
- **Disclosed behavior improvement:** a pre-existing experiment found via TOCTOU now correctly has *this invocation's own* `--add-*` writes rolled back on a later failure (previously they silently survived un-rolled-back, since "not ours to delete the experiment" incorrectly also meant "not ours to undo our own actions").
- **Disclosed exit-code change:** `--create-experiment X --add-run --seed <invalid>` now returns exit 2 (from `--add-run`'s own, earlier, stricter pure-parse-phase check) instead of the old exit 1 — but only when `--add-run` is actually requested; the same invalid `--seed` without `--add-run` present still returns exit 1, unchanged.
- **`load_dotenv` moved out of module-import time** into `bcllm.py::_bootstrap_environment()`, called only from a new `cli_main()` shared by direct execution and the installed console script (`setup.py`'s entry point updated from `bcllm:main` to `bcllm:cli_main` — fixing a second long-standing issue, that installed-script path would otherwise have silently skipped `.env` loading after this change). Importing `bcllm.py` now has zero side effects.
- **Dead code left untouched, as explicitly instructed:** `bcllm_experiment.py::_add_models_at_creation`/`_create_question_snapshots` (unreachable via the real CLI entry point, still exercised by some direct-call unit tests) were not removed.
**A new, unrelated bug found incidentally while writing tests** (not fixed, see the Bugs section above): experiments created with no `--seed` store the literal string `"OFF"` in their config, which `--add-run`'s inheritance then rejects — pre-existing, predates this session.
**Regression coverage:** `tests/unit/db/test_unit_of_work.py` (9 tests, the `UnitOfWork` class in isolation: commit persists, no-commit-call rolls back, exception-inside rolls back, a caller catching the exception still rolls back, the `assert_active()` guard, a real busy-database contention test via a second connection — not a mock — and a proxy-connection-based rollback-failure test, since `sqlite3.Connection`/`Cursor` are immutable C types that can't be monkeypatched directly). `tests/unit/cli/test_composite_flow_rollback.py` (rewritten, 12 tests): usage/domain errors roll back every table (not just `experiments`) with `PRAGMA foreign_key_check`/`integrity_check` verified after every rollback; failures injected after only the model persisted, after model+questions persisted, and after all three (model+questions+run) persisted via a `commit()`-failure injection; the busy-database/commit-failure/rollback-failure cases at the full composite-flow level (exit 1, generic message only, connection always closed); the disclosed TOCTOU behavior change.
**Verification:** full `pytest` (excluding the 2 known pre-existing broken-collection files) — 983 passed (971 baseline + 12 new), 48 failed / 18 skipped / 39 errors, all three byte-identical to every prior baseline this session — zero regression. `python tests/cli_suite/run.py --profile full --yes` — 44 PASS + 1 EXPECTED_FAILURE, unchanged, confirming the real subprocess entry point (including the new bootstrap split) works end-to-end.
**Classification:** Deliberate architectural upgrade from a compensating (non-ACID) rollback mechanism to a real database transaction, implemented per explicit, itemized user approval with 8 required adjustments (all incorporated — see the design doc). Separated from, and a prerequisite to, the still-not-started Typer conversion.

### ✅ Randomization Seed vocabulary separated from Model Seed; Planner no longer silently re-derives a run's frozen seed decision at `--execute` time

**Resolved:** 2026-08-20, Checkpoint A of a two-checkpoint request — full investigation (producers/consumers survey, the Planner bug writeup, the `RANDOM_SEED`/`RUN_RESPONSES_SEED` naming divergence) in `docs/status/seed-vocabulary-separation-investigation.md`. Checkpoint B (Model Seed: `--model-seed`/`MODEL_SEED`, sent as the API request's `seed` field, participating in `variant_signature`) is deliberately deferred, not part of this entry, per explicit instruction not to mix the two in one diff.
**Description:** Two previously-conflated concepts — "Randomization Seed" (controls only `AnswerRandomizer`'s option shuffling; belongs to Experiment and Run; never sent to the API) and the not-yet-implemented "Model Seed" (would be sent as the API request's `seed` field; belongs to Experiment and Model Variant, not Run) — were both informally called "seed" throughout code and docs under inconsistent names (`--seed`, `RUN_RESPONSES_SEED`, `RANDOM_SEED`). This checkpoint standardized on "Randomization Seed" everywhere (CLI `--randomization-seed`, `.env`/config key `RANDOMIZATION_SEED`, local names/functions `randomization_seed`) with no alias, fallback, or backward-compatible acceptance of the old names — this is a pre-production system with only test data, so the rename was applied directly rather than layered with compatibility shims.
**A real, live bug found during the investigation and fixed here:** `Planner._resolve_seed_effective` (renamed `_resolve_randomization_seed_effective`) used `run_config.get("RUN_RESPONSES_SEED")` and treated a missing key the same as an explicit `None`, so on every `--execute` it silently re-applied Experiment→Run inheritance and could override a Run's own frozen "don't randomize" (`None`) decision with the Experiment's seed. Fixed by requiring the key to be present (`PlannerValidationError` if absent) and by removing `experiment_row` from the function's signature entirely, so no fallback path exists at any point after Run creation — inheritance now happens exactly once, at Run creation, never again.
**A second, related bug fixed in the same pass:** `build_run_config_dict`'s inline seed-inheritance logic treated "Experiment has nothing configured" (`None`) the same as `AUTO`, silently auto-generating a random seed for a Run whose Experiment never asked for randomization at all. Fixed in the new canonical `ConfigResolver.resolve_randomization_seed_for_run()` (transformed, not simply deleted, from the previously-dead `resolve_seed_for_run` per explicit instruction — its original `env_key`-based signature was itself architecturally wrong for Run-level resolution, which must never consult `.env`, only inherit from the Experiment's own frozen config; that mismatch is why it had zero production callers before).
**Textual sentinels retired outright:** `"OFF"`/`"NULL"`/`"NONE"`/`""` are no longer recognized anywhere as "no randomization" — only Python `None`/JSON `null` is (closes the `"OFF"` bug moved to this entry from the Bugs section above, `--randomization-seed`'s system-default/AUTO/None/int states are validated strictly by the renamed `ConfigResolver.parse_randomization_seed_strict`/`Planner._normalize_randomization_seed_value`, both raising for anything unparseable instead of silently coercing).
**Renamed symbols (non-exhaustive, full list in the investigation doc):** `ConfigResolver.resolve_randomization_seed`/`resolve_randomization_seed_for_run`/`parse_randomization_seed_strict`; `Planner._resolve_randomization_seed_effective`/`_normalize_randomization_seed_value`; `PlanRun.seed_effective` → `PlanRun.randomization_seed_effective`; `AddRunRequest.seed`/`AddRunResult.seed_display` → `.randomization_seed`/`.randomization_seed_display`; CLI flag `--seed` → `--randomization-seed` on both `bcllm_experiment.py` and `bcllm_run.py`.
**Dead code deleted** (confirmed zero production callers via grep before deletion, per "no historical compatibility" instruction): `ConfigResolver._generate_seed_from_name`; `bcllm_experiment.py`'s unused `generate_seed`/`parse_seed_value` pair.
**Documentation corrected**, including two false claims found and fixed alongside the rename (not asked for directly, but directly analogous — leaving them wrong would have been inconsistent): `configuration-hierarchy.md` and `determinism.md` both previously stated "Experiment seed can be changed after creation" — false; it is frozen at creation like every other Experiment config value, exactly like Run/Model Variant config. `configuration-hierarchy.md` also had the same false claim about Experiment prompts. Also fixed: `system-default-semantics.md`'s stale `RANDOM_SEED` references (vs. the code's actual `RUN_RESPONSES_SEED`, now `RANDOMIZATION_SEED`), `cli-commands.md`'s `--seed` flag rows, `configuration-reference.md`'s `RUN_RESPONSES_SEED` table rows and `.env` example, `data-auditability.md`'s unqualified "Seed" mention, `database-schema.md`'s `RUN_RESPONSES_SEED` JSON examples, and stale `--seed`/lowercase "seed" mentions in `roadmap.md`/`implementation-status.md`.
**Regression coverage:** `tests/unit/core/test_planner.py::test_planner_reads_run_own_none_randomization_seed_without_falling_back_to_experiment` — the exact scenario the bug produced: Experiment `RANDOMIZATION_SEED=42`, Run created with `system-default` (stores `None`), execution must keep `None`, not revert to 42. `test_planner_raises_clear_error_when_run_missing_randomization_seed_key` — an absent key on the Run raises `PlannerValidationError`, not a silent fallback. `tests/test_config_resolver.py::TestResolveRandomizationSeedForRun` (rewritten) — `test_inherited_none_from_experiment_resolves_to_none_not_auto_generated`, `test_system_default_breaks_inheritance_even_with_experiment_seed`, `test_invalid_cli_value_raises_value_error`, `test_invalid_inherited_experiment_value_raises_value_error`. `tests/cli_suite/cases/run.yaml::RN-009` (new) — real subprocess: `--add-run --randomization-seed system-default` against an Experiment with `RANDOMIZATION_SEED=77` stores `null`, not `77`. `RN-010` (new) — invalid `--randomization-seed` is a usage error, exit 2, `runs` table unchanged.
**Verification:** full `pytest -q --ignore=tests/test_error_collector.py --ignore=tests/test_model_capabilities.py` — 986 passed (983 baseline + 3 net new), 48 failed / 18 skipped / 39 errors, all three byte-identical to every prior baseline — zero regression. `python tests/cli_suite/run.py --profile full --yes` — 47 cases, 46 PASS + 1 EXPECTED_FAILURE (45+1 baseline, +2 new cases RN-009/RN-010 both passing).
**Classification:** Vocabulary/naming correction combined with a confirmed live correctness bug in the execution pipeline (Planner silently overriding a frozen Run decision), fixed together per explicit, itemized (10-point) user approval. Checkpoint B (Model Seed) intentionally not started — separate diff, per instruction.

### ✅ Model Seed implemented (`MODEL_SEED`/`--model-seed`); OpenRouterClient no longer independently reconstructs the request payload it sends

**Resolved:** 2026-08-20, Checkpoint B — full design in `docs/status/model-seed-checkpoint-b-design.md`. Separate checkpoint from Checkpoint A (Randomization Seed vocabulary), per explicit instruction not to mix the two in one diff.
**Description:** Two changes, approved and implemented together because the second was a mandatory architectural prerequisite the user required before the first could be trusted:

1. **Single canonical request payload.** Previously, `ExecutionEngine` hand-built a `request_payload` dict purely for the `request_json` audit field (never actually sent), while `OpenRouterClient.chat_completion` independently built its own `payload` dict from scalar kwargs — the one actually POSTed. A third, independent reimplementation of the same conditional-omission logic lived in `tests/test_request_config_application.py`, sufficient to hide either of the first two silently diverging. Fixed by extracting the ONE shared builder, `src/api/request_payload.py::build_chat_completion_payload`, called **exactly once per attempt** by `ExecutionEngine.api_call_with_retry` — the same object is then serialized into `request_json` and passed unmodified to `OpenRouterClient.chat_completion(payload=..., base_url=...)`, whose signature no longer accepts individual scalar parameters (`model_id`, `temperature`, `top_p`, etc.) at all. This structurally eliminates the "sent but not audited / audited but not sent" risk class the user flagged before approving — there is no second construction left to drift from the first.
2. **`MODEL_SEED` (Model Seed)** — belongs to Experiment and model_variant, never Run; resolved `CLI > .env > None` at Experiment creation and `CLI > Experiment's own frozen value > None` at `--add-model` (no `.env` consultation at that tier, matching `PROVIDER`); `system-default` breaks inheritance via the same mechanism `--provider system-default` already uses; integer including `0` sent verbatim as the API request's `"seed"` field (explicit `is not None`, never truthy); `None` omits the key entirely; no `AUTO` state anywhere; participates in `variant_signature` (`SIGNATURE_FIELD_ORDER`, directly after `repeat_penalty`) — no back-compat handling for previously-stored signatures, per explicit instruction (pre-production, test data only, per ADR-003). Total separation from `RANDOMIZATION_SEED`: different resolvers, different config keys, never share a code path; `RANDOMIZATION_SEED` never reaches the API, `MODEL_SEED` never reaches `AnswerRandomizer`.

**`debug` field investigation (empirical, not assumed):** a controlled 2-call smoke test against the real OpenRouter API (`google/gemini-2.5-flash-lite`, pinned `google-ai-studio` provider, `MODEL_SEED=42`, minimal output) found that `debug.echo_upstream_body` adds exactly one thing — a first SSE chunk containing the transformed request body actually sent to the upstream provider. Cost, tokens, and provider were already present identically with debug on or off (not gated by the flag, contrary to a plausible assumption). No field confirms a provider *honored* a requested seed — only that it was forwarded upstream (confirmed via the seed appearing in the echoed body); the system correspondingly never claims `MODEL_SEED` guarantees deterministic output, only that the request asked for one. Streaming is required for debug (confirmed), but BCLLM already always streams — no client change needed for that. `src/api/stream_aggregator.py` already captured `debug_info` correctly (built, unused, since nothing previously set `debug: true` in the real payload); no new DB columns were added — `responses.raw_response`/`raw_response_consolidated` already losslessly capture the echo once the request side correctly requests it. `debug` now flows through the same canonical payload as everything else — `request_json` always accurately reflects whether it was requested (previously it could not, since it was built separately from the real payload). Default stays **off** (`OPENROUTER_DEBUG_ENABLED`, unchanged) — OpenRouter's own docs mark the flag "not for production," and the echoed shape is provider-specific, so enabling it globally across a multi-provider benchmark would produce structurally inconsistent audit data by default; it remains fully available and fully audited for an explicit opt-in run.
**Regression coverage:** `tests/unit/api/test_request_payload.py` (25 tests) — the canonical builder in isolation: None-omission for every field, `0`/falsy values preserved, field order, reasoning-conflict rule, debug field. `tests/unit/core/test_request_fidelity.py` (15 tests, the mandatory fidelity test) — `json.loads(request_json) == payload actually passed as json= to the POST`, across no-optionals/all-optionals/`model_seed` None-0-42/provider-lock/reasoning/structured/debug-on-off, secrets absent from all persisted records, the upstream echo staying distinguishable from `request_json` (never overwriting it), malformed debug not invalidating a normal response, repeated-attempt payload determinism. `tests/test_config_resolver.py::TestModelSeedResolution` (13 tests) — CLI>env>None at Experiment level, CLI>Experiment>None at variant level (never `.env`), `system-default` breaking inheritance even with an Experiment value present, `0` preserved, total separation from `RANDOMIZATION_SEED`. `tests/test_variant_signature.py::TestModelSeedInSignature` (7 tests) — position, collision-regression (two variants differing only by `--model-seed`), stable full field-order assertion. `tests/unit/core/test_planner_model_seed.py` (6 tests) — config row → `ModelConfig.model_seed` mapping. `tests/unit/core/test_execution_engine_model_seed.py` (6 tests) + `tests/integration/test_seed_independence.py` (3 tests, real Planner+ExecutionEngine+in-memory-DB path with `RANDOMIZATION_SEED=7` and `MODEL_SEED=42` configured together) — each seed proven to affect only its own responsibility. `tests/cli_suite/cases/model.yaml` (AM-011..015, new) and `experiment.yaml` (CE-012, new) — real subprocess coverage of `--model-seed` at both Experiment and Model Variant creation, `0` preserved, `system-default` inheritance-break, invalid value rejected, `variant_signature` collision regression, Experiment→variant inheritance.
**Verification:** full `pytest -q --ignore=tests/test_error_collector.py --ignore=tests/test_model_capabilities.py` — 1063 passed (986 baseline + 77 net new), 48 failed / 18 skipped / 39 errors, all three byte-identical to every prior baseline this session — zero regression. `python tests/cli_suite/run.py --profile full --yes` — 53 cases, 52 PASS + 1 EXPECTED_FAILURE (47+1 baseline, +6 new cases all passing), including the real `--execute` subprocess cases (EX-001..003) confirming the refactored `ExecutionEngine`/`OpenRouterClient`/`request_payload` architecture works end-to-end through a real subprocess, not just at the unit level.
**Classification:** Deliberate architectural upgrade (single-construction request payload, closing a structural audit-fidelity risk class) combined with a new, fully-specified model parameter, implemented together per explicit, itemized user approval and a required empirical investigation (not assumed) of the `debug` field's real behavior before finalizing its design.

---

## How to Add New Issues

When you discover a new issue, add it to this document with:

```markdown
### [Severity] Issue Title

**Severity:** Critical | High | Medium | Low  
**Impact:** [What is affected]  
**Description:** [What is wrong]  
**Reproduction:** [How to reproduce, if bug]  
**Suggested Fix:** [What should be done]  
**Effort:** Small | Medium | Large  
**Dependencies:** [What else needs to change]
```

---

## Related Documents

- [status/implementation-status.md](implementation-status.md) — What exists
- [status/roadmap.md](roadmap.md) — Intent and priorities
- [contracts/](../contracts/README.md) — System invariants (issues may violate these)
