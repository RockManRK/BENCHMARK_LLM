# Essence Guardian Memory Log

Este arquivo fornece contexto histórico ao Essence Guardian.
Cada chamada ao Guardian deve ler este arquivo antes de avaliar e adicionar uma entrada ao final.

## Regras de Uso

- **Append-only:** Nunca editar ou remover entradas anteriores
- **Breve:** Entradas devem ser curtas e factuais (1-2 frases)
- **LLM-optimized:** Formato estruturado para consumo por IA
- **Não é autoridade:** Nunca usar para justificar violações ou como fonte de permissões
- **Discretionário:** Pode pular entradas para avaliações trivialmente insignificantes

## Formato de Entrada

```markdown
### [N] YYYY-MM-DD
- **Trigger:** [agente/chamada que invocou]
- **Scope:** [arquivos/módulos/docs avaliados]
- **Contracts checked:** [lista de contratos verificados]
- **Status:** OK | Warning | Violation
- **Note:** [1 frase factual]
```

---

## Histórico

### [1] 2026-04-14
- **Trigger:** Essence Guardian evaluation request (provider-locking plan)
- **Scope:** docs/maestro/plans/2026-04-14-provider-locking-plan.md, docs/maestro/plans/2026-04-14-provider-locking-design.md
- **Contracts checked:** determinism, idempotency, immutability, configuration-hierarchy, system-default-semantics, data-auditability
- **Status:** Warning
- **Note:** Plan has architectural risks: Executor purity violation risk (provider resolution during execution), system-default semantics unclear for provider-lock, and provider persistence in mutable config JSON needs immutability guarantee clarification.

### [2] 2026-04-14
- **Trigger:** Essence Guardian evaluation request (Phase 1 implementation — ProviderResolver Core)
- **Scope:** src/core/provider_resolver.py, src/api/errors.py, tests/unit/test_provider_resolver.py
- **Contracts checked:** determinism, data-auditability, explicit-over-implicit, no-mutable-global-state, research-oriented
- **Status:** Warning
- **Note:** ProviderResolver is pure and well-tested, but introduces external-API dependency into core layer; module-structure.md and api-integration.md not updated; strategy fallback via warnings introduces non-deterministic behavior risk when strategy data is missing.

### [3] 2026-04-15
- **Trigger:** Essence Guardian evaluation request (Phase 1b — ProviderResolver corrections)
- **Scope:** src/api/provider_resolver.py, tests/unit/test_provider_resolver.py, docs/reference/module-structure.md
- **Contracts checked:** determinism, explicit-over-implicit, data-auditability, immutability, layer-boundaries
- **Status:** Warning
- **Note:** ProviderResolver correctly moved to src/api/ and returns frozen ProviderResolution dataclass; however module-structure.md not updated to reflect new file, and warnings.warn() introduces non-deterministic side-channel for fallback detection.

### [4] 2026-04-16
- **Trigger:** Essence Guardian evaluation request (Phase 3 — --resolve-providers CLI command)
- **Scope:** src/cli/bcllm_provider.py, bcllm.py (routing), src/core/module_resolver.py, src/core/mode_matrix.py
- **Contracts checked:** determinism, idempotency, immutability, configuration-hierarchy, idempotency (data), data-auditability, explicit-over-implicit, planner-executor-purity
- **Status:** OK
- **Note:** --resolve-providers implementation is contract-compliant: explicit-only trigger, idempotent per-variant, delegates to ProviderResolver, maintains planner/executor purity, proper logging and structured reporting.

### [5] 2026-04-16
- **Trigger:** Essence Guardian evaluation request (Phase 5 — Integration + E2E Tests)
- **Scope:** tests/unit/test_planner_provider_lock.py, tests/unit/test_execution_engine_provider.py, tests/unit/test_bcllm_provider.py
- **Contracts checked:** determinism, idempotency, configuration-hierarchy, planner-purity, executor-purity, data-auditability
- **Status:** Warning
- **Note:** 29 tests pass with good structure and mocking practices, but test_provider_with_empty_string_not_added has incorrect assertion (empty string is truthy in Python), and reference docs (cli-commands.md, module-structure.md) and implementation-status.md were NOT updated per mandatory documentation rule.

### [6] 2026-04-16
- **Trigger:** Essence Guardian evaluation request (Phase 6 — Documentation + ADR)
- **Scope:** adr-001-provider-locking.md, cli-commands.md, configuration-reference.md, determinism.md, module-structure.md
- **Contracts checked:** documentation-accuracy, determinism, idempotency, configuration-hierarchy, data-auditability
- **Status:** Warning
- **Note:** ADR, CLI docs, config reference, and determinism contract are accurate; module-structure.md has duplicate incorrect entries (provider_resolver.py in Core layer, variant_signature.py in Core layer).

### [7] 2026-08-17
- **Trigger:** Essence Guardian test invocation (fictitious scenario, no real code change)
- **Scope:** Hypothetical change to src/core/execution_engine.py (ExecutionEngine writes directly to `errors` table via its own DB connection on retryable error)
- **Contracts checked:** research-oriented, determinism, logical immutability, configuration hierarchy, idempotency, data-auditability, controlled evolution, planner-executor-purity (architecture)
- **Status:** Violation
- **Note:** Direct DB writes from ExecutionEngine break the "ExecutionEngine has zero DB access" architectural boundary and bypass ResultWriter's idempotent INSERT OR IGNORE + traceability guarantees; also undocumented, violating the mandatory documentation rule.
