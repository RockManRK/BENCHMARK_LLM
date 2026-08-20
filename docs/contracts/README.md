---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# System Contracts Index

**Purpose:** Authoritative index of all system invariants and guarantees  
**Authority:** These contracts are non-negotiable unless superseded by an Architecture Decision Record (ADR)  
**Source of Truth Rule:** If documentation conflicts with code, **code is the source of truth** unless an ADR states otherwise

---

## Contract Registry

| Contract | Scope | Last Updated | Status |
|----------|-------|--------------|--------|
| [determinism.md](determinism.md) | Execution reproducibility | 2026-04-11 | ✅ Active |
| [idempotency.md](idempotency.md) | Execution & data writes | 2026-04-11 | ✅ Active |
| [immutability.md](immutability.md) | Snapshots, plans, history | 2026-04-11 | ✅ Active |
| [configuration-hierarchy.md](configuration-hierarchy.md) | Config resolution | 2026-04-11 | ✅ Active |
| [system-default-semantics.md](system-default-semantics.md) | system-default behavior | 2026-08-19 | ✅ Active |
| [data-auditability.md](data-auditability.md) | Data traceability | 2026-04-11 | ✅ Active |
| [interaction-contracts.md](interaction-contracts.md) | Event emission, UI boundaries | 2026-08-18 | 🟡 Partial — CLI Output Boundaries normative (ADR-002); Review UI, Event Emission, Logging Boundaries still placeholder |

---

## How AI Agents Must Use Contracts

### Mandatory Rules

1. **Treat contracts as constraints** — Never propose or implement changes that violate contracts
2. **Validate against code** — Contracts describe intent; code implements reality. If they diverge, flag for human review
3. **ADR supersedes contracts** — Only an Architecture Decision Record can override a contract
4. **No inference** — Never assume behavior not explicitly stated in contracts or code

### Change Protocol

To modify a contract:
1. Create an ADR documenting why the change is needed
2. Get human approval
3. Update the contract
4. Update this index with new `last-validated` date

---

## Core System Philosophy

The Benchmark LLM system prioritizes:
- **Clarity over convenience** — Explicit intent, no implicit behavior
- **Reproducibility over speed** — Same config always produces same requests
- **Auditability over simplicity** — All data traceable to origin
- **Explicit over implicit** — No inference, no ad-hoc execution

If a feature conflicts with these principles, **the feature is wrong**.

---

## Contract Violation Handling

If an AI agent detects a contract violation in code or documentation:
1. **Do not assume correctness** — Flag the violation explicitly
2. **Present all evidence** — Show contract text, conflicting code/doc, and impact
3. **Pause for human decision** — Do not proceed until human resolves the ambiguity
4. **Record the decision** — If human clarifies behavior, create ADR if architectural

---

**This document is the entry point for all system contracts.**  
All AI agents working on this codebase must read and understand these contracts before making changes.
