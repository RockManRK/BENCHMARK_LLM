# Domain Mapping: V1 → V2

**Document ID:** `docs/architecture/gap-reports/00-domain-mapping.md`
**Date:** 2026-03-29
**Status:** Complete

---

## Overview

This document provides a complete mapping of functional domains from V1 (legacy) to V2 (current), identifying gaps, improvements, and new domains.

---

## Domain Mapping Table

| # | Domain | V1 Location | V2 Location | Status | Notes |
|---|--------|-------------|-------------|--------|-------|
| 1 | **Execution Core** | `src_legacy/core/` | `src/core/` | ✅ Complete | Core architecture preserved, improvements added |
| 2 | **Logging System** | `src_legacy/utils/logging_config.py` | **MISSING** | ❌ Missing | **CRITICAL GAP** — needs migration |
| 3 | **CLI System** | `src_legacy/cli/`, `main.py` | `src/cli/bcllm_*.py` | ✅ Complete | New command-per-module paradigm |
| 4 | **Review UI** | `src_legacy/cli/review_ui.py` | `src/review/review_ui.py` | ✅ Complete | Extracted to dedicated module |
| 5 | **Database Layer** | `src_legacy/db/` | `src/db/` | ✅ Complete | Improved repository pattern |
| 6 | **Configuration System** | `src_legacy/utils/config.py` | `src/core/config_resolver.py`, `null_semantics.py` | ✅ Complete | Significant improvements |
| 7 | **Error Handling** | `src_legacy/core/error_collector.py`, `api/` | `src/api/errors.py`, `retry.py` | ✅ Complete | Explicit error classification |
| 8 | **Answer Parsing** | `src_legacy/core/answer_parser.py` | `src/core/answer_parser.py` | ⚠️ Partial | Needs feature parity verification |
| 9 | **Validation** | — | `src/validators/` | 🆕 New | NEW domain in V2 |
| 10 | **Variant Configuration** | `src_legacy/core/variant_config.py` | `src/utils/variant_signature.py` | ✅ Moved | Relocated to utils/ |

---

## Detailed Domain Analysis

### 1. Execution Core

**Status:** ✅ Complete with improvements

**V1 Files:**
- `src_legacy/core/execution_engine.py`
- `src_legacy/core/execution_plan.py`
- `src_legacy/core/planner.py`
- `src_legacy/core/result_writer.py`
- `src_legacy/core/answer_parser.py`
- `src_legacy/core/randomizer.py`
- `src_legacy/core/variant_config.py`
- `src_legacy/core/run_manager.py`

**V2 Files:**
- `src/core/execution_engine.py`
- `src/core/execution_plan.py`
- `src/core/planner.py`
- `src/core/result_writer.py`
- `src/core/answer_parser.py`
- `src/core/randomizer.py`
- `src/core/config_resolver.py` (NEW)
- `src/core/null_semantics.py` (NEW)
- `src/core/mode.py`
- `src/core/mode_matrix.py`
- `src/core/mode_resolver.py`

**Improvements in V2:**
1. Explicit null semantics (`EXPLICIT_NULL`)
2. Centralized configuration resolution (`ConfigResolver`)
3. Type-specific `ModelConfig` dataclass
4. Explicit `RetryPolicy` in ExecutionPlan
5. Better type annotations

**Gaps:** None

---

### 2. Logging System

**Status:** ❌ **MISSING** — Critical Gap

**V1 Files:**
- `src_legacy/utils/logging_config.py`

**V2 Files:**
- **NONE**

**Impact:**
- No logging configuration in V2
- No rotating file handlers
- No structured logging
- No initialization summary logging

**Action Required:**
Migrate `src_legacy/utils/logging_config.py` to `src/utils/logging_config.py` with V2 adaptations.

**Migration Checklist:**
- [ ] Copy `logging_config.py` to `src/utils/`
- [ ] Update imports for V2 module structure
- [ ] Verify integration with V2 execution flow
- [ ] Test with V2 CLI commands

---

### 3. CLI System

**Status:** ✅ Complete (paradigm shift)

**V1 Files:**
- `src_legacy/main.py` (monolithic entry point)
- `src_legacy/cli/cli.py`
- `src_legacy/cli/experiment_commands.py`
- `src_legacy/cli/review_ui.py`
- `src_legacy/cli/output_formatter.py`
- `src_legacy/cli/statistics.py`

**V2 Files:**
- `src/cli/bcllm_main.py` (new entry point)
- `src/cli/bcllm_experiment.py`
- `src/cli/bcllm_model.py`
- `src/cli/bcllm_questions.py`
- `src/cli/bcllm_run.py`
- `src/cli/bcllm_execute.py`
- `src/cli/bcllm_review.py`
- `src/cli/database.py`

**Paradigm Shift:**
- V1: Monolithic `main.py` with all commands
- V2: Command-per-module approach (`bcllm_*.py`)
- V2: No immediate execution (experiment-based only)

**Gaps:** None (intentional redesign)

---

### 4. Review UI

**Status:** ✅ Complete (extracted to dedicated module)

**V1 Files:**
- `src_legacy/cli/review_ui.py`

**V2 Files:**
- `src/review/review_ui.py`

**Improvements in V2:**
1. Extracted from `cli/` to dedicated `review/` module
2. Uses Rich library for better terminal UI
3. Cleaner separation of concerns

**Gaps:** None

---

### 5. Database Layer

**Status:** ✅ Complete

**V1 Files:**
- `src_legacy/db/schema.py`
- `src_legacy/db/schema.sql`
- `src_legacy/db/models.py`
- `src_legacy/db/repository.py.old`

**V2 Files:**
- `src/db/schema.py`
- `src/db/models.py`
- `src/db/repository.py`

**Improvements in V2:**
1. Cleaner repository pattern
2. Better type annotations
3. Updated schema aligned with V2 ExecutionPlan

**Gaps:** None

---

### 6. Configuration System

**Status:** ✅ Complete (significant improvements)

**V1 Files:**
- `src_legacy/utils/config.py` (Pydantic Settings)
- `src_legacy/utils/config_hierarchy.py`

**V2 Files:**
- `src/core/config_resolver.py`
- `src/core/null_semantics.py`

**Improvements in V2:**
1. **Explicit Null Semantics:**
   - `None` = "not specified, use fallback"
   - `EXPLICIT_NULL` = "explicitly null, DO NOT use fallback"

2. **Centralized Resolution:**
   - Single `ConfigResolver` class
   - Explicit resolution order: CLI > .env > system defaults > NULL

3. **Type-Safe Parsing:**
   - Dedicated parser functions for int/float/bool
   - Better error messages

**Gaps:** None

---

### 7. Error Handling

**Status:** ✅ Complete

**V1 Files:**
- `src_legacy/core/error_collector.py`
- `src_legacy/api/error_handler.py`
- `src_legacy/api/retry.py`

**V2 Files:**
- `src/api/errors.py`
- `src/api/retry.py`
- `src/core/execution_engine.py` (error classification)

**Improvements in V2:**
1. Explicit error classification in `_classify_error()` method
2. `RetryPolicy` dataclass in ExecutionPlan
3. `attempt_count` tracked in ExecutionResult
4. New `config_error` type

**Gaps:** None

---

### 8. Answer Parsing

**Status:** ⚠️ Partial (needs verification)

**V1 Files:**
- `src_legacy/core/answer_parser.py`

**V2 Files:**
- `src/core/answer_parser.py`

**V1 Features (to verify in V2):**
- Hierarchical pattern matching (explicit → context → structural → fallback)
- Confidence levels: clear, ambiguous, no_answer, low_confidence
- Portuguese/Spanish article filtering
- Markdown pattern support (**[A-D]**, etc.)
- Edge case handling (repeated letters, multiple letters, etc.)

**Action Required:**
Verify V2 `answer_parser.py` has feature parity with V1.

**Verification Checklist:**
- [ ] Pattern hierarchy matches V1
- [ ] Confidence levels implemented correctly
- [ ] Article filtering for Portuguese/Spanish
- [ ] Markdown pattern support
- [ ] Edge case handling

---

### 9. Validation (NEW)

**Status:** 🆕 New domain in V2

**V1 Files:**
- None

**V2 Files:**
- `src/validators/model_id_validator.py`
- `src/validators/__init__.py`

**Purpose:**
- Input validation for model IDs
- Validation utilities for CLI arguments
- Schema validation for configuration

**V2 Principle:**
**Validation is explicit and early** — validate inputs before they reach the execution core.

---

### 10. Variant Configuration

**Status:** ✅ Moved (core → utils)

**V1 Files:**
- `src_legacy/core/variant_config.py`

**V2 Files:**
- `src/utils/variant_signature.py`

**Purpose:**
- `variant_id` generation (hash-based)
- `variant_signature` generation (human-readable)

**Note:** Functionality preserved, location changed.

---

## Contradictions Found

### 1. Execution Plan Structure

**Location:** `docs/architecture/to-be/llmbc_system.md` vs `src/core/execution_plan.py`

**Contradiction:**
- Documentation states ExecutionPlan should have `experiment_id` and `experiment_name` at top level
- V2 implementation has `experiment_id` but may not have `experiment_name`

**Action:** Verify and align implementation with documentation.

---

### 2. Configuration Resolution Order

**Location:** `docs/architecture/to-be/llmbc_system.md` vs `src/core/config_resolver.py`

**Contradiction:**
- Documentation states: "Configurações de Sistema > .env > experiments > runs/model_variants"
- Implementation uses: "CLI > .env > system defaults > NULL"

**Note:** The implementation appears correct per QWEN.md principles. Documentation may be outdated.

**Action:** User consultation required to confirm correct resolution order.

---

### 3. Review Field Calculation

**Location:** `docs/architecture/contracts/domain-review-contract.md` vs `src/core/result_writer.py`

**Contradiction:**
- Contract states: `needs_review = (parse_confidence != 'clear' OR selected_answer IS NULL)`
- Implementation may have slight variation in logic

**Action:** Verify implementation matches contract exactly.

---

## Summary

### Domain Count

| Category | Count |
|----------|-------|
| Domains from V1 | 8 |
| New domains in V2 | 2 |
| **Total V2 domains** | **10** |

### Status Summary

| Status | Count | Domains |
|--------|-------|---------|
| ✅ Complete | 7 | Execution Core, CLI System, Review UI, Database Layer, Configuration System, Error Handling, Variant Configuration |
| ❌ Missing | 1 | Logging System |
| ⚠️ Partial | 1 | Answer Parsing |
| 🆕 New | 1 | Validation |

### Critical Gaps

| Domain | Gap | Severity | Action Required |
|--------|-----|----------|-----------------|
| Logging System | `logging_config.py` missing | **HIGH** | Migrate from V1 |
| Answer Parsing | Feature parity unverified | **MEDIUM** | Verify against V1 |

### Contradictions Requiring User Decision

| Area | Contradiction | Resolution |
|------|---------------|------------|
| Configuration Resolution | Documentation vs Implementation | User consultation required |
| Execution Plan Structure | Documentation vs Implementation | Verify and align |
| Review Field Calculation | Contract vs Implementation | Verify exact logic |

---

## Recommendations

### Immediate Actions

1. **Migrate Logging System**
   - Copy `src_legacy/utils/logging_config.py` to `src/utils/logging_config.py`
   - Update imports for V2 module structure
   - Test with V2 CLI commands

2. **Verify Answer Parser**
   - Compare V1 and V2 `answer_parser.py` side-by-side
   - Ensure feature parity
   - Update V2 if missing features

3. **Resolve Contradictions**
   - Consult user on configuration resolution order
   - Align ExecutionPlan structure with documentation
   - Verify review field calculation logic

### Future Improvements

1. **Parallel Execution** — V2 should support parallel API calls (mentioned in V1 requirements)
2. **Enhanced Validation** — Expand `validators/` module with more validators
3. **Better Error Messages** — Improve error messages for CLI users
4. **Documentation Updates** — Update outdated documentation to match V2 implementation

---

## Appendix: File Migration Checklist

### Files to Migrate from V1 to V2

- [ ] `src_legacy/utils/logging_config.py` → `src/utils/logging_config.py`
- [ ] `src_legacy/utils/image_handler.py` → `src/utils/image_handler.py` (if needed)
- [ ] `src_legacy/utils/progress.py` → `src/utils/progress.py` (if needed)
- [ ] `src_legacy/utils/answer_schema.py` → `src/utils/answer_schema.py` (if needed)

### Files to Verify for Feature Parity

- [ ] `src/core/answer_parser.py` (vs V1)
- [ ] `src/core/randomizer.py` (vs V1)
- [ ] `src/api/client.py` (vs V1)

---

**Document Complete.**
