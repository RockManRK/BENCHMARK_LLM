---
type: normative
audience: ai
last-validated: 2026-04-11
status: active
---

# Determinism Contract

**Scope:** Execution reproducibility  
**Invariant:** Same configuration must always produce the same set of requests

---

## Contract Statement

Given identical inputs and configuration, the system must produce **identical API requests** every time. This ensures scientific reproducibility of benchmark experiments.

---

## Determinism Guarantees

### 1. Configuration Freezing

When an experiment is created:
- All configuration is snapshotted and frozen
- Changes to `.env` or system defaults **do not** affect existing experiments
- The frozen configuration is the sole determinant of execution behavior

**Implementation:** `Experiment.config_json` stores complete configuration snapshot

### 2. Seed-Based Randomization

Answer option randomization is controlled by the `seed` parameter with **three-state behavior**:

#### Seed States

| Seed Value | Meaning | Where Valid |
|------------|---------|-------------|
| `seed = None` | Randomization **OFF** (use original order A, B, C, D) | Experiment, Run |
| `seed = AUTO` | Resolve to random integer at **run creation time** | Experiment only |
| `seed = <integer>` | Randomization **ON** with deterministic shuffle | Experiment, Run |

#### Experiment → Run Resolution

At **experiment level**, seed can be `None`, `AUTO`, or an integer:
- `None` → Randomization disabled for all runs (unless overridden at run level)
- `AUTO` → Placeholder meaning "generate a random seed when each run is created"
- `<integer>` → Fixed seed for all runs (unless overridden at run level)

At **run creation time**, `AUTO` is resolved into a **random integer**:
```python
# Contract: AUTO resolution happens ONLY at run creation
if experiment_seed == "AUTO":
    run_seed = random.randint(0, MAX_INT)  # Resolved once, frozen forever
else:
    run_seed = experiment_seed  # None or int, passed through
```

**Critical:** By the time a run exists, its seed is **always** either `None` or an `int`. The value `AUTO` never exists at run level.

#### Randomization Decision

The randomizer uses a simple contract:
```python
# Contract: seed=None means randomization DISABLED
# Contract: seed=int means randomization ENABLED (deterministic)
# Contract: seed=0 does NOT disable randomization (0 is a valid seed)

randomization_enabled = (seed is not None)
```

**Implementation:** `src/core/randomizer.py` — `AnswerRandomizer` class

### 3. Question Presentation is Experimental Truth

What was presented to the LLM is the **authoritative record**:
- Options are saved **exactly as presented** (including any randomization)
- The system **never** "un-randomize" responses after execution
- The system **never** rewrites LLM response text
- Each response carries its own experimental context

**Rationale:** Scientific integrity — the LLM answered what it saw, not what we intended to show

### 4. Correctness Calculation

The `is_correct` field is calculated using `correct_option_presented` (the option space that was actually shown to the LLM), not the original dataset order.

---

## What Determinism Does NOT Guarantee

- **Same responses** — LLMs are non-deterministic; responses may vary
- **Same timing** — Network latency and API behavior vary
- **Same costs** — API pricing may change
- **Execution order** — Execution may be parallel; order of completion is not guaranteed. **Determinism applies to generated content (request payloads, option shuffling), not temporal execution order**

---

## Seed Inheritance

Seed values follow the configuration hierarchy:

```
System defaults → .env → Experiment → Run
```

- **Experiment seed:** Can be `None`, `AUTO`, or an integer. Can be changed after creation (does not affect existing runs)
- **Run seed:** Frozen at run creation; always `None` or `int` (never `AUTO`)
- **AUTO resolution:** Happens at run creation time only; the resolved integer is frozen into the run
- **System default:** `None` means randomization disabled (use original order)

---

## Violation Examples

### ❌ WRONG: Assuming truthy seed check

```python
# VIOLATION: seed=0 would disable randomization incorrectly
if seed_effective:
    randomize()
```

### ✅ CORRECT: Explicit None check

```python
if seed_effective is not None:
    randomize()
```

### ❌ WRONG: Post-execution option rewriting

```python
# VIOLATION: Never modify what was presented
response.options = original_order  # NEVER DO THIS
```

### ✅ CORRECT: Preserve presented options

```python
# CORRECT: Keep options exactly as presented
response.options = presented_options  # Immutable after execution
```

---

## Related Contracts

- [configuration-hierarchy.md](configuration-hierarchy.md) — Seed inheritance
- [immutability.md](immutability.md) — Snapshots cannot change
- [data-auditability.md](data-auditability.md) — Traceability of experimental conditions

---

**This contract is non-negotiable.** Any change that breaks determinism breaks the system's core purpose as a research tool.
