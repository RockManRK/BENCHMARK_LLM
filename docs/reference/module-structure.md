---
type: reference
audience: ai
last-validated: 2026-08-20
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
│   ├── provider_resolver.py # Provider endpoint resolution
│   ├── request_payload.py # Canonical chat completion payload builder
│   ├── response_parser.py # LLM response parsing
│   └── stream_aggregator.py # Streaming response handling
├── cli/                  # CLI command modules
│   ├── __init__.py
│   ├── bcllm_main.py     # Main help and entry point
│   ├── bcllm_experiment.py # Experiment lifecycle management (Typer parsing since marco 4A, 2026-08-20)
│   ├── bcllm_model.py    # Model variant management
│   ├── bcllm_questions.py # Question snapshot management (Typer parsing since marco 4A, 2026-08-20)
│   ├── bcllm_run.py      # Run management (Typer parsing since marco 4B, 2026-08-20)
│   ├── bcllm_execute.py  # Execution entry point
│   ├── bcllm_export.py   # Export results
│   ├── bcllm_review.py   # Review UI
│   ├── database.py       # DB connection helper
│   ├── param_types.py    # Typer callback equivalents of special_config_values.py's parse_*_or_system_default (CLI migration Fase 2)
│   ├── commands/         # Real typer.Typer command definitions, one per migrated module (CLI migration Fase 4)
│   │   ├── __init__.py
│   │   ├── questions.py  # Typer command replacing bcllm_questions.py's former argparse create_parser() (marco 4A)
│   │   ├── experiment.py # Typer command replacing bcllm_experiment.py's former argparse create_parser() (marco 4A)
│   │   └── run.py        # Typer command replacing bcllm_run.py's former argparse create_parser() (marco 4B)
│   └── presentation/      # Rich-based presentation foundation (CLI migration Fase 2/6)
│       ├── __init__.py
│       ├── console.py     # Console/error_console singletons
│       ├── errors.py      # Exit-code-contract command wrapper (not yet wired to a live command)
│       └── theme.py       # Rich theme (semantic styles)
├── core/                 # Core business logic
│   ├── __init__.py
│   ├── planner.py        # Read-only plan builder
│   ├── execution_engine.py # Pure execution (no DB)
│   ├── execution_plan.py # Immutable plan dataclasses
│   ├── result_writer.py  # DB writes only
│   ├── async_orchestrator.py # Async execution bridge
│   ├── async_writer.py   # Async result writer
│   ├── config_resolver.py # Configuration resolution
│   ├── special_config_values.py  # FORCE_SYSTEM_DEFAULT constant
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
│   └── question_loader.py # Question dataset loading
├── db/                   # Database layer
│   ├── __init__.py
│   ├── models.py         # Entity dataclasses
│   ├── repository.py     # Repository pattern (CRUD operations)
│   ├── schema.py         # Schema creation SQL
│   └── unit_of_work.py   # UnitOfWork — composite CREATE-flow transaction boundary only
├── review/               # Review UI
│   ├── __init__.py
│   └── review_ui.py      # TUI for manual review
├── utils/                # Utilities
│   ├── __init__.py
│   ├── logging_config.py # Logging setup (LOG_LEVEL, LOG_FILE_PATH, LOG_PROFILE, JSONL sibling)
│   ├── log_events.py     # LogProfile enum + centralized Event name vocabulary + EVENT_PROFILE map
│   ├── log_emitter.py    # emit_event() — the one event-emission path (human + JSONL, redaction, severity floor)
│   ├── redaction.py      # redact() — recursive secret redaction for log output only
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
| `client.py` | `OpenRouterClient` — wraps `httpx.AsyncClient`; sends a pre-built payload (`chat_completion(payload, base_url)`, no scalar kwargs — see `request_payload.py`) and receives the response |
| `provider_resolver.py` | Provider endpoint resolution via OpenRouter `/models/{id}/endpoints` API |
| `errors.py` | API error types (network, auth, rate_limit, server) |
| `message_builder.py` | Builds OpenRouter API request messages |
| `request_payload.py` | `build_chat_completion_payload()` — the ONE canonical chat completion request payload builder. Called once per attempt by `ExecutionEngine`; the same object is serialized into `request_json` (audit) and handed unmodified to `OpenRouterClient.chat_completion()` (transport) — see `docs/status/model-seed-checkpoint-b-design.md`. |
| `response_parser.py` | Parses streaming responses; extracts text |
| `stream_aggregator.py` | Aggregates streaming response chunks |

**Key Design:** Provider-agnostic interface; OpenRouter is current implementation.

---

### CLI Layer (`src/cli/`)

**Purpose:** Command parsing and dispatch

| Module | Commands | Responsibility |
|--------|----------|---------------|
| `bcllm_main.py` | `--help` | Help display, argument parser definition |
| `bcllm_experiment.py` | `--create-experiment`, `--experiment`, `--list-experiments`, `--remove-experiment` | Experiment lifecycle (including `--provider-lock`) |
| `bcllm_model.py` | `--add-model`, `--list-models`, `--remove-model` | Model variant management (including `--provider`) |
| `bcllm_provider.py` | `--resolve-providers` | Provider resolution for model variants |
| `bcllm_questions.py` | `--add-questions`, `--list-questions` | Question snapshot management (no removal command — QuestionSnapshot is immutable) |
| `bcllm_run.py` | `--add-run`, `--list-runs`, `--run`, `--remove-run` | Run management (corrected 2026-08-20: the real, tested flag is `--add-run` — `--create-run` was a pre-existing doc-drift error, never a real flag, see `docs/status/known-issues.md`) |
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
| `special_config_values.py` | `FORCE_SYSTEM_DEFAULT` constant for bypassing inheritance |
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

---

### Database Layer (`src/db/`)

**Purpose:** Database access and entity definitions

| Module | Responsibility |
|--------|---------------|
| `models.py` | Entity dataclasses (Experiment, ModelVariant, QuestionSnapshot, Run, Response, Error) |
| `repository.py` | Repository pattern for CRUD operations (ExperimentRepository, ResponseRepository, etc.) |
| `schema.py` | Complete schema SQL; `create_schema()` function |
| `unit_of_work.py` | `UnitOfWork` — explicit transaction boundary for the composite `--create-experiment` + `--add-*` CLI flow only (`bcllm.py::_handle_composite_flow`). Never used by `ResponseRepository`/`ResultWriter`/`--execute` — see `docs/status/composite-flow-unit-of-work-design.md`. |

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
| `logging_config.py` | Logging setup (file + console, rotation); configures both the human-readable logger and the `benchmark_llm.jsonl` structured logger from `LOG_PROFILE`/`LOG_LEVEL`/`LOG_FILE_PATH` |
| `log_events.py` | `LogProfile` (MINIMAL/NORMAL/DETAILED/TRACE, cumulative) and `Event` — the centralized, stable `event_name` vocabulary; `EVENT_PROFILE` maps each INFO/DEBUG event to its minimum required profile (WARNING+ events always emit, at any profile) |
| `log_emitter.py` | `emit_event()` — single construction point for both the human-readable log line and the JSONL structured record for one event; applies the severity-floor/profile check, redaction, and never lets a logging failure propagate — see `docs/contracts/interaction-contracts.md` §4 |
| `redaction.py` | `redact()` — recursive, structure-preserving redaction of secret-shaped keys/tokens/URL credentials for logging output only; never applied to DB-persisted data |
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
