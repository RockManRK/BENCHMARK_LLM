# V2 (Current) Domain Inventory

**Document ID:** `docs/architecture/v2-current/00-domain-inventory.md`
**Date:** 2026-03-29
**Status:** Complete

---

## Overview

This document provides a complete inventory of all functional domains discovered in the V2 (current) codebase located in `src/`.

**V2 Entry Point:** `src/cli/bcllm_main.py` — New CLI paradigm (experiment-based)

---

## Directory Structure

```
src/
├── __init__.py             # Package initialization (v2.0.0)
├── api/                    # External API integration
├── cli/                    # Command-line interface (new paradigm)
├── core/                   # Core execution logic
├── db/                     # Database layer
├── review/                 # Manual review interface (extracted from cli/)
├── utils/                  # Cross-cutting utilities
└── validators/             # Input validation (NEW)
```

---

## Domain 1: Execution Core

**Location:** `src/core/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `execution_engine.py` | Pure execution engine (NO DB access). Executes ExecutionPlan, makes API calls, returns ExecutionResult list | ✅ Implemented |
| `execution_plan.py` | Immutable data structures: ExecutionPlan, PlanRun, PlanItem, PlanVariant, ModelConfig, QuestionPayload, Prompts, RetryPolicy | ✅ Implemented |
| `planner.py` | Builds ExecutionPlan from database state. Read-only. Deduplicates items, resolves seeds/prompts | ✅ Implemented |
| `result_writer.py` | ONLY component with DB write access. Persists ExecutionResult to responses/errors tables. Calculates `needs_review` | ✅ Implemented |
| `answer_parser.py` | Answer parsing with confidence levels | ⚠️ Present (needs verification) |
| `randomizer.py` | Answer option randomization with seed support | ⚠️ Present (needs verification) |
| `config_resolver.py` | Centralized configuration resolution. CLI > .env > system defaults > NULL | ✅ Implemented |
| `null_semantics.py` | EXPLICIT_NULL sentinel for distinguishing "not specified" vs "explicitly null" | ✅ Implemented |
| `mode.py` | Execution mode definitions | ⚠️ Present |
| `mode_matrix.py` | Mode configuration matrix | ⚠️ Present |
| `mode_resolver.py` | Mode resolution logic | ⚠️ Present |
| `argv_utils.py` | Argument utilities | ⚠️ Present |
| `module_resolver.py` | Module resolution utilities | ⚠️ Present |
| `question_loader.py` | Question loading utilities | ⚠️ Present |

### Key Design Principles (Same as V1)

- **ExecutionEngine**: NO database access, pure execution only
- **Planner**: Read-only, builds immutable ExecutionPlan
- **ResultWriter**: ONLY DB write component, calculates `needs_review`
- **ExecutionPlan**: Immutable, self-contained, serializable

### V2 Improvements over V1

1. **Explicit Null Semantics**: `EXPLICIT_NULL` sentinel for CLI null handling
2. **Centralized Config Resolution**: `ConfigResolver` class for all configuration
3. **Type-Specific ModelConfig**: Dedicated dataclass for model configuration
4. **RetryPolicy**: Explicit retry policy in ExecutionPlan

---

## Domain 2: Logging System

**Location:** `src/utils/` — **NOT YET IMPLEMENTED**

### Status

| File | Status |
|------|--------|
| `logging_config.py` | ❌ Missing (needs to be migrated from V1) |

### Gap

V2 does NOT have a dedicated logging configuration module. This is a **critical gap** that needs to be addressed.

**Recommendation:** Migrate `src_legacy/utils/logging_config.py` to `src/utils/logging_config.py` with V2 adaptations.

---

## Domain 3: CLI System

**Location:** `src/cli/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `bcllm_main.py` | New CLI entry point (experiment-based paradigm) | ✅ Implemented |
| `bcllm_experiment.py` | Experiment management commands | ✅ Implemented |
| `bcllm_model.py` | Model variant commands | ✅ Implemented |
| `bcllm_questions.py` | Question snapshot commands | ✅ Implemented |
| `bcllm_run.py` | Run management commands | ✅ Implemented |
| `bcllm_execute.py` | Execution commands | ✅ Implemented |
| `bcllm_review.py` | Review commands | ✅ Implemented |
| `database.py` | Database utilities for CLI | ⚠️ Present |

### New CLI Paradigm

V2 uses a **command-per-module** approach instead of V1's monolithic `main.py`:

```bash
# Old V1
python -m src.main --create-experiment my_exp

# New V2
python -m src.cli.bcllm_main --create-experiment my_exp
```

### Commands Supported

- `--create-experiment <name>` — Create new experiment
- `--list-experiment` — List all experiments
- `--experiment <name>` — Show experiment details
- `--remove-experiment <name>` — Remove experiment
- `--add-model <model_id>` — Add model to experiment
- `--list-model` — List models in experiment
- `--model <model_id>` — Show model details
- `--remove-model <model_id>` — Remove model from experiment
- `--add-questions [spec]` — Add questions to experiment
- `--list-questions` — List questions in experiment
- `--create-run <name>` — Create new run
- `--list-run` — List runs in experiment
- `--run <name>` — Show run details
- `--remove-run <name>` — Remove run
- `--execute` — Execute run

---

## Domain 4: Review UI (Manual Review)

**Location:** `src/review/` — **EXTRACTED from cli/**

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `review_ui.py` | Interactive CLI interface for manual answer classification (Rich-based) | ✅ Implemented |
| `__init__.py` | Package initialization | ✅ Present |

### V2 Improvements over V1

1. **Separated Module**: Review UI extracted from `cli/` to dedicated `review/` module
2. **Rich Library**: Uses Rich library for better terminal UI
3. **Cleaner Architecture**: Separation of concerns (review is not a CLI command)

### Review Fields (Same as V1)

| Field | Set By | Purpose |
|-------|--------|---------|
| `parse_confidence` | ExecutionEngine | Parser confidence level |
| `needs_review` | ResultWriter (derived) | Flag for human review |
| `manual_answer` | Reviewer | Human-corrected answer |

---

## Domain 5: Database Layer

**Location:** `src/db/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `schema.py` | Database schema definitions | ✅ Implemented |
| `models.py` | Data model classes | ✅ Implemented |
| `repository.py` | Repository pattern for data access | ✅ Implemented |
| `repository.py.txt` | Repository reference (text file) | ⚠️ Reference only |

### V2 Improvements over V1

1. **Cleaner Repository Pattern**: Better separation of data access logic
2. **Updated Schema**: Aligned with V2 ExecutionPlan structure
3. **Type Hints**: Better type annotations throughout

---

## Domain 6: Configuration System

**Location:** `src/core/`, `src/utils/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `config_resolver.py` | Centralized configuration resolution | ✅ Implemented |
| `null_semantics.py` | EXPLICIT_NULL sentinel for null handling | ✅ Implemented |

### V2 Improvements over V1

1. **Explicit Null Semantics**: Clear distinction between `None` and `EXPLICIT_NULL`
2. **Centralized Resolution**: Single `ConfigResolver` class for all configuration
3. **Better Documentation**: Inline documentation of resolution order
4. **Type-Safe Parsing**: Dedicated parser functions for int/float/bool

### Configuration Resolution Order

```
CLI > .env > system defaults > NULL
```

### Null Semantics

```python
from src.core.null_semantics import EXPLICIT_NULL

# None = "not specified, use fallback"
value = None  # Will use .env or default

# EXPLICIT_NULL = "explicitly null, DO NOT use fallback"
value = EXPLICIT_NULL  # Will use NULL, no fallback
```

---

## Domain 7: Error Handling

**Location:** `src/api/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `errors.py` | Error type definitions | ✅ Implemented |
| `retry.py` | Retry logic for API calls | ✅ Implemented |

### Error Types (from execution_engine.py)

- `timeout` — API timeout
- `http_429` — Rate limit exceeded
- `http_5xx` — Server errors
- `network_error` — Connection failures
- `authentication_error` — Auth failures
- `parse_error` — Response parsing failures
- `api_error` — General API errors
- `config_error` — Configuration errors (NEW in V2)

### V2 Improvements

1. **Explicit Error Classification**: `_classify_error()` method in ExecutionEngine
2. **RetryPolicy Dataclass**: Explicit retry policy in ExecutionPlan
3. **Attempt Tracking**: `attempt_count` tracked in ExecutionResult

---

## Domain 8: Answer Parsing

**Location:** `src/core/answer_parser.py`

### Status

| File | Status |
|------|--------|
| `answer_parser.py` | ⚠️ Present (needs verification against V1) |

### Expected Features (from V1)

- Hierarchical pattern matching (explicit → context → structural → fallback)
- Confidence levels: clear, ambiguous, no_answer, low_confidence
- Portuguese/Spanish article filtering
- Markdown pattern support

**Note:** Full verification of V2 answer_parser.py needed to confirm feature parity with V1.

---

## Domain 9: Validation (NEW in V2)

**Location:** `src/validators/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `model_id_validator.py` | Model ID validation | ✅ Implemented |
| `__init__.py` | Package initialization | ✅ Present |

### Purpose

This is a **NEW domain** not present in V1. It provides:

- Input validation for model IDs
- Validation utilities for CLI arguments
- Schema validation for configuration

### V2 Principle

**Validation is explicit and early** — validate inputs before they reach the execution core.

---

## Domain 10: Variant Configuration

**Location:** `src/utils/`

### Files and Responsibilities

| File | Purpose | Status |
|------|---------|--------|
| `variant_signature.py` | Model variant signature generation | ✅ Implemented |

### Purpose

Handles model variant identity management:
- `variant_id` generation (hash-based)
- `variant_signature` generation (human-readable)

**Note:** In V1, this was in `src_legacy/core/variant_config.py`. In V2, it's been moved to `utils/`.

---

## Cross-Cutting Concerns

### Utils Module (`src/utils/`)

| File | Purpose | Status |
|------|---------|--------|
| `variant_signature.py` | Variant signature generation | ✅ Implemented |
| `logging_config.py` | ❌ MISSING (needs migration from V1) |

### API Module (`src/api/`)

| File | Purpose | Status |
|------|---------|--------|
| `client.py` | OpenRouter API client | ⚠️ Present (needs verification) |
| `errors.py` | Error type definitions | ✅ Implemented |
| `retry.py` | Retry logic | ✅ Implemented |

---

## V2 Execution Flow (Same as V1)

```
CLI (bcllm_main.py)
    ↓
Planner (builds ExecutionPlan from DB)
    ↓
ExecutionPlan (immutable data structure)
    ↓
ExecutionEngine (pure execution, NO DB)
    ↓
ExecutionResult list (pure data)
    ↓
ResultWriter (ONLY DB write component)
    ↓
Database (responses, errors tables)
```

---

## Summary

**Total Domains Identified:** 10 (2 NEW domains beyond initial 8)

1. ✅ **Execution Core** — execution_engine.py, planner.py, result_writer.py, execution_plan.py, config_resolver.py, null_semantics.py
2. ❌ **Logging System** — **MISSING** (needs migration from V1)
3. ✅ **CLI System** — cli/bcllm_*.py (new command-per-module paradigm)
4. ✅ **Review UI** — review/review_ui.py (extracted from cli/)
5. ✅ **Database Layer** — db/schema.py, models.py, repository.py
6. ✅ **Configuration System** — core/config_resolver.py, null_semantics.py
7. ✅ **Error Handling** — api/errors.py, retry.py
8. ⚠️ **Answer Parsing** — core/answer_parser.py (needs verification)
9. 🆕 **Validation** — validators/ (NEW domain)
10. 🆕 **Variant Configuration** — utils/variant_signature.py (moved from core/)

---

## Gaps Identified

### Critical Gaps

| Domain | Gap | Severity |
|--------|-----|----------|
| Logging System | `logging_config.py` missing | **HIGH** |
| Answer Parsing | Feature parity with V1 unverified | **MEDIUM** |
| API Client | `client.py` implementation unverified | **MEDIUM** |

### New Domains in V2

| Domain | Purpose |
|--------|---------|
| Validation | Input validation for model IDs and CLI arguments |
| Variant Configuration | Variant identity management (moved from core) |

---

## V2 Architecture Improvements over V1

1. **Explicit Null Semantics** — Clear distinction between "not specified" and "explicitly null"
2. **Centralized Config Resolution** — Single `ConfigResolver` class
3. **Separated Review UI** — Extracted from `cli/` to dedicated `review/` module
4. **Command-per-Module CLI** — Better separation of CLI concerns
5. **Validation Layer** — New `validators/` module for input validation
6. **Better Type Hints** — More explicit type annotations throughout
7. **RetryPolicy Dataclass** — Explicit retry policy in ExecutionPlan

---

## Notes

- V2 is **incomplete** compared to V1
- Core execution architecture is well-implemented
- Logging system is **missing** and needs migration
- CLI paradigm has changed (experiment-based, no immediate execution)
- Review UI has been extracted to its own module
- New validation domain added
- Configuration resolution is more explicit and type-safe
