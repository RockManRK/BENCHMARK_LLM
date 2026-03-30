# Error Handling — V2 Current State

**Document Type:** Current State Analysis
**Domain:** Error Handling
**Source:** `src/` directory (TO-BE architecture)
**Purpose:** Document what actually exists in V2 implementation

---

## 1. Domain Overview

### 1.1 What Exists in V2

The V2 Error Handling domain implements error classification, retry logic, and error propagation with the following components:

| Component | Status | Location |
|-----------|--------|----------|
| ErrorClassifier | ✅ Implemented | `src/api/errors.py` |
| APIError Hierarchy | ✅ Implemented | `src/api/errors.py` |
| RetryHandler | ✅ Implemented | `src/api/retry.py` |
| RetryPolicy | ✅ Implemented | `src/core/execution_plan.py` |
| ExecutionEngine Error Handling | ⚠️ Partial | `src/core/execution_engine.py` |
| ResultWriter Error Persistence | ✅ Implemented | `src/core/result_writer.py` |
| ErrorCollector | ❌ MISSING | Not implemented in V2 |
| Logging Integration | ❌ MISSING | No logging statements |

### 1.2 Architectural Alignment

V2 follows the TO-BE architecture principles for error handling:

- ✅ **Explicit Error Types**: Error class hierarchy with `error_type` field
- ✅ **Policy-Driven Retry**: RetryPolicy dataclass controls retry behavior
- ✅ **Error Propagation**: Errors flow through ExecutionEngine → ResultWriter → Database
- ✅ **Error Persistence**: Failed results written to `errors` table
- ⚠️ **Error Transparency**: Error classification exists but logging is MISSING

---

## 2. Component Status

### 2.1 ErrorClassifier

**Status**: ✅ Implemented (but NOT used by ExecutionEngine)

**What's Coded**:
- Static methods for classifying HTTP errors into domain-specific types
- Deterministic classification (no heuristics, no inference)
- Clear error type mapping based on HTTP status codes

**Implementation Details**:
```python
class ErrorClassifier:
    @staticmethod
    def classify_http(status_code: int, response_text: str) -> APIError:
        message = f"HTTP {status_code}: {response_text}"

        if status_code == 429:
            return RateLimitError(message)

        if 500 <= status_code < 600:
            return ServerError(message)

        if status_code in (401, 403):
            return AuthenticationError(message)

        if 400 <= status_code < 500:
            return ClientError(message)

        # Fallback
        return APIError(message, error_type=f"http_{status_code}")

    @staticmethod
    def classify_timeout(message: str = "Request timed out") -> TimeoutError:
        return TimeoutError(message)

    @staticmethod
    def classify_network(message: str = "Network error") -> NetworkError:
        return NetworkError(message)
```

**Classification Rules**:
| Status Code | Error Type | Class |
|-------------|-----------|-------|
| 429 | `http_429` | `RateLimitError` |
| 500-599 | `http_5xx` | `ServerError` |
| 401, 403 | `authentication` | `AuthenticationError` |
| 400-499 (other) | `http_4xx` | `ClientError` |

**Gap**:
- ❌ ExecutionEngine does NOT use `ErrorClassifier`
- ❌ ExecutionEngine has simplified inline `_classify_error()` instead

---

### 2.2 APIError Hierarchy

**Status**: ✅ Implemented

**What's Coded**:
- Base `APIError` class with `error_type` field
- Specific error subclasses for each error type
- Consistent constructor signature

**Error Classes**:
```python
class APIError(Exception):
    """Base API error."""
    def __init__(self, message: str, error_type: str, raw_error: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.raw_error = raw_error

class AuthenticationError(APIError):
    """Authentication/authorization failure (401, 403)."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="authentication", raw_error=raw_error)

class RateLimitError(APIError):
    """Rate limit exceeded (429)."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="http_429", raw_error=raw_error)

class ServerError(APIError):
    """Server error (5xx)."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="http_5xx", raw_error=raw_error)

class ClientError(APIError):
    """Client error (4xx, non-auth)."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="http_4xx", raw_error=raw_error)

class TimeoutError(APIError):
    """Request timeout."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="timeout", raw_error=raw_error)

class NetworkError(APIError):
    """Network connectivity error."""
    def __init__(self, message: str, raw_error: dict | None = None) -> None:
        super().__init__(message, error_type="network_error", raw_error=raw_error)
```

**Alignment with V1**:
- ✅ Same error types (authentication, rate_limit, server_error, etc.)
- ✅ Same `error_type` field for programmatic handling
- ✅ Same exception hierarchy

---

### 2.3 RetryHandler

**Status**: ✅ Implemented (but NOT used by ExecutionEngine)

**What's Coded**:
- Policy-driven retry logic
- Executes `RetryPolicy` configuration
- Supports backoff strategies: exponential, linear, constant
- Checks if errors are retryable per policy

**Implementation Details**:
```python
class RetryHandler:
    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self.policy = policy if policy is not None else RetryPolicy()

    def is_retryable(self, error: APIError) -> bool:
        """Check if error is retryable based on policy."""
        return error.error_type in self.policy.retry_on

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on backoff strategy."""
        if self.policy.backoff == 'exponential':
            return 2 ** attempt
        if self.policy.backoff == 'linear':
            return float(attempt)
        # constant
        return 1.0

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        last_exception: Exception | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return await func(*args, **kwargs)

            except APIError as e:
                last_exception = e

                # Check if retryable
                if not self.is_retryable(e):
                    raise

                # Check if more attempts available
                if attempt >= self.policy.max_attempts:
                    break

                # Wait before retry
                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-APIError exceptions
                last_exception = e

                if attempt >= self.policy.max_attempts:
                    break

                delay = self.calculate_delay(attempt)
                await asyncio.sleep(delay)

        if last_exception is not None:
            raise last_exception

        raise RuntimeError("Retry loop completed without result or exception")
```

**Backoff Strategies**:
| Strategy | Formula | Example (attempts 1-3) |
|----------|---------|------------------------|
| `exponential` | `2^attempt` | 2s, 4s, 8s |
| `linear` | `attempt` | 1s, 2s, 3s |
| `constant` | `1.0` | 1s, 1s, 1s |

**Gap**:
- ❌ ExecutionEngine does NOT use `RetryHandler`
- ❌ ExecutionEngine has inline retry loop instead
- ❌ Inconsistent retry behavior between components

---

### 2.4 RetryPolicy

**Status**: ✅ Implemented (in `src/core/execution_plan.py`)

**What's Coded**:
```python
@dataclass(frozen=True)
class RetryPolicy:
    """Policy for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (default 3)
        backoff: Backoff strategy: 'exponential', 'linear', 'constant' (default 'exponential')
        retry_on: List of error types to retry on (default: ['http_429', 'http_5xx', 'timeout', 'network_error'])
    """
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    retry_on: list[str] = field(default_factory=lambda: ['http_429', 'http_5xx', 'timeout', 'network_error'])
```

**Configuration Parameters**:
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_attempts` | 3 | Maximum retry attempts before giving up |
| `backoff` | `'exponential'` | Backoff strategy |
| `retry_on` | `['http_429', 'http_5xx', 'timeout', 'network_error']` | Error types triggering retry |

**Alignment with V1**:
- ✅ Same max_attempts (3)
- ✅ Same retryable error types (429, 5xx, timeout, network)
- ⚠️ Different backoff formula (V2: `2^attempt`, V1: `base_delay * 2^attempt`)

---

### 2.5 ExecutionEngine Error Handling

**Status**: ⚠️ Partial (simplified inline implementation)

**What's Coded**:
- Inline retry loop in `_execute_item()`
- Simplified error classification
- Error result creation on failure

**Implementation Details**:
```python
def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
    attempt_count = 0
    last_error_type: str | None = None
    last_error_message: str | None = None

    # Retry loop
    max_attempts = run.retry_policy.max_attempts

    for attempt in range(1, max_attempts + 1):
        attempt_count = attempt

        try:
            # Call API
            response = self._call_api_sync(...)

            # Success!
            return ExecutionResult(
                item_id=item.item_id,
                status="success",
                response_text=response_text,
                selected_answer=parsed.answer,
                parse_confidence=parsed.confidence,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error_type=None,
                error_message=None,
                attempt_count=attempt_count,
            )

        except Exception as e:
            # Record error
            last_error_type = self._classify_error(e)
            last_error_message = str(e)

            # Continue to next attempt
            if attempt < max_attempts:
                continue

    # All attempts failed
    return ExecutionResult(
        item_id=item.item_id,
        status="failure",
        response_text=None,
        selected_answer=None,
        parse_confidence=None,
        latency_ms=None,
        input_tokens=None,
        output_tokens=None,
        error_type=last_error_type,
        error_message=last_error_message,
        attempt_count=attempt_count,
    )

def _classify_error(self, error: Exception) -> str:
    """Classify an error type (simplified)."""
    error_str = str(error).lower()

    if "timeout" in error_str:
        return "timeout"
    if "429" in error_str or "rate limit" in error_str:
        return "http_429"
    if "500" in error_str or "502" in error_str or "503" in error_str:
        return "http_5xx"
    if "connection" in error_str or "network" in error_str:
        return "network_error"
    if "authentication" in error_str or "401" in error_str:
        return "authentication_error"
    if "parse" in error_str:
        return "parse_error"

    return "api_error"
```

**Gaps**:
- ❌ Does NOT use `RetryHandler` from `src/api/retry.py`
- ❌ Does NOT use `ErrorClassifier` from `src/api/errors.py`
- ❌ Simplified error classification (string matching vs. proper classification)
- ❌ No delay between retries (missing backoff!)
- ❌ No logging of retry attempts

---

### 2.6 ResultWriter Error Persistence

**Status**: ✅ Implemented (aligned with contract)

**What's Coded**:
- Persists failed `ExecutionResult` to `errors` table
- Writes error fields: `error_type`, `error_message`, `attempt_count`
- Updates run status based on error outcomes

**Implementation Details**:
```python
def write_results(self, results: list[ExecutionResult]) -> WriteReport:
    report = WriteReport()

    for result in results:
        if result.status == 'success':
            written = self._write_response(result)
            if written:
                report.responses_written += 1
            else:
                report.responses_skipped += 1
        else:  # failure
            self._write_error(result)
            report.errors_written += 1

    # Update run statuses
    for run_id, run_results in results_by_run.items():
        status = self._determine_run_status(run_results)
        self._update_run_status(run_id, status)
        report.runs_updated.append((run_id, status))

    return report

def _write_error(self, result: ExecutionResult) -> None:
    cursor = self.db_connection.cursor()

    # Get model_id from variant
    model_id = self._get_model_id_from_variant(result.variant_id)

    # Generate error_id
    error_id = self._generate_error_id(
        result.run_id,
        result.variant_id,
        result.snapshot_id,
    )

    cursor.execute("""
        INSERT INTO errors (
            error_id, run_id, variant_id, snapshot_id,
            model_id, question_id, error_type, error_message, attempt_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        error_id,
        result.run_id,
        result.variant_id,
        result.snapshot_id,
        model_id,
        result.question_id,
        result.error_type,
        result.error_message,
        result.attempt_count,
    ))

    self.db_connection.commit()
```

**Contract Alignment**:
- ✅ Writes failed results to `errors` table
- ✅ Includes `attempt_count` for retry visibility
- ✅ Updates run status after all writes
- ✅ NO execution (only receives results)

**Gaps**:
- ❌ No error_details field (V1 had `error_details` JSON column)
- ❌ No stack_trace capture
- ❌ No error category classification

---

### 2.7 ErrorCollector

**Status**: ❌ MISSING

**V1 Behavior** (for reference):
- In-memory error aggregation
- Error categorization by type and category
- Error summary generation
- Stack trace capture

**V2 Status**:
- ❌ No ErrorCollector module
- ❌ No error aggregation
- ❌ No error summary generation

**Impact**:
- No high-level error visibility
- No error pattern analysis
- No error reporting

---

### 2.8 Logging Integration

**Status**: ❌ MISSING (Critical Gap)

**V1 Logging** (for reference):
- Comprehensive logging throughout all components
- Retry attempts logged with delay and error message
- Errors logged with full context
- Progress tracking during execution

**V2 Logging**:
- ❌ No logging in `ExecutionEngine._execute_item()`
- ❌ No logging in `RetryHandler.execute_with_retry()`
- ❌ No logging in `OpenRouterClient.chat_completion()`
- ❌ No logging in `ResultWriter.write_results()`

**Impact**:
- No visibility into retry behavior
- No debugging capability for failures
- No audit trail
- No error diagnostics

---

## 3. Error Propagation Path

### 3.1 Current Flow

```
OpenRouterClient.chat_completion()
    ↓ (raises APIError via ErrorClassifier)
ExecutionEngine._execute_item()
    ↓ (catches Exception, classifies via _classify_error)
ExecutionResult (status="failure")
    ↓
ResultWriter.write_results()
    ↓
errors table
```

### 3.2 Error Classification at Each Level

**OpenRouterClient**:
```python
except httpx.TimeoutException as e:
    raise ErrorClassifier.classify_timeout(str(e))
except httpx.ConnectError as e:
    raise ErrorClassifier.classify_network(str(e))
except httpx.RequestError as e:
    raise NetworkError(str(e))

def _handle_http_error(self, response: httpx.Response) -> None:
    error = ErrorClassifier.classify_http(response.status_code, error_message)
    raise error
```

**ExecutionEngine**:
```python
except Exception as e:
    last_error_type = self._classify_error(e)  # Simplified string matching
    last_error_message = str(e)
```

**ResultWriter**:
```python
# No classification - just persists what ExecutionResult provides
self._write_error(result)
```

---

## 4. Differences from V1

### 4.1 Architectural Changes

| Aspect | V1 | V2 |
|--------|----|----|
| **RetryHandler** | Used by ExecutionEngine | NOT used (inline retry) |
| **ErrorClassifier** | Used throughout | Only used by OpenRouterClient |
| **ErrorCollector** | Implemented | MISSING |
| **Logging** | Comprehensive | MISSING |
| **Backoff Formula** | `base_delay * 2^attempt` | `2^attempt` (no base_delay) |
| **Error Persistence** | errors table + error_details | errors table only |
| **Retry Delay** | Implemented with asyncio.sleep | MISSING in ExecutionEngine |

### 4.2 Design Philosophy

**V1**:
- Comprehensive error tracking
- Logging at every step
- Centralized error classification

**V2**:
- Clean error class hierarchy
- Policy-driven retry (on paper)
- Simplified inline implementation

### 4.3 Implementation Approach

**V1**:
- Async-first with RetryHandler decorator
- ErrorCollector for aggregation
- Rotating file handler for logs

**V2**:
- Sync wrapper for async API calls
- No error aggregation
- No logging

---

## 5. Known Gaps

### 5.1 Critical Gaps (HIGH Priority)

1. **Logging System MISSING**
   - No visibility into retry behavior
   - No debugging capability
   - **Impact**: BLOCKER for production use

2. **RetryHandler NOT Integrated**
   - ExecutionEngine has inline retry instead
   - No delay between retries (missing backoff!)
   - **Impact**: API abuse, ineffective retry

3. **ErrorClassifier NOT Used**
   - ExecutionEngine has simplified string matching
   - **Impact**: Imprecise error classification

### 5.2 Moderate Gaps (MEDIUM Priority)

4. **ErrorCollector MISSING**
   - No error aggregation
   - No error summary generation
   - **Impact**: Hard to analyze error patterns

5. **Backoff Formula Regression**
   - V2: `2^attempt` (2s, 4s, 8s)
   - V1: `1.0 * 2^attempt` (1s, 2s, 4s)
   - **Impact**: Longer delays than intended

6. **No Stack Trace Capture**
   - V1 captured stack traces in ErrorCollector
   - V2 only stores error_message
   - **Impact**: Harder to debug complex failures

### 5.3 Minor Gaps (LOW Priority)

7. **No error_details Field**
   - V1 had JSON error_details column
   - V2 only has error_type and error_message
   - **Impact**: Less context for debugging

8. **No Error Category Enum**
   - V1 had ErrorCategory enum
   - V2 only has error_type strings
   - **Impact**: Harder to group errors

---

## 6. Summary

### 6.1 V2 Current State Summary

**Implemented** (✅):
- ErrorClassifier (standalone, not integrated)
- APIError hierarchy (authentication, rate_limit, server_error, etc.)
- RetryHandler (standalone, not integrated)
- RetryPolicy (per-run configuration)
- ResultWriter error persistence
- Run status updates based on errors

**Partial** (⚠️):
- ExecutionEngine error handling (inline retry, no backoff, no logging)
- Error classification (simplified string matching)

**Missing** (❌):
- Logging System (CRITICAL)
- ErrorCollector
- RetryHandler integration
- ErrorClassifier integration in ExecutionEngine
- Stack trace capture
- Error details JSON field

### 6.2 Architectural Alignment

V2 is **partially aligned** with TO-BE architecture principles:
- ✅ Explicit error types (APIError hierarchy)
- ✅ Policy-driven retry (RetryPolicy dataclass)
- ✅ Error propagation (ExecutionEngine → ResultWriter → Database)
- ❌ Error transparency (logging MISSING)
- ❌ Retry execution (backoff MISSING in ExecutionEngine)

**Gaps are implementation details**, but some are critical (logging, backoff).

### 6.3 Next Steps

1. **Add Logging** (CRITICAL) — Instrument all components with retry and error logging
2. **Integrate RetryHandler** — Replace inline retry in ExecutionEngine
3. **Add Backoff Delay** — Critical for effective retry behavior
4. **Integrate ErrorClassifier** — Use in ExecutionEngine._classify_error()
5. **Add ErrorCollector** — Optional but useful for error analysis
6. **Add Stack Trace Capture** — For complex debugging scenarios

This document captures the current state of V2 error handling without proposing fixes (that's the Gap Report's job).
