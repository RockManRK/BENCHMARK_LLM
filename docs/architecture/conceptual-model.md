---
type: conceptual
audience: both
last-validated: 2026-04-11
status: active
---

# Conceptual Model

**Purpose:** Core entities, relationships, and lifecycle  
**Scope:** How experiments, runs, model variants, and question snapshots relate

---

## Entity Relationship Diagram

```
┌──────────────────┐
│   Experiment     │
│──────────────────│
│ experiment_id    │◄────── FK from: ModelVariant, QuestionSnapshot, Run
│ name (unique)    │
│ description      │
│ config_json      │  ← Frozen configuration snapshot
│ config_hash      │  ← SHA-256 integrity check
│ created_at       │
└────────┬─────────┘
         │
    ┌────┴────┬────────────┬────────────────┐
    │         │            │                │
    ▼         ▼            ▼                ▼
┌────────┐ ┌──────────┐ ┌──────────────┐ ┌────────┐
│ Model  │ │ Question │ │     Run      │ │ (more) │
│Variant │ │ Snapshot │ │──────────────│ │        │
│────────│ │──────────│ │ run_id       │ │        │
│variant │ │snapshot  │ │ experiment_id│ │        │
│_id     │ │_id       │ │ config       │ │        │
│experiment│ │experiment│ │ status       │ │        │
│_id     │ │_id       │ │ duration     │ │        │
│model_id│ │json_     │ │ created_at   │ │        │
│variant_│ │question_ │ └──────┬───────┘ │        │
│signature│ │id       │        │         │        │
│config  │ │question_ │        │         │        │
│created_│ │position  │        ▼         │        │
│_at     │ │question_ │ ┌──────────────┐ │        │
│        │ │payload   │ │  Response    │ │        │
│        │ │created_at│ │──────────────│ │        │
└────────┘ └──────────┘ │response_id   │ │        │
                         │run_id        │◄┘        │
                         │variant_id    │          │
                         │snapshot_id   │          │
                         │model_id      │          │
                         │question_id   │          │
                         │status        │          │
                         │response_text │          │
                         │selected_     │          │
                         │  answer      │          │
                         │is_correct    │          │
                         │parse_        │          │
                         │  confidence  │          │
                         │review_status │          │
                         │manual_answer │          │
                         │raw_response  │          │
                         │cost, tokens  │          │
                         │latency_ms    │          │
                         │started_at    │          │
                         │finished_at   │          │
                         └──────────────┘
                              │
                         Also: Error table
                         (same FK structure)
```

---

## Entity Definitions

### 1. Experiment

**Purpose:** Represents a research intent with frozen configuration.

An experiment is the **top-level container** for a benchmarking study. It defines:
- Which models to evaluate
- Which questions to ask
- Default prompts and configuration
- The universe of possible executions

**Lifecycle:**
1. **Created** — With name and optional configuration
2. **Grows** — Models, questions added over time
3. **Executed** — Runs created and executed
4. **Never deleted** — Soft delete only; historical data preserved

**Immutability:**
- Name: Immutable after creation
- Configuration: Frozen (config_json stores complete state)
- Questions: Can be added, never removed
- Models: Can be added or removed (removal only prevents future use; historical data preserved)

### 2. Model Variant

**Purpose:** Represents an **intentional configuration** of a base model.

A model variant is **not** just a model name — it's a specific configuration:
- Base model identifier (e.g., `openai/gpt-4`)
- Reasoning effort level
- Temperature, top_p, top_k, etc.
- Vision/structured output flags
- Max tokens settings

**Why variants?** The same base model with different configurations (temperature, reasoning effort) is effectively a different system under test. Variants make these differences explicit and auditable.

**Lifecycle:**
1. **Created** — When added to experiment with configuration
2. **Used** — In runs and executions
3. **Removed** — Only prevents future use; historical data preserved

**Immutability:** Configuration frozen after creation. To change config, create new variant.

### 3. Question Snapshot

**Purpose:** A **frozen copy** of a question from the source dataset.

When questions are added to an experiment, they are **snapshotted** — their complete payload (stem, options, answer key, metadata) is copied and stored. This ensures:
- Changes to the source dataset don't affect existing experiments
- Experiments are reproducible even if source data changes
- The exact question presented to the LLM is preserved

**Lifecycle:**
1. **Created** — When questions are added to experiment (from dataset)
2. **Used** — In executions
3. **Never modified** — Immutable after creation

**Immutability:** Fully immutable. To change a question, snapshot a new version.

### 4. Run

**Purpose:** A concrete **execution instance** of an experiment.

A run represents one execution of an experiment's configuration against its models and questions. Runs allow:
- Running the same experiment multiple times (different seeds, prompts)
- Tracking execution status (pending, running, completed, failed)
- Accumulating duration across partial executions

**Lifecycle:**
1. **Created** — With seed and optional prompt overrides
2. **Running** — During execution
3. **Completed/Failed** — Terminal state
4. **Never modified** — Configuration frozen; only status/duration change

**Configuration:** Run config can override experiment-level settings for:
- `seed` (RUN_RESPONSES_SEED)
- `system_prompt`
- `user_prompt`

### 5. Response

**Purpose:** The result of executing one model variant against one question snapshot.

A response captures:
- **What was asked** — Traced to snapshot
- **What answered** — Full response text
- **How parsed** — Selected answer, confidence
- **How performed** — Correctness, tokens, latency, cost
- **Review status** — Whether human reviewed it

**Lifecycle:**
1. **Created** — By ResultWriter after execution
2. **Optionally reviewed** — Manual answer may be added
3. **Never modified** — Original data immutable; review adds fields only

### 6. ExecutionPlan

**Purpose:** An **immutable, self-contained description** of work to execute.

The ExecutionPlan is generated by the Planner and consumed by the ExecutionEngine. It is:
- **Immutable** — Cannot be modified after creation
- **Self-contained** — All configuration resolved at plan creation
- **Transient** — Not persisted to database (reference/audit only)

**Why a plan?** Separating planning from execution ensures:
- Planning is read-only (no state inference)
- Execution is deterministic (plan is fixed)
- Plans can be audited (what was planned vs what executed)

---

## Relationships Summary

| Relationship | Cardinality | Description |
|--------------|-------------|-------------|
| Experiment → ModelVariant | 1:N | Experiment has many variants |
| Experiment → QuestionSnapshot | 1:N | Experiment has many snapshots |
| Experiment → Run | 1:N | Experiment has many runs |
| Run → Response | 1:N | Run has many responses |
| ModelVariant → Response | 1:N | Variant has many responses |
| QuestionSnapshot → Response | 1:N | Snapshot has many responses |
| Response → Error | 1:0..1 | Response may have error |

---

## Configuration Inheritance

```
System Defaults (lowest priority)
    ↑
.env (user defaults)
    ↑
Experiment (frozen at creation, can grow)
    ↑
Run / Model Variant (highest priority for execution)
```

See [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md) for full details.

---

## Execution Flow

```
CLI Command
    ↓
Planner (reads DB, builds ExecutionPlan)
    ↓
ExecutionPlan (immutable description of work)
    ↓
ExecutionEngine (pure execution; no DB access)
    ↓
ResultWriter (writes to DB; idempotent)
    ↓
Database (responses, errors, run status)
```

See [execution-architecture.md](execution-architecture.md) for detailed flow.

---

## Related Documents

- [overview.md](overview.md) — System at a glance
- [execution-architecture.md](execution-architecture.md) — Component data flow
- [contracts/immutability.md](../contracts/immutability.md) — What cannot change
- [contracts/data-auditability.md](../contracts/data-auditability.md) — Traceability
