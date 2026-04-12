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
| `LOG_LEVEL` | No | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FILE_PATH` | No | `./logs/benchmark.log` | Log file path (relative to project root) |

**Behavior:**
- Console: Shows `LOG_LEVEL` and above
- File: Shows `DEBUG` and above (more detailed)

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
| `MODEL_VISION` | `bool` | `false` | Enable vision/multimodal support |
| `STRUCTURED_OUTPUTS` | `bool` | `false` | Enable JSON schema responses |

---

### 5. Run Defaults

These values serve as defaults when creating runs.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `RUN_RESPONSES_SEED` | `str/int` | `None` | Seed for answer randomization (`AUTO`, `<int>`, or `None` for no randomization) |
| `SYSTEM_PROMPT` | `str` | `None` | System prompt for all runs (None = not sent in API request) |
| `USER_PROMPT` | `str` | `None` | User prompt template with `{question}`, `{options}` placeholders (None = not sent) |

**Seed Behavior:**
- `AUTO` → Resolved to random int at run creation time
- `<int>` → Fixed seed for reproducibility
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
- Run seed, prompts are captured at creation and never change

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
MODEL_VISION=
STRUCTURED_OUTPUTS=

# Run Defaults
RUN_RESPONSES_SEED=
SYSTEM_PROMPT=
USER_PROMPT=

# Concurrency
CONCURRENCY=
```

---

## Related Documents

- [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md) — Inheritance rules
- [contracts/system-default-semantics.md](../contracts/system-default-semantics.md) — system-default behavior
- [reference/cli-commands.md](cli-commands.md) — CLI flags that use these settings
