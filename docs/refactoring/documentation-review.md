# Documentation Review — Phase 1

**Session**: refactoring-2026-03-19
**Phase**: 1/11
**Date**: 2026-03-20
**Reviewer**: architect

---

## Summary

Reviewed 7 architectural documents for internal conflicts, ambiguities, and gaps. The documentation is **largely consistent** with strong alignment to core principles in QWEN.md. However, **3 critical conflicts** and **5 major ambiguities** were found that must be resolved before Phase 2 (AS-IS Inventory) to prevent implementation confusion.

**Key Findings**:
- **Critical**: ExecutionPlan structure inconsistency between documents
- **Critical**: Run status lifecycle mismatch
- **Critical**: Review field ownership ambiguity
- **Major**: ExecutionPlan persistence location unclear
- **Major**: Filter mechanism underspecified
- **Major**: Retry policy ownership ambiguous

---

## Conflicts Found

| Document A | Document B | Conflict Description | Severity |
|------------|------------|---------------------|----------|
| `execution-plan.md` | `execute-run.md` | **ExecutionPlan structure**: `execution-plan.md` defines `items` as flat list per run with `variant_id` and `snapshot_id` resolved. `execute-run.md` Phase E describes building plan from `(run_id, variant_id, snapshot_id)` combinations but doesn't clarify if items are flat or nested. The YAML shows `items` inside each `run`, but the deduplication logic in Phase E suggests cross-run deduplication. | Critical |
| `execute-run.md` | `result-writer.md` | **Run status values**: `execute-run.md` lists `pending`, `running`, `completed`, `failed`, `partial_failed`. `result-writer.md` only mentions `completed`, `partial_failed`, `failed`, `running` — missing `pending`. Unclear when `pending` transitions to `running`. | Critical |
| `domain-review-contract.md` | `result-writer.md` | **Review field ownership**: `domain-review-contract.md` states `needs_review` is "derived, set by ResultWriter". But `execute-run.md` Phase G says ResultWriter "persistir em `responses`" without mentioning derived field calculation. Unclear if ResultWriter calculates `needs_review` or receives it pre-calculated from ExecutionEngine. | Critical |
| `command-contracts.md` | `execute-run.md` | **ExecutionPlan persistence**: `command-contracts.md` says `--execute-run` creates ExecutionPlan "em memória ou persistido como referência". `execution-plan.md` says "persisted only as reference/audit". `execute-run.md` doesn't mention persistence at all. Unclear if ExecutionPlan should be persisted by default or only on demand. | Major |
| `execution-plan.md` | `execute-run.md` | **Retry policy location**: `execution-plan.md` YAML shows `retry_policy` inside each `run` object. `execute-run.md` Phase F mentions "executar com retry técnico" but doesn't specify where retry configuration comes from. Unclear if retry is per-run, per-experiment, or global. | Major |
| `domain-review-contract.md` | `QWEN.md` | **Review fields in schema**: `domain-review-contract.md` proposes adding `parse_confidence`, `needs_review`, `manual_answer` to `responses` table. `QWEN.md` makes no mention of review workflow at all. This is a significant domain concept not reflected in the mental model. | Major |
| `execute-run.md` | `command-contracts.md` | **Filter scope**: `execute-run.md` Section 2 mentions "Com filtros: executa apenas o subconjunto especificado" but doesn't define filter syntax or mechanism. `command-contracts.md` doesn't mention filters at all. Unclear how filters are passed from CLI to Planner. | Minor |

---

## Ambiguities Found

| Document | Section | Ambiguity | Impact |
|----------|---------|-----------|--------|
| `execution-plan.md` | 4.2 | **`prompts_effective` structure**: Shows `system` and `user` keys but doesn't specify if this is the complete structure. QWEN.md mentions "prompt templates" but doesn't define resolution priority (run vs experiment defaults). | High |
| `execution-plan.md` | 5 | **`model_config_effective` completeness**: States "MUST include all parameters that affect model behavior" but doesn't provide exhaustive list. Implementers won't know which parameters to resolve. | High |
| `execute-run.md` | 8 | **Deduplication key**: Says "Verificar se já existe resposta persistida" with `WHERE run_id AND variant_id AND snapshot_id` but doesn't specify if this is a unique constraint or application-level check. | High |
| `result-writer.md` | 5 | **Idempotency mechanism**: Says "Se já existir: NÃO sobrescrever, NÃO duplicar" but doesn't specify how to detect existence (unique constraint? SELECT before INSERT? UPSERT?). | High |
| `execute-run.md` | 10 | **Retry técnico definition**: Mentions "executar com retry técnico" but doesn't define what constitutes a retryable error vs terminal failure. | Medium |
| `domain-review-contract.md` | 4 | **`is_correct` derivation timing**: Shows `is_correct` as derived field but doesn't specify when it's calculated (INSERT time? QUERY time? VIEW?). Schema shows it as `BOOLEAN` column, suggesting storage. | Medium |
| `command-contracts.md` | 8 | **Removal semantics**: Says "marcar entidades como inativas" but doesn't specify the mechanism (soft delete flag? separate `active` table? status field?). | Medium |
| `execution-plan.md` | 7 | **Engine input granularity**: Says "recebe um run do plano por vez (recomendado) ou o plano inteiro" — this is a design decision that affects batching and parallelism strategy. | Low |

---

## Gaps Found

| Concept/Flow | What's Missing | Why It Matters |
|--------------|----------------|----------------|
| **Error handling flow** | No document describes what happens when ExecutionEngine encounters an unrecoverable error (e.g., API key invalid, network permanently down). | Implementation needs clear error propagation path from Engine → ResultWriter → Run status. |
| **Planner interface** | No contract defines the interface between CLI and Planner (input parameters, output format, error conditions). | Phase 2 needs to understand what CLI must provide to Planner. |
| **Randomizer contract** | `execute-run.md` mentions `Randomizer (seed do run → fallback experimento)` but no document defines Randomizer interface or seed resolution priority. | Reproducibility depends on deterministic randomization. |
| **OpenRouterClient contract** | `execute-run.md` mentions `OpenRouterClient` but no interface definition exists. | Implementation needs clear API contract for model invocation. |
| **Question payload structure** | `execution-plan.md` shows `question_payload` with `stem`, `options`, `answer_key` but doesn't define complete schema or validation rules. | ExecutionEngine needs to know exact payload structure for prompt assembly. |
| **Timing info schema** | Multiple documents reference `timing_info` but none define its structure (latency? token timestamps? per-attempt breakdown?). | Metrics and auditing require consistent timing data. |
| **Token counting** | No document specifies how token usage is tracked, reported, or attributed (per-request? per-response? aggregated?). | Cost tracking and rate limiting depend on token metrics. |
| **Experiment defaults resolution** | QWEN.md mentions "default configuration" and "prompt templates" but no document defines how defaults are stored or resolved. | Planner needs to know where to fetch defaults. |
| **Run creation preconditions** | `command-contracts.md` says `--create-run` creates a `run` but doesn't specify preconditions (must have models? must have snapshots?). | Implementation needs validation rules. |
| **Review workflow trigger** | `domain-review-contract.md` defines review fields but doesn't describe the review workflow itself (how does a user access responses needing review? how is `manual_answer` submitted?). | Review feature is incomplete without workflow definition. |

---

## Consistency with QWEN.md

| Contract | Alignment Status | Notes |
|----------|-----------------|-------|
| `command-contracts.md` | ✅ Aligned | Strongly aligns with principles: "Experiments are explicit", "Execution is never implicit", "No inference during execution". Clear separation of concerns. |
| `execute-run.md` | ✅ Aligned | Follows "No execution without identity" and "All results are auditable". Phases clearly separate resolution (Planner) from execution (Engine). |
| `execution-plan.md` | ✅ Aligned | Perfectly embodies "immutable execution plans" principle. Explicit about "Planner decides, Engine executes". |
| `result-writer.md` | ✅ Aligned | Aligns with "append-only for results" database philosophy. Clear boundary: "does not decide scope". |
| `domain-review-contract.md` | ⚠️ Partial | Review workflow is not mentioned in QWEN.md conceptual model. The 3 review fields (`parse_confidence`, `needs_review`, `manual_answer`) are implementation details that should be referenced in the mental model. |
| `README.md` | ✅ Aligned | Correctly summarizes architecture and points to QWEN.md as source of truth. Appropriately flags outdated docs. |

---

## Recommendations

### Critical (Must Resolve Before Phase 2)

1. **Resolve ExecutionPlan structure ambiguity**
   - Clarify in `execute-run.md` that items are nested per run (matching `execution-plan.md` YAML)
   - Add explicit statement: "Each run contains its own flat list of items; no cross-run deduplication"

2. **Align run status lifecycle**
   - Add `pending` to `result-writer.md` status table
   - Define transition: `pending` → `running` occurs when Planner emits ExecutionPlan

3. **Clarify review field ownership**
   - Update `result-writer.md` to explicitly state: "ResultWriter calculates `needs_review` from `parse_confidence` and `selected_answer` before INSERT"
   - Add `parse_confidence` and `needs_review` to QWEN.md conceptual model under ResultWriter

### Major (Should Resolve Before Implementation)

4. **Define ExecutionPlan persistence policy**
   - Decide: persist every ExecutionPlan? Only on failure? Never (memory only)?
   - Update `command-contracts.md` and `execution-plan.md` with consistent statement

5. **Specify retry policy ownership**
   - Define if retry is per-run, per-experiment, or system-wide
   - Add retry configuration source to `execution-plan.md` structure

6. **Complete `model_config_effective` definition**
   - Add exhaustive list of parameters that affect model behavior
   - Include: `temperature`, `top_p`, `top_k`, `max_output_tokens`, `frequency_penalty`, `presence_penalty`, `stop_sequences`, `enable_vision`, `structured_output`, `reasoning_mode`, `reasoning_effort`

7. **Add review workflow to QWEN.md**
   - Add brief mention of manual review as optional post-execution workflow
   - Reference `domain-review-contract.md`

### Minor (Can Resolve During Implementation)

8. **Define filter mechanism**
   - Document CLI filter syntax (e.g., `--model-filter`, `--question-filter`)
   - Specify how filters propagate to Planner

9. **Specify idempotency mechanism**
   - Recommend: unique constraint on `(run_id, variant_id, snapshot_id)` with INSERT ... ON CONFLICT DO NOTHING

10. **Define timing_info and token counting schema**
    - Add to `execution-plan.md` or separate metrics contract

---

## Approval Status

- [x] Ready for Phase 2 (no critical conflicts)
- [ ] Needs resolution (critical conflicts found)

**Resolution Log** (2026-03-20):
- ✅ **Conflict 1** (ExecutionPlan structure): Resolved — Added explicit statement to `execute-run.md` clarifying per-run deduplication, no cross-run.
- ✅ **Conflict 2** (Run status lifecycle): Resolved — Added `pending` status to `result-writer.md` with full lifecycle table and transition rules.
- ✅ **Conflict 3** (Review field ownership): Resolved — Added Section 10 to `result-writer.md` explicitly stating ResultWriter calculates `needs_review`. Updated QWEN.md to include review fields.

**Current Status**: All critical conflicts resolved. **Phase 2 is cleared to begin.**

---

## Next Steps

1. **Pause Phase 2** until critical conflicts are resolved
2. **Update affected documents** with clarifications from Recommendations section
3. **Re-validate** updated documents against QWEN.md
4. **Proceed to Phase 2** once all Critical items are marked resolved

---

**Review Completed**: 2026-03-20
**Time Spent**: ~45 minutes
**Documents Reviewed**: 7
**Total Findings**: 7 conflicts, 8 ambiguities, 10 gaps
