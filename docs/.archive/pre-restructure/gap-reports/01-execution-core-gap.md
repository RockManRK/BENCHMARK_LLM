# Execution Core — Gap Report

**Document Type:** Gap Analysis  
**Domain:** Execution Core  
**Comparison:** V1 (Legacy) → V2 (Current)  
**Purpose:** Identify feature parity gaps and migration priorities  

---

## 1. Feature Parity Matrix

| V1 Feature | V2 Status | Gap Severity | Notes |
|------------|-----------|--------------|-------|
| **ExecutionEngine** | ✅ Implemented | NONE | Pure execution, NO DB access |
| **ResultWriter** | ✅ Implemented | NONE | Idempotent, calculates needs_review |
| **Planner** | ✅ Implemented | NONE | Read-only, resolves effective config |
| **ExecutionPlan** | ✅ Implemented | NONE | Immutable dataclasses |
| **OpenRouterClient** | ⚠️ Partial | MEDIUM | Timeout reduced (120s vs 180s) |
| **RetryHandler** | ⚠️ Partial | HIGH | Exists but NOT integrated |
| **AnswerParser** | ✅ Implemented | NONE | V1 parity achieved |
| **AnswerRandomizer** | ⚠️ Partial | MEDIUM | Exists, needs verification |
| **Logging System** | ❌ MISSING | CRITICAL | No visibility into execution |
| **ErrorClassifier** | ⚠️ Partial | LOW | Exists but NOT used by ExecutionEngine |
| **Multimodal Support** | ⚠️ Unknown | MEDIUM | Needs verification |
| **Debug Mode** | ❌ MISSING | LOW | No request/response capture |
| **Repository Pattern** | ❌ Abandoned | LOW | Direct SQLite in V2 |

---

## 2. Missing Components

### 2.1 Logging System (CRITICAL)

**V1 Behavior**:
- Comprehensive logging throughout all components
- Structured messages with context (model, run_id, item_id)
- Multiple log levels (DEBUG, INFO, WARNING, ERROR)
- Progress tracking during execution

**V2 Status**:
- ❌ No logging in `ExecutionEngine`
- ❌ No logging in `ResultWriter`
- ❌ No logging in `Planner`
- ❌ No logging in `OpenRouterClient`

**Impact**:
- No visibility into execution progress
- No debugging capability for failures
- No audit trail for compliance
- No performance diagnostics

**Migration Priority**: **HIGH** (BLOCKER)

**Recommended Approach**:
- Add `logging` module imports to all components
- Instrument key operations (start, complete, error)
- Use structured logging with context (run_id, item_id, model_id)
- Configure root logger in application entry point

---

### 2.2 RetryHandler Integration (HIGH)

**V1 Behavior**:
- `ExecutionEngine` uses `RetryHandler` for API calls
- Consistent retry behavior across all API calls
- Exponential backoff: 1s, 2s, 4s, 8s (capped at 60s)
- Max 3 retries by default

**V2 Status**:
- ✅ `RetryHandler` exists in `src/api/retry.py`
- ❌ `ExecutionEngine` has inline retry loop instead
- ❌ Inconsistent retry behavior

**Impact**:
- Technical debt (duplicate retry logic)
- Potential bugs from inconsistent behavior
- Harder to maintain (two retry implementations)

**Migration Priority**: **HIGH**

**Recommended Approach**:
- Refactor `ExecutionEngine._execute_item()` to use `RetryHandler`
- Pass `RetryPolicy` from `PlanRun` to `RetryHandler`
- Remove inline retry loop
- Add tests for retry behavior

---

### 2.3 Debug Mode (LOW)

**V1 Behavior**:
- `include_debug=True` flag in API client
- Captures request payload and upstream body
- Useful for debugging API issues

**V2 Status**:
- ❌ No debug mode in `OpenRouterClient`

**Impact**:
- Harder to debug API integration issues
- No visibility into raw request/response

**Migration Priority**: **LOW**

**Recommended Approach**:
- Add `include_debug` parameter to `OpenRouterClient.chat_completion()`
- Capture request payload and response body
- Return debug info in `CompletionResponse.raw_response`

---

## 3. Improved Components (V2 Enhancements)

### 3.1 Provider-Agnostic Design

**V1**: Tightly coupled to OpenRouter  
**V2**: Abstract `CompletionProvider` base class

**Improvement**:
- Easy to add new providers (Anthropic, Google, etc.)
- Testable with mock providers
- Cleaner architecture

---

### 3.2 Immutable Dataclasses

**V1**: Mutable dataclasses  
**V2**: `frozen=True` dataclasses

**Improvement**:
- Reproducibility (plans cannot change)
- Thread safety (immutable objects)
- Clear ownership (only Planner creates plans)

---

### 3.3 Contract-Driven Development

**V1**: Implicit contracts  
**V2**: Explicit contracts (e.g., `result-writer.md`)

**Improvement**:
- Clear expectations
- Easier validation
- Better documentation

---

### 3.4 Policy-Driven Retry

**V1**: Hardcoded retry config  
**V2**: `RetryPolicy` dataclass

**Improvement**:
- Per-run retry configuration
- Flexible backoff strategies (exponential, linear, constant)
- Explicit retryable error types

---

## 4. Regression Risks

### 4.1 API Timeout Reduction (MEDIUM)

**V1**: 180 seconds  
**V2**: 120 seconds

**Risk**:
- Reasoning models may timeout (some take 2-3 minutes)
- Execution failures for slow models
- Incomplete results

**Mitigation**:
- Restore 180s timeout (or make configurable)
- Add timeout per model variant

---

### 4.2 Simplified Error Classification (LOW)

**V1**: `ErrorClassifier` module with comprehensive mapping  
**V2**: Inline `_classify_error()` in ExecutionEngine

**Risk**:
- Less precise error types
- Harder to debug failures
- Inconsistent error handling

**Mitigation**:
- Integrate `ErrorClassifier` from `src/api/errors.py`
- Use in `ExecutionEngine._classify_error()`

---

### 4.3 Repository Pattern Abandoned (LOW)

**V1**: Repository pattern for DB access  
**V2**: Direct SQLite in ResultWriter

**Risk**:
- Harder to test (DB coupling)
- Less abstraction
- SQL scattered throughout code

**Mitigation**:
- Consider reintroducing repository pattern
- Or add integration tests for ResultWriter

---

### 4.4 Multimodal Support Unknown (MEDIUM)

**V1**: Explicit multimodal support (`build_multimodal_message()`)  
**V2**: Not verified

**Risk**:
- Vision models may not work
- Image-based questions fail

**Mitigation**:
- Verify multimodal support in V2
- Add `build_multimodal_message()` if missing
- Test with image-based questions

---

## 5. Migration Priority

### 5.1 HIGH Priority (BLOCKERS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Logging System** | Medium | High | Add logging to all components immediately |
| **RetryHandler Integration** | Low | Medium | Refactor ExecutionEngine to use RetryHandler |

**Rationale**: These gaps block production use and introduce bugs.

---

### 5.2 MEDIUM Priority (FEATURE GAPS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **API Timeout** | Low | Medium | Increase to 180s or make configurable |
| **AnswerRandomizer Verification** | Low | Medium | Verify seed=None semantics |
| **Multimodal Support** | Medium | Medium | Verify and test image support |

**Rationale**: These gaps may cause execution failures in specific scenarios.

---

### 5.3 LOW Priority (TECHNICAL DEBT)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **ErrorClassifier Integration** | Low | Low | Use ErrorClassifier in ExecutionEngine |
| **Debug Mode** | Low | Low | Add debug mode to OpenRouterClient |
| **Repository Pattern** | High | Low | Consider reintroducing (optional) |

**Rationale**: These are nice-to-haves, not blockers.

---

## 6. Summary

### 6.1 Gap Summary by Severity

| Severity | Count | Components |
|----------|-------|------------|
| **CRITICAL** | 1 | Logging System |
| **HIGH** | 1 | RetryHandler Integration |
| **MEDIUM** | 3 | API Timeout, AnswerRandomizer, Multimodal Support |
| **LOW** | 3 | ErrorClassifier, Debug Mode, Repository Pattern |

### 6.2 Overall Assessment

**V2 Architecture**: ✅ **SOUND**
- Follows TO-BE principles
- Clean separation of concerns
- Immutable data structures
- Contract-driven design

**V2 Implementation**: ⚠️ **INCOMPLETE**
- Core components implemented
- Critical gaps (logging, retry integration)
- Some regressions (timeout, error classification)

**Migration Readiness**: ❌ **NOT READY**
- Logging gap is a BLOCKER
- Retry integration needed before production
- Verification needed for randomizer and multimodal

### 6.3 Recommended Migration Path

**Phase 1 (IMMEDIATE)**:
1. Add logging to all components
2. Integrate RetryHandler into ExecutionEngine
3. Increase API timeout to 180s

**Phase 2 (SHORT-TERM)**:
4. Verify AnswerRandomizer behavior
5. Verify multimodal support
6. Integrate ErrorClassifier

**Phase 3 (OPTIONAL)**:
7. Add debug mode
8. Consider repository pattern

### 6.4 Success Criteria

Migration complete when:
- ✅ All HIGH priority gaps closed
- ✅ Logging provides full visibility
- ✅ Retry behavior matches V1
- ✅ All MEDIUM priority gaps addressed or accepted
- ✅ Tests pass for all components

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-29  
**Next Review**: After Phase 1 implementation
