---
type: normative
audience: ai
last-validated: 2026-08-18
status: active
---

# Configuration Hierarchy Contract

**Scope:** Configuration resolution  
**Invariant:** Configuration follows a strict inheritance chain; undefined values inherit from the next level up

---

## Contract Statement

All configuration resolution follows a **strict hierarchy** with precedence. A level inherits from its parent when a value is not explicitly set.

---

## Hierarchy Levels (Highest to Lowest Precedence)

```
CLI Arguments (highest) 
    ↓
Run / Model Variant (execution-time)
    ↓
Experiment (creation-time)
    ↓
.env (user defaults)
    ↓
System Defaults (lowest)
```

### Level Definitions

| Level | Scope | When Set | Example |
|-------|-------|----------|---------|
| **CLI** | Single command | At execution | `--randomization-seed 42` |
| **Run/Model Variant** | Specific execution instance or model config | When adding run or model to experiment | Run's own Randomization Seed and prompts (Run); Model Seed (Model Variant — see note below) |
| **Experiment** | All runs within experiment | When creating or modifying experiment | Experiment's default Randomization Seed, Model Seed, default prompts, model list |
| **.env** | User defaults | Always loaded at startup | `RANDOMIZATION_SEED=42`, `SYSTEM_PROMPT="..."` |
| **System Defaults** | Built-in fallback | When nothing else is set | `None` for prompts, `None` for both Randomization Seed and Model Seed (no randomization / no seed sent) |

**Two distinct concepts, both called "seed" informally — never confuse them:** Randomization Seed (`--randomization-seed`/`RANDOMIZATION_SEED`) controls only `AnswerRandomizer`'s shuffling of presented options; it belongs to Experiment and Run, never to a model variant, and is never sent to the API. Model Seed (`--model-seed`/`MODEL_SEED`) is sent as the API request's `seed` field for deterministic inference; it belongs to Experiment and Model Variant (not Run), and never affects randomization. See `docs/status/seed-vocabulary-separation-investigation.md` for the full separation.

---

## Resolution Algorithm

For each configuration key:

1. **Check CLI** — Was it explicitly passed on command line?
2. **Check Run/Model Variant** — Was it set for this specific run or model?
3. **Check Experiment** — Was it set in experiment configuration?
4. **Check .env** — Is there a user default in environment variables?
5. **Use System Default** — Built-in fallback (often `None` or "ignore in request")

**First non-None value wins.**

---

## Inheritance Rules

### 1. Experiment Inherits from .env

When creating an experiment:
- If a value is not specified, inherit from `.env`
- Once experiment is created, `.env` changes **do not** affect it
- The experiment's configuration is **frozen** (except for allowed growth)

### 2. Run Inherits from Experiment

When creating a run:
- If a value is not specified, inherit from experiment
- Run configuration is **frozen** at creation; never changes
- Only run-specific values can differ: `RANDOMIZATION_SEED`, `system_prompt`, `user_prompt` — Model Seed is never one of them (it is not a Run-level concept at all)

### 3. Model Variant Inherits from Experiment

When adding a model variant:
- If a model parameter is not specified, inherit from experiment defaults
- Model variant configuration is **frozen** at creation
- Model parameters include: `reasoning`, `max_tokens`, `temperature`, `top_p`, `top_k`, `repeat_penalty`, `vision`, `structured`

---

## Configuration Freezing

**Critical Rule:** Once an entity (experiment, run, model variant) is created, its configuration is **frozen**.

```python
# CORRECT: Configuration frozen at creation
experiment_config = {
    "RANDOMIZATION_SEED": 42,
    "SYSTEM_PROMPT": "You are a benchmark assistant",
    # ... all resolved values captured here
}

# WRONG: Never modify frozen configuration
experiment_config["RANDOMIZATION_SEED"] = 123  # VIOLATION
```

### Exceptions (Growth, Not Modification)

- **Experiment:** Can add questions and models (growth), but cannot change frozen config
- **Run:** Cannot be modified at all
- **Model Variant:** Cannot be modified; add new variant instead

---

## Randomization Seed Resolution

Randomization Seed (controls only `AnswerRandomizer`; never sent to the API — see `docs/status/seed-vocabulary-separation-investigation.md`) follows special resolution rules, and the resolution point differs by level:

**At Experiment creation:**
```
CLI --randomization-seed → .env RANDOMIZATION_SEED → System default (None = no randomization)
```
`AUTO` is a valid value at this level but is stored verbatim as the string `"AUTO"` — **not** resolved to a number here.

**At Run creation:**
```
CLI --randomization-seed → Experiment's own RANDOMIZATION_SEED → System default (None = no randomization)
```
This is the **only** point where `AUTO` (whether passed directly on the Run's own `--randomization-seed AUTO`, or inherited from the Experiment) is resolved to a concrete integer — a deterministic value derived from the run and experiment IDs. `AUTO` must never appear on a persisted Run.

**Corrected 2026-08-20** (seed vocabulary separation checkpoint — see `docs/status/known-issues.md`): both the "Experiment seed can be changed" claim below and this chain's stale example signature were fixed, alongside a real Planner bug found in the same pass — the Planner used to re-derive this inheritance at every `--execute` instead of reading the Run's own already-frozen value, silently overriding an explicit "don't randomize" decision made at Run creation. Fixed; see `src/core/planner.py::_resolve_randomization_seed_effective`.

- **AUTO resolution:** Happens at **Run creation time only** — never at Experiment creation, never re-derived at `--execute` time.
- **Experiment's Randomization Seed:** Frozen at creation, exactly like every other Experiment config value — **cannot be changed** after creation (no CLI path modifies it; the only genuine post-creation-mutable field on Experiment is `--provider-lock`, a separate, already-documented exception — see `docs/status/known-issues.md`).
- **Run's Randomization Seed:** Frozen at creation; never changes. Once set (an integer, or `None` for no randomization), it is the Run's final, authoritative decision — nothing downstream (including the Planner, at `--execute` time) may recompute or override it.
- **System default:** `None` means randomization disabled (use original order). Never a textual sentinel (`"OFF"`/`"NULL"`/`"NONE"`/`""` are all retired — see `docs/status/known-issues.md`).

**Implementation:** `src/core/config_resolver.py` — `resolve_randomization_seed()` (Experiment level) and `resolve_randomization_seed_for_run()` (Run level, the only place AUTO resolves to a number).

---

## Prompt Resolution

System and user prompts follow:

```
CLI --system-prompt/--user-prompt → Run prompt → Experiment prompt → .env SYSTEM_PROMPT/USER_PROMPT → System default (None = not sent)
```

(Fixed 2026-08-18 — same omission as the seed chain above; see ADR-002.)

- If not configured at any level: **not sent** in API request
- `None` is explicit "do not send" signal
- Both Run prompts and Experiment prompts are frozen at creation and cannot be changed afterward — corrected 2026-08-20 alongside the Randomization Seed mutability fix above; this claim had the same bug (no CLI path modifies `SYSTEM_PROMPT`/`USER_PROMPT` on an existing experiment either)

**Implementation:** `src/core/config_resolver.py` — `resolve_prompt()` method

---

## Model Parameter Resolution

Individual model parameters follow:

```
CLI (--reasoning, --temperature, etc.) → Model variant param → Experiment default → .env parameter → System default (None = not sent)
```

(Fixed 2026-08-18 — same omission as the seed/prompt chains above; see ADR-002.)

- If not configured: **not sent** in API request
- This activates the API server's own defaults
- Parameters include: `reasoning`, `max_tokens`, `reasoning_tokens`, `temperature`, `top_p`, `top_k`, `repeat_penalty`, `vision`, `structured`

---

## Violation Examples

### ❌ WRONG: Ignoring hierarchy

```python
# VIOLATION: Hardcoding instead of following hierarchy
randomization_seed = 42  # Where did this come from? Ignores hierarchy!
```

### ✅ CORRECT: Following hierarchy

```python
# CORRECT: Resolve through hierarchy — Experiment level (does NOT resolve AUTO)
randomization_seed = config_resolver.resolve_randomization_seed(
    cli_value=cli_args.randomization_seed,
    env_key="RANDOMIZATION_SEED",
    experiment_name=experiment_name,
)
# CORRECT: Run level (the only place AUTO resolves to an integer)
randomization_seed = config_resolver.resolve_randomization_seed_for_run(
    cli_value=cli_args.randomization_seed,
    experiment_seed=exp_config.get("RANDOMIZATION_SEED"),
    run_id=run_id,
    experiment_id=experiment_id,
)
```

### ❌ WRONG: Allowing .env to override frozen config

```python
# VIOLATION: Re-reading .env after experiment creation
experiment.randomization_seed = os.environ.get("RANDOMIZATION_SEED")  # Ignores frozen config!
```

### ✅ CORRECT: Respecting frozen configuration

```python
# CORRECT: Use experiment's frozen config
experiment_randomization_seed = experiment.config_json.get("RANDOMIZATION_SEED")
# .env changes do not affect this
```

---

## Related Contracts

- [system-default-semantics.md](system-default-semantics.md) — "system-default" bypass behavior
- [determinism.md](determinism.md) — Seed inheritance for reproducibility
- [immutability.md](immutability.md) — Configuration freezing

---

**This contract is non-negotiable.** Configuration hierarchy ensures predictability and reproducibility.
