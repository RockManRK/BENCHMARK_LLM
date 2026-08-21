---
type: status
audience: ai
last-validated: 2026-08-19
status: active
---

# Checkpoint: `questions` system-default logic, baseline before Typer structural conversion

**Addendum (2026-08-19, same day, after this checkpoint was first written):** between this checkpoint and the start of the actual Typer conversion, a separate, larger architectural fix was implemented and approved as its own checkpoint — see `docs/status/known-issues.md`'s Resolved Issues entry *"Composite `--add-*` flow bypassed `parse_args_normalized` entirely... ('same action, same path')"*. That fix touched `bcllm_model.py`/`bcllm_questions.py`/`bcllm_run.py`/`bcllm.py` (the `NonExitingArgumentParser`/`ParserExit` mechanism, the Request/Result-dataclass action pattern, the shared `run_add_*` adapters, the seed-parsing unification, and the composite-flow rollback-on-usage-error fix). **The numeric baseline below is therefore stale for whole-repo comparisons** — it predates that fix. The 4 behavioral properties in sections 1–4 below are unaffected (nothing in the "same action, same path" fix touched filter-combination logic, the contradiction rule, or the "usage error before connection" invariant — it only fixed composite failing to *apply* that invariant consistently) and remain accurate. The fresh, post-architecture-fix numeric baseline (still pre-Typer-conversion) is recorded in the known-issues.md entry linked above: `cli_suite --profile full` = 44 PASS + 1 EXPECTED_FAILURE (unchanged in aggregate — two composite-flow cases, `AQ-003`/`AQ-004`, had their exit-code/message *expectations* corrected to match now-consistent standalone/composite behavior, not a regression); `pytest` (same exclusions) = 966 passed, 48 failed, 18 skipped, 39 errors (48/18/39 byte-identical to every prior baseline this session, including the one below — zero regression, only new passing tests added). **Use that entry's numbers, not this file's, as the pre-Typer-conversion baseline.**

**Purpose:** Freeze and document the exact behavior of `--add-questions`/`--where`/`--exclude` (and their `system-default` handling, implemented earlier the same day — see `docs/status/known-issues.md` Resolved Issues) **before** `src/cli/bcllm_questions.py` and `src/cli/bcllm_experiment.py` are converted from `argparse` to Typer (CLI migration Fase 4 marco 4A, structural step). The Typer conversion that follows this checkpoint must preserve every property below exactly — it is a mechanical rewrite, not a behavior change. Any test that regresses against this checkpoint after the conversion is a bug in the conversion, not a reason to "fix" the semantics.

**Addendum (2026-08-20 — marco 4A conversion complete):** the Typer conversion this checkpoint gated has now happened for both modules (`src/cli/commands/questions.py`, `src/cli/commands/experiment.py`, `create_parser()` removed from both). Every property in sections 1–4 below was verified preserved — not assumed — via `tests/unit/cli/test_questions_standalone_composite_parity.py` (real argv through the new Typer parser, both flows) and the existing `test_questions_system_default.py`/`test_question_snapshot_equivalence.py` suites, all re-run and passing unchanged. This file's own narrative (argparse-specific mechanics: `parser.error()`, `argparse.ArgumentError`, `parse_args_normalized()`) describes the **pre-conversion implementation** and is kept as-is as a historical record of what the conversion had to preserve — it does not describe current code. See `docs/status/known-issues.md`'s "CLI Typer migration marco 4A" Resolved Issues entry for the current implementation and full verification.

**Numeric baseline recorded at the time this checkpoint was first written (superseded — see addendum above):**
- `python tests/cli_suite/run.py --profile full --yes`: **44 PASS + 1 EXPECTED_FAILURE**
- `pytest -q --ignore=tests/test_error_collector.py --ignore=tests/test_model_capabilities.py`: **944 passed, 48 failed, 18 skipped, 39 errors**

The 48 failed / 18 skipped / 39 errors are pre-existing, unrelated, and have been byte-identical across every verification run this entire session (see `known-issues.md`'s Resolved Issues entries) — they are not this checkpoint's concern. Only regressions in the **passed** count, or in cli_suite's PASS/FAIL states, matter for this specific comparison.

---

## 1. Multiple `--where` are combined by AND

**Behavior:** A question is included only if it matches **every** `--where` filter given (repeating the flag adds conditions, all of which must hold).

**Where implemented:** `src/cli/bcllm_questions.py::matches_filters` (identical logic reused by `bcllm_experiment.py`'s composite path via the shared `filter_questions`/`matches_filters` import):
```python
if include_filters:
    for field, value in include_filters:
        if _get_nested_field(question, field) != value:
            return False   # any mismatch rejects the question -> AND
```

**Status:** Explicit user decision (2026-08-19, this session, before marco 4A began): *"múltiplos --where representam condições combinadas por AND... A repetição da flag é deliberadamente permitida e não deve gerar erro."* Confirmed, not inferred.

**Test coverage:** `tests/unit/cli/test_questions_system_default.py::TestMultipleConcreteFiltersAllowed::test_standalone_multiple_where_and_combined`; `tests/unit/core/test_normalize_filter_list.py::TestConcreteFiltersPassThrough::test_multiple_concrete_filters_allowed_and_unchanged` (the list-normalization layer that lets multiple concrete values through unchanged, distinct from the AND-application logic itself, which lives in `matches_filters`).

---

## 2. Semantics of multiple `--exclude`

**Behavior:** A question is excluded if it matches **any** `--exclude` filter given (repeating the flag adds conditions; matching just one is enough to exclude — **OR**, not AND).

**Where implemented:** Same `matches_filters` function:
```python
if exclude_filters:
    for field, value in exclude_filters:
        if _get_nested_field(question, field) == value:
            return False   # any match rejects the question -> OR (across exclude conditions)
```

**Status — important distinction from point 1:** this is **pre-existing, unchanged behavior** — no code in this session touched `matches_filters`' combination logic itself (only the `system-default`/list-normalization layer feeding into `include_filters`/`exclude_filters` was added). During the original investigation (this session, before the dedicated system-default fix), the user explicitly asked to *"documente e peça decisão específica sobre a combinação de múltiplos --exclude antes de implementá-la"* — that specific decision request was about whether OR is the **intended** semantics going forward, and it was never explicitly answered, because implementation never touched this logic (there was nothing to "implementá-la" for — the combination logic already existed, untouched, before and after this session's work).

**This checkpoint documents current behavior; it does not constitute the requested decision.** The upcoming Typer conversion must preserve OR-semantics for `--exclude` exactly as-is (per "preserve behavior," not because it has been confirmed correct). If a future session decides AND is actually wanted for `--exclude`, that is a semantic change requiring the same explicit-decision process as any other ambiguous item — not something the Typer conversion should touch, silently or otherwise.

**Test coverage:** No dedicated unit test exercises multi-`--exclude` OR-combination specifically (only single-exclude and single-include cases are covered by this session's new tests) — `matches_filters` itself has no direct unit test file found; its behavior is exercised indirectly through `filter_questions`/`handle_add_questions` integration paths. **Gap noted, not fixed here** — worth a dedicated `test_matches_filters.py` if/when `--exclude`'s intended semantics gets its explicit decision.

---

## 3. `system-default` combined with a concrete value returns exit code 2

**Behavior:** `--where system-default --where status=valid` (or the `--exclude` equivalent, or `system-default` repeated) is rejected as a contradiction, exit code 2, before any handler runs.

**Where implemented:** `src/core/special_config_values.py::normalize_filter_list_or_system_default` raises `ValueError` when `'system-default'` appears alongside any other value (including itself, repeated) in the same list. Both `bcllm_questions.py::main()` and `bcllm_experiment.py::main()` catch this the same way they catch `argparse.ArgumentError` — `except ValueError as e: parser.error(str(e))` — `parser.error()` is argparse's own usage-error path, always exit code 2.

**Test coverage:**
- `tests/unit/core/test_normalize_filter_list.py::TestContradictionRejected` (4 cases: concrete+system-default either order, system-default repeated, case-insensitive repeat) — pure function, no CLI involved.
- `tests/unit/cli/test_questions_system_default.py::TestContradictionExitsWithCode2` — real `main()` invocation via `pytest.raises(SystemExit)`, `.code == 2` asserted directly, for both `--where` and `--exclude`.
- `tests/cli_suite/cases/questions.yaml::AQ-008` — real subprocess, real exit code, real (empty) DB state asserted via `unchanged_tables`.

---

## 4. Usage errors occur before any connection or write

**Behavior:** Every `system-default`-related rejection (FORBIDDEN scalar flags, and the filter-list contradiction from point 3) happens during argument parsing/normalization, structurally before `get_database_connection()` is ever called — so before any table is even opened for writing, let alone written to.

**Where implemented:** In every CLI module's `main()` (`bcllm_experiment.py`, `bcllm_model.py`, `bcllm_run.py`, `bcllm_provider.py`, `bcllm_questions.py`), the `try/except argparse.ArgumentError / except ValueError` block wrapping `parse_args_normalized()` (+ `normalize_filter_list_or_system_default()` calls, where applicable) is the **first** thing `main()` does; `conn = get_database_connection()` is the line immediately after that `try/except` block, never before it.

**Test coverage:**
- `tests/unit/cli/test_questions_system_default.py::TestNoWriteBeforeUsageError` — `src.cli.bcllm_questions.get_database_connection` mocked via `unittest.mock.patch`, `mock_conn.assert_not_called()` after a `SystemExit(2)` is raised, for both a FORBIDDEN scalar (`--source-file system-default`, `--experiment system-default`) case.
- `tests/cli_suite/cases/questions.yaml::AQ-008`/`AQ-009`, `experiment.yaml::CE-010`/`CE-011`, `model.yaml::AM-009`/`AM-010`, `run.yaml::RN-008` — real subprocess + real DB assertions (`unchanged_tables` or `COUNT(*) = 0`) proving no row was ever written, across every FORBIDDEN flag in every module, not just `questions`.

---

## `normalize_filter_list_or_system_default` is CLI-framework-independent

Confirmed by direct inspection of `src/core/special_config_values.py`: the function's signature is `(values: list[str] | None) -> list[str] | ForceSystemDefault`, its body references only `values`, `FORCE_SYSTEM_DEFAULT`, and the stdlib `ValueError` — **zero** references to `argparse` or any CLI-framework type anywhere in the function (the module itself imports `argparse` at the top, but only the sibling scalar function `normalize_special_config_values` uses it, for `argparse.ArgumentError`/`argparse.Action`). This was a deliberate design choice, not an accident: it is exactly what lets this function be called unchanged from `main()`'s current `argparse`-based code today, and from a Typer callback (or command body) after the conversion, with the caller responsible for translating its `ValueError` into whatever exit-2 mechanism the framework in use provides (`parser.error()` today; a `typer.BadParameter`/`typer.Exit(2)`-shaped wrapper after conversion).

---

## Ground rules for the upcoming Typer conversion (per explicit user instruction, 2026-08-19)

- **Structural only.** Preserve behavior, persistence, and external CLI syntax exactly. No flag renamed, no default changed, no new validation added, no existing validation removed.
- **Any new bug or semantic decision discovered during the conversion must be separated from the migration and presented before being fixed** — not corrected inline as part of the "mechanical" rewrite, per this project's established process for ambiguous/nuanced findings.
- This checkpoint (the 4 documented properties + the numeric baselines above) is what "preserved behavior" is measured against when the conversion is verified.
