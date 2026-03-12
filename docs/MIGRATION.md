# Migration Guide - Benchmark LLM v2.0

This guide documents the breaking changes and migration path for upgrading to Benchmark LLM v2.0 with the new experiment tracking system.

## Overview

Version 2.0 introduces a complete redesign of the database schema and execution model to support:
- **Three execution modes**: Test, Dev, and Experiment
- **Frozen configurations** for reproducible experiments
- **Simplified data model** with better auditability

## ⚠️ Breaking Changes

### Database Schema

**The new schema is NOT backward compatible.** Existing databases cannot be migrated and must be recreated.

#### Removed Tables
- `iterations` - Iteration number is now a field in `responses`
- `operational_logs` - Logs are written to files only

#### Modified Tables
- `runs` - Completely redesigned
  - Removed: `created_at`, `config`
  - Added: `experiment_id`, `seed`, `is_dev`, `finished_at`

- `models` - Simplified structure
  - Removed: `context_length`, `max_completion_tokens`
  - Added: `supports_multimodal`, `metadata_json`, `created_at`

- `responses` - Major changes
  - Removed: `iteration_id`, `question_text`, `options_json`, `options_randomized`, `correct_answer`, `reasoning_details`
  - Added: `iteration` (integer field)
  - Changed: Foreign keys now reference new schema

- `errors` - Decoupled from responses
  - Removed: `response_id` (required)
  - Added: `run_id`, `question_id`, `model_id` (all optional)

#### New Tables
- `experiments` - Experiment tracking with frozen configuration
- `questions` - Question persistence for reproducibility

---

## Version 1.1.0 Changes (Consolidação de Tokens)

### Schema Changes

#### Column Renamed
- `output_tokens` → `response_tokens` (semantically more accurate)

**Migration:**
```sql
-- Data is automatically migrated using:
-- response_tokens = COALESCE(response_tokens, output_tokens)
```

#### New Column
- `effective_tokens` - Total computational cost (input + response + reasoning)

#### Changed Default
- `parse_confidence` DEFAULT changed from `'clear'` to `'unknown'` (more conservative)

### Token Calculation Formulas (Documented)

```
total_tokens = input_tokens + response_tokens
effective_tokens = input_tokens + response_tokens + reasoning_tokens
```

**Important:** `reasoning_tokens` are a **subtype** of `response_tokens`, not additional.

### Code Changes

#### Response Model
```python
# Before (v1.0.x)
response = Response(
    input_tokens=100,
    output_tokens=50,  # OLD NAME
    total_tokens=150,
)

# After (v1.1.0)
response = Response(
    input_tokens=100,
    response_tokens=50,  # NEW NAME
    total_tokens=150,
    effective_tokens=160,  # NEW (includes reasoning)
)
```

#### Token Extraction (Consolidated)
```python
# Before (v1.0.x) - Multiple locations
input_tokens = usage.get("prompt_tokens", 0)
output_tokens = usage.get("completion_tokens", 0)
reasoning_tokens = self._extract_reasoning_tokens(usage)

# After (v1.1.0) - Single consolidated method
tokens = self._extract_token_usage(api_response)
# Returns: {
#   "input_tokens": 100,
#   "response_tokens": 50,
#   "total_tokens": 150,
#   "reasoning_tokens": 10,
#   "effective_tokens": 160,
#   "cost": 0.0012
# }
```

### Logging Changes

#### Structured Token Logging
```
# Before (v1.0.x)
INFO - Token usage: model=gpt-4, input=100, output=50, total=150

# After (v1.1.0) - Structured format
INFO - Token usage | model=gpt-4 | question=Q001 | input=100 | response=50 | reasoning=10 | total=150 | effective=160
```

### Migration Script

For existing databases, run the migration script:

```bash
# Backup first
sqlite3 data/benchmark.db ".backup 'data/benchmark_backup.db'"

# Run migration
sqlite3 data/benchmark.db < migrations/001_remove_output_tokens.sql
```

The migration script:
1. Creates a backup table `responses_backup`
2. Creates new `responses_new` table with updated schema
3. Migrates data with `response_tokens = COALESCE(response_tokens, output_tokens)`
4. Drops old table and renames new one
5. Rebuilds all indexes

### Backward Compatibility

The code maintains backward compatibility in the parsing layer:
```python
# Fallback for old data
tokens = {
    "input_tokens": parsed.get("input_tokens", 0),
    "response_tokens": parsed.get("response_tokens", parsed.get("output_tokens", 0)),
    # ...
}
```

---

### Execution Model

#### Test Mode
**Before:**
```bash
python -m src.main --models gpt-4 --test-mode
```

**After:**
```bash
python -m src.main --models gpt-4 --mode test
# OR (backward compatible)
python -m src.main --models gpt-4 --test-mode
```

#### Dev Mode (Default)
**Before:**
```bash
python -m src.main --models gpt-4
```

**After:**
```bash
python -m src.main --models gpt-4
# Same command, now explicitly defaults to --mode dev
```

#### Experiment Mode (NEW)
```bash
python -m src.main --models gpt-4,claude-3 --mode experiment --experiment my_study
```

### API Changes

#### RunManager

**Before:**
```python
from src.db.repository import RunManager

run_manager = RunManager(db_manager)
run = run_manager.initialize_run(config={"models": ["gpt-4"]})
```

**After:**
```python
from src.core.run_manager import RunManager
from src.utils.config import Settings

settings = get_settings()
run_manager = RunManager(db_manager, settings)
run = run_manager.initialize_run(config={"models": ["gpt-4"], "seed": 42})
```

#### Response Model

**Before:**
```python
from src.db.models import Response

response = Response(
    iteration_id=1,
    question_id="Q001",
    model_id="gpt-4",
    run_id="run-123",
    question_text="What is...?",
    options_json='{"A": "..."}',
    # ...
)
```

**After:**
```python
from src.db.models import Response

response = Response(
    run_id="run-123",
    question_id="Q001",
    model_id="gpt-4",
    iteration=1,  # Now an integer, not a foreign key
    selected_answer="A",
    response_text="The answer is...",
    is_correct=True,
    # ...
)
```

### Repository Changes

#### New Repositories
- `ExperimentRepository` - Experiment CRUD operations
- `QuestionRepository` - Question persistence

#### Removed Repositories
- `IterationRepository` - No longer needed (iterations are fields)

#### Modified Repositories
- `RunRepository` - Updated for new schema
- `ResponseRepository` - Updated for new schema
- `ModelRepository` - Updated for new schema
- `ErrorRepository` - Updated for new schema

## Migration Steps

### Step 1: Backup Existing Data (if needed)

If you have existing benchmark data you want to preserve:

```bash
# Export existing data to JSON/CSV before upgrading
python scripts/export_data.py --output backup.json
```

**Note:** No export script is provided in v2.0. If you need to preserve data, you must create a custom export script using the old codebase.

### Step 2: Update Code

1. **Update imports:**
```python
# Old
from src.db.models import Iteration, OperationalLog

# New
from src.db.models import Experiment
# (Iteration and OperationalLog removed)
```

2. **Update Response creation:**
```python
# Old
response = Response(iteration_id=iteration_id, question_text=..., options_json=...)

# New
response = Response(run_id=run_id, question_id=question_id, iteration=iteration_number, ...)
```

3. **Update RunManager initialization:**
```python
# Old
run_manager = RunManager(db_manager)

# New
run_manager = RunManager(db_manager, settings)
```

### Step 3: Recreate Database

Delete existing database and let the schema be recreated:

```bash
# Delete old database
rm data/benchmark.db

# Run benchmark (schema will be created automatically)
python -m src.main --models gpt-4 --mode dev
```

### Step 4: Update Scripts

If you have custom scripts that query the database:

1. **Update SQL queries** for new schema
2. **Replace `iteration_id` with `iteration`** in queries
3. **Remove references to `operational_logs`** table
4. **Add `experiment_id` joins** if needed

Example query migration:

**Before:**
```sql
SELECT r.*, i.iteration_number
FROM responses r
JOIN iterations i ON r.iteration_id = i.iteration_id
WHERE r.run_id = ?
```

**After:**
```sql
SELECT r.*, r.iteration as iteration_number
FROM responses r
WHERE r.run_id = ?
```

## New Features

### Execution Modes

#### Test Mode
```bash
python -m src.main --models gpt-4 --mode test
```
- In-memory database
- No data persistence
- Useful for validation and testing

#### Dev Mode (Default)
```bash
python -m src.main --models gpt-4
```
- Full persistence
- No experiment tracking
- `is_dev = true` in runs

#### Experiment Mode
```bash
python -m src.main --models gpt-4,claude-3 \
  --mode experiment \
  --experiment comparative_study \
  --seed 42
```
- Full persistence
- Frozen configuration
- Experiment tracking
- Reproducible runs

### Configuration Freeze

In experiment mode, configuration is frozen and hashed:

```python
settings = get_settings()
config_hash = settings.get_config_hash()
# Hash is stored in experiments table
```

### Improved Logging

Initialization now includes structured logging:

```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : EXPERIMENT
Experiment          : comparative_study
Persist data        : YES
Configuration       : FROZEN (config_hash=8f3a9c2e)
System prompt       : DEFAULT
Seed                : 42
Models              : gpt-4, claude-3
Questions           : Q001-Q100 (100 questions)
============================================================
```

## Troubleshooting

### Error: "Experiment name required for experiment mode"

**Cause:** Using `--mode experiment` without `--experiment <name>`

**Solution:**
```bash
python -m src.main --models gpt-4 --mode experiment --experiment my_study
```

### Error: "cannot import name 'Iteration'"

**Cause:** Old code importing removed classes

**Solution:**
```python
# Remove this line:
from src.db.models import Iteration

# Update code to use iteration number field instead
```

### Error: "table iterations does not exist"

**Cause:** Old SQL queries or code referencing removed table

**Solution:** Update queries to use `responses.iteration` field instead of joining with `iterations` table.

### Database locked errors

**Cause:** Old database with incompatible schema

**Solution:**
```bash
# Delete old database
rm data/benchmark.db

# Re-run benchmark
python -m src.main --models gpt-4
```

## Rollback Plan

If you need to rollback to v1.x:

1. **Keep v2.0 code separate:**
```bash
# Rename current directory
mv benchmark_llm benchmark_llm-v2

# Clone or restore v1.x
git checkout <v1.x-tag>
```

2. **Database incompatibility:**
   - v2.0 cannot read v1.x databases
   - v1.x cannot read v2.0 databases
   - Maintain separate data directories

## Support

For issues or questions:
1. Check the [SCHEMA.md](docs/SCHEMA.md) documentation
2. Review the [README.md](README.md) for usage examples
3. Open an issue on the repository

---

**Last updated:** 2026-03-07  
**Version:** 2.0.0
