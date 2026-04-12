---
type: normative
audience: ai
last-validated: 2026-04-11
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

## System Default Values by Parameter

| Parameter | System Default Behavior | Effect |
|-----------|------------------------|--------|
| `--seed` | `None` | Randomization **disabled**; use original order A, B, C, D |
| `--system-prompt` | `None` | **Not sent** in API request |
| `--user-prompt` | `None` | **Not sent** in API request |
| `--reasoning` | `None` | **Not sent** in API request |
| `--max-tokens` | `None` | **Not sent** in API request (API server default) |
| `--reasoning-tokens` | `None` | **Not sent** in API request |
| `--temperature` | `None` | **Not sent** in API request (API server default) |
| `--top-p` | `None` | **Not sent** in API request (API server default) |
| `--top-k` | `None` | **Not sent** in API request (API server default) |
| `--repeat-penalty` | `None` | **Not sent** in API request (API server default) |
| `--vision` | `None` | **Not sent** in API request |
| `--structured` | `None` | **Not sent** in API request |
| `--add-questions` | All available | Use all questions from dataset |
| `--where` / `--exclude` | No filtering | Do not filter questions |

**Pattern:** For most parameters, `system-default` means **do not send in API request**, allowing the API server's own defaults to activate.

---

## Commands That Do NOT Support `system-default`

The following structural commands cannot accept `system-default`:

- `--create-experiment` (requires explicit name)
- `--url` (must be explicitly provided)
- `--data-set` / `--dataset-path` (must be explicitly provided)
- `--add-model` (requires explicit model ID)
- `--remove-model` (requires explicit model ID)
- `--add-run` (structural command)
- `--remove-run` (structural command)
- `--execute` (structural command)

**Rationale:** These commands define structure or identity; they cannot inherit from system defaults meaningfully.

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

**Implementation:** `src/core/null_semantics.py` — `FORCE_SYSTEM_DEFAULT` constant

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
# seed comes from .env RANDOM_SEED or system default

# Case 2: Explicit system-default → bypasses .env
bcllm --create-experiment my_exp --seed system-default
# seed is None (no randomization), ignoring .env
```

---

## Violation Examples

### ❌ WRONG: Checking .env after system-default

```python
# VIOLATION: system-default should bypass .env
if value == FORCE_SYSTEM_DEFAULT:
    return os.environ.get("RANDOM_SEED")  # Still checking env!
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
    return experiment_config.get("seed")  # WRONG!
```

### ✅ CORRECT: Recognizing explicit instruction

```python
# CORRECT: system-default is user instruction to bypass hierarchy
if cli_value == FORCE_SYSTEM_DEFAULT:
    return None  # System built-in default for seed
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

## Related Contracts

- [configuration-hierarchy.md](configuration-hierarchy.md) — Where system-default fits in hierarchy
- [determinism.md](determinism.md) — Seed system-default disables randomization

---

**This contract is non-negotiable.** `system-default` semantics ensure users can explicitly bypass inheritance when needed.
