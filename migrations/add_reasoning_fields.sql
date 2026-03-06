-- Migration: Add reasoning fields to responses table
-- Date: 2026-03-06
-- Phase: 2 - Data Collection (Reasoning Details)
-- Description: Adds reasoning_details and reasoning_tokens columns to the responses table
--              for storing reasoning trace data from AI models.

-- Add reasoning_details column (JSON TEXT)
-- Stores an array of reasoning steps/contents from the model
ALTER TABLE responses ADD COLUMN reasoning_details TEXT DEFAULT NULL;

-- Add reasoning_tokens column (INTEGER)
-- Stores the number of tokens used for reasoning (if provided by API)
ALTER TABLE responses ADD COLUMN reasoning_tokens INTEGER DEFAULT NULL;

-- Note: These columns are nullable to maintain backward compatibility
-- with existing databases and benchmarks run without reasoning support.
