# Configuration System — V1 Legacy Analysis

**Document Type:** Legacy Analysis (Read-Only)
**Domain:** Configuration System
**Source:** `src_legacy/utils/config.py`
**Purpose:** Extract architectural concepts from V1 implementation for historical reference

---

## 1. Domain Overview

### 1.1 Purpose

The Configuration System provides centralized settings management for the benchmark_llm project. It handles configuration resolution from multiple sources (CLI, .env, system defaults), validates configuration values, and provides a unified interface for accessing settings throughout the application.

### 1.2 Core Responsibilities

- **Settings Management**: Define all configuration options using Pydantic Settings
- **Environment Variable Loading**: Load non-sensitive configuration from `.env` files
- **Validation**: Enforce type safety and value constraints using Pydantic validators
- **API Key Security**: Ensure API keys are loaded from system environment variables only
- **Execution Mode Control**: Support test, development, and experiment modes
- **Configuration Serialization**: Provide methods for hashing and dictionary conversion

### 1.3 Design Principles

1. **Security First**: API keys must come from system environment variables, not `.env` files
2. **Type Safety**: All configuration values are typed and validated
3. **Flexible Defaults**: Sensible defaults for non-sensitive configuration
4. **Mode-Aware**: Different behavior based on execution mode (test/dev/experiment)
5. **Immutability in Experiment Mode**: Configuration is frozen in experiment mode

---

## 2. Configuration Hierarchy

### 2.1 Resolution Order

V1 uses a **three-tier hierarchy**:

```
CLI Arguments > .env File > System Defaults
```

**Important**: V1 does **not** have explicit null semantics. Missing values fall back to the next level.

### 2.2 Resolution Timing

| Configuration Category | When Resolved | Notes |
|------------------------|---------------|-------|
| System Settings | Application startup | Database path, log level, execution mode |
| Experiment Settings | Experiment creation | Questions dataset path, default questions |
| Model Settings | Model variant creation | Temperature, max tokens, reasoning params |
| Run Settings | Run execution | Seed, prompts |

### 2.3 Environment Variable Patterns

**Naming Convention**: Uppercase with underscores

**Examples**:
- `OPENROUTER_API_KEY`
- `DATABASE_PATH`
- `LOG_LEVEL`
- `QUESTIONS_DATASET_PATH`
- `RUN_RESPONSES_SEED`
- `SYSTEM_PROMPT_TEMPLATE`
- `USER_PROMPT_TEMPLATE`

### 2.4 Configuration Persistence

**V1 Approach**: Configuration is stored in `config_json` field of experiments.

**Serialization**:
```python
def get_config_dict(self) -> dict:
    return {
        "default_prompt": self.default_prompt,
        "use_structured_outputs": self.use_structured_outputs,
        "random_seed_policy": str(self.random_seed) if self.random_seed else "none",
        "questionnaire_path": str(self.questionnaire_path),
        "model_max_tokens": self.model_max_tokens,
        "model_temperature": self.model_temperature,
        # ... more fields
    }
```

**Hash Calculation**:
```python
def get_config_hash(self) -> str:
    config_dict = self.get_protocol_config()
    config_json = json.dumps(config_dict, sort_keys=True, default=str)
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]
```

---

## 3. V1 Settings Class Structure

### 3.1 Settings Class Overview

**Base Class**: `pydantic_settings.BaseSettings`

**Key Features**:
- Field validation with `@field_validator`
- Model-level validation with `@model_validator`
- Computed properties for mode checks
- Configuration serialization methods

### 3.2 Configuration Categories

#### 3.2.1 OpenRouter API Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openrouter_api_key` | `str` | `""` | API key (from system env only) |
| `openrouter_base_url` | `str` | `"https://openrouter.ai/api/v1"` | API base URL |

**Security Validator**:
```python
@model_validator(mode="after")
def validate_api_key_from_env(self) -> "Settings":
    env_api_key = os.getenv("OPENROUTER_API_KEY")
    if env_api_key:
        object.__setattr__(self, "openrouter_api_key", env_api_key)
    return self
```

#### 3.2.2 Database Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `database_path` | `Path` | `Path("./data/benchmark.db")` | SQLite database path |

#### 3.2.3 Logging Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `log_level` | `str` | `"INFO"` | Logging level |
| `log_file_path` | `Path` | `Path("./logs/benchmark.log")` | Log file path |

**Validator**:
```python
@field_validator("log_level")
@classmethod
def validate_log_level(cls, value: str) -> str:
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    value_upper = value.upper()
    if value_upper not in valid_levels:
        raise ValueError(f"Invalid log level: {value}")
    return value_upper
```

#### 3.2.4 Test Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_iterations` | `int` | `1` | Default iterations per model |
| `use_memory_db` | `bool` | `False` | Use in-memory database |
| `random_seed` | `Optional[str | int]` | `None` | Seed for randomization |

**Seed Validator**:
```python
@field_validator("random_seed", mode="before")
@classmethod
def validate_random_seed(cls, value: Optional[str | int]) -> Optional[str | int]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        if value.upper() == "AUTO":
            return "AUTO"
        try:
            value = int(value)
        except ValueError:
            raise ValueError(f"Random seed must be an integer or 'AUTO', got '{value}'")
    if isinstance(value, int) and value < 0:
        raise ValueError("Random seed must be a non-negative integer")
    return value
```

#### 3.2.5 Structured Outputs & Vision

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_structured_outputs` | `bool` | `False` | Use JSON schema responses |
| `enable_vision` | `bool` | `False` | Enable vision support |

#### 3.2.6 OpenRouter Debug Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `openrouter_debug_enabled` | `bool` | `False` | Enable debug mode |

**Experiment Mode Blocker**:
```python
@model_validator(mode="after")
def validate_openrouter_debug_enabled_after(self) -> "Settings":
    if self.execution_mode == ExecutionMode.EXPERIMENT and self.openrouter_debug_enabled:
        logger.warning("openrouter_debug_enabled is BLOCKED in EXPERIMENT mode.")
        object.__setattr__(self, "openrouter_debug_enabled", False)
    return self
```

#### 3.2.7 Prompt Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `default_prompt` | `Optional[str]` | `None` | Default prompt instruction |
| `default_questions` | `Optional[str]` | `None` | Default questions (from .env) |
| `questions_dataset_path` | `Path` | `Path("./data/enamed_questions.json")` | Questions dataset path |
| `questionnaire_path` | `Path` | `Path("./data/enamed_questions.json")` | Questionnaire path |

#### 3.2.8 Execution Mode Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `execution_mode` | `ExecutionMode` | `ExecutionMode.DEV` | Test, dev, or experiment |
| `experiment_name` | `Optional[str]` | `None` | Experiment name (required for experiment mode) |
| `system_prompt` | `Optional[str]` | `None` | System prompt template |
| `user_prompt_template` | `Optional[str]` | `None` | User prompt template |

**Execution Mode Enum**:
```python
class ExecutionMode(str, Enum):
    TEST = "test"           # No persistence, in-memory DB
    DEV = "dev"             # Persistence, no experiment tracking
    EXPERIMENT = "experiment"  # Persistence with frozen config
```

#### 3.2.9 Model Generation Parameters

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_max_tokens` | `Optional[int]` | `None` | Max tokens for generation |
| `model_temperature` | `Optional[float]` | `None` | Temperature parameter |
| `model_top_p` | `Optional[float]` | `None` | Top-P sampling |
| `model_top_k` | `Optional[int]` | `None` | Top-K sampling |
| `model_repeat_penalty` | `Optional[float]` | `None` | Repeat penalty |

#### 3.2.10 Reasoning Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reasoning_effort` | `Optional[str]` | `None` | Effort level (xhigh, high, medium, low, minimal, none) |
| `reasoning_max_tokens` | `Optional[int]` | `None` | Max tokens for reasoning |
| `reasoning_exclude` | `Optional[bool]` | `None` | Exclude reasoning from response |
| `reasoning_enabled` | `Optional[bool]` | `None` | Enable reasoning |

#### 3.2.11 Model Variant Identity

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `reasoning_mode` | `Optional[str]` | `"unspecified"` | Reasoning mode for variant identity |
| `enable_vision` | `bool` | `False` | Vision for variant identity |
| `enable_structured` | `bool` | `False` | Structured outputs for variant identity |

---

## 4. Null Handling in V1

### 4.1 Null Semantics

**V1 Behavior**: No explicit null semantics.

- `None` values are allowed for optional fields
- Empty strings are treated as "not provided"
- No `EXPLICIT_NULL` concept
- Missing CLI values fall back to .env, then to defaults

### 4.2 Empty String Handling

**Pattern**: Empty strings are converted to `None` in validators:

```python
@field_validator("model_max_tokens", mode="before")
@classmethod
def validate_model_max_tokens(cls, value: Optional[str | int]) -> Optional[int]:
    if value is None or value == "":
        return None
    # ... parse integer
```

### 4.3 Optional vs Required Fields

**Required Fields** (raise error if missing):
- `experiment_name` (in experiment mode)
- `openrouter_api_key` (must be set via system env)

**Optional Fields** (default to `None` or sensible default):
- All model generation parameters
- Reasoning parameters
- Prompts

---

## 5. Configuration Capture Timing

### 5.1 Experiment Creation

**What's Captured**:
- `questions_dataset_path`
- `default_questions` (transient)
- Protocol configuration (for hash):
  - `default_prompt`
  - `use_structured_outputs`
  - `random_seed_policy`

**What's NOT Stored**:
- Model generation parameters (considered model variants)
- Reasoning parameters (considered model variants)

### 5.2 Model Variant Creation

**What's Captured**:
- `reasoning_mode`
- `enable_vision`
- `enable_structured`
- Generation parameters (temperature, max_tokens, etc.)

**Identity Fields** (define variant signature):
- `reasoning_mode`
- `reasoning_effort` (when mode='effort')
- `max_output_tokens` (when mode='budget')
- `vision_enabled`
- `structured_output`
- `web_access_enabled`

### 5.3 Run Execution

**What's Resolved**:
- `random_seed` (or "AUTO")
- `system_prompt`
- `user_prompt_template`

**Inheritance**:
- Runs inherit from experiment defaults
- CLI overrides .env

---

## 6. Computed Properties

### 6.1 Mode Check Properties

```python
@property
def should_persist_data(self) -> bool:
    return self.execution_mode != ExecutionMode.TEST

@property
def is_dev_mode(self) -> bool:
    return self.execution_mode == ExecutionMode.DEV

@property
def is_experiment_mode(self) -> bool:
    return self.execution_mode == ExecutionMode.EXPERIMENT

@property
def is_test_mode(self) -> bool:
    return self.execution_mode == ExecutionMode.TEST

@property
def is_config_frozen(self) -> bool:
    return self.execution_mode == ExecutionMode.EXPERIMENT
```

### 6.2 API Configuration Check

```python
@property
def is_api_configured(self) -> bool:
    return bool(self.openrouter_api_key)
```

---

## 7. Configuration Serialization

### 7.1 Protocol Configuration

**Purpose**: Fields that define the experiment protocol (used in hash).

```python
def get_protocol_config(self) -> dict:
    return {
        "default_prompt": self.default_prompt,
        "use_structured_outputs": self.use_structured_outputs,
        "random_seed_policy": str(self.random_seed) if self.random_seed else "none",
    }
```

### 7.2 Full Configuration Dictionary

**Purpose**: Complete serialization including all fields.

```python
def get_config_dict(self) -> dict:
    return {
        # Protocol (used in config hash)
        "default_prompt": self.default_prompt,
        "use_structured_outputs": self.use_structured_outputs,
        "random_seed_policy": str(self.random_seed) if self.random_seed else "none",
        # Metadata (informational, do NOT affect hash)
        "questionnaire_path": str(self.questionnaire_path),
        "openrouter_base_url": self.openrouter_base_url,
        "default_iterations": self.default_iterations,
        # Model Variants (do NOT affect hash, can vary per run)
        "model_max_tokens": self.model_max_tokens,
        "model_temperature": self.model_temperature,
        "model_top_p": self.model_top_p,
        "model_top_k": self.model_top_k,
        "model_repeat_penalty": self.model_repeat_penalty,
        "reasoning_effort": self.reasoning_effort,
        "reasoning_max_tokens": self.reasoning_max_tokens,
        "reasoning_exclude": self.reasoning_exclude,
        "reasoning_enabled": self.reasoning_enabled,
        "enable_vision": self.enable_vision,
        "openrouter_debug_enabled": self.openrouter_debug_enabled,
        # Additional context
        "execution_mode": self.execution_mode.value,
        "experiment_name": self.experiment_name,
        "system_prompt": self.system_prompt,
        "user_prompt_template": self.user_prompt_template,
        "random_seed": self.random_seed,
    }
```

### 7.3 Generation Parameters

**Purpose**: Get current generation parameter values with source names.

```python
def get_generation_params(self) -> dict[str, tuple[str, any]]:
    return {
        "temperature": ("model_temperature", self.model_temperature),
        "max_tokens": ("model_max_tokens", self.model_max_tokens),
        "top_p": ("model_top_p", self.model_top_p),
        "top_k": ("model_top_k", self.model_top_k),
        "repeat_penalty": ("model_repeat_penalty", self.model_repeat_penalty),
    }
```

---

## 8. Environment Variable Mapping

### 8.1 Special Mappings

**Prompt Templates**:
```python
# In __init__
if 'system_prompt' not in kwargs:
    system_prompt_template = os.getenv("SYSTEM_PROMPT_TEMPLATE")
    if system_prompt_template is not None:
        kwargs['system_prompt'] = system_prompt_template

if 'user_prompt_template' not in kwargs:
    user_prompt_template = os.getenv("USER_PROMPT_TEMPLATE")
    if user_prompt_template is not None:
        kwargs['user_prompt_template'] = user_prompt_template
```

### 8.2 .env Loading

**Implementation**:
```python
from dotenv import load_dotenv

# Load .env file for non-sensitive configuration
# NOTE: OPENROUTER_API_KEY should NOT be in .env - use system environment variable
load_dotenv(".env")
```

**Settings Config**:
```python
model_config = SettingsConfigDict(
    env_file=None,  # .env already loaded manually
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)
```

---

## 9. Key Design Decisions

### 9.1 Security: API Key from System Env Only

**Decision**: `OPENROUTER_API_KEY` must come from system environment variable, not `.env` file.

**Rationale**:
- `.env` files are often committed to version control
- System environment variables are more secure
- Prevents accidental API key exposure

**Implementation**:
```python
@model_validator(mode="after")
def validate_api_key_from_env(self) -> "Settings":
    env_api_key = os.getenv("OPENROUTER_API_KEY")
    if env_api_key:
        object.__setattr__(self, "openrouter_api_key", env_api_key)
    return self
```

### 9.2 Execution Modes

**Decision**: Three distinct execution modes (test, dev, experiment).

**Rationale**:
- Test mode: No persistence, fast iteration
- Dev mode: Persistence, flexible configuration
- Experiment mode: Frozen configuration, reproducibility

### 9.3 Protocol Hash

**Decision**: Hash only protocol-defining fields, not model variants.

**Rationale**:
- Allows comparing different model variants within same experiment
- Protocol defines the experiment "rules"
- Model parameters are variants, not protocol

### 9.4 Pydantic Settings

**Decision**: Use Pydantic Settings for configuration management.

**Rationale**:
- Type safety
- Automatic validation
- Clear field definitions
- Serialization support

---

## 10. Summary

The V1 Configuration System was built around these foundational concepts:

1. **Pydantic Settings** — Type-safe, validated configuration

2. **Security First** — API keys from system environment only

3. **Three-Tier Hierarchy** — CLI > .env > defaults

4. **Execution Modes** — Test, dev, experiment with different behaviors

5. **Protocol Hash** — Hash only protocol-defining fields

6. **Validation** — Extensive field and model validators

7. **Serialization** — Methods for dictionary and hash generation

8. **Immutability in Experiment Mode** — Frozen configuration for reproducibility

This document captures the architectural essence of V1 without proposing improvements or comparing to V2 implementations.

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Source**: `src_legacy/utils/config.py`
