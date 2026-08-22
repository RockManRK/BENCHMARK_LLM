-- Benchmark LLM - TO-BE Database Schema
-- Generated from: src/db/schema.py::get_schema_sql()
--
-- ⚠️  SOURCE OF TRUTH: src/db/schema.py
-- This file is a generated reference copy for documentation purposes only.
-- The active schema definition (used at runtime) is in src/db/schema.py.
-- If there is any discrepancy, schema.py takes precedence.
--
-- Regenerated 2026-08-21 (test-debt reconciliation, ENT-01 deep-audit
-- finding on commit 922603c): the previous copy of this file had drifted
-- significantly from schema.py — missing ON DELETE CASCADE on 3 foreign
-- keys, missing the 'removed' run status, missing responses.raw_response_
-- consolidated/request_json (the same 2 of the 7 ENT-02 columns that also
-- had to be added to Response/ResponseRepository), and the errors table's
-- real (response_id, attempt_number) composite primary key plus its
-- response_id/attempt_number columns entirely. This copy is now a literal,
-- byte-for-byte dedented reproduction of get_schema_sql()'s return value —
-- regenerate it the same way if schema.py changes again, rather than
-- hand-editing this file to avoid the same drift recurring.
--
-- This schema reflects the CURRENT implemented state:
-- - 6 tables: experiments, model_variants, question_snapshots, runs, responses, errors
-- - NO is_active columns (removed in TO-BE architecture)
-- - Run status values: pending, completed, failed, partial_failed, removed
--   ('removed' is a soft-delete marker set by --remove-run — see
--   docs/contracts/immutability.md; 'running' was never a value — runs go
--   directly to a final status via RunFinalizer)
-- - errors is keyed by (response_id, attempt_number), not error_id alone —
--   error_id is a plain column, not the primary key

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- experiments table
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id     TEXT PRIMARY KEY,
    name              TEXT UNIQUE NOT NULL,
    description       TEXT,
    config_json       TEXT NOT NULL,
    config_hash       TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- model_variants table (with experiment_id FK)
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_variants (
    variant_id        TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    model_id          TEXT NOT NULL,
    variant_signature TEXT NOT NULL,
    config            TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, variant_signature)
);

-- Index for variants by experiment
CREATE INDEX IF NOT EXISTS idx_variants_by_experiment ON model_variants(experiment_id);

-- ============================================================================
-- question_snapshots table (with experiment_id FK)
-- ============================================================================
CREATE TABLE IF NOT EXISTS question_snapshots (
    snapshot_id       TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    json_question_id  TEXT NOT NULL,
    question_position INTEGER NOT NULL,
    question_payload  TEXT NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, question_position)
);

-- Index for snapshots by experiment
CREATE INDEX IF NOT EXISTS idx_snapshots_by_experiment ON question_snapshots(experiment_id);

-- ============================================================================
-- runs table
-- ============================================================================
CREATE TABLE IF NOT EXISTS runs (
    run_id            TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,
    config            TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    duration          INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 'removed': set by --remove-run (src/cli/bcllm_run.py::handle_remove_run)
    -- instead of a hard DELETE, so the row (and its config, for
    -- auditability) stays — see docs/contracts/immutability.md
    -- ("Run: status, duration ... Execution lifecycle tracking" is
    -- the documented mutable exception this reuses) and
    -- docs/status/known-issues.md.
    CHECK(status IN ('pending', 'completed', 'failed', 'partial_failed', 'removed'))
);

-- Index for listing runs by experiment
CREATE INDEX IF NOT EXISTS idx_runs_by_experiment ON runs(experiment_id);

-- Partial index for pending runs (common query for execution)
CREATE INDEX IF NOT EXISTS idx_runs_pending ON runs(status) WHERE status = 'pending';

-- ============================================================================
-- responses table
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
    raw_response_consolidated TEXT,
    request_json      TEXT,
    cost              REAL,
    input_tokens      INTEGER,
    response_tokens   INTEGER,
    reasoning_tokens  INTEGER,
    effective_tokens  INTEGER,
    latency_ms        INTEGER,
    started_at        TIMESTAMP,
    finished_at       TIMESTAMP,

    -- Experimental context (randomization tracking)
    -- Estas colunas congelam o contexto experimental real:
    -- randomization_enabled: se randomização foi aplicada
    -- randomization_seed: seed usada (None = desligada)
    -- options_presented: alternativas como apresentadas (JSON)
    -- correct_option_presented: gabarito no espaço apresentado
    -- option_letter_map: mapeamento de letra apresentada para original
    randomization_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    randomization_seed  INTEGER,
    options_presented   TEXT,
    correct_option_presented TEXT,
    option_letter_map   TEXT,

    UNIQUE(run_id, variant_id, snapshot_id)
);

-- Index for listing responses by run
CREATE INDEX IF NOT EXISTS idx_responses_by_run ON responses(run_id);

-- ============================================================================
-- errors table
-- ============================================================================
-- Errors are keyed by (response_id, attempt_number).
-- response_id is a logical reference (no FK constraint) because errors may
-- be written before the response row exists (e.g., API failure on first attempt).
CREATE TABLE IF NOT EXISTS errors (
    error_id          TEXT NOT NULL,
    response_id       TEXT NOT NULL,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
    snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
    question_id       TEXT NOT NULL,
    error_type        TEXT NOT NULL,
    error_message     TEXT NOT NULL,
    attempt_number    INTEGER NOT NULL DEFAULT 1,
    attempt_count     INTEGER NOT NULL DEFAULT 1,
    stack_trace       TEXT,
    occurred_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (response_id, attempt_number)
);

-- Index for listing errors by run
CREATE INDEX IF NOT EXISTS idx_errors_by_run ON errors(run_id);

-- Index for error history per response
CREATE INDEX IF NOT EXISTS idx_errors_by_response ON errors(response_id);
