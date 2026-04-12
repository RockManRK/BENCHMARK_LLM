---
type: reference
audience: ai
last-validated: 2026-04-11
status: active
---

# API Integration Reference

**Purpose:** OpenRouter and local model serving integration details  
**Source:** Validated against `src/api/` modules

---

## Architecture Note: Provider-Agnostic Design

**OpenRouter is the current implementation, not a conceptual dependency.**

The API client layer is designed as an abstract interface:
- `OpenRouterClient` implements the current provider
- Different providers can be supported by implementing the same interface
- Local model serving (e.g., llama.cpp) is also supported via separate client

**All API interactions must go through the client abstraction** — never direct HTTP calls from ExecutionEngine or other components.

---

## OpenRouterClient

**Module:** `src/api/client.py`

### Purpose

Wraps `httpx.AsyncClient` for async communication with OpenRouter API.

### Key Methods

| Method | Purpose |
|--------|---------|
| `__init__(base_url, api_key)` | Initialize with base URL and API key |
| `async generate_response(messages, **params)` | Send messages to model, receive response |
| `async close()` | Close httpx.AsyncClient |

### Parameters Supported

| Parameter | Type | Description | OpenRouter Mapping |
|-----------|------|-------------|-------------------|
| `max_tokens` | `int` | Max tokens for generation (1 or above) | `max_tokens` |
| `reasoning` | `dict` | Reasoning effort configuration | `reasoning: {effort: <level>}` |
| `temperature` | `float` | Temperature (0.0-2.0) | `temperature` |
| `top_p` | `float` | Top-P sampling (0.0-1.0) | `top_p` |
| `top_k` | `int` | Top-K sampling (0 or above) | `top_k` |
| `repeat_penalty` | `float` | Repeat penalty (0.0-2.0) | `repeat_penalty` |

**Note:** Parameters set to `None` are **not sent** in API request (activates API server defaults).

### Authentication

- API key passed via `Authorization: Bearer <key>` header
- **Key must come from system environment variable**, never from `.env` file
- Base URL configurable (default: `https://openrouter.ai/api/v1`)

### Response Format

OpenRouter returns:
```json
{
  "id": "gen-...",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Response text..."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200,
    "total_tokens": 300
  },
  "cost": 0.0012
}
```

### Error Handling

| Error Type | HTTP Status | Retry? |
|------------|-------------|--------|
| Network error | N/A | ✅ Yes |
| Rate limit | 429 | ✅ Yes |
| Auth error | 401 | ❌ No |
| Server error | 5xx | ✅ Yes |
| Bad request | 400 | ❌ No |

---

## Message Builder

**Module:** `src/api/message_builder.py`

### Purpose

Constructs OpenRouter API request messages.

### Message Structure

```python
messages = [
    {"role": "system", "content": system_prompt},  # Optional
    {"role": "user", "content": user_prompt}
]
```

- System prompt included only if not `None`
- User prompt formatted with question and options

---

## Response Parser

**Module:** `src/api/response_parser.py`

### Purpose

Extracts and parses model responses.

### Parsing Steps

1. **Extract text** from API response
2. **Find answer pattern** (A/B/C/D) using regex
3. **Calculate confidence** (`clear`, `ambiguous`, `no_answer`, `unknown`, `low_confidence`)
4. **Return structured result**

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `clear` | Unambiguous answer found (e.g., `\boxed{A}`, `Answer: A`) |
| `ambiguous` | Multiple possible answers detected |
| `no_answer` | No answer pattern found |
| `low_confidence` | Weak answer signal |
| `unknown` | Parsing failed unexpectedly |

### Answer Patterns Recognized

- `\boxed{A}`, `\boxed{B}`, etc.
- `Answer: A`, `Answer: B`, etc.
- `The answer is A`, `The correct option is B`
- `Letra A`, `Alternativa B` (Portuguese)
- Single letter at end of response

---

## Stream Aggregator

**Module:** `src/api/stream_aggregator.py`

### Purpose

Handles streaming responses from API.

### Behavior

- Receives chunks from API
- Aggregates into complete response
- Handles chunk errors gracefully

---

## Retry Handler

**Module:** `src/core/retry.py`

### Purpose

Centralized retry with exponential backoff.

**Contract:** All API calls go through retry handler — no bypass allowed.

### Configuration

```python
RetryPolicy(
    max_attempts=3,
    backoff="exponential",  # or "linear"
    initial_delay=1.0,
    max_delay=60.0,
)
```

### Retry Logic

```
Attempt 1 → Fail? → Wait (backoff) → Attempt 2 → Fail? → Wait → Attempt 3 → Fail? → Give up
```

- **Exponential backoff:** delay × 2^attempt (capped at max_delay)
- **Linear backoff:** delay × attempt (capped at max_delay)
- **Retry attempts are logged** with experiment/run/model/question context

### Retryable Errors

| Error Type | Retry? |
|------------|--------|
| Network timeout | ✅ Yes |
| Rate limit (429) | ✅ Yes |
| Server error (5xx) | ✅ Yes |
| Auth error (401) | ❌ No |
| Bad request (400) | ❌ No |

---

## Local Model Serving (llama.cpp)

**Status:** Supported via separate client implementation.

**Design:** Same interface as OpenRouterClient, but communicates with local server instead of HTTP API.

**Configuration:** Use model-specific `--url` flag to point to local server.

---

## Error Types

**Module:** `src/api/errors.py`

### Error Classification

| Error Class | Description | Examples |
|-------------|-------------|----------|
| `NetworkError` | Connection issues | Timeout, DNS, connection refused |
| `AuthError` | Authentication failures | Invalid key, expired token |
| `RateLimitError` | Rate limiting | 429 Too Many Requests |
| `ServerError` | Server-side failures | 500, 502, 503 |
| `BadRequestError` | Client errors | 400, 404, 422 |

---

## API Request Flow

```
ExecutionEngine
    ↓
Build request (model config + question payload)
    ↓
RetryHandler.execute_with_retry(api_call)
    ↓
OpenRouterClient.generate_response(messages, **params)
    ↓
httpx.AsyncClient.post(base_url + "/chat/completions", ...)
    ↓
Receive response
    ↓
Parse response (AnswerParser)
    ↓
Return ExecutionResult
```

---

## Token Accounting

| Token Type | Source | Stored In |
|------------|--------|-----------|
| `input_tokens` | API response `usage.prompt_tokens` | `responses.input_tokens` |
| `response_tokens` | API response `usage.completion_tokens` | `responses.response_tokens` |
| `reasoning_tokens` | API response (if provided) | `responses.reasoning_tokens` |
| `effective_tokens` | Calculated: input + response + reasoning | `responses.effective_tokens` |

---

## Cost Tracking

| Field | Source |
|-------|--------|
| `cost` | API response `cost` field |
| `latency_ms` | Calculated: `finished_at - started_at` |

---

## Related Documents

- [architecture/execution-architecture.md](../architecture/execution-architecture.md) — API layer in execution flow
- [contracts/determinism.md](../contracts/determinism.md) — Same config produces same requests
- [reference/configuration-reference.md](configuration-reference.md) — API configuration settings
- [reference/module-structure.md](module-structure.md) — API layer modules
