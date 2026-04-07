# Runs Duration Accumulation - Fix Summary

**Date:** 2026-04-07  
**Status:** ✅ Complete  
**Tests:** 9/9 passing

---

## Problem

The `runs.duration` column was **never implemented**. The `_update_run_status()` method only updated the `status` field but never populated or accumulated the `duration` field.

### Root Cause

```python
# BEFORE (src/core/result_writer.py:443)
def _update_run_status(self, run_id: str, status: str) -> None:
    cursor.execute("""
        UPDATE runs SET status = ? WHERE run_id = ?
    """, (status, run_id))
    # ❌ Duration was never updated
```

---

## Solution

Replaced `_update_run_status()` with `_update_run_status_and_duration()` that:

1. **Accumulates duration** from successful responses using `duration = duration + ?`
2. **Only counts successful responses** - failed/timed-out requests do NOT contribute
3. **Supports incremental execution** - duration accumulates across multiple executions
4. **Logs duration updates** for auditability

### Implementation

```python
# AFTER (src/core/result_writer.py:447)
def _update_run_status_and_duration(
    self,
    run_id: str,
    status: str,
    latency_ms: int = 0,
) -> None:
    if latency_ms > 0:
        # Accumulate: ADD latency to existing duration
        cursor.execute("""
            UPDATE runs
            SET status = ?,
                duration = duration + ?
            WHERE run_id = ?
        """, (status, latency_ms, run_id))
    else:
        # Update status only
        cursor.execute("""
            UPDATE runs SET status = ? WHERE run_id = ?
        """, (status, run_id))
```

### Integration in write_results()

```python
# src/core/result_writer.py:163-168
for run_id, run_results in results_by_run.items():
    status = self._determine_run_status(run_results)
    # Calculate total latency for successful responses only
    latency_ms = sum(
        r.latency_ms for r in run_results
        if r.status == 'success' and r.latency_ms is not None
    )
    self._update_run_status_and_duration(run_id, status, latency_ms)
```

---

## Behavior

### ✅ What Works Now

| Scenario | Duration Behavior |
|----------|------------------|
| Single successful response (1500ms) | `duration = 1500` |
| Multiple successful responses (1000ms + 2000ms) | `duration = 3000` |
| Mixed successes and failures | Only successful responses contribute |
| All failures | `duration = 0` |
| Incremental execution (1st: 1000ms, 2nd: 2500ms) | `duration = 3500` |
| Null latency | Filtered out (doesn't contribute) |
| Zero latency | Added (edge case, results in +0) |

### ❌ What Does NOT Contribute to Duration

- Failed responses (status = 'failure')
- Timed-out requests
- Responses with `latency_ms = None`
- Idempotent skips (already-existing responses)

---

## Test Coverage

Created comprehensive tests in `tests/unit/core/test_result_writer_duration.py`:

### TestDurationAccumulation (4 tests)
- ✅ Single success response adds latency
- ✅ Multiple success responses accumulate latency
- ✅ Failed responses do NOT contribute
- ✅ All failures = duration remains 0

### TestIncrementalExecution (2 tests)
- ✅ Duration accumulates across multiple executions
- ✅ Mixed successes/failures accumulate correctly

### TestEdgeCases (3 tests)
- ✅ Null latency doesn't cause errors
- ✅ Zero latency is handled
- ✅ Large latency values work correctly

**All 9 tests passing** ✅

---

## Database Schema

No schema changes required. The `runs.duration` column already exists:

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
    config TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    duration INTEGER DEFAULT 0,  -- ✅ Already exists
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
);
```

---

## Migration Notes

### No Migration Needed

- ✅ No schema changes
- ✅ No data migration required
- ✅ Existing runs with `duration = 0` remain unchanged
- ✅ New executions will start accumulating duration correctly

### Backward Compatibility

- ✅ Existing code continues to work
- ✅ No breaking changes to API
- ✅ No changes to ExecutionResult structure
- ✅ No changes to planner or execution engine

---

## Logging

Duration updates are now logged:

```
RUN_UPDATE | run=run-001 | status=completed | latency_added=3500ms
```

This allows auditing and debugging of duration accumulation.

---

## Verification

### Manual Testing

To verify the fix works with real executions:

1. Run an experiment with multiple models and questions
2. Check the database after execution:

```sql
SELECT run_id, status, duration 
FROM runs 
WHERE experiment_id = 'your-exp-id';
```

3. Verify that `duration` matches the sum of `latency_ms` from successful responses:

```sql
SELECT SUM(latency_ms) as total_latency
FROM responses
WHERE run_id = 'your-run-id'
  AND status = 'success';
```

Both values should match.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/core/result_writer.py` | Replaced `_update_run_status()` with `_update_run_status_and_duration()` |
| `tests/unit/core/test_result_writer_duration.py` | Created comprehensive test suite (9 tests) |

---

## Summary

The `runs.duration` field is now **fully functional** and:

- ✅ Accumulates `latency_ms` from successful responses only
- ✅ Supports incremental execution (accumulates across multiple runs)
- ✅ Ignores failed/timed-out requests
- ✅ Handles edge cases (null, zero, large values)
- ✅ Fully tested (9/9 tests passing)
- ✅ No breaking changes or migrations required
- ✅ Logged for auditability

The fix ensures that `runs.duration` accurately represents the **cumulative execution time of successful requests**, exactly as specified in the requirements.
