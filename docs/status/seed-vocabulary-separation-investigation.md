---
type: status
audience: ai
last-validated: 2026-08-20
status: checkpoint-a-implemented
---

# Investigation: separating Randomization Seed from Model Seed

**Checkpoint A implemented and verified 2026-08-20.** This document remains the original pre-implementation survey (producers/consumers of every seed-related symbol, the Planner bug this investigation found, proposed names, affected files, risks, tests) — kept as-is for historical reference rather than rewritten after the fact. For the completed implementation's description, exact final symbol names, regression coverage, and verified baseline, see the Resolved Issues entry "Randomization Seed vocabulary separated from Model Seed..." in `docs/status/known-issues.md`. Checkpoint B (Model Seed, §3/§4 below) remains proposed only — not started, per explicit instruction to keep the two checkpoints in separate diffs.

---

## 0. The most important finding first

**`Planner._resolve_seed_effective` (`src/core/planner.py:531-586`) can silently override a Run's own, explicitly-frozen "no randomization" decision with the Experiment's seed — for every real run, not an edge case.**

```python
run_seed = run_config.get("RUN_RESPONSES_SEED")
if run_seed is not None:
    return self._normalize_seed_value(run_seed)
# falls through to the experiment's seed
```

`run.config["RUN_RESPONSES_SEED"]` is **always present as a key** after a real run creation (`ConfigResolver.build_run_config_dict` unconditionally returns `{"RUN_RESPONSES_SEED": resolved_seed, ...}` — confirmed by reading its return statement, `src/core/config_resolver.py:623-627`). So `run_config.get(...)` returning `None` **always** means "this run's seed was explicitly resolved to `None` at creation time" — never "key absent." `dict.get()` cannot distinguish "key maps to `None`" from "key missing," and this code uses that ambiguity as if it were the latter: it falls back to the experiment's seed whenever the run's own seed is `None`, silently re-applying experiment-level inheritance **at every `--execute`**, even though `build_run_config_dict` already resolved and froze the run's seed once, at creation time, per `docs/contracts/immutability.md`'s "Run configuration is frozen at creation."

Concretely: an experiment has `RUN_RESPONSES_SEED=42`. A run is created with `--randomization-seed system-default` (per the user's new spec: "system-default: interromper a herança e resolver para None") — the run's own config correctly stores `RUN_RESPONSES_SEED: None`. At `--execute` time, `_resolve_seed_effective` sees `run_seed is None`, falls through, and uses the experiment's `42` anyway — **silently ignoring the run's own explicit choice**. The bug is not hypothetical or rare; it fires for every run whose own resolved seed is `None`, which is the normal, common case for "don't randomize this run."

**This must be fixed as part of Checkpoint A** — the user's Run semantics ("None significa não randomizar," "cada novo Run pode receber um Randomization Seed próprio," Run immutability) cannot hold with this bug present, regardless of any renaming. The fix is small and localized: distinguish "key present with value `None`" from "key absent" via `"RUN_RESPONSES_SEED" in run_config` instead of `run_seed is not None`. Since the key is *always* present for a correctly-created run, the correct behavior is almost certainly: **never fall back to the experiment at `_resolve_seed_effective` time at all** — the fallback that mattered already happened once, at run-creation time. The experiment-config fallback branch (`src/core/planner.py:583-586`) may need to become dead code (kept only for defensive robustness against a row from before this fix, if any exist — none do, pre-production, per the "no historical compatibility" instruction) rather than live inheritance logic. Proposing this precisely as part of Checkpoint A's plan below, not deciding unilaterally here.

---

## 1. Producers and consumers of each symbol

### `--seed` (CLI flag)

| Where | Role |
|---|---|
| `src/cli/bcllm_experiment.py:110-113` | Defines `--seed` on the experiment-creation parser (`type` unset → str), no format validation at parse time. |
| `src/cli/bcllm_run.py:117-122` | Defines `--seed` on the run parser (`type=str`). `parse_add_run_request` (pure parse phase) validates its *format* via `parse_seed_value_strict` before any connection opens. |
| `src/cli/bcllm_run.py` (`AddRunRequest.seed` field) | Structured request field, threaded into `add_run_action` → `ConfigResolver.build_run_config_dict`. |
| `bcllm.py::_build_create_argv` / `_build_action_argv` | Forwards `--seed` into **both** the experiment-creation parse AND `--add-run`'s own parse when both are present in one composite command — the reason yesterday's "invalid `--seed` with `--add-run` present → exit 2 vs. exit 1 without it" disclosed behavior split exists. |
| `docs/contracts/*.md`, `docs/reference/cli-commands.md`, `docs/reference/configuration-reference.md` | Documented (see §3 below — several entries are stale/self-contradictory). |
| `tests/test_config_resolver.py`, `tests/unit/cli/test_bcllm_run_same_action_same_path.py`, `tests/unit/cli/test_composite_flow_rollback.py`, `tests/cli_suite/cases/{experiment,run}.yaml` | ~180+ references total across these files — the bulk of the test-impact surface (§9). |

**No other module defines a `--seed` flag.** `bcllm_model.py` has no seed flag today — confirms `MODEL_SEED`/`--model-seed` genuinely doesn't exist yet, not just under a different name.

### `RUN_RESPONSES_SEED` (config key)

| Where | Role |
|---|---|
| `.env` / `.env.example` | `RUN_RESPONSES_SEED=AUTO` — the actual, real .env key consulted (confirmed by direct read). |
| `src/core/config_resolver.py:440` | `build_experiment_config_dict`'s `resolve_seed(..., env_key="RUN_RESPONSES_SEED", ...)` call — the only place `.env` is actually consulted for this. |
| `src/core/config_resolver.py:506` | Stored into a new experiment's `config_json` as `"RUN_RESPONSES_SEED": resolved_seed if resolved_seed is not None else "OFF"` — **the source of the `"OFF"` sentinel bug already in `known-issues.md`.** |
| `src/core/config_resolver.py:600, 624` | `build_run_config_dict`'s experiment-inheritance fallback and the run's own returned config key. |
| `src/core/planner.py:579, 586, 608` | `_resolve_seed_effective`/`_normalize_seed_value` read this key from both `run.config` and `experiment.config_json` (see §0 for the bug here) and are the ONLY place that still recognizes `"OFF"`/`"NULL"`/`"NONE"`/`""` as textual sentinels — a second, independent implementation of "parse a possibly-stringly-typed seed," duplicating (with different rules) `parse_seed_value_strict`. |
| `src/db/schema.py` | Not a column — lives inside the `experiments.config_json`/`runs.config` JSON blobs, never a dedicated column. |
| `docs/reference/configuration-reference.md:118,293`, `docs/reference/cli-commands.md:41`, `docs/reference/database-schema.md` | Documented (matches code's real key name — these are the *accurate* docs). |
| `docs/contracts/configuration-hierarchy.md:42,184`, `docs/contracts/system-default-semantics.md:134,150`, and `resolve_seed`'s own docstring examples (`config_resolver.py:104,211,222-231`) | Use **`RANDOM_SEED`** instead — see §2, this is a real, unresolved naming divergence between code and several docs/docstrings. |

### `resolved_seed` (local variable name, 2 independent instances)

- `build_experiment_config_dict` (`config_resolver.py:438`) — experiment-level, never resolves `AUTO`.
- `build_run_config_dict` (`config_resolver.py:589,594,598,602,606,609`) — run-level, resolves `AUTO` to a concrete int via `_generate_seed_from_run`.

Not a shared function — each is a local variable inside its own method, both independently computing "what should this entity's `RUN_RESPONSES_SEED` be." No cross-module consumers of the name itself (it never crosses a function boundary), but the DUPLICATION of "parse a seed value, handle AUTO" logic between these two methods, plus the dead `resolve_seed_for_run` (below), plus `Planner._normalize_seed_value`, means there are **effectively 3 independent implementations of seed-string parsing in this codebase today**, two of which (`build_run_config_dict`'s inline logic, `_normalize_seed_value`) don't call the shared `parse_seed_value_strict` at all for their "what counts as OFF" step.

### `resolve_seed_for_run` — **dead code**

`src/core/config_resolver.py:257-306`. Confirmed by grep: **zero production callers** anywhere in `src/`; only exercised directly by `tests/test_config_resolver.py`. The real run-creation path (`build_run_config_dict`) has its own separate, inline duplicate of this exact logic instead of calling it. This was already known (flagged in an earlier session), unchanged since. Given "não manter compatibilidade histórica" and "não implementar nada antes de apresentar" — flagging for an explicit decision in Checkpoint A: delete it, or make `build_run_config_dict` actually call it (eliminating the duplication either way)? Proposed below in §4.

### `randomization_seed` (persisted field / audit column)

| Where | Role |
|---|---|
| `src/db/schema.py` (`responses` table) | Column `randomization_seed INTEGER` — the seed *actually used* for that specific response's shuffle, captured at execution time, independent of `Run.seed_effective`'s own value (they're normally equal, but this column is the audit-of-record, not a derived/recomputed value). |
| `src/core/execution_engine.py:106,132,167,751,782,826` | `ExecutionResult.randomization_seed` field; set from `run.seed_effective` per item (line 751), read back for the persisted `Response` object (line 826). |
| `src/core/result_writer.py:233,264` | Persists it into the `responses` row. |
| `migrations/add_randomization_columns.py` | The (single, already-applied) migration that added this + the other 4 randomization audit columns — not a live migration path, historical record only. |

### `option_letter_map` / `options_presented` / `correct_option_presented` / `randomization_enabled`

All four, together with `randomization_seed`, are the complete Randomization Seed audit trail on `responses` (§6 below) — same producer/consumer set: `AnswerRandomizer.randomize_options()` produces the shuffle result, `ExecutionEngine` captures it into `ExecutionResult`, `ResultWriter.write_result()` persists all five columns together. **None of these four relate to Model Seed in any way** — confirmed, no code path connects them to model configuration.

### `AUTO`

- **Experiment level:** `resolve_seed` (`config_resolver.py:191-255`) explicitly does **not** resolve it — returns the string `"AUTO"` unchanged, stored verbatim in the experiment's `config_json`. Confirmed correct against the user's spec (§2 of their message) — recommend preserving this semantic unchanged, only renaming the surrounding vocabulary.
- **Run level:** `build_run_config_dict` (`config_resolver.py:586-609`) is the **only** place `"AUTO"` is ever resolved to a concrete integer (`_generate_seed_from_run(run_id, experiment_id)` — a deterministic hash, not `random`). Confirmed: after a run is created, its stored `RUN_RESPONSES_SEED` is never the string `"AUTO"` — matches "AUTO nunca pode existir em um Run persistido."
- `resolve_seed_for_run` (dead code) also resolves `AUTO`, duplicating the logic `build_run_config_dict` actually uses live.
- `Planner._normalize_seed_value` does **not** know about `"AUTO"` at all — if it ever received the literal string `"AUTO"` (which, per the above, should never happen for a correctly-created run), its `int("AUTO")` attempt would raise `ValueError`, caught, returning `None` (silently disabling randomization) rather than erroring loudly. Worth a defensive test even though the string shouldn't reach this point.

### `"OFF"` (and `"NULL"`/`"NONE"`/`""`)

- **Written** by `build_experiment_config_dict` (`config_resolver.py:506`) — the *only* production write site, and only for `"OFF"` specifically (not the other three).
- **Read/recognized** by `Planner._normalize_seed_value` (`planner.py:606-613`) — all four strings (`"OFF"`, `"NULL"`, `"NONE"`, `""`), case-insensitive after `.strip().upper()`.
- **Rejected** by `parse_seed_value_strict` (`config_resolver.py:30-86`) — raises `ValueError` for all of these (this is the function CLI parsing/`build_run_config_dict` uses) — meaning `"OFF"` is simultaneously (a) written into experiment config by one function, (b) silently tolerated/normalized by the planner, and (c) rejected as invalid input by the strict parser everything else uses. This inconsistency is exactly yesterday's `known-issues.md` bug and is fully in scope for Checkpoint A's "eliminar OFF" requirement.
- Per the user's explicit instruction, none of `"OFF"`/`"NULL"`/`"NONE"`/`""` should be written OR accepted anywhere after Checkpoint A — `build_experiment_config_dict` must store real JSON `null` (Python `None`) instead, and `Planner._normalize_seed_value`'s four-string recognition becomes unreachable dead code to remove (no historical rows to support, per the pre-production instruction).

---

## 2. Naming divergence: `RANDOM_SEED` vs `RUN_RESPONSES_SEED` — needs your decision, not assumed

The user's message says "flag omitida: consultar RANDOM_SEED no .env," matching **several existing docs and docstrings** (`configuration-hierarchy.md:42`, `system-default-semantics.md:134,150`, `resolve_seed`'s own docstring examples) — but the **real, live `.env` key and the real code's `env_key` argument is `RUN_RESPONSES_SEED`** (confirmed: `.env` file, `.env.example`, `config_resolver.py:440`'s actual call, `configuration-reference.md:118,293`, `cli-commands.md:41` all agree on `RUN_RESPONSES_SEED`). Per `CLAUDE.md`'s "code wins unless an ADR states otherwise," the docs/docstrings using `RANDOM_SEED` are the stale ones — but since the user's own message independently uses that same (stale) name, I'm flagging this explicitly rather than assuming which way to resolve it:

- **Option A (recommended):** keep the `.env` key as `RUN_RESPONSES_SEED`, matching the user's own vocabulary section ("configuração atual: `RUN_RESPONSES_SEED`" — labeled *current*, not proposed-new) and the majority of accurate docs. Fix the stale `RANDOM_SEED` references in `configuration-hierarchy.md`/`system-default-semantics.md`/docstrings to say `RUN_RESPONSES_SEED` instead (or a renamed key, see below).
- **Option B:** actually rename the `.env` key to `RANDOM_SEED` (or something else), updating `.env`/`.env.example`/every doc/every code reference — larger, and contradicts the user's own "configuração atual: RUN_RESPONSES_SEED" framing.

Separately: should `RUN_RESPONSES_SEED` (the config-dict/`.env` key itself) be renamed at all as part of this vocabulary cleanup — e.g. to `RANDOMIZATION_SEED`, matching the new `--randomization-seed` flag and "Randomization Seed" terminology exactly? The user's message doesn't explicitly ask for this (only the CLI flag rename is explicit), but leaving the config key as `RUN_RESPONSES_SEED` while the CLI flag becomes `--randomization-seed` and the vocabulary section calls it "Randomization Seed" throughout is itself a small residual inconsistency. Flagging as an open naming question for Checkpoint A's approval, not deciding here.

---

## 3. Names that need to change to eliminate ambiguity (proposed, exact)

| Current | Proposed | Where |
|---|---|---|
| `--seed` (bcllm_experiment.py, bcllm_run.py) | `--randomization-seed` | Both parsers. Per instruction: **remove entirely, no alias.** |
| `AddRunRequest.seed` | `AddRunRequest.randomization_seed` | `src/cli/bcllm_run.py` |
| `parse_seed_value_strict` | Keep name (already generic/qualifier-free by design — used by both concepts' format validation) OR rename to `parse_int_seed_strict` if Model Seed reuses it (see §7) | `src/core/config_resolver.py` |
| `resolve_seed` | `resolve_randomization_seed` | `config_resolver.py:191` |
| `resolve_seed_for_run` | Delete (dead code) OR rename to `resolve_randomization_seed_for_run` if kept — **needs your decision, see §1** | `config_resolver.py:257` |
| `_generate_seed_from_name` / `_generate_seed_from_run` | `_generate_randomization_seed_from_name` / `..._from_run` | `config_resolver.py:308,324` — these are AUTO-generation helpers specific to randomization; keeping them qualifier-free risks a future Model Seed AUTO feature (explicitly not wanted per §3 of the user's message) reusing them by mistake. |
| `build_experiment_config_dict`'s local `resolved_seed` | `resolved_randomization_seed` | `config_resolver.py:438` |
| `build_run_config_dict`'s local `resolved_seed` / `cli_seed` / `exp_seed` | `resolved_randomization_seed` / `cli_randomization_seed` / `exp_randomization_seed` | `config_resolver.py:586-609` |
| `Planner._resolve_seed_effective` | `_resolve_randomization_seed_effective` | `planner.py:531` |
| `Planner._normalize_seed_value` | `_normalize_randomization_seed_value` | `planner.py:588` |
| `PlanRun.seed_effective` | `PlanRun.randomization_seed_effective` | `src/core/execution_plan.py:334` |
| `ExecutionResult.randomization_seed` | Already correctly qualified — **no change.** | `execution_engine.py` |
| `run.seed_effective` (all call sites: `bcllm_execute.py:359`, `async_orchestrator.py:291`, `execution_engine.py:312,450,478,751`) | `run.randomization_seed_effective` | Follows from the `PlanRun` rename above. |

**New names needed for Model Seed (doesn't exist yet):** `--model-seed` (CLI), `MODEL_SEED` (config key), `AddModelRequest.model_seed`, `ModelConfig.model_seed`, a `resolve_model_seed` method (or reuse `_resolve_cli_or_experiment`, which already exists and is generic — see §7), `model_seed` field on `variant_signature`'s `SIGNATURE_FIELD_ORDER`, a `seed` parameter on `OpenRouterClient.chat_completion()` (the API's own field name, not ours to rename) fed from `model_config.model_seed`.

---

## 4. Documents using "seed" without qualification (audit)

| File | Issue |
|---|---|
| `docs/contracts/determinism.md:34-70,123-160` | Entire "Seed-Based Randomization" section uses bare "seed" throughout — needs a full pass to say "Randomization Seed" explicitly, since Model Seed will also affect determinism (differently) once it exists. |
| `docs/contracts/configuration-hierarchy.md:39-42,75,93,99,115,125-126,173-199` | Bare "seed" throughout; **also contains a real, standalone bug independent of naming** — see §5. |
| `docs/contracts/system-default-semantics.md:47,134-174` | Bare "seed"; also uses `RANDOM_SEED` (§2). |
| `docs/contracts/data-auditability.md:47` | "Seed, prompts, and model parameters are traceable" — lumps Randomization Seed in with "model parameters" without distinguishing it from the *soon-to-exist* Model Seed, which genuinely *is* a model parameter. |
| `docs/reference/cli-commands.md:41,94,291,297` | Bare "seed"; also the mutability bug (§5). |
| `docs/reference/configuration-reference.md:118,200,251,293` | Bare "seed" in table entries. |
| `docs/reference/database-schema.md` | Documents the `responses.randomization_seed` column — already correctly qualified; needs a note added once `model_variants`/`model_variants.config`'s `MODEL_SEED` and its own audit trail (the `seed` key inside `responses.request_json`) exist. |
| `docs/status/known-issues.md` (yesterday's `"OFF"` entry) | Already correctly says "Randomization Seed" implicitly via `RUN_RESPONSES_SEED`/`--add-run` context — no fix needed, just cross-reference from the new Checkpoint A entry. |

`docs/.archive/**` and `docs/maestro/plans/archive/**` were excluded from this audit — per `CLAUDE.md`, the archive is not current reference and its ~15 additional "seed" hits (from the earlier grep) don't need updating.

---

## 5. A second documentation bug found: "Experiment seed can be changed after creation" — false, contradicts immutability

**Two files assert this, and it is not true of the real code:**
- `docs/contracts/configuration-hierarchy.md:125` — "**Experiment seed:** Can be changed; does not affect existing runs"
- `docs/reference/cli-commands.md:94` — "Can change seed (doesn't affect existing runs)" (under `--experiment <name>`'s "Modification Rules")

**Confirmed false by direct inspection:** `bcllm_experiment.py` defines `--seed` exactly once, on the shared parser used only by `--create-experiment` (`create_parser()`, line 110). `main()`'s only two branches for `args.experiment` (not `args.create_experiment`) are `handle_show_experiment` (read-only) and `handle_modify_provider_lock` (the one, already-known, already-flagged-in-`known-issues.md` exception that actually rewrites `config_json`/`config_hash`). **No code path modifies an experiment's seed after creation.** `configuration-hierarchy.md:99` even shows `experiment_config["seed"] = 123  # VIOLATION` as a *bad* example two lines away from line 125's claim that changing it is fine — the document contradicts itself internally, independent of matching or not matching real code.

This is exactly the kind of text §8 of the user's message asks me to find ("permita modificar Experiment ou Run após criação") — both instances need correcting to say the experiment's Randomization Seed (and Model Seed, once it exists) are frozen at creation exactly like everything else in `config_json`, with the same status as the `--provider-lock` exception (a separate, already-documented tension, not something to conflate with seed).

Also stale: `configuration-hierarchy.md:180-184` shows a `resolve_seed(cli_value=..., run_config=..., experiment_config=..., env_key="RANDOM_SEED")` call signature that **does not match** the real method (`resolve_seed(self, cli_value, env_key, experiment_name)` — no `run_config`/`experiment_config` parameters exist). Aspirational/outdated example, needs correcting alongside the rename.

---

## 6. Fields that currently guarantee randomization auditability

Exactly five columns on `responses` (`src/db/schema.py`), all written together by `ResultWriter.write_result()` (`result_writer.py:233,263-267`), all sourced from `AnswerRandomizer.randomize_options()`'s return value via `ExecutionEngine`:

1. `randomization_enabled` (bool) — was shuffling on for this specific response.
2. `randomization_seed` (int, nullable) — the actual seed used (or `NULL` if disabled).
3. `options_presented` (JSON) — the options in the order actually shown to the model.
4. `correct_option_presented` (str) — which presented letter was correct, in the presented space.
5. `option_letter_map` (JSON) — mapping from presented letter back to the original.

Together these let any response be fully reconstructed and verified independent of re-running anything — this is the Randomization Seed's entire auditability contract, and it's already complete and correct today. **Model Seed's auditability, once it exists, is different and separate:** it lives in `responses.request_json` (the full captured API request payload — already persisted, already captures every other model parameter the same way) plus `model_variants.config`'s frozen `MODEL_SEED` and the `variant_signature` string itself. No new dedicated column is needed for Model Seed the way `randomization_seed` exists for the other concept — `request_json` and `config` already are the audit trail for every other model parameter, and Model Seed should follow the exact same pattern, not get special treatment.

---

## 7. Where `MODEL_SEED` needs to enter, layer by layer (exact locations)

| Layer | File / location | Change |
|---|---|---|
| CLI flag | `src/cli/bcllm_model.py::create_parser()` | New `--model-seed` argument, `type=str` (same pattern as the numeric flags using `parse_int_or_system_default` — reuse that, since Model Seed is a plain int like `--top-k`, not a specially-parsed value like Randomization Seed's AUTO-aware format). |
| Classification | `bcllm_model.py::SYSTEM_DEFAULT_SUPPORTED` | Add `'model_seed'` — `system-default` breaks inheritance → `None`, matching every other model-level flag (`--temperature`, `--top-p`, etc.) exactly, per the user's explicit "MODEL_SEED é uma configuração de modelo, equivalente em nível a: reasoning; temperature; ..." framing. |
| Request dataclass | `AddModelRequest` (`bcllm_model.py`) | New field `model_seed: int \| ForceSystemDefault \| None = None`. |
| ConfigResolver | `ConfigResolver.build_model_config_dict` (`config_resolver.py:629+`) | New `"MODEL_SEED": self._resolve_cli_or_experiment(getattr(cli_args, 'model_seed', None), exp_config, "MODEL_SEED", parse_int)` entry — reuses the *existing*, already-generic `_resolve_cli_or_experiment` helper (no new resolution mechanism needed; it already implements exactly "CLI > experiment > None," matching the user's specified hierarchy precisely) and the existing `parse_int` local closure already used for `MODEL_TOP_K`/`MODEL_MAX_TOKENS_TOTAL`. |
| Experiment config | `ConfigResolver.build_experiment_config_dict` (`config_resolver.py:410+`) | New `"MODEL_SEED"` entry alongside the other 10 model-level defaults already there (`BASE_URL`, `MODEL_MAX_TOKENS_REASONING`, etc.) — Model Seed belongs at the Experiment level too (per the user's spec: "pertence ao Experiment e à model_variant") for the same reason those other 10 model-level defaults do: a variant that doesn't specify its own value inherits the experiment's frozen default. |
| `model_variants.config` | Written automatically once the above two are in place — no separate change (same mechanism as every other model-level key). | |
| `variant_signature` | `src/utils/variant_signature.py::SIGNATURE_FIELD_ORDER` | Insert `('MODEL_SEED', 'model_seed')` — position per the user's own conceptual example (`reasoning`, `vision`, `structured`, **`model_seed`**, `temp`, `top_p`, ...) — i.e. right after `STRUCTURED_OUTPUTS`, before `MODEL_TEMPERATURE`. |
| `ModelConfig` (execution-time) | `src/core/execution_plan.py::ModelConfig` | New field `model_seed: int \| None = None`. |
| `Planner._build_model_config` | `src/core/planner.py:618-662` | New `model_seed=config.get("MODEL_SEED")` — no normalization needed (unlike Randomization Seed, Model Seed is never a string sentinel; `parse_int_or_system_default` at the CLI layer already guarantees it's a clean int or `None` by the time it's in `config_json`). |
| `ExecutionPlan` | No new field needed — `ModelConfig` (above) is already reached via `PlanVariant.model_config_effective`, which `ExecutionEngine` already reads. | |
| `ExecutionEngine` | Two places, both must be updated together (pre-existing duplication, not new — see below) — `execution_engine.py:656-669` (`api_client.chat_completion(...)` real call) and `execution_engine.py:557-628` (the separate audit-log `request_payload` mirror used only for `request_json`). | Add `seed=model_config.model_seed` to the real call; add `if model_config.model_seed is not None: request_payload["seed"] = model_config.model_seed` to the mirror. **Risk:** these two payload-construction blocks are already independently maintained today (confirmed: `client.py`'s payload and `execution_engine.py`'s `request_payload` are two separate dict-building blocks with the same shape) — a real, pre-existing duplication risk, not introduced by this change, but Model Seed inherits it unless deduplicated as part of Checkpoint B. |
| API client | `src/api/client.py::OpenRouterClient.chat_completion()` | New parameter `seed: int \| None = None`; `if seed is not None: payload["seed"] = seed` — follows the exact existing pattern for every other optional field (confirmed: this is a "add if not None" payload builder throughout, already the exact semantics the user asked for — "omitir completamente a chave seed" when `None`). |
| Request audit | `responses.request_json` | Automatic once the two `request_payload`/`payload` builders above include it — no separate change; this is Model Seed's auditability trail (§6). |
| Presentation/export | `bcllm_model.py::handle_list_models` (prints `config` dict — already generic, no change needed) and any `--output json/csv` export path (not yet implemented — `docs/status/known-issues.md`'s "Export Format Limitations" already covers this gap generally) | No dedicated change beyond what already happens automatically via `config`'s JSON serialization. |

---

## 8. Does the payload strip `None`-valued keys?

**Yes, confirmed, everywhere already** — both `src/api/client.py::chat_completion()` and `src/core/execution_engine.py`'s `request_payload` mirror use the identical `if <value> is not None: payload[key] = <value>` pattern for every single optional field (`temperature`, `top_p`, `top_k`, `repeat_penalty`, `max_tokens`, `stop`, `response_format`, `provider`) with zero exceptions. `MODEL_SEED` following this exact same pattern is not a new mechanism — it's applying an existing, consistent, already-well-tested convention to one more field.

---

## 9. Test and documentation impact (scale, not exhaustive line-by-line)

**Tests (rough counts from grep, to size the work — not all lines need changes, this is the search surface):**
- `tests/test_config_resolver.py` — ~145 seed-related lines; the largest single file, covers `resolve_seed`/`resolve_seed_for_run`/`build_experiment_config_dict`/`build_run_config_dict` directly. Every test calling `resolver.resolve_seed(...)`/`resolve_seed_for_run(...)` needs updating for the rename (§3); `resolve_seed_for_run`'s ~10 tests need a decision (delete with the dead function, or keep testing it if kept).
- `tests/unit/cli/test_bcllm_run_same_action_same_path.py` — `--seed` → `--randomization-seed` flag rename throughout.
- `tests/unit/cli/test_composite_flow_rollback.py` — same rename; also the tests that currently work around the `"OFF"` bug by passing an explicit seed (§ known-issues.md) can likely lose that workaround once `"OFF"` is eliminated and the Planner bug (§0) is fixed — worth re-checking once both land.
- `tests/factories/run.py`, `tests/factories/experiment.py` — seed-related factory defaults/params, used broadly; a rename here has the widest blast radius of any single file since factories are shared fixtures.
- `tests/cli_suite/cases/experiment.yaml`, `run.yaml` — real-subprocess CLI cases using `--seed`; flag rename plus new cases for `--randomization-seed`'s exact semantics per §2 of the user's message (zero, system-default, AUTO, inheritance, override).
- `tests/unit/db/test_repository.py`, `tests/unit/core/test_planner_images.py`, `tests/unit/core/test_run_finalizer.py`, `tests/integration/test_execution_contract.py`, `tests/integration/test_execution_concurrency.py` — reference `RUN_RESPONSES_SEED`/seed-effective indirectly; need a pass to confirm none assume the current (buggy) Planner fallback behavior as "correct."
- **New test files needed:** none of the current suite exercises Model Seed (doesn't exist), so all of §7 of the user's "Testes Essenciais" list for Model Seed is net-new.

**Documentation:** the 8 files listed in §4 plus the 2 files with the mutability bug in §5 (`configuration-hierarchy.md` appears in both lists — it has both problems). `known-issues.md` gets a new Resolved Issues entry once Checkpoint A lands (superseding, or absorbing, yesterday's `"OFF"` Bugs entry). `docs/status/roadmap.md`/`implementation-status.md` — not yet audited in detail; a quick pass needed to confirm neither references the old `--seed` flag name as a still-planned/still-current item.

---

## Summary for approval

| # | Question asked | Answer |
|---|---|---|
| 1 | Producers/consumers of the 8 symbols | §1, full table per symbol. |
| 2 | Where seed feeds `AnswerRandomizer` | Exclusively via `run.seed_effective` (proposed rename: `randomization_seed_effective`) → `ExecutionEngine`/`AsyncOrchestrator` → `randomizer.randomize_options(seed=...)`/`set_seed(...)`. No other path. |
| 3 | Does the current seed leak into the API request? | **No** — confirmed by grep, `src/api/client.py` has zero `seed`-related code today. Model Seed doesn't exist yet; nothing to leak. |
| 4 | Names needing change | §3, exact proposed names. |
| 5 | Docs using unqualified "seed" | §4. Plus a real (not naming-related) mutability bug found in 2 of them — §5. |
| 6 | Fields guaranteeing randomization auditability | §6 — 5 existing `responses` columns, already complete and correct. |
| 7 | Where `MODEL_SEED` enters each layer | §7, file-by-file, reusing existing generic mechanisms (`_resolve_cli_or_experiment`, the payload "add if not None" pattern) rather than inventing new ones. |
| 8 | Does the payload drop `None` keys? | §8 — yes, already the universal convention. |
| 9 | Test/doc impact | §9. |

**Additionally found, not asked for directly:** (a) the Planner inheritance bug in §0 — needs fixing as part of Checkpoint A for the user's Run semantics to actually hold; (b) `RUN_RESPONSES_SEED` vs `RANDOM_SEED` naming divergence in §2 — needs an explicit decision; (c) the "Experiment seed can be changed" documentation bug in §5, independent of the renaming work; (d) `resolve_seed_for_run` dead code and the general 3-way duplication of seed-string-parsing logic — needs a decision on delete-vs-consolidate.

Awaiting approval before Checkpoint A (Randomization Seed). Checkpoint B (Model Seed) follows separately, as instructed, in its own diff.
