---
type: adr
audience: both
date: 2026-08-22
status: accepted
---

# ADR-004: Computed Results Must Remain Traceable Even When Persistence Fails

**Status:** Accepted — approved 2026-08-22, implemented as ASY-01
**Date:** 2026-08-22
**Context:** A deep audit of commit `922603c` (finding ASY-01, `docs/status/auditoria-profunda-922603c.md`) found that when `AsyncWriter` exhausts its retries and aborts, items still sitting in the shared queue — real, already-computed, potentially API-billed `ExecutionResult`s — are never drained, never persisted, and never logged as lost. `RunFinalizer` then computes `runs.status` purely from `COUNT(*)` over `responses`/`errors`, with no visibility into the abort, and can report `completed` with zero rows in either table. Live reproduction (isolated in-memory DB, real `AsyncWriter`/`RunFinalizer`, no mocks of the write path) confirmed exactly this: `{'status': 'completed', 'duration_ms': 0, 'response_count': 0}` after two real computed results — one whose write failed permanently, one abandoned in the queue — vanished without a trace. This ADR defines the criteria that must hold before that code is touched.

**Governing principle:**

> Uma resposta já recebida de um provedor externo e potencialmente cobrada jamais pode desaparecer sem rastreabilidade.

---

## Decision

### 1. When is a result considered to exist?

A result exists, for auditability purposes, from the moment `ExecutionEngine` produces an `ExecutionResult` — not from the moment it lands in `responses`. The system currently has only one, informal name for this: "received." It is a real, distinct state from "persisted," and the codebase must stop implicitly treating them as the same thing (which is exactly what `RunFinalizer`'s DB-only view does today). Between being received and being persisted, a result's only representation is the in-memory `asyncio.Queue` — which is not durable, not visible to any other component, and today can be silently abandoned with no consequence anywhere else in the system.

### 2. What data must survive a persistence failure?

Not the full `raw_response` content durably in the database — if the database write path is what is failing, that is often not achievable, and this ADR does not pretend otherwise. What must survive, at minimum, for every received-but-unpersisted item:

- Its identity: `run_id`, `variant_id`, `snapshot_id`, `question_id`.
- The fact that a result was received and could not be durably persisted, and why (the underlying exception).
- Enough forensic content (status, cost/tokens if known, a bounded excerpt of `response_text`) to support manual reconciliation against provider-side billing records if ever needed.

The full verbatim response is not guaranteed to survive when the database itself is the failing component. This is consistent with `docs/contracts/data-auditability.md` §4c's existing three-way separation (DB / logs / upstream echo, none a substitute for another) — extended here to the one case that contract section does not yet cover: an item for which no DB row is possible at all.

### 3. Relationship between a received result and a persisted result

A received result becomes persisted only via a successful `ResultWriter.write_result()` call. Until then it is "received, not yet persisted" — and the system must be able to represent that state explicitly, not silently, in two places:
- **A durable, queryable trace of the attempt** (see Decision 6) — not just a log line, because logs alone are diagnostic evidence, never the record of truth (`data-auditability.md` §4c) — an unpersisted item having *only* a log trace is already the second-choice fallback, not the first.
- **The Run's own terminal status** (see Decisions 4–5) — must never claim more certainty than the database actually contains.

### 4. Criteria for `completed`

`completed` may be reported **only when every item received during that Run's execution has a corresponding, correctly-typed row in `responses` or `errors`** — i.e., nothing was received and then silently dropped. Today's rule (`error_count == 0`) stays necessary but is not sufficient by itself, because it can't see items that were never given a row at all. This ADR closes that gap **without adding a new signal to check** — see Decision 6: once every received item is guaranteed a row (success or error), `error_count == 0` becomes trustworthy again by construction, and `RunFinalizer`'s existing counting logic needs no change.

### 5. Criteria for `partial_failed` (and `failed`)

`partial_failed`'s existing meaning — some items have real `responses` rows, some have real `errors` rows — is unchanged and must stay unchanged; existing tests and the existing mental model both depend on it. A write-failure or an abandoned-in-queue item is not a new, third kind of outcome requiring a new status value: it **is** a failure, in the same sense any other unrecoverable item-level failure is — the response was computed but the system could not stand behind it as durably recorded, so it must be treated exactly like a research-integrity failure and re-attempted, not treated as a success. It gets an `errors` row (see Decision 6) with a distinct `error_type` identifying *why* it's an error (persistence failure vs. abandonment vs. a genuine API error) — the run's status then falls out of the **existing, unmodified** `_determine_status` counting rule: `partial_failed` if something else in the run genuinely succeeded, `failed` if nothing did. **No new `runs.status` value, no schema `CHECK` constraint change, no `RunFinalizer` signature change.**

### 6. How to treat items that were computed but never persisted

Every such item — the one that triggered the abort, and every one drained from the queue afterward — gets a best-effort `errors` row via the existing `ResultWriter._write_error()` path (it already only reads `error_type`/`error_message`/`attempt_count`, not `status`, so it applies unmodified to an originally-`status='success'` result whose *persistence* failed). Distinct `error_type` values (e.g. `write_failure` for the triggering item, `abandoned_after_writer_abort` for drained items) preserve the difference between "the write itself failed" and "this was never even attempted after a sibling's write failed," without inventing new tables or columns. If even this best-effort write fails (total database unavailability), the CRITICAL log event is the last-resort record — explicitly a fallback, not the primary mechanism, per Decision 2.

This preserves the already-decided fail-fast contract exactly: `AsyncWriter` still stops consuming new queue items the moment persistence is confirmed broken. Writing one small, already-existing-shaped `errors` row per abandoned item during the abort/drain sequence is a bounded, one-time audit action — not a resumption of normal processing, not a retry of the original write, not "per-item resilience" (which was explicitly rejected earlier in this project's history — see `docs/status/known-issues.md`'s AsyncWriter fail-fast entry).

### 7. Re-execution behavior

Falls out for free from two already-existing, already-tested mechanisms, given Decisions 5–6:
- `Planner._get_executed_items()` already excludes an item only when `responses.raw_response IS NOT NULL`. An item with only an `errors` row (no `responses` row) is already correctly treated as "not yet executed" — no Planner change needed.
- `Planner._get_runs()`'s bare `--execute` already includes any run with status `pending`/`failed`/`partial_failed`. Since Decision 5 guarantees the run's status is never `completed` when something was lost, the run automatically becomes eligible for a future bare `--execute` again — no change to run selection needed either.

---

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Thread a `writer_aborted` flag into `RunFinalizer.finalize_run()` and have it override the computed status | Works, but adds a second source of truth (a passed-in flag) alongside the DB-state-driven counting `RunFinalizer` was explicitly designed around ("Status is determined from counts... single owner"). The `errors`-row approach (Decision 6) makes the existing counting honest instead, needing no new parameter. |
| Introduce a new `runs.status` value (e.g. `aborted`) distinct from `partial_failed` | Real semantic clarity gain, but costs a schema `CHECK` change and touches every piece of code that enumerates status values (CLI display, `_get_runs()`'s `IN (...)` list, docs). Not justified once Decision 6 makes `partial_failed`/`failed` already correctly reachable — the *reason* for the failure is preserved at the `errors.error_type` level instead, which is exactly the granularity that column already exists for. |
| Retry the abandoned item's persistence during drain, instead of just recording it as an error | Directly reopens the "per-item resilience instead of fail-fast" question this project already settled against (same normative decision the G8 AsyncWriter checkpoint locked in). If the DB is genuinely unavailable, attempting more writes during drain risks hanging or hiding a second failure behind the first. |
| Re-enqueue abandoned items for automatic retry within the same process | The underlying failure is a database availability problem — retrying more writes in the same broken environment doesn't help, and it's not this component's job to implement its own backoff-forever loop. Re-execution via a later, separate invocation (Decision 7) already provides the real recovery path once the underlying issue is fixed. |
| Do nothing; document the gap as accepted debt | Directly contradicts the governing principle and the audit's own severity rating (Alta/Imediata) — a `completed` run with zero evidence anything happened is a silent, maximally deceptive false positive, not a tolerable edge case. |

---

## Consequences

### Positive
- Closes the exact failure mode the audit found: a `completed` run can no longer report success while a computed, possibly-billed result was silently dropped.
- Zero schema changes, zero new `runs.status` values, zero `RunFinalizer` signature changes — the fix works entirely by making an already-existing counting rule see data it was blind to before.
- Re-execution recovery is automatic (Decision 7) — no operator action needed beyond re-running `--execute` once the underlying issue is resolved.
- Reuses `ResultWriter._write_error()` unmodified — no new write path to test/maintain.

### Negative
- Adds one (best-effort, already-shaped) DB write per abandoned/failed-to-persist item during an already-rare abort path — negligible overhead, but it is new code on a path that must itself never throw uncaught.
- `errors.error_type` gains 1–2 new literal values (e.g. `write_failure`, `abandoned_after_writer_abort`) that downstream consumers (Review UI, export, any future dashboard) should be prepared to see and label distinctly from a genuine API error — not a breaking change, but a discoverability note for whoever builds that surface next.
- If the `errors`-row write itself also fails (total DB unavailability), the system falls back to log-only traceability for that item — an accepted, explicitly-stated limit (Decision 2), not a silent gap.

## Contracts Affected

None overridden. This ADR is additive clarification, not an exception:
- [contracts/idempotency.md](../../contracts/idempotency.md) — "Logging Never Affects Idempotency" stays exactly as-is: the `errors` row, not the log line, is what makes re-execution correctly retry an abandoned item (Decision 7) — the log is forensic only, never a resume/retry signal.
- [contracts/data-auditability.md](../../contracts/data-auditability.md) §4c — extended (not changed) to cover the one case it didn't yet address: an item for which no `responses` row is possible at all. The three-way separation (DB / logs / upstream echo) gains a documented degenerate case (DB has only an `errors` row, or in the worst case none at all) rather than silence.

## Related Documents

- [status/auditoria-profunda-922603c.md](../../status/auditoria-profunda-922603c.md) — ASY-01, the finding that triggered this ADR.
- [status/known-issues.md](../../status/known-issues.md) — the AsyncWriter fail-fast normative decision (G8 checkpoint) this ADR's Decision 6 is deliberately consistent with.
- `src/core/async_writer.py`, `src/core/async_orchestrator.py`, `src/core/run_finalizer.py`, `src/core/planner.py::_get_executed_items`/`_get_runs` — implementation surfaces once this ADR is accepted.
