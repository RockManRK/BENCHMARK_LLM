# QWEN_TECH.md — Technical Context

**Last Updated:** 2026-03-17  
**Document Purpose:** Describe the CURRENT technical reality of the benchmark_llm repository

---

## 1. Language & Runtime

- **Language:** Python 3.10+
- **Type System:** Type hints on all functions (Python 3.10+ syntax)
- **Async Support:** Yes (`asyncio`, `httpx` async client)
- **Platform:** Windows (development environment), cross-compatible

---

## 2. Core Dependencies

### Production Dependencies (`requirements.txt`)

| Package | Version | Purpose |
|---------|---------|---------|
| `httpx` | >=0.25.0 | Async HTTP client for OpenRouter API |
| `pydantic` | >=2.0.0 | Data validation and settings management |
| `pydantic-settings` | >=2.0.0 | Environment-based configuration |
| `Pillow` | >=10.0.0 | Image processing for multimodal questions |
| `python-dotenv` | >=1.0.0 | Environment variable management |
| `rich` | >=13.0.0 | Terminal output formatting (progress bars, tables) |

### Testing Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | >=7.4.0 | Test framework |
| `pytest-asyncio` | >=0.21.0 | Async test support |
| `pytest-mock` | >=3.11.0 | Mocking utilities |
| `responses` | >=0.24.0 | HTTP request mocking |

---

## 3. Project Structure

```
benchmark_llm/
├── src/                          # Source code (main package)
│   ├── __init__.py
│   ├── main.py                   # Entry point, BenchmarkRunner orchestrator
│   ├── api/                      # OpenRouter API integration
│   │   ├── __init__.py
│   │   ├── client.py             # Async HTTP client, MessageBuilder
│   │   ├── error_handler.py      # Error handling
│   │   ├── model_capabilities.py # Model feature detection
│   │   ├── parser.py             # Response parsing
│   │   └── retry.py              # Retry logic
│   ├── cli/                      # Command-line interface
│   │   ├── __init__.py
│   │   ├── cli.py                # Argument parsing (CLIParser)
│   │   ├── experiment_commands.py # Experiment management commands
│   │   ├── output_formatter.py   # Console/JSON/CSV/Markdown formatters
│   │   ├── review_ui.py          # Review UI (if applicable)
│   │   └── statistics.py         # Statistics calculation
│   ├── core/                     # Core business logic
│   │   ├── __init__.py
│   │   ├── answer_parser.py      # Answer parsing logic
│   │   ├── error_collector.py    # Error tracking
│   │   ├── execution_engine.py   # Execution engine (context-agnostic)
│   │   ├── filter.py             # Question filtering
│   │   ├── iteration_executor.py # Iteration execution
│   │   ├── loader.py             # Data/question loading
│   │   ├── question_executor.py  # Question execution
│   │   ├── randomizer.py         # Answer randomization
│   │   ├── run_manager.py        # Benchmark lifecycle management
│   │   └── variant_config.py     # Model variant configuration
│   ├── db/                       # Database layer
│   │   ├── __init__.py
│   │   ├── models.py             # Dataclasses for entities
│   │   ├── repository.py         # Repository pattern implementations
│   │   ├── schema.py             # DatabaseManager, schema management
│   │   └── schema.sql            # SQL schema definition (TO-BE architecture)
│   └── utils/                    # Utilities
│       ├── __init__.py
│       ├── answer_schema.py      # Answer schema utilities
│       ├── config.py             # Pydantic Settings management
│       ├── config_hierarchy.py   # Configuration hierarchy
│       ├── image_handler.py      # Image handling utilities
│       ├── logging_config.py     # Logging configuration
│       └── progress.py           # Progress tracking
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures and configuration
│   └── test_*.py                 # Test modules (31 files)
├── conductor/                    # Project management
│   ├── index.md
│   ├── product.md
│   ├── product-guidelines.md
│   ├── tech-stack.md
│   ├── tracks.md
│   ├── workflow.md
│   ├── code_styleguides/
│   └── tracks/                   # Individual track plans
├── data/                         # Database and data files
├── docs/                         # Documentation (actively maintained)
├── logs/                         # Operational logs (git-ignored)
├── migrations/                   # SQL migration scripts
├── old/                          # Archived files (git-ignored)
├── plans/                        # Planning documents
├── .env.example                  # Environment template
├── .gitignore
├── bcllm.py                      # CLI entry point (alternative to -m src.main)
├── CHANGELOG.md
├── MANUAL.md                     # User manual
├── QWEN.md                       # Project context (mental model)
├── README.md                     # User-facing documentation
├── requirements.txt
├── setup.py                      # Package installation configuration
└── TESTING_GUIDE.md
```

### Folder Responsibilities

| Folder | Purpose | Can New Code Go Here? |
|--------|---------|----------------------|
| `src/api/` | OpenRouter API integration | ✅ Yes |
| `src/cli/` | CLI parsing and output | ✅ Yes |
| `src/core/` | Business logic, execution | ✅ Yes |
| `src/db/` | Database schema, models, repositories | ✅ Yes |
| `src/utils/` | Shared utilities | ✅ Yes |
| `tests/` | Test suite | ✅ Yes |
| `conductor/` | Project management, planning | ✅ For planning docs |
| `docs/` | User/technical documentation | ✅ Yes |
| `migrations/` | DB migration scripts | ✅ For migrations only |
| `old/` | Archived files | ❌ No (read-only archive) |
| `plans/` | Planning documents | ⚠️ Review first |

---

## 4. Database Layer Overview

### Architecture: TO-BE Schema (Clean Architecture)

**File:** `src/db/schema.sql` (source of truth)  
**Version:** 1.0 (Clean Architecture)  
**Generated:** 2026-03-17

### Core Tables (8 tables)

1. **`experiments`** — Frozen experiment configuration
   - Immutable: `config_json`, `config_hash`, prompt templates
   - Global defaults for temperature, reasoning mode, etc.

2. **`model_variants`** — Intentional model variants (identity-defining)
   - Identity fields: `reasoning_mode`, `reasoning_effort`, `vision_enabled`, `structured_output`, `web_access_enabled`
   - Optional parameters: `temperature`, `top_p`, `max_output_tokens`

3. **`runs`** — Concrete execution unit (no iterations)
   - Links to `experiment_id`
   - Optional `run_group_id` for grouping
   - Status: `pending` → `running` → `completed` | `failed`

4. **`question_snapshots`** — Immutable executable questions
   - Frozen per experiment
   - Links to `experiment_id` and `question_id`

5. **`responses`** — Successful or valid model executions
   - Links: `run_id`, `variant_id`, `snapshot_id`
   - Contains: answer, response text, tokens, timing, raw JSON

6. **`errors`** — Error tracking
   - Links to responses
   - Contains: error details, raw response JSON

7. **`models`** — Base model registry
   - Model metadata, provider info

8. **`run_models`** — Many-to-many between runs and variants
   - Tracks which variants are in which runs
   - Status tracking per variant

### Repository Pattern

**File:** `src/db/repository.py`

Repositories implemented:
- `ExperimentRepository`
- `RunRepository`
- `ModelRepository`
- `ModelVariantRepository`
- `RunModelRepository`
- `ExperimentModelRepository`
- `QuestionRepository`
- `QuestionSnapshotRepository`
- `ResponseRepository`
- `ErrorRepository`

### Data Models

**File:** `src/db/models.py`

Dataclasses defined:
- `Experiment`
- `Run`
- `Model`
- `ModelVariant`
- `RunModel`
- `Question`
- `QuestionSnapshot`
- `Response`
- `Error`

### Database Manager

**File:** `src/db/schema.py`

- `DatabaseManager` class
- Connection management with context manager support
- Foreign key support enabled (`PRAGMA foreign_keys = ON`)

---

## 5. CLI Layer Overview

### Entry Points

1. **`bcllm.py`** (root) — Direct CLI entry point
   ```python
   #!/usr/bin/env python3
   import sys
   from src.main import main
   sys.exit(main())
   ```

2. **`python -m src.main`** — Module entry point

3. **`setup.py`** — Package installation (defines `bcllm` console script)

### CLI Parser

**File:** `src/cli/cli.py`

- `CLIParser` class using `argparse`
- Supports: `--models`, `--iterations`, `--questions`, `--experiment`, `--create-experiment`, `--add-model`, etc.
- Question range expansion: `Q001-Q010`
- Metadata filtering: `--where status=valid has_image=false`

### Execution Modes

**File:** `src/utils/config.py`

```python
class ExecutionMode(str, Enum):
    TEST = "test"         # In-memory DB, no persistence
    DEV = "dev"           # Persistence, no experiment tracking
    EXPERIMENT = "experiment"  # Full experiment tracking
```

### Output Formatters

**File:** `src/cli/output_formatter.py`

- `ConsoleFormatter` — Rich terminal output
- `JSONFormatter`
- `CSVFormatter`
- `MarkdownFormatter`

---

## 6. Execution Layer Overview

### BenchmarkRunner

**File:** `src/main.py`

Main orchestrator:
- CLI argument parsing
- Configuration loading
- Database initialization
- Test execution coordination
- Statistics calculation
- Output formatting

### ExecutionEngine

**File:** `src/core/execution_engine.py`

**Design Principle:** Context-agnostic execution
- Does NOT know about `run_id`, `experiment_id`, or database
- Does NOT persist results
- ONLY executes and returns raw results
- Persistence is caller's responsibility (`BenchmarkRunner`/`RunManager`)

### RunManager

**File:** `src/core/run_manager.py`

- Benchmark lifecycle management
- Run initialization
- Seed determination
- Experiment tracking

### Key Design Patterns

1. **Separation of Concerns:**
   - `ExecutionEngine` → Execution only
   - `RunManager` → Lifecycle and persistence
   - `BenchmarkRunner` → Orchestration

2. **Repository Pattern:**
   - All database access through repositories
   - Dataclasses for type safety

3. **Dependency Injection:**
   - Components receive dependencies via constructor
   - Testable with mocks

---

## 7. Architectural Rules for Code Generation

### DO

- ✅ Use type hints on all functions
- ✅ Use dataclasses for data structures
- ✅ Use repository pattern for database access
- ✅ Keep execution logic separate from persistence
- ✅ Use async/await for API calls
- ✅ Use Pydantic for settings validation
- ✅ Use logging module (not print statements)
- ✅ Write tests for new functionality
- ✅ Follow existing module structure

### DO NOT

- ❌ Do NOT create new tables without updating `schema.sql`
- ❌ Do NOT bypass repositories for database access
- ❌ Do NOT mix execution logic with persistence
- ❌ Do NOT use global state for configuration
- ❌ Do NOT hardcode paths (use `pathlib.Path`)
- ❌ Do NOT commit `.env` files (API keys are security risk)
- ❌ Do NOT modify `old/` folder (archive only)

### Where New Code Should Go

| Feature Type | Location |
|--------------|----------|
| New API endpoint/method | `src/api/client.py` or new file in `src/api/` |
| New CLI command | `src/cli/cli.py` and `src/cli/experiment_commands.py` |
| New execution logic | `src/core/` (new or existing module) |
| New database entity | `src/db/models.py`, `src/db/repository.py`, `src/db/schema.sql` |
| New utility | `src/utils/` |
| New test | `tests/` with naming `test_<feature>.py` |
| New documentation | `docs/` |

---

## 8. Known Legacy Code

### Archived (Moved to `old/` on 2026-03-17)

The following were moved to `old/` during project cleanup:

- **Database check scripts** (11 files) — One-off inspection scripts
- **Test/verification scripts** (11 files) — Standalone tests, superseded by `/tests` suite
- **Migration scripts** (3 files) — Runners for old migrations
- **Utility scripts** (3 files) — Demo/setup scripts
- **Documentation duplicates** (3 files) — `SYSTEM_CONTEXT.md`, `SYSTEM_DOCUMENTATION.md`, `SYSTEM_DOCUMENTATION_2.md`
- **Garbage files** — `$null`, `0.24.0`

### Current Technical Debt / Notes

1. **Schema Transition:**
   - `src/db/schema.sql` represents TO-BE architecture
   - Existing database may have legacy schema
   - Migrations in `migrations/` folder handle transitions

2. **Execution Plan / ResultWriter:**
   - Refer to `docs/architecture/` for planned components
   - `ExecutionPlan` and `ResultWriter` contracts are in design phase

3. **Configuration Hierarchy:**
   - `src/utils/config_hierarchy.py` exists but usage unclear
   - Primary config is `src/utils/config.py` (Pydantic Settings)

---

## 9. Testing Strategy

### Test Framework

- **Primary:** `pytest`
- **Async Support:** `pytest-asyncio`
- **Mocking:** `pytest-mock`, `responses` (HTTP mocking)

### Test Organization

**File:** `tests/conftest.py`

Fixtures provided:
- `db_manager` — In-memory database for testing
- `settings` — Default settings
- Mock LLM response builders (for `pytest-httpx`)

### Test Markers

```python
@pytest.mark.slow        # Slow tests (deselect with -m "not slow")
@pytest.mark.integration # Integration tests
```

### Test Coverage Target

- **Goal:** >80% coverage for all modules
- **Command:** `pytest tests/ --cov=src --cov-report=term-missing`

### Test Files (31 modules)

Core tests:
- `test_api_client.py`
- `test_cli.py`
- `test_config.py`
- `test_data_loading.py`
- `test_database.py`
- `test_error_collector.py`
- `test_execution.py`
- `test_execution_engine.py`
- `test_integration.py`
- `test_logging_config.py`
- `test_model_capabilities.py`
- `test_parser.py`
- `test_retry.py`
- `test_utils.py`
- ... and 17 more

---

## 10. Configuration System

### Settings Management

**File:** `src/utils/config.py`

- Pydantic `BaseSettings` with environment variable validation
- `.env` file loaded for non-sensitive config
- **Security:** `OPENROUTER_API_KEY` MUST be set via system environment variable (NOT in `.env`)

### Key Configuration Options

```python
class Settings(BaseSettings):
    # OpenRouter
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    
    # Database
    database_path: Path = "./data/benchmark.db"
    
    # Logging
    log_level: str = "INFO"
    log_file_path: Path = "./logs/benchmark.log"
    
    # Execution
    default_iterations: int = 1
    random_seed: Optional[int] = None
    
    # Model parameters (optional, blank = model defaults)
    model_max_tokens: Optional[int]
    model_temperature: Optional[float]
    model_top_p: Optional[float]
    model_top_k: Optional[int]
    model_repeat_penalty: Optional[float]
    
    # Features
    use_structured_outputs: bool = False
    enable_vision: bool = False
    reasoning_effort: Optional[str] = None
    reasoning_mode: str = "unspecified"
```

### Environment Variables

**File:** `.env.example`

See `.env.example` for template. Key points:
- `OPENROUTER_API_KEY` → System environment only
- `DATABASE_PATH`, `LOG_LEVEL`, etc. → Can be in `.env`
- Blank values = use model/server defaults

---

## 11. Logging System

### Configuration

**File:** `src/utils/logging_config.py`

- `LoggingConfig` class for configuration
- `setup_logging()` function for initialization
- Separate operational logs (`.log` files) from experimental data (SQLite)

### Log Destinations

- **Operational Logs:** `logs/benchmark.log` (git-ignored)
- **Experimental Data:** SQLite database (`data/benchmark.db`)

### Log Levels

- `DEBUG` — Detailed debugging
- `INFO` — General progress
- `WARNING` — Warnings
- `ERROR` — Errors
- `CRITICAL` — Critical failures

---

## 12. API Integration

### OpenRouter Client

**File:** `src/api/client.py`

- Async HTTP client using `httpx`
- Supports text-only and multimodal (text + image) messages
- `MessageBuilder` class for building API messages

### Error Handling

**File:** `src/api/error_handler.py`

- HTTP error handling
- Rate limit handling
- Retry logic

### Retry Logic

**File:** `src/api/retry.py`

- Configurable retry strategies
- Exponential backoff support

### Model Capabilities

**File:** `src/api/model_capabilities.py`

- Model feature detection
- Capability caching

---

## 13. Unclear / Needs Clarification

1. **`src/utils/config_hierarchy.py`** — Exists but usage pattern unclear
2. **`src/cli/review_ui.py`** — Purpose not immediately clear from name
3. **`plans/` folder** — Contains planning documents, review before acting
4. **`conductor/tracks/`** — Individual track plans, may be outdated
5. **ExecutionPlan / ResultWriter** — Mentioned in architecture docs, implementation status unclear

---

## 14. Summary

### What Works Well

- ✅ Clean separation of concerns (execution vs. persistence)
- ✅ Repository pattern for database access
- ✅ Type-safe dataclasses
- ✅ Comprehensive test suite
- ✅ Async API client
- ✅ Flexible configuration system

### Areas for Improvement

- ⚠️ Schema transition in progress (TO-BE vs. legacy)
- ⚠️ Some utility modules unclear (`config_hierarchy.py`)
- ⚠️ Architecture documentation may be ahead of implementation

### Key Files to Know

| Purpose | File |
|---------|------|
| Entry point | `src/main.py` or `bcllm.py` |
| Configuration | `src/utils/config.py` |
| Database schema | `src/db/schema.sql` |
| Data models | `src/db/models.py` |
| Repositories | `src/db/repository.py` |
| Execution | `src/core/execution_engine.py` |
| API client | `src/api/client.py` |
| CLI parsing | `src/cli/cli.py` |
| Tests | `tests/conftest.py` + `test_*.py` |

---

**End of Document**
