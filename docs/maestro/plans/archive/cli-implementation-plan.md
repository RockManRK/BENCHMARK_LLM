---
session_id: pending
design_document_ref: docs/maestro/plans/cli-implementation-design.md
created_at: 2026-03-21
---

# Implementation Plan: bcllm CLI Implementation

## Overview

Implement and stabilize the bcllm CLI per the TO-BE specification (`docs/architecture/to-be/comandos_tobe.md`), with mandatory fixes for Model ID validation and structured output compatibility.

## Phases

### Phase 1: CLI Infrastructure Fixes
**Agent:** `refactor`  
**Dependencies:** None  
**Validation:** `python -m src.cli.bcllm_model --experiment test --add-model google/gemini-3.1-flash-lite-preview`  
**Files:**
- Modify: `src/cli/bcllm_model.py` - Relax model ID validation
- Create: `src/validators/model_id_validator.py` - Dedicated validator module

**Work:**
1. Replace restrictive regex with permissive `provider/model_id` format check
2. Accept any characters after the slash (including dots, colons, numbers)
3. Add unit tests for all valid examples from spec

---

### Phase 2: Structured Output Compatibility
**Agent:** `coder`  
**Dependencies:** Phase 1 complete  
**Validation:** Compare legacy vs v2 structured behavior  
**Files:**
- Read: `src/api/client.py` (lines 188-239) for reference
- Create: `src/api/structured_output.py` - Structured output handler
- Modify: `src/cli/bcllm_model.py` - Add `--structured` flag support

**Work:**
1. Inspect legacy `response_format` implementation in `src/api/client.py`
2. Implement compatible structured output handler in v2
3. Wire `--structured` flag to model variant configuration

---

### Phase 3: Experiment Commands
**Agent:** `coder`  
**Dependencies:** Phase 1 complete  
**Validation:** `python -m src.cli.bcllm_experiment --create-experiment test_exp`  
**Files:**
- Modify: `src/cli/bcllm_experiment.py` - Add optional flags support

**Work:**
1. Add optional flags to `--create-experiment`: `--add-questions`, `--seed`, `--add-model`, `--system_prompt`, `--user_prompt`, `--retry_policy`
2. Implement seed generation (AUTO vs explicit)
3. Ensure `.env` is read only at experiment creation time

---

### Phase 4: Question Commands
**Agent:** `coder`  
**Dependencies:** Phase 1 complete  
**Validation:** `python -m src.cli.bcllm_questions --experiment test_exp --add-questions 1-10`  
**Files:**
- Read: `src/cli/bcllm_questions.py` - Current implementation
- Modify: `src/cli/bcllm_questions.py` - Add range and filter support

**Work:**
1. Implement range parsing: `1-50`
2. Implement individual question list: `1 5 10`
3. Add `--where` and `--exclude` filter support
4. Ensure idempotent snapshotting

---

### Phase 5: Run Commands
**Agent:** `coder`  
**Dependencies:** Phase 1 complete  
**Validation:** `python -m src.cli.bcllm_run --experiment test_exp --add-run`  
**Files:**
- Read: `src/cli/bcllm_run.py` - Current implementation
- Modify: `src/cli/bcllm_run.py` - Full CRUD support

**Work:**
1. Implement `--add-run` with optional `--seed`, `--system_prompt`, `--user_prompt`
2. Implement `--list-runs`
3. Implement `--remove-run`
4. Enforce immutability after creation

---

### Phase 6: Execute Command
**Agent:** `coder`  
**Dependencies:** Phases 3-5 complete  
**Validation:** `python -m src.cli.bcllm_execute --experiment test_exp --execute`  
**Files:**
- Read: `src/cli/bcllm_execute.py` - Current implementation
- Read: `src/core/planner.py` - Execution plan generation
- Modify: `src/cli/bcllm_execute.py` - Add filters and retry policy

**Work:**
1. Add `--run`, `--questions`, `--models`, `--retry_policy` filters
2. Implement partial execution (pending items only)
3. Add clear messaging when nothing is pending
4. Support default execution order strategy (run-first)

---

### Phase 7: Manual Review Interface
**Agent:** `coder`  
**Dependencies:** Phase 6 complete  
**Validation:** `python -m src.cli.bcllm_review --experiment test_exp`  
**Files:**
- Read: `src/cli/review_ui.py` - Legacy reference
- Create: `src/review/review_ui.py` - Manual review interface

**Work:**
1. Implement keyboard navigation interface
2. Support A/B/C/D/N/E classification
3. Implement incremental persistence
4. Add real-time statistics display

---

### Phase 8: Integration Testing
**Agent:** `tester`  
**Dependencies:** Phases 1-7 complete  
**Validation:** Full end-to-end test suite passes  
**Files:**
- Create: `tests/test_cli_integration.py`

**Work:**
1. Write integration tests for all CLI commands
2. Test cross-invocation state persistence
3. Validate model ID formats (all examples from spec)
4. Test structured output compatibility
5. Test partial execution scenarios

---

## Dependencies Graph

```
Phase 1 (Infrastructure)
    ├── Phase 2 (Structured)
    ├── Phase 3 (Experiments)
    ├── Phase 4 (Questions)
    └── Phase 5 (Runs)
            │
            └── Phase 6 (Execute)
                    │
                    └── Phase 7 (Review)
                            │
                            └── Phase 8 (Integration Tests)
```

## Execution Strategy

**Recommended Mode:** Sequential  
**Rationale:** Phases have clear dependencies; parallel execution would create file ownership conflicts and complicate validation.

## Validation Commands

| Phase | Command | Expected Result |
|-------|---------|-----------------|
| 1 | `bcllm --experiment test --add-model google/gemini-3.1-flash-lite-preview` | Success (model added) |
| 1 | `bcllm --experiment test --add-model stepfun/step-3.5-flash:free` | Success (colon accepted) |
| 2 | `bcllm --experiment test --add-model openai/gpt-4 --structured` | Success (structured flag stored) |
| 3 | `bcllm --create-experiment test_exp --seed AUTO` | Success (experiment created) |
| 4 | `bcllm --experiment test_exp --add-questions 1-10` | Success (10 questions snapshotted) |
| 5 | `bcllm --experiment test_exp --add-run` | Success (run created) |
| 6 | `bcllm --experiment test_exp --execute` | Success (execution plan generated and executed) |
| 7 | `bcllm --review-experiment test_exp` | Success (review UI launches) |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Model ID validation too permissive | Add unit tests for edge cases; reject empty strings and missing slash |
| Structured output incompatibility | Direct comparison with legacy behavior; use same `response_format` structure |
| State persistence issues | Integration tests verify cross-invocation state |
| Partial execution edge cases | Test scenarios with mixed pending/completed items |

## Completion Criteria

1. All CLI commands from `comandos_tobe.md` functional
2. Model ID validation accepts all spec examples
3. `--structured` flag matches legacy behavior
4. Execution is never implicit
5. All integration tests pass
6. No Critical/Major code review findings
