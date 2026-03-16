-- Migration: Add variant_id to responses table
-- Purpose: Support model variant tracking in responses
-- Date: 2026-03-15

-- Add variant_id column to responses
ALTER TABLE responses ADD COLUMN variant_id TEXT;

-- Add index for faster lookups by variant
CREATE INDEX IF NOT EXISTS idx_responses_variant ON responses(variant_id);

-- Add foreign key constraint (optional, for referential integrity)
-- Note: SQLite doesn't support adding foreign keys to existing columns
-- The constraint is enforced by application logic

-- Update existing responses to use model_id as variant_id (backward compatibility)
-- This is a temporary measure until all responses use proper variant_id
UPDATE responses 
SET variant_id = model_id 
WHERE variant_id IS NULL;
