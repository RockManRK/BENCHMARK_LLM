-- Migration 003: Model Variants System
-- Purpose: Implement model variant tracking for reasoning, vision, and structured outputs
-- Date: 2026-03-13
-- 
-- This migration replaces the simple models table with a variant-based system.
-- Each model variant represents a unique combination of:
--   - Base model (provider/model_name)
--   - Reasoning mode (off/auto/effort/budget/unspecified)
--   - Vision enabled (true/false)
--   - Structured outputs enabled (true/false)
--
-- IMPORTANT: This is a BREAKING migration. Not backward compatible.

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================================
-- STEP 1: Drop old tables (if exist)
-- ============================================================================

-- Drop responses table first (has FK to models)
DROP TABLE IF EXISTS responses;

-- Drop errors table (has FK to models)
DROP TABLE IF EXISTS errors;

-- Drop models table
DROP TABLE IF EXISTS models;

-- ============================================================================
-- STEP 2: Create new schema with variants
-- ============================================================================

-- TABLE: models (base model registry - no execution parameters)
-- Purpose: Registry of unique base models (provider + model_name combination)
CREATE TABLE IF NOT EXISTS models (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
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
-- TABLE: responses (updated to reference model_variants)
-- Purpose: Store individual model responses to questions.
--          Now references model_variants instead of base models.
-- ============================================================================

CREATE TABLE IF NOT EXISTS responses (
    -- IDENTIFICATION (6 columns)
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
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
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE RESTRICT
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_responses_run ON responses(run_id);

-- Index for fast lookups by snapshot
CREATE INDEX IF NOT EXISTS idx_responses_snapshot ON responses(snapshot_id);

-- Index for fast lookups by question
CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id);

-- Index for fast lookups by variant (replaces model index)
CREATE INDEX IF NOT EXISTS idx_responses_variant ON responses(variant_id);

-- Composite index for run + iteration
CREATE INDEX IF NOT EXISTS idx_responses_run_iteration ON responses(run_id, iteration);

-- Composite index for accuracy analysis by variant
CREATE INDEX IF NOT EXISTS idx_responses_variant_correct ON responses(variant_id, is_correct);

-- ============================================================================
-- TABLE: errors (updated to reference model_variants)
-- Purpose: Track errors that occur during benchmark execution.
-- ============================================================================

CREATE TABLE IF NOT EXISTS errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    question_id TEXT,
    variant_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE SET NULL,
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id) ON DELETE SET NULL
);

-- Index for fast lookups by run
CREATE INDEX IF NOT EXISTS idx_errors_run ON errors(run_id);

-- Index for fast lookups by variant
CREATE INDEX IF NOT EXISTS idx_errors_variant ON errors(variant_id);

-- Index for fast lookups by error type
CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);

-- Index for fast lookups by timestamp
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp);

-- ============================================================================
-- STEP 3: Create system views for convenience
-- ============================================================================

-- VIEW: responses_with_model
-- Purpose: Join responses with variant and base model info for easy querying
CREATE VIEW IF NOT EXISTS responses_with_model AS
SELECT 
    r.response_id,
    r.run_id,
    r.snapshot_id,
    r.question_id,
    r.variant_id,
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
    -- Variant identity fields
    mv.model_id,
    mv.reasoning_mode,
    mv.reasoning_effort,
    mv.reasoning_max_tokens,
    mv.vision_enabled,
    mv.structured_enabled,
    mv.variant_signature,
    -- Base model info
    m.provider,
    m.model_name
FROM responses r
JOIN model_variants mv ON r.variant_id = mv.variant_id
JOIN models m ON mv.model_id = m.model_id;

-- VIEW: variant_stats
-- Purpose: Pre-aggregated statistics per model variant
CREATE VIEW IF NOT EXISTS variant_stats AS
SELECT 
    mv.variant_id,
    mv.model_id,
    mv.variant_signature,
    mv.reasoning_mode,
    mv.vision_enabled,
    mv.structured_enabled,
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
FROM model_variants mv
LEFT JOIN responses r ON mv.variant_id = r.variant_id
GROUP BY mv.variant_id, mv.model_id, mv.variant_signature, 
         mv.reasoning_mode, mv.vision_enabled, mv.structured_enabled;

-- ============================================================================
-- End of Migration 003
-- ============================================================================
