---
type: conceptual
audience: both
last-validated: 2026-04-11
status: active
---

# Design Principles

**Purpose:** Core philosophy, trade-off rationale, and non-goals  
**Scope:** Why the system is designed the way it is

---

## Core Philosophy

### 1. Experiments Are Explicit

No implicit or ad-hoc execution mode exists. Every action must be tied to an explicit experiment with frozen configuration.

**Why:** Research requires intentional design. Ad-hoc execution creates data that cannot be reproduced or audited.

**Trade-off:** Less convenient for quick testing; more rigorous for scientific work.

### 2. Execution Is Never Implicit

The system never decides what to execute on its own. All execution scope is determined by explicit user command.

**Why:** Implicit execution hides behavior and makes debugging impossible.

**Trade-off:** More commands to learn; clearer behavior to audit.

### 3. All Results Are Auditable

Every piece of data traces back to its origin: which experiment, run, model variant, and question produced it.

**Why:** Scientific integrity requires knowing not just the answer, but the complete conditions under which it was generated.

**Trade-off:** More storage overhead; complete data provenance.

### 4. No Mutable Global State

No global variables or shared mutable state exists. All state is scoped to explicit entities (experiments, runs, plans).

**Why:** Mutable global state makes behavior unpredictable and debugging impossible.

**Trade-off:** More explicit parameter passing; predictable behavior.

### 5. No Execution Without Identity

Every execution has a unique identity (run_id, plan_id). No anonymous or untracked execution exists.

**Why:** Without identity, results cannot be audited or reproduced.

**Trade-off:** Must create runs before executing; complete traceability.

### 6. No Inference During Execution

The system never guesses what configuration to use. All configuration is resolved before execution begins.

**Why:** Inference creates hidden behavior that cannot be audited.

**Trade-off:** More upfront configuration; no surprises during execution.

---

## Trade-Off Decisions

### Reproducibility Over Speed

**Decision:** Same configuration always produces same requests, even if execution takes longer.

**Rationale:** As a research tool, reproducibility is more important than execution speed. Results must be verifiable.

**Impact:** Sequential execution was the original design; parallel execution was added later with careful design to maintain content determinism (even if temporal order varies).

### Explicit Over Implicit

**Decision:** No auto-detection, no smart defaults that hide behavior, no inference.

**Rationale:** Implicit behavior is the enemy of auditability. If the system "figures out" what to do, that decision cannot be audited.

**Impact:** Users must be explicit about their intent. More commands, clearer behavior.

### Append-Only Over Mutable

**Decision:** Results are appended, never updated. Historical data is immutable.

**Rationale:** If data changes, the audit trail is broken. Scientists must trust that data represents what actually happened.

**Impact:** More storage usage; complete historical record. Review annotations are additive, not replacements.

### Freezing Over Flexibility

**Decision:** Experiment configuration is frozen at creation (with controlled growth exceptions).

**Rationale:** If experiment configuration changes, prior results are no longer comparable. Freezing ensures comparability.

**Impact:** Cannot retroactively change experiment settings. Must create new experiment or new run with different settings.

### Read/Write Separation Over Convenience

**Decision:** Planner reads only; ExecutionEngine executes only; ResultWriter writes only.

**Rationale:** Separation of concerns makes each component auditable and testable independently.

**Impact:** More components to understand; each component is simpler and more testable.

---

## Non-Goals

The following are **explicitly not goals** for this system:

| Non-Goal | Rationale |
|----------|-----------|
| Real-time model serving | This is batch-oriented, not an API service |
| Model training or fine-tuning | Evaluates existing models only |
| Automated research insights | Collects data; analysis is downstream |
| Built-in visual dashboards | Export enables external visualization; dashboards may be added as separate tooling |
| Multi-user collaboration | Single-user research tool |
| Cloud-native deployment | Local execution with SQLite |
| Built-in model comparison UI | Data export enables external analysis; comparison UI may be a future extension |
| Automatic experiment design | Human controls research intent |

---

## What Changed and Why

### Parallel Execution (Added)

**Original design:** Sequential execution only  
**Change:** Parallel execution support added  
**Why:** Large experiments take hours; parallelism reduces wall-clock time  
**Constraint:** Determinism applies to content, not temporal order

### Logging System (Added)

**Original design:** Minimal logging  
**Change:** Comprehensive configurable logging with file rotation  
**Why:** Logs are scientific data; enable debugging and process analysis  
**Contract:** Logs include experiment/run/model/question identifiers

### Retry Safety (Added)

**Original design:** Basic retry  
**Change:** Centralized retry with exponential backoff  
**Why:** API failures are common; aggressive retry loops are harmful  
**Contract:** All API calls go through centralized retry (no bypass)

---

## What Has NOT Changed

| Principle | Status | Rationale |
|-----------|--------|-----------|
| Determinism | ✅ Unchanged | Core to research integrity |
| Idempotency | ✅ Unchanged | Prevents duplicate data |
| Immutability | ✅ Unchanged | Historical data cannot change |
| Configuration Hierarchy | ✅ Unchanged | Predictable resolution |
| Explicit Over Implicit | ✅ Unchanged | Auditability requires explicitness |
| Append-Only Results | ✅ Unchanged | Audit trail integrity |

---

## For AI Agents

When working on this system:

1. **Respect the principles** — If a change violates a principle, reconsider the approach
2. **Do not optimize for convenience** — Principles prioritize correctness over convenience
3. **Do not add implicit behavior** — Everything must be explicit and auditable
4. **Do not introduce mutable global state** — Scope state to explicit entities
5. **Do not bypass component boundaries** — Planner reads, Engine executes, Writer writes

If you're unsure whether a change aligns with these principles, **flag it for human review**.

---

## Related Documents

- [overview.md](overview.md) — System at a glance
- [contracts/](../contracts/README.md) — System invariants
- [conceptual-model.md](conceptual-model.md) — Entity relationships
- [execution-architecture.md](execution-architecture.md) — Component data flow

---

**These principles are the system's north star. Changes that conflict with them require explicit human approval.**
