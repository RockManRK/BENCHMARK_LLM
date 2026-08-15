# Benchmark LLM

**Benchmark LLM** is a **reproducible, experiment‑driven benchmarking system** for evaluating Large Language Models (LLMs).

The system submits questions to multiple LLMs, collects responses, parses answers, and evaluates correctness — with **complete auditability and scientific reproducibility**.

---

## Core Principles

- **Experiments are explicit**
- **Execution is never implicit**
- **All results are auditable**
- **No mutable global state**
- **No execution without identity**
- **No inference during execution**

If something exists in the database, **it means something actually happened**.

---

## Quick Start

```bash
# 1. Create experiment
python bcllm.py --create-experiment my_exp --add-questions "1-10"

# 2. Add model variant (separate command, one per command)
python bcllm.py --experiment my_exp --add-model openai/gpt-4 --reasoning low

# 3. Create run
python bcllm.py --experiment my_exp --add-run

# 4. Execute (requires OPENROUTER_API_KEY as system environment variable)
python bcllm.py --experiment my_exp --execute
```

**Requirements:**
- Python 3.10+
- `OPENROUTER_API_KEY` set as system environment variable (not in `.env`)

---

## High-Level Architecture

```
CLI
 ↓
Planner (read-only)
 ↓
ExecutionPlan (immutable)
 ↓
AsyncOrchestrator (parallel execution)
 ↓
ExecutionEngine (pure execution; no DB)
 ↓
ResultWriter (DB writes only; idempotent)
 ↓
Database
```

**Key Design:**
- Planner reads only; ExecutionEngine executes only; ResultWriter writes only
- Execution plans are immutable; once created, they cannot change
- Results are idempotent; re-execution never creates duplicates

---

## Documentation

This project uses a structured documentation system with clear separation of concerns:

| Type | Location | Purpose |
|------|----------|---------|
| **Contracts** (normative) | `docs/contracts/` | System invariants — non-negotiable |
| **Architecture** (conceptual) | `docs/architecture/` | Design intent & relationships |
| **Reference** (implementation) | `docs/reference/` | Current state details |
| **Guides** (operational) | `docs/guides/` | How to work with the system |
| **Status** (tracking) | `docs/status/` | What exists, issues, roadmap |

**Start here:** `docs/architecture/overview.md` for system at a glance

**For AI agents:** `docs/guides/ai-development-workflow.md` for navigation, contracts, and validation rules

---

## CLI Commands Overview

All commands require `--experiment <name>` or `--create-experiment <name>`.

| Category | Commands |
|----------|----------|
| **Experiments** | `--create-experiment`, `--experiment`, `--list-experiments` (not implemented), `--remove-experiment` (not implemented) |
| **Models** | `--add-model` (one per command), `--list-models`, `--remove-model` |
| **Questions** | `--add-questions`, `--list-questions`, `--remove-question` (not supported — questions are immutable) |
| **Runs** | `--add-run`, `--list-runs`, `--run`, `--remove-run` |
| **Execution** | `--execute` (supports `--run`, `--questions`, `--models` filters) |
| **Export** | `--export` (JSON format) |
| **Review** | `--review-experiment`, `--review-all` (currently blocked by routing issues) |

**Text flags must be quoted** (e.g., `--system-prompt "text with spaces"`)

See `docs/reference/cli-commands.md` for complete command reference.

---

## Configuration

Configuration follows a strict hierarchy:

```
CLI Arguments (highest) → Run/Model → Experiment (frozen) → .env (at creation only) → System Defaults (lowest)
```

**Critical:** `.env` is only consulted at experiment creation time. Run-level and Model-level resolution never falls back to `.env`.

See `docs/reference/configuration-reference.md` for complete .env settings.

---

## Database

- SQLite with 6 tables: experiments, model_variants, question_snapshots, runs, responses, errors
- Identity is immutable (experiments, snapshots, plans)
- Results are append-only (responses, errors)
- Historical data is never deleted
- Full traceability via foreign key chains

See `docs/reference/database-schema.md` for complete schema.

---

## Source of Truth

This project intentionally separates **architecture** from **implementation**.

- **Code is source of truth** — if documentation and code disagree, code wins (unless an ADR states otherwise)
- **Contracts are normative** — they define invariants that must never be violated
- **Roadmap is intent** — planned work is not a promise or guarantee

See `docs/contracts/README.md` for all system invariants.

---

## Final Note

This project prioritizes:

- **clarity over convenience**
- **reproducibility over speed**
- **explicit intent over implicit behavior**

If a feature conflicts with these principles, **the feature is wrong**.

---

## Project Status for Funding Reviewers

The development of **Benchmark LLM** is currently paused due to limited resources required to advance to the next phase of the system. This section is provided specifically for funding reviewers who need evidence of ongoing work, architectural maturity, and project viability.

The project already has a fully structured architecture, well‑defined contracts, a reproducible execution pipeline, and comprehensive documentation. The pause reflects resource constraints — not technical blockers — and the system is ready for continued development as soon as funding becomes available.

The requested funding will enable:

- expansion of experiment coverage and model providers  
- completion of the review and export subsystems  
- strengthening of execution invariants and contract validation  
- progression of the roadmap documented in `docs/status/`  

All existing components remain stable, auditable, and aligned with the project’s core principles: **reproducibility, explicit execution, and full traceability**. The current state represents a solid foundation awaiting the resources necessary to resume active development.

---
