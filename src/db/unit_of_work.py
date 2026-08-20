"""Explicit transaction boundary for the composite --create-experiment +
--add-* entity-creation flow (bcllm.py::_handle_composite_flow — the only
call site). See docs/status/composite-flow-unit-of-work-design.md.

Scope, permanently: Experiment/ModelVariant/QuestionSnapshot/Run creation
only. NEVER ResponseRepository/ResultWriter/--execute — see
docs/contracts/idempotency.md and
docs/status/composite-flow-atomicity-investigation.md.

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
    it fails SAFE (rollback), not silently wrong.

    Any exception raised inside the `with` block — including one raised
    by __enter__ itself (e.g. BEGIN IMMEDIATE timing out against a busy
    database) — must be caught by the CALLER wrapping the entire `with`
    statement (not just its body): if __enter__ raises, __exit__ is never
    invoked at all (this is standard Python `with`-statement behavior),
    so this class cannot roll back a transaction that was never
    successfully opened — there is nothing to roll back in that case,
    but the exception itself still must not reach the user as a raw
    traceback. See bcllm.py::_handle_composite_flow for the required
    `try: with UnitOfWork(conn) as uow: ... / except Exception:` shape.
    """

    def __init__(self, conn: sqlite3.Connection, *, immediate: bool = True):
        self._conn = conn
        self._immediate = immediate
        self._committed = False

    def __enter__(self) -> "UnitOfWork":
        self._conn.execute("BEGIN IMMEDIATE" if self._immediate else "BEGIN")
        return self

    def assert_active(self) -> None:
        """Raise if the underlying transaction is no longer open —
        evidence that a write meant to participate in this unit of work
        actually committed on its own (forgot to pass commit=False to
        its repository save() call). Call this after each participating
        write, and again inside commit() itself, so a future composite
        action that forgets commit=False fails loudly and immediately
        instead of silently losing atomicity.
        """
        if not self._conn.in_transaction:
            raise RuntimeError(
                "UnitOfWork transaction is no longer open — a write meant to "
                "participate in this unit of work likely committed on its own "
                "(forgot to pass commit=False to its repository save() call). "
                "Refusing to silently continue as if atomicity still held."
            )

    def commit(self) -> None:
        self.assert_active()
        self._conn.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self._committed:
            self._conn.rollback()
        return False
