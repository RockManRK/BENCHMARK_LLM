---
type: adr
audience: both
date: 2026-04-14
status: accepted
---

# ADR-001: Provider Selection & Locking for OpenRouter

**Status:** Accepted
**Date:** 2026-04-14
**Context:** OpenRouter models can be served by multiple providers. The system's default behavior lets OpenRouter choose providers dynamically, which introduces non-determinism into benchmark results.

## Decision

Implement explicit provider resolution via `--resolve-providers` CLI command:

1. **Provider resolution is explicit**: Users run `--resolve-providers` to resolve and persist providers for model variants.

2. **Provider is part of deterministic config**: Once resolved, `PROVIDER` is frozen in `model_variants.config`.

3. **Pre-execution validation**: When `PROVIDER_LOCK=true`, execution fails if any variant has `PROVIDER=null`.

4. **Executor is pure**: Provider is read from `ExecutionPlan`, not resolved during execution.

5. **`null` never means "resolve automatically"**: `PROVIDER=null` means "let OpenRouter choose" (when `PROVIDER_LOCK=false`).

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Auto-resolve at execution time | Rejected — violates "explicit over implicit" principle; Executor would need DB write access |
| Hybrid with auto-warn | Rejected — blurs explicit/implicit boundary; adds branching logic |

## Consequences

### Positive
- Deterministic provider selection → reproducible benchmark results
- Clear audit trail (provider logged in ExecutionPlan)
- Explicit user control over provider selection

### Negative
- Extra CLI step required before execution (when `PROVIDER_LOCK=true`)
- Provider availability risk (resolved provider may go down)

### Neutral
- No new database columns (uses existing `config` JSON)
- Planner and Executor remain pure (no DB writes during execution)

## Contracts Affected

- [contracts/determinism.md](../determinism.md) — Added Provider Locking section to define invariant

## Related Documents

- [reference/cli-commands.md](../../reference/cli-commands.md) — `--resolve-providers`, `--provider`, `--provider-lock`
- [reference/configuration-reference.md](../../reference/configuration-reference.md) — `AUTO_PROVIDER_LOCK`, `PROVIDER_SELECTION_STRATEGY`
- [architecture/execution-architecture.md](../execution-architecture.md) — Provider resolution in execution flow