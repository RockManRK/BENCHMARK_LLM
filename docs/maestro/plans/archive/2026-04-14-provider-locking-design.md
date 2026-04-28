---
date: 2026-04-14
task: Provider Locking for OpenRouter
design_depth: standard
task_complexity: medium
status: approved
---

# Design Document: Provider Locking for OpenRouter

## Problem Statement

The system currently doesn't specify which provider to use when calling OpenRouter models. OpenRouter's default load balancing can select different providers between requests for the same model, introducing non-determinism into benchmark results. This violates the system's core contracts of determinism, reproducibility, and auditability.

## Requirements

### Functional
- **REQ-1**: Users can explicitly set a provider when adding a model variant via `--provider <slug>`
- **REQ-2**: Users can enable provider lock for an experiment via `--provider-lock true|false|system-default`
- **REQ-3**: Users can resolve providers for all unresolved variants via `--resolve-providers`
- **REQ-4**: `AUTO_PROVIDER_LOCK` and `PROVIDER_SELECTION_STRATEGY` in `.env` define default behavior at experiment creation
- **REQ-5**: Pre-execution validation aborts if `PROVIDER_LOCK=true` and any variant has `PROVIDER=null`
- **REQ-6**: Resolved provider is included in the API request body as `provider.only: ["<slug>"], allow_fallbacks: false`
- **REQ-7**: `system-default` for `--provider-lock` bypasses inheritance and resolves to `false` (per system-default-semantics.md)

### Non-Functional
- **REQ-8**: Planner and Executor remain pure — no provider resolution, no DB writes
- **REQ-9**: All provider resolution is idempotent and auditable
- **REQ-10**: No new database columns — uses existing `config` JSON fields

## Architecture

### Approach Selected
**Approach 1: Explicit `--resolve-providers` Command** — Provider resolution is a separate CLI command that persists providers into `model_variants.config` before execution. The Planner validates provider lock status before plan generation. The Executor reads the resolved provider and includes it in the API request.

### Alternatives Considered
- **Approach 2 (Auto-resolve at execution)**: Rejected because it violates "explicit over implicit" and makes the Executor impure (DB writes).
- **Approach 3 (Hybrid with auto-warn)**: Rejected because it blurs the explicit/implicit boundary and adds branching logic to execution.

### Decision Matrix

| Criterion | Weight | Approach 1 | Approach 2 | Approach 3 |
|-----------|--------|------------|------------|------------|
| Determinism/Reproducibility | 35% | 5: Fully explicit | 2: Implicit | 3: Mixed |
| System Contract Compliance | 30% | 5: Matches principle | 2: Violates | 3: Partially violates |
| User Experience | 20% | 3: Extra step but clear | 5: Fewer steps | 4: Flexible but confusing |
| Implementation Complexity | 15% | 4: Clean separation | 3: Executor side-effect | 3: Multiple code paths |
| **Weighted Total** | | **4.25** | **2.95** | **3.35** |

### Component Changes

| Component | Change | Purpose |
|-----------|--------|---------|
| `src/cli/bcllm_provider.py` | New | CLI module for `--resolve-providers` |
| `src/core/provider_resolver.py` | New | OpenRouter API client for `/models/{id}/endpoints` |
| `src/cli/bcllm_model.py` | Modify | Add `--provider` flag to `--add-model` |
| `src/cli/bcllm_experiment.py` | Modify | Add `--provider-lock` to create and modify |
| `bcllm.py` | Modify | Route `--resolve-providers`, composite flow updates |
| `src/core/planner.py` | Modify | Add `_validate_provider_lock()` |
| `src/core/config_resolver.py` | Modify | Add provider resolution methods |
| `src/core/execution_engine.py` | Modify | Include `provider` object in API request when set |
| `src/core/module_resolver.py` | Modify | Register provider module |
| `.env.example` | Modify | Add `AUTO_PROVIDER_LOCK`, `PROVIDER_SELECTION_STRATEGY` |

### Data Flow

```
--resolve-providers
  ↓
ProviderResolver.resolve(model_id, strategy)
  → GET /api/v1/models/{model_id}/endpoints
  → Apply strategy (first/cheapest/fastest/lowest-latency)
  → Return provider slug (from endpoint.tag field)
  ↓
Persist to model_variants.config.PROVIDER

--execute (Planner)
  ↓
_validate_provider_lock() — abort if LOCK=true and PROVIDER=null
  ↓
ExecutionPlan includes resolved provider per variant
  ↓
Executor reads PROVIDER → adds "provider": {"only": [...], "allow_fallbacks": false}
```

## Agent Team

| Agent | Phase | Purpose |
|-------|-------|---------|
| `coder` | ProviderResolver, CLI modules | Core implementation |
| `coder` | Planner validation, Executor integration | Integration changes |
| `coder` | ConfigResolver, composite flow | Config hierarchy changes |
| `tester` | Unit + integration tests | Test coverage |
| `code_reviewer` | Final review | Quality gate |
| `technical_writer` | Documentation updates | docs + ADR |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Provider goes down after resolution | Medium | High | Explicit failure; user must re-run `--resolve-providers` |
| API endpoint changes response format | Low | Medium | Response validation + clear errors |
| Strategy data missing (no latency) | Medium | Low | Fallback to `first` with warning |
| Concurrent `--resolve-providers` | Low | Low | DB transaction/lock prevents duplicates |
| `PROVIDER_LOCK` modification post-creation | Low | Low | Allowed via `--provider-lock` on existing experiment |

## Success Criteria

1. `--resolve-providers` resolves all unresolved variants and prints a summary report (resolved/skipped/failed)
2. `--execute` with `PROVIDER_LOCK=true` and unresolved variants fails with clear error message directing user to `--resolve-providers`
3. `--execute` with resolved providers sends correct `provider.only` payload to OpenRouter API
4. All existing tests pass; new unit tests cover ProviderResolver strategies
5. Determinism verified: same resolved provider → same API request every time
6. `--provider-lock system-default` correctly bypasses `.env` inheritance
