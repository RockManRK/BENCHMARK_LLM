# V2 Implementation Plan

**Document Type:** Implementation Checklist
**Project:** Benchmark LLM V2
**Version:** 1.0
**Date:** 2026-03-29
**Status:** Actionable
**Complete Plan:** @docs\architecture\v2-implementation-plan.md

---

# ✅ V2 — Implementation Checklist (Single Source of Execution Truth)

> **Referenced by:** `@docs\architecture\v2-implementation-plan.md`  
> **Purpose:** This document is the **only operational checklist** for implementation.  
> All agents must follow this checklist **and** the Fundamental System Contracts.

---

# Steps for each implementation block:

A block corresponds to one or more related capabilities defined in:
@docs/architecture/v2-implementation-checklist.md

1. Create a commit to save the current project state;

2. Implement the capabilities defined for this block, respecting:
   - the implementation checklist
   - the fundamental system contracts

3. Run applicable smoke tests (structural or runtime, depending on activation);

4. Perform a technical review focusing on:
   - correctness
   - code quality
   - edge cases
   - test coverage

5. Invoke the Essence Guardian sub-agent ('essence-guardian') to evaluate:
   - adherence to system contracts
   - architectural consistency
   - risk of conceptual drift

6. Apply corrections if required by reviews;

7. Present a concise report to the user summarizing:
   - what was implemented
   - what was validated
   - any deferred activations or risks

8. Do not proceed to the next block without explicit user approval.

---

## 🧠 How to Use This Checklist

- This checklist defines **what must exist**, **when it becomes active**, and **how it is validated**
- Items are **not phases** — they are **capabilities**
- Capabilities move through three states:
  - **CAPABILITY (STRUCTURAL)** — must exist in code
  - **ACTIVATION (RUNTIME)** — becomes usable
  - **VALIDATION** — behavior confirmed

> **Rule:**  
> You may implement CAPABILITY at any time.  
> You may only VALIDATE after ACTIVATION is possible.

---

## 🛑 Global Rules (Always Enforced)

- All changes must respect the Fundamental System Contracts
- No capability may violate:
  - determinism
  - idempotency
  - logical immutability
  - configuration hierarchy
- CLI is never a configuration level
- `system-default` always bypasses inheritance
- Logs are scientific data
- No capability is considered complete until validated

---

## 🔴 Capability: Logging & Observability

### CAPABILITY (STRUCTURAL)
- Logging system configurable via `.env`
- Logs written to file and console
- Log rotation enabled
- Logs include identifiers:
  - experiment
  - run
  - model
  - question
- Logs are crash‑safe
- Logs do not expose sensitive data

### ACTIVATION (RUNTIME)
- Activated immediately (no dependency)

### VALIDATION
- Logs appear on startup
- Logs persist after abrupt interruption
- Logs correctly tag experiment/run/model/question

---

## 🔴 Capability: Retry Safety

### CAPABILITY (STRUCTURAL)
- Single centralized retry mechanism exists
- No API call path exists outside retry
- Retry uses exponential backoff
- Retry has max delay cap
- Retry attempts are logged

### ACTIVATION (RUNTIME)
- Activated when real API execution exists

### VALIDATION
- Retry delay observed in real failures
- No aggressive retry loops
- Retry behavior visible in logs

---

## 🟠 Capability: Execution Core

### CAPABILITY (STRUCTURAL)
- ExecutionEngine is the only execution entry point
- Planner is read‑only
- ResultWriter is idempotent
- Execution plan supports partial execution

### ACTIVATION (RUNTIME)
- Activated when execution is wired to real models

### VALIDATION
- Partial execution works
- Reexecution skips completed items
- No duplicate data generated

---

## 🟠 Capability: Export Results

### CAPABILITY (STRUCTURAL)
- Export operates only on persisted data
- Export does not modify data
- Export respects immutability
- Export structure exists even with no data

### ACTIVATION (RUNTIME)
- Activated after first real execution

### VALIDATION
- Export reflects partial executions
- Export consistent after reexecution
- No duplicated or missing entries

---

## 🟠 Capability: Review UI

### CAPABILITY (STRUCTURAL)
- UI supports PT and EN
- Undo history exists
- Undo does not violate immutability
- Batch classification exists structurally

### ACTIVATION (RUNTIME)
- Activated when real data exists

### VALIDATION
- Undo reverts DB state
- Batch classification persists correctly
- Review can be paused and resumed

---

## 🟡 Capability: Execution Control

### CAPABILITY (STRUCTURAL)
- Dry‑run mode exists
- Timeout configurable via `.env`

### ACTIVATION (RUNTIME)
- Activated during real execution

### VALIDATION
- Dry‑run validates plan without execution
- Timeout supports long reasoning models

---

## 🔵 Capability: Documentation & Closure

### CAPABILITY (STRUCTURAL)
- Architecture documented
- Contracts documented
- Accepted gaps recorded

### ACTIVATION (RUNTIME)
- Not applicable

### VALIDATION
- Documentation matches implementation

---

## 🧾 Completion Rules

- A capability is **implemented** when CAPABILITY is complete
- A capability is **usable** when ACTIVATION is possible
- A capability is **done** only after VALIDATION
- The Essence Guardian must review before marking VALIDATION complete

---

## ✔️ Final Notes

- This checklist is **the only execution guide**
- The implementation plan references this checklist
- No additional documents are required
- No agent should invent steps outside this checklist