# Configuration System — Gap Report

**Document Type:** Gap Analysis
**Domain:** Configuration System
**Comparison:** V1 (Legacy) → V2 (Current)
**Purpose:** Identify configuration differences, null semantics enhancements, and migration priorities

---

## 1. Feature Parity Matrix

| V1 Feature | V2 Status | Gap Severity | Notes |
|------------|-----------|--------------|-------|
| **Configuration hierarchy** | ✅ Enhanced | NONE | V2 adds EXPLICIT_NULL semantics |
| **Pydantic Settings** | ❌ Replaced | LOW | V2 uses ConfigResolver component |
| **Environment variable loading** | ✅ Implemented | NONE | Same approach (python-dotenv) |
| **Field validation** | ⚠️ Partial | LOW | V2 has manual validation |
| **Execution modes** | ⚠️ Partial | MEDIUM | V2 simplified mode handling |
| **Protocol hash** | ❌ Removed | LOW | V2 doesn't compute config hash |
| **Null semantics** | ✅ Enhanced | NONE | V2 adds EXPLICIT_NULL |
| **JSON storage** | ✅ Implemented | NONE | Same approach |
| **Seed AUTO resolution** | ✅ Enhanced | NONE | V2 clarifies timing |
| **Boolean parsing** | ✅ Implemented | NONE | Same behavior |

---

## 2. Architecture Differences

### 2.1 Configuration Management Approach

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **Component** | `Settings` class (Pydantic) | `ConfigResolver` class | **Changed** |
| **Validation** | Pydantic validators | Manual validation | **Changed** |
| **Type Safety** | Automatic (Pydantic) | Manual | **Changed** |
| **Serialization** | Built-in (Pydantic) | Manual JSON | **Changed** |

**Assessment**: V2 moved from Pydantic Settings to a custom ConfigResolver component.

**Gap Severity**: **LOW** — Architectural change, not a regression.

**Trade-offs**:
- ✅ V2: More explicit control over resolution
- ✅ V1: Automatic type validation
- ❌ V2: Manual validation required
- ❌ V2: No automatic type coercion

---

### 2.2 Configuration Hierarchy

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **Resolution order** | CLI > .env > defaults | CLI > .env > defaults > NULL | **Enhanced** |
| **Null handling** | Falls back to next level | EXPLICIT_NULL bypasses .env | **Enhanced** |
| **Null-by-default** | No | Yes (for prompts) | **Enhanced** |

**Assessment**: V2 enhanced hierarchy with explicit null semantics.

**Gap Severity**: **NONE** — Enhancement, not a regression.

---

### 2.3 Null Semantics

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **EXPLICIT_NULL** | ❌ Not implemented | ✅ Implemented | **Added** |
| **CLI null parsing** | ❌ Not documented | ✅ Documented contract | **Added** |
| **Case-insensitive null** | ❌ Not implemented | ✅ Implemented | **Added** |
| **Mandatory field null rejection** | ❌ Not implemented | ✅ Documented | **Added** |

**Assessment**: V2 added comprehensive null semantics.

**Gap Severity**: **NONE** — Significant enhancement.

---

## 3. Configuration Timing Differences

### 3.1 Experiment Creation

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **When captured** | Experiment creation | Experiment creation | Same |
| **What's captured** | Protocol config + metadata | 14 keys (1 EXP + 10 MODEL + 3 RUN) | **Changed** |
| **Hash calculation** | ✅ Yes (protocol only) | ❌ No | **Removed** |

**Assessment**: V2 captures more configuration at experiment creation but removed hash calculation.

**Gap Severity**: **LOW** — Hash removal is intentional simplification.

---

### 3.2 Model Variant Creation

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **When captured** | Variant creation | Variant creation | Same |
| **Identity fields** | reasoning_mode, vision, structured, etc. | All 10 model keys | **Changed** |
| **Storage** | Separate columns + config | config JSON only | **Changed** |

**Assessment**: V2 simplified variant storage to JSON only.

**Gap Severity**: **LOW** — Intentional simplification.

---

### 3.3 Run Creation

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **When captured** | Run creation | Run creation | Same |
| **Seed AUTO resolution** | ⚠️ Unclear timing | ✅ Explicit (at run creation) | **Clarified** |
| **Prompt inheritance** | From experiment | From experiment | Same |

**Assessment**: V2 clarified AUTO seed resolution timing.

**Gap Severity**: **NONE** — Clarification, not a regression.

---

## 4. Missing Features in V2

### 4.1 Pydantic Validation (LOW)

**V1 Behavior**:
- Automatic type validation via Pydantic
- Field validators with `@field_validator`
- Model validators with `@model_validator`
- Automatic type coercion

**V2 Status**:
- ❌ No Pydantic integration
- ❌ Manual validation in resolver methods
- ❌ No automatic type coercion

**Impact**:
- More boilerplate code
- Risk of validation inconsistencies
- No automatic type safety

**Migration Priority**: **LOW**

**Recommended Approach**:
- Keep manual validation (more explicit)
- Add validation helper methods
- Document validation rules clearly

---

### 4.2 Protocol Hash (LOW)

**V1 Behavior**:
- `get_config_hash()` method
- Hash of protocol-defining fields only
- Used for experiment deduplication

**V2 Status**:
- ❌ No hash calculation
- ❌ No deduplication check

**Impact**:
- Cannot detect duplicate experiments
- No integrity check for protocol

**Migration Priority**: **LOW**

**Recommended Approach**:
- Optional: Re-add hash calculation if deduplication is needed
- Consider hash for audit purposes only

---

### 4.3 Execution Mode Handling (MEDIUM)

**V1 Behavior**:
- `ExecutionMode` enum (test, dev, experiment)
- Mode-aware properties (`is_experiment_mode`, `is_config_frozen`)
- Debug mode blocked in experiment mode

**V2 Status**:
- ⚠️ Mode handling not in ConfigResolver
- ❌ No mode enum in core module
- ❌ No mode-aware validation

**Impact**:
- Mode validation scattered in CLI layer
- No centralized mode handling

**Migration Priority**: **MEDIUM**

**Recommended Approach**:
- Consider adding mode handling to ConfigResolver
- Or document that mode is CLI-layer concern

---

### 4.4 Computed Properties (LOW)

**V1 Behavior**:
- `is_api_configured` property
- `should_persist_data` property
- `is_config_frozen` property
- `get_generation_params()` method

**V2 Status**:
- ❌ No computed properties in ConfigResolver
- ❌ Properties are CLI-layer concern

**Impact**:
- More code in CLI layer
- Less centralized logic

**Migration Priority**: **LOW**

**Note**: This is an architectural choice, not a gap.

---

## 5. Improved Features in V2

### 5.1 EXPLICIT_NULL Semantics

**V1 Behavior**:
- No explicit null concept
- Missing values always fall back to next level

**V2 Enhancement**:
- ✅ `EXPLICIT_NULL` sentinel value
- ✅ CLI `null` bypasses .env
- ✅ Case-insensitive parsing
- ✅ Documented in contract

**Benefit**:
- Explicit intent over implicit behavior
- Allows bypassing .env defaults
- Consistent with "no inference" principle

---

### 5.2 Null-by-Default for Prompts

**V1 Behavior**:
- Prompts could have string defaults
- Empty strings treated as "not provided"

**V2 Enhancement**:
- ✅ Prompts default to NULL
- ✅ No implicit fallback strings
- ✅ Explicit configuration required

**Benefit**:
- Auditable (can see what was actually configured)
- No hidden defaults
- Consistent with null semantics

---

### 5.3 AUTO Seed Timing Clarification

**V1 Behavior**:
- Unclear when AUTO is resolved
- Seed resolution mixed with experiment config

**V2 Enhancement**:
- ✅ Explicit: AUTO resolved at RUN_CREATION only
- ✅ Experiment level stores "AUTO" string
- ✅ Run level generates deterministic integer

**Benefit**:
- Clear separation of concerns
- Each run gets unique deterministic seed
- Auditable seed generation

---

### 5.4 Configuration Key Organization

**V1 Behavior**:
- All settings in single Settings class
- No clear separation by scope

**V2 Enhancement**:
- ✅ Clear key categorization (SYSTEM, EXPERIMENT, MODEL, RUN)
- ✅ Documented resolution timing per category
- ✅ Contract-based key inventory

**Benefit**:
- Clear ownership boundaries
- Easier to understand what's captured when
- Better documentation

---

## 6. Configuration Key Inventory Comparison

### 6.1 Key Count

| Category | V1 | V2 | Change |
|----------|----|----|--------|
| **SYSTEM** | ~5 | 5 | Same |
| **EXPERIMENT** | ~4 (including transient) | 1 (+ 4 transient) | **Simplified** |
| **MODEL** | ~14 | 10 | **Consolidated** |
| **RUN** | 3 | 3 | Same |
| **TOTAL** | ~26 | ~23 | -3 |

### 6.2 Key Naming Changes

| V1 Key | V2 Key | Change |
|--------|--------|--------|
| `openrouter_base_url` | `BASE_URL` | **Renamed** (uppercase, shortened) |
| `model_max_tokens` | `MODEL_MAX_TOKENS_TOTAL` | **Renamed** (more explicit) |
| `model_temperature` | `MODEL_TEMPERATURE` | Same naming |
| `random_seed` | `RUN_RESPONSES_SEED` | **Renamed** (scope clarified) |
| `system_prompt` | `SYSTEM_PROMPT` | Same naming |
| `user_prompt_template` | `USER_PROMPT` | **Renamed** (simplified) |

**Assessment**: V2 uses consistent uppercase naming with clear scope prefixes.

---

## 7. Validation Differences

### 7.1 Field Validation

| Field Type | V1 | V2 | Change |
|------------|----|----|--------|
| **Log level** | ✅ Pydantic validator | ❌ Not in ConfigResolver | **Moved** |
| **Random seed** | ✅ Pydantic validator | ✅ Manual in resolver | **Changed** |
| **Execution mode** | ✅ Pydantic validator | ❌ Not in ConfigResolver | **Moved** |
| **Reasoning effort** | ✅ Pydantic validator | ✅ Manual in resolver | **Changed** |
| **Boolean fields** | ✅ Pydantic validator | ✅ Manual in resolver | **Changed** |

**Assessment**: V2 moved validation from Pydantic to manual resolver methods.

**Gap Severity**: **LOW** — Architectural choice.

---

### 7.2 Error Handling

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **Invalid values** | Pydantic ValidationError | Manual ValueError | **Changed** |
| **Missing required** | Pydantic error | Manual error | **Changed** |
| **Error messages** | Automatic from Pydantic | Custom messages | **Changed** |

**Assessment**: V2 has more control over error messages but more boilerplate.

---

## 8. Environment Variable Handling

### 8.1 .env Loading

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **Loading mechanism** | `load_dotenv(".env")` | `load_dotenv(env_path, override=True)` | **Enhanced** |
| **Caching** | Global `_settings` instance | `env_dict` in resolver | **Changed** |
| **Override behavior** | Default | `override=True` | **Enhanced** |

**Assessment**: V2 uses `override=True` for more predictable behavior.

---

### 8.2 API Key Security

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **API key source** | System env only | Not in ConfigResolver | **Moved** |
| **Validation** | Pydantic validator | CLI-layer concern | **Moved** |

**Assessment**: API key handling moved out of ConfigResolver.

**Note**: This is intentional — ConfigResolver handles configuration, not secrets.

---

## 9. Migration Priority

### 9.1 HIGH Priority (BLOCKERS)

None identified. V2 configuration system is functionally complete.

---

### 9.2 MEDIUM Priority (IMPROVEMENTS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Execution mode handling** | Medium | Low | Consider adding mode enum/handling |

**Rationale**: Centralized mode handling improves consistency.

---

### 9.3 LOW Priority (OPTIONAL)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Pydantic validation** | High | Medium | Keep manual validation (more explicit) |
| **Protocol hash** | Low | Low | Optional: re-add for audit purposes |
| **Computed properties** | Low | Low | Optional: add helper methods |

**Rationale**: These are architectural choices, not regressions.

---

## 10. Summary

### 10.1 Gap Summary by Severity

| Severity | Count | Components |
|----------|-------|------------|
| **CRITICAL** | 0 | None |
| **HIGH** | 0 | None |
| **MEDIUM** | 1 | Execution mode handling |
| **LOW** | 4 | Pydantic validation, Protocol hash, Computed properties, API key handling |

### 10.2 Overall Assessment

**V2 Architecture**: ✅ **SOUND**
- Clear separation of concerns
- Explicit null semantics
- Well-documented contracts
- Consistent naming

**V2 Implementation**: ✅ **COMPLETE**
- ConfigResolver implemented
- All resolution methods working
- Null semantics implemented
- JSON storage working

**Migration Readiness**: ✅ **READY**
- No critical gaps
- Enhanced null semantics
- Clearer configuration timing

### 10.3 Key Improvements in V2

1. **EXPLICIT_NULL semantics** — Allows bypassing .env defaults

2. **Null-by-default** — Prompts and optional values default to NULL

3. **AUTO seed timing** — Explicit: resolved at RUN_CREATION only

4. **Key organization** — Clear categorization (SYSTEM, EXPERIMENT, MODEL, RUN)

5. **Contract-based** — Documented resolution rules

6. **JSON storage** — Flexible schema, easy serialization

### 10.4 Recommended Next Steps

1. **Optional**: Consider adding execution mode handling to ConfigResolver

2. **Optional**: Add validation helper methods for common patterns

3. **Optional**: Consider protocol hash for audit purposes

4. **Recommended**: Keep manual validation (more explicit than Pydantic)

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Comparison**: V1 (Legacy) → V2 (Current)
