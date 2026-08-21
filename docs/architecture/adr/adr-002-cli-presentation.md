---
type: adr
audience: both
date: 2026-08-18
status: accepted
---

# ADR-002: CLI Presentation Architecture (Typer/Rich migration, Fase 1)

**Status:** Accepted
**Date:** 2026-08-18
**Context:** The CLI (`bcllm.py` + `src/cli/bcllm_*.py`) is being migrated
from 8 independent `argparse.ArgumentParser` instances to Typer, with a
centralized Rich-based presentation layer, per user directive. The
external command surface (every flag, its name, type, and special values
like `system-default`) is explicitly **not** changing — this migration
modernizes the implementation, not the interface a user types. Before any
code changes, two foundational decisions needed to be made explicit: what
the CLI is contractually allowed to promise about its own output
(`docs/contracts/interaction-contracts.md` was a placeholder, and its own
text says it "MUST be completed before UI-related work begins"), and
whether the existing flag-presence-based dispatcher
(`src/core/mode_resolver.py` / `module_resolver.py` / `mode_matrix.py`)
survives the migration.

## Decision

1. **`docs/contracts/interaction-contracts.md` Section 2 (CLI Output
   Boundaries) is now normative**, scoped deliberately to five concerns:
   stdout carries results only, stderr carries diagnostics only, exit
   codes are `0`/`1`/`2`/`130` with fixed meanings, `--output json` (when
   implemented) is ANSI-free and stream-pure, and no-color/non-TTY
   disables Rich styling without changing text content. Sections 1
   (Review UI Boundaries), 3 (Event Emission), and 4 (Logging Boundaries)
   remain placeholders — deliberately deferred, not silently dropped. The
   *visual* design of console output (tables, panels, theme, color
   palette) is explicitly out of scope for this contract and for this
   phase of the migration; it is a Fase 6 presentation-layer decision.

2. **The mode/module dispatcher is kept, not replaced.** The CLI's
   external form stays flag-based
   (`--create-experiment`/`--experiment --add-model`/`--execute`, not
   `bcllm <group> <action>`), so the problem `mode_resolver.py` +
   `module_resolver.py` + `mode_matrix.py` solve — routing an argv to the
   right handler when the same flag can mean different things in
   different combinations — still exists after the migration. Typer
   replaces `argparse.ArgumentParser` per module (parameter declarations,
   validation, help/error rendering), invoked programmatically by the
   existing dispatcher; it is not exposed as a public subcommand tree.

3. **Two known bugs in the dispatcher are fixed as part of this phase,
   not deferred**: `--questions` is missing from
   `module_resolver.py`'s `ADD_ACTION_FLAGS`/`PRIORITY_FLAGS`, so
   `bcllm --experiment X --questions "1-5"` is silently swallowed by the
   `--experiment` show-path instead of being routed as a filter; and
   `bcllm.py`'s TOCTOU `IntegrityError` handler always re-raises
   regardless of branch, contradicting its own "continue on existing
   experiment" comment. Both are mechanical, deterministic fixes with no
   business-rule ambiguity (see the "correções prévias" phase of the
   migration plan for the full list and process).

4. **`docs/contracts/configuration-hierarchy.md` and `determinism.md` had
   a documentation gap, not a behavior gap**: the top-level precedence
   ladder in `configuration-hierarchy.md` lists "CLI Arguments" as
   highest, but every concrete per-key chain in that same file (seed,
   prompts, model params) and the seed chain in `determinism.md` omitted
   CLI entirely. `config_resolver.py` does consult `cli_args` first
   everywhere it resolves a value — verified by reading every
   `resolve_*`/`build_*_config_dict` method. Fixed as a documentation-only
   correction in this same phase (both files, all four chains — no ADR
   needed on its own, no invariant changes): see each file's inline
   "Fixed 2026-08-18" note. Caught initially only for
   `configuration-hierarchy.md`; the Essence Guardian review of this ADR
   flagged that `determinism.md` had the identical, untracked gap, fixed
   in the same pass.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|--------------|
| Full contract completion (all 4 sections of interaction-contracts.md) before any migration code | Rejected by explicit user decision — Review UI Boundaries, Event Emission, and full Logging Boundaries have no urgency yet and would delay the migration for invariants nothing currently depends on; narrowing to Section 2 keeps the gate meaningful without over-scoping it |
| Replace the flag-based CLI with a `bcllm <group> <action>` subcommand tree | Rejected by explicit user decision — external command syntax is fixed; only the internal implementation changes |
| Let Typer's own subcommand dispatch replace `mode_resolver`/`module_resolver`/`mode_matrix` | Not possible without the subcommand tree above; the ambiguity these modules resolve (same flag, different meaning by combination) has no Typer-native equivalent for a flat, non-subcommand CLI |

## Consequences

### Positive
- The migration now has a concrete, checkable output contract instead of
  inferring one ad hoc per command as it's rewritten.
- `bcllm --help`, exit codes, and stream discipline (stdout/stderr) are
  now protected by a contract the Essence Guardian can check against,
  not just convention.
- Two real routing bugs get fixed with unambiguous justification instead
  of being carried forward silently.

### Negative
- The contract is still incomplete (3 of 4 sections) — a future
  contributor could mistake "interaction-contracts.md is normative" for
  "interaction-contracts.md is complete." The status line and per-section
  markers exist specifically to prevent that.
- Keeping the dispatcher means the migration does not get to simplify
  away `mode_resolver.py`/`module_resolver.py`/`mode_matrix.py`, which
  together are non-trivial machinery whose only job is disambiguating a
  flag-based interface — a cost accepted in exchange for not changing
  the CLI's external form.

### Neutral
- No database schema or execution-pipeline change of any kind — this ADR
  is scoped entirely to the CLI/presentation layer.

## Contracts Affected

- [contracts/interaction-contracts.md](../../contracts/interaction-contracts.md) — Section 2 (CLI Output Boundaries) filled in and made normative; Sections 1/3/4 explicitly left as placeholders.

## Related Documents

- `C:\Users\rockm\.claude\plans\deep-growing-dragon.md` — the full CLI Typer/Rich migration plan this ADR is Fase 1 of.
- [reference/cli-commands.md](../../reference/cli-commands.md) — current documented command surface (had known drift from code — `--create-run` vs `--add-run` corrected 2026-08-20 as part of marco 4B's `bcllm_run.py` migration; `--data-set` and the composite-flow example contradiction remain open, to be corrected as their affected groups are migrated).
- [contracts/configuration-hierarchy.md](../../contracts/configuration-hierarchy.md) — per-key chains corrected to include CLI precedence explicitly (documentation-only, see Decision 4).
- [contracts/determinism.md](../../contracts/determinism.md) — seed inheritance chain corrected the same way (documentation-only, see Decision 4).
- [status/known-issues.md](../../status/known-issues.md) — new entry tracking that current (pre-migration) CLI output has not been audited against `interaction-contracts.md` Section 2; to be closed incrementally as each group migrates in Fase 4.
- [contracts/data-auditability.md](../../contracts/data-auditability.md) — logging philosophy referenced by interaction-contracts.md Section 4.
