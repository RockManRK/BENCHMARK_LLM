---
type: normative
audience: ai
last-validated: 2026-08-18
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

### 2. Randomization Seed

Answer option randomization is controlled by the Randomization Seed
(`--randomization-seed`/`RANDOMIZATION_SEED` — see
`docs/status/seed-vocabulary-separation-investigation.md` for why this is
called out by full name: it is a distinct concept from the unrelated
Model Seed, which is sent as the API request's `seed` field and never
touches `AnswerRandomizer`) with **three-state behavior**:

#### Randomization Seed States

| Value | Meaning | Where Valid |
|------------|---------|-------------|
| `None` | Randomization **OFF** (use original order A, B, C, D) | Experiment, Run |
| `AUTO` | Resolve to a deterministic integer at **run creation time** | Experiment only |
| `<integer>` | Randomization **ON** with deterministic shuffle | Experiment, Run |

#### Experiment → Run Resolution

At **experiment level**, the Randomization Seed can be `None`, `AUTO`, or an integer:
- `None` → Randomization disabled for all runs (unless overridden at run level)
- `AUTO` → Placeholder meaning "resolve to a concrete seed when each run is created"
- `<integer>` → Fixed seed for all runs (unless overridden at run level)

At **run creation time**, `AUTO` is resolved into a **deterministic integer**
derived from the run and experiment IDs (SHA-256 of `f"{experiment_id}:{run_id}"`) —
not a random draw, so the resolved value is reproducible from those IDs alone:
```python
# Contract: AUTO resolution happens ONLY at run creation
if experiment_seed == "AUTO":
    run_seed = _generate_randomization_seed_from_run(run_id, experiment_id)  # deterministic, frozen forever
else:
    run_seed = experiment_seed  # None or int, passed through
```

**Critical:** By the time a run exists, its Randomization Seed is **always**
either `None` or an `int`. The value `AUTO` never exists at run level — and
once frozen, the Planner reads the run's own stored value at `--execute`
time and never recomputes or re-inherits it (fixed 2026-08-20, see
`docs/status/known-issues.md`: `Planner._resolve_randomization_seed_effective`
used to silently re-apply Experiment→Run inheritance on every execute,
overriding an explicit frozen `None` decision).

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

### 5. Provider Locking

When `PROVIDER_LOCK=true` and `PROVIDER` is resolved for a model variant, the provider slug becomes part of the deterministic configuration.

**Invariant**: Same `PROVIDER` + model + config → same API request payload, always.

**Resolution contract**:
- `PROVIDER` is resolved once via `--resolve-providers`
- Resolved provider is persisted in `model_variants.config.PROVIDER`
- ExecutionPlan includes `resolved_provider` per variant
- Executor includes `provider.only` in request payload

**When `PROVIDER_LOCK=true`**:
- Pre-execution validation requires all variants to have `PROVIDER != null`
- If any variant has `PROVIDER=null`, execution fails with clear error

**When `PROVIDER_LOCK=false`**:
- `PROVIDER=null` is allowed
- OpenRouter's default load balancing applies
- Results may not be reproducible across provider changes

---

### 6. Model Seed (generation determinism, distinct from randomization determinism)

Model Seed (`MODEL_SEED`, sent as the API request's `seed` field) is a
**separate** determinism concern from Randomization Seed above — see
`docs/status/model-seed-checkpoint-b-design.md`. Randomization Seed
determines whether `AnswerRandomizer` produces the same option order
every time; Model Seed determines whether the *generation itself* is
requested to be deterministic. Neither can affect the other — they never
share a resolver, a config key, or a code path.

**What this contract guarantees**: the same `MODEL_SEED` value produces
the same `"seed"` field in the API request payload, every time (payload
construction is deterministic — see `src/api/request_payload.py`).

**What this contract does NOT guarantee**: that the provider's generated
output is identical across calls with the same seed. `MODEL_SEED` is a
*request*, not a promise the system can verify or enforce — the system
never claims determinism of the response itself, only of the request
sent. Some providers may not honor `seed` at all; BCLLM does not filter
or validate provider support before sending it (see
`docs/status/model-seed-checkpoint-b-design.md`, "Backends") — an
unsupported parameter surfaces as a normal API error, never a silent drop.

---

### 7. Logging Visibility into Payload Determinism

At `LOG_PROFILE=TRACE`, `REQUEST_PAYLOAD_TRACE` logs the full redacted
canonical payload for each attempt (`src/core/execution_engine.py`,
right after `build_chat_completion_payload()` constructs it) — this is
the same single canonical payload described in Section 6 above and in
`docs/status/model-seed-checkpoint-b-design.md`, not a second,
independently-derived value. There is no separate `payload_fingerprint`
field or hashing step anywhere in the system; the full (redacted)
payload is what TRACE logs, not a digest of it — any prior design
material describing a `payload_fingerprint` field describes an
unimplemented proposal, not current behavior. Logging this payload is
diagnostic only (see `docs/contracts/data-auditability.md` §4c) and has
no bearing on determinism itself, which is guaranteed by construction
(one payload object, reused for `request_json` and transport), not by
anything logging observes.

---

## What Determinism Does NOT Guarantee

- **Same responses** — LLMs are non-deterministic; responses may vary
- **Same timing** — Network latency and API behavior vary
- **Same costs** — API pricing may change
- **Execution order** — Execution may be parallel; order of completion is not guaranteed. **Determinism applies to generated content (request payloads, option shuffling), not temporal execution order**

---

## Randomization Seed Inheritance

Randomization Seed values follow the configuration hierarchy:

```
System defaults → .env → Experiment → Run → CLI --randomization-seed
```

(Fixed 2026-08-18 — this chain previously omitted CLI, the same gap
found and fixed in `configuration-hierarchy.md`'s three per-key chains;
see ADR-002, Decision 4. Not a behavior change: `resolve_randomization_seed()`
already checks `cli_value` first — only the documented chain was incomplete.
This chain is written lowest-to-highest precedence, so CLI is appended
at the end, not the start; `configuration-hierarchy.md`'s chains are
written highest-to-lowest, so CLI is prepended there instead — same
precedence, opposite notation.)

- **Experiment's Randomization Seed:** Can be `None`, `AUTO`, or an integer. Frozen at creation, exactly like every other Experiment config value — **cannot be changed** after creation (corrected 2026-08-20; this line previously and incorrectly claimed it could be changed — see `docs/status/known-issues.md`)
- **Run's Randomization Seed:** Frozen at run creation; always `None` or `int` (never `AUTO`); once frozen, this is the run's final decision and nothing downstream (including the Planner at `--execute` time) may recompute or override it
- **AUTO resolution:** Happens at run creation time only, via a deterministic hash of the run and experiment IDs; the resolved integer is frozen into the run
- **System default:** `None` means randomization disabled (use original order). Textual sentinels (`"OFF"`/`"NULL"`/`"NONE"`/`""`) are retired — only Python `None`/JSON `null` represents "no randomization"

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
