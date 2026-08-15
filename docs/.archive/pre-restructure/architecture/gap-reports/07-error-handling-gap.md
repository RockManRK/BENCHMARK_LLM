# Error Handling — Gap Report

**Document Type:** Gap Analysis
**Domain:** Error Handling
**Comparison:** V1 (Legacy) → V2 (Current)
**Purpose:** Identify feature parity gaps and migration priorities

---

## 1. Feature Parity Matrix

| V1 Feature | V2 Status | Gap Severity | Notes |
|------------|-----------|--------------|-------|
| **ErrorClassifier** | ⚠️ Partial | MEDIUM | Exists but NOT used by ExecutionEngine |
| **APIError Hierarchy** | ✅ Implemented | NONE | Same error types as V1 |
| **RetryHandler** | ⚠️ Partial | HIGH | Exists but NOT integrated |
| **RetryPolicy** | ✅ Implemented | NONE | Per-run configuration |
| **ExecutionEngine Retry** | ⚠️ Partial | CRITICAL | Inline retry, NO backoff delay |
| **ErrorCollector** | ❌ MISSING | MEDIUM | No error aggregation |
| **Logging Integration** | ❌ MISSING | CRITICAL | No visibility into errors/retry |
| **Stack Trace Capture** | ❌ MISSING | LOW | Only error_message stored |
| **Error Details JSON** | ❌ MISSING | LOW | Only error_type/message stored |
| **ErrorCategory Enum** | ❌ MISSING | LOW | Only error_type strings |

---

## 2. Missing Components

### 2.1 Logging Integration (CRITICAL)

**V1 Behavior**:
- Comprehensive logging throughout all components
- Retry attempts logged with delay and error message:
  ```
  INFO - Retry attempt 1/3 after 1.00s delay due to: HTTP 503 Service Unavailable
  ```
- Errors logged with full context (model, run_id, item_id)
- Progress tracking during execution

**V2 Status**:
- ❌ No logging in `ExecutionEngine._execute_item()`
- ❌ No logging in `RetryHandler.execute_with_retry()`
- ❌ No logging in `OpenRouterClient._handle_http_error()`
- ❌ No logging in `ResultWriter.write_results()`

**Impact**:
- No visibility into retry behavior
- No debugging capability for failures
- No audit trail for compliance
- No performance diagnostics
- **BLOCKER for production use**

**Migration Priority**: **CRITICAL**

**Recommended Approach**:
- Add `logging` module imports to all components
- Instrument key operations:
  - Retry attempt start (with attempt number, delay, error)
  - Retry success (with attempt count)
  - Retry failure (max attempts exceeded)
  - Error classification (error type, message)
  - Error persistence (run_id, error_type)
- Use structured logging with context (run_id, item_id, model_id)
- Configure root logger in application entry point

---

### 2.2 RetryHandler Integration (HIGH)

**V1 Behavior**:
- `ExecutionEngine` used `RetryHandler` for API calls
- Consistent retry behavior across all API calls
- Exponential backoff: 1s, 2s, 4s, 8s (capped at 60s)
- Max 3 retries by default
- Delay between retries via `asyncio.sleep(delay)`

**V2 Status**:
- ✅ `RetryHandler` exists in `src/api/retry.py`
- ❌ `ExecutionEngine` has inline retry loop instead
- ❌ **NO DELAY between retries** (missing `asyncio.sleep()`!)
- ❌ Inconsistent retry behavior

**Current V2 Inline Retry** (in `ExecutionEngine._execute_item()`):
```python
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        last_error_type = self._classify_error(e)
        last_error_message = str(e)
        if attempt < max_attempts:
            continue  # NO DELAY!
```

**Impact**:
- **CRITICAL**: No delay between retries = API abuse
- Technical debt (duplicate retry logic)
- Potential bugs from inconsistent behavior
- Harder to maintain (two retry implementations)
- Ineffective retry (no backoff to let transient issues resolve)

**Migration Priority**: **HIGH**

**Recommended Approach**:
1. **Immediate fix**: Add delay to inline retry loop
   ```python
   import asyncio
   
   for attempt in range(1, max_attempts + 1):
       try:
           response = self._call_api_sync(...)
           return ExecutionResult(...)
       except Exception as e:
           if attempt < max_attempts:
               delay = run.retry_policy.backoff_delay(attempt)
               await asyncio.sleep(delay)  # ADD THIS
   ```

2. **Long-term fix**: Refactor `ExecutionEngine._execute_item()` to use `RetryHandler`
   - Pass `RetryPolicy` from `PlanRun` to `RetryHandler`
   - Remove inline retry loop
   - Add tests for retry behavior

---

### 2.3 ErrorCollector (MEDIUM)

**V1 Behavior**:
- In-memory error aggregation via `ErrorCollector`
- Error categorization by type and category
- Error summary generation:
  ```python
  summary = collector.get_error_summary()
  # {
  #     "total_errors": 10,
  #     "by_category": {ErrorCategory.TIMEOUT: 5, ErrorCategory.API: 3, ...},
  #     "by_type": {"TimeoutError": 5, "HTTPStatusError": 3, ...}
  # }
  ```
- Stack trace capture for debugging

**V2 Status**:
- ❌ No ErrorCollector module
- ❌ No error aggregation
- ❌ No error summary generation
- ❌ No stack trace capture

**Impact**:
- No high-level error visibility
- No error pattern analysis
- No error reporting for users
- Harder to identify systemic issues

**Migration Priority**: **MEDIUM**

**Recommended Approach**:
- Reimplement `ErrorCollector` in V2
- Add error aggregation during execution
- Provide error summary in CLI output
- Optional: Add error analytics endpoint

---

### 2.4 ErrorClassifier Integration (MEDIUM)

**V1 Behavior**:
- `ErrorClassifier.classify_http()` used throughout
- Consistent error classification based on HTTP status
- `ErrorCategory.from_exception_type()` for exception classification

**V2 Status**:
- ✅ `ErrorClassifier` exists in `src/api/errors.py`
- ✅ Used by `OpenRouterClient._handle_http_error()`
- ❌ NOT used by `ExecutionEngine._classify_error()`
- ❌ ExecutionEngine uses simplified string matching instead

**Current V2 ExecutionEngine Classification**:
```python
def _classify_error(self, error: Exception) -> str:
    error_str = str(error).lower()

    if "timeout" in error_str:
        return "timeout"
    if "429" in error_str or "rate limit" in error_str:
        return "http_429"
    if "500" in error_str or "502" in error_str or "503" in error_str:
        return "http_5xx"
    # ... simplified string matching
```

**Impact**:
- Imprecise error classification
- May miss error types not matching string patterns
- Inconsistent with OpenRouterClient classification
- Harder to maintain (duplicate classification logic)

**Migration Priority**: **MEDIUM**

**Recommended Approach**:
- Refactor `ExecutionEngine._classify_error()` to use `ErrorClassifier`
- Handle APIError exceptions by extracting `error_type` field
- Handle other exceptions via `ErrorClassifier.classify_timeout()` etc.

---

## 3. Regressions

### 3.1 Backoff Formula Regression (MEDIUM)

**V1 Formula**:
```python
delay = base_delay * (exponential_base ** attempt)
# base_delay = 1.0, exponential_base = 2.0
# Attempt 0: 1.0s, Attempt 1: 2.0s, Attempt 2: 4.0s, Attempt 3: 8.0s
```

**V2 Formula** (in `RetryHandler.calculate_delay()`):
```python
if self.policy.backoff == 'exponential':
    return 2 ** attempt
# Attempt 1: 2s, Attempt 2: 4s, Attempt 3: 8s
```

**Regression**:
- V1 started at 1.0s (attempt 0-indexed)
- V2 starts at 2.0s (attempt 1-indexed)
- V2 has no `base_delay` configuration

**Impact**:
- Longer initial delay than V1
- Less configurable (no `base_delay` parameter)
- May cause unnecessary wait time

**Mitigation**:
- Add `base_delay` parameter to `RetryPolicy`
- Update formula: `delay = base_delay * (2 ** attempt)`
- Or adjust attempt indexing to match V1

---

### 3.2 No Max Delay Cap (MEDIUM)

**V1 Behavior**:
```python
delay = min(delay, self.config.max_delay)  # max_delay = 60.0
```

**V2 Status**:
- ❌ No `max_delay` parameter in `RetryPolicy`
- ❌ No cap on exponential backoff

**Impact**:
- Unbounded delay growth (2^10 = 1024s = 17 minutes!)
- May cause excessive wait times for high retry counts

**Mitigation**:
- Add `max_delay` parameter to `RetryPolicy`
- Cap delay in `RetryHandler.calculate_delay()`

---

### 3.3 No Stack Trace Capture (LOW)

**V1 Behavior**:
- `ErrorCollector.capture_error_from_exception()` captured stack traces:
  ```python
  stack_trace = traceback.format_exc()
  ```
- Stored in `ErrorInfo.stack_trace` field

**V2 Status**:
- ❌ No stack trace capture
- ❌ Only `error_message` stored in errors table

**Impact**:
- Harder to debug complex failures
- Less context for error analysis

**Mitigation**:
- Add `stack_trace` field to `ExecutionResult`
- Capture stack trace in `ExecutionEngine._execute_item()`
- Store in errors table (optional, may be large)

---

### 3.4 No Error Details JSON (LOW)

**V1 Behavior**:
- `error_handler.normalize_openrouter_error()` created detailed error JSON:
  ```python
  normalized = {
      "error_type": error_type,
      "http_status": http_status,
      "message": error_message,
      "raw_body": response_body,
  }
  ```
- Stored in `error_details` column (JSON format)

**V2 Status**:
- ❌ No `error_details` column in errors table
- ❌ Only `error_type` and `error_message` stored

**Impact**:
- Less context for debugging API errors
- No access to raw response body for analysis

**Mitigation**:
- Add `error_details` column to errors table (JSON)
- Populate with normalized error data from `ErrorClassifier`

---

### 3.5 No ErrorCategory Enum (LOW)

**V1 Behavior**:
- `ErrorCategory` enum for grouping errors:
  ```python
  class ErrorCategory(Enum):
      API = "api"
      NETWORK = "network"
      TIMEOUT = "timeout"
      RATE_LIMIT = "rate_limit"
      AUTHENTICATION = "authentication"
      VALIDATION = "validation"
      DATABASE = "database"
      UNKNOWN = "unknown"
  ```

**V2 Status**:
- ❌ No ErrorCategory enum
- ❌ Only `error_type` strings

**Impact**:
- Harder to group errors by category
- Less structured error analysis

**Mitigation**:
- Add `ErrorCategory` enum to `src/api/errors.py`
- Map `error_type` strings to categories

---

## 4. Improved Features (V2 Enhancements)

### 4.1 Policy-Driven Retry

**V1**: Hardcoded `RetryConfig` dataclass
**V2**: `RetryPolicy` in execution plan (per-run configuration)

**Improvement**:
- Per-run retry configuration
- Flexible backoff strategies (exponential, linear, constant)
- Explicit retryable error types list
- Configurable via experiment/run config

---

### 4.2 Explicit Error Types

**V1**: Error types via string matching
**V2**: `APIError` class hierarchy with `error_type` field

**Improvement**:
- Type-safe error handling
- Clear error class hierarchy
- Consistent error construction
- Better IDE support

---

### 4.3 ErrorClassifier Module

**V1**: Inline classification logic
**V2**: Dedicated `ErrorClassifier` class with static methods

**Improvement**:
- Centralized classification logic
- Deterministic classification (no heuristics)
- Easy to test in isolation
- Clear classification rules

---

## 5. Migration Priority

### 5.1 CRITICAL Priority (BLOCKERS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Logging Integration** | Medium | High | Add logging to all components immediately |
| **Retry Backoff Delay** | Low | Critical | **ADD DELAY NOW** - prevents API abuse |

**Rationale**: These gaps block production use and may cause API abuse.

**Immediate Action Required**:
```python
# In ExecutionEngine._execute_item(), add delay:
import asyncio

for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        if attempt < max_attempts:
            # CRITICAL FIX: Add delay before retry
            delay = 2 ** attempt  # Or use RetryPolicy.backoff_delay()
            await asyncio.sleep(delay)
```

---

### 5.2 HIGH Priority (FUNCTIONAL GAPS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **RetryHandler Integration** | Medium | Medium | Refactor ExecutionEngine to use RetryHandler |
| **ErrorClassifier Integration** | Low | Low | Use ErrorClassifier in _classify_error() |

**Rationale**: These gaps cause inconsistent behavior and technical debt.

---

### 5.3 MEDIUM Priority (FEATURE GAPS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **ErrorCollector** | Medium | Low | Reimplement for error aggregation |
| **Backoff Formula Fix** | Low | Low | Add base_delay parameter to RetryPolicy |
| **Max Delay Cap** | Low | Medium | Add max_delay to RetryPolicy |

**Rationale**: These gaps reduce usability but are not blockers.

---

### 5.4 LOW Priority (ENHANCEMENTS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Stack Trace Capture** | Low | Low | Add stack_trace to ExecutionResult |
| **Error Details JSON** | Medium | Low | Add error_details column to errors table |
| **ErrorCategory Enum** | Low | Low | Add ErrorCategory enum for grouping |

**Rationale**: These are nice-to-haves for better debugging.

---

## 6. Summary

### 6.1 Gap Summary by Severity

| Severity | Count | Components |
|----------|-------|------------|
| **CRITICAL** | 2 | Logging, Retry Backoff Delay |
| **HIGH** | 2 | RetryHandler Integration, ErrorClassifier Integration |
| **MEDIUM** | 3 | ErrorCollector, Backoff Formula, Max Delay Cap |
| **LOW** | 3 | Stack Trace, Error Details, ErrorCategory |

### 6.2 Overall Assessment

**V2 Architecture**: ✅ **SOUND**
- Clean error class hierarchy
- Policy-driven retry design
- Explicit error classification

**V2 Implementation**: ❌ **CRITICAL GAPS**
- Logging MISSING (BLOCKER)
- **Retry delay MISSING (CRITICAL - API abuse risk)**
- RetryHandler NOT integrated
- ErrorClassifier NOT fully integrated

**Migration Readiness**: ❌ **NOT READY**
- **CRITICAL**: Must add retry delay immediately
- Logging gap is a BLOCKER
- Retry integration needed before production

### 6.3 Recommended Migration Path

**Phase 0 (IMMEDIATE - TODAY)**:
1. **Add retry delay to ExecutionEngine** — Prevents API abuse
   ```python
   await asyncio.sleep(2 ** attempt)
   ```

**Phase 1 (THIS WEEK)**:
2. Add logging to all components
3. Integrate ErrorClassifier in ExecutionEngine
4. Add max_delay cap to RetryPolicy

**Phase 2 (NEXT WEEK)**:
5. Refactor ExecutionEngine to use RetryHandler
6. Fix backoff formula (add base_delay)
7. Add ErrorCollector for error aggregation

**Phase 3 (OPTIONAL)**:
8. Add stack trace capture
9. Add error_details JSON column
10. Add ErrorCategory enum

### 6.4 Success Criteria

Migration complete when:
- ✅ **CRITICAL**: Retry delay implemented (no API abuse)
- ✅ All CRITICAL priority gaps closed
- ✅ Logging provides full visibility into retry and errors
- ✅ RetryHandler integrated and tested
- ✅ ErrorClassifier used consistently
- ✅ All HIGH priority gaps addressed or accepted
- ✅ Tests pass for retry behavior

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Next Review**: After Phase 1 implementation
