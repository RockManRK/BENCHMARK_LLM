---
type: reference
audience: ai
last-validated: 2026-04-11
status: active
---

# Module Structure Reference

**Purpose:** `src/` layout and responsibility per module  
**Source:** Validated against actual codebase structure

---

## Directory Structure

```
src/
├── __init__.py
├── api/                  # API client layer
│   ├── __init__.py
│   ├── client.py         # OpenRouterClient (httpx.AsyncClient wrapper)
│   ├── errors.py         # API error types
│   ├── message_builder.py # Request message construction
│   ├── response_parser.py # LLM response parsing
│   └── stream_aggregator.py # Streaming response handling
├── cli/                  # CLI command modules
│   ├── __init__.py
│   ├── bcllm_main.py     # Main help and entry point
│   ├── bcllm_experiment.py # Experiment lifecycle management
│   ├── bcllm_model.py    # Model variant management
│   ├── bcllm_questions.py # Question snapshot management
│   ├── bcllm_run.py      # Run management
│   ├── bcllm_execute.py  # Execution entry point
│   ├── bcllm_export.py   # Export results
│   ├── bcllm_review.py   # Review UI
│   └── database.py       # DB connection helper
├── core/                 # Core business logic
│   ├── __init__.py
│   ├── planner.py        # Read-only plan builder
│   ├── execution_engine.py # Pure execution (no DB)
│   ├── execution_plan.py # Immutable plan dataclasses
│   ├── result_writer.py  # DB writes only
│   ├── async_orchestrator.py # Async execution bridge
│   ├── async_writer.py   # Async result writer
│   ├── config_resolver.py # Configuration resolution
│   ├── null_semantics.py  # FORCE_SYSTEM_DEFAULT constant
│   ├── mode.py           # CLI mode enumeration
│   ├── mode_resolver.py  # Mode resolution from argv
│   ├── mode_matrix.py    # Mode validation matrix
│   ├── module_resolver.py # Module dispatch
│   ├── run_finalizer.py  # Run status/duration updates
│   ├── retry.py          # Centralized retry handler
│   ├── answer_parser.py  # Answer parsing from LLM text
│   ├── answer_randomizer.py # Fisher-Yates shuffle
│   ├── argv_utils.py     # Argument parsing utilities
│   ├── json_serializer.py # JSON serialization
│   ├── question_loader.py # Question dataset loading
│   └── variant_signature.py # Variant identity generation
├── db/                   # Database layer
│   ├── __init__.py
│   ├── models.py         # Entity dataclasses
│   ├── repository.py     # Repository pattern (CRUD operations)
│   └── schema.py         # Schema creation SQL
├── review/               # Review UI
│   ├── __init__.py
│   └── review_ui.py      # TUI for manual review
├── utils/                # Utilities
│   ├── __init__.py
│   ├── logging_config.py # Logging setup
│   └── variant_signature.py # Variant signature generation
└── validators/           # Validation
    ├── __init__.py
    └── model_id_validator.py # Model ID validation
```

---

## Module Responsibilities

### Entry Point

**`bcllm.py`** (project root)
- CLI dispatcher
- Loads `.env` via `python-dotenv`
- Resolves mode (CREATE, MODIFY, EXECUTE, EXPORT, INVALID)
- Dispatches to appropriate `src/cli/` module
- Handles composite flows (CREATE + ADD_* in single command)

---

### API Layer (`src/api/`)

**Purpose:** External API communication

| Module | Responsibility |
|--------|---------------|
| `client.py` | `OpenRouterClient` — wraps `httpx.AsyncClient`; handles auth, request building, response receiving |
| `errors.py` | API error types (network, auth, rate_limit, server) |
| `message_builder.py` | Builds OpenRouter API request messages |
| `response_parser.py` | Parses streaming responses; extracts text |
| `stream_aggregator.py` | Aggregates streaming response chunks |

**Key Design:** Provider-agnostic interface; OpenRouter is current implementation.

---

### CLI Layer (`src/cli/`)

**Purpose:** Command parsing and dispatch

| Module | Commands | Responsibility |
|--------|----------|---------------|
| `bcllm_main.py` | `--help` | Help display, argument parser definition |
| `bcllm_experiment.py` | `--create-experiment`, `--experiment`, `--list-experiments`, `--remove-experiment` | Experiment lifecycle |
| `bcllm_model.py` | `--add-model`, `--list-models`, `--remove-model` | Model variant management |
| `bcllm_questions.py` | `--add-questions`, `--list-questions`, `--remove-question` | Question snapshot management |
| `bcllm_run.py` | `--create-run`, `--list-runs`, `--run`, `--remove-run` | Run management |
| `bcllm_execute.py` | `--execute` | Execution orchestration (Planner → Engine → Writer) |
| `bcllm_export.py` | `--export` | Export results to CSV/JSON |
| `bcllm_review.py` | `--review-experiment`, `--review-all` | Review UI entry point |
| `database.py` | (internal) | Database connection helper |

**Key Design:** CLI modules are orchestration only; no domain logic.

---

### Core Layer (`src/core/`)

**Purpose:** Business logic and execution

#### Execution Pipeline

| Module | Role | DB Access |
|--------|------|-----------|
| `planner.py` | Read-only plan builder | Read-only |
| `execution_engine.py` | Pure execution (API calls) | None |
| `result_writer.py` | Persist results | Write-only |
| `async_orchestrator.py` | Async bridge (sync caller → async internal) | Via writer |
| `async_writer.py` | Async result queue consumer | Write-only |
| `execution_plan.py` | Immutable plan dataclasses | None |
| `run_finalizer.py` | Update run status/duration | Write-only |

#### Configuration & Utilities

| Module | Responsibility |
|--------|---------------|
| `config_resolver.py` | Centralized config resolution with hierarchy |
| `null_semantics.py` | `FORCE_SYSTEM_DEFAULT` constant for bypassing inheritance |
| `mode.py` | CLI mode enumeration (CREATE, MODIFY, EXECUTE, EXPORT, INVALID) |
| `mode_resolver.py` | Resolves mode from argv |
| `mode_matrix.py` | Validates mode + command combinations |
| `module_resolver.py` | Dispatches to correct CLI module |
| `retry.py` | Centralized retry handler with exponential backoff |
| `answer_parser.py` | Parses LLM responses for selected answer (A/B/C/D) |
| `answer_randomizer.py` | Fisher-Yates shuffle for answer options |
| `question_loader.py` | Loads and filters questions from dataset |
| `json_serializer.py` | Consistent JSON serialization |
| `argv_utils.py` | Argument parsing utilities |
| `variant_signature.py` | Generates human-readable variant signatures |

---

### Database Layer (`src/db/`)

**Purpose:** Database access and entity definitions

| Module | Responsibility |
|--------|---------------|
| `models.py` | Entity dataclasses (Experiment, ModelVariant, QuestionSnapshot, Run, Response, Error) |
| `repository.py` | Repository pattern for CRUD operations (ExperimentRepository, ResponseRepository, etc.) |
| `schema.py` | Complete schema SQL; `create_schema()` function |

**Key Design:** Schema created programmatically, no migration scripts.

---

### Review Layer (`src/review/`)

**Purpose:** Manual review UI

| Module | Responsibility |
|--------|---------------|
| `review_ui.py` | TUI for reviewing ambiguous answers (Rich-based) |

---

### Utilities (`src/utils/`)

**Purpose:** Cross-cutting utilities

| Module | Responsibility |
|--------|---------------|
| `logging_config.py` | Logging setup (file + console, rotation) |
| `variant_signature.py` | Variant signature generation (used by model management) |

---

### Validators (`src/validators/`)

**Purpose:** Input validation

| Module | Responsibility |
|--------|---------------|
| `model_id_validator.py` | Validates model ID format |

---

## Module Dependencies

```
bcllm.py
    ↓
src/cli/* (orchestration)
    ↓
src/core/* (business logic)
    ↓
┌──────────┬────────────┬────────────┐
│ src/api/ │  src/db/   │ src/review │
└──────────┴────────────┴────────────┘
```

**Rule:** Modules should only depend on lower layers, never on sibling or higher layers (except `bcllm.py` dispatcher).

---

## File Count by Layer

| Layer | Files | Lines (approx) |
|-------|-------|----------------|
| API | 5 | ~600 |
| CLI | 9 | ~2500 |
| Core | 22 | ~4500 |
| DB | 3 | ~500 |
| Review | 1 | ~700 |
| Utils | 2 | ~200 |
| Validators | 1 | ~50 |
| **Total** | **43** | **~9050** |

---

## Related Documents

- [architecture/overview.md](../architecture/overview.md) — System at a glance
- [architecture/execution-architecture.md](../architecture/execution-architecture.md) — Component data flow
- [reference/database-schema.md](database-schema.md) — Schema details
