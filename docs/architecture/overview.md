---
type: conceptual
audience: both
last-validated: 2026-04-11
status: active
---

# System Overview

**Purpose:** System scope, philosophy, and what it is/isn't  
**Scope:** High-level understanding of the Benchmark LLM system

---

## What This System Is

The Benchmark LLM is a **reproducible, experiment-driven benchmarking system** for evaluating Large Language Models (LLMs) against a dataset of questions.

It submits questions to multiple LLMs (via OpenRouter API or local llama.cpp), collects responses, parses answers, and evaluates correctness — all with **complete auditability and scientific reproducibility**.

---

## What This System Is NOT

- ❌ **Not a model training system** — It evaluates existing models, does not train them
- ❌ **Not a real-time inference service** — No API serving; batch-oriented execution
- ❌ **Not a model comparison dashboard** — Focus is on data collection, not visualization (export enables downstream analysis)
- ❌ **Not an automated research pipeline** — Human controls experiment design, execution scope, and review

---

## Core Philosophy

The system prioritizes:

| Principle | Meaning |
|-----------|---------|
| **Clarity over convenience** | Explicit intent; no implicit behavior or inference |
| **Reproducibility over speed** | Same configuration always produces same requests |
| **Auditability over simplicity** | All data traceable to origin; nothing hidden |
| **Explicit over implicit** | No ad-hoc execution; everything intentional |
| **Data integrity over convenience** | Historical data never deleted or modified; append-only results |

**If a feature conflicts with these principles, the feature is wrong.**

---

## System Scope

### Current Capabilities

| Capability | Status | Description |
|------------|--------|-------------|
| Experiment Management | ✅ Implemented | Create, modify, list experiments |
| Model Variant Management | ✅ Implemented | Add/remove model configurations |
| Question Snapshotting | ✅ Implemented | Freeze questions into experiments |
| Run Management | ✅ Implemented | Create/remove execution runs |
| Execution | ✅ Implemented | Execute experiments against models (sequential + parallel) |
| Answer Parsing | ✅ Implemented | Parse LLM responses for selected answer |
| Manual Review | ✅ Implemented | TUI for reviewing ambiguous answers |
| Export | ✅ Implemented | Export results for downstream analysis |
| Configuration Hierarchy | ✅ Implemented | System → .env → Experiment → Run/Model |
| Logging | ✅ Implemented | Configurable logging with file rotation |
| Retry Safety | ✅ Implemented | Centralized retry with backoff |
| API Integration | ✅ Implemented | OpenRouter client + local llama.cpp support |

### Planned Capabilities

| Capability | Status | Description |
|------------|--------|-------------|
| Enhanced Review UI | 📝 Planned | Multi-language (PT/EN), multi-level undo, batch ops |
| Parallel Execution Optimization | 📝 Planned | Improved concurrency controls |
| Advanced Analytics | 📝 Planned | Built-in analysis beyond export |

---

## System Architecture at a Glance

```
User (CLI)
    ↓
bcllm.py (dispatcher)
    ↓
┌─────────────────────────────────────┐
│  CLI Modules (src/cli/)             │
│  - bcllm_experiment.py              │
│  - bcllm_model.py                   │
│  - bcllm_questions.py               │
│  - bcllm_run.py                     │
│  - bcllm_execute.py                 │
│  - bcllm_review.py                  │
│  - bcllm_export.py                  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Core Components (src/core/)        │
│  - Planner (read-only)              │
│  - ExecutionEngine (pure execution) │
│  - ResultWriter (DB writes only)    │
│  - ConfigResolver                   │
│  - AnswerParser                     │
│  - AnswerRandomizer                 │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  API Layer (src/api/)               │
│  - OpenRouterClient                 │
│  - Response Parser                  │
│  - Error Handling                   │
│  - Stream Aggregator                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│  Database Layer (src/db/)           │
│  - SQLAlchemy-like models           │
│  - Repository pattern               │
│  - Schema management                │
└─────────────────────────────────────┘
    ↓
SQLite Database (benchmark.db)
```

---

## Key Entities

| Entity | Purpose | Immutability |
|--------|---------|--------------|
| **Experiment** | Research intent + frozen configuration | Mostly immutable (can grow) |
| **Model Variant** | Intentional model configuration | Immutable after creation |
| **Question Snapshot** | Snapshotted question payload | Immutable |
| **Run** | Execution instance | Config frozen; status mutable |
| **ExecutionPlan** | Immutable description of work | Fully immutable |
| **Response** | LLM answer result | Original data immutable; review fields mutable |
| **Error** | Execution error record | Immutable |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| Database | SQLite 3 |
| CLI | argparse |
| TUI (Review) | Rich |
| API Client | httpx (async) |
| Configuration | python-dotenv |
| Testing | pytest |

---

## Related Documents

- [contracts/](../contracts/README.md) — System invariants and guarantees
- [conceptual-model.md](conceptual-model.md) — Entity relationships and lifecycle
- [execution-architecture.md](execution-architecture.md) — Component data flow
- [design-principles.md](design-principles.md) — Philosophy and trade-offs

---

**This document provides the 10,000-foot view. For details, see the linked documents.**
