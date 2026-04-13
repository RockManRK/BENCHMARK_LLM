---
type: status
audience: both
last-validated: 2026-04-11
status: active
---

# Known Issues and Technical Debt

**Purpose:** Bugs, technical debt, and design limitations  
**Scope:** Items requiring attention

---

## Bugs

### 🔴 No Critical Bugs Currently Known

If you encounter a bug, please add it to this document with:
- Description
- Reproduction steps
- Impact assessment
- Suggested fix

---

## Technical Debt

### ⚠️ Review UI Limitations

**Severity:** Medium  
**Impact:** Review UX could be significantly improved  
**Description:**
- Review UI is currently single-language only
- No batch classification (one at a time only)
- Single-level undo (no history)
- No progress persistence across sessions (quit and resume loses position)

**Suggested Fix:** Refactor review UI with:
- Language selection (PT/EN)
- Batch mode for multiple items
- Undo history stack
- Session state persistence

**Effort:** Medium  
**Dependencies:** Review UI refactor

---

### ⚠️ Export Format Limitations

**Severity:** Low  
**Impact:** Analysis requires JSON parsing; no spreadsheet-friendly format  
**Description:**
- Export currently JSON-only
- No CSV export for spreadsheet analysis
- No customizable export schema

**Suggested Fix:** Add CSV export service with configurable columns

**Effort:** Small  
**Dependencies:** Export service extension

---

### ⚠️ Documentation Drift Risk

**Severity:** Medium  
**Impact:** Documentation may become outdated as code evolves  
**Description:**
- Documentation was comprehensively restructured (this document set)
- Without disciplined updates, docs will drift from code
- No automated validation that docs match implementation

**Suggested Fix:**
- Establish documentation update protocol
- Schedule periodic audits (quarterly recommended)
- Consider automated validation tooling (future enhancement)

**Effort:** Ongoing  
**Dependencies:** Process discipline

---

### ⚠️ Logging Context Consistency

**Severity:** Low  
**Impact:** Log analysis may require parsing multiple formats  
**Description:**
- Logging includes experiment/run/model/question context
- Context format varies across modules
- No structured logging schema (e.g., JSON logs)

**Suggested Fix:** Standardize log context format across all modules

**Effort:** Medium  
**Dependencies:** Logging refactor

---

## Design Limitations

### ℹ️ Sequential-by-Default Execution

**Impact:** Large experiments may take hours  
**Description:**
- Default concurrency is 1 (sequential)
- Parallel execution is supported but requires explicit configuration
- Users may not realize parallelism is available

**Mitigation:** Document parallel configuration in user guide  
**Future:** Consider sensible default concurrency

---

### ℹ️ SQLite Limitations

**Impact:** Single-user, local-only storage  
**Description:**
- SQLite is single-writer by design
- No concurrent multi-user access
- No remote access without file sharing

**Rationale:** System is designed as single-user research tool  
**Future:** If multi-user needed, consider database migration (major change)

---

### ℹ️ No Built-In Analytics

**Impact:** Analysis requires external tools  
**Description:**
- System collects data but doesn't analyze it
- No built-in charts, statistics, or comparisons
- Export enables downstream analysis

**Rationale:** Data collection is the core responsibility; analysis is downstream  
**Future:** Analytics may be added as separate module or external tooling

---

## Resolved Issues

### ✅ Parallel Execution Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** AsyncOrchestrator with semaphore-based concurrency implemented  
**Impact:** Large experiments can run in parallel with configurable concurrency

### ✅ Retry Safety Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** Centralized retry handler with exponential/linear backoff implemented  
**Impact:** Transient API failures are handled gracefully

### ✅ Logging System Implementation

**Resolved:** 2026-04 (prior to documentation restructure)  
**Description:** Configurable logging with file rotation and crash-safety implemented  
**Impact:** System behavior is observable and debuggable

---

## How to Add New Issues

When you discover a new issue, add it to this document with:

```markdown
### [Severity] Issue Title

**Severity:** Critical | High | Medium | Low  
**Impact:** [What is affected]  
**Description:** [What is wrong]  
**Reproduction:** [How to reproduce, if bug]  
**Suggested Fix:** [What should be done]  
**Effort:** Small | Medium | Large  
**Dependencies:** [What else needs to change]
```

---

## Related Documents

- [status/implementation-status.md](implementation-status.md) — What exists
- [status/roadmap.md](roadmap.md) — Intent and priorities
- [contracts/](../contracts/README.md) — System invariants (issues may violate these)
