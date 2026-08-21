---
type: reference
audience: ai
last-validated: 2026-04-11
status: active
---

# Configuration Reference

**Purpose:** Complete `.env` settings reference  
**Source:** Validated against `.env.example`, `src/core/config_resolver.py`, and CLI modules

---

## Configuration Loading

The `.env` file is loaded **once** at application startup by `bcllm.py` via `python-dotenv`:

```python
load_dotenv(".env", override=True)
```

All modules read from `os.environ`, **not** by loading `.env` directly.

---

## Configuration Categories

### 1. API Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | **YES** | (none) | API key for OpenRouter (set via system env, NOT in `.env`) |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1` | Base URL for OpenRouter API |
| `BASE_URL` | No | `https://openrouter.ai/api/v1` | Default base URL for experiments |

**⚠️ SECURITY:** `OPENROUTER_API_KEY` must NEVER be in `.env`. Set via system environment variable only.

---

### 2. Logging Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` — the stdlib severity threshold a handler emits at. |
| `LOG_FILE_PATH` | No | `./logs/benchmark.log` | Log file path (relative to project root). The structured JSONL sibling file is derived automatically from this path (same directory, same stem, `.jsonl` suffix) — never independently configured. |
| `LOG_PROFILE` | No | `NORMAL` | Depth profile: `MINIMAL`, `NORMAL`, `DETAILED`, `TRACE` (cumulative). Controls which `INFO`/`DEBUG`-severity structured events are emitted — see `docs/status/checkpoint-c-logging-observability-design.md` for the full per-profile event catalog. No CLI override exists (`.env`-only, matching `LOG_LEVEL`'s own precedent). |
| `OPENROUTER_DEBUG_ENABLED` | No | `false` | OpenRouter's own `debug.echo_upstream_body` feature — adds the upstream-transformed request body to the response stream (TRACE-profile log visibility only; always captured in `responses.raw_response`/`raw_response_consolidated` regardless of profile). **Independent of `LOG_LEVEL`/`LOG_PROFILE`** — a separate axis entirely (see below). Not part of the frozen Experiment/Run/Model-Variant configuration hierarchy — an operational/per-process setting, same category as `LOG_LEVEL`, not `MODEL_SEED`/`RANDOMIZATION_SEED`. |

**Behavior:**
- Console: Shows `LOG_LEVEL` and above
- File: Shows `DEBUG` and above (more detailed)
- JSONL: same severity floor as the file; which `INFO`/`DEBUG` events exist at all is additionally gated by `LOG_PROFILE`. `WARNING`+ events are never suppressed by `LOG_PROFILE`, at any level.

**`LOG_LEVEL`/`LOG_PROFILE` vs. `OPENROUTER_DEBUG_ENABLED` — do not confuse these:**
`LOG_LEVEL`/`LOG_PROFILE` control *this system's own* logging depth —
they never change what gets sent to the API. `OPENROUTER_DEBUG_ENABLED`
changes the actual API request payload (`build_chat_completion_payload`
adds a `debug` key when true) — it is auditable in `request_json` for
that reason (see `docs/contracts/data-auditability.md` §4b), and its
effect on the *response* (the echoed upstream body) is separately visible
in logs only at `LOG_PROFILE=TRACE`. A controlled real-API investigation
(`docs/status/model-seed-checkpoint-b-design.md` §5, reused for
Checkpoint C) found `debug` adds exactly the upstream-echo chunk — it
does not gate cost/tokens/provider (already available without it) and
never confirms a requested seed was honored, only forwarded.

---

### 1b. Database Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_PATH` | No | `./data/bcllm.db` | SQLite database file path (relative to project root, or absolute) |

**Behavior:**
- A SYSTEM-level key (same category as `LOG_FILE_PATH`) — resolved fresh from the environment on every CLI invocation, never stored in `experiment.config_json`, never consulted through the CLI > Run/Model > Experiment > `.env` hierarchy.
- Read by `src/cli/database.py::get_database_path()`. Relative paths are resolved against the project root, not the current working directory; the parent directory is created automatically if missing.
- Primary use case: redirecting the CLI at an isolated sandbox database (e.g. the CLI test suite, `docs/tests/`) without copying `bcllm.py`/`src/`.

---

### 3. Questions Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QUESTIONS_DATASET_PATH` | **YES** | (none) | Path to questions JSON file |
| `DEFAULT_QUESTIONS` | No | (None) | JSON array of question IDs to use by default |
| `QUESTIONS_STATUS_ADD` | No | (None) | Filter: only include questions with these status values |
| `QUESTIONS_STATUS_EXCLUDE` | No | (None) | Filter: exclude questions with these status values |

**Question ID Format:** Question identifiers are **numeric indices** (e.g., `1`, `5`, `10`), not `Q***` format.

**Format for `DEFAULT_QUESTIONS`:**
```json
[1, 2, 3, 5, 10]
```

**Filter Examples:**
```bash
# Include only valid questions
QUESTIONS_STATUS_ADD=valid

# Exclude annulled questions
QUESTIONS_STATUS_EXCLUDE=annulled
```

---

### 4. Model Defaults

These values serve as defaults when creating model variants. Leave blank to use model API's own defaults.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MODEL_MAX_TOKENS_REASONING` | `int` | (blank) | Max tokens for reasoning phase (1 or above) |
| `MODEL_MAX_TOKENS_TOTAL` | `int` | `16384` | Max total tokens (reasoning + completion) (1 or above) |
| `MODEL_REASONING_EFFORT` | `str` | (blank) | `xhigh`, `high`, `medium`, `low`, `minimal`, `none` |
| `MODEL_TEMPERATURE` | `float` | (blank) | Temperature (0.0-2.0) |
| `MODEL_TOP_P` | `float` | (blank) | Top-P sampling (0.0-1.0) |
| `MODEL_TOP_K` | `int` | (blank) | Top-K sampling (0 or above) |
| `MODEL_REPEAT_PENALTY` | `float` | (blank) | Repeat penalty (0.0-2.0) |
| `MODEL_SEED` | `int` | (blank) | Model Seed — sent as the API request's `seed` field for deterministic inference. No `AUTO` state. Distinct from `RANDOMIZATION_SEED` above — see `docs/status/model-seed-checkpoint-b-design.md`. |
| `MODEL_VISION` | `bool` | `false` | Enable vision/multimodal support |
| `STRUCTURED_OUTPUTS` | `bool` | `false` | Enable JSON schema responses |

---

### 5. Run Defaults

These values serve as defaults when creating runs.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RANDOMIZATION_SEED` | `str/int` | `None` | Randomization Seed for answer option shuffling (`AUTO`, `<int>`, or `None` for no randomization) — controls `AnswerRandomizer` only, never sent to the API. Not to be confused with Model Seed (`MODEL_SEED`, a model-variant-level setting sent as the API request's `seed` field — see `docs/status/seed-vocabulary-separation-investigation.md`). |
| `SYSTEM_PROMPT` | `str` | `None` | System prompt for all runs (None = not sent in API request) |
| `USER_PROMPT` | `str` | `None` | User prompt template with `{question}`, `{options}` placeholders (None = not sent) |

**Randomization Seed Behavior:**
- `AUTO` → Resolved to a deterministic int at run creation time (never at experiment creation, never re-derived at `--execute` time)
- `<int>` → Fixed seed for reproducibility (`0` is valid, not treated as unset)
- `None` → No randomization (original order A, B, C, D)

**Prompt Behavior:**
- `None` → Not sent in API request
- Any string value → Sent as prompt

---

### 6. Concurrency Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONCURRENCY` | No | `1` | Maximum concurrent API calls (parallel execution) |

**Behavior:**
- `1` → Sequential execution
- `>1` → Parallel execution with semaphore limit

---

### 7. Provider Locking (OpenRouter)

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_PROVIDER_LOCK` | `false` | Default provider lock setting for new experiments. Set to `true` to require provider resolution before execution. |
| `PROVIDER_SELECTION_STRATEGY` | `first` | Strategy for `--resolve-providers`. Options: `first`, `cheapest`, `fastest`, `lowest-latency`. |

**Provider Resolution Strategies:**
- `first`: First endpoint listed by OpenRouter
- `cheapest`: Lowest prompt pricing
- `fastest`: Highest throughput
- `lowest-latency`: Lowest latency

---

## Configuration Resolution

Configuration follows the **hierarchy**:

```
CLI Arguments (highest priority)
    ↓
Run / Model Variant config
    ↓
Experiment config (frozen at creation)
    ↓
.env (used ONLY at experiment creation)
    ↓
System Defaults (lowest priority)
```

**Important:** `.env` is only consulted **at experiment creation time**. Once an experiment is created, its configuration is frozen. Run-level and Model-level resolution **never falls back to `.env`** — they inherit from experiment configuration only.

**Resolution Algorithm (at experiment creation):**
1. Check if value was explicitly passed via CLI
2. Check if value exists in `.env`
3. Use system built-in default (often `None` = "not sent in API request")

**Resolution Algorithm (for runs and models):**
1. Check if value was explicitly set for run or model variant
2. Inherit from experiment configuration (frozen)
3. Use system built-in default

**First non-None value wins.**

See [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md) for full specification.

---

## Experiment Config Schema

The `Experiment.config_json` stores these fields:

| Key | Type | Description |
|-----|------|-------------|
| `RANDOMIZATION_SEED` | `str \| null` | Randomization Seed (`"AUTO"`, `null`, or integer) — `AnswerRandomizer` only, never sent to the API |
| `SYSTEM_PROMPT` | `str \| null` | System prompt template |
| `USER_PROMPT` | `str \| null` | User prompt template with `{question}`, `{options}` |
| `BASE_URL` | `str \| null` | API base URL |
| `QUESTIONS_DATASET_PATH` | `str \| null` | Questions file path |
| `PROVIDER_LOCK` | `bool \| null` | Provider lock setting (`true` = require resolved providers) |
| `PROVIDER_SELECTION_STRATEGY` | `str` | Provider resolution strategy (default: `first`) |

---

## Model Variant Config Schema

The `ModelVariant.config` stores these fields:

| Key | Type | Description |
|-----|------|-------------|
| `MODEL_ID` | `str` | Base model identifier |
| `REASONING` | `str \| null` | Reasoning effort |
| `MAX_TOKENS` | `int \| null` | Max tokens for generation |
| `REASONING_TOKENS` | `int \| null` | Max reasoning tokens |
| `TEMPERATURE` | `float \| null` | Temperature |
| `TOP_P` | `float \| null` | Top-P sampling |
| `TOP_K` | `int \| null` | Top-K sampling |
| `REPEAT_PENALTY` | `float \| null` | Repeat penalty |
| `MODEL_SEED` | `int \| null` | Sent as the API request's `seed` field. `null` omits the key entirely. Never `AUTO`. |
| `VISION` | `bool \| null` | Vision support |
| `STRUCTURED` | `bool \| null` | Structured output |
| `BASE_URL` | `str \| null` | Model-specific API URL |
| `PROVIDER` | `str \| null` | OpenRouter provider slug (e.g., `deepinfra/turbo`). `null` means unresolved — OpenRouter chooses. |

---

## System-Default Semantics

When a CLI flag receives `system-default`:
- **Bypasss inheritance chain** (does NOT check `.env`)
- Uses system built-in default for that parameter
- For most model parameters: "not sent in API request" (activates API server defaults)

See [contracts/system-default-semantics.md](../contracts/system-default-semantics.md) for complete specification.

---

## Configuration Freezing

When an experiment is created:
- All resolved configuration values are **frozen** into `Experiment.config_json`
- Changes to `.env` **do not** affect existing experiments
- Experiments can grow (add questions/models) but frozen config cannot change

When a run is created:
- Run configuration is **frozen** into `Run.config`
- Run's Randomization Seed, prompts are captured at creation and never change

---

## Validation

Configuration is validated at:
1. **CLI level** — argparse validates types and required fields
2. **Resolver level** — `ConfigResolver` normalizes values
3. **Planning level** — `Planner` validates prerequisites before execution

**No inference:** Missing configuration is NOT inferred; it uses system defaults or fails validation.

---

## Example .env File

```bash
# API Configuration
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
BASE_URL=https://openrouter.ai/api/v1

# Database (optional; defaults to ./data/bcllm.db)
DATABASE_PATH=./data/bcllm.db

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/benchmark.log

# Questions
QUESTIONS_DATASET_PATH=data/*.json
QUESTIONS_STATUS_ADD=
QUESTIONS_STATUS_EXCLUDE=

# Model Defaults
MODEL_MAX_TOKENS_TOTAL=
MODEL_TEMPERATURE=
MODEL_TOP_P=
MODEL_SEED=
MODEL_VISION=
STRUCTURED_OUTPUTS=

# Run Defaults
RANDOMIZATION_SEED=
SYSTEM_PROMPT=
USER_PROMPT=

# Concurrency
CONCURRENCY=

# Provider Locking
AUTO_PROVIDER_LOCK=false
PROVIDER_SELECTION_STRATEGY=first
```

---

## Related Documents

- [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md) — Inheritance rules
- [contracts/system-default-semantics.md](../contracts/system-default-semantics.md) — system-default behavior
- [reference/cli-commands.md](cli-commands.md) — CLI flags that use these settings
