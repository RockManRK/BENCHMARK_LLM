---
session_id: migrate-null-to-system-default
task_complexity: complex
workflow_mode: standard
execution_mode: sequential
date: 2026-03-31
---

# Implementation Plan: Migrate "null" → "system-default"

## Phase Overview

| Phase | Title | Agent | Status | Dependencies |
|-------|-------|-------|--------|--------------|
| 1 | Rename Sentinel Core | refactor | pending | None |
| 2 | Update CLI Normalization | coder | pending | Phase 1 |
| 3 | Update Config Resolver | coder | pending | Phase 1 |
| 4 | Update CLI Command Validation | coder | pending | Phase 2 |
| 5 | Update API Client & Execution | coder | pending | Phase 3 |
| 6 | Update Tests | tester | pending | Phases 1-5 |
| 7 | Update Documentation | technical_writer | pending | Phases 1-6 |
| 8 | Final Validation | code_reviewer | pending | Phases 1-7 |

## Phase Details

### Phase 1: Rename Sentinel Core
**Agent**: refactor  
**Files**: `src/core/null_semantics.py`, `src/core/argv_utils.py`  
**Changes**:
- Rename class `EXPLICIT_NULL` → `FORCE_SYSTEM_DEFAULT`
- Update module exports
- Update all internal references

**Validation**: `pytest tests/unit/core/test_null_normalization.py -v`

---

### Phase 2: Update CLI Normalization
**Agent**: coder  
**Files**: `src/core/null_semantics.py`  
**Changes**:
- Update `normalize_nulls_explicit()` to recognize `"system-default"`
- Add rejection logic for `"null"` with migration error
- Preserve `"none"` as literal

**Validation**: `pytest tests/unit/core/test_null_normalization.py -v`

---

### Phase 3: Update Config Resolver
**Agent**: coder  
**Files**: `src/core/config_resolver.py`  
**Changes**:
- Replace `is EXPLICIT_NULL` → `is FORCE_SYSTEM_DEFAULT`
- Update comments/docstrings

**Validation**: `pytest tests/unit/core/test_config_resolver.py -v`

---

### Phase 4: Update CLI Command Validation
**Agent**: coder  
**Files**: `src/cli/bcllm_experiment.py`, `src/cli/bcllm_model.py`, `src/cli/bcllm_run.py`  
**Changes**:
- Update error messages: `'null'` → `'system-default'`

**Validation**: `pytest tests/integration/test_cli_null_semantics.py -v`

---

### Phase 5: Update API Client & Execution
**Agent**: coder  
**Files**: `src/core/execution_engine.py`, `src/api/client.py`  
**Changes**:
- Update comments/docstrings referencing old name

**Validation**: `pytest tests/integration/test_execution.py -v`

---

### Phase 6: Update Tests
**Agent**: tester  
**Files**: All `tests/**/*.py`  
**Changes**:
- Replace `"null"` → `"system-default"`
- Replace `EXPLICIT_NULL` → `FORCE_SYSTEM_DEFAULT`
- Add tests for new behavior

**Validation**: `pytest tests/ -v`

---

### Phase 7: Update Documentation
**Agent**: technical_writer  
**Files**: `docs/architecture/contracts/*.md`, `docs/architecture/to-be/*.md`  
**Changes**:
- Update all references to new literal/sentinel

**Validation**: Manual review + grep

---

### Phase 8: Final Validation
**Agent**: code_reviewer  
**Scope**: All changed files  
**Changes**:
- Review for correctness, completeness
- Check for missed references
- Validate test coverage

**Validation**: Address Critical/Major findings

---

## Acceptance Criteria

- [ ] No `EXPLICIT_NULL` references remain
- [ ] `"system-default"` works correctly
- [ ] `"null"` rejected with error
- [ ] `"none"` preserved as literal
- [ ] All tests pass
- [ ] Docs updated
