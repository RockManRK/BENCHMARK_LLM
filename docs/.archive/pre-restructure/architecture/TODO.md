# Architecture Documentation Program — Master ToDo

**Created**: 2026-03-29  
**Status**: In Progress  
**Session**: `arch-doc-program-2026-03-29`

---

## Task Description

Create comprehensive architecture documentation for Benchmark LLM, a platform for benchmarking LLMs through questions. The system has two codebases:

- **V1 (Legacy)**: `src_legacy/` — Complete but poorly architected code
- **V2 (Current)**: `src/` — Well-planned but incomplete implementation

This documentation program will analyze both versions, identify gaps, and produce a complete architecture reference that respects V2 contracts while learning from V1's implemented behavior.

---

## Objectives

This documentation program must achieve the following 7 functional requirements:

1. **Document V1 Legacy Architecture** — Capture the as-built architecture of the legacy system, including all components, data flows, and behaviors
2. **Document V2 Current Architecture** — Capture the as-planned architecture of the current implementation, including contracts and intended behavior
3. **Identify Gaps** — Produce a gap report showing what V2 is missing compared to V1's functionality
4. **Define Adaptation Strategy** — Create a V2 adaptation plan that incorporates necessary V1 learnings without violating V2's architectural contracts
5. **Establish Domain Boundaries** — Define clear domain boundaries for all system components
6. **Create Reference Documentation** — Produce developer-facing reference docs for each domain
7. **Maintain Audit Trail** — Ensure all architectural decisions are traceable and auditable

---

## Rules

The following rules govern this documentation program:

| Rule | Description |
|------|-------------|
| **V1 Code Not Copied** | V1 code is analyzed for understanding only — no direct copying into V2 |
| **V2 Contracts Respected** | V2 architectural contracts are the source of truth — adaptations must not violate them |
| **Contradictions Flagged** | Any contradiction between V1 behavior and V2 contracts must be explicitly flagged for resolution |
| **No Speculation** | Documentation describes only what exists in code or is explicitly planned — no speculative features |
| **Single Source of Truth** | This TODO.md is the master tracking document — all progress is recorded here |

---

## Implementation Plan — 12 Phases

### Phase 1: Setup & ToDo Creation
- [ ] Create `docs/architecture/TODO.md` (this document)
- [ ] Create directory structure for documentation
- [ ] Establish baseline folder organization

### Phase 2: V1 Legacy Analysis — Execution Core
- [ ] Analyze `src_legacy/` execution flow
- [ ] Document legacy execution core architecture
- [ ] Identify execution patterns and behaviors

### Phase 3: V1 Legacy Analysis — Logging System
- [ ] Analyze legacy logging implementation
- [ ] Document logging architecture and flows
- [ ] Identify logging gaps and issues

### Phase 4: V1 Legacy Analysis — CLI System
- [ ] Analyze legacy CLI command structure
- [ ] Document CLI architecture and command flows
- [ ] Identify CLI patterns and user interactions

### Phase 5: V1 Legacy Analysis — Review UI
- [ ] Analyze legacy review UI implementation
- [ ] Document review UI architecture
- [ ] Identify review workflow patterns

### Phase 6: V1 Legacy Analysis — Database Layer
- [ ] Analyze legacy database schema and queries
- [ ] Document database architecture
- [ ] Identify data model patterns

### Phase 7: V1 Legacy Analysis — Configuration System
- [ ] Analyze legacy configuration handling
- [ ] Document configuration architecture
- [ ] Identify configuration patterns and issues

### Phase 8: V1 Legacy Analysis — Error Handling
- [ ] Analyze legacy error handling patterns
- [ ] Document error handling architecture
- [ ] Identify error handling gaps

### Phase 9: V1 Legacy Analysis — Answer Parsing
- [ ] Analyze legacy answer parsing logic
- [ ] Document parsing architecture
- [ ] Identify parsing patterns and edge cases

### Phase 10: V2 Current Architecture Documentation
- [ ] Document V2 Execution Core from `src/`
- [ ] Document V2 contracts and intended behavior
- [ ] Map V2 component architecture

### Phase 11: Gap Analysis Report
- [ ] Compare V1 functionality vs V2 plans
- [ ] Produce gap report with missing features
- [ ] Prioritize gaps by criticality

### Phase 12: V2 Adaptation Strategy
- [ ] Define adaptation approach for each gap
- [ ] Document adaptation decisions and rationale
- [ ] Create final architecture reference

---

## Domain List

### Initial Domains (8)

The following 8 domains define the initial scope of analysis:

| # | Domain | Description |
|---|--------|-------------|
| 1 | **Execution Core** | Core execution engine, run orchestration, model invocation |
| 2 | **Logging System** | Application logging, audit trails, debug output |
| 3 | **CLI System** | Command-line interface, command parsing, user interaction |
| 4 | **Review UI** | Review interface, manual answer correction workflow |
| 5 | **Database Layer** | Schema, queries, data access patterns |
| 6 | **Configuration System** | Environment variables, config resolution, defaults |
| 7 | **Error Handling** | Exception handling, error propagation, recovery |
| 8 | **Answer Parsing** | Response parsing, answer extraction, confidence scoring |

### Domain Expansion Rule

> **If V1 analysis reveals additional domains not listed above, they will be added to this list.**  
> New domains will be documented with: name, description, rationale for addition, and affected phases.

---

## Directory Structure

```
docs/architecture/
├── TODO.md                          # This file — master tracking document
├── legacy-analysis/                 # V1 legacy architecture documentation
│   ├── execution-core.md
│   ├── logging-system.md
│   ├── cli-system.md
│   ├── review-ui.md
│   ├── database-layer.md
│   ├── configuration-system.md
│   ├── error-handling.md
│   └── answer-parsing.md
├── v2-current/                      # V2 current architecture documentation
│   ├── execution-core.md
│   ├── contracts/
│   └── architecture-overview.md
├── gap-reports/                     # Gap analysis between V1 and V2
│   └── gap-analysis.md
├── v2-adaptation/                   # V2 adaptation strategy and decisions
│   └── adaptation-strategy.md
└── contracts/                       # Existing contract documents (already present)
    └── [existing contracts]
```

---

## Progress Tracking

### Overall Status

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1. Setup & ToDo Creation | 🟡 In Progress | 2026-03-29 | — | Creating base structure |
| 2. V1 — Execution Core | ⚪ Pending | — | — | — |
| 3. V1 — Logging System | ⚪ Pending | — | — | — |
| 4. V1 — CLI System | ⚪ Pending | — | — | — |
| 5. V1 — Review UI | ⚪ Pending | — | — | — |
| 6. V1 — Database Layer | ⚪ Pending | — | — | — |
| 7. V1 — Configuration System | ⚪ Pending | — | — | — |
| 8. V1 — Error Handling | ⚪ Pending | — | — | — |
| 9. V1 — Answer Parsing | ⚪ Pending | — | — | — |
| 10. V2 Current Architecture | ⚪ Pending | — | — | — |
| 11. Gap Analysis Report | ⚪ Pending | — | — | — |
| 12. V2 Adaptation Strategy | ⚪ Pending | — | — | — |

### Legend

- 🟢 Completed
- 🟡 In Progress
- ⚪ Pending
- 🔴 Blocked

---

## Notes

- This document is the **single source of truth** for the Architecture Documentation Program
- All phase completions must be recorded in the Progress Tracking section
- New domains discovered during V1 analysis will be added to the Domain List
- Contradictions between V1 and V2 will be flagged with context and resolution status

---

**Source**: `docs/architecture/TODO.md`  
**Maintained by**: Architecture Documentation Program  
**Last Updated**: 2026-03-29
