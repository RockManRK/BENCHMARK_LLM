# Error Handling — V1 Legacy Analysis

**Document Type:** Legacy Analysis (Read-Only)
**Domain:** Error Handling
**Source:** `src_legacy/` directory
**Purpose:** Extract error handling patterns from V1 implementation for historical reference

---

## 1. Domain Overview

### 1.1 Purpose

The Error Handling domain is responsible for classifying, retrying, and propagating errors throughout the system. It ensures transient failures are handled gracefully while fatal errors are surfaced immediately for debugging.

### 1.2 Core Responsibilities

- **Error Classification**: Distinguish retryable (transient) vs. fatal (non-retryable) errors
- **Retry Logic**: Implement exponential backoff for transient failures
- **Error Propagation**: Flow errors through ExecutionEngine → ResultWriter → Database
- **Error Persistence**: Store error details in `errors` table for audit and analysis
- **Error Collection**: Aggregate and summarize errors for reporting

### 1.3 Design Principles

1. **Explicit Error Types**: Each error has a clear type for programmatic handling
2. **Retryable vs. Fatal**: Clear separation between transient and permanent failures
3. **Exponential Backoff**: Progressive delay between retry attempts
4. **Error Transparency**: All errors are logged and persisted for debugging
5. **No Silent Failures**: Every error is captured, classified, and reported

---

## 2. Error Classification

### 2.1 Error Type Hierarchy

V1 used a flat error classification system based on HTTP status codes and exception types:

| Error Type | HTTP Status | Exception Types | Retryable |
|------------|-------------|-----------------|-----------|
| `rate_limit` | 429 | — | ✅ Yes |
| `server_error` | 500 | — | ✅ Yes |
| `bad_gateway` | 502 | — | ✅ Yes |
| `service_unavailable` | 503 | — | ✅ Yes |
| `gateway_timeout` | 504 | — | ✅ Yes |
| `timeout` | — | `httpx.TimeoutException` | ✅ Yes |
| `network_error` | — | `httpx.ConnectError`, `httpx.NetworkError` | ✅ Yes |
| `bad_request` | 400 | — | ❌ No |
| `authentication` | 401 | — | ❌ No |
| `forbidden` | 403 | — | ❌ No |
| `not_found` | 404 | — | ❌ No |
| `provider_error` | 200 (with error in body) | — | ❌ No |
| `validation` | — | `ValueError`, `TypeError`, `KeyError` | ❌ No |
| `parse_error` | — | Parser exceptions | ❌ No |

### 2.2 Error Classification Logic

**`ErrorClassifier.classify_http(status_code, response_text)`**:

```python
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
```

**`ErrorCategory.from_exception_type(exception)`** (ErrorCollector):

```python
if isinstance(exception, httpx.HTTPStatusError):
    status_code = exception.response.status_code
    if status_code == 429:
        return ErrorCategory.RATE_LIMIT
    elif status_code in (401, 403):
        return ErrorCategory.AUTHENTICATION
    elif status_code >= 500:
        return ErrorCategory.API

if isinstance(exception, httpx.TimeoutException):
    return ErrorCategory.TIMEOUT

if isinstance(exception, httpx.ConnectError):
    return ErrorCategory.NETWORK

if exception_type in ("ValueError", "TypeError", "KeyError"):
    return ErrorCategory.VALIDATION
```

### 2.3 ErrorCategory Enum

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

---

## 3. Retry Configuration

### 3.1 RetryConfig Dataclass

```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_status_codes: list[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )
```

### 3.2 Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 3 | Maximum retry attempts before giving up |
| `base_delay` | 1.0s | Initial delay for exponential backoff |
| `max_delay` | 60.0s | Maximum delay cap between retries |
| `exponential_base` | 2.0 | Base for exponential calculation |
| `retryable_status_codes` | [429, 500, 502, 503, 504] | HTTP codes triggering retry |

### 3.3 Backoff Formula

```python
def _calculate_delay(self, attempt: int) -> float:
    delay = self.config.base_delay * (self.config.exponential_base ** attempt)
    return min(delay, self.config.max_delay)
```

**Delay Sequence** (with defaults):
- Attempt 0: 1.0s (1.0 × 2^0)
- Attempt 1: 2.0s (1.0 × 2^1)
- Attempt 2: 4.0s (1.0 × 2^2)
- Attempt 3: 8.0s (1.0 × 2^3)
- Attempt 4: 16.0s (1.0 × 2^4)
- Attempt 5+: 60.0s (capped at max_delay)

### 3.4 Retry Decision Logic

**`RetryHandler._is_retryable_exception(exc)`**:

```python
def _is_retryable_exception(self, exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.ConnectError):
        return True
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in self.config.retryable_status_codes
    return False
```

**Retry Flow**:
```
1. Execute API call
2. If exception raised:
   a. Check if exception is retryable type
   b. If NOT retryable → raise immediately
   c. If retryable and attempts < max_retries → wait and retry
   d. If retryable and attempts >= max_retries → raise RetryError
```

---

## 4. Retry Execution Flow

### 4.1 RetryHandler.execute()

```python
async def execute(
    self,
    func: Callable[P, Coroutine[Any, Any, T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T:
    last_exception: Exception | None = None

    for attempt in range(self.config.max_retries + 1):
        try:
            result = await func(*args, **kwargs)

            if attempt > 0:
                logger.info(f"Operation succeeded after {attempt} retry attempt(s)")

            return result

        except Exception as exc:
            last_exception = exc

            if not self._is_retryable_exception(exc):
                logger.warning(f"Non-retryable error: {exc}")
                raise

            if attempt >= self.config.max_retries:
                logger.error(f"Max retries ({self.config.max_retries}) exceeded")
                raise RetryError(
                    f"Max retries exceeded after {self.config.max_retries} attempts",
                    last_exception=exc
                ) from exc

            delay = self._calculate_delay(attempt)
            logger.info(
                f"Retry attempt {attempt + 1}/{self.config.max_retries} "
                f"after {delay:.2f}s delay due to: {exc}"
            )

            await asyncio.sleep(delay)

    raise RetryError(
        "Unexpected retry loop completion",
        last_exception=last_exception
    )
```

### 4.2 RetryError

```python
class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception | None = None) -> None:
        super().__init__(message)
        self.last_exception = last_exception
```

### 4.3 Logging During Retry

Each retry attempt is logged:
```
INFO - Retry attempt 1/3 after 1.00s delay due to: HTTP 503 Service Unavailable
INFO - Retry attempt 2/3 after 2.00s delay due to: HTTP 503 Service Unavailable
INFO - Operation succeeded after 2 retry attempt(s)
```

Or on failure:
```
ERROR - Max retries (3) exceeded
```

---

## 5. Error Propagation

### 5.1 Propagation Path

```
API Client (OpenRouterClient)
    ↓
RetryHandler (retries transient failures)
    ↓
ExecutionEngine (_execute_item catches exceptions)
    ↓
ExecutionResult (status="failure" with error details)
    ↓
ResultWriter (writes to errors table)
    ↓
Database (errors table)
```

### 5.2 ExecutionEngine Error Handling

**`ExecutionEngine._execute_item()`**:

```python
try:
    # Execute API call
    api_response = await self.api_client.chat_completion(...)

    # Parse response
    parsed = self._parse_api_response(api_response, correct_answer)

    # Build success result
    result = ExecutionResult(
        item_id=item.item_id,
        status="success",
        response_text=parsed.get("response_text", ""),
        selected_answer=parsed.get("selected_answer"),
        is_correct=parsed.get("is_correct"),
        latency_ms=latency_ms,
        input_tokens=tokens.get("input_tokens", 0),
        output_tokens=tokens.get("output_tokens", 0),
        error_type=None,
        error_message=None,
    )

except Exception as e:
    logger.exception(f"Failed to execute item {item.item_id}: {e}")

    # Build error result
    result = ExecutionResult(
        item_id=item.item_id,
        run_id=item.run_id,
        variant_id=item.variant_id,
        model_id=item.model_id,
        snapshot_id=item.snapshot_id,
        question_id=item.question_id,
        iteration_number=item.iteration_number,
        status="failure",
        response_text="",
        selected_answer=None,
        is_correct=None,
        latency_ms=int((time.time() - start_time) * 1000),
        input_tokens=0,
        output_tokens=0,
        error_type=type(e).__name__,
        error_message=str(e),
    )

    return result
```

### 5.3 Error Result Fields

| Field | Value on Failure |
|-------|------------------|
| `status` | `"failure"` |
| `response_text` | `""` (empty string) |
| `selected_answer` | `None` |
| `is_correct` | `None` |
| `error_type` | Exception class name (e.g., `"TimeoutException"`) |
| `error_message` | Exception message string |
| `attempt_count` | Number of retry attempts made |

---

## 6. Error Persistence

### 6.1 ResultWriter Error Handling

**`ResultWriter.write_results()`**:

```python
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
```

**`ResultWriter._write_error()`**:

```python
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

### 6.2 Errors Table Schema

```sql
CREATE TABLE errors (
    error_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    attempt_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id),
    FOREIGN KEY (snapshot_id) REFERENCES question_snapshots(snapshot_id)
);
```

### 6.3 ErrorCollector (Optional Enhanced Tracking)

V1 also had an `ErrorCollector` for in-memory error aggregation:

```python
@dataclass
class ErrorInfo:
    response_id: int
    error_type: str
    error_message: str
    category: ErrorCategory = ErrorCategory.UNKNOWN
    stack_trace: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    context: dict[str, Any] = field(default_factory=dict)
```

**ErrorCollector.get_error_summary()**:
```python
def get_error_summary(self) -> dict[str, Any]:
    by_category: dict[ErrorCategory, int] = {}
    by_type: dict[str, int] = {}

    for error in self.errors:
        # Count by category
        by_category[error.category] = by_category.get(error.category, 0) + 1
        # Count by type
        by_type[error.error_type] = by_type.get(error.error_type, 0) + 1

    return {
        "total_errors": len(self.errors),
        "by_category": by_category,
        "by_type": by_type,
    }
```

---

## 7. Run Status Updates

### 7.1 Status Calculation

**`ResultWriter._determine_run_status()`**:

```python
def _determine_run_status(self, results: list[ExecutionResult]) -> Literal['completed', 'failed', 'partial_failed']:
    if not results:
        return 'completed'

    successes = sum(1 for r in results if r.status == 'success')
    failures = sum(1 for r in results if r.status == 'failure')

    if failures == 0:
        return 'completed'
    elif successes == 0:
        return 'failed'
    else:
        return 'partial_failed'
```

### 7.2 Status Values

| Status | Condition |
|--------|-----------|
| `completed` | All items succeeded (0 failures) |
| `failed` | All items failed (0 successes) |
| `partial_failed` | Mixed results (some success, some failure) |

### 7.3 Status Update Prevention

Run status updates were prevented if the run was already in a terminal state (`completed` or `failed`), ensuring idempotency.

---

## 8. Logging Integration

### 8.1 Logging Configuration

V1 had comprehensive logging via `logging_config.py`:

```python
def setup_logging(config: LoggingConfig) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))
    root_logger.handlers.clear()

    # File handler: Logs EVERYTHING (DEBUG level)
    file_handler = FlushingRotatingFileHandler(
        config.log_file_path,
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
        delay=False,
    )
    file_handler.setLevel(getattr(logging, config.log_level))

    # Console handler: Only shows IMPORTANT messages (INFO level minimum)
    console_handler = FlushingStreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
```

### 8.2 Error Logging

**In RetryHandler**:
```python
logger.warning(f"Non-retryable error: {exc}")
logger.error(f"Max retries ({self.config.max_retries}) exceeded")
logger.info(f"Retry attempt {attempt + 1}/{self.config.max_retries} after {delay:.2f}s delay due to: {exc}")
```

**In ExecutionEngine**:
```python
logger.exception(f"Failed to execute item {item.item_id}: {e}")
```

**In ErrorCollector**:
```python
logger.warning(f"Error captured: {error_type} - {error_message} (response_id={response_id}, category={category.value})")
```

---

## 9. Key Design Decisions

### 9.1 Explicit Error Types

**Decision**: Each error has a machine-readable `error_type` field

**Rationale**:
- Programmatic error handling
- Clear categorization for analysis
- Consistent error reporting

**Implementation**:
- `error_type` field in all error classes
- ErrorClassifier maps HTTP status to error types
- ErrorCategory enum for grouping

---

### 9.2 Retryable vs. Fatal Separation

**Decision**: Clear separation between retryable (transient) and fatal (permanent) errors

**Rationale**:
- Avoid wasting time on unrecoverable errors
- Handle transient failures gracefully
- Fast failure for programming errors

**Implementation**:
- `_is_retryable_exception()` method
- `retryable_status_codes` list
- Immediate raise for non-retryable errors

---

### 9.3 Exponential Backoff

**Decision**: Exponential backoff with cap for retry delays

**Rationale**:
- Give transient issues time to resolve
- Avoid overwhelming the API
- Prevent infinite delays

**Implementation**:
- `delay = base_delay * (exponential_base ^ attempt)`
- `delay = min(delay, max_delay)`
- No jitter (deterministic for reproducibility)

---

### 9.4 Error Transparency

**Decision**: All errors are logged and persisted

**Rationale**:
- Debugging capability
- Audit trail
- Pattern analysis

**Implementation**:
- Comprehensive logging at all levels
- Error persistence in `errors` table
- ErrorCollector for aggregation

---

### 9.5 No Silent Failures

**Decision**: Every error is captured, classified, and reported

**Rationale**:
- No hidden failures
- Clear visibility into execution health
- Actionable error information

**Implementation**:
- ExecutionResult always has status
- Failed results written to errors table
- Run status reflects error outcomes

---

## 10. Critical Defaults

### 10.1 Retry Defaults

```python
max_retries: int = 3
base_delay: float = 1.0
max_delay: float = 60.0
exponential_base: float = 2.0
retryable_status_codes: list[int] = [429, 500, 502, 503, 504]
```

### 10.2 Error Type Mapping

| HTTP Status | Error Type | Retryable |
|-------------|------------|-----------|
| 429 | `rate_limit` | ✅ Yes |
| 500 | `server_error` | ✅ Yes |
| 502 | `bad_gateway` | ✅ Yes |
| 503 | `service_unavailable` | ✅ Yes |
| 504 | `gateway_timeout` | ✅ Yes |
| 400 | `bad_request` | ❌ No |
| 401 | `authentication` | ❌ No |
| 403 | `forbidden` | ❌ No |
| 404 | `not_found` | ❌ No |

### 10.3 Exception Type Mapping

| Exception Type | Error Category | Retryable |
|----------------|----------------|-----------|
| `httpx.TimeoutException` | TIMEOUT | ✅ Yes |
| `httpx.ConnectError` | NETWORK | ✅ Yes |
| `httpx.NetworkError` | NETWORK | ✅ Yes |
| `ValueError` | VALIDATION | ❌ No |
| `TypeError` | VALIDATION | ❌ No |
| `KeyError` | VALIDATION | ❌ No |

---

## 11. Summary

The V1 Error Handling domain was built around these foundational concepts:

1. **Explicit Error Classification** — Each error has a clear type (retryable vs. fatal) based on HTTP status and exception type

2. **Policy-Driven Retry** — RetryConfig controls retry behavior with exponential backoff (1s, 2s, 4s, 8s, capped at 60s)

3. **Comprehensive Error Propagation** — Errors flow through API Client → RetryHandler → ExecutionEngine → ResultWriter → Database

4. **Error Transparency** — All errors are logged, persisted, and aggregated for debugging and analysis

5. **No Silent Failures** — Every error is captured with full context (type, message, stack trace, attempt count)

6. **Run Status Integrity** — Run status accurately reflects error outcomes (completed, failed, partial_failed)

7. **Critical Defaults** — Retry configuration (3 retries, 1s base delay, 60s max delay) controlled correctness

This document captures the architectural essence of V1 error handling without proposing improvements or comparing to V2 implementations.
