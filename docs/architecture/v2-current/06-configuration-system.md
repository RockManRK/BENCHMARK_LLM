# Configuration System — V2 Current State

**Document Type:** Current State Analysis
**Domain:** Configuration System
**Source:** `src/core/config_resolver.py`, `docs/architecture/contracts/configurarion_resolution_contract.md`, `docs/architecture/contracts/cli_null_semantics.md`
**Purpose:** Document what actually exists in V2 implementation

---

## 1. Domain Overview

### 1.1 What Exists in V2

The V2 Configuration System implements a **ConfigResolver** component with explicit priority ordering and null semantics.

| Component | Status | Location |
|-----------|--------|----------|
| ConfigResolver | ✅ Implemented | `src/core/config_resolver.py` |
| Null Semantics | ✅ Implemented | `src/core/null_semantics.py` (EXPLICIT_NULL) |
| Resolution Contracts | ✅ Documented | `docs/architecture/contracts/configurarion_resolution_contract.md` |
| CLI Null Semantics | ✅ Documented | `docs/architecture/contracts/cli_null_semantics.md` |

### 1.2 Architectural Principles

V2 follows these configuration principles:

- ✅ **Explicit Priority** — CLI > .env > system defaults > NULL
- ✅ **Null-by-Default** — Prompts default to NULL (no fallback strings)
- ✅ **EXPLICIT_NULL** — CLI `null` means explicit absence, no fallback
- ✅ **Capture at Creation** — Configuration frozen when entity is created
- ✅ **No Inference** — Nothing is automatically inferred
- ✅ **JSON Storage** — Configurations stored as JSON in entities

---

## 2. ConfigResolver Implementation

### 2.1 Class Overview

**Purpose**: Centralized configuration resolution with explicit priority ordering.

**Resolution Order**:
```
CLI > .env > system defaults > NULL
```

**Key Methods**:
- `load_env(env_path)` — Load .env file into memory
- `resolve_prompt(cli_value, env_key, default)` — Resolve prompt values
- `resolve_seed(cli_value, env_key, experiment_name)` — Resolve seed (experiment level)
- `resolve_seed_for_run(cli_value, env_key, run_id, experiment_id)` — Resolve seed (run level)
- `build_experiment_config_dict(cli_args)` — Build experiment config
- `build_run_config_dict(cli_args, experiment)` — Build run config
- `build_model_config_dict(cli_args, experiment)` — Build model config

### 2.2 Environment Loading

**Implementation**:
```python
def load_env(self, env_path: str | None = None) -> dict[str, str]:
    if env_path is None:
        env_path = ".env"
    
    path = Path(env_path)
    if not path.exists():
        return {}
    
    load_dotenv(env_path, override=True)
    
    self.env_dict = {
        key: value
        for key, value in os.environ.items()
    }
    
    return self.env_dict
```

**Key Points**:
- Loads .env file into `self.env_dict`
- Uses `load_dotenv` with `override=True`
- Returns empty dict if file doesn't exist

---

## 3. Resolution Order

### 3.1 General Resolution Pattern

**All configuration values follow this pattern**:

1. **CLI Value** (if provided and not EXPLICIT_NULL)
2. **.env Value** (if key exists and not empty)
3. **Default** (if provided)
4. **NULL** (null-by-default)

### 3.2 Prompt Resolution

**Method**: `resolve_prompt(cli_value, env_key, default)`

**Implementation**:
```python
def resolve_prompt(
    self,
    cli_value: str | None,
    env_key: str,
    default: str | None = None
) -> str | None:
    # CLI was EXPLICIT_NULL → return None (no fallback)
    if cli_value is EXPLICIT_NULL:
        return None
    
    # CLI provided (not None, not EXPLICIT_NULL)
    if cli_value is not None and cli_value.strip():
        return cli_value.strip()
    
    # CLI was None (not specified) → check .env
    env_value = self.env_dict.get(env_key)
    if env_value is not None and env_value.strip():
        return env_value.strip()
    
    return default
```

**Key Points**:
- `EXPLICIT_NULL` means "explicitly null" — no fallback to .env
- Empty strings are treated as "not provided"
- Default is only used if CLI and .env are both missing

### 3.3 Seed Resolution (Experiment Level)

**Method**: `resolve_seed(cli_value, env_key, experiment_name)`

**Implementation**:
```python
def resolve_seed(
    self,
    cli_value: str | None,
    env_key: str,
    experiment_name: str
) -> int | str | None:
    # CLI was EXPLICIT_NULL → return None (no fallback)
    if cli_value is EXPLICIT_NULL:
        return None
    
    # Check CLI value first
    if cli_value is not None:
        parsed = parse_seed_value(cli_value)
        if parsed == "AUTO":
            return "AUTO"
        if isinstance(parsed, int):
            return parsed
    
    # CLI was None → check .env
    env_value = self.env_dict.get(env_key)
    if env_value is not None:
        parsed = parse_seed_value(env_value)
        if parsed == "AUTO":
            return "AUTO"
        if isinstance(parsed, int):
            return parsed
    
    return None
```

**Key Points**:
- Does NOT resolve "AUTO" to a number (happens at run level)
- Returns "AUTO" string if specified
- `EXPLICIT_NULL` means no fallback to .env

### 3.4 Seed Resolution (Run Level)

**Method**: `resolve_seed_for_run(cli_value, env_key, run_id, experiment_id)`

**Implementation**:
```python
def resolve_seed_for_run(
    self,
    cli_value: str | None,
    env_key: str,
    run_id: str,
    experiment_id: str
) -> int | None:
    if cli_value is not None:
        parsed = parse_seed_value(cli_value)
        if parsed == "AUTO":
            return self._generate_seed_from_run(run_id, experiment_id)
        if isinstance(parsed, int):
            return parsed
    
    env_value = self.env_dict.get(env_key)
    if env_value is not None:
        parsed = parse_seed_value(env_value)
        if parsed == "AUTO":
            return self._generate_seed_from_run(run_id, experiment_id)
        if isinstance(parsed, int):
            return parsed
    
    return None
```

**Key Points**:
- **This is the ONLY place where AUTO is resolved to a number**
- Generates deterministic seed from `run_id:experiment_id` hash
- Used at RUN_CREATION time

### 3.5 Deterministic Seed Generation

**From Experiment Name**:
```python
def _generate_seed_from_name(self, experiment_name: str) -> int:
    hash_bytes = hashlib.sha256(experiment_name.encode()).digest()
    seed = int.from_bytes(hash_bytes[:8], byteorder='big')
    return seed % (2**31)
```

**From Run ID**:
```python
def _generate_seed_from_run(self, run_id: str, experiment_id: str) -> int:
    combined = f"{experiment_id}:{run_id}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    seed = int.from_bytes(hash_bytes[:8], byteorder='big')
    return seed % (2**31)
```

---

## 4. Null Semantics

### 4.1 EXPLICIT_NULL Constant

**Definition**:
```python
# In src/core/null_semantics.py
EXPLICIT_NULL = "__EXPLICIT_NULL__"  # Sentinel value
```

**Purpose**: Represents an explicit "null" passed via CLI.

**Behavior**:
- Means "use system default" (bypass .env hierarchy)
- Case-insensitive (`"null"`, `"NULL"`, `"Null"` all map to EXPLICIT_NULL)
- Serialized as JSON `null` (not string `"null"`)

### 4.2 CLI Null Normalization

**Contract** (from `cli_null_semantics.md`):

```python
"null" → None  # Python None
"null" → null  # JSON null
```

**Normalization Rule**:
- All optional CLI arguments pass through normalization
- `"null"` (case-insensitive) → Python `None`
- `None` → JSON `null` (not string `"null"`)

### 4.3 Mandatory Fields

**Fields that must NEVER accept `null`**:
- `--url` (BASE_URL)
- `--dataset-path` (QUESTIONS_DATASET_PATH)

**Behavior**: Passing `null` to mandatory fields raises an explicit error.

### 4.4 Resolution with EXPLICIT_NULL

**Pattern**:
```python
def _resolve_with_explicit_null(self, cli_value, env_key, parser_func=None):
    # CLI was EXPLICIT_NULL → return None (no fallback)
    if cli_value is EXPLICIT_NULL:
        return None
    
    # CLI provided
    if cli_value is not None:
        return cli_value
    
    # CLI was None → check .env
    env_value = self.env_dict.get(env_key)
    if env_value is not None:
        if parser_func:
            return parser_func(env_key)
        return env_value
    
    return None
```

---

## 5. Configuration Capture Timing

### 5.1 Entity Creation Points

| Entity | When Captured | What's Captured |
|--------|---------------|-----------------|
| **Experiment** | Creation | Questions dataset path, protocol config |
| **Model Variant** | Creation | All 10 model-level keys |
| **Run** | Creation | Seed (AUTO resolved), prompts |

### 5.2 Experiment Creation

**Method**: `build_experiment_config_dict(cli_args)`

**Configuration Keys** (14 total):

**EXPERIMENT keys (1)**:
- `QUESTIONS_DATASET_PATH` — Resolved from .env at experiment creation

**MODEL keys (10)** — Resolved from CLI/.env as defaults for model variants:
- `BASE_URL`
- `MODEL_MAX_TOKENS_REASONING`
- `MODEL_MAX_TOKENS_TOTAL`
- `MODEL_REASONING_EFFORT`
- `MODEL_REPEAT_PENALTY`
- `MODEL_TEMPERATURE`
- `MODEL_TOP_K`
- `MODEL_TOP_P`
- `MODEL_VISION`
- `STRUCTURED_OUTPUTS`

**RUN keys (3)** — Resolved from CLI/.env as defaults for runs:
- `RUN_RESPONSES_SEED` — Resolved (not AUTO), defaults to "OFF"
- `SYSTEM_PROMPT` — Resolved from CLI/.env
- `USER_PROMPT` — Resolved from CLI/.env

**Implementation**:
```python
def build_experiment_config_dict(self, cli_args) -> dict:
    resolved_seed = self.resolve_seed(
        cli_value=getattr(cli_args, 'seed', None),
        env_key="RUN_RESPONSES_SEED",
        experiment_name=getattr(cli_args, 'create_experiment', 'default')
    )
    
    return {
        # EXPERIMENT keys (1)
        "QUESTIONS_DATASET_PATH": self.env_dict.get("QUESTIONS_DATASET_PATH"),
        
        # MODEL keys (10)
        "BASE_URL": self._resolve_with_explicit_null(...),
        "MODEL_MAX_TOKENS_REASONING": self._resolve_with_explicit_null(...),
        # ... more model keys
        
        # RUN keys (3)
        "RUN_RESPONSES_SEED": resolved_seed if resolved_seed is not None else "OFF",
        "SYSTEM_PROMPT": self.resolve_prompt(...),
        "USER_PROMPT": self.resolve_prompt(...),
    }
```

### 5.3 Run Creation

**Method**: `build_run_config_dict(cli_args, experiment)`

**Configuration Keys** (3 total):
- `RUN_RESPONSES_SEED` — int | None (AUTO resolved here)
- `SYSTEM_PROMPT` — str | None
- `USER_PROMPT` — str | None

**Inheritance**:
- Inherits from experiment config as fallback
- CLI overrides experiment config

**Implementation**:
```python
def build_run_config_dict(self, cli_args, experiment) -> dict:
    import json
    exp_config = json.loads(experiment.config_json) if experiment.config_json else {}
    
    resolved_seed = self.resolve_seed_for_run(
        cli_value=getattr(cli_args, 'seed', None),
        env_key="RUN_RESPONSES_SEED",
        run_id="",
        experiment_id=experiment.experiment_id
    )
    
    resolved_system_prompt = self.resolve_prompt(
        cli_value=getattr(cli_args, 'system_prompt', None),
        env_key="SYSTEM_PROMPT",
        default=exp_config.get("SYSTEM_PROMPT")
    )
    
    resolved_user_prompt = self.resolve_prompt(
        cli_value=getattr(cli_args, 'user_prompt', None),
        env_key="USER_PROMPT",
        default=exp_config.get("USER_PROMPT")
    )
    
    return {
        "RUN_RESPONSES_SEED": resolved_seed,
        "SYSTEM_PROMPT": resolved_system_prompt,
        "USER_PROMPT": resolved_user_prompt,
    }
```

### 5.4 Model Variant Creation

**Method**: `build_model_config_dict(cli_args, experiment)`

**Configuration Keys** (10 total):
- `BASE_URL` — str | None
- `MODEL_MAX_TOKENS_REASONING` — int | None
- `MODEL_MAX_TOKENS_TOTAL` — int | None
- `MODEL_REASONING_EFFORT` — str | None
- `MODEL_REPEAT_PENALTY` — float | None
- `MODEL_TEMPERATURE` — float | None
- `MODEL_TOP_K` — int | None
- `MODEL_TOP_P` — float | None
- `MODEL_VISION` — bool | None
- `STRUCTURED_OUTPUTS` — bool | None

**Resolution Order**:
```
CLI > .env > experiment config > NULL
```

**Implementation**:
```python
def build_model_config_dict(self, cli_args, experiment) -> dict:
    import json
    exp_config = json.loads(experiment.config_json) if experiment.config_json else {}
    
    def resolve_cli_or_env(cli_value, env_key, default=None):
        if cli_value is not None:
            if isinstance(cli_value, (float, int)):
                return str(cli_value)
            if cli_value.strip():
                return cli_value.strip()
        env_value = self.env_dict.get(env_key)
        if env_value is not None and env_value.strip():
            return env_value.strip()
        return default
    
    return {
        "BASE_URL": resolve_cli_or_env(getattr(cli_args, 'url', None), "BASE_URL"),
        "MODEL_MAX_TOKENS_REASONING": parse_int(resolve_cli_or_env(...)),
        # ... more keys
    }
```

---

## 6. JSON Storage for Configs

### 6.1 Storage Format

**All entity configurations are stored as JSON strings**:

- `experiments.config_json` — TEXT NOT NULL
- `model_variants.config` — TEXT NOT NULL
- `runs.config` — TEXT NOT NULL

### 6.2 Experiment Config JSON

**Structure**:
```json
{
  "QUESTIONS_DATASET_PATH": "data\\enamed_questions.json",
  "BASE_URL": "https://openrouter.ai/api/v1",
  "MODEL_MAX_TOKENS_TOTAL": 16384,
  "MODEL_TEMPERATURE": null,
  "MODEL_VISION": false,
  "STRUCTURED_OUTPUTS": false,
  "RUN_RESPONSES_SEED": "AUTO",
  "SYSTEM_PROMPT": null,
  "USER_PROMPT": "Select the correct answer..."
}
```

### 6.3 Null Serialization

**Rule**: Python `None` → JSON `null` (not string `"null"`)

**Example**:
```python
import json

config = {
    "MODEL_TEMPERATURE": None,  # Python None
    "MODEL_VISION": False,
}

json_string = json.dumps(config)
# Result: {"MODEL_TEMPERATURE": null, "MODEL_VISION": false}
```

---

## 7. Configuration Keys Inventory

### 7.1 SYSTEM Keys (Resolved at System Start)

**Not persisted in entities** — resolved at system startup:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `DATABASE_PATH` | string | `./data/benchmark.db` | Database path |
| `EXECUTION_MODE` | enum | `normal` | Execution mode |
| `LOG_FILE_PATH` | string | NULL | Log file path |
| `LOG_LEVEL` | enum | `INFO` | Log level |
| `OPENROUTER_DEBUG_ENABLED` | bool | `FALSE` | Debug mode |

### 7.2 EXPERIMENT Keys (Resolved at Experiment Creation)

**Persisted in `experiment.config_json`**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `QUESTIONS_DATASET_PATH` | string | none | Questions dataset path |

**Transient** (not persisted):
- `DEFAULT_QUESTIONS` — Used for question selection
- `QUESTIONS_STATUS_ADD` — Filter for adding questions
- `QUESTIONS_STATUS_EXCLUDE` — Filter for excluding questions
- `MODELS_DEFAULT_FOR_EXPERIMENTS` — Default models (not used, models added explicitly)

### 7.3 MODEL Keys (Resolved at Model Variant Creation)

**Persisted in `model_variant.config`**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `BASE_URL` | string | none | Model API endpoint |
| `MODEL_MAX_TOKENS_REASONING` | int | NULL | Max reasoning tokens |
| `MODEL_MAX_TOKENS_TOTAL` | int | NULL | Max total tokens |
| `MODEL_REASONING_EFFORT` | enum | NULL | Reasoning effort level |
| `MODEL_REPEAT_PENALTY` | float | NULL | Repeat penalty |
| `MODEL_TEMPERATURE` | float | NULL | Temperature |
| `MODEL_TOP_K` | int | NULL | Top-K sampling |
| `MODEL_TOP_P` | float | NULL | Top-P sampling |
| `MODEL_VISION` | bool | NULL | Vision support |
| `STRUCTURED_OUTPUTS` | bool | NULL | JSON schema outputs |

### 7.4 RUN Keys (Resolved at Run Creation)

**Persisted in `run.config`**:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `RUN_RESPONSES_SEED` | int/AUTO/OFF | OFF | Random seed |
| `SYSTEM_PROMPT` | string | NULL | System prompt |
| `USER_PROMPT` | string | NULL | User prompt |

---

## 8. Boolean Resolution

### 8.1 CLI Boolean Parsing

**Implementation**:
```python
def _parse_bool_value(self, value: str | None) -> bool | None:
    if value is None:
        return None
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    if value.upper() == 'NULL':
        return None
    return None
```

**Accepted Values**:
- `true`, `1`, `yes` → `True`
- `false`, `0`, `no` → `False`
- `null`, `NULL`, `Null` → `None`

### 8.2 Environment Boolean Parsing

**Implementation**:
```python
def _parse_bool_env(self, key: str) -> bool | None:
    value = self.env_dict.get(key)
    if not value:
        return None
    if value.lower() in ('true', '1', 'yes'):
        return True
    if value.lower() in ('false', '0', 'no'):
        return False
    return None
```

### 8.3 CLI-or-Env Resolution

**Implementation**:
```python
def _resolve_bool_cli_or_env(self, cli_value: str | None, env_key: str) -> bool | None:
    if cli_value is not None:
        parsed = self._parse_bool_value(cli_value)
        if parsed is not None:
            return parsed
        if cli_value.upper() == 'NULL':
            return None
    return self._parse_bool_env(env_key)
```

---

## 9. Integer and Float Parsing

### 9.1 Integer Parsing

**From Environment**:
```python
def _parse_int_env(self, key: str) -> int | None:
    value = self.env_dict.get(key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None
```

### 9.2 Float Parsing

**From Environment**:
```python
def _parse_float_env(self, key: str) -> float | None:
    value = self.env_dict.get(key)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
```

---

## 10. Key Design Decisions

### 10.1 Explicit Priority Ordering

**Decision**: CLI > .env > system defaults > NULL

**Rationale**:
- Explicit configuration always wins
- .env is only a default source
- NULL is a valid state (null-by-default)

### 10.2 EXPLICIT_NULL Semantics

**Decision**: CLI `null` means explicit absence, no fallback.

**Rationale**:
- Allows bypassing .env defaults
- Explicit intent over implicit behavior
- Consistent with "no inference" principle

### 10.3 AUTO Seed Resolution Timing

**Decision**: AUTO is resolved at RUN_CREATION, not experiment creation.

**Rationale**:
- Each run gets a unique deterministic seed
- Experiment-level config stores "AUTO" string
- Run-level resolution generates actual integer

### 10.4 JSON Storage

**Decision**: All entity configs stored as JSON strings.

**Rationale**:
- Flexible schema (add/remove keys without migrations)
- Easy serialization
- NULL values preserved as JSON `null`

### 10.5 Null-by-Default for Prompts

**Decision**: Prompts default to NULL (no fallback strings).

**Rationale**:
- No implicit defaults
- Explicit configuration required
- Auditable (can see what was actually configured)

---

## 11. Summary

The V2 Configuration System is built around these foundational concepts:

1. **ConfigResolver** — Centralized resolution component

2. **Explicit Priority** — CLI > .env > defaults > NULL

3. **EXPLICIT_NULL** — CLI `null` means no fallback

4. **Null-by-Default** — Prompts and optional values default to NULL

5. **Capture at Creation** — Configuration frozen when entity is created

6. **JSON Storage** — All configs stored as JSON strings

7. **AUTO Seed at Run Level** — AUTO resolved only at run creation

8. **No Inference** — Nothing is automatically inferred

This document captures the current state of V2 Configuration System implementation without proposing fixes.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Source**: `src/core/config_resolver.py`, `docs/architecture/contracts/`
