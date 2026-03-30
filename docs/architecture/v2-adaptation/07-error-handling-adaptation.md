# Error Handling — V2 Adaptation

**Document Type:** Adaptation Guide
**Domain:** Error Handling
**Purpose:** Guide V2 implementation toward TO-BE architecture compliance

---

## 1. Current State Assessment

### 1.1 What's Implemented

**Components** (from `src/` directory):

| Component | Location | Status | Alignment |
|-----------|----------|--------|-----------|
| `ErrorClassifier` | `src/api/errors.py` | ✅ Complete | ✅ Aligned |
| `APIError` Hierarchy | `src/api/errors.py` | ✅ Complete | ✅ Aligned |
| `RetryHandler` | `src/api/retry.py` | ✅ Complete | ✅ Aligned |
| `RetryPolicy` | `src/core/execution_plan.py` | ✅ Complete | ✅ Aligned |
| `ExecutionEngine` (retry) | `src/core/execution_engine.py` | ⚠️ Partial | ❌ Not Aligned |
| `ResultWriter` (errors) | `src/core/result_writer.py` | ✅ Complete | ✅ Aligned |

### 1.2 What's Missing

| Component | Status | Impact |
|-----------|--------|--------|
| Logging Integration | ❌ MISSING | BLOCKER - No visibility |
| Retry Delay in ExecutionEngine | ❌ MISSING | CRITICAL - API abuse risk |
| `ErrorCollector` | ❌ MISSING | MEDIUM - No error aggregation |
| Stack Trace Capture | ❌ MISSING | LOW - Less debug context |
| `error_details` JSON | ❌ MISSING | LOW - Less error context |

### 1.3 Architectural Violations

**Current V2 Violations**:

1. **ExecutionEngine does NOT use RetryHandler**
   - Has inline retry loop instead
   - No delay between retries (missing `asyncio.sleep()`)
   - **Severity**: CRITICAL

2. **ExecutionEngine does NOT use ErrorClassifier**
   - Has simplified `_classify_error()` with string matching
   - **Severity**: MEDIUM

3. **No Logging**
   - No visibility into retry behavior or errors
   - **Severity**: CRITICAL (BLOCKER)

---

## 2. Target State (Architecture Specs)

### 2.1 Error Handling Architecture

```
OpenRouterClient.chat_completion()
    ↓ (raises APIError via ErrorClassifier)
RetryHandler.execute_with_retry()
    ↓ (retries with backoff delay)
ExecutionEngine._execute_item()
    ↓ (catches Exception, logs error, creates ExecutionResult)
ExecutionResult (status="failure" with error details)
    ↓
ResultWriter.write_results()
    ↓ (writes to errors table, logs persistence)
Database (errors table)
```

### 2.2 Key Contracts

**Retry Contract**:
- `RetryPolicy` controls retry behavior
- `RetryHandler` executes retry logic
- Backoff delay: `base_delay * 2^(attempt-1)`, capped at `max_delay`
- Default: 1s, 2s, 4s, 8s, 16s, 32s, 60s (capped)

**Classification Contract**:
- `ErrorClassifier.classify_http()` for HTTP errors
- `ErrorClassifier.classify_timeout()` for timeouts
- `ErrorClassifier.classify_network()` for network errors
- Deterministic classification (no heuristics)

**Logging Contract**:
- Log retry attempts with delay and error message
- Log retry success/failure
- Log error classification
- Log error persistence

**Persistence Contract**:
- Failed results → `errors` table
- Deterministic error IDs: `err-{run_id}-{variant_id}-{snapshot_id}`
- Idempotent writes (INSERT OR IGNORE)

---

## 3. Gap Analysis

### 3.1 Critical Gaps (BLOCKERS)

| Gap | Current State | Target State | Effort |
|-----|---------------|--------------|--------|
| **Logging** | No logging statements | Comprehensive logging at all error points | Medium |
| **Retry Delay** | No delay between retries | `asyncio.sleep(delay)` with backoff formula | Low |

### 3.2 High Priority Gaps

| Gap | Current State | Target State | Effort |
|-----|---------------|--------------|--------|
| **RetryHandler Integration** | Inline retry in ExecutionEngine | Use RetryHandler.execute_with_retry() | Medium |
| **ErrorClassifier Integration** | String matching in _classify_error() | Use ErrorClassifier static methods | Low |

### 3.3 Medium Priority Gaps

| Gap | Current State | Target State | Effort |
|-----|---------------|--------------|--------|
| **ErrorCollector** | Not implemented | Reimplement for error aggregation | Medium |
| **Backoff Formula** | `2^attempt` (no base_delay) | `base_delay * 2^(attempt-1)` | Low |
| **Max Delay Cap** | Not implemented | Add `max_delay` parameter | Low |

### 3.4 Low Priority Gaps

| Gap | Current State | Target State | Effort |
|-----|---------------|--------------|--------|
| **Stack Trace Capture** | Not implemented | Capture in ExecutionResult | Low |
| **Error Details JSON** | Not implemented | Add `error_details` column | Medium |
| **ErrorCategory Enum** | Not implemented | Add enum for grouping | Low |

---

## 4. Implementation Considerations

### 4.1 Critical Fix: Add Retry Delay (IMMEDIATE)

**Problem**: ExecutionEngine has no delay between retries, causing API abuse.

**Current Code** (`src/core/execution_engine.py`):
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

**Fix** (add delay):
```python
import asyncio

for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        last_error_type = self._classify_error(e)
        last_error_message = str(e)
        if attempt < max_attempts:
            # CRITICAL FIX: Add delay before retry
            delay = 2 ** attempt  # Or use RetryPolicy
            await asyncio.sleep(delay)
            continue
```

**Better Fix** (use RetryPolicy):
```python
# Add method to RetryPolicy
def backoff_delay(self, attempt: int) -> float:
    """Calculate delay for a given attempt (1-indexed)."""
    if self.backoff == 'exponential':
        delay = self.base_delay * (2.0 ** (attempt - 1))
        return min(delay, self.max_delay)
    if self.backoff == 'linear':
        delay = self.base_delay * attempt
        return min(delay, self.max_delay)
    return self.base_delay

# Use in ExecutionEngine
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        if attempt < max_attempts:
            delay = run.retry_policy.backoff_delay(attempt)
            await asyncio.sleep(delay)
            continue
```

---

### 4.2 Critical Fix: Add Logging (HIGH)

**Problem**: No visibility into retry behavior or errors.

**Required Log Points**:

**In `ExecutionEngine._execute_item()`**:
```python
import logging

logger = logging.getLogger(__name__)

def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
    attempt_count = 0
    last_error_type: str | None = None
    last_error_message: str | None = None

    max_attempts = run.retry_policy.max_attempts

    for attempt in range(1, max_attempts + 1):
        attempt_count = attempt

        try:
            logger.debug(
                f"Attempting item {item.item_id} (attempt {attempt}/{max_attempts})"
            )

            response = self._call_api_sync(...)

            if attempt > 1:
                logger.info(
                    f"Item {item.item_id} succeeded after {attempt} attempts"
                )

            return ExecutionResult(...)

        except Exception as e:
            last_error_type = self._classify_error(e)
            last_error_message = str(e)

            logger.warning(
                f"Item {item.item_id} failed (attempt {attempt}/{max_attempts}): "
                f"{last_error_type} - {last_error_message}"
            )

            if attempt < max_attempts:
                delay = run.retry_policy.backoff_delay(attempt)
                logger.info(
                    f"Retrying item {item.item_id} after {delay:.2f}s delay"
                )
                await asyncio.sleep(delay)
                continue

    logger.error(
        f"Item {item.item_id} failed after {attempt_count} attempts: "
        f"{last_error_type} - {last_error_message}"
    )

    return ExecutionResult(
        status="failure",
        error_type=last_error_type,
        error_message=last_error_message,
        attempt_count=attempt_count,
        ...
    )
```

**In `OpenRouterClient._handle_http_error()`**:
```python
def _handle_http_error(self, response: httpx.Response) -> None:
    try:
        error_data = response.json()
        error_message = error_data.get("error", {}).get("message", str(response))
    except Exception:
        error_message = response.text or f"HTTP {response.status_code}"

    error = ErrorClassifier.classify_http(response.status_code, error_message)

    logger.warning(
        f"HTTP {response.status_code} for model {model_id}: {error_message}"
    )

    raise error
```

---

### 4.3 High Priority: Integrate RetryHandler (MEDIUM EFFORT)

**Problem**: ExecutionEngine has inline retry instead of using RetryHandler.

**Current Approach** (inline retry):
```python
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return ExecutionResult(...)
    except Exception as e:
        # Handle error
```

**Target Approach** (use RetryHandler):
```python
from src.api.retry import RetryHandler

def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
    # Create retry handler for this item
    retry_handler = RetryHandler(run.retry_policy)

    async def execute_api_call():
        response = self._call_api_sync(...)
        return response

    try:
        response = await retry_handler.execute_with_retry(execute_api_call)
        return ExecutionResult(status="success", ...)
    except Exception as e:
        return ExecutionResult(
            status="failure",
            error_type=self._classify_error(e),
            error_message=str(e),
            attempt_count=run.retry_policy.max_attempts,
            ...
        )
```

**Trade-offs**:
- ✅ Cleaner separation of concerns
- ✅ Consistent retry behavior
- ✅ Easier to test
- ⚠️ More complex async handling
- ⚠️ Requires refactoring `_call_api_sync()` to be fully async

**Recommendation**: Start with inline retry + delay (Section 4.1), then refactor to RetryHandler later.

---

### 4.4 High Priority: Integrate ErrorClassifier (LOW EFFORT)

**Problem**: ExecutionEngine uses simplified string matching for error classification.

**Current Code**:
```python
def _classify_error(self, error: Exception) -> str:
    error_str = str(error).lower()

    if "timeout" in error_str:
        return "timeout"
    if "429" in error_str or "rate limit" in error_str:
        return "http_429"
    if "500" in error_str or "502" in error_str or "503" in error_str:
        return "http_5xx"
    # ...
    return "api_error"
```

**Target Code**:
```python
from src.api.errors import ErrorClassifier, APIError

def _classify_error(self, error: Exception) -> str:
    """Classify an error type using ErrorClassifier."""
    # If it's an APIError, use its error_type
    if isinstance(error, APIError):
        return error.error_type

    # Use ErrorClassifier for other exceptions
    if isinstance(error, httpx.TimeoutException):
        return ErrorClassifier.classify_timeout(str(error)).error_type

    if isinstance(error, (httpx.ConnectError, httpx.NetworkError)):
        return ErrorClassifier.classify_network(str(error)).error_type

    if isinstance(error, httpx.HTTPStatusError):
        return ErrorClassifier.classify_http(
            error.response.status_code,
            error.response.text
        ).error_type

    # Fallback
    return "api_error"
```

---

## 5. Migration Path

### 5.1 Phase 0: Critical Fixes (IMMEDIATE - TODAY)

**Goal**: Prevent API abuse and add basic visibility.

**Tasks**:
1. **Add retry delay to ExecutionEngine** (Section 4.1)
   - Add `asyncio.sleep(delay)` between retries
   - Use `RetryPolicy.backoff_delay()` method
   - Test with simulated failures

2. **Add basic logging** (Section 4.2)
   - Add `logging` import to `execution_engine.py`
   - Log retry attempts with delay
   - Log final failure after max attempts
   - Configure root logger in application entry point

**Validation**:
- ✅ Retry delays are applied (check logs)
- ✅ No API abuse (monitor rate limits)
- ✅ Logs show retry behavior

---

### 5.2 Phase 1: High Priority (THIS WEEK)

**Goal**: Achieve architectural alignment.

**Tasks**:
1. **Integrate ErrorClassifier** (Section 4.4)
   - Replace string matching with ErrorClassifier
   - Test with various error types
   - Verify error_type values match spec

2. **Add comprehensive logging** (Section 4.2)
   - Log in OpenRouterClient
   - Log in ResultWriter
   - Add structured context (run_id, item_id, model_id)

3. **Fix RetryPolicy** (add missing parameters)
   - Add `base_delay: float = 1.0`
   - Add `max_delay: float = 60.0`
   - Update `backoff_delay()` formula

**Validation**:
- ✅ Error types match architecture spec
- ✅ Logs provide full visibility
- ✅ RetryPolicy has all parameters

---

### 5.3 Phase 2: Medium Priority (NEXT WEEK)

**Goal**: Complete feature parity with V1.

**Tasks**:
1. **Refactor to use RetryHandler** (Section 4.3)
   - Replace inline retry with RetryHandler
   - Test async handling
   - Verify retry behavior matches spec

2. **Add ErrorCollector** (optional)
   - Reimplement from V1
   - Add error aggregation
   - Provide error summary in CLI

3. **Add max_delay cap**
   - Ensure delays don't grow unbounded
   - Test with high retry counts

**Validation**:
- ✅ RetryHandler is used consistently
- ✅ ErrorCollector provides aggregation
- ✅ Delays are capped appropriately

---

### 5.4 Phase 3: Low Priority (OPTIONAL)

**Goal**: Enhance debugging capability.

**Tasks**:
1. **Add stack trace capture**
   - Capture in ExecutionResult
   - Store in errors table (optional column)

2. **Add error_details JSON**
   - Add column to errors table
   - Populate with normalized error data

3. **Add ErrorCategory enum**
   - Group error types by category
   - Enable category-based analysis

**Validation**:
- ✅ Stack traces available for debugging
- ✅ Error details provide full context
- ✅ Error categories enable grouping

---

## 6. Validation Criteria

### 6.1 Functional Validation

**Retry Behavior**:
```bash
# Simulate transient failure (HTTP 503)
# Expected: 3 retry attempts with delays (1s, 2s, 4s)
# Check logs for:
# - "Retry attempt 1/3 after 1.00s delay"
# - "Retry attempt 2/3 after 2.00s delay"
# - "Operation succeeded after 2 retry attempt(s)"
```

**Error Classification**:
```python
# Test ErrorClassifier
from src.api.errors import ErrorClassifier

error = ErrorClassifier.classify_http(429, "Rate limit exceeded")
assert error.error_type == "http_429"
assert isinstance(error, RateLimitError)

error = ErrorClassifier.classify_http(503, "Service unavailable")
assert error.error_type == "http_5xx"
assert isinstance(error, ServerError)
```

**Error Persistence**:
```sql
-- Check errors table
SELECT error_type, error_message, attempt_count
FROM errors
WHERE run_id = 'run-001'
ORDER BY created_at DESC;

-- Expected: Errors with correct types and attempt counts
```

### 6.2 Logging Validation

**Required Log Output**:
```
INFO - Starting execution of plan plan-001
DEBUG - Attempting item item-001 (attempt 1/3)
WARNING - Item item-001 failed (attempt 1/3): http_503 - Service unavailable
INFO - Retrying item item-001 after 1.00s delay
DEBUG - Attempting item item-001 (attempt 2/3)
INFO - Item item-001 succeeded after 2 attempts
INFO - Completed run run-001: 1 items executed
```

### 6.3 Performance Validation

**Retry Delay Timing**:
```bash
# Measure actual delays between retries
# Expected: ~1s, ~2s, ~4s (within 10% tolerance)

# Test with mock server that returns 503 twice, then 200
# Measure time between attempts
```

**No API Abuse**:
```bash
# Monitor rate limit headers
# Expected: No 429 errors from excessive retries
# Check: X-RateLimit-Remaining header stays positive
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

**RetryHandler Tests**:
```python
def test_retry_handler_exponential_backoff():
    policy = RetryPolicy(max_attempts=3, backoff='exponential', base_delay=1.0)
    handler = RetryHandler(policy)

    assert handler.calculate_delay(1) == 1.0
    assert handler.calculate_delay(2) == 2.0
    assert handler.calculate_delay(3) == 4.0

def test_retry_handler_max_delay_cap():
    policy = RetryPolicy(max_attempts=10, max_delay=10.0)
    handler = RetryHandler(policy)

    delay = handler.calculate_delay(10)
    assert delay == 10.0  # Capped at max_delay
```

**ErrorClassifier Tests**:
```python
def test_error_classifier_http_status_codes():
    error = ErrorClassifier.classify_http(429, "Rate limit")
    assert error.error_type == "http_429"
    assert isinstance(error, RateLimitError)

    error = ErrorClassifier.classify_http(503, "Unavailable")
    assert error.error_type == "http_5xx"
    assert isinstance(error, ServerError)
```

### 7.2 Integration Tests

**Retry Integration Test**:
```python
async def test_execution_engine_retry_with_delay():
    # Mock API client that fails twice, then succeeds
    call_count = 0
    async def mock_chat_completion(...):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ServerError("Simulated failure")
        return mock_response

    engine = ExecutionEngine(mock_client, ...)
    result = await engine._execute_item(item, run)

    assert call_count == 3  # 3 attempts
    assert result.status == "success"
```

### 7.3 End-to-End Tests

**Full Execution Test**:
```python
def test_full_execution_with_errors():
    # Run experiment with known failing model
    # Check:
    # - Errors are logged
    # - Errors are persisted to database
    # - Run status is 'partial_failed' or 'failed'
    # - Error types are correct
```

---

## 8. Summary

### 8.1 Current State

**Implemented**:
- ✅ ErrorClassifier (standalone)
- ✅ APIError hierarchy
- ✅ RetryHandler (standalone)
- ✅ RetryPolicy
- ✅ ResultWriter error persistence

**Missing**:
- ❌ Logging (BLOCKER)
- ❌ Retry delay in ExecutionEngine (CRITICAL)
- ❌ RetryHandler integration
- ❌ ErrorClassifier integration

### 8.2 Migration Priority

**Phase 0 (IMMEDIATE)**:
1. Add retry delay to ExecutionEngine
2. Add basic logging

**Phase 1 (THIS WEEK)**:
3. Integrate ErrorClassifier
4. Add comprehensive logging
5. Fix RetryPolicy parameters

**Phase 2 (NEXT WEEK)**:
6. Refactor to use RetryHandler
7. Add ErrorCollector (optional)

**Phase 3 (OPTIONAL)**:
8. Add stack trace capture
9. Add error_details JSON
10. Add ErrorCategory enum

### 8.3 Success Criteria

Migration complete when:
- ✅ **CRITICAL**: Retry delay implemented (no API abuse)
- ✅ **CRITICAL**: Logging provides full visibility
- ✅ All HIGH priority gaps closed
- ✅ RetryHandler integrated and tested
- ✅ ErrorClassifier used consistently
- ✅ Tests pass for retry behavior

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Next Review**: After Phase 1 implementation
