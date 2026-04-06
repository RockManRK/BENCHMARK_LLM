# Implementation Plan: Fix Configuration Resolution Contract Violation

**Document Type:** Implementation Plan
**Project:** Benchmark LLM V2
**Version:** 1.1
**Date:** 2026-04-05
**Status:** Draft — Pending Approval

---

## Overview

Fix the configuration resolution bug in both `--add-model` and `--add-run` where `.env` is incorrectly consulted after experiment creation. The fix introduces a unified, domain-agnostic resolution helper in `ConfigResolver` that enforces the contract: CLI → `experiment.config_json` → `None`.

---

## Phase 1: Implement Unified Resolution Helper

**Agent:** `coder`
**Dependencies:** None
**Validation:** `pytest tests/unit/core/test_config_resolver.py -v`

### Scope

In `src/core/config_resolver.py`:

1. **Add `_resolve_cli_or_experiment` method** — A new instance method that implements the unified resolution contract:
   - Input: `cli_value`, `exp_config` dict, `exp_key`, optional `parser` function
   - Logic:
     1. If `cli_value is FORCE_SYSTEM_DEFAULT` → return `None`
     2. If `cli_value is not None` → parse and return
     3. Return `parser(exp_config.get(exp_key))` if parser, else `exp_config.get(exp_key)` or `None`
   - This method knows nothing about `.env`, runs, or models. The name makes explicit that it is only valid **after** experiment creation.

2. **Update `build_model_config_dict`**:
   - Replace the inner `resolve_cli_or_env` function with calls to `self._resolve_cli_or_experiment(cli_value, exp_config, exp_key, parser)`
   - Map each model config key to its corresponding `exp_config` key (they use the same keys: `BASE_URL`, `MODEL_TEMPERATURE`, etc.)
   - Preserve `parse_int`, `parse_float`, and `_parse_bool_value` usage

3. **Update `build_run_config_dict`**:
   - Replace `resolve_prompt` calls for `SYSTEM_PROMPT` and `USER_PROMPT` with `self._resolve_cli_or_experiment(cli_value, exp_config, exp_key)`
   - For `RUN_RESPONSES_SEED`, keep existing `resolve_seed_for_run` behavior but change fallback from `.env` to `exp_config.get("RUN_RESPONSES_SEED")`

### Files Modified
| File | Purpose |
|------|---------|
| `src/core/config_resolver.py` | Add `_resolve_cli_or_experiment` method, update `build_model_config_dict` and `build_run_config_dict` |

---

## Phase 2: Integration Smoke Test

**Agent:** `tester`
**Dependencies:** Phase 1 complete
**Validation:** Manual execution of smoke test script

### Scope

Create and execute an integration smoke test that validates the fix across separate CLI invocations:

1. **Create smoke test script** at `tests/smoke/test_config_resolution_smoke.py`:
   - Step 1: Set `.env` with known model config values (e.g., `MODEL_TEMPERATURE=0.5`)
   - Step 2: Create experiment with different values via CLI (e.g., `--temperature 0.9`)
   - Step 3: Verify `experiment.config_json` contains `MODEL_TEMPERATURE: 0.9`
   - Step 4: Modify `.env` to a third value (e.g., `MODEL_TEMPERATURE=0.3`)
   - Step 5: Run `--add-model` separately — verify variant config has `0.9` (from experiment, not `.env`)
   - Step 6: Run `--add-run` separately — verify run config inherits prompts from experiment
   - Step 7: Test `--temperature system-default` — verify variant stores `null`, not experiment value

2. **Execute the smoke test** and report results.
   - *Note:* Initially executed manually; can be promoted to CI later as part of a slower integration pipeline.

### Files Created
| File | Purpose |
|------|---------|
| `tests/smoke/test_config_resolution_smoke.py` | Integration smoke test for configuration resolution contract |

---

## Phase 3: Code Review

**Agent:** `code_reviewer`
**Dependencies:** Phase 1 + Phase 2 complete
**Validation:** No Critical or Major findings

### Scope

Review all changed files for:
- Correctness of resolution logic
- Adherence to configuration contract
- Edge cases (empty experiment config, missing keys, type coercion)
- No unintended changes to other resolution methods
- Test coverage adequacy

### Files Reviewed
| File | Review Focus |
|------|-------------|
| `src/core/config_resolver.py` | Resolution helper correctness, no `.env` leakage |
| `tests/smoke/test_config_resolution_smoke.py` | Test completeness, realistic scenarios |

---

## Execution Strategy

**Mode:** Sequential (phases depend on previous completion)
- Phase 1 → Phase 2 → Phase 3

**Parallel-safe:** No — each phase depends on the previous.

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking existing behavior | Smoke test validates against contract, not previous behavior |
| `_resolve_cli_or_experiment` method conflicts with existing methods | New method, isolated changes to two build methods |
| `.env` still loaded at startup (unchanged) | No change to `.env` loading — only to post-creation resolution |

---

## Completion Criteria

1. `src/core/config_resolver.py` updated with `_resolve_cli_or_experiment` method and both build methods fixed
2. Smoke test passes: `--add-model` and `--add-run` correctly inherit from `experiment.config_json`
3. Code review has no unresolved Critical/Major findings
4. No existing tests broken

---

Approve this implementation plan before execution begins?

1. **Approve plan** — Plan is correct, proceed to execution.
2. **Revise plan** — Something needs to change before execution.
3. **Abort execution** — Cancel this orchestration.

Use the picker to approve, revise, or abort.
