# Implementation Plan: Execution Pipeline Refactor

**Document Type:** Implementation Plan  
**Project:** Benchmark LLM V2  
**Version:** 1.0  
**Date:** 2026-04-07  
**Status:** Pending Approval  
**Design Reference:** (approved design summary in session)

---

## Overview

Refactor the execution architecture into a single, contract-driven pipeline with:
1. Idempotent Planner (excludes executed items from plan)
2. Configurable concurrency via `BCLLM_MAX_CONCURRENCY` env var
3. RunFinalizer as single owner of `runs.status` and `runs.duration`
4. Dead code removal with evidence-based deletion
5. Integration tests validating contract invariants

---

## Milestones

### Milestone 1: Investigation Report + Essence Guardian Validation
**Agent:** `debugger` (investigation complete) → `essence-guardian` (validation)

**Deliverables:**
- Investigation report with file/function references, SQL inventory, state machine analysis
- essence-guardian validation of invariants I1–I8 against current codebase

**Status:** ✅ Investigation complete, awaiting first essence-guardian call after plan approval

---

### Milestone 2: Create RunFinalizer + Planner Idempotency
**Agent:** `agent-coder`

**Files to Create:**
- `src/core/run_finalizer.py` — RunFinalizer class with `finalize_run(run_id, conn)` method
  - Queries DB for responses belonging to run_id
  - Computes `duration_ms = SUM(latency_ms)` for successful responses
  - Computes status from counts: all completed → `completed`, all failed → `failed`, mixed → `partial_failed`
  - Single `UPDATE runs SET status = ?, duration = ? WHERE run_id = ?`
  - No other code may update runs.*

**Files to Modify:**
- `src/core/planner.py` — Add `_get_executed_items(run_id, conn)` method
  - Queries `responses` table for existing (variant_id, snapshot_id) pairs for the run
  - Excludes these pairs when building PlanItems
  - Returns ExecutionPlan containing only items needing execution

**Validation:** Run existing unit tests for Planner (adjusted), new unit tests for RunFinalizer

**Checkpoint:** Call essence-guardian to verify I3, I4, I5, I6

---

### Milestone 3: Refactor AsyncOrchestrator + Wire Concurrency
**Agent:** `agent-coder`

**Files to Modify:**
- `src/core/async_orchestrator.py`:
  - Add `asyncio.Semaphore` initialized from `BCLLM_MAX_CONCURRENCY` env var (default 1)
  - Wrap item execution in `async with semaphore:` for concurrency control
  - Remove `_update_run_statuses()` method entirely
  - After engine completes, call `RunFinalizer.finalize_run(run_id, conn)` for each run
  - No direct `runs.*` updates anywhere in this file

- `src/cli/bcllm_execute.py`:
  - Read `BCLLM_MAX_CONCURRENCY` from env (or `.env` via existing config resolution)
  - Pass concurrency value to AsyncOrchestrator constructor
  - No new CLI flags added

**Validation:** Smoke test — execute a small run manually

**Checkpoint:** Call essence-guardian to verify I1, I2, I5

---

### Milestone 4: Remove Dead Code
**Agent:** `agent-coder`

**Evidence Required Before Each Deletion:**
- ripgrep search confirming zero references outside tests/docs
- Confirm no CLI path invokes it
- Confirm no dynamic import / reflection

**Files to Modify/Delete:**

1. `src/core/result_writer.py`:
   - Remove `write_results()` method (dead batch path)
   - Remove `_update_run_status_and_duration()` method (duplicate of RunFinalizer)

2. `src/core/execution_engine.py`:
   - Remove `_call_api_sync()` method and `ThreadPoolExecutor` import
   - Remove any sync-only helper methods only called by `_call_api_sync()`

3. `src/db/repository.py`:
   - For `ResponseRepository.save()`, `ErrorRepository.save()`: Change `INSERT OR REPLACE` → `INSERT OR IGNORE`, add columns to match production schema if used by any code path
   - If repositories are confirmed fully unused: remove them entirely
   - If partially used: fix semantics to match production (`INSERT OR IGNORE`, 30 columns for responses)

4. `src/db/schema.py`:
   - If `running` status is removed: update CHECK constraint, migrate any existing `running` rows to `pending` or `failed`
   - If kept: document when it's set (but investigation shows it never is)

**Validation:** Full test suite passes (after removing/adjusting obsolete tests)

**Checkpoint:** Call essence-guardian to verify no contract violations from removals

---

### Milestone 5: Integration Tests
**Agent:** `tester`

**New Test Files to Create:**
- `tests/integration/test_execution_contract.py`:
  - Test: Execute run → re-execute same run → assert no new API calls (mock client call count)
  - Test: Execute run → re-execute → assert `runs.duration` unchanged
  - Test: Execute run → re-execute → assert `runs.status` unchanged
  - Test: Idempotent plan — Planner excludes executed items

- `tests/integration/test_execution_concurrency.py`:
  - Test: `concurrency=1` — sequential execution, all items completed
  - Test: `concurrency=4` — parallel execution, all items completed, correctness preserved
  - Test: `concurrency=4` — re-execute, same skip behavior, duration unchanged

- `tests/unit/core/test_run_finalizer.py`:
  - Test: Computes duration correctly from SUM(latency_ms)
  - Test: Computes status correctly (all completed, all failed, mixed)
  - Test: Handles empty run (no responses)

**Validation:** `pytest tests/integration/test_execution_contract.py tests/integration/test_execution_concurrency.py tests/unit/core/test_run_finalizer.py -v` passes

**Checkpoint:** Call essence-guardian to verify I8

---

### Milestone 6: Documentation
**Agent:** `technical_writer`

**Files to Create:**
- `docs/architecture/adr-execution-pipeline.md`:
  - Single pipeline decision
  - Idempotent Planner rationale
  - RunFinalizer as single owner
  - Concurrency config via env var
  - Dead code removal rationale

**Validation:** Document reviewed for accuracy against implemented code

---

### Milestone 7: Final Essence Guardian + Code Review
**Agent:** `essence-guardian` → `code_reviewer`

- essence-guardian: Full invariant check (I1–I8) against final implementation
- code_reviewer: Review all changed files for correctness, safety, edge cases
- Block completion on unresolved Critical/Major findings

---

## Dependencies

```
Milestone 1 (investigation) ✅ → done
Milestone 2 (RunFinalizer + Planner idempotency)
  └─→ Milestone 3 (AsyncOrchestrator refactor)
        └─→ Milestone 4 (Dead code removal)
              └─→ Milestone 5 (Integration tests)
                    └─→ Milestone 6 (Documentation)
                          └─→ Milestone 7 (Final validation)
```

Milestones 2–4 are sequential (each depends on previous). Milestone 5 depends on 2–4 being complete. Milestone 6 is parallel-safe with 5. Milestone 7 depends on all prior.

---

## Validation Commands

After each milestone:
```bash
python -m pytest tests/ -v --tb=short
```

Specific test runs:
```bash
# Contract tests
python -m pytest tests/integration/test_execution_contract.py -v

# Concurrency tests
python -m pytest tests/integration/test_execution_concurrency.py -v

# RunFinalizer unit tests
python -m pytest tests/unit/core/test_run_finalizer.py -v
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Breaking existing executions | Planner filtering ensures no duplicate API calls; existing data untouched |
| Concurrency race conditions | Semaphore-based limiting; AsyncWriter serializes DB writes; INSERT OR IGNORE for safety |
| Duration computation errors | RunFinalizer queries DB directly; test validates SUM against known values |
| Test flakiness with concurrency | Tests use in-memory SQLite; deterministic seed; mock API client |
| Dead code removal breaks something | Evidence-based deletion only; full test suite must pass after each removal |

---

## Files Summary

| Action | File | Purpose |
|--------|------|---------|
| Create | `src/core/run_finalizer.py` | Single owner of runs updates |
| Create | `tests/integration/test_execution_contract.py` | Contract validation tests |
| Create | `tests/integration/test_execution_concurrency.py` | Concurrency correctness tests |
| Create | `tests/unit/core/test_run_finalizer.py` | RunFinalizer unit tests |
| Create | `docs/architecture/adr-execution-pipeline.md` | Architecture decision record |
| Modify | `src/core/planner.py` | Add idempotency filtering |
| Modify | `src/core/async_orchestrator.py` | Add semaphore, remove run updates, wire RunFinalizer |
| Modify | `src/core/result_writer.py` | Remove dead paths |
| Modify | `src/core/execution_engine.py` | Remove dead sync code |
| Modify | `src/db/repository.py` | Fix or remove conflicting semantics |
| Modify | `src/db/schema.py` | Update status constraint if needed |
| Modify | `src/cli/bcllm_execute.py` | Wire concurrency config |
| Modify | `src/core/async_writer.py` | Minor handoff adjustments |
| Delete | Various test files | Remove obsolete tests no longer reflecting architecture |

---

**Approve this implementation plan before execution begins?**

1. Approve plan
2. Revise plan
3. Abort execution

Use the picker to approve, revise, or abort.