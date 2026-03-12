# Database Schema Documentation

This document describes the SQLite database schema used by Benchmark LLM for storing experiments, runs, and responses.

## Overview

The database is designed to support three execution modes:
- **Test Mode**: No data persistence (in-memory database)
- **Dev Mode**: Full persistence without experiment tracking
- **Experiment Mode**: Full persistence with frozen, auditable configuration

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐
│ experiments  │       │    models    │
├──────────────┤       ├──────────────┤
│ experiment_id│       │   model_id   │
│ name         │       │   provider   │
│ config_hash  │       │  model_name  │
└──────┬───────┘       └──────┬───────┘
       │                      │
       │ 1:N                  │ 1:N
       ▼                      ▼
┌──────────────┐       ┌───────────────────┐
│     runs     │       │question_snapshots │◀─────┐
├──────────────┤       ├───────────────────┤      │
│    run_id    │       │   snapshot_id     │      │
│ experiment_id│       │   experiment_id   │      │
│    is_dev    │       │   question_id     │      │
│     seed     │       │   question_json   │      │
└──────┬───────┘       └───────────────────┘      │
       │                      │                    │
       │ 1:N                  │ 1:N                │ 1:N
       ▼                      ▼                    │
┌──────────────────────────────────────────────────┘
│              responses                           │
├──────────────────────────────────────────────────┤
│           response_id                            │
│           run_id                                 │
│           snapshot_id ───────────────────────────┘
│           model_id ──────────────────────────────┐
│           iteration                              │
│           selected_answer                        │
│           ...                                    │
└──────────────────────────────────────────────────┤
                              ▲                    │
                              │                    │
                       ┌──────────────┐            │
                       │   questions  │            │
                       ├──────────────┤            │
                       │  question_id │────────────┘
                       │     stem     │
                       │  options_json│
                       └──────────────┘

┌──────────────┐
│    errors    │
├──────────────┤
│   error_id   │
│  run_id      │
│  question_id │
│   model_id   │
└──────────────┘
```

---

## Tables

### `experiments`

Stores experiment configurations with frozen, immutable snapshots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `experiment_id` | TEXT | PRIMARY KEY | Unique identifier for the experiment |
| `name` | TEXT | NOT NULL, UNIQUE | Human-readable experiment name |
| `description` | TEXT | | Optional description |
| `config_json` | TEXT | NOT NULL | JSON-serialized configuration snapshot |
| `config_hash` | TEXT | NOT NULL | SHA-256 hash for deduplication |
| `system_prompt` | TEXT | | System prompt used in experiment |
| `user_prompt_template` | TEXT | | User prompt template used |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Indexes:**
- `idx_experiments_name` - Fast lookup by name
- `idx_experiments_hash` - Fast lookup by config hash

**Usage:**
- Created only in **Experiment Mode**
- Configuration is frozen and auditable
- Multiple runs can reference the same experiment

---

### `runs`

Tracks individual benchmark execution runs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `run_id` | TEXT | PRIMARY KEY | Unique identifier for the run |
| `experiment_id` | TEXT | FOREIGN KEY → experiments | Associated experiment (NULL for dev mode) |
| `seed` | INTEGER | | Random seed used (if any) |
| `is_dev` | BOOLEAN | NOT NULL, DEFAULT 0 | True if run is in development mode |
| `started_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Run start timestamp |
| `finished_at` | TIMESTAMP | | Run completion timestamp |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | Run status |

**Status Values:**
- `pending` - Run not yet started
- `running` - Run in progress
- `completed` - Run finished successfully
- `failed` - Run failed due to error

**Indexes:**
- `idx_runs_experiment` - Fast lookup by experiment
- `idx_runs_status` - Fast lookup by status
- `idx_runs_is_dev` - Fast lookup by dev mode flag

**Usage:**
- **Dev Mode**: `experiment_id = NULL`, `is_dev = 1`
- **Experiment Mode**: `experiment_id = <id>`, `is_dev = 0`
- **Test Mode**: No runs created (no persistence)

---

### `models`

Registry of LLM models used in benchmarks.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `model_id` | TEXT | PRIMARY KEY | Unique identifier (e.g., `openai/gpt-4`) |
| `provider` | TEXT | NOT NULL | Provider name (e.g., `openai`, `anthropic`) |
| `model_name` | TEXT | NOT NULL | Model name (e.g., `gpt-4`) |
| `supports_multimodal` | BOOLEAN | NOT NULL, DEFAULT 0 | Multimodal capability flag |
| `metadata_json` | TEXT | | Additional metadata as JSON |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Registration timestamp |

**Indexes:**
- `idx_models_provider` - Fast lookup by provider
- `idx_models_unique` - Unique constraint on (provider, model_name)

**Usage:**
- Models are registered automatically on first use
- Metadata may include context length, capabilities, etc.

---

### `questions`

Stores questionnaire questions for reproducibility.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `question_id` | TEXT | PRIMARY KEY | Unique identifier (e.g., `Q001`) |
| `stem` | TEXT | NOT NULL | Question text/statement |
| `options_json` | TEXT | NOT NULL | JSON-serialized answer options |
| `correct_answer` | TEXT | | Correct answer letter/value |
| `has_image` | BOOLEAN | NOT NULL, DEFAULT 0 | Image presence flag |
| `image_path` | TEXT | | Path to image file (if any) |
| `status` | TEXT | NOT NULL, DEFAULT 'active' | Question status |

**Status Values:**
- `active` - Question is in use
- `archived` - Question retired from active use
- `draft` - Question under development

**Indexes:**
- `idx_questions_status` - Fast lookup by status
- `idx_questions_has_image` - Fast lookup by image flag

**Usage:**
- Questions loaded from external files (JSON/CSV)
- Persisted for audit trails and reproducibility
- This is the CANONICAL CATALOG - questions can be updated here without affecting existing experiment results
- Referenced by question_snapshots, NOT directly by responses

---

### `question_snapshots` (NEW)

Stores **immutable snapshots** of questions used in each experiment.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `snapshot_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing ID |
| `experiment_id` | TEXT | NOT NULL, FK → experiments | Associated experiment (NEVER NULL) |
| `question_id` | TEXT | NOT NULL, FK → questions | Reference to canonical question |
| `question_json` | TEXT | NOT NULL | Complete JSON representation of the question |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

**Indexes:**
- `idx_question_snapshots_experiment` - Fast lookup by experiment
- `idx_question_snapshots_question` - Fast lookup by question
- `idx_question_snapshots_unique` - Unique constraint on (experiment_id, question_id)

**Usage:**
- Created automatically when a question is first used in an experiment
- **Immutable** - never updated after creation
- **Every snapshot MUST belong to a valid experiment** - NO NULL experiment_id allowed
- Ensures reproducibility: experiment results reference the exact question version used
- Responses reference snapshots, not the canonical questions table
- Allows questions to be corrected/updated without affecting old experiments
- In dev mode, a "shadow experiment" is automatically created for isolation

**Snapshot Creation Logic:**
1. When executing a question, check if snapshot exists for (experiment_id, question_id)
2. If exists: reuse existing snapshot_id
3. If not exists: create new snapshot with complete question JSON
4. Snapshot includes: id, stem, options, answer_key, has_image, image_path

**Example JSON stored in question_json:**
```json
{
  "id": "Q001",
  "stem": "Qual é a capital da França?",
  "options": {"A": "Paris", "B": "Londres", "C": "Berlim", "D": "Madrid"},
  "answer_key": "A",
  "has_image": false,
  "image_path": null
}
```

---

### `responses`

Core table storing model responses to questions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `response_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing ID |
| `run_id` | TEXT | NOT NULL, FK → runs | Parent run |
| `snapshot_id` | INTEGER | NOT NULL, FK → question_snapshots | Question snapshot answered (authoritative) |
| `question_id` | TEXT | NOT NULL, FK → questions | Question ID (semantic redundancy) |
| `model_id` | TEXT | NOT NULL, FK → models | Model that responded |
| `iteration` | INTEGER | NOT NULL, DEFAULT 1 | Iteration number (1-based) |
| `selected_answer` | TEXT | | Answer letter selected by model |
| `response_text` | TEXT | | Full model response text |
| `is_correct` | BOOLEAN | | Whether answer is correct |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | Response status |
| `latency_ms` | INTEGER | | Response time in milliseconds |
| `input_tokens` | INTEGER | | Tokens in request (prompt_tokens) |
| `response_tokens` | INTEGER | | Tokens in response (completion_tokens) |
| `total_tokens` | INTEGER | | input_tokens + response_tokens (excludes reasoning_tokens) |
| `reasoning_tokens` | INTEGER | | Reasoning tokens used (subtype of response_tokens) |
| `effective_tokens` | INTEGER | | input_tokens + response_tokens + reasoning_tokens (total computational cost) |
| `cost` | REAL | | Cost in credits (from usage.cost) |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Response timestamp |

**Token Calculation Formulas:**
```
total_tokens = input_tokens + response_tokens
effective_tokens = input_tokens + response_tokens + reasoning_tokens
```

**Note:** `reasoning_tokens` are a subtype of `response_tokens`, not additional. They represent tokens used for internal reasoning/chain-of-thought that are included in the completion but tracked separately for analysis.

**Indexes:**
- `idx_responses_run` - Fast lookup by run
- `idx_responses_snapshot` - Fast lookup by snapshot (authoritative)
- `idx_responses_question` - Fast lookup by question (semantic redundancy)
- `idx_responses_model` - Fast lookup by model
- `idx_responses_run_iteration` - Composite index for (run + iteration)
- `idx_responses_model_correct` - Composite index for accuracy analysis

**Usage:**
- One row per model per question per iteration
- `snapshot_id` is the **authoritative reference** for immutability
- `question_id` is **semantic redundancy** for easier querying and debugging
- Both IDs should always be consistent (question_id matches snapshot's question_json->>'$.id')
- Iteration is a field (not a separate table)
- Token metrics stored separately for analysis

**Why Both snapshot_id and question_id?**
- `snapshot_id` ensures immutability and points to the exact question version used
- `question_id` provides ergonomic queries without requiring JOINs for simple operations
- This design balances data integrity with query convenience

---

### `errors`

Tracks errors during benchmark execution.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `error_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing ID |
| `run_id` | TEXT | FK → runs | Parent run |
| `question_id` | TEXT | FK → questions | Question being answered |
| `model_id` | TEXT | FK → models | Model that encountered error |
| `error_type` | TEXT | NOT NULL | Error type/category |
| `error_message` | TEXT | NOT NULL | Human-readable message |
| `stack_trace` | TEXT | | Full stack trace (if any) |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Error timestamp |

**Indexes:**
- `idx_errors_run` - Fast lookup by run
- `idx_errors_type` - Fast lookup by error type
- `idx_errors_timestamp` - Fast lookup by timestamp

**Usage:**
- Errors tracked separately from responses
- Foreign keys set to NULL if referenced entity deleted (except run)
- Used for debugging and error analysis

---

### `schema_metadata` (Optional)

Documentation table for schema descriptions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `table_name` | TEXT | NOT NULL | Table name |
| `column_name` | TEXT | | Column name (NULL for table-level) |
| `description` | TEXT | NOT NULL | Description text |

**Usage:**
- Optional documentation storage
- Not populated by default
- Available for future tooling integration

---

## Design Decisions

### Why No `iterations` Table?

Previous versions had a separate `iterations` table. This was removed because:
1. **No Independent Metadata**: Iterations have no metadata beyond iteration number
2. **Simpler Queries**: Single table for responses is easier to query
3. **Performance**: Fewer joins required for common queries
4. **Iteration as Field**: Iteration number is just another dimension in responses

### Why Store Questions in Database?

Questions are loaded from external files but persisted because:
1. **Reproducibility**: Ensures exact questions used are preserved
2. **Audit Trail**: Complete record of what was asked
3. **Version Independence**: Database works even if source files change
4. **Analysis**: SQL queries can analyze question patterns

### Why Use Question Snapshots?

**Problem:** Questions may receive corrections over time (grammar, alternative wording, etc.), but experiment results must remain valid and reproducible.

**Solution:** The `question_snapshots` table stores immutable copies of questions at the moment they are first used in an experiment.

**Benefits:**
1. **Reproducibility**: Experiment results always reference the exact question version used
2. **Comparability**: Models compared within an experiment answer identical questions
3. **Independence**: External JSON changes don't affect old experiment results
4. **Audit Trail**: Complete record of what was asked, when, and in what version
5. **Flexibility**: Canonical questions can be corrected without breaking historical data

**How It Works:**
- When a question is executed in an experiment, a snapshot is created (if it doesn't exist)
- The snapshot contains the complete question JSON (id, stem, options, answer_key, etc.)
- All responses reference the snapshot, not the canonical question
- Snapshots are never modified after creation
- Multiple experiments can have different snapshots of the same question

### Why Separate `errors` Table?

Errors are separate from responses because:
1. **Different Cardinality**: A response may have multiple errors
2. **Analysis**: Error patterns can be analyzed independently
3. **Debugging**: Full stack traces don't clutter responses table
4. **Optional**: Not all runs have errors, keeping responses lean

### Token Tracking

Separate token fields (`input_tokens`, `output_tokens`, `reasoning_tokens`) enable:
1. **Cost Analysis**: Calculate API costs per model/run
2. **Performance**: Correlate token usage with accuracy
3. **Optimization**: Identify token-efficient models
4. **Reasoning Impact**: Measure reasoning token overhead

---

## Common Queries

### Get All Runs for an Experiment
```sql
SELECT run_id, started_at, finished_at, status
FROM runs
WHERE experiment_id = ?
ORDER BY started_at DESC;
```

### Get Model Accuracy for a Run
```sql
SELECT model_id, 
       COUNT(*) as total,
       SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct,
       CAST(SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100 as accuracy
FROM responses
WHERE run_id = ?
GROUP BY model_id;
```

### Get Average Latency by Model
```sql
SELECT model_id, AVG(latency_ms) as avg_latency
FROM responses
WHERE run_id = ?
GROUP BY model_id;
```

### Get All Errors for a Run
```sql
SELECT error_type, error_message, question_id, model_id, timestamp
FROM errors
WHERE run_id = ?
ORDER BY timestamp;
```

### Get Experiment by Config Hash
```sql
SELECT experiment_id, name, config_json
FROM experiments
WHERE config_hash = ?;
```

### Get Responses with Question Details (via Snapshot)
```sql
SELECT r.response_id, r.selected_answer, r.is_correct,
       qs.question_json,
       json_extract(qs.question_json, '$.stem') as question_stem,
       json_extract(qs.question_json, '$.answer_key') as correct_answer
FROM responses r
JOIN question_snapshots qs ON r.snapshot_id = qs.snapshot_id
WHERE r.run_id = ?
ORDER BY r.iteration, qs.question_id;
```

### Get All Snapshots for an Experiment
```sql
SELECT snapshot_id, question_id, question_json, created_at
FROM question_snapshots
WHERE experiment_id = ?
ORDER BY question_id;
```

### Compare Question Versions Across Experiments
```sql
SELECT qs.experiment_id, qs.question_id, qs.created_at,
       json_extract(qs.question_json, '$.stem') as stem
FROM question_snapshots qs
WHERE qs.question_id = ?
ORDER BY qs.created_at;
```

---

## Migration Notes

This schema (v2.1) introduces question snapshots for reproducibility. Key changes from v2.0:

| Change | Reason |
|--------|--------|
| Added `question_snapshots` table | Immutable question copies for reproducibility |
| Changed `responses.question_id` to `responses.snapshot_id` | Responses now reference snapshots, not canonical questions |
| Added indexes on `question_snapshots` | Performance for snapshot lookups |

**Note**: No migration path is provided. Databases should be recreated from scratch.
