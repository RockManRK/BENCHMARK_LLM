# Error Handling — Architecture & Contracts

**Document Type:** Architecture Specification (TO-BE)
**Domain:** Error Handling
**Purpose:** Define target architecture, contracts, and design principles for error handling

---

## 1. Error Handling Philosophy

### 1.1 Core Principles

1. **Explicit Error Types**: Every error has a machine-readable type for programmatic handling
2. **Retryable vs. Fatal**: Clear separation between transient (retryable) and permanent (fatal) errors
3. **Policy-Driven Retry**: Retry behavior is configured via policy, not hardcoded
4. **Exponential Backoff**: Progressive delays between retry attempts to avoid API abuse
5. **Error Transparency**: All errors are logged, classified, and persisted for debugging
6. **No Silent Failures**: Every error is captured with full context and propagated appropriately
7. **Idempotent Error Persistence**: Duplicate errors are skipped, not overwritten

### 1.2 Design Goals

- **Reliability**: Handle transient failures gracefully without user intervention
- **Observability**: Provide full visibility into error patterns and retry behavior
- **Efficiency**: Avoid API abuse through intelligent backoff strategies
- **Debuggability**: Capture sufficient context for root cause analysis
- **Consistency**: Uniform error handling across all components

---

## 2. Error Type Contract

### 2.1 Error Class Hierarchy

```
APIError (base)
├── AuthenticationError (401, 403)
├── RateLimitError (429)
├── ServerError (5xx)
├── ClientError (4xx, non-auth)
├── TimeoutError
└── NetworkError
```

### 2.2 Base Error Class

```python
class APIError(Exception):
    """Base API error.

    All API-related errors inherit from this base class.
    Each error has a type for programmatic handling.

    Attributes:
        message: Human-readable error message
        error_type: Machine-readable error type identifier
        raw_error: Optional raw error data from provider
    """

    def __init__(
        self,
        message: str,
        error_type: str,
        raw_error: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.raw_error = raw_error
```

### 2.3 Error Type Values

| Error Type | HTTP Status | Exception Types | Retryable |
|------------|-------------|-----------------|-----------|
| `authentication` | 401, 403 | — | ❌ No |
| `http_429` | 429 | — | ✅ Yes |
| `http_5xx` | 500-599 | — | ✅ Yes |
| `http_4xx` | 400-499 (non-auth) | — | ❌ No |
| `timeout` | — | `httpx.TimeoutException` | ✅ Yes |
| `network_error` | — | `httpx.ConnectError`, `httpx.NetworkError` | ✅ Yes |
| `api_error` | — | Other API errors | Context-dependent |

### 2.4 Error Type Contract

**Requirements**:
1. Every error MUST have an `error_type` string field
2. Error types MUST be deterministic (same input → same type)
3. Error types MUST be machine-readable (snake_case, no spaces)
4. Error types MUST map to retry behavior (retryable or fatal)

**Example**:
```python
try:
    response = await client.chat_completion(...)
except APIError as e:
    if e.error_type in ('http_429', 'http_5xx', 'timeout', 'network_error'):
        # Retryable
        await retry_handler.retry()
    else:
        # Fatal - re-raise immediately
        raise
```

---

## 3. Retry Contract

### 3.1 RetryPolicy Dataclass

```python
@dataclass(frozen=True)
class RetryPolicy:
    """Policy for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (default 3)
        backoff: Backoff strategy: 'exponential', 'linear', 'constant'
        base_delay: Base delay in seconds for exponential backoff (default 1.0)
        max_delay: Maximum delay cap in seconds (default 60.0)
        retry_on: List of error types to retry on
    """
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    base_delay: float = 1.0
    max_delay: float = 60.0
    retry_on: list[str] = field(
        default_factory=lambda: ['http_429', 'http_5xx', 'timeout', 'network_error']
    )
```

### 3.2 Retry Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_attempts` | `int` | 3 | Maximum retry attempts before giving up |
| `backoff` | `str` | `'exponential'` | Backoff strategy |
| `base_delay` | `float` | 1.0 | Initial delay for exponential backoff |
| `max_delay` | `float` | 60.0 | Maximum delay cap between retries |
| `retry_on` | `list[str]` | `['http_429', 'http_5xx', 'timeout', 'network_error']` | Error types triggering retry |

### 3.3 Backoff Formula Contract

**Exponential Backoff**:
```python
def calculate_delay(self, attempt: int) -> float:
    """Calculate delay for a given retry attempt.

    Args:
        attempt: Current attempt number (1-indexed)

    Returns:
        Delay in seconds

    Formula:
        delay = base_delay * (exponential_base ^ (attempt - 1))
        delay = min(delay, max_delay)

    Example (base_delay=1.0, exponential_base=2.0, max_delay=60.0):
        Attempt 1: 1.0s  (1.0 * 2^0)
        Attempt 2: 2.0s  (1.0 * 2^1)
        Attempt 3: 4.0s  (1.0 * 2^2)
        Attempt 4: 8.0s  (1.0 * 2^3)
        Attempt 5: 16.0s (1.0 * 2^4)
        Attempt 6+: 60.0s (capped at max_delay)
    """
    if self.backoff == 'exponential':
        delay = self.base_delay * (2.0 ** (attempt - 1))
        return min(delay, self.max_delay)

    if self.backoff == 'linear':
        delay = self.base_delay * attempt
        return min(delay, self.max_delay)

    # constant
    return self.base_delay
```

**Backoff Strategies**:
| Strategy | Formula | Example (attempts 1-4, base_delay=1.0) |
|----------|---------|----------------------------------------|
| `exponential` | `base_delay * 2^(attempt-1)` | 1s, 2s, 4s, 8s |
| `linear` | `base_delay * attempt` | 1s, 2s, 3s, 4s |
| `constant` | `base_delay` | 1s, 1s, 1s, 1s |

### 3.4 Retry Decision Contract

```python
def is_retryable(self, error: APIError) -> bool:
    """Check if error is retryable based on policy.

    Args:
        error: API error to check

    Returns:
        True if error.error_type is in policy.retry_on
    """
    return error.error_type in self.retry_on
```

**Retryable Error Types** (default):
- `http_429` (rate limit)
- `http_5xx` (server errors)
- `timeout` (request timeout)
- `network_error` (connectivity failures)

**Fatal Error Types** (non-retryable):
- `authentication` (401, 403)
- `http_4xx` (client errors, non-auth)
- Programming errors (`ValueError`, `TypeError`, `KeyError`)

### 3.5 Retry Execution Contract

```python
async def execute_with_retry(
    self,
    func: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute function with retry policy.

    Args:
        func: Async function to execute
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Function result

    Raises:
        Last exception if all attempts fail
        Exception immediately if error is not retryable

    Flow:
        1. For attempt in 1..max_attempts:
           a. Execute func(*args, **kwargs)
           b. If success → return result
           c. If APIError:
              - If not retryable → raise immediately
              - If retryable and attempts remaining → wait and retry
              - If retryable and no attempts remaining → raise RetryError
           d. If other Exception:
              - If attempts remaining → wait and retry
              - If no attempts remaining → raise
        2. If loop completes without result → raise RetryError
    """
    last_exception: Exception | None = None

    for attempt in range(1, self.max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except APIError as e:
            last_exception = e

            # Check if retryable
            if not self.is_retryable(e):
                raise

            # Check if more attempts available
            if attempt >= self.max_attempts:
                break

            # Wait before retry
            delay = self.calculate_delay(attempt)
            await asyncio.sleep(delay)

        except Exception as e:
            # Non-APIError exceptions
            last_exception = e

            # Check if more attempts available
            if attempt >= self.max_attempts:
                break

            # Wait before retry (use default delay for unknown errors)
            delay = self.calculate_delay(attempt)
            await asyncio.sleep(delay)

    # All attempts exhausted
    if last_exception is not None:
        raise last_exception

    raise RuntimeError("Retry loop completed without result or exception")
```

---

## 4. Classification Contract

### 4.1 ErrorClassifier Interface

```python
class ErrorClassifier:
    """Classifies HTTP errors into domain error types.

    This class provides static methods to classify errors based on
    HTTP status codes and error conditions. The classifier is
    deterministic - no heuristics, no inference.
    """

    @staticmethod
    def classify_http(status_code: int, response_text: str) -> APIError:
        """Classify HTTP error by status code.

        Args:
            status_code: HTTP status code
            response_text: Response body text

        Returns:
            Specific APIError subclass

        Classification Rules:
            - 429 → RateLimitError (error_type='http_429')
            - 500-599 → ServerError (error_type='http_5xx')
            - 401, 403 → AuthenticationError (error_type='authentication')
            - 400-499 (other) → ClientError (error_type='http_4xx')
            - Other → APIError (error_type=f'http_{status_code}')
        """
        message = f"HTTP {status_code}: {response_text}"

        if status_code == 429:
            return RateLimitError(message)

        if 500 <= status_code < 600:
            return ServerError(message)

        if status_code in (401, 403):
            return AuthenticationError(message)

        if 400 <= status_code < 500:
            return ClientError(message)

        # Fallback for unexpected status codes
        return APIError(message, error_type=f"http_{status_code}")

    @staticmethod
    def classify_timeout(message: str = "Request timed out") -> TimeoutError:
        """Classify timeout error.

        Args:
            message: Error message

        Returns:
            TimeoutError instance
        """
        return TimeoutError(message)

    @staticmethod
    def classify_network(message: str = "Network error") -> NetworkError:
        """Classify network error.

        Args:
            message: Error message

        Returns:
            NetworkError instance
        """
        return NetworkError(message)
```

### 4.2 Classification Rules

**HTTP Status Code Classification**:
```
IF status_code == 429:
    RETURN RateLimitError(error_type='http_429')

ELSE IF 500 <= status_code < 600:
    RETURN ServerError(error_type='http_5xx')

ELSE IF status_code IN (401, 403):
    RETURN AuthenticationError(error_type='authentication')

ELSE IF 400 <= status_code < 500:
    RETURN ClientError(error_type='http_4xx')

ELSE:
    RETURN APIError(error_type=f'http_{status_code}')
```

**Exception Type Classification**:
```
IF exception is httpx.TimeoutException:
    RETURN TimeoutError(error_type='timeout')

ELSE IF exception is httpx.ConnectError:
    RETURN NetworkError(error_type='network_error')

ELSE IF exception is httpx.NetworkError:
    RETURN NetworkError(error_type='network_error')

ELSE IF exception is httpx.HTTPStatusError:
    RETURN ErrorClassifier.classify_http(exception.response.status_code, ...)

ELSE:
    RETURN APIError(error_type=type(exception).__name__.lower())
```

---

## 5. Propagation Contract

### 5.1 Error Propagation Path

```
OpenRouterClient.chat_completion()
    ↓ (raises APIError via ErrorClassifier)
RetryHandler.execute_with_retry()
    ↓ (retries or raises)
ExecutionEngine._execute_item()
    ↓ (catches Exception, creates ExecutionResult)
ExecutionResult (status="failure" with error details)
    ↓
ResultWriter.write_results()
    ↓ (writes to errors table)
Database (errors table)
```

### 5.2 Component Responsibilities

**OpenRouterClient**:
- Translate HTTP errors to `APIError` subclasses
- Use `ErrorClassifier` for deterministic classification
- Include raw error data when available

```python
def _handle_http_error(self, response: httpx.Response) -> None:
    try:
        error_data = response.json()
        error_message = error_data.get("error", {}).get("message", str(response))
    except Exception:
        error_message = response.text or f"HTTP {response.status_code}"

    error = ErrorClassifier.classify_http(response.status_code, error_message)
    raise error
```

**RetryHandler**:
- Execute retry policy
- Delay between retries via `asyncio.sleep(delay)`
- Raise immediately for non-retryable errors
- Raise `RetryError` when all attempts exhausted

**ExecutionEngine**:
- Catch exceptions from API calls
- Classify error type (via `ErrorClassifier` or `_classify_error()`)
- Create `ExecutionResult` with `status="failure"`
- Include error details: `error_type`, `error_message`, `attempt_count`

```python
def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
    attempt_count = 0
    last_error_type: str | None = None
    last_error_message: str | None = None

    max_attempts = run.retry_policy.max_attempts

    for attempt in range(1, max_attempts + 1):
        attempt_count = attempt

        try:
            response = self._call_api_sync(...)
            # Success - return ExecutionResult with status="success"
            return ExecutionResult(...)

        except Exception as e:
            last_error_type = self._classify_error(e)
            last_error_message = str(e)

            # Continue to next attempt (RetryHandler handles delay)
            if attempt < max_attempts:
                continue

    # All attempts failed - return ExecutionResult with status="failure"
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
```

**ResultWriter**:
- Persist failed results to `errors` table
- Include error fields: `error_type`, `error_message`, `attempt_count`
- Update run status based on error outcomes

---

## 6. Persistence Contract

### 6.1 Errors Table Schema

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

-- Index for error analysis
CREATE INDEX idx_errors_run_id ON errors(run_id);
CREATE INDEX idx_errors_error_type ON errors(error_type);
```

### 6.2 Error ID Generation

```python
def _generate_error_id(
    self,
    run_id: str,
    variant_id: str,
    snapshot_id: str,
) -> str:
    """Generate deterministic error ID from item components.

    Args:
        run_id: Run identifier
        variant_id: Variant identifier
        snapshot_id: Snapshot identifier

    Returns:
        Error ID in format 'err-{run_id}-{variant_id}-{snapshot_id}'
    """
    return f"err-{run_id}-{variant_id}-{snapshot_id}"
```

### 6.3 Error Persistence Contract

**What Gets Saved**:
- `error_id`: Deterministic ID from run_id, variant_id, snapshot_id
- `run_id`: Parent run identifier
- `variant_id`: Model variant identifier
- `snapshot_id`: Question snapshot identifier
- `model_id`: Model identifier (looked up from variant)
- `question_id`: Original question identifier
- `error_type`: Classified error type (e.g., `http_429`, `timeout`)
- `error_message`: Human-readable error message
- `attempt_count`: Number of retry attempts made

**What Does NOT Get Saved**:
- Stack traces (too large, optional enhancement)
- Raw error response (optional enhancement via `error_details` JSON)
- Error context (optional enhancement)

### 6.4 Idempotency Contract

**Uniqueness Constraint**:
```sql
-- Error IDs are deterministic, ensuring uniqueness
-- Duplicate inserts should be skipped (not overwritten)
```

**Idempotency Rule**:
- Same `(run_id, variant_id, snapshot_id)` → same `error_id`
- Duplicate error inserts are skipped (INSERT OR IGNORE)
- Error data is NOT overwritten (append-only for audit)

---

## 7. Run Status Contract

### 7.1 Status Calculation

```python
def _determine_run_status(
    self,
    results: list[ExecutionResult],
) -> Literal['completed', 'failed', 'partial_failed']:
    """Determine run status based on results.

    Rules:
    - All success → 'completed'
    - All failure → 'failed'
    - Mixed → 'partial_failed'

    Args:
        results: List of ExecutionResult for a single run

    Returns:
        Run status string
    """
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

| Status | Condition | Description |
|--------|-----------|-------------|
| `completed` | 0 failures | All items succeeded |
| `failed` | 0 successes | All items failed |
| `partial_failed` | Mixed | Some succeeded, some failed |

### 7.3 Status Update Contract

**When to Update**:
- After all results are persisted
- Only if run is not already in terminal state

**Terminal States**:
- `completed` (cannot transition)
- `failed` (cannot transition)

**Non-Terminal States**:
- `pending` (can transition to any state)
- `running` (can transition to any state)
- `partial_failed` (can transition to `completed` or `failed`)

---

## 8. Logging Contract

### 8.1 Required Log Points

**RetryHandler**:
```python
# On retry attempt
logger.info(
    f"Retry attempt {attempt}/{policy.max_attempts} "
    f"after {delay:.2f}s delay due to: {error_message}"
)

# On retry success
logger.info(f"Operation succeeded after {attempt_count} retry attempt(s)")

# On max retries exceeded
logger.error(f"Max retries ({policy.max_attempts}) exceeded: {error_message}")
```

**ExecutionEngine**:
```python
# On item execution failure
logger.exception(f"Failed to execute item {item.item_id}: {error_message}")

# On item execution success (after retries)
logger.info(
    f"Item {item.item_id} completed after {attempt_count} attempts: "
    f"error_type={error_type}"
)
```

**OpenRouterClient**:
```python
# On HTTP error
logger.warning(
    f"HTTP {response.status_code} for model {model_id}: {error_message}"
)

# On timeout
logger.warning(f"Request timeout for model {model_id}: {error_message}")

# On network error
logger.error(f"Network error for model {model_id}: {error_message}")
```

### 8.2 Log Levels

| Level | Usage |
|-------|-------|
| `DEBUG` | Detailed retry behavior (delay calculation, attempt count) |
| `INFO` | Retry success, execution progress |
| `WARNING` | Retryable errors, HTTP 429/5xx |
| `ERROR` | Max retries exceeded, fatal errors, network failures |
| `CRITICAL` | System-level failures (database, configuration) |

### 8.3 Log Context

All error logs MUST include:
- `run_id`: Run identifier
- `item_id` or `question_id`: Item being executed
- `model_id`: Model being called
- `error_type`: Classified error type
- `attempt_count`: Retry attempt number (if applicable)

---

## 9. Critical Defaults

### 9.1 Retry Defaults

```python
max_attempts: int = 3
base_delay: float = 1.0
max_delay: float = 60.0
backoff: str = 'exponential'
retry_on: list[str] = ['http_429', 'http_5xx', 'timeout', 'network_error']
```

### 9.2 Error Type Mapping

| HTTP Status | Error Type | Retryable |
|-------------|------------|-----------|
| 429 | `http_429` | ✅ Yes |
| 500 | `http_5xx` | ✅ Yes |
| 502 | `http_5xx` | ✅ Yes |
| 503 | `http_5xx` | ✅ Yes |
| 504 | `http_5xx` | ✅ Yes |
| 400 | `http_4xx` | ❌ No |
| 401 | `authentication` | ❌ No |
| 403 | `authentication` | ❌ No |
| 404 | `http_4xx` | ❌ No |

### 9.3 Backoff Sequence

With defaults (`base_delay=1.0`, `max_delay=60.0`, `exponential`):
- Attempt 1: 1.0s
- Attempt 2: 2.0s
- Attempt 3: 4.0s
- Attempt 4: 8.0s
- Attempt 5: 16.0s
- Attempt 6: 32.0s
- Attempt 7+: 60.0s (capped)

---

## 10. Summary

The TO-BE Error Handling architecture is built around these foundational contracts:

1. **Error Type Contract**: Every error has a machine-readable `error_type` field for programmatic handling

2. **Retry Contract**: Policy-driven retry with configurable `max_attempts`, `backoff`, `base_delay`, `max_delay`

3. **Backoff Formula Contract**: Deterministic delay calculation with exponential, linear, or constant strategies

4. **Classification Contract**: Deterministic error classification via `ErrorClassifier` static methods

5. **Propagation Contract**: Clear error flow from API Client → RetryHandler → ExecutionEngine → ResultWriter → Database

6. **Persistence Contract**: Idempotent error persistence with deterministic error IDs

7. **Run Status Contract**: Accurate run status calculation based on success/failure outcomes

8. **Logging Contract**: Comprehensive logging at all error handling points with structured context

These contracts ensure reliable, observable, and debuggable error handling throughout the system.
