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
┌──────────────┐       ┌──────────────┐
│     runs     │──────▶│   responses  │◀──────┐
├──────────────┤       ├──────────────┤       │
│    run_id    │       │  response_id │       │
│ experiment_id│       │   run_id     │       │
│    is_dev    │       │  question_id │───────┘
│     seed     │       │   model_id   │
└──────────────┘       └──────────────┘
                              ▲
                              │
                       ┌──────────────┐
                       │   questions  │
                       ├──────────────┤
                       │  question_id │
                       │     stem     │
                       │  options_json│
                       └──────────────┘

┌──────────────┐
│    errors    │
├──────────────┤
│   error_id   │
│    run_id    │
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
- Referenced by responses via `question_id`

---

### `responses`

Core table storing model responses to questions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `response_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Auto-incrementing ID |
| `run_id` | TEXT | NOT NULL, FK → runs | Parent run |
| `question_id` | TEXT | NOT NULL, FK → questions | Question answered |
| `model_id` | TEXT | NOT NULL, FK → models | Model that responded |
| `iteration` | INTEGER | NOT NULL, DEFAULT 1 | Iteration number (1-based) |
| `selected_answer` | TEXT | | Answer letter selected by model |
| `response_text` | TEXT | | Full model response text |
| `is_correct` | BOOLEAN | | Whether answer is correct |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | Response status |
| `latency_ms` | INTEGER | | Response time in milliseconds |
| `input_tokens` | INTEGER | | Tokens in request |
| `output_tokens` | INTEGER | | Tokens in response |
| `reasoning_tokens` | INTEGER | | Tokens used for reasoning |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Response timestamp |

**Status Values:**
- `pending` - Response not yet received
- `success` - Response received successfully
- `error` - Error occurred during request
- `unsupported` - Model doesn't support this question type

**Indexes:**
- `idx_responses_run` - Fast lookup by run
- `idx_responses_question` - Fast lookup by question
- `idx_responses_model` - Fast lookup by model
- `idx_responses_run_iteration` - Composite index for (run_id, iteration)
- `idx_responses_model_correct` - Composite index for accuracy analysis

**Usage:**
- One row per model per question per iteration
- Iteration is a field (not a separate table)
- Token metrics stored separately for analysis

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

---

## Migration Notes

This schema (v2.0) is a complete redesign. Key changes from v1.x:

| Change | Reason |
|--------|--------|
| Added `experiments` table | Experiment tracking with frozen config |
| Added `questions` table | Question persistence for reproducibility |
| Removed `iterations` table | Iteration as field in `responses` |
| Removed `operational_logs` table | Logs written to files only |
| Changed `runs.config` to `runs.experiment_id` | Normalized experiment reference |
| Added `runs.is_dev` flag | Explicit dev mode tracking |
| Renamed `models.metadata` to `models.metadata_json` | Naming consistency |
| Removed `models.context_length`, `max_completion_tokens` | Moved to metadata_json |
| Changed `responses.iteration_id` to `responses.iteration` | Direct field, no join |
| Removed `responses.question_text`, `options_json` | Reference questions table |

**Note**: No migration path is provided. Databases should be recreated from scratch.
