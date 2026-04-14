# Phase 6 Review Notes - QWEN.md Update

**Phase:** 6 - QWEN.md Update  
**Date:** 2026-04-11  
**Status:** ✅ Complete — Awaiting Review

---

## What Was Done

Completely rewrote `QWEN.md` to reference the new documentation structure and update authority chain.

---

## Changes Made

### 1. Authority Chain Updated ✅

**Before:** Referenced old documents:
- `docs/architecture/to-be/llmbc_system.md`
- `docs/architecture/v2-implementation-checklist.md`
- `docs/architecture/to-be/comandos_simples.md`

**After:** References new structure:
- **Normative:** `docs/contracts/README.md` (all invariants indexed)
- **Conceptual:** `docs/architecture/overview.md`, `conceptual-model.md`, `execution-architecture.md`, `design-principles.md`
- **Reference:** All 5 reference documents
- **Status:** All 3 status documents
- **Operational:** `docs/guides/ai-development-workflow.md`

### 2. Source of Truth Rule Added ✅

Added explicit statement:
> "If documentation conflicts with code, code is the source of truth unless an ADR states otherwise."

### 3. System Contracts Section Added ✅

New table indexing all 7 contracts with what each guarantees. Explicitly states:
- Contracts are normative (constraints, not suggestions)
- Only ADR can override a contract

### 4. Execution Flow Updated ✅

Updated flow diagram to include:
- AsyncOrchestrator (parallel execution)
- Clarified component roles (Planner read-only, Engine no DB, Writer DB-only)

### 5. Configuration Hierarchy Added ✅

Added explicit hierarchy diagram with critical note:
> ".env is only consulted at experiment creation time. Run-level and Model-level resolution never falls back to `.env`"

### 6. CLI Notes Updated ✅

Added critical constraints:
- Text flags must be quoted
- Model variants must be added separately (one per command, after experiment creation)

### 7. AI Agent Working Rules Added ✅

New sections:
- **Absolute Invariants** (5 rules that must never be violated)
- **Violation Detection Protocol** (stop → document → flag → wait → record)
- **Documentation Update Protocol** (reference → status → architecture → contracts)

### 8. Complete Documentation Structure Added ✅

Full directory tree showing:
- contracts/ (normative)
- architecture/ (conceptual)
- reference/ (implementation)
- guides/ (operational)
- status/ (state tracking)
- _review-notes/ (review accumulation)
- archive/ (historical)

**Explicit note:** `docs/maestro/` is NOT part of documentation system.

### 9. Outdated Documentation Notice Updated ✅

Updated to reference:
- `docs/archive/pre-restructure/` — All archived documents
- INVENTORY.md for catalog
- Any document not in new structure

### 10. Core Principles Preserved ✅

All original core principles retained:
- Experiments are explicit
- Execution never implicit
- All results auditable
- No mutable global state
- No execution without identity
- No inference during execution

---

## What Was Removed

- Inline conceptual model details (now reference architecture/conceptual-model.md)
- Inline CLI command details (now reference cli-commands.md)
- Inline database philosophy (now reference database-schema.md)
- Inline environment variables details (now reference configuration-reference.md)
- Outdated document list (now archived with inventory)
- ResultWriter review fields table (now in data-auditability.md contract)

---

## What Was Preserved

- Core principles (6 invariants)
- Project overview
- Conceptual model summary (with reference to full doc)
- Execution flow (updated with async orchestrator)
- Database philosophy (with reference to full schema)
- Environment variables role (with reference to full config doc)
- Final note (principles as north star)

---

## Compliance Check

| Requirement | Status | Notes |
|-------------|--------|-------|
| QWEN.md references new structure | ✅ | All document categories linked |
| Authority chain updated | ✅ | Contracts as normative source |
| Outdated inline imports removed | ✅ | Replaced with references |
| English language | ✅ | All content in English |
| Core principles preserved | ✅ | All 6 invariants retained |
| AI agent rules added | ✅ | Invariants, violation protocol, doc update protocol |

---

## Ready for Review

**File to review:**
- `QWEN.md` (root directory)

**Review focus:**
- Does authority chain correctly point to new structure?
- Are core principles accurately preserved?
- Are AI agent working rules clear and actionable?
- Is documentation structure accurate?

---

**Status:** ⏳ Awaiting your review and approval

After Phase 6 approval, the documentation restructuring project will be **COMPLETE**.
