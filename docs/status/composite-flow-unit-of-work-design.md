---
type: status
audience: ai
last-validated: 2026-08-20
status: implemented-and-validated
---

# Design: real atomicity for the composite `--create-experiment` + `--add-*` flow

**Status: implemented and validated, 2026-08-19–20.** Checkpoint complete, approved, and closed as a unit separate from the still-unstarted Typer conversion. `ResponseRepository` and `src/core/result_writer.py` were never touched, exactly as designed — see the hard boundary in `docs/status/composite-flow-atomicity-investigation.md` §1, restated below.

**Final verification baseline (2026-08-19):** full `pytest` (excluding the 2 known pre-existing broken-collection files) — **983 passed, 48 failed, 18 skipped, 39 errors** (the 48/18/39 are pre-existing and unrelated, byte-identical across every checkpoint this session). `python tests/cli_suite/run.py --profile full --yes` — **44 PASS + 1 EXPECTED_FAILURE**. Essence Guardian review (2026-08-19): all 7 contracts Aligned, no violations; one Warning (documentation lag on `docs/reference/module-structure.md`, fixed same day — `src/db/unit_of_work.py` now listed there). This is the baseline the next checkpoint (Randomization Seed / Model Seed separation, `docs/status/known-issues.md` and upcoming `docs/status/seed-separation-*.md` docs) diffs against.

This follows `docs/status/composite-flow-atomicity-investigation.md` (approved 2026-08-19) and the design below (approved, then adjusted — see the "Adjustments incorporated" section at the end for the 8 changes required before implementation, and exactly how each was implemented).

**Sections 1–9 below describe the design as originally proposed and approved; where implementation ended up differing (mainly section 4's control flow, restructured for the pure-parse-phase adjustment), the "Adjustments incorporated" section at the end is authoritative.**

---

## 1. Scope (per explicit instruction)

**In scope — the composite CREATE flow only:**
- `Experiment` creation (`ExperimentRepository.save`, via `bcllm_experiment.py::_create_experiment_with_config`)
- `ModelVariant` creation (`VariantRepository.save`, via `bcllm_model.py::add_model_action`)
- `QuestionSnapshot` creation (`SnapshotRepository.save`, via `bcllm_questions.py::add_questions_action`)
- `Run` creation (`RunRepository.save`, via `bcllm_run.py::add_run_action`)

**Never in scope, permanently:**
- `ResponseRepository` (`src/core/result_writer.py`'s per-response/per-error commits, `result_writer.py:270,333`). These exist specifically so a crash mid-`--execute` doesn't lose already-generated, real-money API results — `docs/contracts/idempotency.md`'s "partial executions resume from where they left off." No version of this design touches them.
- `--execute`, `AsyncOrchestrator`, `ExecutionEngine` — not reachable from the composite CREATE flow at all.
- `ExperimentRepository.delete`/`VariantRepository.delete`/`SnapshotRepository.delete`/`RunRepository.delete`/`update_status` — used only by standalone `--remove-*` commands and the Review UI, never by the composite CREATE flow. Left untouched, default (immediate-commit) behavior only.

**Dead code found during this investigation, explicitly NOT touched:** `bcllm_experiment.py::_add_models_at_creation` and `_create_question_snapshots` are a second, older implementation of "create a model/snapshot at experiment-creation time," reachable only if `bcllm_experiment.main()`/`handle_create_experiment` is called directly (bypassing `bcllm.py`'s dispatcher) — via the real `python bcllm.py ...` entry point, `_handle_composite_flow` always intercepts `--create-experiment` + any `--add-*` flag first, so these two functions are unreachable in production use today. Some existing unit tests (`test_questions_system_default.py`) call them directly, exercising genuinely-dead-for-the-real-CLI code as if it were live. Out of scope for this change (not part of the real, reachable flow) — flagged here as a separate future cleanup candidate, not decided now.

---

## 2. The Unit of Work: exact design

**New file: `src/db/unit_of_work.py`**

```python
"""Explicit transaction boundary for the composite --create-experiment +
--add-* entity-creation flow. See module docstring in bcllm.py's
_handle_composite_flow for the one call site that uses this.

Scope, permanently: Experiment/ModelVariant/QuestionSnapshot/Run creation
only. NEVER ResponseRepository/ResultWriter/--execute — see
docs/contracts/idempotency.md and docs/status/composite-flow-atomicity-investigation.md.

Participation is explicit, not inferred: a repository write joins this
unit of work only when its caller passes commit=False to that specific
save() call (src/db/repository.py). This module does not wrap, tag, or
inspect the sqlite3.Connection in any way, holds no module-level/global
state, and uses no contextvar — a connection with an open UnitOfWork is
indistinguishable, to any code not explicitly passing commit=False, from
one without it.
"""
from __future__ import annotations

import sqlite3


class UnitOfWork:
    """Wraps one sqlite3.Connection's transaction for a bounded sequence
    of explicitly-participating writes.

    Defaults to ROLLBACK on exit — the caller must call .commit()
    explicitly. This is deliberate, not the more common "commit unless an
    exception occurred" pattern: the composite flow signals "this
    sequence failed" via a non-zero exit code from an action, not by
    raising — commit() being opt-in means a caller that forgets to call
    it fails SAFE (rollback), not silently wrong (a default-commit design
    would persist a failed sequence's partial writes unless every single
    failure path remembered to call rollback() explicitly instead).

    Any exception raised inside the `with` block — expected or not — is
    never suppressed (__exit__ always returns False) and, since commit()
    was never reached, still results in rollback via the same "no
    commit() call" default.
    """

    def __init__(self, conn: sqlite3.Connection, *, immediate: bool = True):
        self._conn = conn
        self._immediate = immediate
        self._committed = False

    def __enter__(self) -> "UnitOfWork":
        self._conn.execute("BEGIN IMMEDIATE" if self._immediate else "BEGIN")
        return self

    def commit(self) -> None:
        self._conn.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self._committed:
            self._conn.rollback()
        return False
```

That is the entire class — deliberately minimal. No retry logic, no nesting/savepoint support (not needed at this scope), no connection pooling concerns (the composite flow already uses exactly one connection for its whole lifetime).

---

## 3. Commit policy (the explicit-participation mechanism)

**`src/db/repository.py`** — exactly 4 methods gain a `commit: bool = True` keyword-only parameter (the only 4 actually called by the composite CREATE flow — confirmed by tracing every call site):

```python
# ExperimentRepository
def save(self, experiment: Experiment, *, commit: bool = True) -> None:
    ...
    if commit:
        self.conn.commit()

# VariantRepository
def save(self, variant: ModelVariant, *, commit: bool = True) -> None:
    ...
    if commit:
        self.conn.commit()

# SnapshotRepository
def save(self, snapshot: QuestionSnapshot, *, commit: bool = True) -> None:
    ...
    if commit:
        self.conn.commit()

# RunRepository
def save(self, run: Run, config: dict, *, commit: bool = True) -> None:
    ...
    if commit:
        self.conn.commit()
```

Every other repository method (`delete`, `update_status`, `ResponseRepository.save`, `ResponseRepository.update_manual_answer`, etc.) is **untouched** — no parameter added, behavior unchanged. Default `commit=True` on the 4 changed methods means every existing caller that does not explicitly pass `commit=False` — standalone `--add-model`/`--add-run`, the (dead but still-tested) `_add_models_at_creation`/`_create_question_snapshots`, anything else — behaves **byte-identically to today**.

This is the "explicit participation" mechanism in full: nothing about the connection, no wrapper, no global/contextvar state. A caller opts a specific write into the shared transaction by passing one keyword argument to that one call.

**Threaded through the 4 action layers**, each gaining the same `commit: bool = True` keyword-only parameter, passed straight to its one `repo.save(...)` call:

| File | Function | Change |
|---|---|---|
| `src/cli/bcllm_experiment.py` | `_create_experiment_with_config(name, args, conn, logger, *, commit: bool = True)` | `repo.save(experiment, commit=commit)` |
| `src/cli/bcllm_model.py` | `add_model_action(request, conn, *, commit: bool = True) -> AddModelResult` | `var_repo.save(variant, commit=commit)` |
| `src/cli/bcllm_model.py` | `run_add_model(argv, conn=None, *, commit: bool = True) -> int` | passes `commit=commit` to `add_model_action` |
| `src/cli/bcllm_questions.py` | `add_questions_action(request, conn, *, commit: bool = True) -> AddQuestionsResult` | `snap_repo.save(snapshot, commit=commit)` inside the per-question loop |
| `src/cli/bcllm_questions.py` | `run_add_questions(argv, conn=None, *, commit: bool = True) -> int` | passes `commit=commit` to `add_questions_action` |
| `src/cli/bcllm_run.py` | `add_run_action(request, conn, *, commit: bool = True) -> AddRunResult` | `run_repo.save(run, config_dict, commit=commit)` |
| `src/cli/bcllm_run.py` | `run_add_run(argv, conn=None, *, commit: bool = True) -> int` | passes `commit=commit` to `add_run_action` |

**"Same action, same path" is preserved, not reintroduced-as-a-fork:** the validation/config-resolution/business logic in each `*_action` function does not change or branch on `commit` — only the single trailing `repo.save(..., commit=commit)` call's behavior differs. Standalone `main()` never passes `commit=False` (so it's always the default `True`, identical to today); only `bcllm.py`'s composite orchestrator passes `commit=False`. One code path, one extra explicit parameter — not two implementations.

---

## 4. `bcllm.py` — the actual rewrite

**`_handle_composite_flow`** (the core change):

```python
from src.db.unit_of_work import UnitOfWork

def _handle_composite_flow(argv, mode, module_name):
    # ... unchanged: has_create/has_add_action check, experiment_name
    # extraction, precondition validation (QUESTIONS_DATASET_PATH,
    # OPENROUTER_API_KEY) — all happen BEFORE any connection is opened,
    # exactly as today ...

    conn = get_database_connection()
    try:
        with UnitOfWork(conn) as uow:
            try:
                create_argv = [...]  # unchanged
                parser = create_parser()
                args = parse_args_normalized(parser, create_argv[1:])

                try:
                    _create_experiment_with_config(
                        experiment_name, args, conn, logger, commit=False,
                    )
                except ValueError as e:
                    if "already exists" in str(e):
                        logger.info(f"COMPOSITE_FLOW | experiment already exists (concurrent)={experiment_name}")
                        # No INSERT happened — nothing of ours to roll
                        # back for the experiment row itself. Any
                        # --add-* actions below still run inside THIS
                        # transaction and DO get rolled back together on
                        # failure — see "behavior change" note below.
                    else:
                        print(f"Error: {e}", file=sys.stderr)
                        return True, 1  # uow rolls back (commit() never called)
                except sqlite3.IntegrityError as e:
                    # Confirmed empirically: a UNIQUE-constraint
                    # IntegrityError does NOT poison the surrounding
                    # SQLite transaction — subsequent statements on the
                    # same connection/transaction still work normally.
                    # TOCTOU handling below is UNCHANGED from today,
                    # just now nested inside the `with` block.
                    error_msg = str(e).lower()
                    if "unique constraint failed" in error_msg and "experiment.name" in error_msg:
                        # ... unchanged: verify via a SEPARATE connection
                        # that another process really did create it ...
                    else:
                        raise

                action_exit_code = _execute_all_add_actions(
                    argv, experiment_name, conn, logger, commit=False,
                )

                if action_exit_code == 0:
                    uow.commit()
                    return True, 0
                else:
                    # uow rolls back automatically on exit (commit() was
                    # never called) — no explicit rollback call needed,
                    # and no compensating DELETEs at all anymore.
                    return True, action_exit_code

            except Exception as e:
                # Anything unexpected (a DB I/O error, a bug) — never let
                # this become a raw traceback. uow still rolls back (same
                # "commit() never called" default). Operational error,
                # not a usage error: exit code 1, per point 6.
                logger.error(f"COMPOSITE_FLOW | unexpected error, rolled back | {e!r}")
                print(f"Error: unexpected failure while setting up the experiment: {e}", file=sys.stderr)
                return True, 1
    finally:
        conn.close()
```

`_execute_all_add_actions` and `_execute_single_action` each gain the same `commit: bool = True` passthrough parameter (no other change to their filtering/argv-building logic).

**`_rollback_created_experiment` is deleted entirely** (~100 lines, including its own orphan-row check and post-delete `PRAGMA foreign_key_check`) — a real `conn.rollback()` makes it structurally impossible for the scenario it guarded against (unexpected `responses`/`errors` rows existing) to matter, since a rollback undoes everything uncommitted regardless of table.

**Behavior change, disclosed, not hidden:** today, when TOCTOU fires (`experiment_created_by_us = False`), a subsequent `--add-*` failure does **not** roll back the earlier successful actions in the same invocation ("it's not ours to roll back" — but the existing code conflates "not ours to delete the experiment" with "not ours to undo our own actions against it," and skips both). Under real atomicity, this invocation's own `--add-model`/`--add-questions`/`--add-run` writes against a pre-existing experiment are naturally undone by `conn.rollback()` if a later action in the same invocation fails — **only** the experiment row itself (never part of our uncommitted transaction in the TOCTOU case) survives, exactly as intended. This is a strict improvement, not a regression, and falls out of using a real transaction for free — no special-case code needed. Called out explicitly per this project's "surface behavior changes, don't hide them" convention.

`experiment_created_by_us` as a variable can be **removed** — it no longer needs to gate the rollback decision (a real `conn.rollback()` only ever undoes what's uncommitted in this transaction, which is automatically "what this invocation did," full stop). It may still be worth keeping for the log-message wording ("already exists (concurrent)" vs. a fresh create), a cosmetic-only use.

---

## 5. Exit-code / traceback guarantees (point 6)

| Failure class | Mechanism | Exit code | Traceback? |
|---|---|---|---|
| Usage error (e.g. `--reasoning garbage-value`) | `run_add_*` returns 2 (unchanged — `ParserExit`-derived, never raises) | 2 | No |
| Domain/operational error (e.g. experiment not found, duplicate variant) | `*_action` returns 1 (unchanged) | 1 | No |
| Unexpected exception (DB I/O error, bug) | Caught by the new `except Exception` inside `_handle_composite_flow`, `uow` rolls back | 1 | **No — this is new.** Today this case propagates as an uncaught traceback (see the atomicity-investigation doc's §4, `TestCompensationFailure`). Fixed as a direct, intended consequence of this design, not a separate patch. |
| Any failure at any point | `uow.commit()` was never reached → rollback | — | Experiment row never left half-configured or "empty shell" — both are structurally impossible now (a real rollback undoes the experiment INSERT too, unlike today's compensating-DELETE mechanism, which could leave an empty-shell experiment if the second of its own two commits failed). |

---

## 6. Performance and contention proof (point 5)

Measured directly (script: scratch, not committed — numbers below are what matters), against a real on-disk SQLite file with the project's actual schema, on this machine (Windows, project's actual disk), simulating `--add-questions` writing N `question_snapshots` rows — the only genuinely N-scaling write in the composite flow (model/experiment/run are always exactly one row each):

**Duration, N = 10 / 100 / 2000 (small / medium / large-representative — the real dataset in `.env` has 100 questions; 2000 tests well beyond current real-world scale):**

| N | (a) today: 1 commit per row | (b) proposed: 1 transaction, deferred `BEGIN` | (c) proposed: 1 transaction, `BEGIN IMMEDIATE` |
|---|---|---|---|
| 10 | 128.6 ms | 6.5 ms | 6.3 ms |
| 100 | 670.3 ms | 7.3 ms | 7.3 ms |
| 2000 | **15,701 ms (15.7s)** | 22.6 ms | 21.9 ms |

The single-transaction design is not a tradeoff against performance — it is **~90–700× faster** at every scale tested, because each `commit()` on this machine costs roughly 6–8 ms (a full journal fsync), and today's code pays that cost once per row instead of once per flow. This was not the primary goal of the change but is a significant, real side benefit worth stating plainly.

**Contention, a second connection reading/writing while a 200-row transaction is open mid-flight (default SQLite settings — no WAL, no explicit `busy_timeout` anywhere in `src/`, confirmed by grep; Python's `sqlite3.connect()` default `timeout=5.0`s applies):**

| | Concurrent `SELECT` | Concurrent `INSERT` |
|---|---|---|
| Deferred `BEGIN` | 1.6 ms (unaffected) | 560 ms (blocked, then succeeds once our transaction commits) |
| `BEGIN IMMEDIATE` | 0.6 ms (unaffected) | 151 ms (blocked, then succeeds) |

Reads are never blocked in either mode (SQLite's rollback-journal readers see the pre-transaction snapshot until commit, regardless of an open writer). A concurrent write blocks for roughly the duration of our transaction — which, per the duration numbers above, is now **tens of milliseconds even at 2000 rows**, versus today's design where the equivalent contention *window* is smeared across the full 15.7-second operation (each of the 2000 individual commits is a brief lock/unlock cycle, but the overall operation — and thus the real-world chance of colliding with another process — takes 700× longer to finish). Net effect: **less real-world contention exposure than today, not more**, on top of the huge duration win.

**Recommendation: `BEGIN IMMEDIATE`.** Marginally better concurrent-write latency in this measurement, and — more importantly — it fails/blocks predictably at the very start of the transaction rather than potentially deep into a multi-row `--add-questions` sequence; a deferred `BEGIN` could in principle do most of the work before discovering at commit time that it lost a race for the write lock, which is a worse failure shape even though duration numbers were nearly identical here.

**Caveat, stated plainly:** this was measured on one machine, with a synthetic empty-DB benchmark, not the real (currently 213-row, all-synthetic) local database or any concurrent real workload. The direction of every result (single-transaction faster, less contention exposure) is robust and not close to a wash, so a materially different real-world outcome is unlikely — but this is not a load-tested production benchmark.

---

## 7. Item 8: `load_dotenv` bootstrap fix

**Current (`bcllm.py`, module top level):**
```python
from dotenv import load_dotenv
load_dotenv(".env", override=True)
```
This runs the instant anything does `import bcllm` — including test code, tooling, or any future programmatic caller — silently overwriting whatever environment that caller had already prepared (`override=True`). This is exactly the mechanism behind the test-isolation bug found and fixed locally in `tests/unit/cli/test_composite_flow_rollback.py` during the previous investigation; fixing it at the source removes the need for every future test file to independently work around it.

**Proposed:**
```python
def _bootstrap_environment() -> None:
    """Load .env into the process environment. Must be called exactly
    once, only from this module's real CLI entry point below — never at
    import time, so importing bcllm.py (tests, tooling, any future
    programmatic caller) never silently overwrites an environment the
    caller already prepared. See docs/status/known-issues.md."""
    load_dotenv(".env", override=True)


if __name__ == "__main__":
    _bootstrap_environment()
    sys.exit(main())
```

**Verified safe for real CLI usage:** `src/core/config_resolver.py::ConfigResolver.load_env()` already only snapshots `os.environ` — its own docstring states ".env file was already loaded by bcllm.py at startup," it never calls `load_dotenv` itself. As long as `_bootstrap_environment()` runs once, before `main()`, at real process start, every downstream `ConfigResolver.load_env()` call sees exactly the same environment it does today. No other code in `src/` calls `dotenv.load_dotenv` (confirmed by grep) — this is the only call site.

**Affected file:** `bcllm.py` only.

---

## 8. Tests to be added alongside the implementation (point 7)

`tests/unit/cli/test_composite_flow_rollback.py` gets substantially rewritten (the compensating-DELETE-specific tests — `TestCompensationFailure`'s two-commit-point characterization — no longer apply, since there is only one commit point now):

- Failure at each stage, with real transactional rollback confirmed (not just row-absence, but `PRAGMA foreign_key_check` + `PRAGMA integrity_check`, as before): after experiment-creation-only, after model persisted (uncommitted), after model+questions persisted (uncommitted), after model+questions+run all pending (uncommitted) — for each, assert **zero** rows across all 4 tables for that experiment, not just the experiments row.
- Unexpected failure: inject a raw exception (e.g. a monkeypatched repository method that raises `sqlite3.OperationalError` mid-sequence) and assert (a) rollback happened (0 rows, PRAGMA-clean), (b) exit code is 1, (c) **no traceback reaches the caller** (`capsys`/return-value based, not `pytest.raises`) — this directly tests the point 6 guarantee that was previously a documented gap.
- TOCTOU + a later action failing (the "behavior change" from §4): pre-existing experiment, `--add-model` succeeds, `--add-questions` fails — confirm the pre-existing experiment row survives, but the model variant this invocation created does **not** (rolled back), demonstrating the disclosed improvement over today's behavior.
- Standalone regression: every standalone `--add-model`/`--add-questions`/`--add-run`/`--create-experiment` test already in the suite must keep passing unmodified — proving `commit=True`'s default preserves immediate-commit behavior exactly (point 4).
- `src/db/unit_of_work.py` gets its own small unit test file: commit-then-persists, no-commit-then-rolls-back, exception-inside-still-rolls-back, nested `try/except` swallowing an exception still rolls back (since `commit()` was never reached).

`cli_suite`'s composite-flow YAML cases (`CE-*`, `AQ-003`/`AQ-004`, `AM-*` composite variants) get re-verified end-to-end as part of the implementation's regression pass, same as every prior checkpoint this session.

---

## 9. Summary of files affected

| File | Change |
|---|---|
| `src/db/unit_of_work.py` | **New.** The `UnitOfWork` class (§2). |
| `src/db/repository.py` | `commit: bool = True` added to `ExperimentRepository.save`, `VariantRepository.save`, `SnapshotRepository.save`, `RunRepository.save` only. |
| `src/cli/bcllm_experiment.py` | `_create_experiment_with_config` gains `commit` passthrough. |
| `src/cli/bcllm_model.py` | `add_model_action`, `run_add_model` gain `commit` passthrough. |
| `src/cli/bcllm_questions.py` | `add_questions_action`, `run_add_questions` gain `commit` passthrough. |
| `src/cli/bcllm_run.py` | `add_run_action`, `run_add_run` gain `commit` passthrough. |
| `bcllm.py` | `_handle_composite_flow` rewritten to use `UnitOfWork`; `_rollback_created_experiment` deleted; `_execute_all_add_actions`/`_execute_single_action` gain `commit` passthrough; `load_dotenv` moved out of module import time (§7). |
| `tests/unit/cli/test_composite_flow_rollback.py` | Substantially rewritten (§8). |
| `tests/unit/db/test_unit_of_work.py` | **New**, small. |

**Not touched, ever, by this design:** `src/core/result_writer.py`, `ResponseRepository` in `src/db/repository.py`, `src/core/async_writer.py`, `src/core/async_orchestrator.py`, `src/core/execution_engine.py`, anything reachable from `--execute`.

---

## Adjustments incorporated (approved 2026-08-19, before implementation)

The proposal above was approved conceptually (UnitOfWork scope, explicit `commit=False` participation, `BEGIN IMMEDIATE`, removing the compensating rollback, the new TOCTOU semantics, the permanent `ResponseRepository`/`ResultWriter`/`--execute` exclusion), with 8 required adjustments. Each is recorded here with exactly how it was implemented, since implementation ended up restructuring `_handle_composite_flow` more than §4 originally sketched.

**1. Exception handling must wrap the entire `with UnitOfWork(...)` block, not just its body.** A failure in `UnitOfWork.__enter__` itself (`BEGIN IMMEDIATE` against a busy database) must not escape as a raw traceback — and per Python's `with`-statement semantics, if `__enter__` raises, `__exit__` is never called at all, so an exception handler placed *inside* the block (wrapping only the body) would never see it. Implemented: `_handle_composite_flow` wraps `try: with UnitOfWork(conn, immediate=True) as uow: ... except Exception as e: ...` — the `try` starts before the `with`, not inside it. Confirmed by test (`TestUnitOfWorkFailuresProduceCleanExitCodes::test_busy_database_on_begin_immediate_returns_1_no_traceback`, using a real second connection holding the lock, not a mock).

**2. Tests added** (`tests/unit/db/test_unit_of_work.py`, `tests/unit/cli/test_composite_flow_rollback.py`): a real busy-database timeout on `BEGIN IMMEDIATE` (genuine contention via a second connection, not synthetic); a `commit()` failure; a `rollback()` failure; each asserted to produce exit code 1, no raw traceback in the user-facing `print()` output (`_assert_user_facing_output_is_generic` — see note below on why this checks the exact generic string rather than scanning all of stderr), and the database connection always closed (`finally: conn.close()` verified via a proxy connection tracking whether `.close()` was called). `sqlite3.Connection`/`Cursor` are immutable C types and can't be monkeypatched directly (confirmed: raises `"cannot set 'X' attribute of immutable type"`) — every failure-injection test uses a thin pure-Python proxy wrapping the real connection instead.

**3. Pure parsing/normalization/validation before opening the connection, wherever possible; enumerate what must stay inside the transaction.** Implemented via a genuine restructuring, not just moving one parse call: `_handle_composite_flow` now has two phases —
- **Pure parse phase (no connection, no lock):** experiment-creation flags are parsed via `bcllm_experiment.create_parser()` (converted to `NonExitingArgumentParser` — it was still a plain `argparse.ArgumentParser`, a gap this adjustment surfaced: any argparse-level usage error in experiment-creation-specific flags would have raised an uncontrolled `sys.exit()`, unprotected by this whole checkpoint's earlier "same action, same path" fix, which only covered `--add-model`/`--add-questions`/`--add-run`'s own parsers). Every requested `--add-*` action is *also* fully parsed here, via three new pure functions extracted from each module's `run_add_*()`: `bcllm_model.parse_add_model_request`, `bcllm_questions.parse_add_questions_request`, `bcllm_run.parse_add_run_request` — each raises `ParserExit` on a usage error, exactly like the parsing half of `run_add_*()` always did, just callable without a connection or an action call attached. `run_add_*()` itself gained an optional `request=` parameter so it can accept an already-parsed request (used by the DB phase below) instead of re-parsing `argv` — no duplicate parsing logic, same functions either way.
- **What stays inside the transaction, and why:** the experiment "already exists" check + `INSERT` (needs to observe committed state, and the insert itself needs the lock); the TOCTOU `IntegrityError` race handling (inherently needs the real `INSERT` attempt); each action's experiment lookup, config-inheritance resolution (reads the experiment's `config_json`), duplicate/dedup checks, and its own `INSERT`. Two known, deliberate exceptions where something *technically* pure stays bundled with a DB-dependent check, not split further in this pass: (a) experiment-level seed/prompt config resolution (`ConfigResolver.build_experiment_config_dict`, pure) is bundled inside `_create_experiment_with_config` alongside its existence check — splitting it has a larger blast radius (that function is also the standalone `--create-experiment` path's canonical implementation) than the win of pre-validating an already-rare invalid-seed-at-experiment-creation-time case; (b) `--add-model`'s `validate_model_id`/vision/structured boolean validation (pure) stays inside `add_model_action` rather than being hoisted into `parse_add_model_request`, preserving their existing exit-code-1 (domain error) classification exactly — moving them into the parse phase would have made them exit-code-2 (usage error) instead, a real classification change not requested here.
  - **Disclosed side effect:** because `--add-run`'s own seed-FORMAT check now runs during the pure parse phase (unchanged logic, just earlier in the overall flow) and `--seed` is forwarded to *both* experiment-creation's args and `--add-run`'s own args, `--create-experiment X --add-run --seed <invalid>` now returns exit 2 (from `--add-run`'s stricter, earlier check) instead of the old exit 1 (from experiment-creation's later config-resolution `ValueError`) — but *only* when `--add-run` is actually requested; `--create-experiment X --seed <invalid> --add-model Y` (no `--add-run`) still returns exit 1, unchanged, since nothing in the parse phase validates seed format for that combination. Both cases have dedicated tests.

**4. Never print unexpected-exception text to the user; generic message only, full detail in the log.** Implemented: `except Exception as e: logger.error(f"... {e!r}", exc_info=True); print("Error: an unexpected failure occurred while setting up the experiment. See the technical log for details.", file=sys.stderr); return True, 1`. Note for anyone extending the tests: `src/utils/logging_config.py`'s console handler defaults to `sys.stderr` too, so the log record (correctly, deliberately) still contains full exception detail on the same stream — point 4 is about the `print()` call specifically, not about scrubbing exception text from stderr as a whole. The test suite checks for the exact literal generic string rather than trying to heuristically strip logging output from `capsys`-captured stderr.

**5. `load_dotenv` moved to a bootstrap explicit entry point, shared by direct execution and the installed console script; importing `bcllm` has zero side effects.** Implemented: `_bootstrap_environment()` (calls `load_dotenv(".env", override=True)`) is called only from a new `cli_main()` function, which both `if __name__ == "__main__": sys.exit(cli_main())` (direct `python bcllm.py` execution) and `setup.py`'s `console_scripts` entry point (`bcllm=bcllm:cli_main`, updated from `bcllm:main` — pointing it at plain `main()` would have silently skipped `.env` loading entirely for the installed console script) now call. Verified safe for real CLI usage: `ConfigResolver.load_env()` only ever snapshots `os.environ`, its own docstring already stated "`.env` file was already loaded by bcllm.py at startup" — as long as `_bootstrap_environment()` runs once before `main()` at real process start, every downstream `load_env()` call sees exactly the same environment as before. No other code in `src/` calls `dotenv.load_dotenv` (confirmed by grep).

**6. A guard that fails if a future composite action forgets to pass `commit=False`.** Implemented as `UnitOfWork.assert_active()`: raises `RuntimeError` if `self._conn.in_transaction` is `False` — evidence that some participating write committed on its own instead of deferring to the unit of work. `UnitOfWork.commit()` calls it internally before committing; `_handle_composite_flow` also calls it explicitly after experiment creation and after every action, so a premature commit is caught at the very next checkpoint rather than possibly being masked by a later action's own (correctly deferred) write re-opening an implicit transaction before the final `commit()` is ever reached. This is a defensive assertion on a property inherent to the connection object (`in_transaction`), not the "implicit connection-based inference" adjustment 3 (of the *original* investigation request) ruled out — it never changes behavior, it only fails loudly when the explicit-participation invariant has already been violated by a bug. Covered by `tests/unit/db/test_unit_of_work.py::TestAssertActiveGuard`.

**7. Do not remove the dead code identified during this change.** `bcllm_experiment.py::_add_models_at_creation` and `_create_question_snapshots` remain untouched, exactly as flagged in the atomicity-investigation doc — unreachable via the real `python bcllm.py` entry point (`_handle_composite_flow` always intercepts `--create-experiment` + any `--add-*` flag first) but still exercised by some existing unit tests that call `bcllm_experiment.main()`/`handle_create_experiment` directly.

**Verification:** full `pytest` (excluding the 2 known pre-existing broken-collection files) — 983 passed (971 baseline + 12 new: 9 in `test_unit_of_work.py`, net +3 in the rewritten `test_composite_flow_rollback.py`), 48 failed / 18 skipped / 39 errors, all three byte-identical to every prior baseline this session — zero regression. `python tests/cli_suite/run.py --profile full --yes` — 44 PASS + 1 EXPECTED_FAILURE, unchanged, confirming the real subprocess entry point (including the new `cli_main()`/bootstrap split) works end-to-end.