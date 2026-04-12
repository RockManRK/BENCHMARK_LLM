---
type: reference
audience: ai
last-validated: 2026-04-11
status: active
---

# Database Schema Reference

**Purpose:** Current database schema with field descriptions  
**Source:** Extracted from `src/db/schema.py` and `src/db/models.py`

---

## Schema Overview

The system uses **SQLite** with 6 tables:

```
experiments ──┬── model_variants
              ├── question_snapshots
              └── runs ──────┬── responses
                             └── errors
```

**No soft delete** — `is_active` columns removed from all tables.

---

## Tables

### 1. experiments

**Purpose:** Top-level experiment definitions with frozen configuration

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `experiment_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `name` | TEXT | UNIQUE, NOT NULL | Human-readable name |
| `description` | TEXT | NULLABLE | Optional description |
| `config_json` | TEXT | NOT NULL | Frozen configuration (JSON string) |
| `config_hash` | TEXT | NOT NULL | SHA-256 hash of config_json |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |

**config_json contents:**
```json
{
  "RUN_RESPONSES_SEED": "AUTO",
  "SYSTEM_PROMPT": null,
  "USER_PROMPT": null,
  "BASE_URL": "https://openrouter.ai/api/v1",
  "MODEL_MAX_TOKENS_TOTAL": 16384,
  "MODEL_VISION": false,
  ...
}
```

---

### 2. model_variants

**Purpose:** Intentional model configurations within experiments

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `variant_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `experiment_id` | TEXT | FK → experiments, NOT NULL | Parent experiment |
| `model_id` | TEXT | NOT NULL | Base model identifier (e.g., `openai/gpt-4`) |
| `variant_signature` | TEXT | NOT NULL | Human-readable identity |
| `config` | TEXT | NOT NULL | Full configuration (JSON) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |

**UNIQUE Constraint:** `(experiment_id, variant_signature)`

**config contents:**
```json
{
  "MODEL_ID": "openai/gpt-4",
  "MODEL_REASONING_EFFORT": "high",
  "MODEL_MAX_TOKENS_TOTAL": 16384,
  "MODEL_TEMPERATURE": null,
  "MODEL_VISION": false,
  ...
}
```

---

### 3. question_snapshots

**Purpose:** Frozen copies of questions from source dataset

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `snapshot_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `experiment_id` | TEXT | FK → experiments, NOT NULL | Parent experiment |
| `json_question_id` | TEXT | NOT NULL | Original dataset ID (e.g., `Q001`) |
| `question_position` | INTEGER | NOT NULL | 1-based position in file |
| `question_payload` | TEXT | NOT NULL | Complete question JSON |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |

**UNIQUE Constraint:** `(experiment_id, question_position)`

**question_payload format:**
```json
{
  "question_id": "Q001",
  "stem": "What is the capital of France?",
  "options": ["London", "Berlin", "Paris", "Madrid"],
  "answer_key": "B",
  "has_image": false
}
```

---

### 4. runs

**Purpose:** Execution instances of experiments

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `experiment_id` | TEXT | FK → experiments, NOT NULL | Parent experiment |
| `config` | TEXT | NOT NULL | Run configuration (JSON) |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | `pending`, `completed`, `failed`, `partial_failed` |
| `duration` | INTEGER | DEFAULT 0 | Accumulated execution time (milliseconds) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |

**CHECK Constraint:** `status IN ('pending', 'completed', 'failed', 'partial_failed')`

**config contents:**
```json
{
  "RUN_RESPONSES_SEED": 42,
  "SYSTEM_PROMPT": "You are a helpful assistant.",
  "USER_PROMPT": "Answer the question:"
}
```

---

### 5. responses

**Purpose:** Execution results for model + question combinations

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `response_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `run_id` | TEXT | FK → runs, NOT NULL | Parent run |
| `variant_id` | TEXT | FK → model_variants, NOT NULL | Model variant used |
| `snapshot_id` | TEXT | FK → question_snapshots, NOT NULL | Question snapshot answered |
| `model_id` | TEXT | NOT NULL | Base model identifier (redundant) |
| `question_id` | TEXT | NOT NULL | Original question ID (redundant) |
| `status` | TEXT | NULLABLE | `success`, `failure`, `pending` |
| `finish_reason` | TEXT | NULLABLE | API finish reason |
| `error_details` | TEXT | NULLABLE | Error information |
| `response_text` | TEXT | NULLABLE | Full model response |
| `selected_answer` | TEXT | NULLABLE | Parsed answer (A/B/C/D) |
| `is_correct` | BOOLEAN | NULLABLE | Matches answer_key |
| `parse_confidence` | TEXT | DEFAULT 'unknown' | `unknown`, `clear`, `ambiguous`, `no_answer`, `low_confidence` |
| `review_status` | TEXT | NULLABLE | `needs_review`, `reviewed`, etc. |
| `manual_answer` | TEXT | NULLABLE | Human-corrected answer |
| `raw_response` | TEXT | NULLABLE | Complete JSON from API |
| `raw_response_consolidated` | TEXT | NULLABLE | Consolidated response text |
| `request_json` | TEXT | NULLABLE | Complete JSON request sent |
| `cost` | REAL | NULLABLE | API cost |
| `input_tokens` | INTEGER | NULLABLE | Input tokens used |
| `response_tokens` | INTEGER | NULLABLE | Response tokens (completion_tokens) |
| `reasoning_tokens` | INTEGER | NULLABLE | Reasoning tokens |
| `effective_tokens` | INTEGER | NULLABLE | input + response + reasoning |
| `latency_ms` | INTEGER | NULLABLE | API call latency |
| `started_at` | TIMESTAMP | NULLABLE | Request sent time |
| `finished_at` | TIMESTAMP | NULLABLE | Response received time |

**Experimental Context Columns (Randomization Tracking):**

| Column | Type | Description |
|--------|------|-------------|
| `randomization_enabled` | BOOLEAN | Whether randomization was applied |
| `randomization_seed` | INTEGER | Seed used (NULL = disabled) |
| `options_presented` | TEXT | Options as shown to LLM (JSON) |
| `correct_option_presented` | TEXT | Correct answer in presented space |
| `option_letter_map` | TEXT | Mapping: presented letter → original letters |

**UNIQUE Constraint:** `(run_id, variant_id, snapshot_id)` — **Idempotency guarantee**

---

### 6. errors

**Purpose:** Execution error records

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `error_id` | TEXT | PRIMARY KEY | UUID-format identifier |
| `run_id` | TEXT | FK → runs, NOT NULL | Parent run |
| `variant_id` | TEXT | FK → model_variants, NOT NULL | Model variant |
| `snapshot_id` | TEXT | FK → question_snapshots, NOT NULL | Question snapshot |
| `question_id` | TEXT | NOT NULL | Original question ID |
| `error_type` | TEXT | NOT NULL | Error classification |
| `error_message` | TEXT | NOT NULL | Error description |
| `attempt_count` | INTEGER | NOT NULL, DEFAULT 1 | Total retry attempts |
| `stack_trace` | TEXT | NULLABLE | Full stack trace |
| `occurred_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Error time |

---

## Indexes

| Table | Index | Purpose |
|-------|-------|---------|
| `experiments` | `idx_experiments_created_at` | List experiments by creation time |
| `model_variants` | `idx_variants_by_experiment` | List variants by experiment |
| `model_variants` | `idx_model_variants_created_at` | List variants by creation time |
| `question_snapshots` | `idx_snapshots_by_experiment` | List snapshots by experiment |
| `question_snapshots` | `idx_question_snapshots_created_at` | List snapshots by creation time |
| `runs` | `idx_runs_by_experiment` | List runs by experiment |
| `runs` | `idx_runs_pending` | Partial index: pending runs (execution) |
| `runs` | `idx_runs_created_at` | List runs by creation time |
| `responses` | `idx_responses_by_run` | List responses by run |
| `responses` | `idx_responses_needs_review` | Partial index: responses needing review |
| `responses` | `idx_responses_started_at` | List responses by start time |
| `responses` | `idx_responses_finished_at` | List responses by finish time |
| `errors` | `idx_errors_by_run` | List errors by run |
| `errors` | `idx_errors_occurred_at` | List errors by occurrence time |

---

## Foreign Key Relationships

```
model_variants.experiment_id → experiments.experiment_id
question_snapshots.experiment_id → experiments.experiment_id
runs.experiment_id → experiments.experiment_id
responses.run_id → runs.run_id
responses.variant_id → model_variants.variant_id
responses.snapshot_id → question_snapshots.snapshot_id
errors.run_id → runs.run_id
errors.variant_id → model_variants.variant_id
errors.snapshot_id → question_snapshots.snapshot_id
```

**CASCADE behavior:** Foreign keys reference experiment tables; deletion cascades per SQLite rules.

---

## Schema Version

- **Version:** TO-BE (greenfield, no migrations)
- **Location:** `src/db/schema.py`
- **Creation:** `create_schema()` function called at startup

---

## Related Documents

- [architecture/conceptual-model.md](../architecture/conceptual-model.md) — Entity relationships
- [contracts/idempotency.md](../contracts/idempotency.md) — UNIQUE constraint ensures no duplicates
- [contracts/data-auditability.md](../contracts/data-auditability.md) — Full traceability via FKs
