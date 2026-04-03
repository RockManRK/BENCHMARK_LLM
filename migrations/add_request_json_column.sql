-- Migration: Add request_json column to responses table
-- Date: 2026-04-03
-- Purpose: Persist the complete API request payload for audit and debugging
--
-- This column stores the exact JSON payload that was sent to the API,
-- enabling full auditability of model requests even in failure scenarios.

ALTER TABLE responses ADD COLUMN request_json TEXT;
