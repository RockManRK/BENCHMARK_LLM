---
session_id: pending
task: Implement and stabilize bcllm CLI behavior per TO-BE specification
task_complexity: complex
design_depth: deep
workflow_mode: standard
created_at: 2026-03-21
---

# Design Document: bcllm CLI Implementation

## Problem Statement

Implement a complete, stable CLI for the `bcllm` benchmark system following the TO-BE specification (`docs/architecture/to-be/comandos_tobe.md`), with mandatory fixes for Model ID validation and structured output compatibility. The CLI must enable end-to-end testing of existing domain and persistence layers without artificial blockers.

## Design Approach

**CLI-to-Domain Integration First** - Remove artificial CLI blockers (argument validation, command routing) to enable end-to-end testing of existing domain/persistence layers. Implement command-by-command with inspect-and-reimplement compatibility for `--structured`.

## Architecture Decisions

### 1. Scope and Boundary
**Decision:** Full CLI Implementation  
**Rationale:** End-to-end coherence required; all commands must be usable in a single session for integrated testing.

### 2. Integration Surface
**Decision:** CLI-to-Domain First  
**Rationale:** Existing domain/persistence layers are sound; CLI is the blocking layer preventing real-world usage.

### 3. Compatibility Strategy
**Decision:** Inspect-and-Reimplement  
**Rationale:** Preserve validated `--structured` behavior from legacy `/src` without carrying technical debt into `/src_v2`.

### 4. Validation Strategy
**Decision:** Command-by-Command Validation  
**Rationale:** Sequential validation minimizes risk and enables incremental testing with clear completion gates.

### 5. Directory Scope
**Decision:** `/src_v2` only  
**Rationale:** Legacy `/src` is read-only reference; all new implementation in `/src_v2`.

## Mandatory Fixes

| Fix | Description | Priority |
|-----|-------------|----------|
| Model ID Validation | Accept any `<provider>/<model_id>` format without character restrictions | Blocking |
| Model Addition | `--add-model` (singular) adds one model per invocation; flags apply to that model only | Blocking |
| Structured Output | Match legacy functional behavior, re-implemented for TO-BE architecture | High |
| Execution Behavior | Never implicit; partial executions process pending items only; clear messaging | High |

## Implementation Order

1. **CLI Infrastructure** - Argument parsing, command routing, validation utilities
2. **Experiment Commands** - Create, view, seed management
3. **Model Commands** - Add (with relaxed validation), remove, list
4. **Question Commands** - Add (with range/filter support), list
5. **Run Commands** - Add, remove, list
6. **Execution Commands** - Execute with filters, retry policy
7. **Manual Review Interface** - Keyboard navigation, classification, statistics

## Out of Scope

- Parallelism
- Distributed execution
- V1 compatibility (except `--structured` behavior)
- Websearch

## Constraints

- DO NOT redesign the CLI
- DO NOT add new commands or flags beyond specification
- DO NOT introduce parallelism beyond default strategy
- DO NOT modify core domain logic unless strictly required
- DO NOT make assumptions or fill gaps not explicitly described

## Success Criteria

1. All CLI commands from `comandos_tobe.md` are functional
2. Model ID validation accepts all valid OpenRouter formats
3. `--structured` flag matches legacy functional behavior
4. Execution is never implicit; clear messaging for no-op scenarios
5. All commands persist state correctly across invocations
6. No regressions relative to documented TO-BE behavior

## Files

| Action | Path | Purpose |
|--------|------|---------|
| Create | `src_v2/cli/` | CLI argument parsing and command routing |
| Create | `src_v2/commands/` | Command implementations for each CLI operation |
| Modify | `src_v2/validators/` | Model ID validation (relaxed format) |
| Create | `src_v2/structured/` | Structured output handler (legacy-compatible) |
| Create | `src_v2/review/` | Manual review interface |

## Validation Commands

- `python -m src_v2.cli --create-experiment test_exp`
- `python -m src_v2.cli --experiment test_exp --add-model google/gemini-3.1-flash-lite-preview`
- `python -m src_v2.cli --experiment test_exp --add-questions 1-10`
- `python -m src_v2.cli --experiment test_exp --execute`
- `python -m src_v2.cli --review-experiment test_exp`
