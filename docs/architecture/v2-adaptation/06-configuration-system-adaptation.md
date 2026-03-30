# Configuration System — V2 Adaptation

**Document Type:** Adaptation Plan
**Domain:** Configuration System
**Purpose:** Define the migration path from V2 Current State to Target Architecture

---

## 1. Current State Assessment

### 1.1 What's Implemented

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| **ConfigResolver** | ✅ Complete | `src/core/config_resolver.py` | All resolution methods implemented |
| **Null Semantics** | ✅ Complete | `src/core/null_semantics.py` | EXPLICIT_NULL implemented |
| **Resolution Contracts** | ✅ Documented | `docs/architecture/contracts/` | 2 contracts documented |
| **JSON Storage** | ✅ Complete | Database schema | All entities store config as JSON |
| **Capture Timing** | ✅ Complete | ConfigResolver methods | Correct timing for each entity |

### 1.2 What's Working Well

**Strengths**:
1. ✅ **Explicit Priority** — CLI > .env > defaults > NULL is implemented correctly
2. ✅ **EXPLICIT_NULL** — CLI `null` bypasses .env as designed
3. ✅ **Null-by-Default** — Prompts default to NULL
4. ✅ **AUTO Seed Timing** — Resolved at RUN_CREATION only
5. ✅ **JSON Storage** — Configs serialized as JSON with proper null handling
6. ✅ **Key Organization** — Clear categorization (SYSTEM, EXPERIMENT, MODEL, RUN)

### 1.3 What's Missing

**Gaps** (from Current → Target):

| Gap | Severity | Effort | Priority |
|-----|----------|--------|----------|
| **Execution mode handling** | MEDIUM | Medium | P2 |
| **Pydantic validation** | LOW | High | P3 (optional) |
| **Protocol hash** | LOW | Low | P3 (optional) |
| **Validation helper methods** | LOW | Low | P2 |
| **Error handling consistency** | MEDIUM | Low | P1 |

---

## 2. Target State (Architecture Specs)

### 2.1 Target Architecture Summary

**From**: `docs/architecture/to-be/06-configuration-system-architecture.md`

**Key Contracts**:
1. **Resolution Hierarchy** — CLI > .env > defaults > NULL
2. **Null Semantics** — EXPLICIT_NULL bypasses .env
3. **Capture Timing** — Frozen at entity creation
4. **Immutability** — No updates after creation
5. **Inheritance** — Child inherits from parent
6. **Key Inventory** — 23 keys (+ 4 transient)
7. **Type Validation** — Explicit rules per type
8. **Seed Resolution** — AUTO at RUN_CREATION only
9. **JSON Serialization** — Python None → JSON null
10. **Error Handling** — Clear, specific errors

### 2.2 Alignment Assessment

| Contract | Current State | Target | Gap |
|----------|---------------|--------|-----|
| Resolution Hierarchy | ✅ Implemented | ✅ Specified | NONE |
| Null Semantics | ✅ Implemented | ✅ Specified | NONE |
| Capture Timing | ✅ Implemented | ✅ Specified | NONE |
| Immutability | ✅ Enforced | ✅ Specified | NONE |
| Inheritance | ✅ Implemented | ✅ Specified | NONE |
| Key Inventory | ✅ 23 keys | ✅ 23 keys | NONE |
| Type Validation | ⚠️ Partial | ✅ Specified | LOW |
| Seed Resolution | ✅ Implemented | ✅ Specified | NONE |
| JSON Serialization | ✅ Implemented | ✅ Specified | NONE |
| Error Handling | ⚠️ Partial | ✅ Specified | MEDIUM |

**Overall Alignment**: **90%** — Core functionality complete, edge cases need work.

---

## 3. Gap Analysis

### 3.1 Functional Gaps

#### 3.1.1 Execution Mode Handling (MEDIUM)

**Current State**:
- Mode handling not in ConfigResolver
- Mode validation scattered in CLI layer
- No centralized mode enum

**Target State**:
- Centralized mode enum (test, dev, experiment)
- Mode-aware validation (e.g., debug blocked in experiment mode)
- Mode properties (is_config_frozen, should_persist_data)

**Gap**: Mode handling is decentralized.

**Impact**:
- Inconsistent mode validation
- Code duplication in CLI layer
- Harder to add mode-aware features

---

#### 3.1.2 Validation Helper Methods (LOW)

**Current State**:
- Manual validation in each resolver method
- Some duplication (e.g., `_parse_int_env`, `_parse_float_env`)
- No centralized validation utilities

**Target State**:
- Reusable validation helpers
- Consistent error messages
- Type-specific validation methods

**Gap**: Validation code is duplicated.

**Impact**:
- More code to maintain
- Risk of inconsistencies
- Harder to add new validation rules

---

#### 3.1.3 Error Handling Consistency (MEDIUM)

**Current State**:
- Mixed error handling (some return None, some raise)
- Inconsistent error messages
- No custom exception types

**Target State**:
- Custom exception types (ConfigurationError, MandatoryFieldError)
- Consistent error messages (field name, expected, actual)
- Clear error recovery strategy

**Gap**: Error handling is inconsistent.

**Impact**:
- Harder to debug configuration errors
- Inconsistent user experience
- Error handling scattered in callers

---

### 3.2 Documentation Gaps

#### 3.2.1 Configuration Key Documentation

**Current State**:
- Keys documented in contracts
- No centralized key inventory with examples

**Target State**:
- Complete key inventory with examples
- Resolution examples for each key
- Common configuration patterns

**Gap**: Examples and patterns not documented.

**Impact**:
- Harder for users to understand configuration
- More support questions

---

#### 3.2.2 Null Semantics Examples

**Current State**:
- Null semantics documented in contract
- Few practical examples

**Target State**:
- Comprehensive examples showing null behavior
- Common null use cases
- Anti-patterns to avoid

**Gap**: Practical examples missing.

**Impact**:
- Users may not understand EXPLICIT_NULL
- Misuse of null semantics

---

## 4. Implementation Considerations

### 4.1 Design Decisions

#### 4.1.1 Keep Manual Validation vs Pydantic

**Option A: Keep Manual Validation** (Recommended)
- ✅ More explicit control
- ✅ Better error messages
- ✅ No external dependency
- ❌ More boilerplate code

**Option B: Add Pydantic Validation**
- ✅ Automatic type coercion
- ✅ Less boilerplate
- ❌ Less control over resolution
- ❌ External dependency

**Recommendation**: **Keep Manual Validation**
- Aligns with "explicit > implicit" principle
- Better control over error messages
- ConfigResolver is already implemented and working

---

#### 4.1.2 Add Execution Mode Handling

**Option A: Add to ConfigResolver**
- ✅ Centralized mode handling
- ✅ Mode-aware validation
- ❌ Increases ConfigResolver scope

**Option B: Keep in CLI Layer**
- ✅ ConfigResolver stays focused
- ❌ Mode validation scattered
- ❌ Code duplication

**Recommendation**: **Hybrid Approach**
- Add mode enum and utilities to `src/core/mode.py`
- ConfigResolver uses mode utilities
- CLI layer handles mode selection

---

#### 4.1.3 Add Protocol Hash

**Option A: Add Hash Calculation**
- ✅ Experiment deduplication
- ✅ Integrity checking
- ❌ Additional complexity

**Option B: Skip Hash**
- ✅ Simpler implementation
- ❌ No deduplication
- ❌ No integrity check

**Recommendation**: **Skip for Now**
- Not critical for current use cases
- Can be added later if needed
- Focus on core functionality first

---

### 4.2 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Breaking changes** | Low | High | Backward-compatible changes only |
| **Performance regression** | Low | Medium | Profile before/after changes |
| **Validation inconsistencies** | Medium | Low | Add comprehensive tests |
| **Documentation drift** | Medium | Low | Update docs with code changes |

---

### 4.3 Testing Strategy

**Unit Tests**:
- Test each resolver method independently
- Test null semantics (EXPLICIT_NULL, case-insensitivity)
- Test type validation (int, float, bool, enum)
- Test seed resolution (fixed, AUTO, null)

**Integration Tests**:
- Test full configuration flow (CLI → .env → entity)
- Test inheritance (experiment → run/variant)
- Test immutability (config doesn't change after creation)

**Edge Cases**:
- Empty strings
- Whitespace-only strings
- Invalid types
- Mandatory fields with null
- AUTO seed resolution

---

## 5. Migration Path

### 5.1 Phase 1: Error Handling Consistency (P1)

**Goal**: Standardize error handling across ConfigResolver.

**Tasks**:
1. Create custom exception types:
   ```python
   class ConfigurationError(Exception):
       """Base exception for configuration errors."""
   
   class MandatoryFieldError(ConfigurationError):
       """Raised when a mandatory field is null."""
   
   class ValidationError(ConfigurationError):
       """Raised when a value fails validation."""
   ```

2. Update resolver methods to raise consistent errors:
   ```python
   def resolve_prompt(self, cli_value, env_key, default=None):
       if cli_value is EXPLICIT_NULL:
           return None
       # ... resolution logic
       
       if mandatory and result is None:
           raise MandatoryFieldError(f"{env_key} cannot be null")
   ```

3. Standardize error messages:
   ```
   {FIELD_NAME} cannot be {ACTUAL_VALUE}. 
   Expected: {EXPECTED_TYPE} (e.g., "{EXAMPLE}")
   ```

**Validation**:
- All resolver methods raise consistent errors
- Error messages include field name, expected, actual
- Tests cover all error scenarios

---

### 5.2 Phase 2: Validation Helpers (P2)

**Goal**: Create reusable validation helper methods.

**Tasks**:
1. Create validation utility class:
   ```python
   class ConfigValidator:
       @staticmethod
       def validate_string(value: str | None, mandatory: bool = False) -> str | None:
           # ... validation logic
       
       @staticmethod
       def validate_int(value: str | None, mandatory: bool = False) -> int | None:
           # ... validation logic
       
       @staticmethod
       def validate_bool(value: str | None, mandatory: bool = False) -> bool | None:
           # ... validation logic
   ```

2. Refactor ConfigResolver to use helpers:
   ```python
   def build_model_config_dict(self, cli_args, experiment) -> dict:
       return {
           "MODEL_TEMPERATURE": ConfigValidator.validate_float(
               getattr(cli_args, 'temperature', None)
           ),
           # ... more keys
       }
   ```

**Validation**:
- All validation uses helper methods
- No duplicated validation code
- Tests cover all validation scenarios

---

### 5.3 Phase 3: Mode Handling (P2)

**Goal**: Centralize execution mode handling.

**Tasks**:
1. Create mode enum and utilities:
   ```python
   from enum import Enum
   
   class ExecutionMode(str, Enum):
       TEST = "test"
       DEV = "dev"
       EXPERIMENT = "experiment"
   
   class ModeUtils:
       @staticmethod
       def is_config_frozen(mode: ExecutionMode) -> bool:
           return mode == ExecutionMode.EXPERIMENT
       
       @staticmethod
       def should_persist_data(mode: ExecutionMode) -> bool:
           return mode != ExecutionMode.TEST
   ```

2. Update ConfigResolver to use mode utilities:
   ```python
   def validate_debug_mode(self, mode: ExecutionMode, debug_enabled: bool) -> bool:
       if mode == ExecutionMode.EXPERIMENT and debug_enabled:
           raise ConfigurationError("Debug mode is blocked in EXPERIMENT mode")
       return debug_enabled
   ```

**Validation**:
- Mode enum used consistently
- Mode-aware validation working
- Tests cover all mode scenarios

---

### 5.4 Phase 4: Documentation (P3)

**Goal**: Complete configuration documentation.

**Tasks**:
1. Add examples to key inventory:
   ```markdown
   ### MODEL_TEMPERATURE
   
   **Example** (.env):
   ```
   MODEL_TEMPERATURE=0.7
   ```
   
   **Example** (CLI):
   ```
   --temperature 0.8
   ```
   
   **Example** (CLI null):
   ```
   --temperature null  # Bypasses .env, uses NULL
   ```
   ```

2. Add null semantics examples:
   ```markdown
   ### EXPLICIT_NULL Examples
   
   **Scenario 1**: Override .env default
   ```
   .env: MODEL_TEMPERATURE=0.7
   CLI:  --temperature null
   Result: MODEL_TEMPERATURE=null (bypasses .env)
   ```
   
   **Scenario 2**: Use .env default
   ```
   .env: MODEL_TEMPERATURE=0.7
   CLI:  (not specified)
   Result: MODEL_TEMPERATURE=0.7 (from .env)
   ```
   ```

**Validation**:
- All keys have examples
- Null semantics clearly documented
- Common patterns documented

---

## 6. Validation Criteria

### 6.1 Functional Validation

**All 28 Configuration Keys**:
- [ ] SYSTEM keys (5) resolved correctly
- [ ] EXPERIMENT keys (1 + 4 transient) resolved correctly
- [ ] MODEL keys (10) resolved correctly
- [ ] RUN keys (3) resolved correctly

**Null Semantics**:
- [ ] EXPLICIT_NULL bypasses .env
- [ ] Case-insensitive null parsing
- [ ] Mandatory fields reject null
- [ ] Optional fields accept null

**Capture Timing**:
- [ ] Experiment config frozen at creation
- [ ] Model variant config frozen at creation
- [ ] Run config frozen at creation
- [ ] AUTO seed resolved at run creation

**Inheritance**:
- [ ] Run inherits from experiment
- [ ] Model variant inherits from experiment
- [ ] CLI overrides all inheritance

---

### 6.2 Code Quality Validation

**Error Handling**:
- [ ] Custom exception types defined
- [ ] Consistent error messages
- [ ] All error scenarios covered

**Validation**:
- [ ] Reusable validation helpers
- [ ] No duplicated validation code
- [ ] All types validated correctly

**Testing**:
- [ ] Unit tests for all resolver methods
- [ ] Integration tests for full flow
- [ ] Edge case tests (empty, null, invalid)

---

### 6.3 Documentation Validation

**Contracts**:
- [ ] Resolution hierarchy documented
- [ ] Null semantics documented
- [ ] Capture timing documented
- [ ] Key inventory documented

**Examples**:
- [ ] All keys have usage examples
- [ ] Null semantics have examples
- [ ] Common patterns documented

---

## 7. Summary

### 7.1 Current State

**V2 Configuration System**: ✅ **90% Aligned** with Target Architecture

**Strengths**:
- ConfigResolver fully implemented
- Null semantics working correctly
- Capture timing correct
- JSON storage working

**Gaps**:
- Error handling inconsistent
- Validation code duplicated
- Mode handling decentralized
- Documentation incomplete

### 7.2 Migration Plan

**Phase 1 (P1)**: Error Handling Consistency
- Custom exception types
- Consistent error messages
- **Effort**: Low

**Phase 2 (P2)**: Validation Helpers
- Reusable validation methods
- Refactor ConfigResolver
- **Effort**: Low

**Phase 3 (P2)**: Mode Handling
- Mode enum and utilities
- Mode-aware validation
- **Effort**: Medium

**Phase 4 (P3)**: Documentation
- Key examples
- Null semantics examples
- **Effort**: Low

### 7.3 Recommended Next Steps

1. **Immediate**: Phase 1 (Error Handling) — Foundation for other improvements

2. **Short-term**: Phase 2 (Validation Helpers) — Reduce code duplication

3. **Medium-term**: Phase 3 (Mode Handling) — Centralize mode logic

4. **Long-term**: Phase 4 (Documentation) — Complete user-facing docs

### 7.4 Success Metrics

**Functional**:
- All 28 configuration keys working correctly
- Null semantics passing all tests
- Capture timing verified

**Code Quality**:
- No duplicated validation code
- Consistent error handling
- >90% test coverage

**Documentation**:
- All contracts documented
- All keys have examples
- User guide complete

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Status**: Adaptation Plan
