# Legacy Execution Core Architecture

**Document Type:** Architectural Extraction (Read-Only)  
**Source:** `src_legacy/` directory  
**Purpose:** Document the essence of the legacy execution system for historical reference

---

## 1. API Client Architecture

### 1.1 Request Construction

The `OpenRouterClient` constructed API requests through the following mechanisms:

**Message Building:**
- `MessageBuilder` class handled message construction
- Two message types supported:
  - Text-only: `build_user_message(content)` returned `{"role": "user", "content": content}`
  - Multimodal: `build_multimodal_message(text, image_path)` encoded images as base64 data URLs
- Image format detection used file suffix mapping (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`)
- System prompts were prepended to messages array as `{"role": "system", "content": system_prompt}`

**Payload Assembly:**
- Base payload always included: `model` and `messages`
- Optional parameters added conditionally (only if not None):
  - `max_tokens`: Maximum completion tokens
  - `temperature`: Sampling temperature
  - `response_format`: JSON schema for structured outputs
  - `reasoning`: Reasoning configuration object
  - `debug`: Debug mode configuration
- All additional kwargs were merged into payload

**Request Configuration:**
- Base URL: `https://openrouter.ai/api/v1` (configurable)
- Default timeout: 180 seconds (3 minutes)
- Authentication: Bearer token via `Authorization` header
- Custom headers: `HTTP-Referer`, `X-Title`, `Content-Type`
- Connection limits: `max_keepalive_connections=0`, `max_connections=10`

### 1.2 Authentication Handling

**Authentication Flow:**
- API key passed to client constructor
- Stored as instance attribute `self.api_key`
- Injected into httpx client initialization headers
- Format: `Authorization: Bearer {api_key}`

**Authentication Errors:**
- HTTP 401 detected and classified as `authentication` error type
- Error message: "Authentication failed: Invalid API key"
- Non-retryable (immediate failure, no retry attempts)
- Logged at ERROR level with model identifier

### 1.3 Response Parsing

**Response Validation:**
- HTTP 200 expected for success
- Non-200 status codes triggered error extraction
- Content-Type checked for JSON parsing eligibility
- Response structure validated for required fields:
  - `choices` array (non-empty)
  - `choices[0].message`
  - `choices[0].message.content`

**Token Usage Extraction:**
- `prompt_tokens`: Input token count
- `completion_tokens`: Output token count (renamed from `output_tokens`)
- `total_tokens`: Sum of prompt and completion tokens
- `cost`: Credit cost from `usage.cost` field
- `completion_tokens_details.reasoning_tokens`: Separate reasoning token count (for reasoning models)
- `effective_tokens`: Calculated as `input_tokens + response_tokens + reasoning_tokens`

**Finish Reason Classification:**
- Success reasons: `stop`, `length`, `eos_token`
- Error reasons: `content_filter`, `function_call`
- Unknown reasons classified as `incomplete` if content empty

**Answer Extraction:**
- `AnswerParser` module used hierarchical pattern matching
- Four confidence levels:
  - `clear`: Single match from explicit/context/structural patterns
  - `ambiguous`: Multiple different letters detected
  - `no_answer`: No patterns matched
  - `low_confidence`: Only fallback pattern matched
- Pattern hierarchy (highest to lowest priority):
  1. Explicit: `resposta: [A-D]`, `answer: [A-D]`, `alternativa correta é [A-D]`
  2. Context: `a resposta é [A-D]`, `the correct answer is [A-D]`, `opção [A-D]`
  3. Structural: `**[A-D]**`, `[A-D]:`, `[A-D])`, `([A-D])`
  4. Fallback: Any isolated `[A-D]` word boundary match
- Article filtering: Portuguese/Spanish article "A" filtered when followed by nouns

**Latency Calculation:**
- Start time captured before API call
- End time captured after response received
- Latency: `(end_time - start_time).total_seconds() * 1000` milliseconds

### 1.4 Error Surfacing

**Error Normalization:**
- `normalize_openrouter_error()` converted API errors to standard format
- Normalized structure:
  - `error_type`: Categorized by HTTP status
  - `http_status`: Original HTTP status code
  - `message`: Human-readable error message
  - `raw_body`: Full response body for debugging

**Error Type Mapping:**
- 400: `bad_request`
- 401: `authentication`
- 403: `forbidden`
- 404: `not_found`
- 429: `rate_limit`
- 500: `server_error`
- 502: `bad_gateway`
- 503: `service_unavailable`
- 504: `gateway_timeout`
- 200 with error in body: `provider_error`

**Error Extraction from Raw Response:**
- `extract_error_from_raw()` handled both wrapped and unwrapped responses
- Debug wrapper format: `{"_debug": {...}, "response": {...}}`
- Checked for `error` field in response data
- Checked for error indicators in message content (e.g., "error", "failed")

**Error Formatting:**
- `format_error_details()` converted error dict to JSON string
- Large `raw_body` truncated for readability (>1000 characters)
- Truncation flagged with `raw_body_truncated: true`

---

## 2. Error Handling Strategy

### 2.1 Expected Error Types

**API Errors:**
- Invalid responses (malformed JSON, missing fields)
- Parsing errors (content extraction failures)
- Provider errors (upstream model failures)

**Network Errors:**
- Connection errors (DNS failures, refused connections)
- Network interruptions during request/response
- Socket timeouts

**Timeout Errors:**
- Request timeout (default 180 seconds)
- Connection timeout
- Read timeout

**Rate Limit Errors:**
- HTTP 429 Too Many Requests
- Quota exceeded errors

**Authentication Errors:**
- HTTP 401 Unauthorized
- HTTP 403 Forbidden
- Invalid or expired API keys

**Validation Errors:**
- Invalid input data (ValueError, TypeError, KeyError)
- Schema validation failures
- Missing required fields

**Database Errors:**
- SQLite operation failures
- Constraint violations
- Connection issues

### 2.2 Retryable vs Fatal Errors

**Retryable Errors:**
- HTTP 429 (rate limit)
- HTTP 500 (server error)
- HTTP 502 (bad gateway)
- HTTP 503 (service unavailable)
- HTTP 504 (gateway timeout)
- `httpx.TimeoutException`
- `httpx.ConnectError`
- `httpx.NetworkError`

**Fatal (Non-Retryable) Errors:**
- HTTP 400 (bad request) - client error, retry won't fix
- HTTP 401 (authentication) - credential issue
- HTTP 403 (forbidden) - permission issue
- HTTP 404 (not found) - resource doesn't exist
- `ValueError`, `TypeError`, `KeyError` - programming errors
- ParseError - response structure invalid
- Any error not in retryable list

**Decision Logic:**
```
_is_retryable_exception(exc):
  - If TimeoutException → retry
  - If ConnectError → retry
  - If NetworkError → retry
  - If HTTPStatusError:
    - Check if status code in retryable_status_codes list
  - Otherwise → do not retry
```

### 2.3 Error Propagation to CLI

**Execution Engine Level:**
- Exceptions caught in `_execute_item()`
- Error converted to `ExecutionResult` with status="failure"
- Error details captured:
  - `error_type`: Exception class name
  - `error_message`: Exception message string
  - `status`: "failure"
  - `selected_answer`: None
  - `is_correct`: None

**Result Writer Level:**
- Failed results written to `errors` table (not `responses`)
- Error object structure:
  - `run_id`, `variant_id`, `question_id`
  - `error_type`: Categorized error type
  - `error_message`: Human-readable message
  - `stack_trace`: Optional stack trace
  - `attempt_count`: Retry attempt count

**Run Status Updates:**
- Run status calculated from result outcomes:
  - `completed`: All items succeeded
  - `partial_failed`: Some succeeded, some failed
  - `failed`: All items failed
- Status update prevented if run already in final state (`completed` or `failed`)

**CLI Output:**
- Progress tracker logged failures
- Error summary generated via `ErrorCollector.get_error_summary()`
- Summary included:
  - Total error count
  - Breakdown by category
  - Breakdown by type

---

## 3. Retry Behavior

### 3.1 Retry Configuration

**RetryConfig Dataclass:**
```
max_retries: int = 3
base_delay: float = 1.0
max_delay: float = 60.0
exponential_base: float = 2.0
retryable_status_codes: list[int] = [429, 500, 502, 503, 504]
```

**Configuration Parameters:**
- `max_retries`: Maximum retry attempts (default 3)
- `base_delay`: Initial delay in seconds (default 1.0)
- `max_delay`: Maximum delay cap in seconds (default 60.0)
- `exponential_base`: Base for exponential calculation (default 2.0)
- `retryable_status_codes`: HTTP codes triggering retry

### 3.2 Retry Trigger Conditions

**When Retries Occurred:**
1. HTTP 429 response received
2. HTTP 5xx response received
3. `httpx.TimeoutException` raised
4. `httpx.ConnectError` raised
5. `httpx.NetworkError` raised

**Retry Decision Flow:**
```
1. Execute API call
2. If exception raised:
   a. Check if exception is retryable type
   b. If not retryable → raise immediately
   c. If retryable and attempts < max_retries → retry
   d. If retryable and attempts >= max_retries → raise RetryError
```

### 3.3 Backoff Strategy

**Exponential Backoff Formula:**
```
delay = base_delay * (exponential_base ^ attempt)
delay = min(delay, max_delay)
```

**Delay Sequence (with defaults):**
- Attempt 0: 1.0 seconds (1.0 * 2^0)
- Attempt 1: 2.0 seconds (1.0 * 2^1)
- Attempt 2: 4.0 seconds (1.0 * 2^2)
- Attempt 3: 8.0 seconds (1.0 * 2^3)
- Attempt 4: 16.0 seconds (1.0 * 2^4)
- Attempt 5+: 60.0 seconds (capped at max_delay)

**Implementation:**
```
_calculate_delay(attempt):
  delay = base_delay * (exponential_base ** attempt)
  return min(delay, max_delay)
```

**No Jitter:**
- Backoff calculation was deterministic (no random jitter)
- Same attempt number always produced same delay

### 3.4 Retry Execution Flow

**RetryHandler.execute():**
```
for attempt in range(max_retries + 1):
  try:
    result = await func(*args, **kwargs)
    if attempt > 0:
      log success after retries
    return result
  except Exception as exc:
    if not _is_retryable_exception(exc):
      log non-retryable error
      raise immediately
    if attempt >= max_retries:
      log max retries exceeded
      raise RetryError
    delay = _calculate_delay(attempt)
    log retry attempt with delay
    await asyncio.sleep(delay)
```

**RetryError:**
- Raised when all retry attempts exhausted
- Message: "Max retries exceeded after {max_retries} attempts"
- `last_exception` attribute preserved for debugging
- Logged at ERROR level

**Logging:**
- Each retry attempt logged with:
  - Attempt number (e.g., "1/3")
  - Delay duration
  - Exception message
- Success after retries logged at INFO level
- Max retries exceeded logged at ERROR level

---

## 4. Critical Defaults

### 4.1 API Client Defaults

**Connection Defaults:**
- `base_url`: `"https://openrouter.ai/api/v1"`
- `timeout`: `180.0` seconds (3 minutes)
- `max_keepalive_connections`: `0` (force close after each request)
- `max_connections`: `10`

**Authentication Headers:**
- `Authorization`: `"Bearer {api_key}"`
- `Content-Type`: `"application/json"`
- `HTTP-Referer`: `"https://github.com/benchmark_llm"`
- `X-Title`: `"benchmark_llm"`

**Request Defaults:**
- `max_tokens`: Not sent if None (use model default)
- `temperature`: Not sent if None (use model default)
- `reasoning`: Not sent if None (use model default)
- `response_format`: Not sent if None (traditional text output)
- `include_debug`: `False` (debug mode disabled)

### 4.2 Retry Defaults

**Default Retry Configuration:**
- `max_retries`: `3` attempts
- `base_delay`: `1.0` seconds
- `max_delay`: `60.0` seconds
- `exponential_base`: `2.0`
- `retryable_status_codes`: `[429, 500, 502, 503, 504]`

### 4.3 Randomization Defaults

**Answer Randomizer:**
- `run_id`: `None` (randomization DISABLED by default)
- When `run_id=None`: Questions executed in natural snapshot order
- When `run_id` set: Fisher-Yates shuffle with seeded RNG
- Standard option letters: `["A", "B", "C", "D"]`

**Seed Resolution Priority:**
1. Run-level seed (if set)
2. Experiment default seed (if set in config)
3. `None` (no randomization)

**Seed Special Values:**
- `None` or empty: No randomization (original A,B,C,D order)
- `"AUTO"`: Automatic seed generation (hash of run_id)
- Integer: Fixed seed for reproducibility

### 4.4 Execution Engine Defaults

**Model Configuration:**
- `max_tokens`: From `settings.model_max_tokens` (None = model default)
- `temperature`: From `settings.model_temperature` (None = model default)
- `top_p`: From `settings.model_top_p` (None = model default)
- `reasoning`: Built from settings (None = not sent)
- `response_format`: `ANSWER_SCHEMA` if `settings.use_structured_outputs=True`

**Reasoning Configuration:**
- `reasoning_mode`: `"unspecified"` (DO NOT SEND reasoning field)
- `reasoning_effort`: `None` (not sent)
- `reasoning_max_tokens`: `None` (not sent)
- `reasoning_enabled`: `None` (not sent)

**Reasoning Mode Semantics:**
- `"unspecified"`: Do not send reasoning field (use model default)
- `"auto"`: Use model's default reasoning behavior
- `"off"`: Send `{"enabled": False}`
- `"effort"`: Send `{"effort": "..."}`
- `"budget"`: Send `{"max_tokens": N}`

### 4.5 Answer Parser Defaults

**Confidence Level Defaults:**
- Empty response: `confidence="no_answer"`, `answer=None`
- Single pattern match: `confidence="clear"`
- Multiple different letters: `confidence="ambiguous"`, `answer=None`
- Only fallback match: `confidence="low_confidence"`

**Pattern Matching:**
- Case insensitive matching
- Multi-line mode enabled
- Article filtering for Portuguese/Spanish "A"

### 4.6 Result Writer Defaults

**Response Fields:**
- `parse_confidence`: `"clear"` if answer extracted, `"no_answer"` otherwise
- `needs_review`: `TRUE` if `parse_confidence` in `("ambiguous", "no_answer", "low_confidence")` OR `selected_answer IS NULL`
- `finish_reason`: `"stop"` (default for successful responses)
- `status`: `"success"` for successful executions

**Idempotency Key:**
- Uniqueness constraint: `(run_id, variant_id, snapshot_id)`
- Duplicate inserts skipped (not overwritten)

### 4.7 "Magic" Values

**Critical Magic Values:**
- `180.0`: Default timeout (3 minutes) - critical for reasoning models
- `0`: Connection limit for `max_keepalive_connections` (force close)
- `10`: Maximum concurrent connections
- `2.0`: Exponential backoff base
- `60.0`: Maximum retry delay cap
- `3`: Default retry count
- `429, 500, 502, 503, 504`: Retryable HTTP status codes
- `["A", "B", "C", "D"]`: Standard answer option letters
- `1`: Fixed iteration number (no iteration concept in current model)
- `1000`: Character threshold for `raw_body` truncation

**Implicit Behaviors:**
- `seed=None` meant "no randomization" (not an error)
- `reasoning=None` meant "don't send field" (not "disable reasoning")
- `max_tokens=None` meant "use model default" (not unlimited)
- Empty `content` after parsing triggered `needs_review=TRUE`
- HTTP 200 with error in body classified as `provider_error`

---

## 5. Component Interactions

### 5.1 Execution Flow

```
CLI
  ↓
Planner (builds ExecutionPlan from database)
  ↓
ExecutionPlan (immutable, self-contained)
  ↓
ExecutionEngine (executes plan, returns ExecutionResults)
  ↓
ResultWriter (persists results, updates run status)
  ↓
Database (responses, errors tables)
```

### 5.2 Data Flow

**Request Path:**
1. Planner reads experiment, runs, variants, snapshots from database
2. Planner builds ExecutionPlan with resolved configuration
3. ExecutionEngine iterates through PlanItems
4. For each item:
   - Build prompt from question payload
   - Apply answer randomization (if enabled)
   - Build messages array with system prompt
   - Call OpenRouterClient.chat_completion()
   - Parse response with ResponseParser
   - Extract answer with AnswerParser
   - Build ExecutionResult

**Response Path:**
1. ExecutionResult returned to ExecutionEngine
2. ExecutionEngine passes results to ResultWriter
3. ResultWriter:
   - Check idempotency (response exists?)
   - Write to `responses` table (success) or `errors` table (failure)
   - Update run status
   - Update run_model status

### 5.3 Separation of Concerns

**ExecutionEngine:**
- Does NOT access database
- Does NOT persist results
- Does NOT resolve configuration
- ONLY executes API calls and returns raw results

**ResultWriter:**
- Does NOT execute models
- Does NOT decide scope
- Does NOT create identity
- ONLY persists results and updates status

**Planner:**
- ONLY builds ExecutionPlan from database state
- Deduplicates items (excludes already-answered)
- Resolves all configuration (no fallback to globals)

---

## 6. Design Principles

### 6.1 Immutability

- ExecutionPlan immutable after creation
- Question snapshots immutable after creation
- Model variants immutable after creation
- Configuration frozen in experiment mode

### 6.2 Explicit Configuration

- No implicit configuration resolution during execution
- All configuration resolved before execution starts
- No fallback to global settings during execution
- ExecutionPlan self-contained (no external dependencies)

### 6.3 Idempotency

- ResultWriter idempotent (same input → same database state)
- Duplicate responses skipped (not overwritten)
- Duplicate errors skipped (not overwritten)
- Partial re-execution supported

### 6.4 Reproducibility

- Seeded randomization for answer shuffling
- Same seed → same randomization
- ExecutionPlan serializable for audit/replay
- All results auditable via database

### 6.5 Separation of Concerns

- Planner: Build plan (database read)
- ExecutionEngine: Execute plan (API calls)
- ResultWriter: Persist results (database write)
- No component does all three

---

## 7. Summary

The legacy execution system was built around these core concepts:

1. **Explicit, immutable execution plans** - All configuration resolved before execution, plans immutable after creation

2. **Separation of execution and persistence** - ExecutionEngine executed API calls without database access; ResultWriter persisted results without executing

3. **Comprehensive error handling** - Retry logic with exponential backoff for transient failures; immediate failure for non-retryable errors

4. **Idempotent result writing** - Duplicate results skipped, partial re-execution supported

5. **Reproducible randomization** - Seeded answer shuffling with explicit enable/disable control

6. **Hierarchical answer parsing** - Pattern matching with confidence classification for manual review routing

7. **Critical defaults** - Many "magic" values controlled correctness (timeouts, retry counts, connection limits)

This document captures the architectural essence without proposing improvements or comparing to newer implementations.
