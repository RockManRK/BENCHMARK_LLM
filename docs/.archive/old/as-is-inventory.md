# AS-IS Inventory — Phase 2

**Session**: refactoring-2026-03-19
**Phase**: 2/11
**Date**: 2026-03-20

---

## Executive Summary

**Total Files Analyzed**: 36 Python source files (excluding tests)
**Total LOC Estimate**: ~8,500 lines
**Main Structural Issues**:
1. Mixed architecture patterns (legacy iteration-based + new experiment-based coexisting)
2. Two critically oversized files: `src/main.py` (1,379 lines), `src/cli/experiment_commands.py` (1,506 lines)
3. Database schema partially aligned with TO-BE contracts, partially legacy
4. CLI layer has both old (--models, --iterations) and new (--experiment, --create-run) paradigms
5. Execution flow follows TO-BE architecture (Planner → ExecutionEngine → ResultWriter) but legacy code paths remain

**Architecture Status**: Transition state — new execution axis implemented but legacy paths not removed

---

## Module Inventory

### Entry Point
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `bcllm.py` | 50 | CLI entry point, delegates to `src.main:main()` | None | Thin wrapper, appropriate |
| `src/main.py` | 1,379 | Main orchestrator (`BenchmarkRunner`), CLI routing, execution flow | `main()`, `BenchmarkRunner.run()`, `_handle_*` methods | **Violates SRP**: 1,379 lines, 20+ handler methods, mixes CLI routing with business logic, direct DB access in handlers |

### CLI Layer (`src/cli/`)
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `cli.py` | 670 | Argument parsing with argparse | `CLIParser`, `parse_arguments()`, `_expand_question_ranges()` | **Oversized**: 670 lines, complex validation logic, metadata parsing, question range expansion |
| `experiment_commands.py` | 1,506 | Experiment/run management commands | `ExperimentManager`, `RunManager`, `handle_experiment_command()` | **Critically oversized**: 1,506 lines, mixes DB operations with UI formatting, legacy iteration concept still present |
| `output_formatter.py` | ~200 | Console/JSON/CSV/Markdown output | `ConsoleFormatter`, `OutputFormatter`, `create_formatter()` | Appropriate size, single responsibility |
| `review_ui.py` | ~400 | Manual review terminal UI | `ReviewUI`, `start_review_by_experiment()` | Uses Rich for terminal UI, appropriate for use case |
| `statistics.py` | ~150 | Statistics calculation | `StatisticsCalculator` | Appropriate size |

### Core Layer (`src/core/`)
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `planner.py` | 350 | Builds immutable ExecutionPlan from DB state | `build_plan()`, `_resolve_*`, `_build_plan_run()` | **Good alignment**: Follows contract, read-only in cycle, appropriate size |
| `execution_engine.py` | 550 | Executes ExecutionPlan via API calls | `execute()`, `_execute_item()`, `_parse_api_response()` | **Mixed**: NO DB access (correct), but 550 lines with prompt building + API calls + parsing |
| `result_writer.py` | 400 | Persists ExecutionResult to DB | `write_results()`, `_write_response()`, `_update_run_status()` | **Good alignment**: Follows contract, calculates `needs_review`, idempotent writes |
| `execution_plan.py` | 250 | Immutable data structures | `ExecutionPlan`, `PlanRun`, `PlanItem`, `ExecutionResult` | **Good alignment**: Dataclasses match contract |
| `randomizer.py` | 200 | Answer option randomization (Fisher-Yates) | `AnswerRandomizer`, `randomize_options()` | Appropriate size, single responsibility |
| `answer_parser.py` | 450 | Parses LLM response to extract answer letter | `AnswerParser`, `parse()`, hierarchical pattern matching | **Oversized**: 450 lines, complex regex hierarchy, but well-documented |
| `loader.py` | ~150 | Loads questions from JSON | `QuestionLoader` | Appropriate size |
| `filter.py` | ~150 | Question metadata filtering | `QuestionFilter` | Appropriate size |
| `run_manager.py` | ~400 | Legacy run lifecycle (iterations) | `RunManager`, `initialize_run()`, `add_models_to_run()` | **Legacy**: Uses iteration concept, being replaced by new execution flow |
| `variant_config.py` | ~150 | Model variant identity building | `VariantConfigBuilder` | Appropriate size |
| `error_collector.py` | ~100 | Error aggregation | `ErrorCollector` | Appropriate size |

### API Layer (`src/api/`)
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `client.py` | 500 | OpenRouter API client | `OpenRouterClient`, `chat_completion()`, `MessageBuilder` | **Oversized**: 500 lines, but appropriate complexity (HTTP client + multimodal support) |
| `error_handler.py` | ~150 | API error classification | `APIErrorHandler` | Appropriate size |
| `parser.py` | ~100 | API response parsing | `parse_response()` | Appropriate size |
| `retry.py` | ~150 | Retry logic | `RetryHandler` | Appropriate size |
| `model_capabilities.py` | ~200 | Model feature detection | `ModelCapabilities` | Appropriate size |

### Database Layer (`src/db/`)
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `models.py` | 450 | Dataclasses for DB entities | `Experiment`, `Run`, `ModelVariant`, `QuestionSnapshot`, `Response`, `Error` | **Good alignment**: Dataclasses match TO-BE schema, includes review fields |
| `schema.py` | 200 | DatabaseManager, schema loading | `DatabaseManager`, `get_schema_sql()` | Appropriate size |
| `schema.sql` | 250 | SQL DDL statements | CREATE TABLE statements | **Good alignment**: Matches TO-BE contracts, includes review fields |

### Utils (`src/utils/`)
| File | Lines | Purpose | Key Functions | Issues |
|------|-------|---------|---------------|--------|
| `config.py` | 730 | Pydantic settings management | `Settings`, `ExecutionMode` | **Oversized**: 730 lines, but appropriate complexity (validation, hierarchy) |
| `config_hierarchy.py` | ~200 | CLI > .env > default resolution | `resolve_with_feedback()` | Appropriate size |
| `logging_config.py` | ~200 | Logging setup | `LoggingConfig`, `setup_logging()` | Appropriate size |
| `image_handler.py` | ~150 | Image loading/validation | `ImageHandler` | Appropriate size |
| `progress.py` | ~100 | Progress bar (Rich) | `ProgressBar` | Appropriate size |
| `answer_schema.py` | ~50 | JSON schema for structured outputs | `ANSWER_SCHEMA` | Appropriate size |

---

## Entity Definitions

### Experiment
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `experiment_id` | TEXT (PK) | `models.py:Experiment`, `schema.sql` | Generated UUID |
| `name` | TEXT (UNIQUE) | `models.py:Experiment` | Human-readable |
| `description` | TEXT | `models.py:Experiment` | Optional |
| `config_json` | TEXT | `models.py:Experiment` | Frozen configuration snapshot |
| `config_hash` | TEXT | `models.py:Experiment` | SHA-256 of protocol config |
| `system_prompt_template` | TEXT | `models.py:Experiment` | Prompt template |
| `user_prompt_template` | TEXT | `models.py:Experiment` | Prompt template |
| `created_at` | TIMESTAMP | `models.py:Experiment` | Auto-generated |

### Model Variant
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `variant_id` | TEXT (PK) | `models.py:ModelVariant` | Hash-based short ID |
| `model_id` | TEXT | `models.py:ModelVariant` | Base model (e.g., "openai/gpt-4") |
| `variant_signature` | TEXT (UNIQUE) | `models.py:ModelVariant` | Human-readable identity |
| `reasoning_mode` | TEXT | `models.py:ModelVariant` | 'off', 'auto', 'effort', 'budget', 'unspecified' |
| `reasoning_effort` | TEXT | `models.py:ModelVariant` | 'xhigh', 'high', 'medium', 'low', 'minimal' |
| `max_output_tokens` | INT | `models.py:ModelVariant` | When mode='budget' |
| `vision_enabled` | BOOLEAN | `models.py:ModelVariant` | Identity field |
| `structured_output` | BOOLEAN | `models.py:ModelVariant` | Identity field |
| `web_access_enabled` | BOOLEAN | `models.py:ModelVariant` | Identity field |

### Question Snapshot
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `snapshot_id` | TEXT (PK) | `models.py:QuestionSnapshot` | Application-generated |
| `experiment_id` | TEXT (FK) | `models.py:QuestionSnapshot` | Required (NOT NULL per contract) |
| `question_id` | TEXT | `models.py:QuestionSnapshot` | Original question ID |
| `question_payload` | TEXT (JSON) | `models.py:QuestionSnapshot` | Complete question JSON |
| `created_at` | TIMESTAMP | `models.py:QuestionSnapshot` | Auto-generated |

### Run
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `run_id` | TEXT (PK) | `models.py:Run` | Generated ID |
| `experiment_id` | TEXT (FK) | `models.py:Run` | Required |
| `seed` | INTEGER | `models.py:Run` | Nullable (None = no randomization) |
| `status` | TEXT | `models.py:Run` | 'pending', 'running', 'completed', 'failed', 'partial_failed' |
| `started_at` | TIMESTAMP | `models.py:Run` | Auto-generated |
| `finished_at` | TIMESTAMP | `models.py:Run` | Nullable |

### Response
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `response_id` | TEXT (PK) | `models.py:Response` | Generated ID |
| `run_id` | TEXT (FK) | `models.py:Response` | Required |
| `variant_id` | TEXT (FK) | `models.py:Response` | Required (TO-BE) |
| `snapshot_id` | TEXT (FK) | `models.py:Response` | Required (TO-BE) |
| `model_id` | TEXT | `models.py:Response` | Base model (redundant for querying) |
| `question_id` | TEXT | `models.py:Response` | Redundant for querying |
| `selected_answer` | TEXT | `models.py:Response` | Parsed answer (A/B/C/D) |
| `response_text` | TEXT | `models.py:Response` | Full model response |
| `is_correct` | BOOLEAN | `models.py:Response` | Derived (may be NULL) |
| `parse_confidence` | TEXT | `models.py:Response` | 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence' |
| `needs_review` | BOOLEAN | `models.py:Response` | Derived by ResultWriter |
| `manual_answer` | TEXT | `models.py:Response` | Human override (optional) |

### Error
| Field | Type | Location | Notes |
|-------|------|----------|-------|
| `error_id` | TEXT (PK) | `models.py:Error` | Generated ID |
| `run_id` | TEXT (FK) | `models.py:Error` | Required |
| `variant_id` | TEXT (FK) | `models.py:Error` | Required (TO-BE) |
| `snapshot_id` | TEXT (FK) | `models.py:Error` | Required (TO-BE) |
| `error_type` | TEXT | `models.py:Error` | Classification |
| `error_message` | TEXT | `models.py:Error` | Human-readable |
| `attempt_count` | INTEGER | `models.py:Error` | Retry count |

---

## CLI Command Mapping

| Command | Handler File | Function | Validation | Side Effects |
|---------|--------------|----------|------------|--------------|
| `--create-experiment <name>` | `src/main.py` | `_handle_create_experiment()` | Name uniqueness | INSERT `experiments`, INSERT `question_snapshots` |
| `--experiment <name>` | `src/main.py` | `_handle_show_experiment()` | Experiment exists | None (read-only) |
| `--experiment <name> --add-model <model>` | `src/main.py` | `_handle_add_models_to_experiment()` | Experiment exists | INSERT `model_variants` |
| `--experiment <name> --add-questions <q>` | `src/main.py` | `_handle_add_questions_to_experiment()` | Experiment exists | INSERT `question_snapshots` (idempotent) |
| `--experiment <name> --create-run` | `src/main.py` | `_handle_create_run()` | Experiment exists | INSERT `runs` |
| `--experiment <name> --run <name> --execute` | `src/main.py` | `_handle_execute_run()` | Experiment + Run exist | INSERT `responses`, INSERT `errors`, UPDATE `runs.status` |
| `--review-experiment <name>` | `src/main.py` | `_handle_review_experiment()` | Experiment exists | None (read-only UI) |
| `--export-results <run_id>` | `src/main.py` | `_handle_export_results()` | Run exists | None (read-only JSON) |

---

## Dependency Graph

```
bcllm.py
  └── src.main:main()
        └── BenchmarkRunner
              ├── src.cli.cli:CLIParser
              ├── src.core.planner:Planner
              │     ├── src.core.execution_plan
              │     └── src.db.repository:* (read-only)
              ├── src.core.execution_engine:ExecutionEngine
              │     ├── src.api.client:OpenRouterClient
              │     ├── src.core.randomizer:AnswerRandomizer
              │     └── src.core.answer_parser:AnswerParser
              ├── src.core.result_writer:ResultWriter
              │     └── src.db.repository:* (write)
              └── src.db.schema:DatabaseManager
```

---

## Architecture Deviations

| Contract | Legacy Implementation | Deviation | Impact |
|----------|----------------------|-----------|--------|
| ExecutionPlan is immutable | ✅ Aligned | None | Low |
| ExecutionEngine has no DB access | ✅ Aligned | None | Low |
| ResultWriter calculates `needs_review` | ✅ Aligned | None | Low |
| Variants are GLOBAL | ⚠️ Partial | No experiment association table | Medium |
| Runs have no iterations | ⚠️ Partial | `RunManager` still uses iterations | Medium |
| Retry policy per-run | ❌ Missing | Not in ExecutionPlan structure | Medium |
| ExecutionPlan persistence | ⚠️ Partial | In-memory only | Low |

---

## Known Broken States

1. **`--remove-model` command** — Always raises `ValueError` (intentional, but CLI exposes it)
2. **Legacy iteration code** — `RunManager` still references iterations
3. **`repository.py.old`** — Exists but unused
4. **`src/main.py`** — 1,379 lines, God object
5. **Dual execution paths** — New and legacy coexist
6. **Test coverage gap** — New execution axis has unit tests, integration tests lag

---

## File Size Violations

### Files > 400 Lines
| File | Lines | Primary Issue |
|------|-------|---------------|
| `src/main.py` | 1,379 | God object |
| `src/cli/experiment_commands.py` | 1,506 | Mixes concerns |
| `src/cli/cli.py` | 670 | Complex parsing |
| `src/utils/config.py` | 730 | Extensive validation |
| `src/core/execution_engine.py` | 550 | Multiple responsibilities |
| `src/api/client.py` | 500 | HTTP + multimodal |
| `src/core/answer_parser.py` | 450 | Complex regex |
| `src/db/models.py` | 450 | Schema definitions |

---

## Recommendations for TO-BE

### Immediate (Phase 3-4)
1. Split `src/main.py` into command objects
2. Remove legacy `RunManager` and iteration code
3. Extract prompt building from `ExecutionEngine` to `Planner`
4. Document filter mechanism

### Short-term (Phase 5-6)
5. Simplify CLI parser
6. Add ExecutionPlan persistence (optional)
7. Implement retry policy in ExecutionPlan
8. Consolidate configuration

---

**Inventory Completed**: 2026-03-20  
**Files Analyzed**: 36  
**Total LOC Estimate**: ~8,500  
**Critical Issues Found**: 3  
**Architecture Deviations**: 13  
**Known Broken States**: 8
