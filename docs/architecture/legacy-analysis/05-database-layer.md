# Database Layer — V1 Legacy Analysis

**Document Type:** Legacy Analysis (Read-Only)
**Domain:** Database Layer
**Source:** `src_legacy/db/` directory
**Purpose:** Extract architectural concepts from V1 implementation for historical reference

---

## 1. Domain Overview

### 1.1 Purpose

The Database Layer provides persistent storage for benchmark experiments, model configurations, question snapshots, execution runs, and results. It ensures data integrity, reproducibility, and auditability through a well-defined schema and access patterns.

### 1.2 Core Responsibilities

- **Schema Management**: Define and maintain database tables, indexes, and constraints
- **Connection Management**: Handle SQLite connections with proper lifecycle
- **Data Access**: Provide CRUD operations for all entities
- **Data Integrity**: Enforce constraints (PK, FK, UNIQUE, CHECK)
- **Immutability**: Support append-only patterns for results
- **Idempotency**: Prevent duplicate writes through unique constraints

### 1.3 Design Principles

1. **Explicit Schema**: Schema defined in SQL file, loaded programmatically
2. **Foreign Keys**: Enabled for referential integrity
3. **Immutability**: Snapshots and results are append-only
4. **Auditability**: All tables have `created_at` timestamps
5. **Idempotency**: Unique constraints prevent duplicates

---

## 2. Schema Structure

### 2.1 Tables Overview

V1 Database contains **7 tables**:

| Table | Purpose | Immutability |
|-------|---------|--------------|
| `experiments` | Experiment definitions with frozen config | Immutable after creation |
| `models` | Base model registry | Mutable (canonical catalog) |
| `model_variants` | Model variant configurations | Mutable |
| `runs` | Execution instances | Mutable status |
| `question_snapshots` | Immutable question copies | Immutable after creation |
| `responses` | Model response results | Append-only |
| `errors` | Execution failures | Append-only |

### 2.2 experiments Table

**Purpose**: Store experiment definitions with frozen configuration and global defaults.

**Columns**:
```sql
experiment_id              TEXT PRIMARY KEY
name                       TEXT NOT NULL UNIQUE
description                TEXT

-- Global defaults (INTENTIONAL)
default_temperature        REAL
default_top_p              REAL
default_max_output_tokens  INTEGER
default_reasoning_mode     TEXT
default_reasoning_effort   TEXT

-- Prompt templates
system_prompt_template     TEXT
user_prompt_template       TEXT

-- Audit
config_json                TEXT NOT NULL
config_hash                TEXT NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Constraints**:
- PRIMARY KEY: `experiment_id`
- UNIQUE: `name`
- NOT NULL: `name`, `config_json`, `config_hash`

**Indexes**:
- `idx_experiments_name` — Fast lookup by name
- `idx_experiments_hash` — Deduplication check

---

### 2.3 models Table

**Purpose**: Canonical catalog of base models (can be updated without affecting results).

**Columns**:
```sql
model_id                   TEXT PRIMARY KEY
provider                   TEXT NOT NULL
model_name                 TEXT NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Constraints**:
- PRIMARY KEY: `model_id`
- NOT NULL: `provider`, `model_name`

**Note**: This table is the CANONICAL CATALOG — models can be updated here without affecting existing experiment results.

---

### 2.4 model_variants Table

**Purpose**: Intentional model variant configurations (identity-defining).

**Columns**:
```sql
variant_id                 TEXT PRIMARY KEY
model_id                   TEXT NOT NULL

-- Identity (INTENT)
reasoning_mode             TEXT
reasoning_effort           TEXT
vision_enabled             BOOLEAN NOT NULL
structured_output          BOOLEAN NOT NULL
web_access_enabled         BOOLEAN NOT NULL

-- Optional intentional parameters
temperature                REAL
top_p                      REAL
max_output_tokens          INTEGER

-- Audit
variant_signature          TEXT NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Constraints**:
- PRIMARY KEY: `variant_id`
- FOREIGN KEY: `model_id` → `models(model_id)` (implicit)
- NOT NULL: `model_id`, `variant_signature`, `vision_enabled`, `structured_output`, `web_access_enabled`

**Indexes**:
- `idx_model_variants_model` — Fast lookup by base model
- `idx_model_variants_signature` — UNIQUE index on `variant_signature`

**Identity Fields** (define `variant_signature`):
- `reasoning_mode`: 'off', 'auto', 'effort', 'budget', 'unspecified'
- `reasoning_effort`: 'xhigh', 'high', 'medium', 'low', 'minimal' (when mode='effort')
- `max_output_tokens`: integer (when mode='budget')
- `vision_enabled`: boolean
- `structured_output`: boolean
- `web_access_enabled`: boolean

**Non-Identity Fields** (NOT part of signature):
- `temperature`, `top_p`, `max_tokens`, `repeat_penalty`

---

### 2.5 runs Table

**Purpose**: Concrete execution unit (no iterations — replaced by multiple runs).

**Columns**:
```sql
run_id                     TEXT PRIMARY KEY
experiment_id              TEXT NOT NULL

-- Optional grouping (replaces iteration)
run_group_id               TEXT

-- Effective configuration
seed                       INTEGER
system_prompt              TEXT
user_prompt                TEXT

-- State
status                     TEXT NOT NULL
started_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
finished_at                TIMESTAMP

-- Metadata
created_by                 TEXT
notes                      TEXT

FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
```

**Constraints**:
- PRIMARY KEY: `run_id`
- FOREIGN KEY: `experiment_id` → `experiments(experiment_id)` with CASCADE delete
- NOT NULL: `experiment_id`, `status`

**Indexes**:
- `idx_runs_experiment` — Fast lookup by experiment
- `idx_runs_group` — Grouping by `run_group_id`
- `idx_runs_status` — Status-based queries

**Status Values**: `pending`, `running`, `completed`, `failed`

---

### 2.6 question_snapshots Table

**Purpose**: Immutable executable questions (snapshotted per experiment).

**Columns**:
```sql
snapshot_id                TEXT PRIMARY KEY
experiment_id              TEXT NOT NULL
question_id                TEXT NOT NULL
question_payload           TEXT NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP

FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE
```

**Constraints**:
- PRIMARY KEY: `snapshot_id`
- FOREIGN KEY: `experiment_id` → `experiments(experiment_id)` with CASCADE delete
- NOT NULL: `experiment_id`, `question_id`, `question_payload`

**Indexes**:
- `idx_question_snapshots_experiment` — Fast lookup by experiment
- `idx_question_snapshots_question` — Fast lookup by question ID

**Immutability**: Snapshots are created once and never modified.

---

### 2.7 responses Table

**Purpose**: Successful or valid model executions (append-only).

**Columns**:
```sql
response_id                TEXT PRIMARY KEY
run_id                     TEXT NOT NULL
variant_id                 TEXT NOT NULL
snapshot_id                TEXT NOT NULL

-- Reference
model_id                   TEXT NOT NULL
question_id                TEXT NOT NULL

-- Result
response_text              TEXT
selected_answer            TEXT
is_correct                 BOOLEAN
finish_reason              TEXT

-- Performance
latency_ms                 INTEGER
input_tokens               INTEGER
output_tokens              INTEGER
total_tokens               INTEGER
cost                       REAL

-- Audit (always present)
provider_model_resolved    TEXT
parse_confidence           TEXT DEFAULT 'unknown'
needs_review               BOOLEAN NOT NULL DEFAULT FALSE
manual_answer              TEXT

-- Optional debug/audit
provider_parameters_effective TEXT
provider_thinking_level    TEXT
provider_debug_payload     TEXT

-- State
status                     TEXT NOT NULL DEFAULT 'success'
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP

FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT
```

**Constraints**:
- PRIMARY KEY: `response_id`
- FOREIGN KEY: `run_id` → `runs(run_id)` with CASCADE delete
- FOREIGN KEY: `variant_id` → `model_variants(variant_id)` with RESTRICT delete
- FOREIGN KEY: `snapshot_id` → `question_snapshots(snapshot_id)` with RESTRICT delete
- UNIQUE: `(run_id, variant_id, snapshot_id)` — Idempotency key
- NOT NULL: `run_id`, `variant_id`, `snapshot_id`, `model_id`, `question_id`, `status`, `needs_review`

**Indexes**:
- `idx_responses_unique` — UNIQUE composite index for idempotency
- `idx_responses_run` — Fast lookup by run
- `idx_responses_variant` — Fast lookup by variant
- `idx_responses_snapshot` — Fast lookup by snapshot
- `idx_responses_needs_review` — PARTIAL index for review queue

**Partial Index**:
```sql
CREATE INDEX IF NOT EXISTS idx_responses_needs_review
    ON responses(needs_review)
    WHERE needs_review = TRUE;
```

**Review Field Calculation**:
```
needs_review = TRUE if (
    parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

---

### 2.8 errors Table

**Purpose**: Technical execution failures (observational, append-only).

**Columns**:
```sql
error_id                   TEXT PRIMARY KEY
run_id                     TEXT NOT NULL
variant_id                 TEXT NOT NULL
snapshot_id                TEXT NOT NULL

-- Reference
model_id                   TEXT NOT NULL
question_id                TEXT NOT NULL

-- Classification
error_type                 TEXT NOT NULL
error_code                 TEXT
error_message              TEXT NOT NULL

-- Technical details
stack_trace                TEXT
attempt_count              INTEGER NOT NULL
is_retryable               BOOLEAN NOT NULL

-- Audit
provider_model_resolved    TEXT
provider_error_payload     TEXT

created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP

FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT
```

**Constraints**:
- PRIMARY KEY: `error_id`
- FOREIGN KEY: `run_id` → `runs(run_id)` with CASCADE delete
- FOREIGN KEY: `variant_id` → `model_variants(variant_id)` with RESTRICT delete
- FOREIGN KEY: `snapshot_id` → `question_snapshots(snapshot_id)` with RESTRICT delete
- NOT NULL: `run_id`, `variant_id`, `snapshot_id`, `model_id`, `question_id`, `error_type`, `error_message`, `attempt_count`, `is_retryable`

**Indexes**:
- `idx_errors_run` — Fast lookup by run
- `idx_errors_variant` — Fast lookup by variant
- `idx_errors_type` — Fast lookup by error type

---

## 3. Entity Relationships

### 3.1 ER Diagram

```
experiments (1) ──────< (N) runs
    │                       │
    │                       │
    │                       │
    └──────< (N) model_variants
                    │
                    │
                    │
                    └──────< (N) responses
                    │            │
                    │            │
    └──────< (N) question_snapshots ──┘
```

### 3.2 Relationship Rules

**experiments → runs** (1:N):
- Cascade delete: Deleting experiment deletes all runs
- Runs cannot exist without an experiment

**experiments → model_variants** (1:N):
- Variants belong to experiments (not global)
- No explicit FK in V1 schema (implicit relationship)

**experiments → question_snapshots** (1:N):
- Cascade delete: Deleting experiment deletes all snapshots
- Snapshots MUST have `experiment_id` (no NULL support)

**runs → responses** (1:N):
- Cascade delete: Deleting run deletes all responses
- Responses reference both `run_id` and `variant_id`

**model_variants → responses** (1:N):
- RESTRICT delete: Cannot delete variant with responses
- Protects historical data integrity

**question_snapshots → responses** (1:N):
- RESTRICT delete: Cannot delete snapshot with responses
- Protects historical data integrity

---

## 4. Indexes and Performance

### 4.1 Index Coverage

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `experiments` | `idx_experiments_name` | Standard | Fast lookup by name |
| `experiments` | `idx_experiments_hash` | Standard | Deduplication check |
| `model_variants` | `idx_model_variants_model` | Standard | Lookup by base model |
| `model_variants` | `idx_model_variants_signature` | UNIQUE | Prevent duplicate variants |
| `runs` | `idx_runs_experiment` | Standard | List runs by experiment |
| `runs` | `idx_runs_group` | Standard | Grouping queries |
| `runs` | `idx_runs_status` | Standard | Status-based queries |
| `question_snapshots` | `idx_question_snapshots_experiment` | Standard | List snapshots by experiment |
| `question_snapshots` | `idx_question_snapshots_question` | Standard | Lookup by question ID |
| `responses` | `idx_responses_unique` | UNIQUE | Idempotency constraint |
| `responses` | `idx_responses_run` | Standard | List responses by run |
| `responses` | `idx_responses_variant` | Standard | List responses by variant |
| `responses` | `idx_responses_snapshot` | Standard | List responses by snapshot |
| `responses` | `idx_responses_needs_review` | **PARTIAL** | Review queue optimization |
| `errors` | `idx_errors_run` | Standard | List errors by run |
| `errors` | `idx_errors_variant` | Standard | List errors by variant |
| `errors` | `idx_errors_type` | Standard | Error type analysis |

### 4.2 Partial Indexes

**`idx_responses_needs_review`**:
```sql
CREATE INDEX IF NOT EXISTS idx_responses_needs_review
    ON responses(needs_review)
    WHERE needs_review = TRUE;
```

**Purpose**: Optimizes review queue queries by indexing only rows that need review.

**Benefit**: Smaller index size, faster queries for the common case (reviewing flagged responses).

---

## 5. Migration Patterns

### 5.1 Schema Creation

**Approach**: Programmatic schema creation from SQL file.

**Implementation**:
```python
def get_schema_sql() -> str:
    schema_path = Path(__file__).parent / "schema.sql"
    return schema_path.read_text(encoding="utf-8")

def initialize(self) -> None:
    conn = self.get_connection()
    cursor = conn.cursor()
    schema_sql = get_schema_sql()
    cursor.executescript(schema_sql)
    conn.commit()
```

### 5.2 Connection Management

**DatabaseManager** class handles:
- File vs in-memory database detection
- Connection reuse for in-memory databases
- Thread-safe connections for file databases
- Foreign key enablement (`PRAGMA foreign_keys = ON`)
- Row factory configuration (`sqlite3.Row`)

### 5.3 Data Access Pattern

**Repository Pattern** (partial implementation):
- `ExperimentRepository` — CRUD for experiments
- `VariantRepository` — CRUD for model variants
- `SnapshotRepository` — CRUD for question snapshots
- `RunRepository` — CRUD for runs
- `ResponseRepository` — CRUD for responses
- `ErrorRepository` — CRUD for errors

**Common Methods**:
- `save(entity)` — Insert or update (idempotent)
- `get_by_id(id)` — Get by primary key
- `list_all()` or `list_by_experiment(id)` — List entities
- `delete(id)` — Hard delete (no soft delete in V1)

---

## 6. Data Access Patterns

### 6.1 Read Patterns

**Common Queries**:

1. **List experiments**:
   ```sql
   SELECT * FROM experiments ORDER BY created_at DESC
   ```

2. **List runs by experiment**:
   ```sql
   SELECT * FROM runs WHERE experiment_id = ? ORDER BY created_at ASC
   ```

3. **List pending runs** (uses partial index):
   ```sql
   SELECT * FROM runs WHERE status = 'pending' ORDER BY created_at ASC
   ```

4. **List responses by run**:
   ```sql
   SELECT * FROM responses WHERE run_id = ? ORDER BY started_at ASC
   ```

5. **List responses needing review** (uses partial index):
   ```sql
   SELECT * FROM responses WHERE needs_review = TRUE ORDER BY started_at ASC
   ```

6. **List errors by run**:
   ```sql
   SELECT * FROM errors WHERE run_id = ? ORDER BY occurred_at ASC
   ```

### 6.2 Write Patterns

**Idempotent Insert**:
```sql
INSERT OR IGNORE INTO responses (
    response_id, run_id, variant_id, snapshot_id, ...
) VALUES (?, ?, ?, ?, ...)
```

**Status Update**:
```sql
UPDATE runs SET status = ? WHERE run_id = ?
```

**Manual Review Update**:
```sql
UPDATE responses
SET manual_answer = ?, is_correct = ?, review_status = 'reviewed'
WHERE response_id = ?
```

### 6.3 Delete Patterns

**Hard Delete Only** (no soft delete):
- Deleting experiment CASCADEs to runs, responses, errors, snapshots
- RESTRICT prevents deletion of variants/snapshots with responses

---

## 7. Key Design Decisions

### 7.1 Immutability Strategy

**Decision**: Snapshots and results are immutable after creation.

**Rationale**:
- Reproducibility (historical data preserved)
- Auditability (clear execution history)
- Thread safety (immutable objects)

**Implementation**:
- `question_snapshots` — Created once, never updated
- `responses` — Append-only (idempotent writes)
- `errors` — Append-only

### 7.2 Idempotency

**Decision**: ResultWriter is idempotent (same input → same DB state).

**Rationale**:
- Supports partial re-execution
- Prevents data loss from accidental re-runs
- Enables crash recovery

**Implementation**:
- UNIQUE constraint: `(run_id, variant_id, snapshot_id)`
- INSERT OR IGNORE (skip duplicates)

### 7.3 Foreign Key Strategy

**Decision**: Foreign keys enabled with CASCADE/RESTRICT rules.

**Rationale**:
- Referential integrity (no orphaned records)
- Cascade delete for parent entities (experiments, runs)
- RESTRICT delete for historical data protection

**Implementation**:
- `PRAGMA foreign_keys = ON` on every connection
- Explicit FK constraints in schema

### 7.4 Partial Indexes

**Decision**: Use partial indexes for review queue optimization.

**Rationale**:
- Smaller index size (only indexed rows that match predicate)
- Faster queries for common case (reviewing flagged responses)

**Implementation**:
- `idx_responses_needs_review WHERE needs_review = TRUE`

### 7.5 Denormalization

**Decision**: Store `model_id` and `question_id` in `responses` and `errors` tables.

**Rationale**:
- Easier querying (no JOIN needed for common reports)
- Better performance for listing operations
- Semantic redundancy for debugging

**Trade-off**:
- Data duplication (acceptable for query performance)

---

## 8. Summary

The V1 Database Layer was built around these foundational concepts:

1. **Explicit schema** — SQL file loaded programmatically, version-controlled

2. **Immutability** — Snapshots and results are append-only, never modified

3. **Idempotency** — UNIQUE constraints prevent duplicate writes

4. **Referential integrity** — Foreign keys with CASCADE/RESTRICT rules

5. **Auditability** — All tables have `created_at` timestamps

6. **Performance optimization** — Partial indexes for common query patterns

7. **Denormalization** — Strategic redundancy for query performance

8. **Repository pattern** — CRUD operations encapsulated in repository classes

This document captures the architectural essence of V1 without proposing improvements or comparing to V2 implementations.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Source**: `src_legacy/db/` directory
