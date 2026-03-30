---
name: "architecture-documentation-program-impl-plan.md"
date: 2026-03-29
version: 1.0
task_complexity: complex
design_depth: deep
status: pending_approval
---

# Architecture Documentation Program — Implementation Plan

---

## 1. Plan Overview

**Total Phases**: 12  
**Agents Involved**: agent-architect, technical_writer, architect, code_reviewer, product_manager  
**Execution Mode**: Sequential (phases have knowledge dependencies)  
**Estimated Effort**: Documentation and analysis only — no code implementation  

**Summary**:
This plan executes the Domain-Driven Analysis approach approved in the design document. It consists of:
- Phase 1: Setup & ToDo creation
- Phase 2: Domain Discovery (V1/V2 analysis to finalize domain list)
- Phases 3-10: Per-domain documentation cycles (8 initial domains)
- Phase 11: Gap report consolidation
- Phase 12: Implementation plan for V2 completion

---

## 2. Dependency Graph

```
Phase 1 (Setup)
    │
Phase 2 (Domain Discovery)
    │
    ├─→ Phase 3 (Execution Core) ──→ Phase 4 (Logging) ──→ Phase 5 (CLI)
    │                                                        │
    ├─→ Phase 6 (Review UI) ──→ Phase 7 (Database) ──→ Phase 8 (Configuration)
    │                                                        │
    └─→ Phase 9 (Error Handling) ──→ Phase 10 (Answer Parsing)
                                       │
                                       ↓
                              Phase 11 (Gap Consolidation)
                                       │
                                       ↓
                              Phase 12 (V2 Implementation Plan)
```

**Parallel Opportunities**: Phases 3-10 can execute in parallel batches of 2-3 domains if file ownership doesn't overlap (all produce separate documentation files).

---

## 3. Execution Strategy

| Stage | Phases | Execution Mode | Rationale |
|-------|--------|----------------|-----------|
| **Stage 1: Foundation** | 1-2 | Sequential | Domain discovery must complete before per-domain work |
| **Stage 2: Domain Docs** | 3-10 | Parallel batches (2-3 per batch) | Independent domains, no file overlap |
| **Stage 3: Consolidation** | 11-12 | Sequential | Requires all domain docs complete |

---

## 4. Phase Details

### Phase 1: Setup & ToDo Creation

**Objective**: Create the ToDo document and establish documentation folder structure.

**Agent**: `technical_writer`

**Files to Create**:
- `docs/architecture/TODO.md` — Master ToDo with task description, objectives, rules, steps
- `docs/architecture/legacy-analysis/` — Directory (empty, for V1 analysis docs)
- `docs/architecture/v2-current/` — Directory (empty, for V2 state docs)
- `docs/architecture/gap-reports/` — Directory (empty, for gap reports)
- `docs/architecture/v2-adaptation/` — Directory (empty, for adaptation docs)

**Implementation Details**:
- TODO.md must include:
  - Task description (from user request)
  - Objectives (7 functional requirements)
  - Rules (V1 code not copied, V2 contracts respected, contradictions flagged)
  - Steps (all phases from this plan)
  - Domain list (8 initial domains + expansion rule)
  - Progress tracking section

**Validation**:
- Verify all directories exist
- Verify TODO.md is readable and contains all required sections

**Dependencies**: None

**Risk**: LOW

---

### Phase 2: Domain Discovery

**Objective**: Analyze V1 and V2 codebases to finalize the domain list, identifying any additional domains not in the initial 8.

**Agent**: `agent-architect`

**Files to Read**:
- `src_legacy/**/*` — All V1 source files
- `src/**/*` — All V2 source files
- `docs/architecture/**/*.md` — All existing architecture documents

**Files to Create**:
- `docs/architecture/legacy-analysis/00-domain-inventory.md` — Complete list of V1 domains discovered
- `docs/architecture/v2-current/00-domain-inventory.md` — Complete list of V2 domains discovered
- `docs/architecture/gap-reports/00-domain-mapping.md` — V1→V2 domain mapping

**Implementation Details**:
- Analyze V1 directory structure: `api`, `cli`, `core`, `db`, `utils`, `main.py`
- Analyze V2 directory structure: `api`, `cli`, `core`, `db`, `review`, `utils`, `validators`
- Identify functional areas not represented in initial 8 domains
- Flag any V1 directories/files that don't map to V2 equivalents
- Update domain list if new domains discovered

**Validation**:
- Domain inventory lists all directories and major modules
- Mapping document identifies gaps at directory level

**Dependencies**: Phase 1

**Risk**: MEDIUM (may discover more domains than expected)

---

### Phase 3: Execution Core Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Execution Core domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/core/` — V1 execution core
- `src/core/` — V2 execution core
- `docs/architecture/legacy.ignore/legacy_execution_core.md` — Existing legacy doc
- `docs/architecture/contracts/result-writer.md` — Existing contract

**Files to Create**:
- `docs/architecture/to-be/01-execution-core-architecture.md` — Architecture & Contracts
- `docs/architecture/v2-adaptation/01-execution-core-adaptation.md` — V2 Adaptation
- `docs/architecture/legacy-analysis/01-execution-core.md` — V1 analysis
- `docs/architecture/v2-current/01-execution-core.md` — V2 current state
- `docs/architecture/gap-reports/01-execution-core-gap.md` — Gap report

**Implementation Details**:
- Document: Execution Engine, Result Writer, Planner, API Client
- Extract V1 concepts without referencing V1 code
- Define contracts: interfaces, invariants, operations
- Identify V2 gaps: what's missing, what's incomplete
- Adaptation: V2 implementation path respecting V2 contracts

**Validation**:
- Architecture doc follows template (7 sections)
- V2 Adaptation doc follows template (6 sections)
- No V1 code references in Architecture doc

**Dependencies**: Phase 2

**Risk**: HIGH (core system complexity)

---

### Phase 4: Logging System Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Logging System domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/utils/logging_config.py` — V1 logging
- `src/utils/` — V2 utils (check for logging)
- `docs/architecture/legacy.ignore/legacy_logging_system.md` — Existing legacy doc

**Files to Create**:
- `docs/architecture/to-be/02-logging-system-architecture.md`
- `docs/architecture/v2-adaptation/02-logging-system-adaptation.md`
- `docs/architecture/legacy-analysis/02-logging-system.md`
- `docs/architecture/v2-current/02-logging-system.md`
- `docs/architecture/gap-reports/02-logging-system-gap.md`

**Implementation Details**:
- Document: Logging configuration, handlers, levels, rotation
- Extract V1 logging philosophy and patterns
- Define contracts: log levels, handlers, configuration
- Identify V2 gaps: logging may be minimal or missing
- Adaptation: V2 implementation with proper logging architecture

**Validation**:
- Architecture doc follows template
- V2 Adaptation identifies specific gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM

---

### Phase 5: CLI System Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the CLI System domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/cli/` — V1 CLI
- `src/cli/` — V2 CLI
- `docs/architecture/to-be/comandos_simples.md` — CLI spec
- `docs/architecture/to-be/comandos_tobe.md` — CLI to-be
- `docs/architecture/contracts/cli_null_semantics.md` — Null semantics contract

**Files to Create**:
- `docs/architecture/to-be/03-cli-system-architecture.md`
- `docs/architecture/v2-adaptation/03-cli-system-adaptation.md`
- `docs/architecture/legacy-analysis/03-cli-system.md`
- `docs/architecture/v2-current/03-cli-system.md`
- `docs/architecture/gap-reports/03-cli-system-gap.md`

**Implementation Details**:
- Document: Commands, argument parsing, configuration hierarchy
- Extract V1 CLI patterns and commands
- Define contracts: command structure, null semantics, configuration resolution
- Identify V2 gaps: commands implemented vs. specified
- Adaptation: V2 implementation respecting CLI contracts

**Validation**:
- Architecture doc aligns with existing CLI contracts
- V2 Adaptation identifies command-by-command gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM (CLI is mostly complete per user)

---

### Phase 6: Review UI Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Review UI domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/cli/review_ui.py` — V1 review UI
- `src/review/` — V2 review
- `docs/architecture/legacy.ignore/legacy_ux_analysis.md` — Existing legacy doc
- `docs/architecture/to-be/comandos_simples.md` — Review commands section

**Files to Create**:
- `docs/architecture/to-be/04-review-ui-architecture.md`
- `docs/architecture/v2-adaptation/04-review-ui-adaptation.md`
- `docs/architecture/legacy-analysis/04-review-ui.md`
- `docs/architecture/v2-current/04-review-ui.md`
- `docs/architecture/gap-reports/04-review-ui-gap.md`

**Implementation Details**:
- Document: Manual review interface, classification workflow, keyboard shortcuts
- Extract V1 review UI flow and features
- Define contracts: review status, manual_answer, needs_review
- Identify V2 gaps: review UI completeness
- Adaptation: V2 implementation respecting review contracts

**Validation**:
- Architecture doc covers full review workflow
- V2 Adaptation identifies UI gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM

---

### Phase 7: Database Layer Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Database Layer domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/db/` — V1 database
- `src/db/` — V2 database
- `docs/architecture/to-be/schema.sql` — Current schema

**Files to Create**:
- `docs/architecture/to-be/05-database-layer-architecture.md`
- `docs/architecture/v2-adaptation/05-database-layer-adaptation.md`
- `docs/architecture/legacy-analysis/05-database-layer.md`
- `docs/architecture/v2-current/05-database-layer.md`
- `docs/architecture/gap-reports/05-database-layer-gap.md`

**Implementation Details**:
- Document: Schema, entities, relationships, constraints
- Extract V1 database patterns
- Define contracts: table structures, foreign keys, indexes
- Identify V2 gaps: schema completeness
- Adaptation: V2 schema evolution path

**Validation**:
- Architecture doc matches schema.sql
- V2 Adaptation identifies missing tables/columns

**Dependencies**: Phase 2

**Risk**: LOW (schema is well-documented)

---

### Phase 8: Configuration System Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Configuration System domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/utils/config.py` — V1 configuration
- `src/utils/` — V2 configuration
- `docs/architecture/contracts/configurarion_resolution_contract.md` — Config contract
- `docs/architecture/contracts/cli_null_semantics.md` — Null semantics

**Files to Create**:
- `docs/architecture/to-be/06-configuration-system-architecture.md`
- `docs/architecture/v2-adaptation/06-configuration-system-adaptation.md`
- `docs/architecture/legacy-analysis/06-configuration-system.md`
- `docs/architecture/v2-current/06-configuration-system.md`
- `docs/architecture/gap-reports/06-configuration-system-gap.md`

**Implementation Details**:
- Document: Configuration hierarchy, resolution order, null semantics
- Extract V1 configuration patterns
- Define contracts: resolution order, null handling, .env behavior
- Identify V2 gaps: configuration completeness
- Adaptation: V2 implementation respecting configuration contracts

**Validation**:
- Architecture doc aligns with config contract
- V2 Adaptation identifies resolution gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM

---

### Phase 9: Error Handling Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Error Handling domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/api/error_handler.py` — V1 error handling
- `src/api/` — V2 API (check for error handling)
- `docs/architecture/legacy.ignore/legacy_execution_core.md` — Error handling section

**Files to Create**:
- `docs/architecture/to-be/07-error-handling-architecture.md`
- `docs/architecture/v2-adaptation/07-error-handling-adaptation.md`
- `docs/architecture/legacy-analysis/07-error-handling.md`
- `docs/architecture/v2-current/07-error-handling.md`
- `docs/architecture/gap-reports/07-error-handling-gap.md`

**Implementation Details**:
- Document: Error types, retry behavior, propagation, classification
- Extract V1 error handling patterns
- Define contracts: error types, retryable vs. fatal, propagation
- Identify V2 gaps: error handling completeness
- Adaptation: V2 implementation with proper error architecture

**Validation**:
- Architecture doc covers all error scenarios
- V2 Adaptation identifies error handling gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM

---

### Phase 10: Answer Parsing Domain

**Objective**: Create Architecture & Contracts document and V2 Adaptation document for the Answer Parsing domain.

**Agent**: `agent-architect` (Architecture doc), `architect` (V2 Adaptation doc)

**Files to Read**:
- `src_legacy/api/parser.py` — V1 parsing
- `src/core/` — V2 (check for parser)
- `docs/architecture/legacy.ignore/legacy_execution_core.md` — Answer parsing section

**Files to Create**:
- `docs/architecture/to-be/08-answer-parsing-architecture.md`
- `docs/architecture/v2-adaptation/08-answer-parsing-adaptation.md`
- `docs/architecture/legacy-analysis/08-answer-parsing.md`
- `docs/architecture/v2-current/08-answer-parsing.md`
- `docs/architecture/gap-reports/08-answer-parsing-gap.md`

**Implementation Details**:
- Document: Pattern matching, confidence classification, answer extraction
- Extract V1 parsing patterns and confidence levels
- Define contracts: parse_confidence values, selected_answer format
- Identify V2 gaps: parser implementation
- Adaptation: V2 implementation with proper parsing architecture

**Validation**:
- Architecture doc covers all parsing patterns
- V2 Adaptation identifies parser gaps

**Dependencies**: Phase 2

**Risk**: MEDIUM

---

### Phase 11: Gap Report Consolidation

**Objective**: Consolidate all gap reports into a master gap analysis document.

**Agent**: `technical_writer`

**Files to Read**:
- `docs/architecture/gap-reports/*.md` — All individual gap reports

**Files to Create**:
- `docs/architecture/gap-reports/99-consolidated-gap-analysis.md` — Master gap report

**Implementation Details**:
- Aggregate all domain gap reports
- Identify cross-domain patterns
- Prioritize gaps by implementation criticality
- Create summary matrix: Domain | Gap | Priority | Effort

**Validation**:
- All domain gaps represented
- Priority matrix complete

**Dependencies**: Phases 3-10

**Risk**: LOW

---

### Phase 12: V2 Implementation Plan

**Objective**: Create the final, detailed implementation plan for completing V2.

**Agent**: `agent-architect` (plan creation), `product_manager` (prioritization)

**Files to Read**:
- `docs/architecture/v2-adaptation/*.md` — All V2 adaptation documents
- `docs/architecture/gap-reports/99-consolidated-gap-analysis.md` — Gap analysis

**Files to Create**:
- `docs/architecture/v2-implementation-plan.md` — Final V2 implementation plan

**Implementation Details**:
- Define implementation phases based on gap priorities
- Order phases by dependency and criticality
- Estimate effort per phase
- Define validation criteria per phase
- Create execution roadmap

**Validation**:
- Plan covers all identified gaps
- Phases are properly ordered
- Validation criteria are measurable

**Dependencies**: Phases 3-11

**Risk**: MEDIUM

---

## 5. File Inventory

| File | Phase | Purpose |
|------|-------|---------|
| `docs/architecture/TODO.md` | 1 | Master ToDo document |
| `docs/architecture/legacy-analysis/00-domain-inventory.md` | 2 | V1 domain inventory |
| `docs/architecture/v2-current/00-domain-inventory.md` | 2 | V2 domain inventory |
| `docs/architecture/gap-reports/00-domain-mapping.md` | 2 | Domain mapping |
| `docs/architecture/to-be/01-execution-core-architecture.md` | 3 | Execution Core Architecture |
| `docs/architecture/v2-adaptation/01-execution-core-adaptation.md` | 3 | Execution Core V2 Adaptation |
| `docs/architecture/legacy-analysis/01-execution-core.md` | 3 | Execution Core V1 Analysis |
| `docs/architecture/v2-current/01-execution-core.md` | 3 | Execution Core V2 Current |
| `docs/architecture/gap-reports/01-execution-core-gap.md` | 3 | Execution Core Gap Report |
| ... (repeat for domains 2-8) | 4-10 | Same pattern for each domain |
| `docs/architecture/gap-reports/99-consolidated-gap-analysis.md` | 11 | Consolidated Gap Analysis |
| `docs/architecture/v2-implementation-plan.md` | 12 | Final V2 Implementation Plan |

**Total Files**: ~45 documents (5 per domain × 8 domains + setup + consolidation + final plan)

---

## 6. Risk Classification

| Phase | Risk Level | Rationale |
|-------|------------|-----------|
| 1 | LOW | Simple file/directory creation |
| 2 | MEDIUM | May discover unexpected domains |
| 3 | HIGH | Core system complexity, critical for V2 |
| 4 | MEDIUM | Logging may be minimal in V2 |
| 5 | MEDIUM | CLI mostly complete, but complex |
| 6 | MEDIUM | Review UI completeness unknown |
| 7 | LOW | Schema well-documented |
| 8 | MEDIUM | Configuration contracts complex |
| 9 | MEDIUM | Error handling patterns vary |
| 10 | MEDIUM | Parser implementation unknown |
| 11 | LOW | Documentation consolidation |
| 12 | MEDIUM | Implementation planning requires synthesis |

---

## 7. Execution Profile

```
Execution Profile:
- Total phases: 12
- Parallelizable phases: 8 (Phases 3-10, in 3-4 batches of 2-3 domains each)
- Sequential-only phases: 4 (Phases 1, 2, 11, 12)
- Estimated parallel wall time: ~60-80% of sequential time
- Estimated sequential wall time: Full linear execution

Note: Native parallel execution currently runs agents in autonomous mode.
All tool calls are auto-approved without user confirmation.
```

**Recommended Execution Mode**: **Sequential** for Phases 1-2 and 11-12, **Parallel batches** for Phases 3-10 (2-3 domains per batch).

---

## 8. Token Budget & Cost Estimate

| Phase | Agent | Est. Input | Est. Output | Est. Cost* |
|-------|-------|-----------|------------|-----------|
| 1 | technical_writer | 500 | 2,000 | $0.01 |
| 2 | agent-architect | 50,000 | 10,000 | $0.90 |
| 3 | agent-architect + architect | 30,000 | 15,000 | $1.20 |
| 4 | agent-architect + architect | 15,000 | 10,000 | $0.60 |
| 5 | agent-architect + architect | 20,000 | 10,000 | $0.80 |
| 6 | agent-architect + architect | 15,000 | 10,000 | $0.60 |
| 7 | agent-architect + architect | 10,000 | 8,000 | $0.45 |
| 8 | agent-architect + architect | 15,000 | 10,000 | $0.60 |
| 9 | agent-architect + architect | 15,000 | 10,000 | $0.60 |
| 10 | agent-architect + architect | 15,000 | 10,000 | $0.60 |
| 11 | technical_writer | 20,000 | 5,000 | $0.30 |
| 12 | agent-architect + product_manager | 30,000 | 15,000 | $1.20 |
| **Total** | | **295,500** | **115,000** | **~$7.86** |

*Cost estimate uses Pro agent rates (~$0.01/1K input, ~$0.04/1K output) with 1.5× retry multiplier. Actual costs may vary.

---

## 9. Approval Gate

**Approve this implementation plan before execution begins?**

1. **Approve plan** — Proceed to session creation and execution
2. **Revise plan** — Need changes before execution
3. **Abort execution** — Stop orchestration

---

**Document Status**: Pending Approval

**Next Step**: User approval → Session creation → Execution Mode Gate → Phase 1 delegation
