# BCLLM CLI Test Suite

Automated black-box test suite for `bcllm.py`. Runs the real CLI (never a
copy of it) against an isolated sandbox database, so a broken command is
caught by `python tests/cli_suite/run.py` instead of by whoever runs it
manually next.

## Run it

```bash
python tests/cli_suite/run.py --profile smoke
```

- First run creates `tests_workspace/` (git-ignored) next to the repo root.
- If it already exists, you'll be asked whether to wipe it — pass `--yes`
  to skip the prompt (CI), or `--keep` to reuse it as-is.
- Ctrl+C at any point cancels cleanly: remaining cases are marked
  `SKIPPED`, and the report is still written.
- After the run: `tests_workspace/report.md` (human) and `report.json`
  (machine/AI, and input to `--compare`), plus one shared SQLite database
  (`tests_workspace/data/bcllm_test.db`) and log
  (`tests_workspace/logs/benchmark.log`) you can inspect by hand.

Profiles: `smoke`, `cli-unit`, `contracts`, `integration-mock`,
`regression`, `full`. A case runs under a profile when the profile name
appears in its `profiles:` list (`full` always runs everything).

By default all `--execute` cases hit a local HTTP stub (started
automatically), never the real network. Two opt-in flags exist for the
cases tagged `requires: [openrouter]` / `requires: [llamacpp]`:

```bash
# real OpenRouter, cheap model only — BLOCKED without --openrouter-model-id
python tests/cli_suite/run.py --profile full --openrouter --openrouter-model-id <cheap-model-id>

# local llama.cpp-compatible server — health-checked first, BLOCKED if unreachable
python tests/cli_suite/run.py --profile full --llamacpp --llamacpp-url http://127.0.0.1:8080
```

## Add a case

Add a case (or a whole new YAML file) under `cases/`. See the schema
comments in `runner/case.py` and the existing files for examples. No code
change is needed — `run.py` discovers every `*.yaml` under `cases/`
automatically, and `runner/coverage.py` reports (each run) which real CLI
flags still have no case at all.

## Naming an ID the CLI only reveals at creation time

Some scenarios need to act on a specific run/variant/snapshot ID (e.g.
"remove this run, then try to execute it by ID again") — an ID that
doesn't exist until a setup step creates it and prints it. A setup step
can capture such a value out of its own stdout with a regex, making it
available as `{name}` in every later setup step, the main command, and db
assertions — the same substitution mechanism `{ns}` already uses:

```yaml
setup:
  - argv: ["--experiment", "{ns}_x", "--add-run"]
    capture:
      run_id: "ID: (run_[0-9a-f]+)"   # regex needs exactly one capture group
  - ["--experiment", "{ns}_x", "--remove-run", "{run_id}"]
command:
  argv: ["--experiment", "{ns}_x", "--execute", "--run", "{run_id}"]
db:
  assertions:
    - query: "SELECT status FROM runs WHERE run_id = ?"
      params: ["{run_id}"]
      equals: "removed"
```

See `tests/cli_suite/cases/run.yaml::RN-004`/`RN-005` for a real example
(the latter is the regression test for the removed-run reactivation bug
described in `docs/status/known-issues.md`). A setup step without
`capture` can still be written as a plain list, `["--flag", "value"]` —
the dict form (`{argv: [...], capture: {...}}`) is only needed when
capturing something.

## Remove a command

Delete the case(s) exercising it. If the underlying CLI flag was actually
removed from `src/cli/`, `runner/coverage.py` will flag any case YAML still
referencing it under "flag(s) used in cases but no longer in the CLI" —
fix that before it silently rots.

## States

`PASS · FAIL · PARTIAL · EXPECTED_FAILURE · UNEXPECTED_PASS · BLOCKED ·
NOT_IMPLEMENTED · PENDING_SPEC · SKIPPED · ERROR` — see `runner/states.py`
for what each means. `EXPECTED_FAILURE`/`UNEXPECTED_PASS` exist because a
real slice of the CLI is currently dead by routing (see
`docs/status/known-issues.md`); a case documenting that with `known_issue:`
turns "still broken" into `EXPECTED_FAILURE` instead of drowning the report
in expected red, and turns "someone fixed it" into a visible
`UNEXPECTED_PASS` instead of silence.

## Design notes

See the plan this suite was built from for the full rationale (sandbox via
`DATABASE_PATH` instead of copying source, single shared DB/log with
per-case namespacing, the `variant_signature`/`BASE_URL` limitation this
suite works around by using `test/<scenario>` model ids, etc.) —
`docs/status/known-issues.md` and `docs/tests/` carry the durable version
of that context.
