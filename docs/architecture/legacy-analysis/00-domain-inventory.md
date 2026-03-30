# V1 (Legacy) Domain Inventory

**Document ID:** `docs/architecture/legacy-analysis/00-domain-inventory.md`
**Date:** 2026-03-29
**Status:** Complete

---

## Overview

This document provides a complete inventory of all functional domains discovered in the V1 (legacy) codebase located in `src_legacy/`.

**V1 Entry Point:** `src_legacy/main.py` — `BenchmarkRunner` class

---

## Directory Structure

```
src_legacy/
├── main.py                 # Main entry point (BenchmarkRunner)
├── __init__.py             # Package initialization
├── api/                    # External API integration
├── cli/                    # Command-line interface
├── core/                   # Core execution logic
├── db/                     # Database layer
└── utils/                  # Cross-cutting utilities
```

---

## Domain 1: Execution Core

**Location:** `src_legacy/core/`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `execution_engine.py` | Pure execution engine (NO DB access). Executes ExecutionPlan, makes API calls, returns ExecutionResult list |
| `execution_plan.py` | Immutable data structures: ExecutionPlan, PlanRun, PlanItem, PlanVariant, ExecutionResult |
| `planner.py` | Builds ExecutionPlan from database state. Read-only. Deduplicates items, resolves seeds/prompts |
| `result_writer.py` | ONLY component with DB write access. Persists ExecutionResult to responses/errors tables. Calculates `needs_review` |
| `answer_parser.py` | Hierarchical pattern matching for answer extraction. Confidence levels: clear, ambiguous, no_answer, low_confidence |
| `variant_config.py` | Model variant identity management. Generates variant_id (hash-based) and variant_signature (human-readable) |
| `randomizer.py` | Answer option randomization with seed support |
| `run_manager.py` | Benchmark lifecycle management (run creation, completion) |
| `filter.py` | Filtering logic for execution scope |
| `loader.py` | Data loading utilities |

### Key Design Principles

- **ExecutionEngine**: NO database access, pure execution only
- **Planner**: Read-only, builds immutable ExecutionPlan
- **ResultWriter**: ONLY DB write component, calculates `needs_review` before INSERT
- **ExecutionPlan**: Immutable, self-contained, serializable

---

## Domain 2: Logging System

**Location:** `src_legacy/utils/logging_config.py`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `logging_config.py` | Comprehensive logging with rotating file handlers, structured formatting, multiple log levels |

### Features

- Root logger configuration with file + console handlers
- RotatingFileHandler with automatic flushing (10MB, 5 backups)
- Hierarchical logger structure (`logging.getLogger(__name__)`)
- Component-specific loggers via `get_structured_logger(component)`
- Initialization summary logging with execution context
- Multi-level log depth (DEBUG to CRITICAL)

### Log Format

```
%(asctime)s - %(levelname)s - %(name)s - %(message)s
```

---

## Domain 3: CLI System

**Location:** `src_legacy/cli/`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `cli.py` | CLI argument parsing, CLIParser class |
| `experiment_commands.py` | Experiment management commands (create, add-model, add-questions, create-run) |
| `review_ui.py` | Manual review interface for ambiguous responses |
| `output_formatter.py` | Console output formatting |
| `statistics.py` | Statistics calculation |

### Commands Supported

- `--create-experiment <name>` — Create new experiment
- `--experiment <name>` — Show experiment details
- `--add-model` — Add models to experiment
- `--add-questions` — Add questions to experiment (evolution)
- `--remove-model` — Remove model from experiment
- `--create-run <name>` — Create new run
- `--run <name>` — Show run details
- `--execute` — Execute run
- `--review-experiment` — Manual review by experiment
- `--review-run` — Manual review by run
- `--review-all` — Manual review all pending
- `--export-results` — Export results as JSON

### Configuration Hierarchy

```
CLI > .env > experiment config > run/model_variant config > system defaults
```

---

## Domain 4: Review UI (Manual Review)

**Location:** `src_legacy/cli/review_ui.py`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `review_ui.py` | Interactive CLI interface for manual answer classification |

### Features

- Groups pending responses by question
- Displays question stem, options, and LLM response
- Keyboard shortcuts: A/B/C/D/N/E/S/Q/Z
- Progress tracking and statistics
- Incremental database saves
- Undo functionality (Z key)

### Review Fields

| Field | Set By | Purpose |
|-------|--------|---------|
| `parse_confidence` | ExecutionEngine | Parser confidence level |
| `needs_review` | ResultWriter (derived) | Flag for human review |
| `manual_answer` | Reviewer | Human-corrected answer |

### Classification Logic

```python
needs_review = (
    parse_confidence != 'clear'
    OR selected_answer IS NULL
)
```

---

## Domain 5: Database Layer

**Location:** `src_legacy/db/`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `schema.py` | DatabaseManager class, schema loading, connection management |
| `schema.sql` | SQL schema definition (CREATE TABLE statements) |
| `models.py` | Data model classes (Response, Error, Experiment, Run, ModelVariant, QuestionSnapshot) |
| `repository.py.old` | Repository pattern (OLD version) |

### Tables (from schema.sql)

- `experiments` — Experiment definitions with frozen config
- `runs` — Execution runs within experiments
- `model_variants` — Model configurations
- `question_snapshots` — Immutable question snapshots
- `responses` — Execution results
- `errors` — Execution failures
- `experiment_models` — Experiment-model associations

### Database Principles

- Append-only for results
- Immutable for identity (experiments, snapshots, variants)
- Auditable by design
- Foreign key support enabled

---

## Domain 6: Configuration System

**Location:** `src_legacy/utils/`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `config.py` | Pydantic-based Settings class, environment variable loading |
| `config_hierarchy.py` | Configuration resolution hierarchy, null semantics |

### Configuration Keys

**EXPERIMENT keys (1):**
- `QUESTIONS_DATASET_PATH`

**MODEL keys (10):**
- `BASE_URL`, `MODEL_MAX_TOKENS_REASONING`, `MODEL_MAX_TOKENS_TOTAL`
- `MODEL_REASONING_EFFORT`, `MODEL_REPEAT_PENALTY`
- `MODEL_TEMPERATURE`, `MODEL_TOP_K`, `MODEL_TOP_P`
- `MODEL_VISION`, `STRUCTURED_OUTPUTS`

**RUN keys (3):**
- `RUN_RESPONSES_SEED`, `SYSTEM_PROMPT`, `USER_PROMPT`

### Null Semantics

- `None` = "not specified, use fallback"
- `EXPLICIT_NULL` = "explicitly null, DO NOT use fallback"
- `null` string from CLI → converted to `EXPLICIT_NULL`

### Resolution Order

```
CLI > .env > experiment config > run/model_variant config > system defaults
```

---

## Domain 7: Error Handling

**Location:** `src_legacy/core/`, `src_legacy/api/`

### Files and Responsibilities

| File | Purpose |
|------|---------|
| `error_collector.py` | Error collection and tracking |
| `api/error_handler.py` | API-specific error handling |
| `api/retry.py` | Retry logic for API calls |

### Error Types

- `timeout` — API timeout
- `http_429` — Rate limit exceeded
- `http_5xx` — Server errors
- `network_error` — Connection failures
- `authentication_error` — Auth failures
- `parse_error` — Response parsing failures
- `api_error` — General API errors

### Retry Behavior

- Configurable max attempts
- Applied per execution item
- Tracked in ExecutionResult.attempt_count

---

## Domain 8: Answer Parsing

**Location:** `src_legacy/core/answer_parser.py`

### Pattern Hierarchy

**EXPLICIT PATTERNS (clear confidence):**
- `resposta: [A-D]`
- `answer: [A-D]`
- `alternativa correta é [A-D]`
- `correta é [A-D]`

**CONTEXT PATTERNS (clear confidence):**
- `a resposta é [A-D]`
- `the correct answer is [A-D]`
- `opção [A-D]`
- `letra [A-D]`
- `alternativa [A-D]`

**STRUCTURAL PATTERNS (clear confidence):**
- `**[A-D]**` (Markdown bold)
- `[A-D]:` at line start
- `[A-D])` at line start
- `([A-D])` at line start

**FALLBACK (low_confidence):**
- Any isolated A-D letter

### Confidence Levels

| Level | Meaning | Action |
|-------|---------|--------|
| `clear` | Single high-confidence match | No review needed |
| `ambiguous` | Multiple different letters found | Review required |
| `no_answer` | No letter patterns found | Review required |
| `low_confidence` | Only fallback pattern matched | Review recommended |

### Edge Cases Handled

- Portuguese/Spanish articles filtered ("A resposta" → not counted as answer A)
- Repeated same letter → clear confidence
- Multiple different letters → ambiguous
- Markdown variations supported
- Case insensitivity
- Reasoning model text separation

---

## Cross-Cutting Concerns

### Utils Module (`src_legacy/utils/`)

| File | Purpose | Used By |
|------|---------|---------|
| `answer_schema.py` | JSON schema for structured outputs | ExecutionEngine |
| `image_handler.py` | Image loading for vision-enabled questions | ExecutionEngine |
| `progress.py` | Progress tracking utilities | CLI, ExecutionEngine |

### API Module (`src_legacy/api/`)

| File | Purpose |
|------|---------|
| `client.py` | OpenRouter API client, MessageBuilder |
| `error_handler.py` | API error classification |
| `retry.py` | Retry logic |
| `model_capabilities.py` | Model capability detection |
| `parser.py` | API response parsing |

---

## V1 Execution Flow

```
CLI (main.py)
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

**Total Domains Identified:** 8 (matches initial list)

1. ✅ **Execution Core** — execution_engine.py, planner.py, result_writer.py, execution_plan.py
2. ✅ **Logging System** — logging_config.py
3. ✅ **CLI System** — cli/, experiment_commands.py
4. ✅ **Review UI** — review_ui.py
5. ✅ **Database Layer** — db/, schema.sql, models.py
6. ✅ **Configuration System** — config.py, config_hierarchy.py
7. ✅ **Error Handling** — error_collector.py, api/error_handler.py, retry.py
8. ✅ **Answer Parsing** — answer_parser.py

**No additional domains discovered beyond the initial 8.**

---

## Notes

- V1 is a complete, working implementation
- Architecture is well-documented in code docstrings
- Separation of concerns is clear (ExecutionEngine has NO DB access)
- ResultWriter is the ONLY DB write component
- Configuration hierarchy is explicit and documented
- Manual review workflow is fully implemented
