---
type: normative
audience: ai
last-validated: 2026-08-21
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
| `--reasoning` | `experiment`, `model` | `None` (only THIS field — see "Reasoning Effort/Tokens Exclusivity" below) | `reasoning.effort` **omitted** from the request; a validly-inherited/independently-resolved `reasoning.max_tokens` is unaffected and still applies unless it's ALSO absent |
| `--max-tokens` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--reasoning-tokens` | `experiment`, `model` | `None` (only THIS field) | `reasoning.max_tokens` **omitted**; a validly-inherited/independently-resolved `reasoning.effort` is unaffected — see below |
| `--temperature` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--top-p` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--top-k` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--repeat-penalty` | `experiment`, `model` | `None` | **Not sent** in API request (API server default) |
| `--model-seed` | `experiment`, `model` | `None` | **Not sent** in API request (breaks inheritance from the experiment's own MODEL_SEED — same mechanism as `--provider system-default`) |
| `--vision` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--structured` | `experiment`, `model` | `None` | **Not sent** in API request |
| `--provider-lock` | `experiment` | `None` (treated as not-enabled) | Same effect as `false` — no per-variant PROVIDER resolution is required before execution; see "Provider and Provider-Lock Semantics" below |
| `--provider` | `model` | `None` (no provider pinned) | Breaks inheritance from the experiment; no `provider` preference sent in the API request — see "Provider and Provider-Lock Semantics" below |
| `--add-questions` / `--questions` | `questions` | All available | Use all questions from dataset, ignoring `.env` `DEFAULT_QUESTIONS` |
| `--where` | `questions` | No inclusion filtering | Apply no filter (ignore `.env` `QUESTIONS_STATUS_ADD`); combining `system-default` with a concrete `key=value` filter in the same flag's occurrences is a contradiction and must be rejected (exit 2) |
| `--exclude` | `questions` | No exclusion filtering | Apply no filter (ignore `.env` `QUESTIONS_STATUS_EXCLUDE`); same contradiction rule as `--where` |

**`--add-questions`/`--where`/`--exclude` implementation status:** implemented 2026-08-19 (CLI Typer migration Fase 4 marco 4A) via `src/core/special_config_values.py::normalize_filter_list_or_system_default` — a list-aware counterpart to the scalar `normalize_special_config_values`, since these three are `action="append"`/list-typed and structurally incompatible with the scalar-only mechanism `--seed`/`--reasoning`/etc. use. Wired into both `src/cli/bcllm_questions.py` (standalone, `handle_add_questions` — previously not wired to `parse_args_normalized` at all) and `src/cli/bcllm_experiment.py` (composite, `_create_question_snapshots`). Full detail and regression coverage: `docs/status/known-issues.md` Resolved Issues.

**Pattern:** For most parameters, `system-default` means **do not send in API request**, allowing the API server's own defaults to activate.

### What "Not Sent" Actually Means (three distinct shapes, 2026-08-21)

"Not sent" is not one uniform mechanism — depending on the parameter, it means one of three different things, and conflating them is itself a source of bugs (see the Reasoning Effort/Tokens Exclusivity section below, and `docs/status/known-issues.md` for the concrete bugs this distinction was written to prevent recurring):

1. **Absence of a top-level field** — the common case (`--temperature`, `--top-p`, `--max-tokens`, `--model-seed`, etc.): the resolved value is `None`, and `build_chat_completion_payload` omits that key from the payload dict entirely (`if value is not None: payload[key] = value`). No `null` is ever sent.
2. **Absence of a subfield within a nested structure** — `--reasoning`/`--reasoning-tokens`: each independently controls one subfield (`effort`/`max_tokens`) of the single `reasoning` object. `system-default` on one subfield omits ONLY that subfield; the object itself is included only if at least one subfield survives, and dropped entirely (never sent as `reasoning: {}`) if both are absent.
3. **Absence of a whole derived structure** — `--vision`/`--structured`/`--system-prompt`: these don't map to a fixed key at all. `system-default` (or `false`/absent) means the message-building/payload logic that would have PRODUCED that structure (a multimodal content block, a `response_format` object, an extra system message) simply never runs — there is no field to omit because the structure was never built. See "Configuration That Alters Request Structure" below.

### API Configuration vs. Local/Structural Configuration

Every SUPPORTED parameter falls into one of these in terms of WHERE `system-default` takes effect:

- **Direct payload field** (shape 1 above): `--temperature`, `--top-p`, `--top-k`, `--repeat-penalty`, `--max-tokens`, `--model-seed`, `--provider`, plus `--reasoning`/`--reasoning-tokens` (shape 2). `system-default` changes what `build_chat_completion_payload` sends to the API.
- **Configuration that alters request structure** (shape 3): `--vision`, `--structured`, `--system-prompt`, `--user-prompt`. `system-default` doesn't omit a field so much as prevent optional content/structure from being added — it must never remove content the question itself requires (the user/assistant message pair is never optional).
- **Local or structural configuration with no direct payload equivalent**: `--randomization-seed` (controls `AnswerRandomizer` locally, never sent to the API), `--provider-lock` (a completeness *gate* checked before execution, not a payload field), `--add-questions`/`--where`/`--exclude` (which snapshots get created — a selection decision, not a request parameter). `system-default` here changes local/DB-side behavior, never the request payload directly.

### Reasoning Effort/Tokens Exclusivity (normative, 2026-08-21)

OpenRouter's `reasoning` object accepts only ONE of `effort`/`max_tokens` — see `docs/Manuais_Diversos/openrouterdocs/reasoning_tokens.md` ("One of the following (not both)"). `--max-reasoning` was removed entirely (2026-08-21) — it was a true, undocumented synonym of `--reasoning-tokens` (both fed the exact same `MODEL_MAX_TOKENS_REASONING` key), not a distinct parameter; see `docs/status/known-issues.md`.

- **Same-layer conflict is a usage error.** A single `--create-experiment`/`--add-model` command passing a concrete value for BOTH `--reasoning` and `--reasoning-tokens` is rejected at parse time, exit code 2 — never silently resolved by priority (`src/cli/commands/{model,experiment}.py`'s command bodies).
- **A concrete value is a complete mode selection that suppresses the sibling's inheritance**, even across layers. `--reasoning high` (or `--reasoning none` — a concrete choice, not an absence) at model-add time, with NO `--reasoning-tokens` passed at all, still forces `MODEL_MAX_TOKENS_REASONING` to `None` even if the experiment has a validly-inherited value for it. The reverse is symmetric for a concrete `--reasoning-tokens`. Implemented in `ConfigResolver._resolve_reasoning_pair`.
- **`system-default` is NOT a mode selection.** `--reasoning system-default` only clears the effort field at this layer — if a valid `--reasoning-tokens` value exists (explicit or inherited), it still applies. Symmetric for `--reasoning-tokens system-default`.
- **`--reasoning-tokens` rejects 0 and negative values** as a usage error (exit 2), not silently treated as `None`/`system-default`. Anthropic's documented floor is 1024 tokens regardless of what's requested, so persisting a literal `0` would misrepresent what actually happens at execution (reasoning stays enabled with ≥1024 tokens spent). `--reasoning none` already exists as the explicit, honest way to disable reasoning — it sends `effort: "none"`, distinct from omitting the `reasoning` object entirely.
- **`--reasoning none` is a real, explicit choice, never collapsed.** It is sent to the API as `effort: "none"` — `Planner._build_model_config` must never treat it as equivalent to "not configured" (that collapse used to silently re-enable reasoning whenever a `MODEL_MAX_TOKENS_REASONING` value was also present — see `docs/status/known-issues.md`).

---

## Configuration That Alters Request Structure (`--vision`, `--structured`, `--system-prompt`, `--user-prompt`)

These four don't have a fixed payload key to check for absence — `system-default` (or the flag's own "disabled" value) must be verified by its **semantic effect**, not by grepping for a key name:

- **`--vision system-default`** → no multimodal content block, no vision-specific transformation of the message, and no inherited vision configuration applied — but the question's own required text content is still sent unmodified.
- **`--structured system-default`** → no `response_format`/schema included in the payload, and no inherited structured-output configuration applied.
- **`--system-prompt system-default`** → no system message is added by this configuration. The run's own resolved value is `None`, and — per the run/experiment inheritance contract — nothing is re-inherited from the experiment for this run once its own config is frozen at creation (`ConfigResolver.build_run_config_dict` bakes in inheritance at creation time; `Planner` must read the run's own frozen value directly, never re-inherit at execution time — see `docs/status/known-issues.md` for the bug where a redundant execution-time fallback silently defeated this).
- **`--user-prompt system-default`** → no additional template/content beyond what the question itself requires is applied; same frozen-at-creation, no-re-inheritance rule as `--system-prompt`.

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
| `--source-file` | `questions` | Structural: the dataset file path must be explicitly provided, same reasoning as `--url` |
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
