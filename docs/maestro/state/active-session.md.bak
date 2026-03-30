---
session_id: global-null-semantics
task: 'Implement global null semantics with metadata-based normalization: create normalize_nulls() and parse_args_normalized() in src/core/argv_utils.py, update 6 CLI modules to use the new helper, update tri-state parsers for --vision/--structured, and add comprehensive tests'
created: '2026-03-28T21:17:52.562Z'
updated: '2026-03-28T21:19:18.803Z'
status: in_progress
workflow_mode: standard
design_document: ''
implementation_plan: ''
current_phase: .nan
total_phases: 11
execution_mode: sequential
execution_backend: native
current_batch: null
task_complexity: medium
token_usage:
  total_input: 0
  total_output: 0
  total_cached: 0
  by_agent: {}
phases:
  - id: P1
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:17:52.562Z'
    completed: '2026-03-28T21:20:00.000Z'
    blocked_by: []
    files_created:
      - src/core/argv_utils.py
    files_modified:
      - src/core/__init__.py (added exports)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced:
        - parse_args_normalized(parser) -> Namespace
        - normalize_nulls(args, parser) -> Namespace
        - _is_nullable_arg(action) -> bool
      patterns_established:
        - Null normalization is metadata-driven (default=None, required=False)
        - Case-insensitive matching ('null', 'NULL', 'Null' → None)
        - Literal 'none' is preserved (not normalized)
      integration_points:
        - P2-P8: CLI modules will use parse_args_normalized(parser)
        - P8: Tri-state parsers (--vision, --structured) will accept 'null'
      assumptions:
        - All CLI modules use argparse.ArgumentParser with proper default=None
      warnings:
        - Arguments with non-None defaults will NOT be normalized
        - Required arguments will NOT be normalized
    errors: []
    retry_count: 0
  - id: P2
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:20:00.000Z'
    completed: '2026-03-28T21:25:00.000Z'
    blocked_by:
      - P1
    files_created: []
    files_modified:
      - src/cli/bcllm_experiment.py (use parse_args_normalized)
      - src/core/argv_utils.py (added has_flag function)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced:
        - has_flag(args: list[str], flag: str) -> bool (added to argv_utils)
      patterns_established:
        - parse_args_normalized() is now the standard for CLI argument parsing
      integration_points:
        - P3-P7: Other CLI modules will use parse_args_normalized(parser)
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P3
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:25:00.000Z'
    completed: '2026-03-28T21:30:00.000Z'
    blocked_by:
      - P1
    files_modified:
      - src/cli/bcllm_model.py (use parse_args_normalized)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P4
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:30:00.000Z'
    completed: '2026-03-28T21:31:00.000Z'
    blocked_by:
      - P1
    files_modified:
      - src/cli/bcllm_questions.py (use parse_args_normalized)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P5
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:31:00.000Z'
    completed: '2026-03-28T21:32:00.000Z'
    blocked_by:
      - P1
    files_modified:
      - src/cli/bcllm_run.py (use parse_args_normalized)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P6
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:32:00.000Z'
    completed: '2026-03-28T21:33:00.000Z'
    blocked_by:
      - P1
    files_modified:
      - src/cli/bcllm_execute.py (use parse_args_normalized)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P7
    status: completed
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:33:00.000Z'
    completed: '2026-03-28T21:34:00.000Z'
    blocked_by:
      - P1
    files_modified:
      - src/cli/bcllm_review.py (use parse_args_normalized)
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: P8
    status: in_progress
    agents:
      - coder
    parallel: false
    started: '2026-03-28T21:34:00.000Z'
    completed: null
    blocked_by:
      - P1
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - coder
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - tester
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P1
      - P2
      - P3
      - P4
      - P5
      - P6
      - P7
      - P8
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - tester
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P9
    files_created: []
    files_modified: []
    files_deleted: []
    downstream_context:
      key_interfaces_introduced: []
      patterns_established: []
      integration_points: []
      assumptions: []
      warnings: []
    errors: []
    retry_count: 0
  - id: .nan
    status: pending
    agents:
      - code_reviewer
    parallel: false
    started: null
    completed: null
    blocked_by:
      - P10
    files_created: []
    files_modified: []
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

# Implement global null semantics with metadata-based normalization: create normalize_nulls() and parse_args_normalized() in src/core/argv_utils.py, update 6 CLI modules to use the new helper, update tri-state parsers for --vision/--structured, and add comprehensive tests Orchestration Log
