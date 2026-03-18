-- ============================================================================
-- Benchmark LLM Database Schema (TO-BE)
-- Purpose: Experimental, auditable, reproducible LLM benchmarking
-- Generated: 2026-03-17
-- Version: 1.0 (Clean Architecture)
-- ============================================================================

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: experiments
-- Purpose: Frozen experiment configuration and global defaults
-- ============================================================================

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id              TEXT PRIMARY KEY,
    name                       TEXT NOT NULL UNIQUE,
    description                TEXT,

    -- Global defaults (INTENTIONAL)
    default_temperature        REAL,
    default_top_p              REAL,
    default_max_output_tokens  INTEGER,
    default_reasoning_mode     TEXT,
    default_reasoning_effort   TEXT,

    -- Prompt templates
    system_prompt_template     TEXT,
    user_prompt_template       TEXT,

    -- Audit
    config_json                TEXT NOT NULL,
    config_hash                TEXT NOT NULL,
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experiments_name
    ON experiments(name);

CREATE INDEX IF NOT EXISTS idx_experiments_hash
    ON experiments(config_hash);

-- ============================================================================
-- TABLE: model_variants
-- Purpose: Intentional model variants (identity-defining configuration)
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_variants (
    variant_id                 TEXT PRIMARY KEY,
    model_id                   TEXT NOT NULL,

    -- Identity (INTENT)
    reasoning_mode             TEXT,
    reasoning_effort           TEXT,
    vision_enabled             BOOLEAN NOT NULL,
    structured_output          BOOLEAN NOT NULL,
    web_access_enabled         BOOLEAN NOT NULL,

    -- Optional intentional parameters
    temperature                REAL,
    top_p                      REAL,
    max_output_tokens          INTEGER,

    -- Audit
    variant_signature          TEXT NOT NULL,
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_variants_model
    ON model_variants(model_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_variants_signature
    ON model_variants(variant_signature);

-- ============================================================================
-- TABLE: runs
-- Purpose: Concrete execution unit (no iterations)
-- ============================================================================

CREATE TABLE IF NOT EXISTS runs (
    run_id                     TEXT PRIMARY KEY,
    experiment_id              TEXT NOT NULL,

    -- Optional grouping (replaces iteration)
    run_group_id               TEXT,

    -- Effective configuration
    seed                       INTEGER, # Tornar runs.seed nullable
    system_prompt              TEXT,
    user_prompt                TEXT,

    -- State
    status                     TEXT NOT NULL,
    started_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at                TIMESTAMP,

    -- Metadata
    created_by                 TEXT,
    notes                      TEXT,

    FOREIGN KEY (experiment_id)
        REFERENCES experiments(experiment_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_experiment
    ON runs(experiment_id);

CREATE INDEX IF NOT EXISTS idx_runs_group
    ON runs(run_group_id);

CREATE INDEX IF NOT EXISTS idx_runs_status
    ON runs(status);

-- ============================================================================
-- TABLE: question_snapshots
-- Purpose: Immutable executable questions
-- ============================================================================

CREATE TABLE IF NOT EXISTS question_snapshots (
    snapshot_id                TEXT PRIMARY KEY,
    experiment_id              TEXT NOT NULL,
    question_id                TEXT NOT NULL,
    question_payload           TEXT NOT NULL,
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (experiment_id)
        REFERENCES experiments(experiment_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_question_snapshots_experiment
    ON question_snapshots(experiment_id);

CREATE INDEX IF NOT EXISTS idx_question_snapshots_question
    ON question_snapshots(question_id);

-- ============================================================================
-- TABLE: responses
-- Purpose: Successful or valid model executions
-- ============================================================================

CREATE TABLE IF NOT EXISTS responses (
    response_id                TEXT PRIMARY KEY,
    run_id                     TEXT NOT NULL,
    variant_id                 TEXT NOT NULL,
    snapshot_id                TEXT NOT NULL,

    -- Reference
    model_id                   TEXT NOT NULL,
    question_id                TEXT NOT NULL,

    -- Result
    response_text              TEXT,
    selected_answer            TEXT,
    is_correct                 BOOLEAN,
    finish_reason              TEXT,

    -- Performance
    latency_ms                 INTEGER,
    input_tokens               INTEGER,
    output_tokens              INTEGER,
    total_tokens               INTEGER,
    cost                        REAL,

    -- Audit (always present)
    provider_model_resolved    TEXT NOT NULL,

    -- Optional debug/audit
    provider_parameters_effective TEXT,
    provider_thinking_level    TEXT,
    provider_debug_payload     TEXT,

    -- State
    status                     TEXT NOT NULL DEFAULT 'success', # Nunca usar responses.status para controle de fluxo.
    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES runs(run_id)
        ON DELETE CASCADE,

    FOREIGN KEY (variant_id)
        REFERENCES model_variants(variant_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (snapshot_id)
        REFERENCES question_snapshots(snapshot_id)
        ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_responses_unique
    ON responses(run_id, variant_id, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_responses_run
    ON responses(run_id);

CREATE INDEX IF NOT EXISTS idx_responses_variant
    ON responses(variant_id);

CREATE INDEX IF NOT EXISTS idx_responses_snapshot
    ON responses(snapshot_id);

-- ============================================================================
-- TABLE: errors
-- Purpose: Technical execution failures (observational)
-- ============================================================================

CREATE TABLE IF NOT EXISTS errors (
    error_id                   TEXT PRIMARY KEY,
    run_id                     TEXT NOT NULL,
    variant_id                 TEXT NOT NULL,
    snapshot_id                TEXT NOT NULL,

    -- Reference
    model_id                   TEXT NOT NULL,
    question_id                TEXT NOT NULL,

    -- Classification
    error_type                 TEXT NOT NULL,
    error_code                 TEXT,
    error_message              TEXT NOT NULL,

    -- Technical details
    stack_trace                TEXT,
    attempt_count              INTEGER NOT NULL,
    is_retryable               BOOLEAN NOT NULL,

    -- Audit
    provider_model_resolved    TEXT, # Precisa ainda ser definido claramente. Em responses ele é NOT NULL, em errors é opcional. Isso faz sentido se: - houver falhas antes da chamada ao provider. Se não, você pode padronizar como NOT NULL.
    provider_error_payload     TEXT,

    created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (run_id)
        REFERENCES runs(run_id)
        ON DELETE CASCADE,

    FOREIGN KEY (variant_id)
        REFERENCES model_variants(variant_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (snapshot_id)
        REFERENCES question_snapshots(snapshot_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_errors_run
    ON errors(run_id);

CREATE INDEX IF NOT EXISTS idx_errors_variant
    ON errors(variant_id);

CREATE INDEX IF NOT EXISTS idx_errors_type
    ON errors(error_type);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================