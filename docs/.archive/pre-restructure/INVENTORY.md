# Pre-Restructure Documentation Inventory

**Created:** 2026-04-11  
**Purpose:** Catalog all documentation before restructuring  
**Status:** Initial inventory for review

---

## Classification Legend

| Symbol | Classification | Meaning |
|--------|---------------|---------|
| ✅ | Current | Matches code; content is valid and accurate |
| ⚠️ | Partial | Contains valid content but needs reconciliation with code or other docs |
| ❌ | Obsolete | Deprecated features, outdated plans, or superseded content |
| 📝 | Planning | Future work, gap analyses, or design materials |

---

## Inventory

### Root-Level Docs (docs/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| add-model-investigation.md | 📝 Planning | Investigation report on add-model behavior | TBD |
| CLI_STABILIZATION_ISSUES_AND_SUGGESTIONS.md | ⚠️ Partial | CLI issues from stabilization phase | May contain valid findings |
| CLI_STANDARDIZATION_REPORT.md | ⚠️ Partial | CLI standardization analysis | May contain valid findings |
| code-review-findings.md | ⚠️ Partial | Code review results | Time-bound findings |
| create-experiment-consolidation-design.md | 📝 Planning | Design doc for create-experiment | Superseded by implementation |
| create-experiment-investigation.md | 📝 Planning | Investigation report | Superseded by implementation |
| global-cli-audit.md | ⚠️ Partial | CLI audit results | May have valid findings |
| phase1-problemas-e-correcoes.md | ❌ Obsolete | Phase 1 problems (Portuguese) | Likely superseded |
| review-interface.md | ⚠️ Partial | Review interface spec | May be partially valid |

---

### Architecture Docs (docs/architecture/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| adr-execution-pipeline.md | ⚠️ Partial | ADR for execution pipeline | Needs validation |
| execution-paths-investigation.md | 📝 Planning | Investigation of execution paths | Reference material |
| parser-refactoring-summary.md | ❌ Obsolete | Past refactoring summary | Historical only |
| runs-duration-fix-summary.md | ❌ Obsolete | Past fix summary | Historical only |
| TODO.md | ⚠️ Partial | Architecture TODOs | May have valid items |
| v2-api-client-implementation-map.md | 📝 Planning | API client implementation plan | Check against code |
| v2-implementation-checklist.md | ⚠️ Partial | **Referenced in QWEN.md** | Needs validation |
| v2-implementation-plan.md | 📝 Planning | **Referenced in QWEN.md** | Large plan (2043 lines) |

---

### Contracts (docs/architecture/contracts/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| cli_module_resolution.md | ⚠️ Partial | CLI module resolution contract | Validate against code |
| cli_system-default_semantics.md | ✅ Current | **Referenced in QWEN.md** | Likely valid |
| command-contracts.md | ⚠️ Partial | Command contract definitions | Validate structure |
| configurarion_resolution_contract.md | ⚠️ Partial | Config resolution (note: typo in name) | Validate against config_resolver.py |
| domain-review-contract.md | ⚠️ Partial | Review domain contract | Validate against code |
| execute-run.md | ⚠️ Partial | Run execution contract | Validate against execution_engine.py |
| execution-plan.md | ⚠️ Partial | Execution plan contract | Validate against execution_plan.py |
| result-writer.md | ⚠️ Partial | Result writer contract | Validate against result_writer.py |

**⚠️ CONFLICT NOTE:** Multiple contracts may overlap or contradict. Need full reconciliation.

---

### Gap Reports (docs/architecture/gap-reports/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| 00-domain-mapping.md | 📝 Planning | Domain mapping analysis | Reference only |
| 01-execution-core-gap.md | 📝 Planning | Execution core gap analysis | Check if gaps filled |
| 02-logging-system-gap.md | 📝 Planning | Logging gap analysis | Check if gaps filled |
| 03-cli-system-gap.md | 📝 Planning | CLI gap analysis | Check if gaps filled |
| 04-review-ui-gap.md | 📝 Planning | Review UI gap analysis | Check if gaps filled |
| 05-database-layer-gap.md | 📝 Planning | Database gap analysis | Check if gaps filled |
| 06-configuration-system-gap.md | 📝 Planning | Config system gap analysis | Check if gaps filled |
| 07-error-handling-gap.md | 📝 Planning | Error handling gap analysis | Check if gaps filled |
| 08-answer-parsing-gap.md | 📝 Planning | Answer parsing gap analysis | Check if gaps filled |
| 99-consolidated-gap-analysis.md | 📝 Planning | Consolidated analysis | Summary document |

**NOTE:** Gap reports are likely outdated as implementation has progressed. Historical reference only.

---

### To-Be Architecture (docs/architecture/to-be/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| 01-execution-core-architecture.md | ⚠️ Partial | Execution core architecture | Validate against code |
| 02-logging-system-architecture.md | ⚠️ Partial | Logging architecture | Check if implemented |
| 03-cli-system-architecture.md | ⚠️ Partial | CLI architecture | Validate against code |
| 04-review-ui-architecture.md | ⚠️ Partial | Review UI architecture | Validate against code |
| 05-database-layer-architecture.md | ⚠️ Partial | Database architecture | Validate against schema |
| 06-configuration-system-architecture.md | ⚠️ Partial | Config architecture | Validate against code |
| 07-error-handling-architecture.md | ⚠️ Partial | Error handling architecture | Validate against code |
| 08-answer-parsing-architecture.md | ⚠️ Partial | Answer parsing architecture | Validate against code |
| cli.md | ⚠️ Partial | CLI spec | Compare with comandos_simples.md |
| **comandos_simples.md** | ✅ Current | **Referenced in QWEN.md** | Authoritative CLI spec |
| comandos_tobe.md | ⚠️ Partial | Future CLI spec | May conflict with comandos_simples.md |
| config_regras.md | ⚠️ Partial | Config rules (Portuguese) | May overlap with other config docs |
| config-key-hierarchy.md | ⚠️ Partial | Config key hierarchy | Validate against code |
| db_plan.md | ❌ Obsolete | Old database plan | Superseded by schema |
| execution-engine.md | ⚠️ Partial | Execution engine spec | Validate against code |
| **llmbc_system.md** | ✅ Current | **Referenced in QWEN.md** | System rules (authoritative) |
| responses.md | ⚠️ Partial | Response handling spec | Validate against code |
| schema_to-be.md | ⚠️ Partial | Target schema | Compare with actual schema |
| testes.md | 📝 Planning | Test strategy | Reference only |
| v2-image-support-implementation-plan.md | 📝 Planning | Image support plan | Future feature |

**⚠️ CONFLICT NOTE:** Multiple CLI specs exist (cli.md, comandos_simples.md, comandos_tobe.md). These may contradict. comandos_simples.md is authoritative per QWEN.md.

**⚠️ CONFLICT NOTE:** Multiple config docs exist (config_regras.md, config-key-hierarchy.md, 06-configuration-system-architecture.md). Need reconciliation.

**⚠️ CONFLICT NOTE:** Multiple schema docs may exist (db_plan.md, schema_to-be.md, actual code). Code is source of truth.

---

### Implementation Docs (docs/implementation/*.md)

| File | Classification | Notes | Superseded By |
|------|---------------|-------|---------------|
| phase7-report.md | ❌ Obsolete | Phase 7 implementation report | Historical only |

---

## Known Conflicts to Resolve

### 1. CLI Specification Conflicts
**Files involved:**
- `to-be/comandos_simples.md` (authoritative per QWEN.md)
- `to-be/cli.md`
- `to-be/comandos_tobe.md`
- `contracts/command-contracts.md`
- Root-level CLI audit/stabilization docs

**Action required:** Validate all against actual `src/cli/` implementation

---

### 2. Configuration System Conflicts
**Files involved:**
- `to-be/config_regras.md`
- `to-be/config-key-hierarchy.md`
- `to-be/06-configuration-system-architecture.md`
- `contracts/configurarion_resolution_contract.md`
- `gap-reports/06-configuration-system-gap.md`

**Action required:** Validate all against `src/core/config_resolver.py`

---

### 3. Database Schema Conflicts
**Files involved:**
- `to-be/db_plan.md` (likely obsolete)
- `to-be/schema_to-be.md`
- `gap-reports/05-database-layer-gap.md`
- Actual code: `src/db/models.py`, `src/db/schema.py`

**Action required:** Extract schema from code; compare with docs

---

### 4. Execution Flow Conflicts
**Files involved:**
- `contracts/execution-plan.md`
- `contracts/execute-run.md`
- `to-be/execution-engine.md`
- `to-be/01-execution-core-architecture.md`
- Actual code: `src/core/execution_engine.py`, `src/core/execution_plan.py`

**Action required:** Validate against code; execution flow belongs in architecture, not contracts

---

### 5. Result Writer / Review Contracts
**Files involved:**
- `contracts/result-writer.md`
- `contracts/domain-review-contract.md`
- `to-be/responses.md`
- Actual code: `src/core/result_writer.py`

**Action required:** Validate contracts against code

---

### 6. Implementation Plan vs Reality
**Files involved:**
- `v2-implementation-plan.md` (2043 lines)
- `v2-implementation-checklist.md`
- Actual codebase state

**Action required:** Audit what's actually implemented vs planned

---

## Observations

1. **Significant duplication:** Multiple documents cover similar ground with different perspectives
2. **Language mixing:** Some docs in Portuguese, most in English
3. **Mixed types:** Planning, reference, contracts, and historical docs all mixed together
4. **QWEN.md references:** Only 3 documents are authoritative per QWEN.md:
   - `llmbc_system.md`
   - `v2-implementation-checklist.md`
   - `comandos_simples.md`
5. **Age variance:** Documents range from recent (2026-03-30) to much older
6. **Gap reports:** Likely partially or fully obsolete as implementation progressed

---

## Next Steps

1. ✅ Review this inventory with project owner
2. ⏳ Confirm classifications
3. ⏳ Identify any missing documents
4. ⏳ Flag critical conflicts for immediate resolution
5. ⏳ Proceed to Phase 2 (Contracts) after approval

---

**Review Notes:** *(To be filled during review)*
