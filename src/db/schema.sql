-- Benchmark LLM Database Schema
-- This schema defines the structure for storing benchmark experiments, runs, and responses.
-- Generated: 2026-03-07

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
    system_prompt TEXT,
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
-- ============================================================================
CREATE TABLE IF NOT EXISTS question_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT,
    question_id TEXT NOT NULL,
    question_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id) ON DELETE SET NULL,
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
--          Responses reference question_snapshots (not questions directly) to
--          ensure immutability and reproducibility of experiment results.
-- ============================================================================
CREATE TABLE IF NOT EXISTS responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 1,
    selected_answer TEXT,
    response_text TEXT,
    is_correct BOOLEAN,
    status TEXT NOT NULL DEFAULT 'pending',
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    reasoning_tokens INTEGER,
    cost REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id) ON DELETE RESTRICT,
    FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE RESTRICT
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_responses_run ON responses(run_id);

-- Index for fast lookups by snapshot
CREATE INDEX IF NOT EXISTS idx_responses_snapshot ON responses(snapshot_id);

-- Index for fast lookups by model
CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);

-- Composite index for common query patterns (run + iteration)
CREATE INDEX IF NOT EXISTS idx_responses_run_iteration ON responses(run_id, iteration);

-- Composite index for accuracy analysis (model + is_correct)
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

-- Index for fast lookups by error type
CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);

-- Index for fast lookups by timestamp
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp);

-- ============================================================================
-- Schema Metadata (Optional - for documentation)
-- This table can be used to store descriptions of tables and columns.
-- Currently not populated by default, but available for future use.
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_metadata (
    table_name TEXT NOT NULL,
    column_name TEXT,
    description TEXT NOT NULL,
    PRIMARY KEY (table_name, column_name)
);

-- ============================================================================
-- End of Schema
-- ============================================================================
