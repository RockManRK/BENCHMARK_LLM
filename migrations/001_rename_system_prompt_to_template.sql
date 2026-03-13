-- Migration: Rename system_prompt to system_prompt_template
-- Date: 2026-03-13
-- Purpose: Semantic clarity - both prompts are templates

-- Rename column in experiments table
ALTER TABLE experiments RENAME COLUMN system_prompt TO system_prompt_template;

-- Update comment (if exists)
-- Note: SQLite doesn't support COMMENT ON, so this is just documentation
-- The column now has symmetric naming: system_prompt_template, user_prompt_template
