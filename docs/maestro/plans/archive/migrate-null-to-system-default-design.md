---
design_depth: standard
task_complexity: complex
date: 2026-03-31
task: Migrate CLI literal "null" to "system-default" for forcing system default behavior
---

# Design Document: Migrate "null" → "system-default" Literal

## Problem Statement

The CLI currently uses `"null"` (case-insensitive) as a reserved literal meaning "force system default behavior / omit from API request". This causes confusion because users conflate CLI `"null"` with JSON `null`, and the internal sentinel `EXPLICIT_NULL` perpetuates semantic ambiguity for code readers (including AIs).

**Goal**: Replace `"null"` with `"system-default"` as the reserved literal, and rename the internal sentinel to `FORCE_SYSTEM_DEFAULT` to eliminate ambiguity throughout the codebase.

## Requirements

### Functional Requirements

- **REQ-1**: `"system-default"` (case-insensitive) normalizes to `FORCE_SYSTEM_DEFAULT` sentinel
- **REQ-2**: `"null"` (case-insensitive) is rejected with clear error and migration hint
- **REQ-3**: `"none"` is preserved as literal string (no special handling)
- **REQ-4**: Mandatory fields (`--url`, `--dataset-path`) reject `system-default` override
- **REQ-5**: Optional fields with `system-default` → `None` in config → omitted from API request

### Non-Functional Requirements

- **REQ-6**: All references to `EXPLICIT_NULL` renamed to `FORCE_SYSTEM_DEFAULT`
- **REQ-7**: All documentation updated to reflect new semantics
- **REQ-8**: All tests updated to use new literal and sentinel name
- **REQ-9**: Error messages reference `'system-default'` only (not legacy `'null'`)

### Constraints

- **CONST-1**: Multi-layer config resolution hierarchy must be preserved
- **CONST-2**: Optional field omission behavior (`None` → omit from API) must not change
- **CONST-3**: Positional arguments (e.g., experiment name) allow `"system-default"` as literal string

## Selected Approach: Atomic Rename + CLI Literal Swap

**Rationale**: Achieves both UX clarity and internal code clarity in a single atomic change. Codebase never exists in inconsistent state.

**Alternatives Considered**:
- *Phased Introduction*: Rejected — delays internal clarity benefit
- *Hybrid with Deprecation*: Rejected — violates hard break decision, keeps legacy terminology alive

## Architecture

### Normalization Flow

```
User Input: --temperature system-default
     ↓
[argparse] → args.temperature = "system-default"
     ↓
[src/core/null_semantics.py] → if value.lower() == "system-default": return FORCE_SYSTEM_DEFAULT
     ↓
[src/core/argv_utils.py] → args.temperature = FORCE_SYSTEM_DEFAULT
     ↓
[src/core/config_resolver.py] → if cli_value is FORCE_SYSTEM_DEFAULT: return None (skip .env)
     ↓
[experiment.config_json] → "MODEL_TEMPERATURE": null (JSON)
     ↓
[api/client.py] → if temperature is None: omit from payload
```

### Key Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Sentinel Definition | `src/core/null_semantics.py` | `FORCE_SYSTEM_DEFAULT` class, normalization logic |
| CLI Parsing | `src/core/argv_utils.py` | `parse_args_normalized()`, calls normalization |
| Config Resolution | `src/core/config_resolver.py` | Multi-layer resolution with sentinel checks |
| CLI Validation | `src/cli/bcllm_*.py` | Mandatory field validation, error messages |
| API Serialization | `src/api/client.py` | Filters out `None` from payload |

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large atomic diff causes merge conflicts | Medium | Coordinate with team, ensure no conflicting changes |
| Users miss migration error | Low | Clear error: `"Use 'system-default' instead"` |
| Test failures from missed references | Medium | Comprehensive grep + full test suite |
| Documentation drift | Low | Update all `.md` files in same commit |

## Success Criteria

- [ ] No references to `EXPLICIT_NULL` in codebase
- [ ] `"system-default"` (any case) → `FORCE_SYSTEM_DEFAULT` sentinel
- [ ] `"null"` (any case) → error with migration hint
- [ ] `"none"` → preserved as literal
- [ ] All tests pass
- [ ] Documentation updated
