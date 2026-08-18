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

### [8] 17-08-2026
- **Trigger:** Main agent evaluation request (Fase 0 CLI test-suite seams: DATABASE_PATH override, base_url plumbing fix)
- **Scope:** .env, .env.example, src/cli/database.py, src/api/client.py, src/core/execution_plan.py, src/core/planner.py, src/core/execution_engine.py
- **Contracts checked:** determinism, idempotency, immutability, configuration-hierarchy, data-auditability, controlled evolution
- **Status:** Warning
- **Note:** BASE_URL plumbing fix (Planner→ExecutionPlan→ExecutionEngine) correctly restores documented behavior and doesn't touch frozen data, but confirmed a real, pre-existing Idempotency-contract tension: `src/utils/variant_signature.py` SIGNATURE_FIELD_ORDER omits BASE_URL even though schema.sql documents config as "10 model-level keys" and variant_signature as "model_id + config hash", so two variants differing only by --url collide on the UNIQUE(experiment_id, variant_signature) constraint and are rejected — this now actively blocks the CLI test suite's local-stub-vs-real-API use case; also flagged known-issues.md/configuration-reference.md as not updated for this fix and DATABASE_PATH respectively.

### [9] 17-08-2026
- **Trigger:** Main agent evaluation request (second pass, same session: mode_matrix.py INVALID routing fix, variant_signature.py field-order fix re-verification, bcllm.py composite-flow atomicity + rollback)
- **Scope:** src/core/mode_matrix.py, src/utils/variant_signature.py, bcllm.py, src/db/schema.py, src/db/schema.sql, src/db/repository.py, src/cli/bcllm_experiment.py, docs/status/known-issues.md
- **Contracts checked:** determinism, idempotency, immutability, configuration-hierarchy, data-auditability, controlled evolution
- **Status:** Warning
- **Note:** variant_signature BASE_URL idempotency gap from [8] is resolved as code, but "no migration" leaves a real (documented-partially) idempotency edge case: re-adding a semantically-identical model+config to a *pre-fix* experiment now hashes differently and won't be recognized as a duplicate. Bigger finding: enabling `(Mode.INVALID, "bcllm_experiment")` in mode_matrix also reactivates `--remove-experiment`'s pre-existing unconditional hard-delete (not just `--list-experiments` as the task framed it) — known-issues.md does disclose this ("reaches its module logic") but doesn't analyze the immutability-contract tension of hard-deleting snapshots/variants/runs that were previously unreachable/dead code. Also found `known-issues.md`'s own claim "the schema doesn't declare cascade" is factually wrong: `src/db/schema.py` (the declared runtime source of truth) DOES declare `ON DELETE CASCADE` on model_variants/question_snapshots/runs' experiment_id FK and `PRAGMA foreign_keys=ON` is enabled — `src/db/schema.sql` (the "reference copy") is stale and lacks it, so the two have silently drifted; bcllm.py rollback's explicit DELETEs are consequently redundant-but-harmless rather than necessary. bcllm.py's tuple[bool,int] return change has no other callers (verified via repo-wide grep). No violation found in the two changes' core logic themselves.

### [10] 17-08-2026
- **Trigger:** Main agent evaluation request (third pass, same session: verify user's three decisions on --remove-experiment/--remove-model/--remove-run)
- **Scope:** src/cli/bcllm_experiment.py::handle_remove_experiment, src/cli/bcllm_run.py::handle_remove_run, src/core/run_finalizer.py, src/core/planner.py::_get_runs, src/cli/bcllm_execute.py, src/core/async_orchestrator.py, bcllm.py::_rollback_created_experiment, tests/unit/cli/test_remove_commands.py, tests/cli_suite/cases/run.yaml::RN-003, docs/status/known-issues.md, docs/reference/cli-commands.md
- **Contracts checked:** logical immutability, idempotency, data-auditability, configuration hierarchy, controlled evolution, research-oriented
- **Status:** Violation
- **Note:** --remove-experiment disabling is complete and sound (composite-flow rollback in bcllm.py is a separate, already-flagged, narrowly-scoped mechanism, not a backdoor); --remove-model's hard delete is genuinely FK-protected against destroying responses/errors, confirmed. But traced a real, reachable bug in --remove-run's soft delete: Planner._get_runs() only applies the status allow-list when run_ids is None — `bcllm --execute --run <removed_run_id>` bypasses it entirely (validate_filters() doesn't check status either), so a removed run with pending items gets re-executed and AsyncOrchestrator's unconditional RunFinalizer.finalize_run() call overwrites status='removed' back to an execution-outcome status, silently reactivating it. This directly contradicts docs/status/known-issues.md's own claim ("verified, not just assumed") and docs/reference/cli-commands.md's unconditional "never picked up by --execute again" — both false for explicit --run targeting. Test suite (test_remove_commands.py, RN-003) only covers the implicit/default discovery path, not this one; RN-003's own comment admits the positive e2e scenario isn't actually expressible in the current runner.

### [11] 17-08-2026
- **Trigger:** Main agent evaluation request (fourth pass, same session: verify the `AND status != 'removed'` one-line fix to `Planner._get_runs()`'s run_ids branch, from finding [10])
- **Scope:** src/core/planner.py::_get_runs/build_plan, src/cli/bcllm_run.py::handle_remove_run docstring, src/cli/bcllm_execute.py, src/db/repository.py, src/core/run_finalizer.py, tests/unit/cli/test_remove_commands.py, tests/test_retry_whitelist_and_rerun.py, docs/status/known-issues.md, docs/reference/cli-commands.md
- **Contracts checked:** logical immutability, idempotency, data-auditability, configuration hierarchy, controlled evolution
- **Status:** OK
- **Note:** Fix confirmed sufficient and correctly placed: `Planner.build_plan()` (src/cli/bcllm_execute.py:333) is the sole caller of `build_plan`, which is the sole caller of `_get_runs` (planner.py:171) — no third path into an ExecutionPlan exists; other `runs`-table queries (`RunRepository.list_by_experiment`/`list_pending`) are unrelated to the execution/planning path (list_by_experiment intentionally still shows 'removed' rows for `--list-runs` audit purposes, list_pending is unused dead code) so the fix has no unintended side effect. Corrected prose in known-issues.md, cli-commands.md, and the handle_remove_run/`_get_runs` docstrings all check out factually against current code — no overclaiming found. New regression test and existing introspection tests (test_retry_whitelist_and_rerun.py) remain consistent with the fixed source.
