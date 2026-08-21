# Repository Guidelines

## Project Structure & Module Organization

Benchmark LLM is a Python >=3.14 (validated: 3.14.2) CLI system for reproducible LLM benchmarking. Root `bcllm.py` dispatches CLI modes; implementation lives under `src/`:

- `src/cli/`: command modules for experiments, models, questions, runs, execution, export, and review.
- `src/core/`: planner, immutable execution plans, execution engine, result writers, config resolution, retry, parsing, and randomization.
- `src/api/`: OpenRouter API client, provider resolution, message building, and response parsing.
- `src/db/`: schema, dataclasses, and repository layer.
- `src/review/`, `src/utils/`, `src/validators/`: focused support modules.

Tests live in `tests/`: unit coverage in `tests/unit/`, integration workflows in `tests/integration/`, smoke tests in `tests/smoke/`, and validation scripts in `tests/validation/`. Documentation is authoritative in `docs/`; start with `QWEN.md`.

## Build, Test, and Development Commands

- `python -m venv .venv`: create a local virtual environment.
- `pip install -r requirements.txt`: install runtime and test dependencies.
- `pip install -e .`: install the package and expose the `bcllm` console script.
- `pytest`: run the full test suite using `pytest.ini` defaults.
- `pytest tests/unit -m "not slow"`: run faster unit tests.
- `python bcllm.py --help` or `bcllm --help`: inspect CLI usage.

## Coding Style & Naming Conventions

Use idiomatic Python with 4-space indentation, type-aware dataclasses where appropriate, and explicit names that reflect domain concepts such as `Experiment`, `ExecutionPlan`, `ResultWriter`, and model variants. Keep CLI modules thin; domain behavior belongs in `src/core/`. Avoid hidden inference or mutable global state. Modules use `snake_case.py`, tests use `test_*.py`, and CLI modules follow `bcllm_<area>.py`.

## Testing Guidelines

Tests are discovered from `tests/` with `test_*.py`, `Test*` classes, and `test_*` functions. Use markers from `pytest.ini`: `domain_rule`, `contract`, `integration`, and `slow`. Add or update tests for behavior changes, especially around determinism, idempotency, immutability, configuration hierarchy, provider locking, and result writing.

## Commit & Pull Request Guidelines

Recent history mixes conventional commits (`fix:`, `feat:`, `feat(docs):`) with short descriptive messages. Prefer concise imperative summaries, adding a scope when useful, for example `fix: preserve pending run status`. Pull requests should describe behavior changes, list tests run, link related issues or ADRs, and include screenshots only for UI/review changes.

## Agent-Specific Instructions

`QWEN.md` is the primary operational entry point. Contracts in `docs/contracts/` are normative; only an ADR can supersede them. If documentation conflicts with code, verify against source unless an ADR says otherwise. When changing code, update reference docs first, then status docs, architecture docs only for conceptual changes, and contracts only with ADR-backed approval.
