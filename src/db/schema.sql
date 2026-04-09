-- Benchmark LLM - TO-BE Database Schema
-- Generated from: src/db/schema.py
-- 
-- This schema reflects the CURRENT implemented state:
-- - 6 tables: experiments, model_variants, question_snapshots, runs, responses, errors
-- - All columns with correct types
-- - All constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK)
-- - All indexes
-- - NO is_active columns (removed in TO-BE architecture)
-- - Correct column names (json_question_id, question_position, config, duration, etc.)

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- experiments table
-- ============================================================================
-- Stores experiment definitions with immutable config
-- 
-- Columns:
--   experiment_id   TEXT PRIMARY KEY  - Unique experiment identifier (exp_XXXXXXXX)
--   name            TEXT UNIQUE       - Human-readable experiment name
--   description     TEXT              - Optional description
--   config_json     TEXT NOT NULL     - JSON configuration (18 experiment-level keys)
--   config_hash     TEXT NOT NULL     - SHA256 hash of config_json for deduplication
--   created_at      TIMESTAMP         - Creation timestamp (auto-populated)
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id     TEXT PRIMARY KEY,
    name              TEXT UNIQUE NOT NULL,
    description       TEXT,
    config_json       TEXT NOT NULL,
    config_hash       TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experiments_created_at
ON experiments(created_at);

-- ============================================================================
-- model_variants table
-- ============================================================================
-- Stores model variant configurations within experiments
-- 
-- Columns:
--   variant_id        TEXT PRIMARY KEY  - Unique variant identifier (var_XXXXXXXX)
--   experiment_id     TEXT NOT NULL     - FK to experiments.experiment_id
--   model_id          TEXT NOT NULL     - Model identifier (provider/model-name)
--   variant_signature TEXT NOT NULL     - Unique signature (model_id + config hash)
--   config            TEXT NOT NULL     - JSON configuration (10 model-level keys)
--   created_at        TIMESTAMP         - Creation timestamp (auto-populated)
-- 
-- Constraints:
--   UNIQUE(experiment_id, variant_signature) - Prevent duplicate variants
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_variants (
    variant_id        TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    model_id          TEXT NOT NULL,
    variant_signature TEXT NOT NULL,
    config            TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, variant_signature)
);

-- Index for variants by experiment (common query pattern)
CREATE INDEX IF NOT EXISTS idx_variants_by_experiment ON model_variants(experiment_id);

CREATE INDEX IF NOT EXISTS idx_model_variants_created_at
ON model_variants(created_at);

-- ============================================================================
-- question_snapshots table
-- ============================================================================
-- Stores immutable question snapshots within experiments
-- 
-- Columns:
--   snapshot_id       TEXT PRIMARY KEY  - Unique snapshot identifier (snap_XXXXXXXX)
--   experiment_id     TEXT NOT NULL     - FK to experiments.experiment_id
--   json_question_id  TEXT NOT NULL     - Source question ID from dataset
--   question_position INTEGER NOT NULL  - Internal numeric ID (1..N)
--   question_payload  TEXT NOT NULL     - JSON payload (stem, options, answer_key, meta)
--   created_at        TIMESTAMP         - Creation timestamp (auto-populated)
-- 
-- Constraints:
--   UNIQUE(experiment_id, question_position) - Prevent duplicate positions
-- ============================================================================
CREATE TABLE IF NOT EXISTS question_snapshots (
    snapshot_id       TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    json_question_id  TEXT NOT NULL,
    question_position INTEGER NOT NULL,
    question_payload  TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, question_position)
);

-- Index for snapshots by experiment (common query pattern)
CREATE INDEX IF NOT EXISTS idx_snapshots_by_experiment ON question_snapshots(experiment_id);

CREATE INDEX IF NOT EXISTS idx_question_snapshots_created_at
ON question_snapshots(created_at);

-- ============================================================================
-- runs table
-- ============================================================================
-- Stores run definitions (execution instances of experiments)
-- 
-- Columns:
--   run_id            TEXT PRIMARY KEY  - Unique run identifier (run_XXXXXXXX)
--   experiment_id     TEXT NOT NULL     - FK to experiments.experiment_id
--   config            TEXT NOT NULL     - JSON configuration (3 run-level keys: seed, system_prompt, user_prompt)
--   status            TEXT NOT NULL     - Lifecycle status (pending|running|completed|failed|partial_failed)
--   duration          INTEGER DEFAULT 0 - Execution duration in milliseconds
--   created_at        TIMESTAMP         - Creation timestamp (auto-populated)
-- 
-- Constraints:
--   CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
-- ============================================================================
CREATE TABLE IF NOT EXISTS runs (
    run_id            TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    config            TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    duration          INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
);

-- Index for listing runs by experiment (common query pattern)
CREATE INDEX IF NOT EXISTS idx_runs_by_experiment ON runs(experiment_id);

-- Partial index for pending runs (optimizes execution queue queries)
CREATE INDEX IF NOT EXISTS idx_runs_pending ON runs(status) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_runs_created_at
ON runs(created_at);

-- ============================================================================
-- responses table
-- ============================================================================
-- Stores model response results for each (run, variant, snapshot) combination
--
-- Columns:
--   response_id       TEXT PRIMARY KEY  - Unique response identifier (resp_XXXXXXXX)
--   run_id            TEXT NOT NULL     - FK to runs.run_id
--   variant_id        TEXT NOT NULL     - FK to model_variants.variant_id
--   snapshot_id       TEXT NOT NULL     - FK to question_snapshots.snapshot_id
--   model_id          TEXT NOT NULL     - Denormalized model identifier for reporting
--   question_id       TEXT NOT NULL     - Denormalized question identifier for reporting
--   status            TEXT              - Response status
--   finish_reason     TEXT              - Model finish reason
--   error_details     TEXT              - Error message if failed
--   response_text     TEXT              - Raw model response text
--   selected_answer   TEXT              - Parsed answer (A/B/C/D)
--   is_correct        BOOLEAN           - Whether selected_answer matches correct_option_presented
--   parse_confidence  TEXT DEFAULT 'unknown' - Parser confidence (clear|ambiguous|unknown)
--   review_status     TEXT              - Review flag (needs_review|reviewed|auto)
--   manual_answer     TEXT              - Human-corrected answer (post-review)
--   raw_response      TEXT              - Complete raw API response
--   cost              REAL              - API cost in USD
--   input_tokens      INTEGER           - Input tokens sent to model
--   response_tokens   INTEGER           - Output tokens from model
--   reasoning_tokens  INTEGER           - Tokens used for reasoning (thinking)
--   effective_tokens  INTEGER           - Total tokens (input + response + reasoning)
--   latency_ms        INTEGER           - API latency in milliseconds
--   started_at        TIMESTAMP         - Execution start time
--   finished_at       TIMESTAMP         - Execution end time
--
-- Experimental Context (Randomization Tracking):
--   Estas colunas congelam o contexto experimental real de cada resposta.
--   Elas evitam inferência indireta via run e garantem auditoria e reprodutibilidade.
--
--   randomization_enabled BOOLEAN       - Se randomização foi aplicada nesta resposta
--   randomization_seed  INTEGER         - Seed usada (NULL = desligada)
--   options_presented   TEXT (JSON)     - Alternativas exatamente como apresentadas à LLM
--   correct_option_presented TEXT       - Gabarito no espaço apresentado (ex: "C")
--   option_letter_map   TEXT (JSON)     - Mapeamento letra apresentada → letra original
--
-- Constraints:
--   UNIQUE(run_id, variant_id, snapshot_id) - Prevent duplicate responses
--
-- Review Fields Contract:
--   review_status values: 'needs_review', 'reviewed', 'auto'
--
-- Randomization Contract:
--   randomization_enabled = TRUE significa que as opções foram embaralhadas
--   correct_option_presented é o gabarito CORRETO no espaço apresentado à LLM
--   is_correct é calculado comparando selected_answer vs correct_option_presented
--   O que foi apresentado à LLM é a verdade experimental e nunca deve ser "desrandomizado"
-- ============================================================================
CREATE TABLE IF NOT EXISTS responses (
    response_id       TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
    snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
    model_id          TEXT NOT NULL,
    question_id       TEXT NOT NULL,
    status            TEXT,
    finish_reason     TEXT,
    error_details     TEXT,
    response_text     TEXT,
    selected_answer   TEXT,
    is_correct        BOOLEAN,
    parse_confidence  TEXT DEFAULT 'unknown',
    review_status     TEXT,
    manual_answer     TEXT,
    raw_response      TEXT,
    cost              REAL,
    input_tokens      INTEGER,
    response_tokens   INTEGER,
    reasoning_tokens  INTEGER,
    effective_tokens  INTEGER,
    latency_ms        INTEGER,
    started_at        TIMESTAMP,
    finished_at       TIMESTAMP,

    -- Contexto experimental de randomização por resposta
    -- Estas colunas congelam o contexto experimental real:
    randomization_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    randomization_seed  INTEGER,
    options_presented   TEXT,
    correct_option_presented TEXT,
    option_letter_map   TEXT,

    UNIQUE(run_id, variant_id, snapshot_id)
);

-- Index for listing responses by run (common query pattern)
CREATE INDEX IF NOT EXISTS idx_responses_by_run ON responses(run_id);

-- Partial index for responses needing review (optimizes review queue queries)
CREATE INDEX IF NOT EXISTS idx_responses_needs_review ON responses(review_status) WHERE review_status = 'needs_review';

CREATE INDEX IF NOT EXISTS idx_responses_started_at
ON responses(started_at);

CREATE INDEX IF NOT EXISTS idx_responses_finished_at
ON responses(finished_at);

-- ============================================================================
-- errors table
-- ============================================================================
-- Stores execution errors for failed model invocations
-- 
-- Columns:
--   error_id          TEXT PRIMARY KEY  - Unique error identifier (err_XXXXXXXX)
--   run_id            TEXT NOT NULL     - FK to runs.run_id
--   variant_id        TEXT NOT NULL     - FK to model_variants.variant_id
--   snapshot_id       TEXT NOT NULL     - FK to question_snapshots.snapshot_id
--   question_id       TEXT NOT NULL     - Denormalized question identifier
--   error_type        TEXT NOT NULL     - Error category (api_error|parse_error|timeout|etc.)
--   error_message     TEXT NOT NULL     - Human-readable error message
--   attempt_count     INTEGER NOT NULL  - Number of retry attempts (default: 1)
--   stack_trace       TEXT              - Full stack trace for debugging
--   occurred_at       TIMESTAMP         - Error occurrence timestamp
-- ============================================================================
CREATE TABLE IF NOT EXISTS errors (
    error_id          TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
    snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
    question_id       TEXT NOT NULL,
    error_type        TEXT NOT NULL,
    error_message     TEXT NOT NULL,
    attempt_count     INTEGER NOT NULL DEFAULT 1,
    stack_trace       TEXT,
    occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for listing errors by run (common query pattern)
CREATE INDEX IF NOT EXISTS idx_errors_by_run ON errors(run_id);

CREATE INDEX IF NOT EXISTS idx_errors_occurred_at
ON errors(occurred_at);