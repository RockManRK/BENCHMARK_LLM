---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# Interaction Contracts

**Scope:** Event emission, rendering boundaries, UI behavior  
**Status:** 📝 Placeholder — Invariants to be defined

---

## Contract Statement

This document will define the invariants for:
- Event emission boundaries (what components emit what events)
- Rendering boundaries (what components are responsible for what UI)
- UI behavior guarantees (consistency, state management)

---

## Current State

**TODO:** This contract is a placeholder. The following areas need invariant definition:

### 1. Review UI Boundaries

- What is the Review UI responsible for?
- What does it delegate to other components?
- What are the UI state invariants? (e.g., undo history, batch classification)
- How does it interact with the database? (read-only? write review fields?)

### 2. CLI Output Boundaries

- What output format does CLI guarantee?
- What progress information is provided?
- What error reporting behavior is guaranteed?

### 3. Event Emission

- What events are emitted during execution?
- What is the event schema?
- What components subscribe to what events?

### 4. Logging Boundaries

- What components are responsible for logging?
- What log levels are used when?
- What information is included in logs?

---

## Known Constraints (from existing code)

From reviewing `src/review/review_ui.py` and related code:

1. **Review UI reads from database** — Loads pending responses for review
2. **Review UI writes review fields** — Updates `manual_answer`, `review_status`, `reviewed_at`
3. **Review UI supports undo** — Can revert last classification
4. **Review UI supports batch operations** — Can classify multiple items at once
5. **Review UI is terminal-based** — Uses Rich library for TUI
6. **Review UI does not modify original data** — Only adds review annotations

---

## Next Steps

1. Review existing review UI implementation
2. Define explicit invariants for each area above
3. Document UI state management rules
4. Define event emission schema (if event system exists)
5. Establish logging boundaries per component

---

**This contract is a placeholder and MUST be completed before UI-related work begins.**
