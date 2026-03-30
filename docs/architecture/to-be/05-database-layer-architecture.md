# Database Layer — Architecture & Contracts

**Document Type:** Architecture Specification
**Domain:** Database Layer
**Status:** TO-BE (Target Architecture)
**Purpose:** Define database philosophy, table contracts, and immutability rules

---

## 1. Database Philosophy

### 1.1 Core Principles

The Benchmark LLM database is built on these foundational principles:

1. **Append-Only for Results**
   - `responses` and `errors` tables are append-only
   - Historical data is never modified or deleted
   - Enables audit trails and reproducibility

2. **Immutable Identity**
   - `experiments`, `model_variants`, `question_snapshots` are immutable after creation
   - Identity-defining fields cannot change
   - Ensures reproducibility of historical runs

3. **Auditable by Design**
   - All tables have `created_at` timestamps
   - Execution tables have timing fields (`started_at`, `finished_at`, `occurred_at`)
   - Every record tells a complete story

4. **No Execution Without Identity**
   - Every response/error must reference a valid `run_id`, `variant_id`, `snapshot_id`
   - Foreign keys enforce referential integrity
   - No orphaned records allowed

5. **No Inference During Execution**
   - All configuration is resolved before execution
   - Database stores effective configuration, not defaults
   - Execution engine reads, never infers

### 1.2 Design Goals

| Goal | Description |
|------|-------------|
| **Reproducibility** | Same experiment + same run = same results |
| **Auditability** | Complete execution history preserved |
| **Idempotency** | Duplicate writes are skipped, not overwritten |
| **Integrity** | Foreign keys enforce valid relationships |
| **Performance** | Partial indexes optimize common queries |

---

## 2. Table Contracts

### 2.1 experiments

**Purpose**: Store frozen experiment definitions with immutable configuration.

**Contract**:
- **Immutability**: After creation, experiments are NEVER modified
- **Uniqueness**: `name` must be unique across all experiments
- **Configuration**: All experiment-level config stored in `config_json`
- **Deduplication**: `config_hash` prevents duplicate configurations

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `experiment_id` | TEXT | PRIMARY KEY | Unique experiment identifier (`exp_XXXXXXXX`) |
| `name` | TEXT | UNIQUE NOT NULL | Human-readable experiment name |
| `description` | TEXT | — | Optional description |
| `config_json` | TEXT | NOT NULL | JSON configuration (18 experiment-level keys) |
| `config_hash` | TEXT | NOT NULL | SHA256 hash of `config_json` for deduplication |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Configuration Keys** (stored in `config_json`):
- `RUN_RESPONSES_SEED` — Default seed for runs
- `RUN_RESPONSES_SYSTEM_PROMPT` — Default system prompt template
- `RUN_RESPONSES_USER_PROMPT` — Default user prompt template
- `EXPERIMENT_DESCRIPTION` — Experiment description
- Plus 14 other experiment-level configuration keys

**Operations**:
- ✅ CREATE — Insert new experiment
- ✅ READ — Query by `experiment_id` or `name`
- ❌ UPDATE — NOT ALLOWED (immutable)
- ✅ DELETE — Hard delete (CASCADEs to related data)

**Constraints**:
```sql
PRIMARY KEY (experiment_id)
UNIQUE (name)
NOT NULL (name, config_json, config_hash)
```

---

### 2.2 model_variants

**Purpose**: Store model variant configurations within experiments.

**Contract**:
- **Immutability**: After creation, variants are NEVER modified
- **Scoping**: Variants belong to experiments (not global)
- **Uniqueness**: `(experiment_id, variant_signature)` must be unique
- **Identity**: `variant_signature` defines variant identity

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `variant_id` | TEXT | PRIMARY KEY | Unique variant identifier (`var_XXXXXXXX`) |
| `experiment_id` | TEXT | NOT NULL FK → experiments | Parent experiment |
| `model_id` | TEXT | NOT NULL | Model identifier (`provider/model-name`) |
| `variant_signature` | TEXT | NOT NULL | Unique signature within experiment |
| `config` | TEXT | NOT NULL | JSON configuration (10 model-level keys) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Configuration Keys** (stored in `config`):
- `reasoning_mode` — 'off', 'auto', 'effort', 'budget', 'unspecified'
- `reasoning_effort` — 'xhigh', 'high', 'medium', 'low', 'minimal'
- `vision_enabled` — boolean
- `structured_output` — boolean
- `web_access_enabled` — boolean
- `temperature`, `top_p`, `max_tokens` — Generation parameters

**Variant Signature Format**:
```
{model_id}::reasoning={mode}::vision={true|false}::structured={true|false}
```

**Operations**:
- ✅ CREATE — Insert new variant
- ✅ READ — Query by `variant_id` or `(experiment_id, variant_signature)`
- ❌ UPDATE — NOT ALLOWED (immutable)
- ✅ DELETE — Hard delete (RESTRICT if has responses)

**Constraints**:
```sql
PRIMARY KEY (variant_id)
FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
UNIQUE (experiment_id, variant_signature)
NOT NULL (experiment_id, model_id, variant_signature, config)
```

**Indexes**:
```sql
CREATE INDEX idx_variants_by_experiment ON model_variants(experiment_id);
```

---

### 2.3 question_snapshots

**Purpose**: Store immutable question snapshots within experiments.

**Contract**:
- **Immutability**: After creation, snapshots are NEVER modified
- **Scoping**: Snapshots belong to experiments (not global)
- **Uniqueness**: `(experiment_id, question_position)` must be unique
- **Completeness**: `question_payload` contains complete question data

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `snapshot_id` | TEXT | PRIMARY KEY | Unique snapshot identifier (`snap_XXXXXXXX`) |
| `experiment_id` | TEXT | NOT NULL FK → experiments | Parent experiment |
| `json_question_id` | TEXT | NOT NULL | Source question ID from dataset |
| `question_position` | INTEGER | NOT NULL | Internal numeric ID (1..N) |
| `question_payload` | TEXT | NOT NULL | JSON payload (stem, options, answer_key, meta) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Question Payload Structure**:
```json
{
  "id": "Q001",
  "stem": "What is 2+2?",
  "options": {
    "A": "3",
    "B": "4",
    "C": "5",
    "D": "6"
  },
  "answer_key": "B",
  "meta": {
    "difficulty": "easy",
    "category": "math"
  }
}
```

**Operations**:
- ✅ CREATE — Insert new snapshot
- ✅ READ — Query by `snapshot_id` or `(experiment_id, json_question_id)`
- ❌ UPDATE — NOT ALLOWED (immutable)
- ✅ DELETE — Hard delete (RESTRICT if has responses)

**Constraints**:
```sql
PRIMARY KEY (snapshot_id)
FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
UNIQUE (experiment_id, question_position)
NOT NULL (experiment_id, json_question_id, question_position, question_payload)
```

**Indexes**:
```sql
CREATE INDEX idx_snapshots_by_experiment ON question_snapshots(experiment_id);
```

---

### 2.4 runs

**Purpose**: Store run definitions (execution instances of experiments).

**Contract**:
- **Config Immutability**: `config` JSON is immutable after creation
- **Status Mutability**: `status` can change during execution lifecycle
- **Validity**: `status` must be one of: `pending`, `running`, `completed`, `failed`, `partial_failed`
- **Duration Tracking**: `duration` accumulates execution time (for partial runs)

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | TEXT | PRIMARY KEY | Unique run identifier (`run_XXXXXXXX`) |
| `experiment_id` | TEXT | NOT NULL FK → experiments | Parent experiment |
| `config` | TEXT | NOT NULL | JSON configuration (3 run-level keys) |
| `status` | TEXT | NOT NULL DEFAULT 'pending' | Lifecycle status |
| `duration` | INTEGER | DEFAULT 0 | Execution duration in milliseconds |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Configuration Keys** (stored in `config`):
- `seed` — Random seed for reproducibility
- `system_prompt` — Effective system prompt
- `user_prompt` — Effective user prompt

**Status Lifecycle**:
```
pending → running → completed
              ↓
              ↓→ failed
              ↓→ partial_failed
```

**Operations**:
- ✅ CREATE — Insert new run
- ✅ READ — Query by `run_id` or `experiment_id`
- ⚠️ UPDATE — `status` and `duration` ONLY
- ✅ DELETE — Hard delete (CASCADEs to responses/errors)

**Constraints**:
```sql
PRIMARY KEY (run_id)
FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
NOT NULL (experiment_id, config, status)
```

**Indexes**:
```sql
CREATE INDEX idx_runs_by_experiment ON runs(experiment_id);
CREATE INDEX idx_runs_pending ON runs(status) WHERE status = 'pending';
```

---

### 2.5 responses

**Purpose**: Store model response results for each (run, variant, snapshot) combination.

**Contract**:
- **Append-Only**: Responses are INSERT-only (idempotent writes)
- **Idempotency**: `(run_id, variant_id, snapshot_id)` must be unique
- **Review Calculation**: `review_status` is calculated from `parse_confidence` and `selected_answer`
- **Token Calculation**: `effective_tokens` = `input_tokens` + `response_tokens` + `reasoning_tokens`

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `response_id` | TEXT | PRIMARY KEY | Unique response identifier (`resp_XXXXXXXX`) |
| `run_id` | TEXT | NOT NULL FK → runs | Parent run |
| `variant_id` | TEXT | NOT NULL FK → model_variants | Model variant |
| `snapshot_id` | TEXT | NOT NULL FK → question_snapshots | Question snapshot |
| `model_id` | TEXT | NOT NULL | Denormalized model identifier |
| `question_id` | TEXT | NOT NULL | Denormalized question identifier |
| `status` | TEXT | — | Response processing status |
| `finish_reason` | TEXT | — | Model finish reason |
| `error_details` | TEXT | — | Error message if failed |
| `response_text` | TEXT | — | Raw model response text |
| `selected_answer` | TEXT | — | Parsed answer (A/B/C/D) |
| `is_correct` | BOOLEAN | — | Whether answer matches answer_key |
| `parse_confidence` | TEXT | DEFAULT 'unknown' | Parser confidence level |
| `review_status` | TEXT | — | Review flag ('needs_review', 'reviewed', 'auto') |
| `manual_answer` | TEXT | — | Human-corrected answer |
| `raw_response` | TEXT | — | Complete raw API response |
| `cost` | REAL | — | API cost in USD |
| `input_tokens` | INTEGER | — | Input tokens sent to model |
| `response_tokens` | INTEGER | — | Output tokens from model |
| `reasoning_tokens` | INTEGER | — | Tokens used for reasoning |
| `effective_tokens` | INTEGER | — | Total tokens (sum of all) |
| `latency_ms` | INTEGER | — | API latency in milliseconds |
| `started_at` | TIMESTAMP | — | Execution start time |
| `finished_at` | TIMESTAMP | — | Execution end time |

**Review Fields Contract**:

| Field | Purpose | Set By | Calculation |
|-------|---------|--------|-------------|
| `parse_confidence` | Parser confidence level | ExecutionEngine | From AnswerParser |
| `selected_answer` | Parsed answer (A/B/C/D) | ExecutionEngine | From AnswerParser |
| `review_status` | Manual review flag | **ResultWriter** | Calculated (see below) |
| `manual_answer` | Human-corrected answer | Reviewer | Post-execution |

**Review Status Calculation** (by ResultWriter):
```python
def calculate_review_status(parse_confidence: str, selected_answer: str | None) -> str:
    if parse_confidence != 'clear' or selected_answer is None:
        return 'needs_review'
    return 'auto'
```

**Token Calculation** (by ResponseRepository):
```python
def calculate_effective_tokens(input_tokens, response_tokens, reasoning_tokens):
    if any(x is None for x in [input_tokens, response_tokens, reasoning_tokens]):
        return None
    return input_tokens + response_tokens + reasoning_tokens
```

**Operations**:
- ✅ CREATE — Insert new response (idempotent)
- ✅ READ — Query by `response_id`, `run_id`, or `review_status`
- ⚠️ UPDATE — `manual_answer`, `review_status` ONLY (manual review)
- ❌ DELETE — NOT ALLOWED (append-only)

**Constraints**:
```sql
PRIMARY KEY (response_id)
FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT
UNIQUE (run_id, variant_id, snapshot_id)
NOT NULL (run_id, variant_id, snapshot_id, model_id, question_id)
```

**Indexes**:
```sql
CREATE INDEX idx_responses_by_run ON responses(run_id);
CREATE INDEX idx_responses_needs_review ON responses(review_status) WHERE review_status = 'needs_review';
```

---

### 2.6 errors

**Purpose**: Store execution errors for failed model invocations.

**Contract**:
- **Append-Only**: Errors are INSERT-only (idempotent writes)
- **Observational**: Errors record what happened, not what should happen
- **Classification**: `error_type` categorizes the failure

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `error_id` | TEXT | PRIMARY KEY | Unique error identifier (`err_XXXXXXXX`) |
| `run_id` | TEXT | NOT NULL FK → runs | Parent run |
| `variant_id` | TEXT | NOT NULL FK → model_variants | Model variant |
| `snapshot_id` | TEXT | NOT NULL FK → question_snapshots | Question snapshot |
| `question_id` | TEXT | NOT NULL | Denormalized question identifier |
| `error_type` | TEXT | NOT NULL | Error category |
| `error_message` | TEXT | NOT NULL | Human-readable error message |
| `attempt_count` | INTEGER | NOT NULL DEFAULT 1 | Number of retry attempts |
| `stack_trace` | TEXT | — | Full stack trace for debugging |
| `occurred_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Error occurrence timestamp |

**Error Types**:
- `api_error` — API call failures (HTTP 4xx, 5xx)
- `timeout` — Request timeout
- `parse_error` — Response parsing failures
- `config_error` — Configuration validation failures

**Operations**:
- ✅ CREATE — Insert new error (idempotent)
- ✅ READ — Query by `error_id` or `run_id`
- ❌ UPDATE — NOT ALLOWED (append-only)
- ❌ DELETE — NOT ALLOWED (append-only)

**Constraints**:
```sql
PRIMARY KEY (error_id)
FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT
NOT NULL (run_id, variant_id, snapshot_id, question_id, error_type, error_message, attempt_count)
```

**Indexes**:
```sql
CREATE INDEX idx_errors_by_run ON errors(run_id);
```

---

## 3. Relationship Contracts

### 3.1 Foreign Key Rules

| From | To | On Delete | On Update | Rationale |
|------|----|-----------|-----------|-----------|
| `model_variants.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION | Deleting experiment deletes variants |
| `question_snapshots.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION | Deleting experiment deletes snapshots |
| `runs.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION | Deleting experiment deletes runs |
| `responses.run_id` | `runs.run_id` | CASCADE | NO ACTION | Deleting run deletes responses |
| `responses.variant_id` | `model_variants.variant_id` | RESTRICT | NO ACTION | Protect historical data |
| `responses.snapshot_id` | `question_snapshots.snapshot_id` | RESTRICT | NO ACTION | Protect historical data |
| `errors.run_id` | `runs.run_id` | CASCADE | NO ACTION | Deleting run deletes errors |
| `errors.variant_id` | `model_variants.variant_id` | RESTRICT | NO ACTION | Protect historical data |
| `errors.snapshot_id` | `question_snapshots.snapshot_id` | RESTRICT | NO ACTION | Protect historical data |

### 3.2 Cascade Delete Chain

```
DELETE experiment
  ↓ CASCADE
  ├─→ model_variants (deleted)
  ├─→ question_snapshots (deleted)
  └─→ runs (deleted)
        ↓ CASCADE
        ├─→ responses (deleted)
        └─→ errors (deleted)
```

### 3.3 RESTRICT Delete Protection

**Protected Deletes** (will fail if has responses/errors):
- `model_variants` — Cannot delete variant with responses
- `question_snapshots` — Cannot delete snapshot with responses

**Rationale**: Historical data integrity — responses and errors reference these entities.

---

## 4. Immutability Rules

### 4.1 What Can/Cannot Change

| Table | Immutable Fields | Mutable Fields | Never Modified |
|-------|------------------|----------------|----------------|
| `experiments` | ALL | — | ✅ Entire row |
| `model_variants` | ALL | — | ✅ Entire row |
| `question_snapshots` | ALL | — | ✅ Entire row |
| `runs` | `run_id`, `experiment_id`, `config`, `created_at` | `status`, `duration` | ✅ Config fields |
| `responses` | `response_id`, FKs, `model_id`, `question_id`, `started_at` | All result fields, `review_status`, `manual_answer` | ✅ Identity fields |
| `errors` | ALL | — | ✅ Entire row |

### 4.2 Immutability Enforcement

**Application-Level**:
- Repository layer does not provide UPDATE methods for immutable tables
- Entity dataclasses are regular (not frozen) but convention enforces immutability

**Database-Level**:
- No SQL triggers (would add complexity)
- Relies on application discipline

**Recommended Enhancement**:
```sql
-- Optional: Add triggers to enforce immutability
CREATE TRIGGER prevent_experiment_update
BEFORE UPDATE ON experiments
BEGIN
    SELECT RAISE(ABORT, 'experiments table is immutable');
END;
```

---

## 5. Audit Requirements

### 5.1 What Must Be Tracked

| Event | Timestamp Field | Table |
|-------|-----------------|-------|
| Experiment created | `created_at` | `experiments` |
| Variant created | `created_at` | `model_variants` |
| Snapshot created | `created_at` | `question_snapshots` |
| Run created | `created_at` | `runs` |
| Response execution started | `started_at` | `responses` |
| Response execution finished | `finished_at` | `responses` |
| Error occurred | `occurred_at` | `errors` |

### 5.2 Audit Trail Queries

**List experiment history**:
```sql
SELECT name, created_at
FROM experiments
ORDER BY created_at DESC;
```

**List run execution timeline**:
```sql
SELECT run_id, status, created_at
FROM runs
WHERE experiment_id = ?
ORDER BY created_at ASC;
```

**List response execution times**:
```sql
SELECT response_id, started_at, finished_at, latency_ms
FROM responses
WHERE run_id = ?
ORDER BY started_at ASC;
```

**List error timeline**:
```sql
SELECT error_id, error_type, occurred_at
FROM errors
WHERE run_id = ?
ORDER BY occurred_at ASC;
```

---

## 6. Query Patterns

### 6.1 Common Queries

**Get experiment with counts**:
```sql
SELECT
    e.experiment_id,
    e.name,
    COUNT(DISTINCT mv.variant_id) as variant_count,
    COUNT(DISTINCT qs.snapshot_id) as question_count,
    COUNT(DISTINCT r.run_id) as run_count
FROM experiments e
LEFT JOIN model_variants mv ON e.experiment_id = mv.experiment_id
LEFT JOIN question_snapshots qs ON e.experiment_id = qs.experiment_id
LEFT JOIN runs r ON e.experiment_id = r.experiment_id
WHERE e.experiment_id = ?
GROUP BY e.experiment_id;
```

**Get pending runs (uses partial index)**:
```sql
SELECT run_id, experiment_id, config
FROM runs
WHERE status = 'pending'
ORDER BY created_at ASC;
```

**Get responses needing review (uses partial index)**:
```sql
SELECT
    r.response_id,
    r.run_id,
    r.variant_id,
    r.model_id,
    r.question_id,
    r.selected_answer,
    r.parse_confidence,
    r.review_status
FROM responses r
WHERE r.review_status = 'needs_review'
ORDER BY r.started_at ASC;
```

**Get run results summary**:
```sql
SELECT
    r.run_id,
    COUNT(resp.response_id) as total_responses,
    SUM(CASE WHEN resp.is_correct = 1 THEN 1 ELSE 0 END) as correct_count,
    SUM(CASE WHEN resp.is_correct = 0 THEN 1 ELSE 0 END) as incorrect_count,
    SUM(CASE WHEN e.error_id IS NOT NULL THEN 1 ELSE 0 END) as error_count
FROM runs r
LEFT JOIN responses resp ON r.run_id = resp.run_id
LEFT JOIN errors e ON r.run_id = e.run_id
WHERE r.run_id = ?
GROUP BY r.run_id;
```

**Get model variant performance**:
```sql
SELECT
    mv.variant_id,
    mv.model_id,
    mv.variant_signature,
    COUNT(resp.response_id) as total_responses,
    AVG(CASE WHEN resp.is_correct = 1 THEN 1.0 ELSE 0.0 END) as accuracy,
    AVG(resp.latency_ms) as avg_latency,
    SUM(resp.cost) as total_cost
FROM model_variants mv
LEFT JOIN responses resp ON mv.variant_id = resp.variant_id
WHERE mv.experiment_id = ?
GROUP BY mv.variant_id;
```

---

## 7. Summary

The Database Layer is the foundation of the Benchmark LLM system, providing:

1. **Immutable identity** — Experiments, variants, and snapshots are frozen after creation
2. **Append-only results** — Responses and errors are never modified
3. **Referential integrity** — Foreign keys enforce valid relationships
4. **Auditability** — All events are timestamped
5. **Idempotency** — Unique constraints prevent duplicate writes
6. **Performance** — Partial indexes optimize common queries

This document defines the contracts that all components must respect when interacting with the database layer.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Status**: TO-BE (Target Architecture)
**Authoritative Source**: `docs/architecture/to-be/schema.sql`
