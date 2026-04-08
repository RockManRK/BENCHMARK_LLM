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

### Hardening 1: Randomizer Determinism
- **What**: `option_letter_map` generated ONCE per run, shared by all items.
- **Where**: `AsyncOrchestrator._execute_run_with_semaphore()` generates the map before spawning tasks.
- **Why**: Ensures all questions in a run see identical option shuffling regardless of execution order or concurrency level. Eliminates per-item RNG race conditions.

### Hardening 2: Sliding Window Concurrency
- **What**: Dynamic task creation using `asyncio.wait(FIRST_COMPLETED)`.
- **How**: Initial batch of `max_concurrency` tasks created, then each completion triggers creation of the next pending task.
- **Why**: Memory-efficient for large plans (no 10,000+ pre-created tasks). True sliding window — as soon as one slot frees, the next item starts.

### Hardening 3: AsyncWriter Retry + Fail-Fast Abort
- **What**: 3 retries with exponential backoff (0.5s, 1.0s, 1.5s), then abort.
- **How**: `AsyncWriter._write_result_with_retry()` loops up to `MAX_RETRIES`. On final failure: sets `abort_event`, logs `WRITE_ABORT`, returns.
- **Orchestrator response**: Detects `abort_event`, cancels pending tasks, still calls `RunFinalizer` to persist collected data.

### Hardening 4: Error Versioning
- **What**: Multiple error rows per item with `attempt_number`, error history prepended to `response_text` on success.
- **Schema**: `errors` table now has composite PRIMARY KEY `(error_id, attempt_number)`.
- **Behavior**: Each error write queries `MAX(attempt_number)` and increments. On eventual success, `ResultWriter._get_error_history()` prepends chronological error log to response text.
- **Why**: Full observability into retry attempts while maintaining single response row per item.

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
