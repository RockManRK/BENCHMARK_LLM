-- Migration 004: Run Models Association Table
-- Purpose: Allow adding models to existing runs dynamically
-- Date: 2026-03-13
--
-- This migration creates an intermediary table to associate models with runs,
-- allowing models to be added to a run after it has been created.
--
-- NOTE: If you are creating a new database from scratch, this migration is NOT needed.
-- Simply use the schema defined in src/db/schema.sql which already includes run_models.
-- This migration is only for converting EXISTING databases.
--
-- To create a fresh database, run:
--   sqlite3 data/benchmark.db < src/db/schema.sql
--
-- To migrate an existing database, run:
--   sqlite3 data/benchmark.db < migrations/004_run_models.sql

-- Enable foreign key support
PRAGMA foreign_keys = ON;

-- ============================================================================
-- STEP 1: Create run_models table
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
-- STEP 2: Migrate existing data (if any)
-- ============================================================================

-- Populate run_models from existing responses
-- This ensures backward compatibility: models that already have responses
-- are registered in run_models with status 'completed'
INSERT OR IGNORE INTO run_models (run_id, variant_id, status, completed_at)
SELECT DISTINCT 
    r.run_id,
    r.variant_id,
    'completed',
    MAX(r.timestamp)
FROM responses r
GROUP BY r.run_id, r.variant_id;

-- ============================================================================
-- End of Migration 004
-- ============================================================================
