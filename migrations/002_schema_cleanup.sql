-- Migration 002: Schema Cleanup
-- Purpose: Remove unused/dead columns and tables to improve conceptual clarity
-- Date: 2026-03-13
--
-- Changes:
-- 1. Remove models.supports_multimodal (never used)
-- 2. Remove models.metadata_json (never used)
-- 3. Remove schema_metadata table (never populated)
--
-- Note: errors.stack_trace is KEPT and now properly populated via traceback.format_exc()

PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. Remove models.supports_multimodal and models.metadata_json
-- ============================================================================
-- SQLite doesn't support DROP COLUMN directly, so we need to recreate the table

-- Create temporary table with new schema
CREATE TABLE IF NOT EXISTS models_new (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Copy data from old table (only the columns we're keeping)
INSERT INTO models_new (model_id, provider, model_name, created_at)
SELECT model_id, provider, model_name, created_at
FROM models;

-- Drop old table
DROP TABLE models;

-- Rename new table
ALTER TABLE models_new RENAME TO models;

-- Recreate indexes
DROP INDEX IF EXISTS idx_models_provider;
DROP INDEX IF EXISTS idx_models_unique;

CREATE INDEX idx_models_provider ON models(provider);
CREATE UNIQUE INDEX idx_models_unique ON models(provider, model_name);

-- ============================================================================
-- 2. Remove schema_metadata table
-- ============================================================================
DROP TABLE IF EXISTS schema_metadata;

-- ============================================================================
-- Migration Complete
-- ============================================================================
