---
type: adr
audience: both
date: 2026-08-19
status: accepted
---

# ADR-003: Pre-Production Local Data Has No Compatibility Guarantee — Contracts Still Apply

**Status:** Accepted
**Date:** 2026-08-19
**Context:** The system is still under active development and has never been used to run a real research experiment. During Fase 3 of the CLI Typer migration, a bug fix changed the shape of newly-written `question_snapshots.question_payload` JSON (see `docs/status/known-issues.md`, "Composite-path question snapshots had a double-wrapped `meta` field"). An Essence Guardian review correctly asked whether any already-persisted local rows could be silently affected by the pre-fix shape, and whether a detection/remediation mechanism was needed. This is the single, official answer to that class of question — future findings of the same shape should reference this ADR rather than re-litigating it.

## Decision

While the system remains pre-production (no real scientific experiment has been run through it), **compatibility with existing local database content is not a requirement**. A bug fix that changes how new rows are written is not obligated to provide migration tooling, a detection script, or a backward-compatible reader for old-shaped rows just because such rows already exist locally — every row in `data/bcllm.db` today is test/development data, not a research record.

**This decision does not relax any system contract.** It narrows one specific, practical question — "must past local data be made compatible with a code fix?" — for the pre-production window only. Everything else stays fully in force, unconditionally:
- **Immutability** (`docs/contracts/immutability.md`): already-persisted rows are still never migrated or rewritten in place — this ADR does not create a new exception, it explains why the *absence* of a migration for the fix above was correct, not merely tolerated.
- **Data auditability** (`docs/contracts/data-auditability.md`): a code fix that changes historical behavior is still fully documented (root cause, fix, regression coverage) in `docs/status/known-issues.md`, exactly as it would be without this ADR.
- **Isolation** (test/diagnostic discipline — see `CLAUDE.md`): tests and diagnostics must still never touch the real `.env` or `data/bcllm.db`. That rule protects against accidental pollution during test runs and is unrelated to whether the data currently in the database is valuable — it applies exactly the same before and after this ADR.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Treat all local historical data as production-critical from day one | Manufactures migration/detection work for data that isn't real, adding overhead with no corresponding risk reduction during active pre-production development |
| Say nothing, leave each future finding to be argued fresh | Already happened once (this ADR's own trigger) — costs review cycles re-deriving the same conclusion each time a data-shape bug fix is reviewed |

## Consequences

### Positive
- Bug fixes that change data shape don't need migration/detection tooling while pre-production, reducing unnecessary scope on genuinely non-actionable findings.
- Future reviewers (human or Essence Guardian) have one place to check before flagging this class of finding as open.

### Negative
- Requires remembering to retire this ADR before the system's first real experiment — see Expiration below. If forgotten, it could mask a genuine future data-integrity concern.

## Expiration

**This decision expires automatically before the first real scientific experiment is run through the system.** From that point on, database content is real research data, and the normal expectation applies in full: a code fix that changes historical behavior must be assessed for its effect on existing real rows, same as any other production data-integrity concern. When that point is reached, this ADR must be marked `deprecated` (or superseded by a successor ADR), not left `accepted` by default.

## Contracts Affected

None overridden. `docs/contracts/immutability.md` and `docs/contracts/data-auditability.md` remain fully binding on system behavior — see Decision above for why this ADR narrows a practical question about past data, not any contract text.

## Related Documents

- [contracts/immutability.md](../../contracts/immutability.md)
- [contracts/data-auditability.md](../../contracts/data-auditability.md)
- [status/known-issues.md](../../status/known-issues.md) — "Composite-path question snapshots had a double-wrapped `meta` field" (the finding that triggered this ADR)
- [essence-guardian-log/guardian_memory.md](../../essence-guardian-log/guardian_memory.md) — entry [14]
- `CLAUDE.md` — "Repository hygiene notes"
