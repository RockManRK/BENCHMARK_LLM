-- Migration: Add error_details column to responses table
-- Date: 2026-03-09
-- Purpose: Add error_details column to store full error response bodies for debugging

-- Add error_details column to responses table
-- This column stores detailed error information (e.g., full API error response body)
ALTER TABLE responses ADD COLUMN error_details TEXT;

-- Note: Existing records will have NULL for error_details, which is acceptable
-- as this is a new feature for tracking error details
