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

**Write failure resilience:** If `AsyncWriter` fails to persist a result, the response is lost and the item will be re-executed on next run. This is a known gap to be addressed in a future iteration.

---

## Consequences

### Positive
- Single execution path eliminates ambiguity
- Duration is always accurate (derived from DB, not accumulated in memory)
- Idempotent planning prevents accidental API costs on re-execution
- Dead code removal reduces maintenance surface

### Risks
- Planner now depends on DB state (intentional, but couples planning to persistence layer)
- Write failure gap: lost responses require re-execution

---

## Source Files

This ADR documents changes to:
- `src/core/async_orchestrator.py`
- `src/core/planner.py`
- `src/core/run_finalizer.py`
- `src/core/result_writer.py`
- `src/core/execution_engine.py`
- `src/db/repositories/response_repository.py`
- `src/db/repositories/error_repository.py`
- `src/db/schema/` (migration removing `running` status)
