---
type: status
audience: both
last-validated: 2026-08-18
status: active
---

# Known Issues and Technical Debt

**Purpose:** Bugs, technical debt, and design limitations  
**Scope:** Items requiring attention

---

## Bugs

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
**Effort:** Small per group, done incrementally as part of the migration already planned.
**Dependencies:** CLI Typer migration Fase 4.

---

### 🟡 `--resolve-providers` ignores a variant's `BASE_URL`, always hits real OpenRouter

**Severity:** Medium
**Impact:** `--resolve-providers` cannot be pointed at a local stub or llama.cpp-style endpoint — it always calls production OpenRouter (`https://openrouter.ai/api/v1`) regardless of a variant's configured `--url`, unlike execution (`--execute`), which was fixed to honor `BASE_URL` this session (see Resolved Issues below).
**Description:** `src/api/provider_resolver.py::ProviderResolver.__init__` accepts a `base_url` parameter (default `https://openrouter.ai/api/v1`), but `src/cli/bcllm_provider.py::handle_resolve_providers` constructs it as `ProviderResolver(api_key)` — never passing a variant's `BASE_URL`. This is the same class of gap as the already-fixed execution-path bug, but in a separate code path (`bcllm_provider.py` → `ProviderResolver` directly, not through `Planner`/`ExecutionEngine`/`ModelConfig`), so fixing one did not fix the other.
**Discovered:** 2026-08-17, while adding CLI test suite coverage for `--resolve-providers` — it can't be exercised against the suite's local HTTP stub, so the corresponding case (`tests/cli_suite/cases/provider.yaml::PR-001`) is tagged `requires: [openrouter]` and stays `BLOCKED` by default instead of silently passing.
**Suggested Fix:** Resolve `BASE_URL` the same way `Planner._build_model_config()` does (from the variant's config, falling back to the experiment default) and pass it into `ProviderResolver(api_key, base_url=...)`.
**Effort:** Small.
**Dependencies:** None.

---

### 🔴 Review UI queries a non-existent `responses.created_at` column

**Severity:** High
**Impact:** `--review-experiment` and `--review-all` reach the review module (routing is fixed — see Resolved Issues below) but immediately fail with `Error during review: no such column: r.created_at`. The manual review flow (`docs/status/implementation-status.md`'s "Review UI blocked by MODE × MODULE routing issues") is still fully blocked, just by a different, previously-invisible bug.
**Description:** `src/review/review_ui.py` (two call sites: `get_pending_by_experiment` ~line 160 and its multi-experiment counterpart ~line 557) selects `r.created_at` where `r` aliases the `responses` table. `responses` has no `created_at` column (`src/db/schema.sql`) — it has `started_at`/`finished_at` instead.
**Reproduction:** `bcllm --review-all` (or `--review-experiment <name>`) with any pending review item — `sqlite3.OperationalError: no such column: r.created_at`. Confirmed 2026-08-17, discovered immediately after fixing the `Mode.INVALID` routing gap below (which had masked this entirely — the review module was never reachable before).
**Suggested Fix:** Decide whether the intended sort/display field is `started_at` or `finished_at`, then update both query sites and the `ReviewItem` construction that reads `row["created_at"]`. Not fixed here — out of this session's scope (manual review UI, `docs/tests/` explicitly lists it as reserved/future coverage) and the correct replacement field is a product call, not just a rename.
**Effort:** Small once the correct field is decided.
**Dependencies:** None technically; decision-blocked on which timestamp field is correct.

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

### ⚠️ Logging Context Consistency

**Severity:** Low  
**Impact:** Log analysis may require parsing multiple formats  
**Description:**
- Logging includes experiment/run/model/question context
- Context format varies across modules
- No structured logging schema (e.g., JSON logs)

**Suggested Fix:** Standardize log context format across all modules

**Effort:** Medium  
**Dependencies:** Logging refactor

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

### ✅ Logging System Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** Configurable logging with file rotation and crash-safety implemented  
**Impact:** System behavior is observable and debuggable

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
**Not fixed by this change:** the "Review UI queries a non-existent `responses.created_at` column" bug above is unrelated.

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
