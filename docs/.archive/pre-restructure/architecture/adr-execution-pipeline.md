# ADR: Single Execution Pipeline with Idempotent Planning and Run Finalization

**Document Type:** Architecture Decision Record
**Project:** Benchmark LLM V2
**Date:** 2026-04-08
**Status:** Accepted
**Phase:** 6 — Documentation

---

## Context

The execution pipeline had duplicated logic, silent metric corruption (`runs.duration` double-counting on re-execution), and dead code paths. Multiple components competed to update `runs.*` state. There was no configurable concurrency and no idempotent planning.

---

## Decisions

### Decision 1: Single Pipeline with Configurable Concurrency

**What:** `AsyncOrchestrator` is the sole execution entry point. Concurrency controlled by `BCLLM_MAX_CONCURRENCY` env var (default 1).

**How:** `asyncio.Semaphore` wraps item execution. `concurrency=1` behaves like sequential.

**Why:** Eliminates dual sync/async paths. Single point of control. Env var keeps CLI clean.

---

### Decision 2: Idempotent Planner

**What:** Planner queries DB for existing responses and excludes them from the `ExecutionPlan`.

**How:** `_get_executed_items(run_id)` queries `responses` where `raw_response IS NOT NULL`.

**Why:** Prevents API calls for completed items. Cost protection is mandatory (I3). Items with errors only are NOT excluded (transient failures can be retried).

**Trade-off:** Planner gains DB awareness. Intentional — cost protection belongs at plan-build time, not execution time.

---

### Decision 3: RunFinalizer as Single Owner

**What:** `RunFinalizer` is the ONLY component that updates `runs.status` and `runs.duration`.

**How:** `finalize_run(run_id)` computes from fresh DB queries: `SUM(latency_ms)` for duration, status from counts.

**Why:** Eliminates in-memory accumulation bugs. Duration derived from DB state, not result lists. Single source of truth.

**What was removed:**
- `AsyncOrchestrator._update_run_statuses()`
- `ResultWriter._update_run_status_and_duration()`

---

### Decision 4: Dead Code Removal

**What was removed:**
- `ResultWriter.write_results()` — dead batch path
- `ResultWriter._update_run_status_and_duration()` — duplicate of RunFinalizer
- `ExecutionEngine.execute()` — sync wrapper (second entry point)
- `ExecutionEngine._call_api_sync()` — sync API caller with ThreadPoolExecutor

**What was fixed:**
- `ResponseRepository.save()` and `ErrorRepository.save()`: `INSERT OR REPLACE` → `INSERT OR IGNORE`
- `running` status removed from schema (never set, caused confusion)

**Why:** Eliminates ambiguity, reduces maintenance, prevents accidental usage.

---

### Decision 5: Immediate Persistence

**What:** `AsyncWriter` continues per-item DB writes via `INSERT OR IGNORE`.

**Why:** Each result persisted immediately after execution. No batch accumulation.

---

## Invariant Mapping

| Invariant | How Satisfied |
|-----------|---------------|
| I1 — Single pipeline | `AsyncOrchestrator` sole entry; semaphore for concurrency |
| I2 — Immediate persistence | `AsyncWriter` per-item writes |
| I3 — Strong idempotency | Planner excludes executed items; no API call made |
| I4 — Consolidation from DB | `RunFinalizer` computes from DB queries |
| I5 — Single owner | `RunFinalizer` only component updating `runs.*` |
| I6 — Duration as int ms | Stored as `SUM(latency_ms)` integer |
| I7 — Writer safety | `INSERT OR IGNORE`; serialized via `AsyncWriter` |
| I8 — Tests | Integration tests for skip/duration/concurrency |

---

## Known Gaps

_No open gaps. All previously identified issues have been resolved._

### Resolved Gaps
- ~~Write failure resilience~~: **RESOLVED** — AsyncWriter now retries 3x with exponential backoff, then aborts the run with clear logging. RunFinalizer still runs on abort to persist whatever was collected.

---

## Hardening Additions (Phase 2)

### Hardening 1: Randomizer Determinism per Option Count
- **What**: `option_letter_map` generated ONCE per run, per option count (e.g., 3-option questions get map_3, 4-option get map_4).
- **Where**: `AsyncOrchestrator._execute_run_with_semaphore()` generates maps lazily via `_get_option_map(option_count)`.
- **Why**: Ensures all questions with the same option count share identical option shuffling, while supporting variable option counts (A–C, A–D, A–E) in the future. Each option_count gets an independent seed derived from `run_seed * 1000 + option_count`.
- **Test**: `TestOptionMapPerOptionCount` proves determinism for same and different counts.

### Hardening 2: Sliding Window Concurrency
- **What**: Dynamic task creation using `asyncio.wait(FIRST_COMPLETED)`.
- **How**: Initial batch of `max_concurrency` tasks created, then each completion triggers creation of the next pending task.
- **Why**: Memory-efficient for large plans (no 10,000+ pre-created tasks). True sliding window — as soon as one slot frees, the next item starts.
- **Test**: `TestSlidingWindowConcurrency` proves 11 items with concurrency=10 starts 11th after any of first 10 complete.

### Hardening 3: AsyncWriter Retry + Fail-Fast Abort
- **What**: 3 retries with exponential backoff (0.5s, 1.0s, 1.5s), then abort.
- **How**: `AsyncWriter._write_result_with_retry()` reuses a single `ResultWriter` instance. On final failure: sets `abort_event`, logs `WRITE_ABORT`.
- **Orchestrator response**: Checks `abort_event` before scheduling, immediately after `wait()`, cancels pending tasks, still calls `RunFinalizer`.
- **Abort semantics**: No new tasks scheduled after abort; in-flight tasks cancelled promptly.
- **Test**: `TestAsyncWriterRetry` proves retry succeeds on 2nd attempt and aborts after max retries.

### Hardening 4: Error Versioning with Canonical Key
- **What**: Multiple error rows per item with `attempt_number`, error history prepended to `response_text` on success.
- **Schema**: `errors` table uses composite PRIMARY KEY `(response_id, attempt_number)`. `response_id` is deterministic: `resp-{run_id}-{variant_id}-{snapshot_id}`.
- **Canonical key**: All error queries use `response_id` — both writes (`_write_error`) and reads (`_get_error_history`). No coupling risk.
- **Why**: Full observability into retry attempts while maintaining single response row per item.
- **Test**: `TestErrorVersioning` and `TestCanonicalErrorKey` prove correctness.

### Hardening 5: ~~Schema Migration~~ — REMOVED
- Schema migration is no longer provided. Only the current errors table schema is supported.
- Historical schema migrations are not offered — this is an actively developed system.

### Hardening 6: Transaction Strategy
- **What**: Standardized autocommit — no `BEGIN IMMEDIATE` anywhere.
- **Why**: All writes use per-item `commit()`. RunFinalizer runs after writer fully drains, so no concurrent writes exist. `BEGIN IMMEDIATE` was unnecessary and could conflict with future parallel execution.
- **Test**: `TestTransactionStrategy` proves no "database is locked" errors at concurrency=4.

### Single-Writer Enforcement for Errors

| Decision | Rationale |
|----------|-----------|
| `ErrorRepository` removed entirely | Contained no essential domain logic. Write path violated single-writer contract and assumed old schema. Read paths were trivial SELECT wrappers. Sole production consumer (ExportService) replaced with direct SQL. |
| `Error` dataclass removed | Fragile schema mirror requiring manual sync. No production consumers. Eliminated to prevent future schema divergence. |
| ExportService reads errors via direct SQL | Single SELECT query does not justify a repository abstraction. Explicit query includes `response_id` and `attempt_number` for error versioning observability. |
| Tests use ResultWriter exclusively | No test may write to `errors` via raw SQL. Tests exercise the production write path (`ResultWriter.write_result()` with a failure `ExecutionResult`). |
| No schema migration provided | Only the current errors table schema is supported. Historical schemas are not migrated. |

### Resolved Warnings from Essence Guardian
| Warning | Resolution | Test |
|---------|------------|------|
| W1: Error history key mismatch | Canonical key = `response_id` (both writes and reads) | `TestCanonicalErrorKey` |
| ~~W2: Schema migration missing~~ | ~~Removed — migration no longer provided~~ | — |
| W3: Option map assumes uniform count | Maps per `(seed, option_count)` pair | `TestOptionMapPerOptionCount` |
| W4: Abort window between waits | Abort checked before scheduling + after `wait()` | `TestAbortWindowClosure` |
| W5: New ResultWriter per retry | Single `_result_writer` instance reused | `TestResultWriterReuse` |
| W6: BEGIN IMMEDIATE overlap | Removed — standardized autocommit | `TestTransactionStrategy` |
| ErrorRepository schema divergence | Removed entirely — single writer enforced | Integration tests via ResultWriter |

---

## Consequences

### Positive
- Single execution path eliminates ambiguity
- Duration is always accurate (derived from DB, not accumulated in memory)
- Idempotent planning prevents accidental API costs on re-execution
- Dead code removal reduces maintenance surface
- Write failures no longer silently lose data — they retry then abort cleanly
- Error versioning provides full retry observability in the response record
- Sliding window scales efficiently regardless of plan size
- Randomizer determinism is provable: same seed = same map for all questions

### Risks
- Planner now depends on DB state (intentional, but couples planning to persistence layer)

---

## Source Files

This ADR documents changes to:
- `src/core/async_orchestrator.py` — sliding window, randomizer determinism, abort handling
- `src/core/async_writer.py` — retry logic, fail-fast abort
- `src/core/planner.py` — idempotent planning
- `src/core/run_finalizer.py` — single owner of runs updates
- `src/core/result_writer.py` — error versioning, error history prepending
- `src/core/execution_engine.py` — removed dead code, run-level option map support
- `src/db/schema.py` — `attempt_number` in errors table, removed `running` status
- `src/cli/bcllm_execute.py` — `BCLLM_MAX_CONCURRENCY` env var
- `tests/integration/test_execution_contract.py` — contract validation tests
- `tests/integration/test_execution_concurrency.py` — concurrency tests
- `tests/integration/test_execution_hardening.py` — hardening tests (Issues 1-4)
- `tests/unit/core/test_run_finalizer.py` — RunFinalizer unit tests
