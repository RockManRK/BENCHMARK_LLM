# Configuration Key Hierarchy

**Document Type:** Reference  
**Project:** Benchmark LLM V2  
**Version:** 1.0  
**Date:** 2026-04-03  

---

## Purpose

This document defines the **exact config keys** used throughout the V2 system to prevent key mismatch bugs.

**Rule:** Config keys MUST be consistent across the entire hierarchy. If there's a mismatch, the system will silently use wrong/default values.

---

## Config Key Flow

```
CLI (.env) → ConfigResolver.build_config_dict() → model_variants.config (JSON)
                                                    ↓
                                              Planner reads
                                                    ↓
                                          ModelConfig dataclass
```

---

## Authoritative Source: ConfigResolver

**File:** `src/core/config_resolver.py`  
**Method:** `build_model_config_dict()` (lines 373-417)

The ConfigResolver generates config dicts with these **EXACT keys**:

| Config Key | Type | CLI Flag | .env Key | Default |
|-----------|------|----------|----------|---------|
| `MODEL_REASONING_EFFORT` | str | `--reasoning` | `MODEL_REASONING_EFFORT` | None |
| `MODEL_MAX_TOKENS_TOTAL` | int | `--max-tokens` | `MODEL_MAX_TOKENS_TOTAL` | None |
| `MODEL_MAX_TOKENS_REASONING` | int | `--reasoning-tokens` | `MODEL_MAX_TOKENS_REASONING` | None |
| `MODEL_TEMPERATURE` | float | `--temperature` | `MODEL_TEMPERATURE` | None |
| `MODEL_TOP_P` | float | `--top-p` | `MODEL_TOP_P` | None |
| `MODEL_TOP_K` | int | `--top-k` | `MODEL_TOP_K` | None |
| `MODEL_REPEAT_PENALTY` | float | `--repeat-penalty` | `MODEL_REPEAT_PENALTY` | None |
| `MODEL_VISION` | bool | `--vision` | `MODEL_VISION` | False |
| `STRUCTURED_OUTPUTS` | bool | `--structured` | `STRUCTURED_OUTPUTS` | False |

---

## Storage: model_variants.config Column

**Table:** `model_variants`  
**Column:** `config` (TEXT - JSON string)

The config dict from ConfigResolver is **directly serialized** to JSON:

```json
{
  "MODEL_VISION": true,
  "MODEL_TEMPERATURE": 0.7,
  "MODEL_MAX_TOKENS_TOTAL": 4096,
  "STRUCTURED_OUTPUTS": false
}
```

**Example:** If user runs:
```bash
bcllm --experiment test --add-model google/gemini-pro --vision true
```

The `model_variants.config` column will contain:
```json
{"MODEL_VISION": true, "MODEL_REASONING_EFFORT": null, ...}
```

---

## Reading: Planner._build_model_config()

**File:** `src/core/planner.py`  
**Method:** `_build_model_config()` (lines 499-532)

The Planner MUST read config using the **SAME keys** that ConfigResolver writes:

```python
config = json.loads(variant_row["config"])

return ModelConfig(
    temperature=config.get("MODEL_TEMPERATURE"),           # ✅ Correct
    top_p=config.get("MODEL_TOP_P"),                       # ✅ Correct
    max_output_tokens=config.get("MODEL_MAX_TOKENS_TOTAL"), # ✅ Correct
    enable_vision=config.get("MODEL_VISION", False),       # ✅ Correct
    structured_output=config.get("STRUCTURED_OUTPUTS", False), # ✅ Correct
    reasoning_mode="effort" if config.get("MODEL_REASONING_EFFORT") and config["MODEL_REASONING_EFFORT"] != "none" else "off",
    reasoning_effort=config.get("MODEL_REASONING_EFFORT") if config.get("MODEL_REASONING_EFFORT") and config["MODEL_REASONING_EFFORT"] != "none" else None,
)
```

### Historical Bug (FIXED)

**Before (WRONG):**
```python
enable_vision=config.get("vision", False)  # ❌ Key doesn't exist in stored config
```

**After (CORRECT):**
```python
enable_vision=config.get("MODEL_VISION", False)  # ✅ Matches ConfigResolver key
```

---

## Internal Representation: ModelConfig Dataclass

**File:** `src/core/execution_plan.py`  
**Class:** `ModelConfig` (lines 183-217)

The ModelConfig dataclass uses **short field names** (internal representation):

```python
@dataclass(frozen=True)
class ModelConfig:
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    enable_vision: bool = False              # ← Short name
    structured_output: bool = False          # ← Short name
    reasoning_mode: str = 'off'
    reasoning_effort: str | None = None
```

**Mapping:** Config key → ModelConfig field:
| Config Key | ModelConfig Field |
|-----------|-------------------|
| `MODEL_TEMPERATURE` | `temperature` |
| `MODEL_TOP_P` | `top_p` |
| `MODEL_MAX_TOKENS_TOTAL` | `max_output_tokens` |
| `MODEL_VISION` | `enable_vision` |
| `STRUCTURED_OUTPUTS` | `structured_output` |
| `MODEL_REASONING_EFFORT` | `reasoning_mode` + `reasoning_effort` |

---

## Usage: ExecutionEngine

**File:** `src/core/execution_engine.py`  
**Method:** `_build_user_message_for_item()` (line 905)

The ExecutionEngine uses the **ModelConfig field names** (not config keys):

```python
model_config = variant.model_config_effective

if model_config.enable_vision:  # ✅ Uses ModelConfig field name
    # Build multimodal message
    ...
```

---

## Signature Generation (Separate Concern)

**File:** `src/utils/variant_signature.py`  
**Constant:** `SIGNATURE_FIELD_ORDER` (lines 25-34)

The variant signature uses a **different mapping** for compact, deterministic signatures:

```python
SIGNATURE_FIELD_ORDER = [
    ('MODEL_REASONING_EFFORT', 'reasoning'),    # Config key → Signature key
    ('MODEL_VISION', 'vision'),                  # Config key → Signature key
    ('STRUCTURED_OUTPUTS', 'structured'),        # Config key → Signature key
    ('MODEL_TEMPERATURE', 'temp'),               # Config key → Signature key
    ('MODEL_TOP_P', 'top_p'),                    # Config key → Signature key
    ('MODEL_TOP_K', 'top_k'),                    # Config key → Signature key
    ('MODEL_MAX_TOKENS_TOTAL', 'max_tokens'),    # Config key → Signature key
    ('MODEL_MAX_TOKENS_REASONING', 'reasoning_tokens'),
]
```

**Example signature:**
```
gemini-pro|vision=true|temp=0.700
```

**Important:** Signature keys (`vision`, `temp`, etc.) are ONLY used for human-readable signatures. They are NOT used in config storage or execution.

---

## API Payload Keys (Different from Config Keys)

When sending requests to OpenRouter, the API uses **completely different keys**:

```python
payload = {
    "model": "google/gemini-pro",
    "messages": [...],
    "temperature": 0.7,        # API key (not MODEL_TEMPERATURE)
    "top_p": 0.9,              # API key (not MODEL_TOP_P)
    "max_tokens": 4096,        # API key (not MODEL_MAX_TOKENS_TOTAL)
}
```

These are defined by the OpenRouter API spec and are NOT related to our internal config keys.

---

## Complete Key Mapping Table

| Layer | Vision Key | Temperature Key | Max Tokens Key |
|-------|-----------|-----------------|----------------|
| **ConfigResolver output** | `MODEL_VISION` | `MODEL_TEMPERATURE` | `MODEL_MAX_TOKENS_TOTAL` |
| **model_variants.config** | `MODEL_VISION` | `MODEL_TEMPERATURE` | `MODEL_MAX_TOKENS_TOTAL` |
| **Planner reads** | `MODEL_VISION` | `MODEL_TEMPERATURE` | `MODEL_MAX_TOKENS_TOTAL` |
| **ModelConfig field** | `enable_vision` | `temperature` | `max_output_tokens` |
| **ExecutionEngine uses** | `enable_vision` | `temperature` | `max_output_tokens` |
| **API payload** | (N/A - in message content) | `temperature` | `max_tokens` |
| **Variant signature** | `vision` | `temp` | `max_tokens` |

---

## Rules for Future Changes

1. **NEVER change config keys** without updating ALL layers
2. **ConfigResolver is the source of truth** for config key names
3. **Planner MUST read using ConfigResolver's key names**
4. **ModelConfig field names are internal** - can be different from config keys
5. **API keys are external** - defined by OpenRouter spec
6. **Signature keys are for display** - not used in execution

---

## Validation Checklist

When adding/modifying config keys:

- [ ] ConfigResolver generates the key
- [ ] Config key is stored in `model_variants.config` JSON
- [ ] Planner reads using the SAME key
- [ ] ModelConfig has corresponding field
- [ ] ExecutionEngine uses ModelConfig field
- [ ] Variant signature mapping is updated (if applicable)
- [ ] This document is updated

---

## Historical Bugs

### Bug: Vision Always False (2026-04-03)

**Symptom:** User sets `--vision true`, but ExecutionEngine logs `VISION_DISABLED`

**Root Cause:** Planner was reading `config.get("vision", False)` instead of `config.get("MODEL_VISION", False)`

**Fix:** Updated Planner to use correct config keys matching ConfigResolver output

**Impact:** All existing model variants created before this fix need to be re-created to have correct config keys

---

**End of Document**
