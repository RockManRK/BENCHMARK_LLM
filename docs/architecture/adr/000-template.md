---
type: conceptual
audience: both
last-validated: 2026-04-11
status: active
---

# Architecture Decision Records

**Purpose:** Record architectural decisions, their context, and consequences  
**Format:** One decision per file; short, explicit, decision-focused

---

## What Is an ADR?

An Architecture Decision Record (ADR) captures:
- **What** was decided
- **Why** it was decided
- **What alternatives** were considered
- **What consequences** the decision has

ADRs are the **only mechanism** that can override a system contract.

---

## When to Create an ADR

Create an ADR when:
- ✅ A system contract needs to change
- ✅ A significant architectural trade-off is made
- ✅ A design principle is bent (not broken)
- ✅ A decision has lasting consequences
- ✅ Future developers need to understand "why"

Do NOT create an ADR for:
- ❌ Bug fixes
- ❌ Refactoring without behavioral change
- ❌ Implementation details
- ❌ Temporary workarounds (document in code comments)

---

## ADR Format

```markdown
---
type: adr
audience: both
date: YYYY-MM-DD
status: accepted | deprecated | superseded
superseded-by: [ADR number if applicable]
---

# ADR-NNN: Short Title

**Status:** [accepted | deprecated | superseded by ADR-NNN]  
**Date:** YYYY-MM-DD  
**Context:** [Brief description of the situation]

## Decision

[What was decided. One clear paragraph.]

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| [Option A] | [Reason] |
| [Option B] | [Reason] |

## Consequences

### Positive
- [What improves]

### Negative
- [What gets worse]
- [What constraints are introduced]

## Contracts Affected

[List any contracts this ADR modifies or supersedes]

## Related Documents

[Links to related architecture, reference, or status docs]
```

---

## ADR Numbering

ADRs are numbered sequentially: `ADR-001`, `ADR-002`, etc.

The number appears in:
- Filename: `001-decision-title.md`
- Document title: `# ADR-001: Decision Title`
- Cross-references: "superseded by ADR-002"

---

## ADR Lifecycle

1. **Proposed** — Decision is being considered
2. **Accepted** — Decision is active and guides development
3. **Deprecated** — Decision is still valid but no longer preferred
4. **Superseded** — Decision is replaced by a newer ADR

---

## Example ADR

```markdown
---
type: adr
audience: both
date: 2026-04-11
status: accepted
---

# ADR-001: Execution Order Not Guaranteed

**Status:** Accepted  
**Date:** 2026-04-11  
**Context:** System supports parallel execution; completion order varies.

## Decision

Execution order is not guaranteed when parallel execution is enabled.
Determinism applies to generated content (request payloads, option shuffling),
not temporal execution order.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Enforce sequential execution | Loses performance benefit of parallelism |
| Sort results by completion | Adds complexity; unnecessary for determinism |

## Consequences

### Positive
- Parallel execution improves wall-clock time for large experiments
- Simpler implementation (no ordering guarantees needed)

### Negative
- Results may complete in different order across runs
- Users cannot assume result order matches plan order

## Contracts Affected

- [contracts/determinism.md](../contracts/determinism.md) — Updated to clarify that determinism applies to content, not temporal order

## Related Documents

- [architecture/execution-architecture.md](execution-architecture.md) — Parallel execution section
```

---

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| *(none yet)* | | | |

---

## Related Documents

- [contracts/](../contracts/README.md) — System invariants (ADRs can override these)
- [design-principles.md](design-principles.md) — Philosophy and trade-offs
- [overview.md](overview.md) — System at a glance
