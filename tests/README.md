# Benchmark LLM

**Reproducible, experiment-driven LLM benchmarking.**

The system is designed around **explicit experiments**, **immutable execution plans**, and **auditable results**.

**No immediate execution. No ad-hoc flows. No ambiguity.**

---

## Quick Start

```bash
# 1. Create experiment
bcllm --create-experiment my_exp --questions Q001-Q050 --seed 42

# 2. Add models
bcllm --experiment my_exp --add-model openai/gpt-4 --add-model anthropic/claude-3

# 3. Create run
bcllm --experiment my_exp --create-run

# 4. Execute
bcllm --experiment my_exp --run

# 5. Review ambiguous answers (if any)
bcllm --review-experiment my_exp

# 6. Export results
bcllm --export-results <run_id>
```

**Full documentation:** [`MANUAL.md`](MANUAL.md)

---

## How It Works

### Execution Flow (SINGLE PATH)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Planner (DB Read-Only)                                   │
│    - Resolves experiment, runs, variants, snapshots         │
│    - Applies filters, deduplicates                          │
│    - Builds immutable ExecutionPlan                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ExecutionEngine (API Calls, NO DB)                       │
│    - Executes exactly what the plan defines                 │
│    - Returns ExecutionResult[]                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ResultWriter (DB Write-Only)                             │
│    - Persists responses/errors                              │
│    - Updates run status                                     │
│    - Guarantees idempotency                                 │
└─────────────────────────────────────────────────────────────┘
```

### Key Concepts

| Concept | What It Is | Why It Exists |
|---------|------------|---------------|
| **Experiment** | Frozen research configuration | Reproducibility |
| **Model Variant** | Intentional model configuration | Clear identity |
| **Question Snapshot** | Immutable question copy | Audit trail |
| **Run** | Concrete execution unit | Groups executions with same seed |
| **ExecutionPlan** | Immutable work description | Separates planning from execution |

---

## Core Principles

| Principle | Meaning |
|-----------|---------|
| **Experiments are explicit** | Every experiment is created intentionally |
| **Execution is never implicit** | No immediate/ad-hoc execution mode |
| **All results are auditable** | Responses reference immutable snapshots |
| **No mutable global state** | Configuration frozen per experiment |
| **No execution without identity** | Variants created before execution |
| **No inference during execution** | ExecutionEngine decides nothing |

**If a result exists in the database, it means something actually happened.**

---

## What Is NOT Supported (By Design)

| Feature | Status | Why |
|---------|--------|-----|
| Direct execution (`--models`) | NOT SUPPORTED | Violates "explicit execution" principle |
| Test mode (in-memory DB) | NOT SUPPORTED | All execution requires experiment |
| Review metadata (timestamps, identity) | NOT SUPPORTED | Minimal review contract |

**These are conscious design decisions, not omissions.**

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`MANUAL.md`](MANUAL.md) | Complete user manual with workflow examples |
| [`QWEN.md`](QWEN.md) | Architectural mental model (source of truth) |
| [`docs/architecture/contracts/`](docs/architecture/contracts/) | Active architectural contracts |
| [`docs/FINAL_CLOSURE_REPORT.md`](docs/FINAL_CLOSURE_REPORT.md) | Project closure report |

**If documentation and code disagree, the documents are correct.**

---

## Database Philosophy

- **Identity is immutable** — Variants and snapshots never change
- **Results are append-only** — Execution outcomes are never modified
- **Historical data is never deleted** — Audit trail is permanent
- **Reexecution creates new plan** — Never reuses old ExecutionPlan

---

## Project Status

**COMPLETE BY DESIGN**

The system implements exactly what the architectural contracts specify:
- ✅ One execution path (Planner → Engine → Writer)
- ✅ One review path (ReviewUI queries `needs_review = TRUE`)
- ✅ Thin CLI (orchestration only, no domain logic)
- ✅ Minimal schema (no unnecessary tables or fields)

**Future work is OPTIONAL enhancement, not required completion.**

---

## Final Note

This project prioritizes:

- **Clarity** over convenience
- **Reproducibility** over speed
- **Explicit intent** over implicit behavior

If a feature conflicts with these principles, **the feature is wrong**.