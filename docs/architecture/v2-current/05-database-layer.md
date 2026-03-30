# Database Layer — V2 Current State

**Document Type:** Current State Analysis
**Domain:** Database Layer
**Source:** `src/db/` directory, `docs/architecture/to-be/schema.sql`
**Purpose:** Document what actually exists in V2 implementation

---

## 1. Domain Overview

### 1.1 What Exists in V2

The V2 Database Layer implements the TO-BE architecture with the following components:

| Component | Status | Location |
|-----------|--------|----------|
| Schema Definition | ✅ Implemented | `docs/architecture/to-be/schema.sql`, `src/db/schema.py` |
| Entity Models | ✅ Implemented | `src/db/models.py` |
| Repository Layer | ✅ Implemented | `src/db/repository.py` |
| Connection Management | ⚠️ Partial | Not explicitly implemented (direct SQLite) |

### 1.2 Architectural Alignment

V2 follows the TO-BE architecture principles:

- ✅ **Append-only results** — `responses` and `errors` tables are append-only
- ✅ **Immutable identity** — Experiments, variants, snapshots are immutable after creation
- ✅ **Auditable by design** — All tables have `created_at` timestamps
- ✅ **Explicit schema** — Schema defined in SQL file and Python code
- ✅ **Foreign keys enabled** — Referential integrity enforced

---

## 2. Current Schema (6 Tables)

### 2.1 Tables Overview

V2 Database contains **6 tables**:

| Table | Purpose | Immutability |
|-------|---------|--------------|
| `experiments` | Frozen experiment definitions | Immutable after creation |
| `model_variants` | Model configurations within experiments | Immutable after creation |
| `question_snapshots` | Immutable question copies | Immutable after creation |
| `runs` | Execution instances | Immutable config, mutable status |
| `responses` | Model response results | Append-only (idempotent writes) |
| `errors` | Execution errors | Append-only |

**Note**: V2 removed the `models` table (base model registry). Model variants now reference `model_id` as a string identifier without a foreign key to a models table.

---

### 2.2 experiments Table

**Purpose**: Store experiment definitions with frozen configuration.

**Columns**:
```sql
experiment_id     TEXT PRIMARY KEY
name              TEXT UNIQUE NOT NULL
description       TEXT
config_json       TEXT NOT NULL
config_hash       TEXT NOT NULL
created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Constraints**:
- PRIMARY KEY: `experiment_id`
- UNIQUE: `name`
- NOT NULL: `name`, `config_json`, `config_hash`

**V2 Entity Model**:
```python
@dataclass
class Experiment:
    experiment_id: str
    name: str
    description: str | None = None
    config_json: str = "{}"
    config_hash: str = ""
    created_at: str | None = None
```

**Repository Methods**:
- `save(experiment)` — Insert or update (idempotent)
- `get_by_id(experiment_id)` — Get by primary key
- `get_by_name(name)` — Get by unique name
- `list_all()` — List all experiments
- `delete(experiment_id)` — Hard delete (CASCADEs to related data)

---

### 2.3 model_variants Table

**Purpose**: Store model variant configurations within experiments.

**Columns**:
```sql
variant_id        TEXT PRIMARY KEY
experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id)
model_id          TEXT NOT NULL
variant_signature TEXT NOT NULL
config            TEXT NOT NULL
created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP

UNIQUE(experiment_id, variant_signature)
```

**Constraints**:
- PRIMARY KEY: `variant_id`
- FOREIGN KEY: `experiment_id` → `experiments(experiment_id)` with CASCADE delete
- UNIQUE: `(experiment_id, variant_signature)` — Prevent duplicate variants
- NOT NULL: `experiment_id`, `model_id`, `variant_signature`, `config`

**Indexes**:
- `idx_variants_by_experiment` — Fast lookup by experiment

**V2 Entity Model**:
```python
@dataclass
class ModelVariant:
    variant_id: str
    experiment_id: str
    model_id: str
    variant_signature: str
    config: str = "{}"
    created_at: str | None = None
```

**Repository Methods**:
- `save(variant)` — Insert or update (idempotent)
- `get_by_id(variant_id)` — Get by primary key
- `get_by_signature(experiment_id, signature)` — Get by signature within experiment
- `list_by_experiment(experiment_id)` — List variants for an experiment
- `delete(variant_id)` — Hard delete

**Variant Signature Format**:
```
{model_id}::reasoning={mode}::vision={true|false}::structured={true|false}
```

---

### 2.4 question_snapshots Table

**Purpose**: Store immutable question snapshots within experiments.

**Columns**:
```sql
snapshot_id       TEXT PRIMARY KEY
experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id)
json_question_id  TEXT NOT NULL
question_position INTEGER NOT NULL
question_payload  TEXT NOT NULL
created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP

UNIQUE(experiment_id, question_position)
```

**Constraints**:
- PRIMARY KEY: `snapshot_id`
- FOREIGN KEY: `experiment_id` → `experiments(experiment_id)` with CASCADE delete
- UNIQUE: `(experiment_id, question_position)` — Prevent duplicate positions
- NOT NULL: `experiment_id`, `json_question_id`, `question_position`, `question_payload`

**Indexes**:
- `idx_snapshots_by_experiment` — Fast lookup by experiment

**V2 Entity Model**:
```python
@dataclass
class QuestionSnapshot:
    snapshot_id: str
    experiment_id: str
    json_question_id: str
    question_position: int
    question_payload: str
    created_at: str | None = None
```

**Repository Methods**:
- `save(snapshot)` — Insert or update (idempotent)
- `get_by_id(snapshot_id)` — Get by primary key
- `get_by_experiment_and_question(experiment_id, json_question_id)` — Get by experiment and question ID
- `list_by_experiment(experiment_id)` — List snapshots for an experiment
- `delete(snapshot_id)` — Hard delete

**Key Changes from V1**:
- `json_question_id` — Original dataset ID (e.g., "Q001")
- `question_position` — 1-based position in file (user-facing)
- `question_payload` — Complete question JSON (stem, options, answer_key, meta)

---

### 2.5 runs Table

**Purpose**: Store run definitions (execution instances of experiments).

**Columns**:
```sql
run_id            TEXT PRIMARY KEY
experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id)
config            TEXT NOT NULL
status            TEXT NOT NULL DEFAULT 'pending'
duration          INTEGER DEFAULT 0
created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP

CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
```

**Constraints**:
- PRIMARY KEY: `run_id`
- FOREIGN KEY: `experiment_id` → `experiments(experiment_id)` with CASCADE delete
- CHECK: `status IN ('pending', 'running', 'completed', 'failed', 'partial_failed')`
- NOT NULL: `experiment_id`, `config`, `status`

**Indexes**:
- `idx_runs_by_experiment` — Fast lookup by experiment
- `idx_runs_pending` — **PARTIAL INDEX** for pending runs

**Partial Index**:
```sql
CREATE INDEX IF NOT EXISTS idx_runs_pending ON runs(status) WHERE status = 'pending';
```

**V2 Entity Model**:
```python
@dataclass
class Run:
    run_id: str
    experiment_id: str
    config: str = "{}"
    status: str = "pending"
    duration: int = 0
    created_at: str | None = None
```

**Repository Methods**:
- `save(run, config)` — Insert or update (config serialized to JSON)
- `get_by_id(run_id)` — Get by primary key
- `list_by_experiment(experiment_id)` — List runs for an experiment
- `list_pending()` — List all pending runs (uses partial index)
- `update_status(run_id, status)` — Update run status
- `delete(run_id)` — Hard delete

**Config Keys** (3 run-level keys):
- `seed` — Random seed for reproducibility
- `system_prompt` — Effective system prompt
- `user_prompt` — Effective user prompt

---

### 2.6 responses Table

**Purpose**: Store model response results for each (run, variant, snapshot) combination.

**Columns**:
```sql
response_id       TEXT PRIMARY KEY
run_id            TEXT NOT NULL REFERENCES runs(run_id)
variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id)
snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id)
model_id          TEXT NOT NULL
question_id       TEXT NOT NULL
status            TEXT
finish_reason     TEXT
error_details     TEXT
response_text     TEXT
selected_answer   TEXT
is_correct        BOOLEAN
parse_confidence  TEXT DEFAULT 'unknown'
review_status     TEXT
manual_answer     TEXT
raw_response      TEXT
cost              REAL
input_tokens      INTEGER
response_tokens   INTEGER
reasoning_tokens  INTEGER
effective_tokens  INTEGER
latency_ms        INTEGER
started_at        TIMESTAMP
finished_at       TIMESTAMP

UNIQUE(run_id, variant_id, snapshot_id)
```

**Constraints**:
- PRIMARY KEY: `response_id`
- FOREIGN KEY: `run_id` → `runs(run_id)` with CASCADE delete
- FOREIGN KEY: `variant_id` → `model_variants(variant_id)` with RESTRICT delete
- FOREIGN KEY: `snapshot_id` → `question_snapshots(snapshot_id)` with RESTRICT delete
- UNIQUE: `(run_id, variant_id, snapshot_id)` — Idempotency key
- NOT NULL: `run_id`, `variant_id`, `snapshot_id`, `model_id`, `question_id`

**Indexes**:
- `idx_responses_by_run` — Fast lookup by run
- `idx_responses_needs_review` — **PARTIAL INDEX** for review queue

**Partial Index**:
```sql
CREATE INDEX IF NOT EXISTS idx_responses_needs_review ON responses(review_status) WHERE review_status = 'needs_review';
```

**V2 Entity Model**:
```python
@dataclass
class Response:
    response_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    model_id: str
    question_id: str
    status: str | None = None
    finish_reason: str | None = None
    error_details: str | None = None
    response_text: str | None = None
    selected_answer: str | None = None
    is_correct: bool | None = None
    parse_confidence: str = "unknown"
    review_status: str | None = None
    manual_answer: str | None = None
    raw_response: str | None = None
    cost: float | None = None
    input_tokens: int | None = None
    response_tokens: int | None = None
    reasoning_tokens: int | None = None
    effective_tokens: int | None = None
    latency_ms: int | None = None
    started_at: str | None = None
    finished_at: str | None = None
```

**Repository Methods**:
- `save(response)` — Insert or update (calculates `effective_tokens`)
- `get_by_id(response_id)` — Get by primary key
- `list_by_run(run_id)` — List responses for a run
- `list_needs_review()` — List all responses needing review (uses partial index)
- `update_manual_answer(response_id, manual_answer)` — Update manual review

**Review Fields Contract**:
| Field | Purpose | Set By |
|-------|---------|--------|
| `parse_confidence` | Parser confidence level | ExecutionEngine |
| `selected_answer` | Parsed answer (A/B/C/D) | ExecutionEngine |
| `review_status` | Manual review flag | **ResultWriter** (calculated) |
| `manual_answer` | Human-corrected answer | Reviewer (post-execution) |

**Review Status Calculation** (by ResultWriter):
```
needs_review = TRUE if (parse_confidence != 'clear' OR selected_answer IS NULL)
review_status = 'needs_review' if needs_review else 'auto'
```

**Token Calculation** (by ResponseRepository):
```python
effective_tokens = input_tokens + response_tokens + reasoning_tokens
```

---

### 2.7 errors Table

**Purpose**: Store execution errors for failed model invocations.

**Columns**:
```sql
error_id          TEXT PRIMARY KEY
run_id            TEXT NOT NULL REFERENCES runs(run_id)
variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id)
snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id)
question_id       TEXT NOT NULL
error_type        TEXT NOT NULL
error_message     TEXT NOT NULL
attempt_count     INTEGER NOT NULL DEFAULT 1
stack_trace       TEXT
occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Constraints**:
- PRIMARY KEY: `error_id`
- FOREIGN KEY: `run_id` → `runs(run_id)` with CASCADE delete
- FOREIGN KEY: `variant_id` → `model_variants(variant_id)` with RESTRICT delete
- FOREIGN KEY: `snapshot_id` → `question_snapshots(snapshot_id)` with RESTRICT delete
- NOT NULL: `run_id`, `variant_id`, `snapshot_id`, `question_id`, `error_type`, `error_message`, `attempt_count`

**Indexes**:
- `idx_errors_by_run` — Fast lookup by run

**V2 Entity Model**:
```python
@dataclass
class Error:
    error_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    question_id: str
    error_type: str
    error_message: str
    attempt_count: int = 1
    stack_trace: str | None = None
    occurred_at: str | None = None
```

**Repository Methods**:
- `save(error)` — Insert or update (idempotent)
- `get_by_id(error_id)` — Get by primary key
- `list_by_run(run_id)` — List errors for a run

**Error Types**:
- `api_error` — API call failures
- `timeout` — Request timeout
- `parse_error` — Response parsing failures
- `config_error` — Configuration validation failures

---

## 3. Constraints Summary

### 3.1 Primary Keys

| Table | Primary Key | Format |
|-------|-------------|--------|
| `experiments` | `experiment_id` | TEXT (UUID recommended: `exp_XXXXXXXX`) |
| `model_variants` | `variant_id` | TEXT (UUID recommended: `var_XXXXXXXX`) |
| `question_snapshots` | `snapshot_id` | TEXT (UUID recommended: `snap_XXXXXXXX`) |
| `runs` | `run_id` | TEXT (UUID recommended: `run_XXXXXXXX`) |
| `responses` | `response_id` | TEXT (UUID recommended: `resp_XXXXXXXX`) |
| `errors` | `error_id` | TEXT (UUID recommended: `err_XXXXXXXX`) |

### 3.2 Foreign Keys

| From Table | To Table | On Delete | On Update |
|------------|----------|-----------|-----------|
| `model_variants.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION |
| `question_snapshots.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION |
| `runs.experiment_id` | `experiments.experiment_id` | CASCADE | NO ACTION |
| `responses.run_id` | `runs.run_id` | CASCADE | NO ACTION |
| `responses.variant_id` | `model_variants.variant_id` | RESTRICT | NO ACTION |
| `responses.snapshot_id` | `question_snapshots.snapshot_id` | RESTRICT | NO ACTION |
| `errors.run_id` | `runs.run_id` | CASCADE | NO ACTION |
| `errors.variant_id` | `model_variants.variant_id` | RESTRICT | NO ACTION |
| `errors.snapshot_id` | `question_snapshots.snapshot_id` | RESTRICT | NO ACTION |

### 3.3 UNIQUE Constraints

| Table | Columns | Purpose |
|-------|---------|---------|
| `experiments` | `name` | Prevent duplicate experiment names |
| `model_variants` | `(experiment_id, variant_signature)` | Prevent duplicate variants within experiment |
| `question_snapshots` | `(experiment_id, question_position)` | Prevent duplicate question positions |
| `responses` | `(run_id, variant_id, snapshot_id)` | Idempotency key (prevent duplicate responses) |

### 3.4 CHECK Constraints

| Table | Constraint | Purpose |
|-------|------------|---------|
| `runs` | `status IN ('pending', 'running', 'completed', 'failed', 'partial_failed')` | Valid status values |

---

## 4. Indexes Summary

### 4.1 Standard Indexes

| Table | Index Name | Columns | Purpose |
|-------|------------|---------|---------|
| `model_variants` | `idx_variants_by_experiment` | `experiment_id` | List variants by experiment |
| `question_snapshots` | `idx_snapshots_by_experiment` | `experiment_id` | List snapshots by experiment |
| `runs` | `idx_runs_by_experiment` | `experiment_id` | List runs by experiment |
| `responses` | `idx_responses_by_run` | `run_id` | List responses by run |
| `errors` | `idx_errors_by_run` | `run_id` | List errors by run |

### 4.2 Partial Indexes

| Table | Index Name | Predicate | Purpose |
|-------|------------|-----------|---------|
| `runs` | `idx_runs_pending` | `status = 'pending'` | Optimize execution queue queries |
| `responses` | `idx_responses_needs_review` | `review_status = 'needs_review'` | Optimize review queue queries |

**Partial Index Benefits**:
- Smaller index size (only indexed rows matching predicate)
- Faster queries for common cases (pending runs, review queue)
- Reduced write overhead (index only updated for matching rows)

---

## 5. Immutability Rules

### 5.1 Immutable Tables

**Fully Immutable** (no updates after creation):
- `experiments` — Frozen experiment definitions
- `model_variants` — Frozen variant configurations
- `question_snapshots` — Frozen question copies

**Implementation**:
- No UPDATE operations in repository layer
- Application-level enforcement (no SQL enforcement)

### 5.2 Mutable Fields

**Partially Mutable** (some fields can change):

| Table | Immutable Fields | Mutable Fields |
|-------|------------------|----------------|
| `runs` | `run_id`, `experiment_id`, `config`, `created_at` | `status`, `duration` |
| `responses` | `response_id`, `run_id`, `variant_id`, `snapshot_id`, `model_id`, `question_id`, `started_at` | `status`, `finish_reason`, `error_details`, `response_text`, `selected_answer`, `is_correct`, `parse_confidence`, `review_status`, `manual_answer`, `raw_response`, `cost`, `tokens`, `latency_ms`, `finished_at` |
| `errors` | All fields except `stack_trace` | `stack_trace` (rarely) |

### 5.3 Append-Only Tables

**Append-Only** (INSERT only, no UPDATE, no DELETE):
- `responses` — Idempotent writes (INSERT OR IGNORE)
- `errors` — Idempotent writes (INSERT OR IGNORE)

**Implementation**:
- UNIQUE constraint prevents duplicates
- INSERT OR IGNORE skips existing records

---

## 6. Implementation Details

### 6.1 Schema Creation

**Approach**: Programmatic schema creation from SQL file and Python code.

**Implementation**:
```python
# src/db/schema.py
def get_schema_sql() -> str:
    return """
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS experiments (...);
    CREATE TABLE IF NOT EXISTS model_variants (...);
    ...
    """

def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(get_schema_sql())
    conn.commit()
```

### 6.2 Repository Pattern

**Implementation**: All repositories in `src/db/repository.py`

**Common Pattern**:
```python
class ExperimentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def save(self, experiment: Experiment) -> None:
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO experiments (...)
            VALUES (?, ?, ?, ?, ?)
        """, (...))
        self.conn.commit()
```

**Repositories**:
- `ExperimentRepository` — CRUD for experiments
- `VariantRepository` — CRUD for model variants
- `SnapshotRepository` — CRUD for question snapshots
- `RunRepository` — CRUD for runs
- `ResponseRepository` — CRUD for responses
- `ErrorRepository` — CRUD for errors

### 6.3 Connection Management

**Current State**: Direct SQLite connections (no centralized manager).

**Usage Pattern**:
```python
import sqlite3

conn = sqlite3.connect("data/benchmark.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")

# Use connection with repositories
experiment_repo = ExperimentRepository(conn)
```

**Gap**: No `DatabaseManager` class like V1 (connection lifecycle not centralized).

---

## 7. Known Gaps

### 7.1 Connection Management (MEDIUM)

**V1 Behavior**:
- `DatabaseManager` class handles connection lifecycle
- Automatic foreign key enablement
- Row factory configuration
- In-memory vs file database detection

**V2 Status**:
- ❌ No centralized connection manager
- ❌ Manual connection setup in each caller
- ❌ No in-memory database support

**Impact**:
- Code duplication (connection setup)
- Risk of forgetting `PRAGMA foreign_keys = ON`
- Harder to test (no in-memory support)

---

### 7.2 Soft Delete Not Implemented (LOW)

**V1 Behavior**:
- Hard delete only (no `is_active` column)

**V2 Status**:
- ✅ Consistent with V1 (hard delete only)
- ✅ No `is_active` columns (as per TO-BE architecture)

**Note**: This is intentional per TO-BE architecture — no soft delete.

---

## 8. Summary

### 8.1 V2 Database Layer Summary

**Implemented** (✅):
- 6 tables with correct structure
- All constraints (PK, FK, UNIQUE, CHECK)
- All indexes (including partial indexes)
- Repository pattern for all entities
- Entity models matching schema

**Alignment with TO-BE**:
- ✅ Append-only results
- ✅ Immutable identity (experiments, variants, snapshots)
- ✅ Auditable (all tables have `created_at`)
- ✅ Foreign keys enabled
- ✅ Idempotency (UNIQUE constraints)
- ✅ Partial indexes for performance

**Gaps**:
- ⚠️ No centralized connection manager
- ⚠️ No in-memory database support

### 8.2 Key Features

**Immutability**:
- `experiments` — Immutable after creation
- `model_variants` — Immutable after creation
- `question_snapshots` — Immutable after creation
- `runs` — Immutable config, mutable status
- `responses` — Append-only (idempotent writes)
- `errors` — Append-only

**Partial Indexes**:
- `idx_runs_pending` — Optimizes execution queue
- `idx_responses_needs_review` — Optimizes review queue

**Idempotency**:
- `UNIQUE(run_id, variant_id, snapshot_id)` on `responses`
- Prevents duplicate responses

**Audit Trail**:
- All tables have `created_at`
- `responses` has `started_at`, `finished_at`
- `errors` has `occurred_at`

This document captures the current state of V2 Database Layer implementation without proposing fixes.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Source**: `src/db/` directory, `docs/architecture/to-be/schema.sql`
