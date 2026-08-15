# Phase 4 Review Notes - Reference Documents

**Phase:** 4 - Reference Documents  
**Date:** 2026-04-11  
**Status:** ✅ Complete — Awaiting Review

---

## What Was Done

Created 5 reference documents in `docs/reference/`:

1. ✅ **cli-commands.md** — Complete CLI command reference (all commands, flags, system-default support)
2. ✅ **configuration-reference.md** — Complete `.env` settings reference (6 categories, resolution algorithm)
3. ✅ **database-schema.md** — Current database schema with field descriptions (6 tables, indexes, FKs)
4. ✅ **module-structure.md** — `src/` layout and responsibility per module (43 files, ~9050 lines)
5. ✅ **api-integration.md** — OpenRouter and local model serving details (client, retry, parsing, errors)

---

## Sources Used

### Primary Sources (Code Inspection)
- `bcllm.py` — CLI dispatcher
- `src/cli/bcllm_main.py` — Command definitions
- `src/cli/bcllm_execute.py` — Execution entry point
- `src/cli/bcllm_experiment.py` — Experiment management
- `src/db/schema.py` — Complete schema SQL
- `src/db/models.py` — Entity dataclasses
- `src/api/client.py` — OpenRouterClient
- `src/api/errors.py` — Error types
- `src/api/message_builder.py` — Message construction
- `src/api/response_parser.py` — Answer parsing
- `src/api/stream_aggregator.py` — Streaming handling
- `src/core/retry.py` — Retry handler
- `.env.example` — Configuration template

### Secondary Sources (Archive Reference)
- `archive/pre-restructure/to-be/comandos_simples.md` — CLI specification (authoritative per QWEN.md)
- `archive/pre-restructure/contracts/` — Existing contracts (aligned with reference)

---

## Reference Design Decisions

### 1. Code-Aligned

All reference documents were written by inspecting actual code first, then documenting what exists.

**Why:** Reference describes implementation; code is source of truth.

### 2. Structured by Layer

Each document covers a distinct layer:
- CLI (user interface)
- Configuration (settings)
- Database (persistence)
- Modules (code organization)
- API (external integration)

**Why:** Makes it easy to find information by concern.

### 3. Complete but Concise

Documents include all necessary detail without implementation specifics.

**Why:** Reference should answer "what exists" and "how to use", not "how it's implemented".

---

## Adjustments Applied (Post-Review)

### 1. CLI Documentation - Flag Quoting and Composite Flows ✅

**Changes:**
- Added explicit section: "Text Flags Must Be Quoted" with correct/incorrect examples
- Removed `--add-model` from composite flow example
- Added explicit section: "Model Variants Must Be Added Separately" with step-by-step examples
- Documented constraint: Only one model variant per `--add-model` command

### 2. Remove Question Deletion ✅

**Changes:**
- Removed `--remove-question` command entirely
- Added note under List Questions: "Questions are immutable once added to an experiment. To change questions, create a new experiment with the desired question set."

### 3. Retry Policy ✅

**Changes:**
- Removed `--retry-policy` flag from Execute command filters table
- Added note: "Retry is configured via `.env` only. Retry policy cannot be overridden via CLI."

### 4. Configuration Reference Corrections ✅

**Changes:**
- Question IDs: Changed from `Q***` format to **numeric indices** (e.g., `1`, `5`, `10`)
- Run defaults updated:
  - `RUN_RESPONSES_SEED` default: `None` (not `AUTO`)
  - `SYSTEM_PROMPT` default: `None` (not sent)
  - `USER_PROMPT` default: `None` (not sent)
- Replaced "blank" wording with explicit `None` semantics
- Added "Prompt Behavior" section explaining None = not sent

### 5. Configuration Resolution Hierarchy ✅

**Changes:**
- Updated hierarchy diagram: `.env (used ONLY at experiment creation)`
- Added explicit warning: "Run-level and Model-level resolution **never falls back to `.env`**"
- Split resolution algorithm into two paths:
  - At experiment creation (CLI → .env → System)
  - For runs/models (Run/Model → Experiment → System)

### 6. Database Schema Verification ✅

**Changes:**
- Verified against both `src/db/schema.py` AND `src/db/schema.sql`
- Updated indexes table with all 16 indexes (added missing ones):
  - `idx_experiments_created_at`
  - `idx_model_variants_created_at`
  - `idx_question_snapshots_created_at`
  - `idx_runs_created_at`
  - `idx_responses_needs_review`, `idx_responses_started_at`, `idx_responses_finished_at`
  - `idx_errors_occurred_at`
- Corrected `errors` table structure (matches schema.sql: no `response_id`, no `attempt_number` in PK)
- Updated FK relationships section

### 7. Configuration Categories ✅

**Acknowledged:** Grouping is reference organization only, not behavioral boundaries. No changes needed.

---

## Potential Issues for Review

### 🔴 Critical (Need Your Input)

1. ~~**CLI Commands Completeness:**~~ ✅ Resolved (quoting, composite flows documented)
2. ~~**Configuration Categories:**~~ ✅ Resolved (grouping confirmed acceptable)
3. ~~**Schema Accuracy:**~~ ✅ Resolved (verified against schema.py AND schema.sql)
4. ~~**API Provider-Agnostic Note:**~~ ✅ Resolved (accurately reflects intent)

### 🟡 Non-Critical (Log for Later)

1. **Response Parser Patterns:**
   - Documented general patterns, not exhaustive regex
   - May need updates as patterns evolve

2. **Error Classification:**
   - Documented error types from `src/api/errors.py`
   - May expand as error handling evolves

---

## Compliance Check

Per the restructuring plan:

| Requirement | Status | Notes |
|-------------|--------|-------|
| Reference describes current implementation | ✅ | All docs code-aligned |
| Reference separate from architecture | ✅ | Implementation details, not concepts |
| English language | ✅ | All documents in English |
| Audience field in frontmatter | ✅ | All documents tagged `audience: ai` |
| Code is source of truth | ✅ | Documents describe, don't prescribe |

---

## Ready for Review

**Files to review:**
1. `docs/reference/cli-commands.md`
2. `docs/reference/configuration-reference.md`
3. `docs/reference/database-schema.md`
4. `docs/reference/module-structure.md`
5. `docs/reference/api-integration.md`

**Review focus:**
- Do reference documents accurately describe current implementation?
- Are any commands, settings, or schema fields missing?
- Is the API provider-agnostic note accurate?

---

**Status:** ⏳ Awaiting your review and approval before Phase 5 (Operational & Status documents)
