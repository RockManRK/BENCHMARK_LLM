---
type: status
audience: ai
last-validated: 2026-08-19
status: active
---

# Investigation: composite `--create-experiment` + `--add-*` flow atomicity

**Requested:** 2026-08-19, explicitly separate from and after the "same action, same path" architecture checkpoint (`docs/status/known-issues.md`'s matching Resolved Issues entry). The user asked 4 specific questions before any further work on this area, and explicitly asked that no transactional refactor be implemented before the design and impact are presented. **Nothing described as "not implemented" below has been implemented.** What *was* implemented this pass: new regression tests exercising the existing compensating-rollback mechanism at multiple failure points (including when compensation itself fails), and the `PRAGMA foreign_key_check`/`PRAGMA integrity_check` verification the user asked for. See `tests/unit/cli/test_composite_flow_rollback.py`.

---

## Current mechanism (recap)

`bcllm.py::_handle_composite_flow` runs `--create-experiment` then, on the same shared `sqlite3.Connection`, each requested `--add-*` action in a fixed order (`model -> questions -> run`, per `ADD_ACTION_FLAGS` in `src/core/module_resolver.py`). Each action's own `add_*_action()` (in `bcllm_model.py`/`bcllm_questions.py`/`bcllm_run.py`) calls its repository's `save()`, which does `INSERT ...; self.conn.commit()` — **immediately and durably**, one commit per row, not deferred. If a later action fails, `_rollback_created_experiment` (`bcllm.py`) issues explicit `DELETE FROM question_snapshots|model_variants|runs WHERE experiment_id = ?`, commits, then deletes the `experiments` row itself. This is a **compensating action**, not a database transaction rollback — by the time it runs, every earlier action's writes are already durably committed; there is nothing left for `conn.rollback()` to undo.

---

## 1. Can repositories/actions participate in a future external transaction / Unit of Work?

**Structurally, no — not without changing `src/db/repository.py` itself**, and the reason is a specific SQLite/Python detail, not just "commits happen too often":

A `SAVEPOINT` wrapped *around* the composite flow, left otherwise untouched, would **not** provide real atomicity, because a bare `COMMIT` (which is what `self.conn.commit()` issues) ends the connection's entire current transaction — it does not respect or defer to any open `SAVEPOINT` a caller might have started around it. Every one of the 11 `self.conn.commit()` call sites in `repository.py` (`ExperimentRepository.save/delete`, `VariantRepository.save/delete`, `SnapshotRepository.save/delete`, `RunRepository.save/update_status/delete`, `ResponseRepository.save/update_manual_answer` — confirmed by direct grep) would each independently close out whatever transaction/savepoint scope a hypothetical orchestrator had opened. **A "cheap savepoint wrapper that doesn't touch the repositories" is not a viable design** — this was checked directly, not assumed.

The only way repositories/actions could participate in an externally-controlled transaction is if they **stop calling `self.conn.commit()` unconditionally** and instead defer to whoever owns the transaction boundary. Two shapes for that:

- **(a) Global removal.** Delete every internal `commit()` call; every caller everywhere becomes responsible for committing. Simple to describe, large blast radius (see §2) — and wrong for at least one real caller (`ResponseRepository`, see the boundary note below).
- **(b) Commit-suppression seam.** Repositories keep calling something like `self._commit()` instead of `self.conn.commit()` directly; `self._commit()` is a no-op when the connection is inside an active, explicitly-opened Unit-of-Work scope (tracked via a flag on a thin connection wrapper, or a contextvar), and behaves exactly as today (immediate commit) otherwise. Every existing caller's *observable* behavior is unchanged unless it explicitly opts into a UoW scope. This is the more surgical option — it still touches all 11 call sites (mechanically, and each needs its own regression check), but it does not require touching every *caller* of those repositories, only the repositories' own commit calls.

**Hard boundary this investigation surfaced, not previously written down:** `ResponseRepository`/`src/core/result_writer.py`'s per-write commits (`responses`/`errors`, confirmed at `result_writer.py:270,333`) are **not a candidate for deferral under any design**, including (b) above with a broadly-scoped UoW. `docs/contracts/idempotency.md`'s "Partial executions resume from where they left off" and its `UNIQUE constraint + INSERT OR IGNORE` pattern exist specifically so a crash/kill mid-`--execute` doesn't lose already-completed, real-money API results — deferring those commits to a batch/transaction boundary spanning the whole run would mean a crash loses everything since the last commit, forcing expensive re-execution of already-answered questions. Any future UoW mechanism must be **opt-in per call site**, never a blanket connection-level change, or it will quietly break this guarantee. This is the single most important constraint on any future design here.

---

## 2. Cost and impact of making composite creation a single transactional operation

Scoped **only** to the composite `--create-experiment + --add-*` entity-creation path (never `ResponseRepository`, per §1):

- **Code touched:** all 11 commit call sites in `repository.py` need the commit-suppression seam (design (b) above) — every one is shared, well-exercised code used by standalone `--add-*`, `--remove-*`, `--provider-lock`, and the Review UI's `update_manual_answer`, not just the composite flow. Each needs its own regression test proving standalone behavior is byte-identical to today (immediate commit, same as now, since nothing outside a UoW scope changes).
- **New code:** a UoW/transaction-scope primitive (context manager or connection wrapper) — not large, but new shared infrastructure that has to be gotten right once, since a bug there is silent (an accidentally-suppressed commit that should have fired looks like data loss, not a crash).
- **`bcllm.py` changes:** `_handle_composite_flow` wraps experiment-creation + all `--add-*` actions in one UoW scope; `_rollback_created_experiment`'s explicit `DELETE`s are replaced by a plain `conn.rollback()` on any action failure, and the whole compensating-delete function (~100 lines, including its own orphan-check and post-delete `foreign_key_check`) is deleted.
- **What gets strictly better:** true atomicity (a crash *during* the rollback attempt itself becomes impossible to reason about incorrectly — see §4, this is exactly the class of bug a real transaction eliminates by construction); no dependency on `_rollback_created_experiment` staying in sync with `ADD_ACTION_FLAGS` if it ever grows (today, someone has to remember to add a new `DELETE` line for a new entity type — a real transaction needs no such bookkeeping).
- **What doesn't get better, and a real regression risk:** SQLite's default transaction/locking behavior means an open write transaction can hold locks affecting concurrent readers/writers for its whole duration; the composite flow today already does several sequential writes on one open implicit-per-statement-then-commit connection, so this isn't a new category of risk, but a UoW spanning experiment-creation + up to 3 `--add-*` actions (which, for `--add-questions`, can mean writing one row per question in the dataset) holds the transaction open measurably longer than today's per-statement commits. Not measured here — would need to be, before committing to this design, especially since `--add-questions system-default` on a large dataset is the realistic worst case.
- **Verification cost:** every one of `tests/cli_suite`'s composite-flow cases (`CE-*`, `AQ-003`/`AQ-004`, `AM-*` composite variants) needs re-verification, plus the new `tests/unit/cli/test_composite_flow_rollback.py` suite added this pass would need rewriting (it asserts specific compensating-delete behavior — e.g. `TestCompensationFailure`'s two-commit-point characterization — that a real transaction makes moot, in a good way).

**This is a real, boundable refactor (not "large" in the way a project-wide UoW would be), but it is not free, and its main risk (transaction hold time on `--add-questions` with large datasets) is unmeasured.** Recommend measuring that specifically before deciding, if this direction is chosen.

---

## 3. Should the compensatory rollback be considered definitive or transitory?

Presented as a real tradeoff, not decided here:

**Case for definitive (keep as the long-term mechanism):** The composite CREATE flow is small and fast (a handful of rows in the common case, `--add-questions` on a large dataset being the exception). It's now well-tested (10 tests across `test_composite_flow_rollback.py`'s two files, covering single- and multi-action failure points, plus the compensation-failure cases below). It touches none of the shared repository commit semantics that `--execute`/`ResultWriter` depends on (§1's hard boundary), so it carries zero risk to the idempotency contract. "Good enough, contained, well-tested" is a legitimate place to stop for a research tool that isn't yet in production (`docs/architecture/adr/adr-003-pre-production-data-scope.md`).

**Case for transitory:** It is not atomic in the ACID sense — §4 demonstrates a real (if narrow) window where a crash *during* the compensation itself leaves a semantically inconsistent "empty shell" experiment row behind, something a real transaction cannot produce by construction. It also silently depends on `_rollback_created_experiment` being manually kept in sync with `ADD_ACTION_FLAGS`/the schema (already flagged in the function's own docstring as something "verified below rather than trusted").

**Recommendation (not a decision):** treat it as **definitive for now, transitory in principle** — i.e., an explicitly-accepted, documented stopgap (this document *is* that documentation), revisited only if either (a) the transaction-hold-time question in §2 turns out to be a non-issue and someone wants the atomicity guarantee for its own sake, or (b) a real incident (not a theoretical one) actually produces an empty-shell experiment in practice. Don't schedule the bigger refactor speculatively.

---

## 4. What guarantees exist if compensation itself fails?

Investigated empirically (not assumed) — see `tests/unit/cli/test_composite_flow_rollback.py::TestCompensationFailure` for the executable proof of both cases below.

**Mechanism:** `_rollback_created_experiment` has **two separate commit points**, not one: an explicit `conn.commit()` right after the 3 child-table `DELETE`s, and a second, *implicit* one inside `ExperimentRepository.delete()`'s own `self.conn.commit()`. Nothing in `_handle_composite_flow` wraps the call to `_rollback_created_experiment` in a `try/except` — a failure there propagates as an **uncaught exception** all the way to `bcllm.py`'s `sys.exit(main())`, producing a raw Python traceback on stderr and Python's default uncaught-exception exit status, not the real action's own exit code.

Two distinct failure windows, confirmed by direct injection:

- **Before the first `conn.commit()`** (e.g. the very first `DELETE FROM question_snapshots` itself raises): confirmed safe. Python's `sqlite3` module discards an uncommitted transaction when the connection is closed (verified directly: write, don't commit, close, reopen — the write is gone). Since `bcllm.py`'s `finally: conn.close()` always runs, the incomplete `DELETE` sequence is discarded and the database ends up **exactly as if no rollback had been attempted at all** — the experiment and everything earlier actions committed are still fully intact. Test: `test_failure_before_any_delete_leaves_original_created_state_fully_intact`.
- **Between the two commit points** (the 3 child `DELETE`s already committed, then `ExperimentRepository.delete()` itself raises): **not safe in the same way.** The child-table deletes are already durable. The result is a genuinely new state — an `experiments` row with zero children, an "empty shell" that looks like a legitimate, just-created-but-empty experiment. It is not a corrupted or dangling-foreign-key state (confirmed: `PRAGMA foreign_key_check`/`PRAGMA integrity_check` both clean in this test), but it is silently wrong: the composite command reported failure, yet a named experiment survives in `--list-experiments`. Test: `test_failure_between_child_deletes_and_experiment_delete_leaves_empty_shell_experiment`.

**No retry, no logged "rollback failed" signal, and no exit-code preservation exist for either window today.** The uncaught-exception path means whatever the *original* triggering action's real exit code was (2 for a usage error, 1 for a domain error) is lost, replaced by Python's generic uncaught-exception behavior. This is a real, if narrow (requires a second failure on top of the first), gap — noted here as investigation evidence per the user's request, **not fixed in this pass**, since a fix here (e.g. wrapping the rollback call in `try/except`, logging clearly, and re-raising or returning a sentinel exit code) is a judgment call about desired behavior on double-failure that deserves the same present-before-implementing treatment as the bigger transactional question, even though it's a much smaller change.

---

## Test coverage added this pass

All in `tests/unit/cli/test_composite_flow_rollback.py` (rewritten; also fixed a real test-isolation bug found while extending it — see below):

- `TestFailureAtDifferentPointsInTheSequence`: failure after only `--add-model` persisted; failure after `--add-model` **and** `--add-questions` persisted (via an injected `--add-run` failure — there is currently no naturally user-reachable way for `--add-run` to fail once its experiment exists, itself a small finding: an invalid `--seed` is intercepted at experiment-creation time, before `--add-run`'s own action ever runs); and a direct unit test of `_rollback_created_experiment` against a manually-constructed experiment with **all three** entity types (model variant, question snapshot, and a run) already persisted, since `--add-run` is last in `ADD_ACTION_FLAGS` and no real composite invocation can "fail after a run is already persisted."
- `TestCompensationFailure`: both failure windows from §4 above, each verified with `PRAGMA foreign_key_check` and `PRAGMA integrity_check`, as explicitly requested.
- Every existing rollback test (from the "same action, same path" checkpoint) now also asserts both PRAGMA checks post-rollback, not just row absence.

**Isolation bug found and fixed while writing these tests:** `bcllm.py` calls `dotenv.load_dotenv(".env", override=True)` at module import time. A test that does `monkeypatch.setenv("DATABASE_PATH", tmp_path)` *before* an in-process `import bcllm`, without also neutralizing `load_dotenv`, is not reliably isolated — the **first** `import bcllm` anywhere in that pytest process re-executes the module top level and silently overwrites `DATABASE_PATH` back to the real `.env`'s `./data/bcllm.db`. This is intermittent, not a hard failure: because Python caches modules, only the first import in the whole process is at risk, and if that first-executed test happens to be a rollback scenario (creates then deletes), the contamination self-cleans and the bug is invisible. Traced this to 213 pre-existing synthetic experiment rows (all obviously test-generated names — `composite_test_*`, `test_standalone_*`, `debug_*`, etc.) accumulated in the real, gitignored `data/bcllm.db` across multiple past sessions. `data/bcllm.db` is gitignored and holds no real research data (`docs/architecture/adr/adr-003-pre-production-data-scope.md`), so this did not leak into the repository or affect any real experiment, but it violates this project's own isolated-diagnostics rule. Fixed by adding `monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: {})` to the test file's autouse fixture, verified via direct probe (env var no longer clobbered). Left the accumulated rows in place — pre-production, gitignored, not this investigation's concern to clean up — but flagging their existence here for visibility.

---

## Summary of what is / isn't decided

| Question | Status |
|---|---|
| Can repos/actions join a future UoW? | Yes, but only via a commit-suppression seam (design (b), §1) — a blanket removal of internal commits is not viable and would break `ResponseRepository`'s crash-safety guarantee. |
| Cost of full transactional composite creation | Bounded (11 call sites + new UoW primitive), main unmeasured risk is transaction hold time on large `--add-questions` datasets. Not implemented. |
| Definitive or transitory rollback? | Recommended: definitive-for-now, revisit only on measured need or a real incident. Not decided by this document — user's call. |
| Guarantees if compensation fails | None today beyond "the DB is never physically corrupted" (PRAGMA-verified) — an empty-shell experiment can survive a double-failure, uncaught, with the wrong exit code. Documented, not fixed. |

No transactional refactor has been implemented. Awaiting direction on whether to proceed with any of the above, and at what scope.
