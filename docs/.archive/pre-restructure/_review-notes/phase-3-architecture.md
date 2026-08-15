# Phase 3 Review Notes - Architecture

**Phase:** 3 - Architecture Documents  
**Date:** 2026-04-11  
**Status:** ✅ Complete — Awaiting Review

---

## What Was Done

Created 5 architecture documents in `docs/architecture/`:

1. ✅ **overview.md** — System purpose, scope, philosophy, capabilities, technology stack
2. ✅ **conceptual-model.md** — Core entities (Experiment, Model Variant, Question Snapshot, Run, Response), relationships, lifecycle
3. ✅ **execution-architecture.md** — Planner/Engine/Writer separation, data flow, parallel execution, error handling
4. ✅ **design-principles.md** — 6 core principles, trade-off decisions, non-goals, what changed/what hasn't
5. ✅ **adr/000-template.md** — ADR format guide with example

---

## Sources Used

### Primary Sources (Code Inspection)
- `bcllm.py` — CLI dispatcher, composite flow handling
- `src/core/planner.py` — Read-only plan builder
- `src/core/execution_engine.py` — Pure execution (1173 lines)
- `src/core/execution_plan.py` — Immutable dataclasses
- `src/core/result_writer.py` — Database writes only
- `src/db/schema.py` — Database schema
- `src/db/models.py` — Entity dataclasses
- `src/cli/bcllm_experiment.py` — Experiment management
- `src/review/review_ui.py` — Review interface

### Secondary Sources (Archive Reference)
- `archive/pre-restructure/to-be/` — Architecture docs (validated against code)
- `archive/pre-restructure/contracts/` — Existing contracts (aligned with architecture)

---

## Architecture Design Decisions

### 1. CQRS-Inspired Separation

Architecture follows read/write/execution separation:
- **Planner:** Read-only
- **ExecutionEngine:** Pure execution (no DB)
- **ResultWriter:** Only DB writes

**Why:** Makes each component independently auditable and testable.

### 2. Entity-Centric Conceptual Model

Documents focus on entities and their relationships rather than implementation details.

**Why:** Architecture changes slowly; implementation changes frequently. Entity relationships are stable.

### 3. Non-Goals Explicitly Stated

Design principles include "what this system is NOT" section.

**Why:** Prevents scope creep and misguided feature requests.

### 4. ADR Template Provided

Created reusable ADR format with example.

**Why:** Ensures consistency when architectural decisions need documentation.

---

## Adjustments Applied (Post-Review)

### 1. Async Orchestrator Audit ✅

**Finding:** Documentation is accurate; no discrepancies found.

**Details:**
- `AsyncOrchestrator` uses `asyncio.Semaphore` for concurrency control
- Sliding window pattern dynamically fills freed slots
- `max_concurrency` defaults to 1 (sequential), configurable via `.env`
- Single `asyncio.run()` call; httpx client lifecycle managed internally
- Writer drains all queued items before returning
- Abort event propagates from writer to engine for early termination
- RunFinalizer updates status/duration after execution

**Conclusion:** Documented behavior matches implementation.

### 2. Non-Goals Wording Softened ✅

**Changes:**
- "Visual dashboards" → "Built-in visual dashboards" (may be added as separate tooling)
- "Model comparison UI" → "Built-in model comparison UI" (may be a future extension)

**Rationale:** These are not core responsibilities today, but are not forbidden future directions.

### 3. API Layer Provider-Agnostic Note Added ✅

**Added section:** "API Layer" in execution-architecture.md
- Clarifies OpenRouter is current implementation, not conceptual dependency
- System is provider-agnostic by design
- API client is abstract interface; multiple providers supported
- Local serving (llama.cpp) also supported via separate client

---

## Potential Issues for Review

### 🔴 Critical (Need Your Input)

1. ~~**Parallel Execution Description:**~~ ✅ Resolved by audit
2. ~~**Entity Relationships:**~~ ✅ Confirmed correct (Response is convergence entity)
3. ~~**Non-Goals:**~~ ✅ Resolved (wording softened)

### 🟡 Non-Critical (Log for Later)

1. **API Layer Details:**
   - Execution architecture mentions OpenRouterClient but doesn't detail the API layer
   - Will be covered in reference/api-integration.md (Phase 4)

2. **Logging Architecture:**
   - Mentioned in overview but not detailed
   - Will be covered when logging is audited against code

3. **Review UI Flow:**
   - Mentioned in overview but not detailed in architecture
   - Will be covered in reference documents

---

## Compliance Check

Per the restructuring plan:

| Requirement | Status | Notes |
|-------------|--------|-------|
| Architecture describes concepts | ✅ | Entity relationships, data flow |
| Architecture separate from reference | ✅ | Implementation details deferred to Phase 4 |
| ADR template provided | ✅ | Format guide with example |
| Design principles documented | ✅ | 6 principles + trade-offs + non-goals |
| English language | ✅ | All documents in English |
| Audience field in frontmatter | ✅ | All documents tagged |
| No code execution | ✅ | Research-only phase |

---

## Ready for Review

**Files to review:**
1. `docs/architecture/overview.md`
2. `docs/architecture/conceptual-model.md`
3. `docs/architecture/execution-architecture.md`
4. `docs/architecture/design-principles.md`
5. `docs/architecture/adr/000-template.md`

**Review focus:**
- Do architecture documents accurately describe system concepts?
- Are entity relationships correct?
- Are design principles aligned with your intent?
- Is the ADR format acceptable?

---

**Status:** ⏳ Awaiting your review and approval before Phase 4 (Reference documents)
