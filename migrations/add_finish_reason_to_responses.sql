-- Migration: Add finish_reason column to responses table
-- Date: 2026-03-09
-- Purpose: Add finish_reason column to store API response termination reasons

-- Add finish_reason column to responses table
-- This column stores the reason why the model stopped generating (e.g., "stop", "length", "eos", "error")
ALTER TABLE responses ADD COLUMN finish_reason TEXT;

-- Note: Existing records will have NULL for finish_reason, which is acceptable
-- as this is a new feature for tracking response termination reasons
