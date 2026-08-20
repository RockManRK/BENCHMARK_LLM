"""Unit tests for src.db.unit_of_work.UnitOfWork in isolation — no CLI,
no bcllm.py involved. See tests/unit/cli/test_composite_flow_rollback.py
for the integration-level coverage (the actual composite --create-experiment
+ --add-* flow using this class).

Isolation: hermetic, on-disk SQLite in tmp_path (BEGIN IMMEDIATE needs a
real file to test locking/contention against a second connection — an
in-memory DB is a single, unshareable connection). No real .env/production
DB touched — this file never imports bcllm.py.
"""

from __future__ import annotations

import sqlite3
import threading
import time

import pytest

from src.db.unit_of_work import UnitOfWork


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "uow_test.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.commit()
    conn.close()
    return path


class TestCommitPersists:
    def test_commit_persists_writes(self, db_path):
        conn = sqlite3.connect(str(db_path))
        with UnitOfWork(conn) as uow:
            conn.execute("INSERT INTO t (v) VALUES ('a')")
            uow.commit()
        conn.close()

        verify = sqlite3.connect(str(db_path))
        rows = verify.execute("SELECT v FROM t").fetchall()
        verify.close()
        assert rows == [("a",)]


class TestNoCommitRollsBack:
    def test_no_commit_call_rolls_back_on_clean_exit(self, db_path):
        """The default: a `with` block that exits normally WITHOUT
        calling uow.commit() still rolls back — this is the "commit is
        opt-in, not opt-out" safety property the whole design relies on
        (the composite flow signals failure via a non-zero return value,
        not by raising)."""
        conn = sqlite3.connect(str(db_path))
        with UnitOfWork(conn) as uow:
            conn.execute("INSERT INTO t (v) VALUES ('never-committed')")
            # deliberately never call uow.commit()
        conn.close()

        verify = sqlite3.connect(str(db_path))
        rows = verify.execute("SELECT v FROM t").fetchall()
        verify.close()
        assert rows == []

    def test_exception_inside_with_block_rolls_back(self, db_path):
        conn = sqlite3.connect(str(db_path))
        with pytest.raises(ValueError, match="boom"):
            with UnitOfWork(conn) as uow:
                conn.execute("INSERT INTO t (v) VALUES ('never-committed')")
                raise ValueError("boom")
        conn.close()

        verify = sqlite3.connect(str(db_path))
        rows = verify.execute("SELECT v FROM t").fetchall()
        verify.close()
        assert rows == []

    def test_caught_exception_inside_with_block_still_rolls_back(self, db_path):
        """A caller that catches the exception INSIDE the `with` block
        (the shape bcllm.py uses for expected action failures) still gets
        a rollback, because commit() was never reached — no explicit
        rollback() call needed by the caller."""
        conn = sqlite3.connect(str(db_path))
        with UnitOfWork(conn) as uow:
            conn.execute("INSERT INTO t (v) VALUES ('never-committed')")
            try:
                raise ValueError("boom")
            except ValueError:
                pass  # swallowed — commit() still never called
        conn.close()

        verify = sqlite3.connect(str(db_path))
        rows = verify.execute("SELECT v FROM t").fetchall()
        verify.close()
        assert rows == []


class TestAssertActiveGuard:
    def test_assert_active_raises_when_transaction_already_closed(self, db_path):
        """The guard from point 6: if something committed the
        transaction out from under the UnitOfWork (e.g. a future
        composite action forgetting to pass commit=False to its
        repository save() call), assert_active() must fail loudly
        instead of letting the caller silently believe atomicity still
        holds."""
        conn = sqlite3.connect(str(db_path))
        uow = UnitOfWork(conn)
        uow.__enter__()
        conn.execute("INSERT INTO t (v) VALUES ('a')")
        conn.commit()  # simulates a participating write forgetting commit=False

        with pytest.raises(RuntimeError, match="no longer open"):
            uow.assert_active()

        uow.__exit__(None, None, None)
        conn.close()

    def test_commit_calls_assert_active_and_raises_the_same_way(self, db_path):
        conn = sqlite3.connect(str(db_path))
        uow = UnitOfWork(conn)
        uow.__enter__()
        conn.execute("INSERT INTO t (v) VALUES ('a')")
        conn.commit()  # premature commit, same as above

        with pytest.raises(RuntimeError, match="no longer open"):
            uow.commit()

        uow.__exit__(None, None, None)
        conn.close()

    def test_assert_active_passes_while_transaction_genuinely_open(self, db_path):
        conn = sqlite3.connect(str(db_path))
        with UnitOfWork(conn) as uow:
            conn.execute("INSERT INTO t (v) VALUES ('a')")
            uow.assert_active()  # must not raise
            uow.commit()
        conn.close()


class TestBusyDatabaseOnEnter:
    def test_begin_immediate_raises_operational_error_when_database_busy(self, db_path):
        """Real contention, not a synthetic mock: a second connection
        holds an open BEGIN IMMEDIATE write lock; UnitOfWork.__enter__'s
        own BEGIN IMMEDIATE on a different connection must fail with a
        real sqlite3.OperationalError (not hang forever) once Python's
        connect-level busy timeout elapses."""
        holder = sqlite3.connect(str(db_path))
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO t (v) VALUES ('held')")
        # deliberately never commits/rolls back — holds the write lock

        try:
            # Short timeout so the test itself stays fast — this is
            # exactly the scenario bcllm.py's outer exception boundary
            # (wrapping the ENTIRE `with UnitOfWork(...)` statement, not
            # just its body) must catch, since __enter__ raising means
            # __exit__ is never even called.
            busy_conn = sqlite3.connect(str(db_path), timeout=0.2)
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with UnitOfWork(busy_conn) as uow:
                    pytest.fail("should never reach the body — __enter__ must raise first")
            busy_conn.close()
        finally:
            holder.rollback()
            holder.close()


class TestRollbackFailure:
    def test_rollback_failure_propagates_out_of_with_statement(self, db_path, monkeypatch):
        """A proxy connection whose rollback() raises — sqlite3.Connection
        is an immutable C type, its methods can't be monkeypatched
        directly (confirmed: raises "cannot set 'rollback' attribute of
        immutable type"), so a thin pure-Python proxy is used instead,
        same technique as the composite-flow-level test for a symmetric
        scenario. Confirms: the failure is NOT swallowed by __exit__
        (propagates to the caller, which is exactly what lets bcllm.py's
        outer except Exception boundary catch it and report a clean exit
        code 1 with no raw traceback shown to the user)."""

        class _RollbackFailsProxy:
            def __init__(self, real_conn):
                self._real_conn = real_conn

            def rollback(self):
                raise sqlite3.OperationalError("simulated rollback failure")

            def __getattr__(self, name):
                return getattr(self._real_conn, name)

        real_conn = sqlite3.connect(str(db_path))
        proxy = _RollbackFailsProxy(real_conn)

        with pytest.raises(sqlite3.OperationalError, match="simulated rollback failure"):
            with UnitOfWork(proxy) as uow:
                real_conn.execute("INSERT INTO t (v) VALUES ('a')")
                # never call uow.commit() — __exit__ will try to roll
                # back and that rollback() call is what's rigged to fail

        real_conn.close()
