---
date: 2026-04-14
task: Provider Locking for OpenRouter
status: approved
design_document: docs/maestro/plans/2026-04-14-provider-locking-design.md
---

# Implementation Plan: Provider Locking for OpenRouter

## Phase 1: ProviderResolver Core
**Agent**: `coder`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Create | `src/core/provider_resolver.py` | OpenRouter API client — fetches endpoints, applies strategy |
| Create | `tests/unit/test_provider_resolver.py` | Unit tests for all strategies with mocked responses |
| Modify | `src/api/errors.py` | Add `NoProviderError` exception class |

**Validation**: `pytest tests/unit/test_provider_resolver.py -v`
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 2: CLI — Model Provider & Experiment Provider Lock
**Agent**: `coder`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Modify | `src/cli/bcllm_model.py` | Add `--provider` flag to parser, store in config |
| Modify | `src/cli/bcllm_experiment.py` | Add `--provider-lock` to create and modify flows |
| Modify | `src/core/config_resolver.py` | Add `resolve_provider_lock()` and `resolve_provider_selection_strategy()` |
| Modify | `.env.example` | Add `AUTO_PROVIDER_LOCK`, `PROVIDER_SELECTION_STRATEGY` |

**Validation**: Manual CLI test
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 3: CLI — `--resolve-providers` Command
**Agent**: `coder`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Create | `src/cli/bcllm_provider.py` | New CLI module — handles `--resolve-providers` |
| Modify | `bcllm.py` | Register provider module in routing |
| Modify | `src/core/module_resolver.py` | Register `bcllm_provider` module |

**Validation**: `bcllm --experiment <name> --resolve-providers`
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 4: Planner Validation + Executor Integration
**Agent**: `coder`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Modify | `src/core/planner.py` | Add `_validate_provider_lock()` |
| Modify | `src/core/execution_engine.py` | Include `provider` object in API request |
| Modify | `src/core/execution_plan.py` | Add `resolved_provider` field to PlanVariant |

**Validation**: `pytest tests/`
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 5: Integration + E2E Tests
**Agent**: `tester`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Create | `tests/integration/test_provider_lock_flow.py` | E2E: create exp → add model → resolve → execute |
| Create | `tests/unit/test_planner_provider_lock.py` | Planner validation tests |
| Create | `tests/unit/test_execution_engine_provider.py` | Executor includes provider in request |

**Validation**: `pytest tests/ -v`
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 6: Documentation + ADR
**Agent**: `technical_writer`
**Files**:
| Action | Path | Purpose |
|--------|------|---------|
| Modify | `docs/reference/cli-commands.md` | Document provider CLI flags |
| Modify | `docs/reference/configuration-reference.md` | Document .env provider settings |
| Modify | `docs/contracts/determinism.md` | Declare provider as deterministic config |
| Create | `docs/architecture/adr/adr-provider-locking.md` | ADR for Provider Selection & Locking |
| Modify | `QWEN.md` | Add note about provider lock flow |
| Modify | `README.md` | Brief mention in Quick Start |

**Validation**: Manual review
**Quality Gate**: `essence-guardian` post-phase verification

---

## Phase 7: Code Review (Quality Gate)
**Agent**: `code_reviewer`
**Scope**: All changed files from Phases 1-6
**Validation**: No Critical or Major findings

---

## Dependencies
```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7
```

All phases sequential. Each phase requires `essence-guardian` verification before proceeding.
