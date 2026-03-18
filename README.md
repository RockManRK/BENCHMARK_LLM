# Benchmark LLM

Benchmark LLM is a **reproducible, experiment‑driven benchmarking system** for evaluating Large Language Models (LLMs).

The system is designed around **explicit experiments**, **immutable execution plans**, and **auditable results**.  
There is **no immediate or ad‑hoc execution mode** in the core system.

---

## Core Principles

- Experiments are explicit
- Execution is never implicit
- All results are auditable
- No mutable global state
- No execution without identity
- No inference during execution

If a result exists in the database, **it means something actually happened**.

---

## Conceptual Architecture

The system is structured around three immutable contracts:

- **ExecutionPlan** — what must be executed
- **ExecutionEngine** — executes exactly what the plan defines
- **ResultWriter** — persists outcomes without deciding scope

High‑level flow:

```
CLI
 ↓
Planner
 ↓
ExecutionPlan (immutable)
 ↓
ExecutionEngine
 ↓
ResultWriter
 ↓
Database
```

---

## Source of Truth

This project intentionally separates **architecture** from **implementation**.

### Architectural contracts (DO NOT MODIFY):
- `docs/architecture/execution-plan.md`
- `docs/architecture/result-writer.md`

### System mental model:
- `QWEN.md`

If documentation and code disagree, **the documents are correct**.

---

## Command Line Interface (Overview)

The CLI is **explicit and declarative**.

There is **no immediate execution mode**.

All executions belong to:
- an experiment
- a run
- a resolved execution plan

Examples (conceptual):

```bash
EXE --create-experiment my_exp
EXE --experiment my_exp --add-model openai/gpt-4
EXE --experiment my_exp --add-questions 1-10
EXE --experiment my_exp --create-run run1
EXE --experiment my_exp --run run1 --execute
```

---

## Database Philosophy

- Identity is immutable
- Results are append‑only
- Historical data is never deleted
- Reexecution always creates a new ExecutionPlan

---

## Documentation Status

The following documents are **known to be outdated** and should not be used as reference until rewritten:

- Legacy CLI examples
- Old execution flows
- Any reference to “quick tests”, “direct flow”, or “iterations”

They are intentionally excluded from this README.

---

## Final Note

This project prioritizes:

- clarity over convenience
- reproducibility over speed
- explicit intent over implicit behavior

If a feature conflicts with these principles, **the feature is wrong**.