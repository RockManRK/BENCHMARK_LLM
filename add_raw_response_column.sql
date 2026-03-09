-- Migration script to add raw_response_json column to responses table
-- Run this if you want to keep existing database
-- Or simply delete the database and let it recreate with new schema

-- Add raw_response_json column to responses table
ALTER TABLE responses ADD COLUMN raw_response_json TEXT;

-- Verify the column was added
SELECT name, type FROM pragma_table_info('responses') WHERE name = 'raw_response_json';
