---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# Immutability Contract

**Scope:** Snapshots, execution plans, historical data  
**Invariant:** Once created, certain data entities are logically immutable and cannot be modified

---

## Contract Statement

Specific system entities are **immutable after creation**: their data cannot be modified, only appended to or superseded by new entities. This ensures auditability and reproducibility.

---

## Immutable Entities

### 1. Question Snapshots

Once a question is snapshotted into an experiment:

- **Cannot be modified** — The snapshot represents what was executed at that point in time
- **Cannot be deleted** — Even if the source dataset changes, snapshots remain
- **Can only be added** — New snapshots can be added to an experiment, never removed

**Rationale:** If the original dataset is updated, existing experiment data must remain reproducible. Snapshots guarantee that running the same experiment tomorrow produces the same results.

**Implementation:** `QuestionSnapshot` entity in `src/db/models.py`

### 2. Execution Plans

Once an `ExecutionPlan` is created by the Planner:

- **Cannot be modified** — The plan is a frozen description of work to execute
- **Is self-contained** — All configuration is resolved at plan creation time
- **Is consumed, not altered** — ExecutionEngine reads the plan; it does not change it

**Implementation:** `ExecutionPlan` dataclass uses `frozen=True` in `src/core/execution_plan.py`

### 3. Historical Execution Data

Once a response or error is written to the database:

- **Cannot be modified** — The result represents what actually happened
- **Can be annotated** — Manual review adds fields (`manual_answer`, `reviewed_at`) but does not alter original data
- **Can be superseded** — New executions create new records; they do not overwrite old ones

**Implementation:** `Response` and `Error` entities; `INSERT OR IGNORE` pattern

### 4. Run Configuration

Once a run is created:

- **Cannot be modified** — Run configuration (seed, prompts) is frozen
- **Status can change** — `pending` → `running` → `completed`/`failed`/`partial_failed`
- **Duration can accumulate** — Partial runs accumulate duration across executions

**Implementation:** `Run` entity in `src/db/models.py`

### 5. Experiment Configuration (Mostly Immutable)

Experiment configuration is **mostly immutable** with specific exceptions:

**Cannot be modified:**
- Experiment name
- Original configuration (frozen at creation)

**Can be extended (not modified):**
- **Questions:** More questions can be added via `--add-questions`; questions cannot be removed
- **Models:** Models can be added or removed; model removal only prevents future runs, does not delete historical data
- **Prompts:** System/user prompts can be changed; this does **not** affect existing runs (they keep original prompts)

**Rationale:** Experiments can grow but their original state is preserved for reproducibility.

---

## Mutable Data (Exceptions)

The following fields are **designed to be mutable**:

| Entity | Mutable Fields | Reason |
|--------|---------------|--------|
| `Response` | `review_status`, `manual_answer`, `reviewed_at` | Manual review workflow |
| `Run` | `status`, `duration` | Execution lifecycle tracking |
| `Experiment` | (growth via additions only) | Can add questions/models, not modify existing |

---

## Violation Examples

### ❌ WRONG: Modifying a snapshot

```python
# VIOLATION: Never alter a snapshot
cursor.execute("""
    UPDATE question_snapshots 
    SET question_payload = ? 
    WHERE snapshot_id = ?
""", (new_payload, snapshot_id))
```

### ✅ CORRECT: Add new snapshot

```python
# CORRECT: Add new snapshot; leave existing ones unchanged
new_snapshot = QuestionSnapshot(
    snapshot_id=generate_uuid(),
    experiment_id=experiment_id,
    question_payload=new_payload,
)
self._write_snapshot(new_snapshot)
```

### ❌ WRONG: Modifying execution plan

```python
# VIOLATION: ExecutionPlan is frozen; cannot be modified
plan.runs[0].seed_effective = 123  # FrozenInstanceError raised
```

### ✅ CORRECT: Create new plan

```python
# CORRECT: Create new plan with different configuration
new_plan = planner.create_plan(experiment_id, seed=123)
```

### ❌ WRONG: Overwriting response data

```python
# VIOLATION: Never alter original response
cursor.execute("""
    UPDATE responses 
    SET selected_answer = ?, parse_confidence = ?
    WHERE response_id = ?
""", (new_answer, new_confidence, response_id))
```

### ✅ CORRECT: Annotate via review fields

```python
# CORRECT: Add manual answer without altering original data
cursor.execute("""
    UPDATE responses 
    SET manual_answer = ?, review_status = 'manual', reviewed_at = ?
    WHERE response_id = ?
""", (manual_answer, datetime.now(), response_id))
```

---

## Immutability vs Append-Only

The system follows an **append-only for results** philosophy:

- **Identity data** (experiments, runs, snapshots, variants): Immutable after creation
- **Result data** (responses, errors): Append-only; never UPDATE existing records
- **Annotation data** (reviews): Can UPDATE designated review fields only

---

## Related Contracts

- [determinism.md](determinism.md) — Snapshots enable reproducibility
- [idempotency.md](idempotency.md) — No duplicate data generation
- [data-auditability.md](data-auditability.md) — Immutability ensures auditability

---

**This contract is non-negotiable.** Mutable historical data breaks the system's scientific integrity and auditability guarantees.
