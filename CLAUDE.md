# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Primary entry point

`QWEN.md` is the primary operational entry point for AI agents in this repo — read it first. It points to a structured `docs/` tree that is normative in places:

- `docs/contracts/README.md` — **normative**, non-negotiable invariants (determinism, idempotency, immutability, configuration hierarchy, auditability). Only an ADR can override a contract.
- `docs/architecture/` — conceptual model, execution architecture, design principles.
- `docs/reference/` — CLI commands, configuration, database schema, module structure (current implementation state).
- `docs/status/` — implementation status, known issues, roadmap (roadmap is explicitly non-normative).
- `docs/guides/ai-development-workflow.md` — AI agent navigation/validation workflow.

**Source of truth rule:** if documentation and code disagree, code wins unless an ADR states otherwise.

**If you detect a contract violation:** stop, document the conflict (contract text + code), flag it to the user, and wait — do not silently "fix" it by picking a side.

## Commands

```bash
# Run all tests
pytest

# Run a single test file / test
pytest tests/test_api_client.py
pytest tests/test_api_client.py::TestClassName::test_name

# Skip slow/integration tests
pytest -m "not slow"

# CLI usage (entry point is bcllm.py at repo root)
python bcllm.py --create-experiment my_exp --add-questions "1-10"
python bcllm.py --experiment my_exp --add-model openai/gpt-4 --reasoning low
python bcllm.py --experiment my_exp --add-run
python bcllm.py --experiment my_exp --execute
```

- `pytest.ini` sets `pythonpath = . src`, so tests import from `src/` directly (no package install needed).
- `OPENROUTER_API_KEY` must be a real system environment variable (not `.env`) for execution to work — this is enforced deliberately, not an oversight.
- No lint/format tooling is configured in this repo currently.

## Architecture

This is a **reproducible, experiment-driven LLM benchmarking system**. There is no immediate/ad-hoc execution mode — every action ties back to an explicit experiment identity.

### Core pipeline (strict, one-directional)

```
CLI → Planner (DB read-only) → ExecutionPlan (immutable) → AsyncOrchestrator
    → ExecutionEngine (pure execution, no DB access) → ResultWriter (DB write-only, idempotent) → Database
```

Each stage has a hard boundary that must not be crossed:
- **Planner** (`src/core/planner.py`) only reads the DB and resolves what work exists; never executes anything.
- **ExecutionPlan** (`src/core/execution_plan.py`) is an immutable dataclass description of work; the only thing ExecutionEngine consumes.
- **ExecutionEngine** (`src/core/execution_engine.py`) makes API calls per the plan; has zero DB access and makes zero scope decisions.
- **ResultWriter** (`src/core/result_writer.py`) only writes `responses`/`errors` and updates run status; never executes models, decides scope, or infers correctness/meaning beyond what ExecutionEngine returned. It does compute `needs_review` from `parse_confidence`/`selected_answer`.

### Domain model

- **Experiment**: research intent + config, frozen at creation. `.env` is consulted only at experiment creation — never at run or model resolution time.
- **Model Variant** (called "model" in CLI): an intentional, immutable configuration of a base model (model_id, reasoning mode, vision/structured-output flags). Created explicitly, one per CLI command, never modified after creation.
- **Question Snapshot**: an immutable copy of a question baked into the experiment at add-time; the original source file becomes irrelevant afterward.
- **Run**: a concrete execution instance (seed, effective prompts, scope) with lifecycle `pending → completed/failed/partial_failed`. Runs don't define models/questions — they only execute what already exists.

### Configuration hierarchy (highest to lowest priority)

```
CLI arguments → Run/Model Variant config → Experiment config (frozen) → .env (creation-time only) → System defaults
```

### Module layout (`src/`)

- `api/` — OpenRouter API client (`client.py`), provider endpoint resolution, message building, streaming response parsing/aggregation. Provider-agnostic interface; OpenRouter is the current implementation.
- `cli/` — one module per command family (`bcllm_experiment.py`, `bcllm_model.py`, `bcllm_questions.py`, `bcllm_run.py`, `bcllm_execute.py`, `bcllm_export.py`, `bcllm_review.py`, `bcllm_provider.py`). Orchestration only — no domain logic lives here.
- `core/` — business logic: the execution pipeline (`planner.py`, `execution_engine.py`, `execution_plan.py`, `result_writer.py`, `async_orchestrator.py`, `async_writer.py`, `run_finalizer.py`), config resolution (`config_resolver.py`, `null_semantics.py`), CLI mode handling (`mode.py`, `mode_resolver.py`, `mode_matrix.py`, `module_resolver.py`), and utilities (`retry.py`, `answer_parser.py`, `question_loader.py`, `json_serializer.py`).
- `db/` — `models.py` (entity dataclasses), `repository.py` (repository-pattern CRUD), `schema.py`/`schema.sql` (schema created programmatically; no migration framework).
- `review/` — Rich-based TUI (`review_ui.py`) for manually reviewing responses flagged `needs_review`.
- `validators/`, `utils/` — model ID validation, logging setup, variant signature generation.

Dependency rule: modules only depend on lower layers (`cli` → `core` → `api`/`db`/`review`), never sideways or upward, except the root `bcllm.py` dispatcher.

### Database

SQLite, 6 tables (`experiments`, `model_variants`, `question_snapshots`, `runs`, `responses`, `errors`). Identity tables are immutable; `responses`/`errors` are append-only. Nothing is ever deleted — if a row exists, it means something actually happened.

## Contract verification gate (essence-guardian)

A read-only subagent, `.claude/agents/essence-guardian.md`, checks work against the 7 fundamental contracts in `docs/contracts/` (determinism, immutability, config hierarchy, idempotency, auditability, etc.) and reports Aligned/Warning/Violation per contract. It never writes code — only evaluates and reports.

**Invoke it proactively via the `Agent` tool (`subagent_type: essence-guardian`), but only at real decision points** — this is the exception, not the routine, because each call costs tokens:
- end of a significant implementation phase
- a change touching the Planner → ExecutionEngine → ResultWriter pipeline
- a change to the configuration hierarchy or any contract-adjacent area
- before reporting a large task as complete

Do **not** call it for small edits, trivial fixes, or exploratory/read-only work.

## Repository hygiene notes

- `Arquivos_Mortos/` is an archive of legacy/superseded code and docs — not part of the active system, do not treat it as current reference.
- `docs/Nao_Apagar-Temporarios_do_Usuario/` holds user working notes; don't restructure it.
- The project was paused for ~4 months as of 2026-08 and work is resuming with a focus on automated CLI testing (per recent commit history) — check `docs/status/known-issues.md` and `docs/status/implementation-status.md` for what's currently broken vs. working before assuming a feature is complete.
