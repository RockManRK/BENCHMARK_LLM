---
type: normative
audience: ai
last-validated: 2026-08-19
status: active
---

# System-Default Semantics Contract

**Scope:** `system-default` instruction behavior  
**Invariant:** `system-default` explicitly bypasses inheritance and uses the system's built-in default behavior

---

## Contract Statement

The `system-default` instruction is an **explicit user directive** to ignore all inherited configuration (including `.env`) and use the system's built-in default behavior for that parameter.

---

## What `system-default` Means

When a user sets a parameter to `system-default`:

1. **Inheritance is broken** — Do not check `.env`, experiment, or any parent level
2. **System built-in default is used** — Each parameter has a defined system default
3. **Intent is explicit** — This is not "use whatever is configured above"; it is "use system behavior"

---

## Three-Way Classification

Every CLI parameter falls into exactly one of three categories with respect to `system-default`:

- **SUPPORTED** — `system-default` has real, valid semantics for this parameter. The value is recognized and converted to the internal `FORCE_SYSTEM_DEFAULT` sentinel (`src/core/special_config_values.py`).
- **FORBIDDEN** — the parameter identifies a specific entity or structural choice. `system-default` (and the deprecated `'null'` literal) is **recognized specifically so it can be explicitly rejected** with a usage error (exit code 2) — never silently accepted, and never silently treated as a literal identifier either (a `--run system-default` must fail as "system-default is not a valid value for --run", not merely as "run 'system-default' not found").
- **NOT_APPLICABLE** — the parameter is not a configuration value at all (a boolean flag, a list-typed selector not yet covered by this mechanism). `system-default` is never inspected; whatever value is given (including the literal string `"system-default"`) passes through untouched to whatever validation already exists for that parameter.

Implementation: `src/core/special_config_values.py::normalize_special_config_values` takes explicit `supported`/`forbidden` sets of dest names per CLI module — eligibility is opt-in, never inferred from argparse metadata (`default=None`/`required=False`). See `docs/status/known-issues.md` ("`_is_nullable_arg`'s blanket sweep...") for the bug this replaced: the previous heuristic silently misclassified identity-selector flags as configuration values.

---

## SUPPORTED Parameters

| Parameter | Module(s) | System Default Behavior | Effect |
|-----------|-----------|------------------------|--------|
| `--randomization-seed` | `experiment`, `run` | `None` | Randomization **disabled**; use original order A, B, C, D |
| `--system-prompt` | `experiment`, `run` | `None` | **Not sent** in API request |
| `--user-prompt` | `experiment`, `run` | `None` | **Not sent** in API request |
| `--reasoning` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--max-reasoning` | `experiment`, `model` | `None` | **Not sent** in API request (alias of `--reasoning-tokens`, same `MODEL_MAX_TOKENS_REASONING` key) |
| `--max-tokens` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--reasoning-tokens` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--temperature` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--top-p` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--top-k` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--repeat-penalty` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--vision` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--structured` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--provider-lock` | `experiment` | `None` (treated as not-enabled) | Same effect as `false` — no per-variant PROVIDER resolution is required before execution; see "Provider and Provider-Lock Semantics" below |
| `--provider` | `model` | `None` (no provider pinned) | Breaks inheritance from the experiment; no `provider` preference sent in the API request — see "Provider and Provider-Lock Semantics" below |
| `--add-questions` / `--questions` | `questions` | All available | Use all questions from dataset, ignoring `.env` `DEFAULT_QUESTIONS` |
| `--where` | `questions` | No inclusion filtering | Apply no filter (ignore `.env` `QUESTIONS_STATUS_ADD`); combining `system-default` with a concrete `key=value` filter in the same flag's occurrences is a contradiction and must be rejected (exit 2) |
| `--exclude` | `questions` | No exclusion filtering | Apply no filter (ignore `.env` `QUESTIONS_STATUS_EXCLUDE`); same contradiction rule as `--where` |

**`--add-questions`/`--where`/`--exclude` implementation status:** implemented 2026-08-19 (CLI Typer migration Fase 4 marco 4A) via `src/core/special_config_values.py::normalize_filter_list_or_system_default` — a list-aware counterpart to the scalar `normalize_special_config_values`, since these three are `action="append"`/list-typed and structurally incompatible with the scalar-only mechanism `--seed`/`--reasoning`/etc. use. Wired into both `src/cli/bcllm_questions.py` (standalone, `handle_add_questions` — previously not wired to `parse_args_normalized` at all) and `src/cli/bcllm_experiment.py` (composite, `_create_question_snapshots`). Full detail and regression coverage: `docs/status/known-issues.md` Resolved Issues.

**Pattern:** For most parameters, `system-default` means **do not send in API request**, allowing the API server's own defaults to activate.

---

## FORBIDDEN Parameters

`system-default` (and the deprecated `'null'` literal) is explicitly rejected with a usage error (exit code 2) for these parameters — never silently accepted, never silently treated as a literal value either:

| Parameter | Module(s) | Why |
|-----------|-----------|-----|
| `--create-experiment` | `experiment` | Identity: the experiment's name, required explicitly |
| `--experiment` | `experiment`, `model`, `run`, `provider` (`questions` too, once wired — see the Fase 4 note above) | Identity: which experiment to act on. `required=True` everywhere except `experiment`'s own show-mode, but classified FORBIDDEN in every module regardless — a required field never needed protection from the old blanket-sweep bug, but the same "never silently treat system-default as a literal identifier" principle applies uniformly to every identity selector, not only the ones the old bug happened to touch (found by Essence Guardian review, 2026-08-19, as an inconsistency in the first version of this fix — `bcllm_experiment.py` had it, the other three modules didn't) |
| `--remove-experiment` | `experiment` | Identity: which experiment to remove (command currently disabled entirely — see `docs/status/known-issues.md` — but the flag-level classification still applies) |
| `--url` | `experiment`, `model` | Structural: the API endpoint must be explicitly provided (not a "system default" concept) |
| `--add-model` | `model` (scalar form only — `experiment`'s composite-flow `--add-model` is `action="append"`, NOT_APPLICABLE for now, see below) | Identity: the model ID being added |
| `--remove-model` | `model` | Identity: the variant being removed |
| `--run` | `run` | Identity: which run to show |
| `--remove-run` | `run` | Identity: which run to remove |
| `--remove-question` | `questions` (target semantics — module not yet wired to this mechanism, see Fase 4 note above) | Identity: which snapshot to remove |
| `--source-file` | `questions` (target semantics — same caveat) | Structural: the dataset file path must be explicitly provided, same reasoning as `--url` |
| `--add-run` | `run` | Structural command (boolean flag; listed for completeness, not independently enforceable as a value) |
| `--execute` | `execute` | Structural command (boolean flag; listed for completeness) |

**Rationale:** These parameters identify a specific entity or structural choice; `system-default` has no meaningful interpretation for them, and treating the literal string as an ordinary (invalid) identifier would produce a misleading "not found" error instead of an honest "this parameter doesn't accept system-default" one.

---

## NOT_APPLICABLE Parameters (not configuration values)

Not part of this mechanism at all — boolean flags with no value (`--list-experiments`, `--list-models`, `--list-questions`, `--list-runs`, `--resolve-providers`), and list-typed identity selectors not yet covered by the scalar-only mechanism (`--add-model` on `bcllm_experiment.py`'s composite flow, `action="append"`). `--output`/`--format` (currently dead flags, deferred to a future presentation-layer decision) are also out of scope here.

---

## Resolution Behavior

When `system-default` is encountered:

```python
# CORRECT: system-default bypasses inheritance
if value == FORCE_SYSTEM_DEFAULT:
    return None  # Use system built-in default
    # Do NOT check .env or parent levels

# WRONG: system-default should not check inheritance
if value == FORCE_SYSTEM_DEFAULT:
    return env.get(key)  # VIOLATION: Still checking .env!
```

**Implementation:** `src/core/special_config_values.py` — `FORCE_SYSTEM_DEFAULT` constant

---

## `system-default` vs Not Specified

There is a critical difference:

| Scenario | Behavior |
|----------|----------|
| Parameter **not specified** | Inherit from next level in hierarchy |
| Parameter = `system-default` | **Bypass** hierarchy; use system built-in default |

### Example

```bash
# Case 1: Not specified → inherits from .env
bcllm --create-experiment my_exp
# Randomization Seed comes from .env RANDOMIZATION_SEED or system default

# Case 2: Explicit system-default → bypasses .env
bcllm --create-experiment my_exp --randomization-seed system-default
# Randomization Seed is None (no randomization), ignoring .env
```

---

## Violation Examples

### ❌ WRONG: Checking .env after system-default

```python
# VIOLATION: system-default should bypass .env
if value == FORCE_SYSTEM_DEFAULT:
    return os.environ.get("RANDOMIZATION_SEED")  # Still checking env!
```

### ✅ CORRECT: Bypassing inheritance

```python
# CORRECT: system-default returns None immediately
if value == FORCE_SYSTEM_DEFAULT:
    return None  # Use system built-in default
```

### ❌ WRONG: Treating system-default as inheritance

```python
# VIOLATION: system-default is NOT "use parent value"
if value == "system-default":
    return experiment_config.get("RANDOMIZATION_SEED")  # WRONG!
```

### ✅ CORRECT: Recognizing explicit instruction

```python
# CORRECT: system-default is user instruction to bypass hierarchy
if cli_value == FORCE_SYSTEM_DEFAULT:
    return None  # System built-in default for Randomization Seed
```

---

## Special Case: `--add-questions`

For question selection, `system-default` means:
- Use **all available questions** from the dataset
- Apply no filtering (ignore `.env` QUESTIONS_STATUS_ADD/EXCLUDE)

```bash
# Add all questions, ignoring .env filters
bcllm --experiment my_exp --add-questions system-default
```

---

## Provider and Provider-Lock Semantics

Confirmed 2026-08-19 by reading `src/core/planner.py`, `src/core/execution_engine.py`, and `src/core/config_resolver.py` directly (not assumed). `--provider` (per-variant, set at `--add-model` time) and `--provider-lock` (per-experiment, set at `--create-experiment` time) are two independently-resolved values that combine at execution time:

- **`--provider SLUG` explicit** — fixes the variant's provider, **regardless of `--provider-lock`**. Stored as `variant.config["PROVIDER"]`. At execution, `Planner._get_variant_provider()` reads it as `PlanVariant.resolved_provider`, and `ExecutionEngine` includes `provider: {"only": [SLUG], "allow_fallbacks": False}` in the request payload whenever `resolved_provider` is not `None` — this genuinely prevents fallback to any other provider (confirmed: the payload uses `only` + `allow_fallbacks: False`, never `order` alone, which would only prioritize a list without blocking fallback).
- **`--provider-lock true`** is a **completeness guarantee**, not a payload-construction switch: `Planner.build_plan()` unconditionally calls `_validate_provider_lock()`, which — only when `PROVIDER_LOCK` is `true` in the experiment config — requires every model variant in the experiment to have `PROVIDER` resolved (non-`None`) before execution is allowed to proceed at all. If any variant is unresolved, `PlannerValidationError` aborts the entire plan with a message pointing to `--resolve-providers`.
- **`--provider system-default`** breaks inheritance from the experiment and leaves the variant's `PROVIDER` explicitly absent (`None`) — `config_resolver.py::_resolve_cli_or_experiment` already implements this correctly (`FORCE_SYSTEM_DEFAULT` → `None`, no fallback).
- **Provider absent (`None`) + `--provider-lock false`** — `_validate_provider_lock()` returns immediately (lock not enabled); `resolved_provider` is `None`; the request payload never gains a `provider` key at all; OpenRouter performs its own default routing (may fall back across providers).
- **Provider absent (`None`) + `--provider-lock true`** — execution is blocked entirely (`PlannerValidationError`) until every variant's provider is resolved and persisted (typically via `--resolve-providers`).

---

## Related Contracts

- [configuration-hierarchy.md](configuration-hierarchy.md) — Where system-default fits in hierarchy
- [determinism.md](determinism.md) — Randomization Seed system-default disables randomization

---

**This contract is non-negotiable.** `system-default` semantics ensure users can explicitly bypass inheritance when needed.
