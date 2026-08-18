"""Test case schema: YAML -> dataclass, with validation.

See the case schema in the approved plan (docs/tests/ draft, evolved) for
the rationale behind each field. Summary:

- `{ns}` in any string field is expanded to a namespace unique to the case
  (derived deterministically from the case id), so cases never collide with
  each other inside the shared suite database, and are reproducible without
  needing a fresh random suffix.
- `setup` commands run before the case and are NOT asserted — if one fails,
  the case becomes ERROR (infrastructure), never FAIL. This lets cases build
  their own prerequisites (e.g. an experiment to add a model to) without the
  suite depending on case execution order, unlike the manual roteiro.
- A setup step can `capture` a named value out of its own stdout via a
  regex with one capture group (e.g. an `--add-run`'s printed run_id).
  Captured names become additional `{placeholder}`s available in every
  later setup step, the main command, and db assertions — the same
  mechanism `{ns}` uses. This exists specifically so a case can act on an
  ID the CLI only reveals at creation time (e.g. removing then
  re-targeting a specific run by id), not derivable from `{ns}` alone.
- `fixture.database` controls DB isolation granularity: "shared" (default)
  runs against the one suite-wide database; "fresh" | "absent" | "corrupt"
  get their own scratch file, for the handful of cases that need to observe
  first-run initialization behavior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_NS_SAFE = re.compile(r"[^a-z0-9_]+")


def namespace_for(case_id: str) -> str:
    """Deterministic, filesystem/SQL-safe namespace for a case id.

    "CE-001" -> "t_ce001". Deterministic (not randomized) so that a suite
    run is reproducible and the database stays legible to a human reading
    the case id next to the experiment name it produced.
    """
    slug = _NS_SAFE.sub("", case_id.lower())
    return f"t_{slug}"


def expand_placeholders(value: Any, replacements: dict[str, str]) -> Any:
    """Recursively substitute '{key}' in strings, lists, and dicts for
    every key in `replacements` (e.g. {"ns": "...", "run_id": "..."})."""
    if isinstance(value, str):
        for key, val in replacements.items():
            value = value.replace(f"{{{key}}}", val)
        return value
    if isinstance(value, list):
        return [expand_placeholders(v, replacements) for v in value]
    if isinstance(value, dict):
        return {k: expand_placeholders(v, replacements) for k, v in value.items()}
    return value


def expand_ns(value: Any, ns: str) -> Any:
    """Recursively substitute '{ns}' in strings, lists, and dicts."""
    return expand_placeholders(value, {"ns": ns})


@dataclass(frozen=True)
class Fixture:
    env: str = "env_valid_minimal"
    dataset: str = "dataset_small_valid"
    database: str = "shared"  # shared | fresh | absent | corrupt

    def __post_init__(self):
        if self.database not in ("shared", "fresh", "absent", "corrupt"):
            raise ValueError(
                f"fixture.database must be one of shared|fresh|absent|corrupt, got {self.database!r}"
            )


@dataclass(frozen=True)
class DbAssertion:
    query: str
    equals: Any = None
    params: tuple = ()


@dataclass(frozen=True)
class DbExpectation:
    assertions: tuple[DbAssertion, ...] = ()
    unchanged_tables: tuple[str, ...] = ()


@dataclass(frozen=True)
class Expect:
    exit_code: int = 0
    stdout_contains: tuple[str, ...] = ()
    stderr_contains: tuple[str, ...] = ()
    stdout_not_contains: tuple[str, ...] = ()
    no_traceback: bool = True


@dataclass(frozen=True)
class KnownIssue:
    ref: str
    note: str = ""


@dataclass(frozen=True)
class SetupStep:
    argv: tuple[str, ...]
    capture: dict[str, str] = field(default_factory=dict)  # name -> regex (one group), applied to this step's stdout


@dataclass(frozen=True)
class Case:
    id: str
    name: str
    area: str
    profiles: tuple[str, ...]
    source_file: Path
    tags: tuple[str, ...] = ()
    priority: str = "normal"
    requires: tuple[str, ...] = ()  # openrouter | llamacpp | fake-api
    fixture: Fixture = field(default_factory=Fixture)
    setup: tuple[SetupStep, ...] = ()
    argv: tuple[str, ...] = ()
    timeout: int = 30
    expect: Expect = field(default_factory=Expect)
    db: DbExpectation = field(default_factory=DbExpectation)
    known_issue: KnownIssue | None = None

    @property
    def namespace(self) -> str:
        return namespace_for(self.id)

    def _replacements(self, captured: dict[str, str] | None) -> dict[str, str]:
        return {"ns": self.namespace, **(captured or {})}

    def resolved_argv(self, captured: dict[str, str] | None = None) -> list[str]:
        replacements = self._replacements(captured)
        return [expand_placeholders(a, replacements) for a in self.argv]

    def resolved_setup_step(self, step: SetupStep, captured: dict[str, str] | None = None) -> list[str]:
        replacements = self._replacements(captured)
        return [expand_placeholders(a, replacements) for a in step.argv]

    def resolved_db_assertions(self, captured: dict[str, str] | None = None) -> list[DbAssertion]:
        replacements = self._replacements(captured)
        out = []
        for a in self.db.assertions:
            out.append(DbAssertion(
                query=a.query,
                equals=a.equals,
                params=tuple(expand_placeholders(p, replacements) for p in a.params),
            ))
        return out


class CaseValidationError(Exception):
    pass


def _parse_expect(raw: dict) -> Expect:
    return Expect(
        exit_code=raw.get("exit_code", 0),
        stdout_contains=tuple(raw.get("stdout_contains", []) or []),
        stderr_contains=tuple(raw.get("stderr_contains", []) or []),
        stdout_not_contains=tuple(raw.get("stdout_not_contains", []) or []),
        no_traceback=raw.get("no_traceback", True),
    )


def _parse_db(raw: dict) -> DbExpectation:
    assertions = tuple(
        DbAssertion(
            query=a["query"],
            equals=a.get("equals"),
            params=tuple(a.get("params", []) or []),
        )
        for a in raw.get("assertions", []) or []
    )
    return DbExpectation(
        assertions=assertions,
        unchanged_tables=tuple(raw.get("unchanged_tables", []) or []),
    )


def _parse_setup_step(raw_step) -> SetupStep:
    """A setup entry is either a plain argv list (no capture — the
    original, still-supported form), or a mapping {argv: [...], capture:
    {name: regex}} when the step needs to capture a value from its own
    stdout for later steps/the main command/db assertions to use."""
    if isinstance(raw_step, dict):
        return SetupStep(
            argv=tuple(raw_step["argv"]),
            capture=dict(raw_step.get("capture", {}) or {}),
        )
    return SetupStep(argv=tuple(raw_step))


def parse_case(raw: dict, source_file: Path) -> Case:
    missing = [k for k in ("id", "name", "area", "profiles", "command") if k not in raw]
    if missing:
        raise CaseValidationError(f"{source_file}: missing required field(s): {missing}")

    command = raw["command"]
    if "argv" not in command:
        raise CaseValidationError(f"{source_file} ({raw['id']}): command.argv is required")

    fixture_raw = raw.get("fixture", {}) or {}

    known_issue_raw = raw.get("known_issue")
    known_issue = (
        KnownIssue(ref=known_issue_raw["ref"], note=known_issue_raw.get("note", ""))
        if known_issue_raw
        else None
    )

    return Case(
        id=raw["id"],
        name=raw["name"],
        area=raw["area"],
        profiles=tuple(raw["profiles"]),
        source_file=source_file,
        tags=tuple(raw.get("tags", []) or []),
        priority=raw.get("priority", "normal"),
        requires=tuple(raw.get("requires", []) or []),
        fixture=Fixture(
            env=fixture_raw.get("env", "env_valid_minimal"),
            dataset=fixture_raw.get("dataset", "dataset_small_valid"),
            database=fixture_raw.get("database", "shared"),
        ),
        setup=tuple(_parse_setup_step(s) for s in raw.get("setup", []) or []),
        argv=tuple(command["argv"]),
        timeout=command.get("timeout", 30),
        expect=_parse_expect(raw.get("expect", {}) or {}),
        db=_parse_db(raw.get("db", {}) or {}),
        known_issue=known_issue,
    )


def load_cases(cases_dir: Path) -> list[Case]:
    """Load every *.yaml file in cases_dir (one or more cases per file).

    A file may contain a single case mapping, or a top-level `cases:` list
    of case mappings. Raises CaseValidationError on duplicate ids or
    malformed cases — fails loudly rather than silently dropping a case.
    """
    cases: list[Case] = []
    seen_ids: dict[str, Path] = {}

    for path in sorted(cases_dir.glob("**/*.yaml")):
        with open(path, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        if doc is None:
            continue

        raw_cases = doc["cases"] if isinstance(doc, dict) and "cases" in doc else [doc]

        for raw in raw_cases:
            case = parse_case(raw, path)
            if case.id in seen_ids:
                raise CaseValidationError(
                    f"Duplicate case id {case.id!r}: {seen_ids[case.id]} and {path}"
                )
            seen_ids[case.id] = path
            cases.append(case)

    return cases
