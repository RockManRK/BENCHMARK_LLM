# Configuration System — Architecture & Contracts

**Document Type:** Architecture Specification (TO-BE)
**Domain:** Configuration System
**Purpose:** Define the target architecture and contracts for configuration resolution

---

## 1. Configuration Philosophy

### 1.1 Core Principles

The Configuration System is built on these foundational principles:

1. **Explicit > Inherited**
   - Explicit configuration (CLI) always wins
   - Inherited configuration (.env) is only a default
   - Nothing is automatically inferred

2. **Null-by-Default**
   - Optional values default to NULL
   - NULL is a valid state (not an error)
   - NULL means "don't send" (for API parameters)

3. **Capture at Creation**
   - Configuration is frozen when entity is created
   - Entities don't inherit from .env after creation
   - Historical data is immutable

4. **No Inference During Execution**
   - ExecutionEngine doesn't resolve configuration
   - All configuration is pre-computed
   - Execution is deterministic

5. **Auditable Resolution**
   - Every configuration value has a known source
   - NULL values are explicit (not accidental)
   - Resolution is reproducible

---

## 2. Resolution Hierarchy Contract

### 2.1 Resolution Order

**All configuration values follow this priority**:

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Arguments                        │
│              (highest priority, explicit)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    .env File                            │
│            (default values, can be bypassed)            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                 System Defaults                         │
│              (built-in defaults, rare)                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                      NULL                               │
│            (null-by-default for optional)               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Hierarchy vs Override

**Critical Distinction**:

| Concept | Description | Example |
|---------|-------------|---------|
| **Hierarchy** (Inheritance) | Parent → Child inheritance | Experiment → Run → Model Variant |
| **Override** (Explicit) | Higher priority wins | CLI > .env |

**Hierarchy** (what child inherits from parent):
```
System Defaults ← .env ← Experiment ← Run/Model Variant
```

**Override** (what wins when specified):
```
CLI > .env > System Defaults
```

### 2.3 FORCE_SYSTEM_DEFAULT Behavior

**Definition**: `FORCE_SYSTEM_DEFAULT` is a sentinel value representing explicit `"system-default"` passed via CLI.

**Behavior**:
```
CLI: --temperature system-default
     ↓
FORCE_SYSTEM_DEFAULT (sentinel)
     ↓
Return None (no fallback to .env)
```

**Contract**:
- `FORCE_SYSTEM_DEFAULT` bypasses .env hierarchy
- Case-insensitive: `"system-default"`, `"SYSTEM-DEFAULT"`, `"System-Default"` all map to `FORCE_SYSTEM_DEFAULT`
- Serialized as JSON `null` (not string `"system-default"`)

### 2.4 Resolution Pseudocode

```python
def resolve_value(cli_value, env_key, default=None):
    # CLI was FORCE_SYSTEM_DEFAULT → no fallback
    if cli_value is FORCE_SYSTEM_DEFAULT:
        return None

    # CLI provided → use CLI value
    if cli_value is not None:
        return cli_value

    # CLI not provided → check .env
    env_value = env_dict.get(env_key)
    if env_value is not None:
        return env_value

    # .env not set → use default (or NULL)
    return default
```

---

## 3. Null Semantics Contract

### 3.1 Null Definition

**NULL** in the Configuration System means:

| Context | Meaning |
|---------|---------|
| **CLI** | "Explicitly don't set this value" |
| **.env** | "Use system default" |
| **API Request** | "Don't send this parameter" |
| **Storage** | JSON `null` (not string `"null"`) |

### 3.2 Null Normalization

**CLI Input**:
```
"system-default" (string, case-insensitive) → FORCE_SYSTEM_DEFAULT (sentinel) → None (Python) → null (JSON)
```

**Implementation**:
```python
def normalize_system_default(value: str | None) -> str | None:
    if value is None:
        return None
    if value.lower() == "system-default":
        return FORCE_SYSTEM_DEFAULT
    return value
```

### 3.3 Mandatory vs Optional Fields

**Mandatory Fields** (must NEVER accept `null`):
- `BASE_URL` — API endpoint is required
- `QUESTIONS_DATASET_PATH` — Dataset path is required

**Behavior**:
```python
if cli_value is FORCE_SYSTEM_DEFAULT and field.is_mandatory:
    raise ConfigurationError(f"{field.name} cannot be system-default")
```

**Optional Fields** (can accept `"system-default"`):
- All MODEL keys (temperature, max_tokens, etc.)
- All RUN keys (prompts, seed)

**Behavior**:
```python
if cli_value is FORCE_SYSTEM_DEFAULT:
    return None  # Valid for optional fields
```

### 3.4 Empty String Handling

**Contract**:
- Empty string (`""`) → treated as "not provided" → falls through to next level
- Whitespace-only string → trimmed → treated as empty

**Implementation**:
```python
if value is not None and value.strip():
    return value.strip()  # Non-empty
return None  # Empty or whitespace-only
```

---

## 4. Capture Timing Contract

### 4.1 Entity Creation Points

| Entity | When Captured | What's Captured | Inheritance |
|--------|---------------|-----------------|-------------|
| **Experiment** | Creation | 14 keys (1 EXP + 10 MODEL + 3 RUN) | .env defaults |
| **Model Variant** | Creation | 10 MODEL keys | Experiment config |
| **Run** | Creation | 3 RUN keys (AUTO resolved) | Experiment config |

### 4.2 Experiment Creation

**Trigger**: `--create-experiment <name>`

**What's Resolved**:
```
CLI > .env → experiment.config_json
```

**Configuration Keys** (14 total):

**EXPERIMENT (1)**:
- `QUESTIONS_DATASET_PATH` — Resolved from .env

**MODEL (10)** — Defaults for model variants:
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

**RUN (3)** — Defaults for runs:
- `RUN_RESPONSES_SEED` — Resolved (not AUTO), defaults to "OFF"
- `SYSTEM_PROMPT` — Resolved from CLI/.env
- `USER_PROMPT` — Resolved from CLI/.env

**Immutability**:
- `experiment.config_json` is NEVER updated after creation
- Child entities (runs, variants) inherit from this frozen config

---

### 4.3 Model Variant Creation

**Trigger**: `--experiment <name> --add-model <model_id>`

**What's Resolved**:
```
CLI > .env > experiment.config → model_variant.config
```

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

**Inheritance**:
- Variant inherits from `experiment.config_json` as fallback
- CLI overrides experiment config
- .env overrides experiment config

**Immutability**:
- `model_variant.config` is NEVER updated after creation

---

### 4.4 Run Creation

**Trigger**: `--experiment <name> --create-run <run_name>`

**What's Resolved**:
```
CLI > .env > experiment.config → run.config
```

**Configuration Keys** (3 total):
- `RUN_RESPONSES_SEED` — int | "AUTO" | None
  - **AUTO is resolved here** (at RUN_CREATION)
  - Generates deterministic seed from `run_id:experiment_id`
- `SYSTEM_PROMPT` — str | None
- `USER_PROMPT` — str | None

**Inheritance**:
- Run inherits from `experiment.config_json` as fallback
- CLI overrides experiment config
- .env overrides experiment config

**Immutability**:
- `run.config` is NEVER updated after creation

---

### 4.5 Execution Time

**Trigger**: `--experiment <name> --run <run_name> --execute`

**What's Resolved**: **NOTHING**

**Contract**:
- ExecutionEngine does NOT resolve configuration
- ExecutionEngine reads pre-computed config from ExecutionPlan
- All configuration is frozen before execution

**Flow**:
```
Planner → ExecutionPlan (immutable) → ExecutionEngine → ResultWriter
                                    ↑
                              Config frozen here
```

---

## 5. Immutability Rules

### 5.1 Immutable Entities

**Fully Immutable** (no updates after creation):
- `experiments.config_json` — Frozen at experiment creation
- `model_variants.config` — Frozen at variant creation
- `runs.config` — Frozen at run creation

**Rationale**:
- Reproducibility (historical data preserved)
- Auditability (clear configuration history)
- No implicit changes (configuration doesn't drift)

### 5.2 Mutable Fields

**Partially Mutable** (some fields can change):

| Entity | Immutable Fields | Mutable Fields |
|--------|------------------|----------------|
| `experiments` | All fields | None |
| `model_variants` | All fields | None |
| `runs` | `config` | `status`, `duration` |

### 5.3 .env After Creation

**Contract**:
> After an entity is created, `.env` is NEVER consulted for that entity.

**Example**:
```
1. Create experiment with TEMPERATURE=0.7 in .env
   → experiment.config_json = {"MODEL_TEMPERATURE": 0.7}

2. Change .env to TEMPERATURE=0.9
   → experiment.config_json is STILL 0.7 (frozen)

3. Create new experiment
   → new_experiment.config_json = {"MODEL_TEMPERATURE": 0.9}
```

**Rationale**:
- `.env` is only a default source
- Explicit configuration (at creation) wins
- Historical data is reproducible

---

## 6. Inheritance Rules

### 6.1 Parent → Child Inheritance

**Hierarchy**:
```
System ← .env ← Experiment ← Run/Model Variant
```

**Inheritance Pattern**:
```python
# Model Variant creation
variant_config = {
    "MODEL_TEMPERATURE": cli_value or .env_value or experiment_config.get("MODEL_TEMPERATURE")
}

# Run creation
run_config = {
    "SYSTEM_PROMPT": cli_value or .env_value or experiment_config.get("SYSTEM_PROMPT")
}
```

### 6.2 Sibling Independence

**Contract**:
> Sibling entities (runs, variants) are independent. Changes to one don't affect others.

**Example**:
```
Experiment A
├── Variant 1 (temperature=0.7)
├── Variant 2 (temperature=0.9)  ← Independent of Variant 1
├── Run 1 (seed=42)
└── Run 2 (seed=AUTO)  ← Independent of Run 1
```

### 6.3 Override vs Inheritance

**Distinction**:

| Concept | Direction | Example |
|---------|-----------|---------|
| **Override** | CLI > .env | CLI `--temperature 0.8` overrides .env `TEMPERATURE=0.7` |
| **Inheritance** | Parent → Child | Run inherits from Experiment config |

**Combined Example**:
```
.env: TEMPERATURE=0.7
Experiment: {"MODEL_TEMPERATURE": 0.7}
Variant: CLI --temperature system-default → None (FORCE_SYSTEM_DEFAULT, no fallback)
Variant: CLI not specified → 0.7 (inherited from experiment)
Variant: CLI --temperature 0.9 → 0.9 (CLI override)
```

---

## 7. Configuration Key Inventory

### 7.1 SYSTEM Keys (5 keys)

**Resolved at**: System startup
**Persisted in**: Not persisted (runtime only)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `DATABASE_PATH` | string | `./data/benchmark.db` | Database path |
| `EXECUTION_MODE` | enum | `normal` | Execution mode |
| `LOG_FILE_PATH` | string | NULL | Log file path |
| `LOG_LEVEL` | enum | `INFO` | Log level |
| `OPENROUTER_DEBUG_ENABLED` | bool | `FALSE` | Debug mode |

---

### 7.2 EXPERIMENT Keys (1 persisted + 4 transient)

**Resolved at**: Experiment creation
**Persisted in**: `experiment.config_json`

| Key | Type | Default | Description | Persisted |
|-----|------|---------|-------------|-----------|
| `QUESTIONS_DATASET_PATH` | string | none | Questions dataset path | ✅ |

**Transient** (not persisted, used only during creation):
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `DEFAULT_QUESTIONS` | list | NULL | Default questions for selection |
| `QUESTIONS_STATUS_ADD` | string | NULL | Filter for adding questions |
| `QUESTIONS_STATUS_EXCLUDE` | string | NULL | Filter for excluding questions |

---

### 7.3 MODEL Keys (10 keys)

**Resolved at**: Model variant creation
**Persisted in**: `model_variant.config`

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

---

### 7.4 RUN Keys (3 keys)

**Resolved at**: Run creation
**Persisted in**: `run.config`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `RUN_RESPONSES_SEED` | int/AUTO/OFF | OFF | Random seed |
| `SYSTEM_PROMPT` | string | NULL | System prompt |
| `USER_PROMPT` | string | NULL | User prompt |

---

### 7.5 Key Count Summary

| Category | Count | Persisted |
|----------|-------|-----------|
| **SYSTEM** | 5 | 0 |
| **EXPERIMENT** | 1 (+ 4 transient) | 1 |
| **MODEL** | 10 | 10 |
| **RUN** | 3 | 3 |
| **TOTAL** | **23** (+ 4 transient) | **14** |

---

## 8. Type Validation Rules

### 8.1 String Validation

**Contract**:
- Trim whitespace
- Empty string → NULL
- Non-empty → trimmed value

**Implementation**:
```python
def validate_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value if value else None
```

### 8.2 Integer Validation

**Contract**:
- Parse from string
- Invalid format → NULL (for optional) or Error (for mandatory)

**Implementation**:
```python
def validate_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None  # or raise Error for mandatory fields
```

### 8.3 Float Validation

**Contract**:
- Parse from string
- Invalid format → NULL (for optional) or Error (for mandatory)

**Implementation**:
```python
def validate_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None  # or raise Error for mandatory fields
```

### 8.4 Boolean Validation

**Contract**:
- Accept: `true`, `false`, `1`, `0`, `yes`, `no` (case-insensitive)
- `null` → NULL
- Invalid → NULL (for optional) or Error (for mandatory)

**Implementation**:
```python
def validate_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    value_lower = value.lower().strip()
    if value_lower in ('true', '1', 'yes'):
        return True
    if value_lower in ('false', '0', 'no'):
        return False
    if value_lower == 'system-default':
        return None
    return None  # or raise Error for mandatory fields
```

### 8.5 Enum Validation

**Contract**:
- Case-insensitive matching
- Invalid value → NULL (for optional) or Error (for mandatory)

**Example** (Reasoning Effort):
```python
VALID_EFFORTS = {'xhigh', 'high', 'medium', 'low', 'minimal', 'none'}

def validate_reasoning_effort(value: str | None) -> str | None:
    if value is None:
        return None
    value_lower = value.lower().strip()
    if value_lower in VALID_EFFORTS:
        return value_lower
    return None  # or raise Error for mandatory fields
```

---

## 9. Seed Resolution Contract

### 9.1 Seed Values

**Accepted Values**:
| Value | Meaning |
|-------|---------|
| Integer (e.g., `42`) | Fixed seed for reproducibility |
| `"AUTO"` (case-insensitive) | Automatic deterministic seed |
| `null` | No randomization (original A,B,C,D order) |
| Empty/None | No randomization (original A,B,C,D order) |

### 9.2 Resolution Timing

**Experiment Level** (stores value, doesn't resolve AUTO):
```python
def resolve_seed_experiment(cli_value, env_key, experiment_name):
    # Returns: int | "AUTO" | None
    # Does NOT resolve "AUTO" to integer
```

**Run Level** (resolves AUTO to integer):
```python
def resolve_seed_run(cli_value, env_key, run_id, experiment_id):
    # Returns: int | None
    # Resolves "AUTO" to deterministic integer
```

### 9.3 AUTO Resolution Algorithm

**Implementation**:
```python
def _generate_seed_from_run(run_id: str, experiment_id: str) -> int:
    combined = f"{experiment_id}:{run_id}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    seed = int.from_bytes(hash_bytes[:8], byteorder='big')
    return seed % (2**31)
```

**Properties**:
- Deterministic (same run_id + experiment_id → same seed)
- Unique per run (different run_id → different seed)
- Positive integer (modulo 2^31)

---

## 10. JSON Serialization Contract

### 10.1 Serialization Rules

**Contract**:
- Python `None` → JSON `null`
- Python `True` → JSON `true`
- Python `False` → JSON `false`
- Python `int` → JSON number
- Python `float` → JSON number
- Python `str` → JSON string

**Implementation**:
```python
import json

config = {
    "MODEL_TEMPERATURE": None,  # Python None
    "MODEL_VISION": False,      # Python False
    "MODEL_MAX_TOKENS_TOTAL": 16384,  # Python int
}

json_string = json.dumps(config)
# Result: {"MODEL_TEMPERATURE": null, "MODEL_VISION": false, "MODEL_MAX_TOKENS_TOTAL": 16384}
```

### 10.2 Deserialization Rules

**Contract**:
- JSON `null` → Python `None`
- JSON `true` → Python `True`
- JSON `false` → Python `False`
- JSON number → Python `int` or `float`
- JSON string → Python `str`

**Implementation**:
```python
import json

config_dict = json.loads(json_string)
# null → None, false → False, 16384 → 16384
```

### 10.3 Storage Format

**Database Columns**:
- `experiments.config_json` — TEXT NOT NULL
- `model_variants.config` — TEXT NOT NULL
- `runs.config` — TEXT NOT NULL

**Format**: Compact JSON (no pretty printing)

**Example**:
```json
{"QUESTIONS_DATASET_PATH":"data\\enamed_questions.json","MODEL_TEMPERATURE":null,"MODEL_VISION":false}
```

---

## 11. Error Handling Contract

### 11.1 Error Types

| Error Type | When Raised | Example |
|------------|-------------|---------|
| `ConfigurationError` | General configuration failure | Invalid value |
| `MandatoryFieldError` | Mandatory field is null | `BASE_URL=null` |
| `ValidationError` | Value fails validation | `TEMPERATURE=abc` |

### 11.2 Error Messages

**Contract**:
- Clear and specific
- Include field name
- Include expected type/value
- Include actual value

**Example**:
```
ConfigurationError: BASE_URL cannot be null. 
Expected: Valid URL string (e.g., "https://api.example.com")
Actual: null
```

### 11.3 Error Recovery

**Contract**:
- Configuration errors are fatal (no automatic recovery)
- User must fix configuration and retry
- No partial execution (all-or-nothing)

---

## 12. Summary

The Configuration System Architecture is built on these foundational contracts:

1. **Resolution Hierarchy** — CLI > .env > defaults > NULL

2. **Null Semantics** — FORCE_SYSTEM_DEFAULT bypasses .env, null-by-default for optional

3. **Capture Timing** — Configuration frozen at entity creation

4. **Immutability** — Configs don't change after creation

5. **Inheritance** — Child inherits from parent, CLI overrides all

6. **Key Inventory** — 23 keys (+ 4 transient) across 4 categories

7. **Type Validation** — Explicit validation rules for each type

8. **Seed Resolution** — AUTO resolved at RUN_CREATION only

9. **JSON Serialization** — Python None → JSON null

10. **Error Handling** — Clear, specific errors with no automatic recovery

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Status**: Target Architecture (TO-BE)
