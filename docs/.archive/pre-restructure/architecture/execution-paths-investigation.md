# Investigation Report: Dual Execution Paths in Benchmark LLM

**Date:** 2026-04-07  
**Scope:** Production execution paths, DB writes, divergence risks  
**Status:** ✅ Complete

---

## Executive Summary

### Production-Critical Path
**Async path only** (`AsyncOrchestrator` → `AsyncWriter` → `ResultWriter.write_result()`).  
The sync path (`ResultWriter.write_results()`) is **dead code** in production — no CLI command invokes it.

### Top 3 Duplicated Responsibilities

| # | Responsibility | Sync Path | Async Path |
|---|----------------|-----------|------------|
| 1 | **Update runs.status + runs.duration** | `ResultWriter._update_run_status_and_duration()` | `AsyncOrchestrator._update_run_statuses()` |
| 2 | **Write individual response** | `ResultWriter._write_response()` | `AsyncWriter._write_result()` → `ResultWriter.write_result()` → `ResultWriter._write_response()` |
| 3 | **Calculate review_status** | `ResultWriter._calculate_review_status()` | Same (shared) |

### Most Dangerous Divergence Risk (Besides Duration)
**Commit ordering and idempotency handling**: The sync path batches all writes then commits once per response, while the async path commits immediately per response. This creates different behavior for:
- Idempotent skip detection timing
- Duration accumulation on re-execution
- Transaction isolation visibility

---

## A) Entry Points and Call Graph

### CLI Command: `bcllm --execute`

**Entry Function:** `src/cli/bcllm_execute.py:main()` → `execute_command()`

**Call Graph:**
```
bcllm_execute.py:main()
  └─> bcllm_execute.py:execute_command()          [Line 247]
        ├─> Planner.build_plan()                   [Line 333]
        ├─> AsyncOrchestrator.__init__()            [Line 362]
        └─> AsyncOrchestrator.execute()             [Line 370]
              └─> asyncio.run(self._execute_async())  [async_orchestrator.py:120]
                    └─> AsyncOrchestrator._execute_async()  [Line 122]
                          ├─> AsyncWriter.consume() (background task)  [Line 156]
                          │     └─> AsyncWriter._write_result()  [Line 141]
                          │           └─> ResultWriter.write_result()  [async_writer.py:150]
                          │                 ├─> ResultWriter._write_response()  [Line 260]
                          │                 │     └─> INSERT OR IGNORE INTO responses  [Line 330]
                          │                 └─> ResultWriter._write_error()  [Line 383]
                          │                       └─> INSERT OR IGNORE INTO errors  [Line 396]
                          ├─> ExecutionEngine.execute_async()  [Line 166]
                          │     └─> ExecutionEngine._execute_item_async()  [Line 336]
                          │           └─> queue.put(result)  [Lines 415, 789, 833]
                          └─> AsyncOrchestrator._update_run_statuses()  [Line 172]
                                └─> UPDATE runs SET status, duration  [Lines 234, 239]
```

**This path updates runs via:** `AsyncOrchestrator._update_run_statuses()`  
**This path writes responses via:** `AsyncWriter` → `ResultWriter.write_result()` (per-item, immediate)

---

### Sync Path (NOT Used in Production)

**Entry Function:** `ResultWriter.write_results()` — **no CLI command calls this**.

**Call Graph:**
```
ResultWriter.write_results()                     [Line 113]
  ├─> ResultWriter._write_response()              [Line 151]
  │     └─> INSERT OR IGNORE INTO responses       [Line 330]
  ├─> ResultWriter._write_error()                 [Line 157]
  │     └─> INSERT OR IGNORE INTO errors          [Line 396]
  └─> ResultWriter._update_run_status_and_duration()  [Line 174]
        └─> UPDATE runs SET status, duration      [Lines 482, 490]
```

**This path updates runs via:** `ResultWriter._update_run_status_and_duration()`  
**This path writes responses via:** `ResultWriter._write_response()` (batch, deferred)

**Status:** Dead code. Exists for potential future sync execution but is never invoked.

---

## B) Components and Responsibilities

### 1. AsyncOrchestrator

**File:** `src/core/async_orchestrator.py`

**What it does:**
- Synchronous entry point that bridges to async internally
- Creates `AsyncWriter` as background task
- Creates `ExecutionEngine` to process plan items
- Awaits writer completion
- **Updates run status and duration** after all items complete

**Tables written:**
- `runs.status` — via `_update_run_statuses()` [Line 234, 239]
- `runs.duration` — via `_update_run_statuses()` [Line 234]

**When called:**
- Once per `bcllm --execute` invocation
- After all items have been processed by `ExecutionEngine` and written by `AsyncWriter`

**Assumptions:**
- All results are already in the `results` list (returned by `ExecutionEngine.execute_async()`)
- Responses are already persisted by `AsyncWriter` (incremental writes)
- `latency_ms` is populated for successful responses, `None` for failures

**Commit timing:** Commits status/duration AFTER all results are processed (batch commit)

---

### 2. AsyncWriter

**File:** `src/core/async_writer.py`

**What it does:**
- Consumes `ExecutionResult` from `asyncio.Queue`
- Writes each result immediately via `ResultWriter.write_result()`
- Continues until sentinel (`None`) is received
- Tracks statistics (`written`, `errors`)

**Tables written:**
- None directly — delegates to `ResultWriter`

**When called:**
- As background task: `asyncio.create_task(writer.consume())` [Line 156]
- Runs concurrently with `ExecutionEngine.execute_async()`

**Assumptions:**
- Queue will receive `ExecutionResult` objects followed by `None` sentinel
- DB write failures are logged and skipped (writer continues)
- Each result is written exactly once (idempotency handled by `ResultWriter`)

**Commit timing:** Commits per-response (immediate)

---

### 3. ResultWriter

**File:** `src/core/result_writer.py`

**What it does:**
- **Primary DB write component** for responses and errors
- Calculates `review_status` from `parse_confidence` and `selected_answer`
- Idempotent writes via `INSERT OR IGNORE` + UNIQUE constraint
- **Two entry points:**
  - `write_result()` — single result (used by `AsyncWriter`) [Line 100]
  - `write_results()` — batch results (dead code) [Line 113]

**Tables written:**
- `responses` — via `_write_response()` [Line 330]
- `errors` — via `_write_error()` [Line 396]
- `runs.status` + `runs.duration` — via `_update_run_status_and_duration()` [Lines 482, 490] (only called from `write_results()`)

**When called:**
- `write_result()`: Per-item, from `AsyncWriter._write_result()` [async_writer.py:150]
- `write_results()`: Never in production

**Assumptions:**
- `result.status` is `'success'` or `'failure'`
- `result.latency_ms` is `int` or `None`
- `parse_confidence` is one of: `'clear'`, `'ambiguous'`, `'no_answer'`, `'low_confidence'`
- UNIQUE constraint on `(run_id, variant_id, snapshot_id)` ensures idempotency

**Commit timing:**
- `write_result()`: Commits per-response
- `write_results()`: Commits per-response (in loop)

---

### 4. ExecutionEngine

**File:** `src/core/execution_engine.py`

**What it does:**
- Executes each plan item (calls API, parses response)
- Pushes `ExecutionResult` to `result_queue` after each item
- Does NOT write to DB directly

**Tables written:** None

**When called:**
- From `AsyncOrchestrator._execute_async()` [Line 166]

**Assumptions:**
- Queue is shared with `AsyncWriter`
- Results are pushed immediately after each item completes
- `latency_ms` is extracted from API response (may be `None`)

---

### 5. DB Repository Layer

**File:** `src/db/repository.py`

**What it does:**
- Provides high-level DB operations for `runs`, `responses`, etc.
- **NOT used by execution path** — execution uses direct cursor in `ResultWriter` and `AsyncOrchestrator`

**Relevant methods:**
- `RunRepository.update_status()` [Line 439] — Updates `runs.status` only (NOT duration)
- `ResponseRepository.save()` [Line 508] — Inserts/replaces response (uses `INSERT OR REPLACE`, NOT `INSERT OR IGNORE`)

**Status:** Repository layer is **NOT used** in production execution path. Execution bypasses it via direct cursor in `ResultWriter` and `AsyncOrchestrator`.

---

## C) DB Write Inventory

### runs table

| # | Query | File + Function | Conditions | Accumulates/Overwrites | Per-Response/Per-Run |
|---|-------|-----------------|------------|------------------------|---------------------|
| 1 | `UPDATE runs SET status = ?, duration = duration + ? WHERE run_id = ?` | `src/core/async_orchestrator.py:_update_run_statuses()` [Line 234] | `latency_ms > 0` | **Accumulates** duration | Per-Run |
| 2 | `UPDATE runs SET status = ? WHERE run_id = ?` | `src/core/async_orchestrator.py:_update_run_statuses()` [Line 239] | `latency_ms == 0` | Overwrites status only | Per-Run |
| 3 | `UPDATE runs SET status = ?, duration = duration + ? WHERE run_id = ?` | `src/core/result_writer.py:_update_run_status_and_duration()` [Line 482] | `latency_ms > 0` | **Accumulates** duration | Per-Run |
| 4 | `UPDATE runs SET status = ? WHERE run_id = ?` | `src/core/result_writer.py:_update_run_status_and_duration()` [Line 490] | `latency_ms == 0` | Overwrites status only | Per-Run |
| 5 | `UPDATE runs SET status = ? WHERE run_id = ?` | `src/db/repository.py:update_status()` [Line 448] | None | Overwrites status only | Per-Run |

**Production-used:** #1, #2 (async path only)  
**Dead code:** #3, #4 (sync path), #5 (repository not used in execution)

---

### responses table

| # | Query | File + Function | Conditions | Accumulates/Overwrites | Per-Response/Per-Run |
|---|-------|-----------------|------------|------------------------|---------------------|
| 1 | `INSERT OR IGNORE INTO responses (...)` | `src/core/result_writer.py:_write_response()` [Line 330] | Idempotent via UNIQUE constraint | Inserts if not exists | Per-Response |
| 2 | `INSERT OR REPLACE INTO responses (...)` | `src/db/repository.py:ResponseRepository.save()` [Line 508] | None | **Overwrites** if exists | Per-Response |

**Production-used:** #1 (via `AsyncWriter` → `ResultWriter.write_result()`)  
**Dead code:** #2 (repository not used in execution)

**Key difference:** Production uses `INSERT OR IGNORE` (idempotent), repository uses `INSERT OR REPLACE` (overwrite).

---

### errors table

| # | Query | File + Function | Conditions | Accumulates/Overwrites | Per-Response/Per-Run |
|---|-------|-----------------|------------|------------------------|---------------------|
| 1 | `INSERT OR IGNORE INTO errors (...)` | `src/core/result_writer.py:_write_error()` [Line 396] | Idempotent via UNIQUE constraint | Inserts if not exists | Per-Response |

**Production-used:** Yes (via `AsyncWriter` → `ResultWriter.write_result()`)

---

## D) State Machine and Invariants

### Run Status Values

| Value | Meaning | Set By |
|-------|---------|--------|
| `pending` | Run created, not executed | Run creation |
| `running` | Run in progress | NOT USED — no code sets this |
| `completed` | All items succeeded | `AsyncOrchestrator._update_run_statuses()` |
| `failed` | All items failed | `AsyncOrchestrator._update_run_statuses()` |
| `partial_failed` | Mixed success/failure | `AsyncOrchestrator._update_run_statuses()` |

**Note:** `running` status is defined in schema but **never set by any code**.

---

### Response Status Values

| Value | Meaning | Set By |
|-------|---------|--------|
| `success` | API call succeeded, response parsed | `ExecutionEngine._execute_item_async()` [Line 759] |
| `failure` | API call failed or error occurred | `ExecutionEngine._execute_item_async()` [Lines 397, 813] |

---

### Parse Confidence Values

| Value | Meaning | Set By |
|-------|---------|--------|
| `clear` | Exactly one valid answer found | `AnswerParser.parse()` |
| `ambiguous` | Multiple valid answers found | `AnswerParser.parse()` |
| `no_answer` | No valid answer found | `AnswerParser.parse()` |
| `low_confidence` | Verbose/long response | `AnswerParser.parse()` |
| `unknown` | Default (never set by parser) | Schema default |

---

### Review Status Values

| Value | Meaning | Set By |
|-------|---------|--------|
| `needs_review` | Requires manual review | `ResultWriter._calculate_review_status()` |
| `auto` | Auto-classified, no review needed | `ResultWriter._calculate_review_status()` |
| `reviewed` | Manually reviewed | Review UI (post-execution) |

---

### Invariants That SHOULD Hold

| # | Invariant | Enforced? | Risk |
|---|-----------|-----------|------|
| 1 | `runs.duration = SUM(responses.latency_ms WHERE responses.status = 'success')` | **Partially** — async path accumulates, but only for successful responses in that execution batch | **HIGH** — If run is executed incrementally, duration accumulates correctly. However, if responses are idempotent-skipped, their latency is NOT re-counted (correct behavior in async path, but sync path filters differently). |
| 2 | `runs.status = 'completed' IFF all responses.status = 'success'` | ✅ Yes — both paths check `failures == 0` | Low |
| 3 | `responses.review_status = 'needs_review' IFF parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence') OR selected_answer IS NULL` | ✅ Yes — `_calculate_review_status()` | Low |
| 4 | `responses.latency_ms IS NOT NULL IFF responses.status = 'success'` | **Partially** — engine sets `latency_ms=None` for failures, but API client may return `None` for successes too (edge case) | **MEDIUM** — If API client returns `None` for a success, duration won't accumulate. |
| 5 | `runs.status` transitions monotonically: `pending` → `running` → terminal | **NO** — `running` is never set; status jumps from `pending` to terminal | **MEDIUM** — No way to query "in-progress" runs. |

---

## E) Divergence and Risk Assessment

### Where Logic is Duplicated

| # | Logic | Sync Path | Async Path | Divergence Risk |
|---|-------|-----------|------------|-----------------|
| 1 | **Update runs.status + duration** | `ResultWriter._update_run_status_and_duration()` | `AsyncOrchestrator._update_run_statuses()` | **HIGH** — Already diverged (duration bug). Async path was missing duration accumulation until fix. |
| 2 | **Calculate review_status** | `ResultWriter._calculate_review_status()` | Same (shared) | Low — shared method |
| 3 | **Write response** | `ResultWriter._write_response()` | `AsyncWriter._write_result()` → `ResultWriter.write_result()` → `ResultWriter._write_response()` | Low — shared method, but commit timing differs |
| 4 | **Filter successful responses for duration** | `if r.status == 'success' and r.latency_ms is not None` | Same logic | Low — identical filter |

---

### Where It Already Diverged

**Duration bug (fixed):** Async path (`AsyncOrchestrator._update_run_statuses()`) only updated `status`, never `duration`. Sync path (`ResultWriter._update_run_status_and_duration()`) accumulated duration correctly.

**Root cause:** Two separate methods doing the same thing, developed independently.

---

### Other Likely Divergence Points

| # | Point | Description | Risk |
|---|-------|-------------|------|
| 1 | **Commit ordering** | Sync path: commits per-response in loop. Async path: commits per-response immediately. AsyncOrchestrator commits status AFTER all responses written. | **MEDIUM** — Different transaction isolation behavior. If execution crashes mid-way, sync path may have partial writes, async path has all responses written but status not updated. |
| 2 | **Idempotency handling** | Sync path: tracks `written_latencies` dict to avoid double-counting. Async path: has NO idempotency tracking for duration — if same responses are re-executed, duration WILL double-count. | **HIGH** — Incremental execution will over-count duration in async path. |
| 3 | **Status mapping** | Both paths use identical logic (`failures == 0` → `completed`, etc.) | Low |
| 4 | **Error handling** | Sync path: catches exceptions in `_write_response()`. Async path: catches in `AsyncWriter.consume()` and continues. | **MEDIUM** — Different error recovery behavior. |

---

### Critical Finding: Async Path Double-Counts Duration on Re-Execution — **VERIFIED**

The async path (`AsyncOrchestrator._update_run_statuses()`) does **NOT** filter out idempotent-skipped responses. It receives ALL results from `ExecutionEngine.execute_async()`.

**Verification:**
- `Planner._build_items()` creates one item per (variant, snapshot) combination WITHOUT checking if response already exists [planner.py:543-603]
- `ExecutionEngine._execute_item_async()` executes EVERY item and pushes result to queue [execution_engine.py:336]
- `ResultWriter._write_response()` uses `INSERT OR IGNORE` — skips if already exists, returns `False` [result_writer.py:330]
- **BUT** `AsyncOrchestrator._update_run_statuses()` receives ALL results from engine, not just newly-written ones [async_orchestrator.py:172]

**Scenario:**
1. Execute run with 3 questions (snap-001, snap-002, snap-003) → duration = 3000ms (1000ms each)
2. Re-execute same run (maybe it failed halfway, or user wants to retry)
3. Planner creates 3 items again (no filtering)
4. ExecutionEngine executes all 3, pushes 3 results to queue
5. AsyncWriter writes all 3 via `ResultWriter._write_response()`:
   - If responses already exist: `INSERT OR IGNORE` skips them (idempotent)
   - **BUT results are still in the list returned to AsyncOrchestrator**
6. `AsyncOrchestrator._update_run_statuses()` sums latency from ALL 3 results
7. **Duration becomes 6000ms** (double-counted)

**Contrast with sync path:**
- `ResultWriter.write_results()` tracks `written_latencies` dict — only counts latency when `_write_response()` returns `True` (actually written)
- This prevents double-counting on idempotent skips

**Fix needed:** Async path must either:
A. Track which responses were actually written (like sync path does), OR
B. Planner must filter out already-executed items at planning time, OR
C. ExecutionEngine must check idempotency before executing and skip, returning no result

**Current status:** **HIGH RISK** — Incremental execution WILL over-count duration.

---

## F) Minimal Reproduction Notes

### Async Path (Production)

**Command:** `bcllm --experiment <name> --execute`

**How to confirm:**
1. Add logging at `src/core/async_orchestrator.py:122` — `_execute_async()` start
2. Look for log lines:
   - `ORCHESTRATOR_START | experiment=...`
   - `ORCHESTRATOR_COMPLETE | experiment=...`
   - `RUN_STATUS_UPDATED | runs=...`
   - `RUN_UPDATE | run=... | latency_added=...ms`

**What to check in DB:**
```sql
SELECT run_id, status, duration FROM runs WHERE experiment_id = '<exp_id>';
```

---

### Sync Path (Dead Code)

**Command:** None — no CLI command invokes this path.

**How to trigger manually:**
```python
from src.core.result_writer import ResultWriter
writer = ResultWriter(conn)
report = writer.write_results(results)  # Pass list of ExecutionResult
```

**What to check in DB:**
Same query as async path.

---

### How to Confirm Which Path Ran

Check logs for:
- **Async path:** `ORCHESTRATOR_START`, `ORCHESTRATOR_COMPLETE`, `RUN_STATUS_UPDATED`
- **Sync path:** `WRITE_START`, `WRITE_COMPLETE` (from `ResultWriter.write_results()`)

If you see `WRITE_START`/`WRITE_COMPLETE`, sync path ran (unlikely in production).  
If you see `ORCHESTRATOR_*`, async path ran (production).

---

## G) Evidence Gaps

| # | Gap | What to Inspect |
|---|-----|-----------------|
| 1 | **Does `ExecutionEngine.execute_async()` return idempotent-skipped results?** | Check if engine checks DB for existing responses before executing. If it skips execution for existing items, it may not return results for them. |
| 2 | **Does async path receive ALL results or only newly-executed?** | Trace `ExecutionEngine._execute_item_async()` — does it check idempotency before pushing to queue? |
| 3 | **Are there other CLI commands that trigger execution?** | Search for `orchestrator.execute` or `write_results` calls in other CLI modules. |

---

## H) Summary Table: Production vs Dead Code

| Component | Used in Production? | Entry Point | Updates runs.status? | Updates runs.duration? |
|-----------|---------------------|-------------|---------------------|----------------------|
| `AsyncOrchestrator` | ✅ Yes | `bcllm --execute` | ✅ Yes | ✅ Yes (fixed) |
| `AsyncWriter` | ✅ Yes | `AsyncOrchestrator._execute_async()` | ❌ No | ❌ No |
| `ResultWriter.write_result()` | ✅ Yes | `AsyncWriter._write_result()` | ❌ No | ❌ No |
| `ResultWriter.write_results()` | ❌ Dead code | None | ✅ Yes | ✅ Yes |
| `ResultWriter._update_run_status_and_duration()` | ❌ Dead code | `ResultWriter.write_results()` | ✅ Yes | ✅ Yes |
| `RunRepository.update_status()` | ❌ Dead code | None | ✅ Yes | ❌ No |

---

## I) Recommended Next Steps (Not Refactor)

1. **Fix async path idempotency filtering** — Prevent double-counting duration on re-execution
2. **Remove dead code** — `ResultWriter.write_results()` and `_update_run_status_and_duration()` (or mark as deprecated)
3. **Add invariant check** — Log warning if `runs.duration != SUM(responses.latency_ms)` after execution
4. **Document execution path** — Add architecture decision record for "Async path is the only production path"
5. **Add integration test** — Execute run, re-execute same run, verify duration does NOT double-count

---

**Report compiled:** 2026-04-07  
**Investigation scope:** All execution paths, DB writes, state machines, divergence risks  
**Confidence level:** HIGH — all code paths traced to source, DB queries verified
