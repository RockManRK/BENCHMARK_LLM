-- Benchmark LLM Database Schema
-- This schema defines the structure for storing benchmark experiments, runs, and responses.
-- Generated: 2026-03-14
-- Version: 4 (Model Variants System - Fixed Order)

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TABLE: experiments
-- Purpose: Store experiment configurations with frozen, immutable snapshots.
--          Each experiment represents a specific research question or benchmark
--          configuration that can be reproduced across multiple runs.
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    config_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    system_prompt_template TEXT,
    user_prompt_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by name
CREATE INDEX IF NOT EXISTS idx_experiments_name ON experiments(name);

-- Index for fast lookups by hash (to detect duplicate configs)
CREATE INDEX IF NOT EXISTS idx_experiments_hash ON experiments(config_hash);

-- ============================================================================
-- TABLE: runs
-- Purpose: Track individual benchmark execution runs.
--          Each run represents a single execution of the benchmark tool.
--          Runs can be associated with an experiment or be standalone (dev mode).
-- ============================================================================
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    seed INTEGER,
    is_dev BOOLEAN NOT NULL DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE SET NULL
);

-- Index for fast lookups by experiment
CREATE INDEX IF NOT EXISTS idx_runs_experiment ON runs(experiment_id);

-- Index for fast lookups by status
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

-- Index for fast lookups by is_dev flag
CREATE INDEX IF NOT EXISTS idx_runs_is_dev ON runs(is_dev);

-- ============================================================================
-- TABLE: models
-- Purpose: Registry of LLM models used in benchmarks.
--          Each unique model (provider + model_name combination) is stored once.
--          This table stores ONLY base model information, NOT execution parameters.
-- ============================================================================
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    supports_multimodal BOOLEAN NOT NULL DEFAULT 0,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookups by provider
CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider);

-- Unique index to prevent duplicate model registrations
CREATE UNIQUE INDEX IF NOT EXISTS idx_models_unique ON models(provider, model_name);

-- ============================================================================
-- TABLE: model_variants
-- Purpose: Registry of model variants with execution parameters.
--          Each variant is a unique combination of:
--          - Base model (model_id)
--          - Reasoning configuration (mode, effort, max_tokens)
--          - Vision enabled
--          - Structured outputs enabled
--
-- Identity fields (used in variant_signature):
--   - reasoning_mode: 'off', 'auto', 'effort', 'budget', 'unspecified'
--   - reasoning_effort: 'xhigh', 'high', 'medium', 'low', 'minimal' (when mode='effort')
--   - reasoning_max_tokens: integer (when mode='budget')
--   - vision_enabled: boolean
--   - structured_enabled: boolean
--
-- Non-identity fields (NOT part of variant_signature):
--   - temperature, top_p, top_k, max_tokens, repeat_penalty
--   These are execution parameters that do NOT define variant identity.
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_variants (
    -- Short stable identifier (hash-based)
    variant_id TEXT PRIMARY KEY,

    -- Base model reference
    model_id TEXT NOT NULL,

    -- Identity fields (define variant_signature)
    reasoning_mode TEXT NOT NULL DEFAULT 'unspecified'
        CHECK (reasoning_mode IN ('off', 'auto', 'effort', 'budget', 'unspecified')),
    reasoning_effort TEXT
        CHECK (reasoning_effort IN ('xhigh', 'high', 'medium', 'low', 'minimal')),
    reasoning_max_tokens INTEGER,
    vision_enabled BOOLEAN NOT NULL DEFAULT 0,
    structured_enabled BOOLEAN NOT NULL DEFAULT 0,

    -- Human-readable signature (unique per model_id + identity)
    variant_signature TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
);

-- Index for fast lookups by base model
CREATE INDEX IF NOT EXISTS idx_model_variants_model ON model_variants(model_id);

-- Index for fast lookups by reasoning mode
CREATE INDEX IF NOT EXISTS idx_model_variants_reasoning ON model_variants(reasoning_mode);

-- Unique index: one variant per (model_id + identity combination)
CREATE UNIQUE INDEX IF NOT EXISTS idx_model_variants_unique
ON model_variants(
    model_id,
    reasoning_mode,
    COALESCE(reasoning_effort, ''),
    COALESCE(reasoning_max_tokens, 0),
    vision_enabled,
    structured_enabled
);

-- ============================================================================
-- TABLE: run_models
-- Purpose: Associate model variants with runs. Allows adding models to
--          existing runs dynamically. Each entry tracks the execution status
--          of a specific model variant within a specific run.
--
-- Status values:
--   - pending: Model added to run but execution not started
--   - running: Model is currently being executed (some iterations done)
--   - completed: All iterations completed for this model in this run
--   - removed: Model removed from run (no responses yet)
-- ============================================================================

CREATE TABLE IF NOT EXISTS run_models (
    -- Composite primary key: one entry per (run, variant) pair
    run_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,

    -- Status tracks execution progress for this model in this run
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'removed')),

    -- Timestamp when model was added to run
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Timestamp when model completed (all iterations done)
    completed_at TIMESTAMP,

    -- Primary key
    PRIMARY KEY (run_id, variant_id),

    -- Foreign keys
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_run_models_run ON run_models(run_id);

-- Index for fast lookups by variant
CREATE INDEX IF NOT EXISTS idx_run_models_variant ON run_models(variant_id);

-- Index for fast lookups by status
CREATE INDEX IF NOT EXISTS idx_run_models_status ON run_models(status);

-- ============================================================================
-- TABLE: experiment_models
-- Purpose: Associate model variants with experiments. This table defines
--          which models belong to an experiment. Runs reference these models.
--          Simple association: no status field, removal is physical (DELETE).
-- ============================================================================

CREATE TABLE IF NOT EXISTS experiment_models (
    experiment_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (experiment_id, variant_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
);

-- Index for fast lookups by experiment
CREATE INDEX IF NOT EXISTS idx_experiment_models_exp ON experiment_models(experiment_id);

-- Index for fast lookups by variant
CREATE INDEX IF NOT EXISTS idx_experiment_models_variant ON experiment_models(variant_id);

-- ============================================================================
-- TABLE: questions
-- Purpose: Store questionnaire questions for reproducibility.
--          Questions are loaded from external files (JSON/CSV) and persisted
--          here to ensure audit trails and version independence.
--          This is the CANONICAL CATALOG - questions can be updated here
--          without affecting existing experiment results.
-- ============================================================================
CREATE TABLE IF NOT EXISTS questions (
    question_id TEXT PRIMARY KEY,
    stem TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_answer TEXT,
    has_image BOOLEAN NOT NULL DEFAULT 0,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'active'
);

-- Index for fast lookups by status
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);

-- Index for fast lookups by has_image flag
CREATE INDEX IF NOT EXISTS idx_questions_has_image ON questions(has_image);

-- ============================================================================
-- TABLE: question_snapshots
-- Purpose: Store IMMUTABLE snapshots of questions used in each experiment.
--          Each snapshot captures the complete question JSON at the moment
--          it was first used in an experiment, ensuring reproducibility.
--          Snapshots are created only once per (experiment_id, question_id) pair.
--          EVERY snapshot MUST be associated with a valid experiment (NO NULL).
-- ============================================================================
CREATE TABLE IF NOT EXISTS question_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE RESTRICT
);

-- Index for fast lookups by experiment
CREATE INDEX IF NOT EXISTS idx_question_snapshots_experiment ON question_snapshots(experiment_id);

-- Index for fast lookups by question
CREATE INDEX IF NOT EXISTS idx_question_snapshots_question ON question_snapshots(question_id);

-- Unique index to prevent duplicate snapshots for same (experiment, question)
CREATE UNIQUE INDEX IF NOT EXISTS idx_question_snapshots_unique
ON question_snapshots(experiment_id, question_id);

-- ============================================================================
-- TABLE: responses
-- Purpose: Store individual model responses to questions.
--          This is the core data table for benchmark analysis.
--          Each row represents one model's answer to one question in one iteration.
--          Responses reference model_id (base models) for tracking.
-- ============================================================================

CREATE TABLE IF NOT EXISTS responses (
    -- IDENTIFICATION (6 columns)
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 1,

    -- RESPONSE DATA (4 columns)
    selected_answer TEXT,
    response_text TEXT,
    is_correct BOOLEAN,
    status TEXT NOT NULL DEFAULT 'pending',

    -- TERMINATION (2 columns)
    finish_reason TEXT,
    error_details TEXT,

    -- PERFORMANCE (1 column)
    latency_ms INTEGER,

    -- TOKENS (5 columns)
    input_tokens INTEGER,
    response_tokens INTEGER,
    total_tokens INTEGER,
    reasoning_tokens INTEGER,
    effective_tokens INTEGER,

    -- COST (1 column)
    cost REAL,

    -- AUDIT (2 columns)
    raw_response_json TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- MANUAL REVIEW (4 columns)
    parse_confidence TEXT NOT NULL DEFAULT 'unknown',
    review_status TEXT NOT NULL DEFAULT 'auto',
    reviewed_at TIMESTAMP,
    manual_answer TEXT,

    -- FOREIGN KEYS
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE RESTRICT,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE RESTRICT
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_responses_run ON responses(run_id);

-- Index for fast lookups by snapshot
CREATE INDEX IF NOT EXISTS idx_responses_snapshot ON responses(snapshot_id);

-- Index for fast lookups by question
CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id);

-- Index for fast lookups by model
CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);

-- Composite index for run + iteration
CREATE INDEX IF NOT EXISTS idx_responses_run_iteration ON responses(run_id, iteration);

-- Composite index for accuracy analysis by model
CREATE INDEX IF NOT EXISTS idx_responses_model_correct ON responses(model_id, is_correct);

-- ============================================================================
-- TABLE: errors
-- Purpose: Track errors that occur during benchmark execution.
--          Errors are associated with a specific run, question, and model.
-- ============================================================================

CREATE TABLE IF NOT EXISTS errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    question_id TEXT,
    model_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE SET NULL,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE SET NULL
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_errors_run ON errors(run_id);

-- Index for fast lookups by model
CREATE INDEX IF NOT EXISTS idx_errors_model ON errors(model_id);

-- Index for fast lookups by error type
CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);

-- Index for fast lookups by timestamp
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp);

-- ============================================================================
-- SYSTEM VIEWS
-- ============================================================================

-- VIEW: responses_with_model
-- Purpose: Join responses with base model info for easy querying
CREATE VIEW IF NOT EXISTS responses_with_model AS
SELECT
    r.response_id,
    r.run_id,
    r.snapshot_id,
    r.question_id,
    r.model_id,
    r.iteration,
    r.selected_answer,
    r.response_text,
    r.is_correct,
    r.status,
    r.finish_reason,
    r.error_details,
    r.latency_ms,
    r.input_tokens,
    r.response_tokens,
    r.total_tokens,
    r.reasoning_tokens,
    r.effective_tokens,
    r.cost,
    r.raw_response_json,
    r.timestamp,
    r.parse_confidence,
    r.review_status,
    r.reviewed_at,
    r.manual_answer,
    -- Base model info
    m.provider,
    m.model_name
FROM responses r
JOIN models m ON r.model_id = m.model_id;

-- VIEW: model_stats
-- Purpose: Pre-aggregated statistics per model
CREATE VIEW IF NOT EXISTS model_stats AS
SELECT
    m.model_id,
    m.provider,
    m.model_name,
    COUNT(r.response_id) AS total_responses,
    SUM(CASE WHEN r.is_correct = 1 THEN 1 ELSE 0 END) AS correct_answers,
    SUM(CASE WHEN r.is_correct = 0 THEN 1 ELSE 0 END) AS incorrect_answers,
    SUM(CASE WHEN r.status = 'error' THEN 1 ELSE 0 END) AS error_count,
    ROUND(
        100.0 * SUM(CASE WHEN r.is_correct = 1 THEN 1 ELSE 0 END) /
        NULLIF(COUNT(r.response_id), 0),
        2
    ) AS accuracy_percent,
    ROUND(AVG(r.latency_ms), 2) AS avg_latency_ms,
    SUM(r.input_tokens) AS total_input_tokens,
    SUM(r.response_tokens) AS total_response_tokens,
    SUM(r.reasoning_tokens) AS total_reasoning_tokens,
    SUM(r.effective_tokens) AS total_effective_tokens,
    ROUND(SUM(r.cost), 6) AS total_cost
FROM models m
LEFT JOIN responses r ON m.model_id = r.model_id
GROUP BY m.model_id, m.provider, m.model_name;

-- ============================================================================
-- End of Schema
-- ============================================================================
