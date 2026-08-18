"""Read-only SQLite helpers for asserting on suite database state.

Rule from the draft spec, kept: never mutate the SQLite database outside
the CLI itself. Every function here only SELECTs / runs PRAGMA checks.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from .case import DbAssertion

# The 6 tables of the schema (src/db/schema.sql). Fingerprinting is
# restricted to this fixed list rather than an arbitrary table name coming
# from a YAML case, so a typo in `unchanged_tables` fails loudly instead of
# silently querying nothing.
KNOWN_TABLES = (
    "experiments",
    "model_variants",
    "question_snapshots",
    "runs",
    "responses",
    "errors",
)


@dataclass
class AssertionOutcome:
    assertion: DbAssertion
    actual: object
    passed: bool


def run_assertion(conn: sqlite3.Connection, assertion: DbAssertion) -> AssertionOutcome:
    cur = conn.execute(assertion.query, assertion.params)
    row = cur.fetchone()
    actual = row[0] if row is not None else None
    return AssertionOutcome(assertion=assertion, actual=actual, passed=(actual == assertion.equals))


def fingerprint_table(conn: sqlite3.Connection, table: str) -> str:
    if table not in KNOWN_TABLES:
        raise ValueError(f"Unknown table {table!r}; expected one of {KNOWN_TABLES}")
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    payload = json.dumps(rows, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fingerprint_tables(conn: sqlite3.Connection, tables: tuple[str, ...]) -> dict[str, str]:
    return {t: fingerprint_table(conn, t) for t in tables}


def diff_fingerprints(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Returns the list of table names whose fingerprint changed."""
    return [t for t in before if before.get(t) != after.get(t)]


def integrity_issues(conn: sqlite3.Connection) -> list[str]:
    """Runs PRAGMA foreign_key_check and PRAGMA integrity_check.

    Returns a list of human-readable problems; empty means clean.
    """
    issues: list[str] = []

    for row in conn.execute("PRAGMA foreign_key_check"):
        issues.append(f"foreign_key_check: {tuple(row)}")

    for row in conn.execute("PRAGMA integrity_check"):
        result = row[0]
        if result != "ok":
            issues.append(f"integrity_check: {result}")

    return issues
