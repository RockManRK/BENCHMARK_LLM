---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# Configuration Hierarchy Contract

**Scope:** Configuration resolution  
**Invariant:** Configuration follows a strict inheritance chain; undefined values inherit from the next level up

---

## Contract Statement

All configuration resolution follows a **strict hierarchy** with明确 precedence. A level inherits from its parent when a value is not explicitly set.

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
| **CLI** | Single command | At execution | `--seed 42` |
| **Run/Model Variant** | Specific execution instance or model config | When adding run or model to experiment | Run seed, run prompts |
| **Experiment** | All runs within experiment | When creating or modifying experiment | Experiment seed, default prompts, model list |
| **.env** | User defaults | Always loaded at startup | `RANDOM_SEED=42`, `SYSTEM_PROMPT="..."` |
| **System Defaults** | Built-in fallback | When nothing else is set | `None` for prompts, `None` for seed (no randomization) |

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
- Only run-specific values can differ: `seed`, `system_prompt`, `user_prompt`

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
    "seed": 42,
    "system_prompt": "You are a benchmark assistant",
    # ... all resolved values captured here
}

# WRONG: Never modify frozen configuration
experiment_config["seed"] = 123  # VIOLATION
```

### Exceptions (Growth, Not Modification)

- **Experiment:** Can add questions and models (growth), but cannot change frozen config
- **Run:** Cannot be modified at all
- **Model Variant:** Cannot be modified; add new variant instead

---

## Seed Resolution

Seed follows special resolution rules:

```
Run seed → Experiment seed → .env RANDOM_SEED → System default (None = no randomization)
```

- **AUTO resolution:** Happens at **run creation time only**
- **Experiment seed:** Can be changed; does not affect existing runs
- **Run seed:** Frozen; never changes
- **System default:** `None` means randomization disabled (use original order)

**Implementation:** `src/core/config_resolver.py` — `resolve_seed()` method

---

## Prompt Resolution

System and user prompts follow:

```
Run prompt → Experiment prompt → .env SYSTEM_PROMPT/USER_PROMPT → System default (None = not sent)
```

- If not configured at any level: **not sent** in API request
- `None` is explicit "do not send" signal
- Run prompts are frozen; experiment prompts can be changed (doesn't affect existing runs)

**Implementation:** `src/core/config_resolver.py` — `resolve_prompt()` method

---

## Model Parameter Resolution

Individual model parameters follow:

```
Model variant param → Experiment default → .env parameter → System default (None = not sent)
```

- If not configured: **not sent** in API request
- This activates the API server's own defaults
- Parameters include: `reasoning`, `max_tokens`, `reasoning_tokens`, `temperature`, `top_p`, `top_k`, `repeat_penalty`, `vision`, `structured`

---

## Violation Examples

### ❌ WRONG: Ignoring hierarchy

```python
# VIOLATION: Hardcoding instead of following hierarchy
seed = 42  # Where did this come from? Ignores hierarchy!
```

### ✅ CORRECT: Following hierarchy

```python
# CORRECT: Resolve through hierarchy
seed = config_resolver.resolve_seed(
    cli_value=cli_args.seed,
    run_config=run_config.get("seed"),
    experiment_config=experiment_config.get("seed"),
    env_key="RANDOM_SEED",
)
```

### ❌ WRONG: Allowing .env to override frozen config

```python
# VIOLATION: Re-reading .env after experiment creation
experiment.seed = os.environ.get("RANDOM_SEED")  # Ignores frozen config!
```

### ✅ CORRECT: Respecting frozen configuration

```python
# CORRECT: Use experiment's frozen config
experiment_seed = experiment.config_json.get("seed")
# .env changes do not affect this
```

---

## Related Contracts

- [system-default-semantics.md](system-default-semantics.md) — "system-default" bypass behavior
- [determinism.md](determinism.md) — Seed inheritance for reproducibility
- [immutability.md](immutability.md) — Configuration freezing

---

**This contract is non-negotiable.** Configuration hierarchy ensures predictability and reproducibility.
