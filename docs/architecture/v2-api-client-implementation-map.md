# V2 API Client — Implementation Map

**Document Type:** Design & Implementation Guide  
**Project:** Benchmark LLM V2  
**Version:** 1.0  
**Date:** 2026-03-30  
**Status:** Authoritative Reference  

---

## 1. Purpose and Scope

### 1.1 Purpose

The V2 API Client is a **provider-agnostic adapter layer** responsible for:

- Translating domain-level completion requests into provider-specific API calls
- Normalizing provider responses into a standardized `CompletionResponse` format
- Classifying and raising domain-specific errors
- Executing retry logic based on explicit policy
- Logging all API interactions for auditability

### 1.2 Scope Boundaries

**In Scope:**
- HTTP communication with completion providers (OpenRouter, llama.cpp, etc.)
- Authentication and header management
- Request payload construction
- Response parsing and normalization
- Error classification and translation
- Retry execution (policy-driven)
- Request/response logging

**Out of Scope:**
- Configuration resolution (responsibility of `ConfigResolver`)
- Database access (responsibility of `Planner` and `ResultWriter`)
- Execution planning or scope decisions (responsibility of `Planner`)
- Result persistence (responsibility of `ResultWriter`)
- Answer parsing or evaluation (responsibility of `ExecutionEngine`)
- Prompt template resolution (responsibility of `ConfigResolver`)

### 1.3 Design Principles

1. **Provider Agnosticism:** The client does not know about experiments, runs, or questions. It only knows about models and messages.

2. **Explicit Configuration:** The client receives all configuration explicitly. It does not resolve settings, read `.env`, or access global state.

3. **No Implicit Behavior:** The client does not infer, assume, or apply defaults. If a parameter is `None`, it is not sent to the API.

4. **Deterministic Errors:** Errors are classified deterministically based on HTTP status codes and error types. No heuristics.

5. **Policy-Driven Retry:** The client does not decide what to retry. It executes the `RetryPolicy` passed to it.

6. **Crash-Safe Logging:** All API interactions are logged before and after execution. Logs are flushed immediately.

---

## 2. Responsibilities and Non-Responsibilities

### 2.1 Responsibilities (What the API Client DOES)

| Responsibility | Description |
|----------------|-------------|
| **HTTP Communication** | Makes async HTTP requests to provider endpoints |
| **Authentication** | Manages API keys and authentication headers |
| **Request Building** | Constructs provider-specific request payloads |
| **Response Parsing** | Extracts content, tokens, and metadata from responses |
| **Error Classification** | Translates HTTP errors into domain error types |
| **Retry Execution** | Executes retry logic based on `RetryPolicy` |
| **Observability** | Logs all API requests, responses, and errors |
| **Timeout Management** | Enforces request timeouts |
| **Connection Management** | Manages HTTP client lifecycle and connection pooling |

### 2.2 Non-Responsibilities (What the API Client DOES NOT Do)

| Non-Responsibility | Rationale |
|--------------------|-----------|
| **Configuration Resolution** | Client receives explicit configuration; does not resolve from `.env` or hierarchy |
| **Database Access** | Client is stateless; persistence is responsibility of `Planner` and `ResultWriter` |
| **Execution Planning** | Client does not decide what to execute; receives explicit instructions |
| **Prompt Resolution** | Client receives resolved prompts; does not apply templates or inheritance |
| **Answer Parsing** | Client returns raw content; parsing is responsibility of `ExecutionEngine` |
| **Result Persistence** | Client returns `CompletionResponse`; persistence is responsibility of caller |
| **Retry Policy Decisions** | Client executes policy; does not decide what is retryable |
| **Provider Discovery** | Client does not discover or enumerate providers; receives explicit `base_url` |

---

## 3. Provider Abstraction Strategy

### 3.1 Provider Interface

All providers implement the `CompletionProvider` abstract base class:

```python
class CompletionProvider(ABC):
    @abstractmethod
    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResponse:
        pass
```

### 3.2 Supported Providers

#### OpenRouter (Primary)

- **Base URL:** `https://openrouter.ai/api/v1` (configurable)
- **Authentication:** Bearer token via `Authorization` header
- **Endpoint:** `/chat/completions` (POST)
- **API Contract:** OpenAI-compatible chat completions format

#### llama.cpp (Local)

- **Base URL:** User-specified (e.g., `http://localhost:8080/v1`)
- **Authentication:** None (local deployment)
- **Endpoint:** `/v1/chat/completions` (POST)
- **API Contract:** OpenAI-compatible format

### 3.3 Provider Abstraction Rules

1. **Single Interface:** All providers implement the same `CompletionProvider` interface.

2. **Standardized Response:** All providers return `CompletionResponse` dataclass.

3. **Provider-Specific Logic:** Provider-specific behavior (e.g., authentication, error formats) is encapsulated within the provider implementation.

4. **No Provider Detection:** The client does not auto-detect providers. The `base_url` determines the provider.

5. **Uniform Error Handling:** All providers use the same error hierarchy (`APIError` and subclasses).

### 3.4 Future Provider Support

To add a new provider:

1. Create a new class inheriting from `CompletionProvider`
2. Implement `chat_completion()` method
3. Handle provider-specific authentication and error formats
4. Return `CompletionResponse` with standardized fields

**Example:**
```python
class CustomProvider(CompletionProvider):
    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict],
        **kwargs
    ) -> CompletionResponse:
        # Provider-specific implementation
        return CompletionResponse(...)
```

---

## 4. Request Lifecycle

### 4.1 Sequential Flow

```
1. ExecutionEngine receives ExecutionPlan
2. For each PlanRun in plan.runs:
   3. Resolve configuration (ConfigResolver)
   4. Initialize RetryHandler with RetryPolicy
   5. For each PlanItem in run.items:
      6. Build messages array (system + user)
      7. Build model config from variant
      8. Create CompletionProvider instance
      9. Call provider.chat_completion() with retry
      10. Log request and response
      11. Parse response (content, tokens, latency)
      12. Return CompletionResponse
13. ExecutionEngine processes response
14. ResultWriter persists results
```

### 4.2 Timing and Timeout

**Default Timeout:** 120 seconds (configurable via `timeout` parameter)

**Timeout Behavior:**
- Timeout applies to the entire HTTP request
- Timeout errors are classified as `TimeoutError` (retryable)
- Timeout is enforced by `httpx.AsyncClient`

**Latency Tracking:**
- Measured from before HTTP request to after response parsing
- Tracked in `CompletionResponse.latency_ms`
- Logged for observability

### 4.3 Connection Management

```python
# httpx.AsyncClient configuration
client = httpx.AsyncClient(
    timeout=timeout,
    # Limits configured for crash safety
    limits=httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20
    )
)
```

**Rationale:** Balance between connection reuse and crash safety. Connections are cleaned up properly to avoid "Event loop is closed" errors.

### 4.4 Async Context Handling

The API client is fully async. It supports both:

**Pure Async Context:**
```python
async with OpenRouterClient(api_key) as client:
    response = await client.chat_completion(...)
```

**Mixed Sync/Async Context:**
```python
# In sync ExecutionEngine
loop = asyncio.get_running_loop()
response = await asyncio.create_task(
    client.chat_completion(...)
)
```

---

## 5. Payload Construction Rules

### 5.1 Request Structure

```python
payload = {
    "model": model_id,
    "messages": messages,
    # Optional parameters (ONLY if not None)
    "temperature": float,
    "top_p": float,
    "max_tokens": int,
    "stop": list[str],
    "response_format": dict,
}
```

### 5.2 Null Semantics

**Critical Rule:** Parameters are **only sent if explicitly set** (not `None`).

```python
# Correct V2 pattern
if temperature is not None:
    payload["temperature"] = temperature
```

**Rationale:** `None` means "use provider default". This allows the system to avoid overriding provider-side defaults unintentionally.

### 5.3 Message Building

**System Prompt Handling:**

```python
messages = []

# Add system prompt ONLY if not None
if system_prompt is not None:
    messages.append({"role": "system", "content": system_prompt})

# Always add user message
messages.append({"role": "user", "content": user_message})
```

**Null System Prompt:** If `system_prompt` is `None`, no system message is sent. This is the V2 default behavior.

**User Message Construction:**

```python
# Build user message from question payload
stem = question_payload.stem
options_text = "\n".join([
    f"{chr(65+i)}) {opt}" 
    for i, opt in enumerate(question_payload.options)
])

user_message = f"""{stem}

{options_text}

{user_prompt_template}"""
```

### 5.4 Generation Parameters

| Parameter | Type | Default | Sent When |
|-----------|------|---------|-----------|
| `temperature` | float | `None` | `temperature is not None` |
| `top_p` | float | `None` | `top_p is not None` |
| `max_tokens` | int | `None` | `max_tokens is not None` |
| `stop` | list[str] | `None` | `stop is not None` |
| `response_format` | dict | `None` | `response_format is not None` |

### 5.5 Structured Outputs

When `response_format` is provided:

```python
# Example: JSON schema for answer extraction
response_format = {
    "type": "json_object",
    "schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "enum": ["A", "B", "C", "D"]}
        },
        "required": ["answer"]
    }
}

payload["response_format"] = response_format
```

**Usage:** Controlled by `ModelVariant.structured_enabled` field.

---

## 6. Retry, Backoff, and Error Classification Model

### 6.1 Retry Policy Structure

```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    retry_on: tuple[str, ...] = (
        'http_429',      # Rate limit
        'http_5xx',      # Server errors
        'timeout',       # Request timeouts
        'network_error', # Network failures
    )
```

### 6.2 Error Classification

```python
class ErrorClassifier:
    @staticmethod
    def classify_http(status_code: int, response_text: str) -> APIError:
        if status_code == 429:
            return RateLimitError(f"HTTP {status_code}: {response_text}")
        
        if 500 <= status_code < 600:
            return ServerError(f"HTTP {status_code}: {response_text}")
        
        if status_code in (401, 403):
            return AuthenticationError(f"HTTP {status_code}: {response_text}")
        
        if 400 <= status_code < 500:
            return ClientError(f"HTTP {status_code}: {response_text}")
        
        return APIError(f"HTTP {status_code}: {response_text}", error_type=f"http_{status_code}")
```

### 6.3 Error Types and Retry Behavior

| Error Type | HTTP Status | Retryable | Rationale |
|------------|-------------|-----------|-----------|
| `AuthenticationError` | 401, 403 | **No** | Credentials invalid; retry won't help |
| `RateLimitError` | 429 | **Yes** | Transient; backoff will help |
| `ServerError` | 500-599 | **Yes** | Server-side issue; may resolve |
| `ClientError` | 400-499 (non-auth) | **No** | Client error; request is invalid |
| `TimeoutError` | N/A | **Yes** | Network transient issue |
| `NetworkError` | N/A | **Yes** | Connectivity issue; may resolve |

### 6.4 Backoff Strategies

**Exponential (Default):**
```python
delay = 2 ** attempt  # 2s, 4s, 8s, 16s, ...
```

**Linear:**
```python
delay = attempt  # 1s, 2s, 3s, 4s, ...
```

**Constant:**
```python
delay = 1.0  # 1s, 1s, 1s, 1s, ...
```

### 6.5 Retry Execution Flow

```python
async def execute_with_retry(func, context=""):
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await func()
        
        except APIError as e:
            if not is_retryable(e):
                raise  # Non-retryable, fail immediately
            
            if attempt >= policy.max_attempts:
                break  # Exhausted, will raise after loop
            
            delay = calculate_delay(attempt)
            log_retry_attempt(attempt, delay, e)
            await asyncio.sleep(delay)
    
    raise last_exception  # All attempts exhausted
```

### 6.6 Retry Logging

```
INFO: RETRY_START | operation=chat_completion | item=run-001::var-abc::snap-xyz::it-1 | max_attempts=3
WARNING: RETRY_ATTEMPT | operation=chat_completion | item=... | attempt=1/3 | delay=2.00s | error=Rate limit exceeded
INFO: RETRY_SUCCESS | operation=chat_completion | item=... | attempts=2
```

---

## 7. Response Parsing and Normalization Contract

### 7.1 Expected Response Structure

```python
{
    "id": "chatcmpl-123",
    "model": "openai/gpt-4",
    "choices": [
        {
            "message": {
                "content": "The answer is (B).",
                "role": "assistant"
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 10,
        "total_tokens": 60
    }
}
```

### 7.2 Response Parsing

```python
def parse_response(data: dict, start_time: float) -> CompletionResponse:
    # Extract content
    content = data["choices"][0]["message"]["content"]
    
    # Extract token usage
    usage = data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    
    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    
    return CompletionResponse(
        content=content,
        model_id=data.get("model", ""),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        raw_response=data,
    )
```

### 7.3 Token Counting

**Standard Fields:**
- `prompt_tokens`: Input tokens sent to model
- `completion_tokens`: Output tokens generated
- `total_tokens`: Sum of prompt + completion

**Reasoning Tokens (Future):**
Some models (e.g., Qwen with reasoning) may return `completion_tokens_details`:

```python
completion_tokens_details = usage.get("completion_tokens_details", {})
reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)
effective_tokens = input_tokens + output_tokens + reasoning_tokens
```

**Status:** Reserved for future use. Not currently implemented.

### 7.4 Content Extraction

**Standard Content:**
```python
content = data["choices"][0]["message"]["content"]
```

**Reasoning Models (Future):**
Some reasoning models may output to separate fields:

```python
message = data["choices"][0]["message"]
content = message.get("content", "")

# Fallback to reasoning_content if content is empty
if not content:
    content = message.get("reasoning_content", "")
```

**Status:** Reserved for future use. Not currently implemented.

### 7.5 Finish Reason Handling

**Success Reasons:**
- `"stop"` - Normal completion
- `"length"` - Hit max_tokens limit
- `"eos_token"` - End of sequence token

**Error Reasons:**
- `"content_filter"` - Content policy violation
- `"function_call"` - Unexpected function call

**V2 Approach:** Finish reason is logged but not used for status determination. Status is determined by HTTP success/failure.

---

## 8. Configuration Surface

### 8.1 Configurable Parameters

| Parameter | Source | Default | Notes |
|-----------|--------|---------|-------|
| `api_key` | Explicit | **Required** | Passed explicitly, never resolved from `.env` |
| `base_url` | Explicit | `"https://openrouter.ai/api/v1"` | Determines provider |
| `timeout` | Explicit | `120` | Request timeout in seconds |
| `temperature` | Variant config | `None` | `None` = provider default |
| `top_p` | Variant config | `None` | `None` = provider default |
| `max_tokens` | Variant config | `None` | `None` = provider default |
| `response_format` | Variant config | `None` | `None` = no schema |

### 8.2 Non-Configurable (Fixed) Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `Content-Type` | `"application/json"` | Fixed header |
| `Authorization` scheme | `"Bearer"` | Fixed auth scheme |
| Message format | OpenAI chat format | Provider contract |
| Error classification | Deterministic rules | No heuristics |

### 8.3 Configuration Hierarchy

The API client **does not participate** in configuration hierarchy. It receives explicit configuration:

```
ConfigResolver → ExecutionEngine → API Client
                (explicit config)
```

**Example:**
```python
# ConfigResolver resolves configuration from hierarchy
config = ConfigResolver.resolve(
    cli_args=cli_args,
    env_settings=env_settings,
    experiment_config=experiment_config,
    run_config=run_config,
)

# ExecutionEngine passes explicit config to API client
response = await client.chat_completion(
    model_id=variant.model_id,
    messages=messages,
    temperature=variant.config.temperature,  # Explicit value
    max_tokens=variant.config.max_tokens,    # Explicit value
)
```

### 8.4 Null Semantics

**Rule:** `null` (None in Python) means "do not send, use provider default".

**Examples:**
```python
# temperature=None → Do not send temperature field
# Provider uses its default
await client.chat_completion(
    model_id="openai/gpt-4",
    messages=messages,
    temperature=None,  # Not sent to API
)

# temperature=0.7 → Send temperature=0.7
await client.chat_completion(
    model_id="openai/gpt-4",
    messages=messages,
    temperature=0.7,  # Sent to API
)
```

---

## 9. Observability and Debugging Requirements

### 9.1 Logging Architecture

**Logger Hierarchy:**
```
root (benchmark_llm)
├── api.client (API requests/responses)
├── api.retry (Retry attempts)
├── core.execution (Execution flow)
└── db (Database operations)
```

### 9.2 Log Levels

| Level | API Client Usage |
|-------|------------------|
| **DEBUG** | Full request/response payloads (sensitive data redacted) |
| **INFO** | Request start, response summary, latency, tokens |
| **WARNING** | Retry attempts, non-retryable errors |
| **ERROR** | HTTP errors, timeouts, network failures |
| **CRITICAL** | Unrecoverable failures |

### 9.3 Required Log Messages

**Request Start:**
```
INFO: API_REQUEST | endpoint=/v1 | model=openai/gpt-4 | prompt_length=150
```

**Response Received:**
```
INFO: API_RESPONSE | model=openai/gpt-4 | latency=523ms | tokens=60
```

**Retry Attempt:**
```
WARNING: RETRY_ATTEMPT | operation=chat_completion | item=run-001::var-abc::snap-xyz::it-1 | attempt=1/3 | delay=2.00s | error=Rate limit exceeded
```

**Error:**
```
ERROR: API_ERROR | status=429 | error_type=rate_limit | error=Rate limit exceeded
```

### 9.4 Log Format

```
%(asctime)s - %(levelname)s - %(name)s - %(message)s
2026-03-30 14:30:00 - INFO - src.api.client - API_REQUEST | endpoint=/v1 | model=openai/gpt-4
```

### 9.5 Crash-Safe Logging

**Requirement:** All log handlers must flush after every write.

```python
class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()  # Ensure log is written immediately
```

**Rationale:** Logs are scientific data. They must persist even if the process crashes.

### 9.6 Sensitive Data Handling

**Rule:** API keys and sensitive data must never appear in logs.

**Implementation:**
```python
# Log prompt length, not content
prompt_length = sum(len(msg.get("content", "")) for msg in messages)
logger.info(f"API_REQUEST | prompt_length={prompt_length}")

# Log error type, not full error response (may contain sensitive data)
logger.error(f"API_ERROR | status={status_code} | error_type={error_type}")
```

### 9.7 Debug Mode (Future)

**Reserved for future implementation:**

A debug mode could capture full request/response payloads for debugging:

```python
if debug_mode:
    logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
    logger.debug(f"Response body: {json.dumps(data, indent=2)}")
```

**Restriction:** Debug mode must be explicitly enabled and must redact sensitive data.

---



## Appendix A: File Locations

| Component | File Path |
|-----------|-----------|
| API Client | `src/api/client.py` |
| Error Hierarchy | `src/api/errors.py` |
| Retry Handler | `src/core/retry.py` |
| Execution Plan | `src/core/execution_plan.py` |
| Execution Engine | `src/core/execution_engine.py` |
| Result Writer | `src/core/result_writer.py` |
| Config Resolver | `src/core/config_resolver.py` |
| Logging Config | `src/utils/logging_config.py` |

---

## Appendix B: Related Documents

- **System Rules:** `docs/architecture/to-be/llmbc_system.md`
- **CLI Commands:** `docs/architecture/to-be/comandos_simples.md`
- **ResultWriter Contract:** `docs/architecture/contracts/result-writer.md`
- **Implementation Checklist:** `docs/architecture/v2-implementation-checklist.md`

---

**Document Status:** Complete  
**Last Updated:** 2026-03-30  
**Maintainer:** V2 Architecture Team
