---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# Idempotency Contract

**Scope:** Execution and data writes  
**Invariant:** The system never generates duplicate data for the same combination of experiment, run, model, and question

---

## Contract Statement

All execution and data write operations must be **idempotent**: repeating the same operation produces the same result without side effects or duplication.

---

## Idempotency Guarantees

### 1. Execution Idempotency

Re-executing an experiment **never** creates duplicate results:

- The system tracks which combinations have been executed
- Already-completed items are **skipped** on re-execution
- Partial executions resume from where they left off
- No manual intervention required to avoid duplicates

**Implementation:** `ResultWriter` uses `UNIQUE constraint + INSERT OR IGNORE` pattern

### 2. ResultWriter Idempotency

Each result is written with a **unique composite key** ensuring:

```sql
-- Conceptual constraint (actual schema in src/db/schema.py)
UNIQUE(run_id, variant_id, snapshot_id)
```

If the same result is written twice:
- First write: **succeeds**
- Second write: **ignored** (no error, no duplicate)

**Implementation:** `src/core/result_writer.py` — `write_result()` method

### 3. Question Snapshot Idempotency

Adding questions to an experiment is idempotent:
- Adding the same question twice produces one snapshot
- The system detects existing snapshots and skips them
- No duplicate question entries per experiment

### 4. Model Variant Idempotency

Adding a model variant to an experiment:
- Same model with same config → recognized as existing variant
- Data generated with a variant persists even if variant is removed
- Removing a variant only prevents future runs; never deletes historical data

---

## Partial Reexecution

The system supports intelligent partial execution:

```bash
# Execute only questions 1-10 (by 1-based position) for specific models
bcllm --experiment <name> --execute --questions "1-10" --models <variant_id>
```

On subsequent executions:
- System identifies what's already completed within the selected scope
- Skips completed items
- Only processes missing items
- Never produces duplicate data

---

## Idempotency Boundaries

### What IS Idempotent

- ✅ Re-running the same experiment
- ✅ Adding questions that already exist (skipped)
- ✅ Adding model variants that already exist (recognized)
- ✅ Writing results that already exist (ignored)
- ✅ Creating runs with same configuration (new run ID, independent data)

### What IS NOT Idempotent

- ❌ Creating a new run (creates new execution instance)
- ❌ Adding a **different** model variant (new configuration)
- ❌ Modifying experiment configuration after creation (not allowed)

---

## Implementation Pattern

```python
# CORRECT: Idempotent write pattern
def write_result(self, result: ExecutionResult) -> None:
    """Write result with idempotency guarantee.
    
    Uses UNIQUE constraint + INSERT OR IGNORE to ensure
    the same result can be written multiple times safely.
    """
    cursor.execute("""
        INSERT OR IGNORE INTO responses (
            response_id, run_id, variant_id, snapshot_id, ...
        ) VALUES (?, ?, ?, ?, ...)
    """, (...))
```

---

## Violation Examples

### ❌ WRONG: Non-idempotent write

```python
# VIOLATION: No uniqueness check; creates duplicates
cursor.execute("INSERT INTO responses VALUES (...)", data)
```

### ✅ CORRECT: Idempotent write

```python
# CORRECT: UNIQUE constraint + INSERT OR IGNORE
cursor.execute("""
    INSERT OR IGNORE INTO responses (...) VALUES (...)
""", data)
```

### ❌ WRONG: Assuming re-execution needs cleanup

```python
# VIOLATION: Deleting before re-execution loses historical data
cursor.execute("DELETE FROM responses WHERE run_id = ?", run_id)
```

### ✅ CORRECT: Skip existing items

```python
# CORRECT: Check before writing; skip if exists
if not self._result_exists(run_id, variant_id, snapshot_id):
    self._write_result(result)
```

---

## Logging Never Affects Idempotency

Idempotency state (what has/hasn't been executed) lives **only** in the
`responses`/`errors` tables via the `UNIQUE(run_id, variant_id,
snapshot_id)` + `INSERT OR IGNORE` pattern above — never in logs. A
logging failure (handler I/O error, redaction exception, disk full,
process killed mid-write) must never be interpreted by resume/retry
logic as "this item was not yet attempted": `emit_event()`
(`src/utils/log_emitter.py`) catches and swallows its own failures so
they can never block or delay the DB write that actually determines
idempotency, and a missing/incomplete log line carries no meaning for
whether an item needs re-execution. Verified in
`tests/unit/utils/test_logging_concurrency_crash_safety.py::TestHandlerFailureNeverBreaksExecution::test_write_failure_does_not_cause_duplicate_result_semantics`.
See `docs/contracts/interaction-contracts.md` §4 and
`docs/contracts/data-auditability.md` §4c for the broader logs-vs-DB
separation this follows from.

---

## Related Contracts

- [determinism.md](determinism.md) — Same config produces same requests
- [immutability.md](immutability.md) — Historical data never deleted
- [data-auditability.md](data-auditability.md) — All data traceable

---

**This contract is non-negotiable.** Duplicate data breaks the scientific integrity of benchmark results.
