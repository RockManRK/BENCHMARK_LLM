---
type: status
audience: both
last-validated: 2026-04-11
status: active
---

# Roadmap and Priorities

**Purpose:** Intent and priorities for future work  
**Scope:** Near-term and future directions  
**⚠️ WARNING:** This document represents **intent, not commitment**. Priorities may change based on user needs, technical constraints, or resource availability.

---

## How to Read This Document

This roadmap is **non-normative**: it describes what the system's maintainers intend to build, but does not guarantee delivery or timeline.

**AI agents must not treat this document as constraints or promises.**

---

## Near-Term Priorities (Next 1-3 Months)

### 🔴 URGENT Priority

#### 1. Provider Selection Control

**What:** Ability to explicitly select OpenRouter provider per experiment and/or run  
**Why:** OpenRouter may route requests to different providers automatically; provider variability introduces unwanted experimental noise; provider selection must be controllable  
**Dependencies:** API client extension, experiment/run config extension  
**Effort:** Medium  
**Status:** 📝 Planned
**Ref**: "https://openrouter.ai/docs/sdks/typescript/api-reference/providers"

**Breakdown:**
- [ ] Add provider selection to experiment configuration
- [ ] Add provider override at run level
- [ ] Ensure provider is passed in API requests
- [ ] Document provider selection behavior

---

### 🟡 High Priority

#### 2. Review UI Enhancements

**What:** Multi-language (PT/EN), multi-level undo, session persistence  
**Why:** Review is a major user workflow; current UX is limiting productivity; currently blocked by routing issues  
**Dependencies:** MODE × MODULE routing fix, Review UI refactor  
**Effort:** Medium  
**Status:** 📝 Planned

**Breakdown:**
- [ ] Fix MODE × MODULE routing issues (blocker)
- [ ] Language selection (PT/EN)
- [ ] Multi-level undo history
- [ ] Session state persistence (resume where you left off)

---

#### 3. CLI Improvement via Typer and/or Click

**What:** Modern CLI framework integration  
**Why:** Current argparse-based CLI is limiting; Typer/Click would improve UX, help text, and command discovery  
**Dependencies:** CLI refactor  
**Effort:** Medium  
**Status:** 📝 Planned

**Breakdown:**
- [ ] Evaluate Typer vs Click
- [ ] Migrate command structure
- [ ] Improve help text and error messages
- [ ] Maintain backward compatibility

---

#### 4. OpenRouter Metadata Support

**What:** Pass experiment/run context in API request headers  
**Why:** Better API-side tracking and debugging  
**Dependencies:** API client extension  
**Effort:** Small  
**Status:** 📝 Planned
**Ref:** "https://openrouter.ai/docs/guides/features/broadcast/overview#optional-trace-data"

**Breakdown:**
- [ ] session_id per experiment/run
- [ ] http_referer header
- [ ] x_open_router_title header

---

### 🟢 Medium Priority

#### 5. Export Validation and Redesign

**What:** Validate and redesign export service  
**Why:** Export is critical and sensitive; current implementation requires validation before being relied upon  
**Dependencies:** Export service audit  
**Effort:** Medium  
**Status:** 📝 Planned

**Breakdown:**
- [ ] Audit current export implementation
- [ ] Validate computed fields correctness
- [ ] Redesign if needed
- [ ] Add CSV export

---

#### 6. Experiment List/Remove Implementation

**What:** Implement `--list-experiments` and `--remove-experiment` commands  
**Why:** Currently not implemented; basic experiment management gap  
**Dependencies:** CLI extension  
**Effort:** Small  
**Status:** 📝 Planned

---

#### 7. Experiment Modification (Seed/Prompts)

**What:** Allow changing seed, system prompt, user prompt on existing experiments  
**Why:** Currently not implemented; limits experiment flexibility  
**Dependencies:** Config resolution update  
**Effort:** Small  
**Status:** 📝 Planned

---

### 🔵 Research / Investigation

#### 8. OpenRouter Multi-Model Request

**What:** Study OpenRouter "models" parameter (multi-model request)  
**Why:** Evaluate advantages, disadvantages, and feasibility for benchmarking  
**Dependencies:** Research only  
**Effort:** Small (research)  
**Status:** 📝 Research

**Breakdown:**
- [ ] Research OpenRouter multi-model API
- [ ] Evaluate impact on determinism
- [ ] Assess feasibility for benchmark system

---

#### 9. Research-Enabled Runs (Internet Access)

**What:** Optional internet access for models  
**Why:** Some research scenarios may require web-enabled models  
**Dependencies:** API client extension  
**Effort:** Small  
**Status:** 📝 Research

---

### 🟣 Quality of Life

#### 10. Improved UI (Execution Visibility, Review, Results)

**What:** Better visibility into execution progress, review status, and results  
**Why:** Current UI is minimal; users need better feedback  
**Dependencies:** UI enhancement  
**Effort:** Medium  
**Status:** 📝 Planned

---

#### 11. Post-Run Statistics

**What:** Automatic statistics after run completion  
**Why:** Users need quick insights without external analysis  
**Dependencies:** Statistics module  
**Effort:** Medium  
**Status:** 📝 Planned

**Breakdown:**
- [ ] Correct vs incorrect answers
- [ ] Percentages per model and per run
- [ ] Aggregated summaries

---

## Future Directions (1-2 Months)

### Analytics and Visualization

**What:** Built-in analytics and charting  
**Why:** Users may want quick insights without external tools  
**Dependencies:** Data analysis module  
**Effort:** Large  
**Status:** 💭 Idea

**Considerations:**
- Keep separate from core data collection
- Export-first approach still applies
- May be external module or plugin

---

### Advanced Experiment Controls

**What:** More sophisticated experiment configuration  
**Why:** Research may require complex experiment designs  
**Dependencies:** Architecture review  
**Effort:** Medium  
**Status:** 💭 Idea

**Considerations:**
- Maintain configuration freezing
- Maintain reproducibility
- May require ADR for significant changes

---

### Multi-User Support

**What:** Concurrent user access  
**Why:** Collaboration scenarios  
**Dependencies:** Major architectural change (database migration)  
**Effort:** Large  
**Status:** 💭 Idea

**Considerations:**
- Current design is single-user
- Would require database migration from SQLite
- Major change requiring ADR

---

## Not Planned (Explicitly Out of Scope)

| Capability | Rationale |
|------------|-----------|
| Real-time model serving | System is batch-oriented |
| Model training/fine-tuning | Evaluates existing models only |
| Automated research insights | Analysis is downstream |
| Built-in visual dashboards | Export enables external visualization |
| Cloud-native deployment | Local execution with SQLite |
| Automatic experiment design | Human controls research intent |

---

## Completed Capabilities (Recent)

These capabilities were recently implemented:

| Capability | Completed | Notes |
|------------|-----------|-------|
| Parallel execution | 2026-04 | AsyncOrchestrator with semaphore |
| Retry safety | 2026-04 | Centralized retry with backoff |
| Logging system | 2026-04 | Configurable with rotation |
| Answer parsing | 2026-04 | Multiple patterns recognized |
| Answer randomization | 2026-04 | Fisher-Yates with seed control |
| Export service | 2026-04 | JSON with computed fields |
| Configuration hierarchy | 2026-04 | System → .env → Experiment → Run/Model |
| Database layer | 2026-04 | 6 tables, constraints, indexes |

---

## How to Update This Document

When priorities change:

1. **Move items** between priority levels
2. **Add new items** with clear description and effort estimate
3. **Mark completed items** in "Completed Capabilities" section
4. **Update `last-validated` date** in frontmatter

**Remember:** This document is intent, not promise. It's okay to change direction.

---

## Related Documents

- [status/implementation-status.md](implementation-status.md) — What exists
- [status/known-issues.md](known-issues.md) — What needs attention
- [contracts/](../contracts/README.md) — System invariants (roadmap must respect these)
- [architecture/design-principles.md](../architecture/design-principles.md) — Philosophy and trade-offs
