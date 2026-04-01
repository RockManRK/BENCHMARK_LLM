---
session_id: cli-composite-flow-fixes
task: 'Fix 14 code review findings for CLI composite flow implementation (1 Critical, 4 Major, 7 Minor, 2 Suggestions). Critical: configuration drift. Major: TOCTOU race condition, missing validation, load_env() API, fragile argv reconstruction.'
created: '2026-03-31T22:58:11.010Z'
updated: '2026-04-01T00:15:45.929Z'
status: completed
workflow_mode: standard
implementation_plan: |-
  ## Implementation Plan — CLI Composite Flow Code Review Fixes

  **Objective:** Fix 14 code review findings (excluding "Add Failure Scenario Tests" suggestion)

  **Execution Mode:** Sequential (8 phases)

  ### Phase 1: Extract Experiment Creation
  **Agent:** agent-coder
  **File:** `src/cli/bcllm_experiment.py`
  **Task:** Extract `_create_experiment_with_config()` function from existing creation logic
  **Validation:** `python -m pytest tests/test_config_resolver.py -v`

  ### Phase 2: Update Composite Flow
  **Agent:** agent-coder
  **File:** `bcllm.py`
  **Task:** Call shared function instead of inline creation
  **Validation:** `python bcllm.py --create-experiment test_exp --add-model openai/gpt-4o-mini`

  ### Phase 3: TOCTOU Fix
  **Agent:** agent-coder
  **File:** `bcllm.py`
  **Task:** Add IntegrityError handling for race condition
  **Validation:** Manual concurrent execution test

  ### Phase 4: load_env() API Fix
  **Agent:** agent-coder
  **File:** `src/core/config_resolver.py`
  **Task:** Remove misleading `env_path` parameter
  **Validation:** `python -m pytest tests/test_config_resolver.py::TestLoadEnv -v`

  ### Phase 5: Remove Mode.INVALID
  **Agent:** agent-coder
  **Files:** `src/cli/bcllm_model.py`, `bcllm_questions.py`, `bcllm_run.py`
  **Task:** Remove `Mode.INVALID` from VALID_MODES
  **Validation:** `python -m pytest tests/unit/core/test_module_resolver.py -v`

  ### Phase 6: NULL Handling Fix
  **Agent:** agent-coder
  **Files:** `src/cli/bcllm_model.py`, `bcllm_experiment.py`
  **Task:** Use `EXPLICIT_NULL` sentinel, respect cli_null_semantics.md
  **Validation:** Manual NULL flag tests

  ### Phase 7: Precondition Validation
  **Agent:** agent-coder
  **File:** `bcllm.py`
  **Task:** Add validation without blocking ADD_* during CREATE
  **Validation:** `python bcllm.py --create-experiment test_exp2 --add-questions 1-5`

  ### Phase 8: Config Equivalence Test
  **Agent:** tester
  **File:** `tests/test_cli_composite_flows.py`
  **Task:** Add test verifying standalone vs. composite create identical config
  **Validation:** `python -m pytest tests/test_cli_composite_flows.py -v`
current_phase: 8
total_phases: 8
execution_mode: sequential
execution_backend: native
current_batch: null
task_complexity: complex
token_usage:
  total_input: 0
  total_output: 0
  total_cached: 0
  by_agent: {}
phases:
  - id: 1
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T22:58:11.010Z'
    completed: '2026-03-31T23:00:54.353Z'
    blocked_by: []
    files_created: []
    files_modified:
      - src/cli/bcllm_experiment.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 2
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:00:54.353Z'
    completed: '2026-03-31T23:04:26.823Z'
    blocked_by: []
    files_created: []
    files_modified:
      - bcllm.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 3
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:04:26.823Z'
    completed: '2026-03-31T23:08:39.996Z'
    blocked_by: []
    files_created: []
    files_modified:
      - bcllm.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 4
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:08:39.996Z'
    completed: '2026-03-31T23:11:18.644Z'
    blocked_by: []
    files_created: []
    files_modified:
      - src/core/config_resolver.py
      - docs/architecture/v2-current/06-configuration-system.md
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 5
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:11:18.644Z'
    completed: '2026-03-31T23:22:04.643Z'
    blocked_by: []
    files_created: []
    files_modified:
      - src/cli/bcllm_model.py
      - src/cli/bcllm_questions.py
      - src/cli/bcllm_run.py
      - src/core/mode_matrix.py
      - tests/unit/cli/test_bcllm_model.py
      - tests/unit/cli/test_bcllm_questions.py
      - tests/unit/cli/test_bcllm_run.py
      - tests/unit/cli/test_bcllm_experiment.py
      - tests/unit/core/test_mode_matrix.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 6
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:22:04.643Z'
    completed: '2026-03-31T23:56:13.955Z'
    blocked_by: []
    files_created: []
    files_modified:
      - src/cli/bcllm_model.py
      - src/cli/bcllm_experiment.py
      - src/core/config_resolver.py
      - tests/unit/core/test_null_normalization.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 7
    status: completed
    agents:
      - agent-coder
    parallel: false
    started: '2026-03-31T23:56:13.955Z'
    completed: '2026-04-01T00:07:09.059Z'
    blocked_by: []
    files_created: []
    files_modified:
      - bcllm.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: 8
    status: completed
    agents:
      - tester
    parallel: false
    started: '2026-04-01T00:07:09.059Z'
    completed: '2026-04-01T00:11:18.207Z'
    blocked_by: []
    files_created: []
    files_modified:
      - tests/test_cli_composite_flows.py
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
---

# Fix 14 code review findings for CLI composite flow implementation (1 Critical, 4 Major, 7 Minor, 2 Suggestions). Critical: configuration drift. Major: TOCTOU race condition, missing validation, load_env() API, fragile argv reconstruction. Orchestration Log
