# Phase 2 Review Notes - Contracts

**Phase:** 2 - Contracts  
**Date:** 2026-04-11  
**Status:** ✅ Complete — Awaiting Review

---

## What Was Done

Created 8 contract documents in `docs/contracts/`:

1. ✅ **README.md** — Index, source-of-truth statement, agent usage rules
2. ✅ **determinism.md** — Same config → same requests; seed behavior; experimental truth
3. ✅ **idempotency.md** — No duplicate data; UNIQUE constraint pattern; partial reexecution
4. ✅ **immutability.md** — Snapshots, plans, historical data cannot be modified; append-only philosophy
5. ✅ **configuration-hierarchy.md** — System > .env > experiment > run/model inheritance; freezing rules
6. ✅ **system-default-semantics.md** — `system-default` bypasses inheritance; parameter defaults table
7. ✅ **data-auditability.md** — Full traceability; response provenance; review trail; logging as data
8. ✅ **interaction-contracts.md** — 📝 Placeholder with TODOs for UI/event invariants

---

## Sources Used

### Primary Sources (Code Inspection)
- `src/core/execution_engine.py` — Randomization contract, execution flow
- `src/core/execution_plan.py` — Immutability (frozen dataclasses)
- `src/core/result_writer.py` — Idempotency (INSERT OR IGNORE pattern)
- `src/core/randomizer.py` — Seed=None vs seed=int behavior
- `src/core/config_resolver.py` — Hierarchy resolution, system-default handling
- `src/db/models.py` — Entity structure, traceability fields
- `src/db/schema.py` — Database constraints

### Secondary Sources (Archive Reference)
- `archive/pre-restructure/to-be/llmbc_system.md` — System rules (authoritative per QWEN.md)
- `archive/pre-restructure/to-be/comandos_simples.md` — CLI specification (authoritative per QWEN.md)
- `archive/pre-restructure/contracts/` — Existing contracts (validated against code)

---

## Contract Design Decisions

### 1. Explicit Over Implicit

All contracts state **what** the invariant is, **why** it exists, and **examples** of correct/incorrect behavior. No inference required.

### 2. Code-Aligned

Contracts were written by inspecting actual code first, then documenting the invariant the code implements. If code doesn't match old docs, code wins.

### 3. Agent-Focused

Contracts include:
- "How AI Agents Must Use" section (in README.md)
- Violation examples (❌ WRONG vs ✅ CORRECT)
- Clear "non-negotiable" statements
- Related contracts cross-references

### 4. Placeholder Acknowledged

`interaction-contracts.md` is explicitly marked as placeholder with TODOs. This prevents AI agents from assuming it's complete while providing structure for future work.

---

## Potential Issues for Review

### 🔴 Critical (Need Your Input)

1. **Seed Contract Accuracy:**
   - Contract states: `seed=None` → randomization OFF; `seed=int` → randomization ON
   - Code shows: `AnswerRandomizer` follows this pattern
   - **Question:** Is this the correct behavior? (Old docs may have conflicted)

2. **Configuration Freezing Exceptions:**
   - Contract states: Experiments can add questions/models but not modify frozen config
   - **Question:** Is this accurate? Can prompts be changed on existing experiments? (Code allows it, but does it affect existing runs?)

3. **System-Default Table:**
   - I documented system defaults as "None = not sent in API request" for most parameters
   - **Question:** Is this accurate for all parameters? Any exceptions?

### 🟡 Non-Critical (Log for Later)

1. **Interaction Contracts Placeholder:**
   - Left as TODO pending review UI implementation audit
   - Should we prioritize completing this contract?

2. **Logging Boundaries:**
   - Mentioned in data-auditability.md but not fully specified
   - Should logging have its own contract section?

3. **Error Classification:**
   - Error types and classification not fully documented in contracts
   - May need to be added when error handling architecture is reviewed

---

## Compliance Check

Per the implementation checklist requirements:

| Capability | Contract Coverage | Status |
|------------|------------------|--------|
| Logging & Observability | Partially (data-auditability.md mentions logging) | ⚠️ Needs interaction-contracts.md completion |
| Retry Safety | Not in contracts (implementation detail) | ✅ Not a system invariant |
| Execution Core | ✅ determinism.md, idempotency.md, immutability.md | ✅ Covered |
| Export Results | ✅ idempotency.md (export operates on persisted data) | ✅ Covered |
| Review UI | ⚠️ interaction-contracts.md is placeholder | ⏳ Needs completion |
| Execution Control | ✅ configuration-hierarchy.md (timeout via .env) | ✅ Covered |

---

## Revision History

### 2026-04-11 — Seed Semantics Correction (User Review)

**Issue:** Seed behavior was underspecified (missing AUTO state)

**Changes applied:**
1. ✅ Added three-state seed behavior table (None, AUTO, int)
2. ✅ Documented experiment → run resolution step
3. ✅ Clarified that AUTO never exists at run level (resolved to int)
4. ✅ Updated execution order section (parallel is already implemented, not future)
5. ✅ Updated seed inheritance section for consistency

**Status:** ✅ Resolved — Awaiting final approval

---

## Ready for Review

**Files to review:**
1. `docs/contracts/README.md`
2. `docs/contracts/determinism.md`
3. `docs/contracts/idempotency.md`
4. `docs/contracts/immutability.md`
5. `docs/contracts/configuration-hierarchy.md`
6. `docs/contracts/system-default-semantics.md`
7. `docs/contracts/data-auditability.md`
8. `docs/contracts/interaction-contracts.md`

**Review focus:**
- Do contracts accurately reflect actual code behavior?
- Are there any invariants missing?
- Are the violation examples clear?
- Is the system-default table accurate?

---

**Status:** ⏳ Awaiting your review and approval before Phase 3 (Architecture)
