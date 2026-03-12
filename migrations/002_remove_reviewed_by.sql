-- Migration: 002_remove_reviewed_by.sql
-- Purpose: Remove reviewed_by column from responses table
-- Date: 2026-03-12
-- 
-- This migration removes the reviewed_by column which was never used.
-- Since the application is used by a single reviewer, tracking the reviewer
-- identity is unnecessary and adds complexity.
--
-- IMPORTANT: This column is always NULL in existing installations,
-- so no data will be lost.

-- ============================================================================
-- STEP 1: Create backup
-- ============================================================================

-- Backup the entire responses table
CREATE TABLE IF NOT EXISTS responses_backup AS SELECT * FROM responses;

-- Verify backup
SELECT 'Backup created: responses_backup' AS status;
SELECT COUNT(*) AS backup_row_count FROM responses_backup;

-- ============================================================================
-- STEP 2: Create new responses table (without reviewed_by)
-- ============================================================================

CREATE TABLE responses_new (
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
    total_tokens INTEGER,           -- input_tokens + response_tokens (excludes reasoning_tokens)
    reasoning_tokens INTEGER,       -- Reasoning tokens (NOT included in total_tokens)
    effective_tokens INTEGER,       -- input_tokens + response_tokens + reasoning_tokens
    
    -- COST (1 column)
    cost REAL,
    
    -- AUDIT (2 columns)
    raw_response_json TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- MANUAL REVIEW (4 columns) - reviewed_by removed
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

-- ============================================================================
-- STEP 3: Migrate data
-- ============================================================================

-- Insert data from old table to new table (excluding reviewed_by)
INSERT INTO responses_new (
    response_id, run_id, snapshot_id, question_id, model_id, iteration,
    selected_answer, response_text, is_correct,
    status, finish_reason, error_details, latency_ms,
    input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens,
    cost, raw_response_json, timestamp,
    parse_confidence, review_status, reviewed_at, manual_answer
)
SELECT 
    response_id,
    run_id,
    snapshot_id,
    question_id,
    model_id,
    iteration,
    selected_answer,
    response_text,
    is_correct,
    status,
    finish_reason,
    error_details,
    latency_ms,
    input_tokens,
    response_tokens,
    total_tokens,
    reasoning_tokens,
    effective_tokens,
    cost,
    raw_response_json,
    timestamp,
    parse_confidence,
    review_status,
    reviewed_at,
    manual_answer
FROM responses;

-- Verify migration
SELECT 'Data migrated' AS status;
SELECT COUNT(*) AS new_row_count FROM responses_new;

-- ============================================================================
-- STEP 4: Drop old table and rename new one
-- ============================================================================

-- Drop old responses table
DROP TABLE responses;

-- Rename new table to responses
ALTER TABLE responses_new RENAME TO responses;

-- Verify table rename
SELECT 'Table renamed to responses' AS status;

-- ============================================================================
-- STEP 5: Rebuild indexes
-- ============================================================================

-- Recreate all indexes
CREATE INDEX IF NOT EXISTS idx_responses_run ON responses(run_id);
CREATE INDEX IF NOT EXISTS idx_responses_snapshot ON responses(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_responses_question ON responses(question_id);
CREATE INDEX IF NOT EXISTS idx_responses_model ON responses(model_id);
CREATE INDEX IF NOT EXISTS idx_responses_run_iteration ON responses(run_id, iteration);
CREATE INDEX IF NOT EXISTS idx_responses_model_correct ON responses(model_id, is_correct);

SELECT 'Indexes rebuilt' AS status;

-- ============================================================================
-- STEP 6: Verification queries
-- ============================================================================

-- Verify column structure
PRAGMA table_info(responses);

-- Verify row count matches
SELECT 
    (SELECT COUNT(*) FROM responses_backup) AS backup_count,
    (SELECT COUNT(*) FROM responses) AS current_count;

-- Verify reviewed_by column does not exist
SELECT 'Migration complete - reviewed_by column removed' AS status;

-- ============================================================================
-- ROLLBACK INSTRUCTIONS (if needed)
-- ============================================================================
-- 
-- If you need to rollback this migration:
-- 
-- 1. Drop the new responses table:
--    DROP TABLE responses;
-- 
-- 2. Rename backup back to responses:
--    ALTER TABLE responses_backup RENAME TO responses;
-- 
-- 3. Verify rollback:
--    PRAGMA table_info(responses);
-- 
-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
