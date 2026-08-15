# Investigation Report: `--add-model` Command Entry Points

**Date:** 2026-03-26  
**Status:** Investigation Complete  
**Scope:** `src/` codebase only  

---

## Executive Summary

This investigation identified **FOUR distinct entry points** for the `--add-model` command in the codebase. Two parallel, functional paths coexist with different behaviors, configuration resolution strategies, and validation logic.

**Key Finding:** The codebase has divergent implementation paths that can produce inconsistent results for the same user inputs.

---

## 1. Entry Point Inventory

| # | Entry Point | File(s) | CLI Invocation | Accessibility |
|---|-------------|---------|----------------|---------------|
| **EP1** | Legacy CLI Parser | `src/cli/cli.py` + `src/main.py` | `bcllm.py --experiment <name> --add-model <model>` | User-accessible |
| **EP2** | Dedicated Model Module | `src/cli/bcllm_model.py` | `python -m src.cli.bcllm_model --experiment <name> --add-model <model_id>` | User-accessible |
| **EP3** | Experiment Module (creation-time) | `src/cli/bcllm_experiment.py` | `python -m src.cli.bcllm_experiment --create-experiment <name> --add-model <model_id>` | User-accessible |
| **EP4** | ExperimentManager Class | `src/cli/experiment_commands.py` | Internal method call | Internal-only |

---

## 2. Detailed Entry Point Analysis

### EP1: Legacy CLI Parser

**Files:** `src/cli/cli.py` + `src/main.py`

**CLI Invocation:**
```bash
bcllm.py --experiment my_exp --add-model openai/gpt-4 --add-model anthropic/claude-3
```

**Flag Definition** (`cli.py` line 119):
```python
parser.add_argument(
    "--add-model",
    action="append",
    dest="add_models",
    metavar="MODEL",
    help="Add a model to the experiment. Can be specified multiple times. Use with --experiment.",
)
```

**Execution Flow:**
1. `bcllm.py` routes to `src/main.py` via `_handle_experiment_context()` (line 487)
2. Routes to `_handle_add_models_to_experiment()` (line 503)
3. Calls `ExperimentManager.add_models_to_experiment()` (line 621+)

**Configuration Resolution:**
- Uses `ExperimentManager._create_model_variant()` (line 789 in `experiment_commands.py`)
- Uses `VariantConfig.build_signature()` from `src/core/variant_config.py`
- **Does NOT use `ConfigResolver.build_model_config_dict()`**
- **Does NOT generate `variant_signature` via `generate_variant_signature()`**
- Uses internal signature generation via `VariantConfig` class
- **Does NOT read from `.env`**

**Validation:**
- ❌ No model ID format validation
- ❌ No boolean value validation
- ⚠️ Duplicate check via `variant_repo.get_by_id(variant_id)` (not signature-based)

**Flags Supported (3 total):**
- `--reasoning-effort`
- `--enable-vision`
- `--enable-structured`

**Error Messages:**
- Uses Rich console for formatted errors
- Generic error messages without valid value lists

---

### EP2: Dedicated Model Module (Authoritative)

**File:** `src/cli/bcllm_model.py`

**CLI Invocation:**
```bash
python -m src.cli.bcllm_model --experiment my_exp --add-model google/gemini-3.1-flash-lite-preview
```

**Flag Definition** (`bcllm_model.py` line 51):
```python
group.add_argument(
    "--add-model",
    metavar="MODEL_ID",
    help="Add model variant (format: provider/model-name)",
)
```

**Execution Flow:**
1. `bcllm.py` routes to `bcllm_model.main()` (line 29-30)
2. Calls `handle_add_model(args, conn)` directly (line 149)
3. Uses `ConfigResolver.build_model_config_dict()` (line 177)
4. Generates signature via `generate_variant_signature()` (line 179)

**Configuration Resolution:**
- Uses `ConfigResolver.build_model_config_dict(args, experiment)`
- Resolution order: **CLI > .env > experiment > NULL**
- All 10 model-level keys from contract are resolved

**Variant Signature Generation:**
- Uses `generate_variant_signature(model_id, config)` from `src/utils/variant_signature.py`
- Signature format: `model_name|key1=value1|key2=value2...`
- Float normalization: 3 decimal places
- Fixed field order (8 config fields)

**Validation:**
- ✅ Model ID format validation via `validate_model_id()`
- ✅ Boolean value validation for `--vision` and `--structured`
- ✅ Duplicate detection via `var_repo.get_by_signature(experiment_id, signature)`

**Flags Supported (14 total):**
- `--url`
- `--max-reasoning`
- `--max-tokens`
- `--reasoning`
- `--repeat-penalty`
- `--temperature`
- `--top-k`
- `--top-p`
- `--reasoning-tokens`
- `--vision`
- `--structured`

**Error Messages:**
- Explicit format errors with valid value lists
- Signature collision warnings

---

### EP3: Experiment Module at Creation

**File:** `src/cli/bcllm_experiment.py`

**CLI Invocation:**
```bash
python -m src.cli.bcllm_experiment --create-experiment my_exp --add-model openai/gpt-4
```

**Flag Definition** (`bcllm_experiment.py` line 195):
```python
parser.add_argument(
    "--add-model",
    action="append",
    metavar="MODEL_ID",
    dest="add_models",
    help="Add model variant at creation time (can be used multiple times)",
)
```

**Execution Flow:**
1. `bcllm.py` routes to `bcllm_experiment.main()` (line 27-28)
2. Calls `handle_create_experiment(args, conn)` (line 293)
3. Calls `_add_models_at_creation(models, experiment, conn, resolver)` (line 359)

**Configuration Resolution:**
- Uses `ConfigResolver.build_model_config_dict()` (line 373)
- Resolution order: **CLI > .env > NULL**
- Same 10 model-level keys as EP2

**Variant Signature Generation:**
- Uses `generate_variant_signature(model_id, config)` (line 375)
- Identical to EP2

**Validation:**
- ✅ Model ID format validation via `validate_model_id()`
- ✅ Boolean validation for `--vision` and `--structured`
- ✅ Duplicate detection via `var_repo.get_by_signature()`

**Flags Supported:**
- Same as EP2 (14 model configuration flags)
- Only available at experiment creation time

---

### EP4: ExperimentManager Class

**File:** `src/cli/experiment_commands.py`

**CLI Invocation:**
Not directly accessible. Called internally from `src/main.py::_handle_add_models_to_experiment()`.

**Method Signature** (line 464):
```python
def add_models_to_experiment(
    self,
    experiment_name: str,
    models: list[str],
    reasoning_mode: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    vision_enabled: bool = False,
    structured_enabled: bool = False,
) -> None:
```

**Execution Flow:**
1. Called from `src/main.py::_handle_add_models_to_experiment()` (line 651)
2. Calls `_create_model_variant()` for each model (line 514)

**Configuration Resolution:**
- Uses `VariantConfig` class from `src/core/variant_config.py`
- **Does NOT use `ConfigResolver`**
- **Does NOT read from `.env`**
- Hardcoded parameters passed to method

**Variant Signature Generation:**
- Uses `VariantConfig.build_signature(model_id)` (line 826)
- Signature format differs from EP2/EP3

**Validation:**
- ❌ No model ID format validation
- ❌ No boolean value validation
- ⚠️ Duplicate check via `variant_repo.get_by_id(variant_id)` (not signature-based)

**Flags Supported:**
- `reasoning_mode`, `reasoning_effort`, `reasoning_max_tokens`, `vision_enabled`, `structured_enabled`
- Does NOT support: `temperature`, `max_tokens`, `top_p`, `top_k`, `repeat_penalty`, `reasoning_tokens`, `url`

---

## 3. Behavioral Comparison (Side-by-Side)

| Aspect | EP1 (Legacy) | EP2 (Model) | EP3 (Creation) | EP4 (Manager) |
|--------|--------------|-------------|----------------|---------------|
| **Config Resolution** | `VariantConfig` (no .env) | `ConfigResolver` (CLI > .env > exp > NULL) | `ConfigResolver` (CLI > .env > NULL) | `VariantConfig` (no .env) |
| **Signature Generation** | `VariantConfig.build_signature()` | `generate_variant_signature()` | `generate_variant_signature()` | `VariantConfig.build_signature()` |
| **Duplicate Detection** | `get_by_id(variant_id)` | `get_by_signature(exp_id, sig)` | `get_by_signature(exp_id, sig)` | `get_by_id(variant_id)` |
| **Model ID Validation** | ❌ None | ✅ `validate_model_id()` | ✅ `validate_model_id()` | ❌ None |
| **Boolean Validation** | ❌ None | ✅ `_validate_bool_value()` | ✅ `_validate_bool_value()` | ❌ None |
| **Flags Supported** | 3 | 14 | 14 | 5 |
| **.env Support** | ❌ No | ✅ Yes | ✅ Yes | ❌ No |
| **Error Messages** | Rich console, generic | Explicit with valid values | Explicit with valid values | Rich console, generic |

---

## 4. Authoritative Path Determination

### Evidence from Documentation

**QWEN.md** (Project Architecture Document):
- States: "All executions are intentional, identifiable, and reproducible"
- Model Variants section: "Variants are created explicitly, are never inferred, are never modified after creation"
- Does NOT specify which CLI path is authoritative

**to-be-architecture.md** (lines 141-180):
- Documents `bcllm_model.py` as the dedicated module for model variant management
- Shows `--add-model` command with full parameter list
- States purpose: "Model variant management within experiments"

**CLI Routing Logic** (`bcllm.py` lines 73-74):
```python
if "--add-model" in args or "--list-models" in args or "--remove-model" in args:
    return "bcllm_model"
```
- Routes `--add-model` to `bcllm_model` module by default
- This suggests `bcllm_model.py` is the **intended primary path**

### Evidence from Code Comments

**`bcllm_model.py`** (lines 1-17):
```python
"""Model variant management CLI.

This module provides CLI commands for managing model variants within experiments:
- Add model variants to experiments
- List model variants in an experiment
- Remove model variants (soft delete)

Usage:
    bcllm_model.py --experiment <name> --add-model <model_id>
```
- Comprehensive documentation
- Explicit usage examples

### Conclusion: Authoritative Path

**EP2 (`bcllm_model.py`) is the intended authoritative path** based on:

1. **Routing priority** in `bcllm.py` (line 73-74)
2. **Complete feature set** (14 flags vs 3-5 in other paths)
3. **Configuration resolution** (uses `ConfigResolver` with full CLI > .env > exp > NULL chain)
4. **Validation completeness** (model ID format, boolean values, signature collision)
5. **Documentation alignment** (to-be-architecture.md documents `bcllm_model.py` as primary)
6. **Error message quality** (explicit, actionable errors)

---

## 5. Risks of Keeping Both Paths Active

### Risk 1: Inconsistent Variant Signatures

**Scenario:** Same inputs produce different signatures

| Path | Signature Method | Example Output |
|------|------------------|----------------|
| EP1/EP4 | `VariantConfig.build_signature()` | `gemini-3.1-flash-lite-preview|reasoning=low|vision=true` |
| EP2/EP3 | `generate_variant_signature()` | `gemini-3.1-flash-lite-preview|reasoning=low|vision=true|temp=0.800` |

**Impact:** Users can create "duplicate" variants that are actually different due to signature format differences.

### Risk 2: Configuration Divergence

**Scenario:** Same CLI flags produce different configurations

```bash
# Via EP1 (legacy)
bcllm.py --experiment my_exp --add-model openai/gpt-4 --temperature 0.8
# → temperature IGNORED (not supported)

# Via EP2 (model module)
python -m src.cli.bcllm_model --experiment my_exp --add-model openai/gpt-4 --temperature 0.8
# → temperature APPLIED (resolved from CLI)
```

**Impact:** Users get different model behavior depending on which entry point they use.

### Risk 3: .env Inconsistency

**Scenario:** .env configuration applied inconsistently

```bash
# .env contains: MODEL_TEMPERATURE=0.5

# Via EP1/EP4
# → .env IGNORED, uses hardcoded defaults

# Via EP2/EP3
# → .env APPLIED (CLI > .env > exp > NULL)
```

**Impact:** Configuration that "should" be global (.env) only applies to some entry points.

### Risk 4: Validation Gaps

| Validation | EP1 | EP2 | EP3 | EP4 |
|------------|-----|-----|-----|-----|
| Model ID format | ❌ | ✅ | ✅ | ❌ |
| Boolean values | ❌ | ✅ | ✅ | ❌ |
| Signature collision | ❌ (uses variant_id) | ✅ | ✅ | ❌ (uses variant_id) |

**Impact:** Invalid configurations can be created via EP1/EP4 that would be rejected by EP2/EP3.

### Risk 5: Duplicate Variants

**Scenario:** Same model can be added twice via different paths

```bash
# Step 1: Add via EP1
bcllm.py --experiment my_exp --add-model openai/gpt-4

# Step 2: Add via EP2
python -m src.cli.bcllm_model --experiment my_exp --add-model openai/gpt-4
# → May succeed if signature generation differs
```

**Impact:** Database contains duplicate variants with different IDs but same effective configuration.

### Risk 6: User Confusion

**Evidence from `cli.py` docstring** (lines 55-62):
```python
Examples:
  # Add models to experiment
  %(prog)s --experiment my_exp --add-model openai/gpt-4 --add-model anthropic/claude-3
```

**Evidence from `bcllm_model.py` docstring** (lines 10-11):
```python
Usage:
    bcllm_model.py --experiment <name> --add-model <model_id>
```

**Impact:** Documentation shows conflicting usage patterns. Users don't know which is correct.

---

## 6. Additional Findings

### Finding 1: Legacy Path Still Actively Used

**Evidence:**
- `cli.py` epilog (lines 55-100) contains extensive examples using `--add-model`
- `main.py` `_handle_add_models_to_experiment()` is fully implemented and called
- Integration tests (`tests/test_cli_integration.py`) test the legacy path extensively

**Conclusion:** Legacy path is **actively maintained**, not deprecated.

### Finding 2: Signature Generation Divergence

**`VariantConfig.build_signature()`** (used by EP1/EP4):
- Located in `src/core/variant_config.py`
- Signature format: `model_name|reasoning=low|vision=true...`
- Field set determined by `VariantConfig` class attributes

**`generate_variant_signature()`** (used by EP2/EP3):
- Located in `src/utils/variant_signature.py`
- Signature format: `model_name|reasoning=low|vision=true|temp=0.800...`
- Fixed 8-field order from `SIGNATURE_FIELD_ORDER` list
- Float normalization: 3 decimal places

**Impact:** Same configuration produces different signatures depending on path.

### Finding 3: Database Schema Mismatch

**`ModelVariant` model** (`src/db/models.py` lines 44-58):
```python
@dataclass
class ModelVariant:
    variant_id: str
    experiment_id: str
    model_id: str
    variant_signature: str
    config: str = "{}"
    created_at: str | None = None
```

**EP1/EP4** creates variants with:
- `variant_id` from `VariantConfig.build_variant_id()`
- `variant_signature` from `VariantConfig.build_signature()`
- `config` NOT populated (uses default `"{}"`)

**EP2/EP3** creates variants with:
- `variant_id` from `uuid.uuid4()`
- `variant_signature` from `generate_variant_signature()`
- `config` populated with full 10-key configuration JSON

**Impact:** Variants created via different paths have different data completeness.

### Finding 4: Duplicate Flag Detection

**`bcllm_experiment.py`** uses custom `DuplicateFlagWarningParser` (lines 33-73):
- Warns on duplicate flags: `Warning: --add-model specified multiple times, using last value`
- Only active in `bcllm_experiment.py`

**`bcllm_model.py`** uses standard `argparse.ArgumentParser`:
- `action="append"` allows multiple `--add-model` flags
- No warning, intended behavior

**`cli.py`** uses standard `argparse.ArgumentParser`:
- `action="append"` for `--add-model`
- No warning, intended behavior

**Impact:** Different user experience for duplicate flag handling.

### Finding 5: Error Message Consistency

| Path | Error Format | Example |
|------|--------------|---------|
| EP1 | Rich console | `[red]Error: Experiment 'my_exp' not found[/red]` |
| EP2 | Plain stderr | `Error: Experiment not found: my_exp` |
| EP3 | Plain stderr | `Error: Experiment not found: my_exp` |
| EP4 | Rich console | `[red]Error: ...[/red]` |

**Impact:** Inconsistent user experience, different parsing difficulty for automated tools.

---

## 7. Summary Table

| Criterion | EP1 (Legacy) | EP2 (Model) | EP3 (Creation) | EP4 (Manager) |
|-----------|--------------|-------------|----------------|---------------|
| **Authoritative** | ❌ No | ✅ Yes | ⚠️ Creation-only | ❌ Internal |
| **Feature Complete** | ❌ 3 flags | ✅ 14 flags | ✅ 14 flags | ❌ 5 params |
| **Config Resolution** | ❌ Hardcoded | ✅ Full chain | ✅ Full chain | ❌ Hardcoded |
| **Validation** | ❌ Minimal | ✅ Complete | ✅ Complete | ❌ Minimal |
| **Signature Consistency** | ⚠️ VariantConfig | ✅ Standard | ✅ Standard | ⚠️ VariantConfig |
| **Error Quality** | ⚠️ Generic | ✅ Explicit | ✅ Explicit | ⚠️ Generic |
| **Actively Used** | ✅ Yes | ✅ Yes | ⚠️ Creation only | ✅ Yes |
| **Tested** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

---

## 8. Root Cause Analysis: Null Handling Inconsistency

### Current Behavior by Flag Type

| Flag Type | NULL Handling | Validation | Location |
|-----------|---------------|------------|----------|
| **Boolean** (`--vision`, `--structured`) | Accept `true`, `false`, `NULL` (case-insensitive) | ✅ Explicit validation in `handle_add_model()` | `bcllm_model.py` |
| **Numeric** (`--temperature`, `--top-p`, `--max-tokens`) | argparse `type=int/float` rejects non-numeric | ⚠️ argparse rejects at parse time | `bcllm_model.py` |
| **String** (`--reasoning`, `--url`) | No validation, accepts any string including `NULL` | ❌ No validation | `config_resolver.py` |

### Why Inconsistent?

The validation logic is split between three different paths:

1. **Argparse type converters** (numeric flags)
   - `type=int` or `type=float` in argparse
   - Rejects non-numeric values at parse time
   - Cannot accept `NULL` string

2. **Manual boolean validation** (only in `bcllm_model.py`)
   - `_validate_bool_value()` function
   - Explicit check in `handle_add_model()`
   - Accepts `NULL` string and converts to `None`

3. **No validation** (string flags)
   - `resolve_cli_or_env()` treats empty strings as "not provided"
   - Falls through to `.env` or `None`
   - Accepts any string including `NULL`, `null`, empty strings

### ConfigResolver Behavior

**Boolean Resolution** (`config_resolver.py` lines 528-547):
```python
def _resolve_bool_cli_or_env(self, cli_value: str | None, env_key: str) -> bool | None:
    if cli_value is not None:
        parsed = self._parse_bool_value(cli_value)
        if parsed is not None:
            return parsed
        if cli_value.upper() == 'NULL':
            return None
    return self._parse_bool_env(env_key)

def _parse_bool_value(self, value: str | None) -> bool | None:
    if value is None:
        return None
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    if value.upper() == 'NULL':
        return None
    return None  # ← Invalid values return None silently
```

**Issue:** `_parse_bool_value()` returns `None` for invalid values (line 517), meaning invalid boolean values silently become `None` instead of raising an error.

### Root Cause Summary

1. **Boolean flags** have explicit validation in `handle_add_model()` because they accept string values that must be parsed
2. **Numeric flags** use `type=int` or `type=float` in argparse, which rejects non-numeric values at parse time
3. **String flags** (`--reasoning`, `--url`) have **no validation** - they accept any string including `NULL`, `null`, empty strings
4. The `_parse_bool_value()` function returns `None` for invalid values, which means invalid boolean values silently become `None` instead of raising an error

---

## 9. Final Assessment

**The codebase has TWO parallel, functional `--add-model` paths:**

### Path A: Legacy Path (EP1 + EP4)
- **Entry:** `bcllm.py --experiment --add-model` → `main.py` → `ExperimentManager`
- **Characteristics:**
  - Simpler, fewer flags (3-5)
  - No .env support
  - Different signature generation (`VariantConfig.build_signature()`)
  - Less validation
  - Uses `variant_id` for deduplication instead of `variant_signature`

### Path B: Authoritative Path (EP2)
- **Entry:** `bcllm_model.py --experiment --add-model`
- **Characteristics:**
  - Full feature set (14 flags)
  - Complete configuration resolution (CLI > .env > exp > NULL)
  - Standard signature generation (`generate_variant_signature()`)
  - Comprehensive validation
  - Uses `variant_signature` for deduplication

### EP3: Special Case
- Creation-time only variant of EP2
- Same implementation, limited to experiment creation context

---

## 10. Recommendations

### Immediate Actions Required

1. **Consolidate signature generation**
   - Single source of truth: `generate_variant_signature()`
   - Include ALL model-affecting fields (currently missing `BASE_URL`, `MODEL_REPEAT_PENALTY`)
   - Normalize numeric formatting consistently

2. **Unify validation logic**
   - Single validation layer for all flag types
   - Consistent null handling across all flags
   - Case-insensitive text values

3. **Resolve entry point divergence**
   - Option A: Make EP1 delegate to EP2
   - Option B: Deprecate EP1 with warnings
   - Option C: Fix both paths identically (not recommended)

4. **Standardize error messages**
   - Consistent format across all entry points
   - Explicit valid value lists
   - Actionable error descriptions

### Long-Term Actions

1. **Deprecate legacy path** with migration guide
2. **Consolidate configuration resolution** to single `ConfigResolver` path
3. **Add duplicate flag detection** to all entry points
4. **Update documentation** to reflect authoritative path

---

## Appendix A: File Reference

| File | Purpose | Lines |
|------|---------|-------|
| `src/cli/bcllm_model.py` | Authoritative model variant CLI | 1-200 |
| `src/cli/cli.py` | Legacy CLI parser | 1-150 |
| `src/main.py` | Legacy entry point | 487-700 |
| `src/cli/experiment_commands.py` | ExperimentManager class | 464-900 |
| `src/cli/bcllm_experiment.py` | Experiment creation CLI | 293-400 |
| `src/core/config_resolver.py` | Configuration resolution | 416-566 |
| `src/core/variant_config.py` | VariantConfig class | 789-850 |
| `src/utils/variant_signature.py` | Signature generation | 20-90 |
| `src/db/models.py` | ModelVariant dataclass | 44-58 |

---

**END OF INVESTIGATION REPORT**
