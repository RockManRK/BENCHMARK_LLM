# V1 API Communication — Operational Knowledge Extract

**Document Type:** Technical Reference (Descriptive)  
**Source:** `src_legacy/` codebase  
**Date:** 2026-03-30  
**Purpose:** Extract operational knowledge about API communication from V1 implementation

---

## 1. Supported Providers

### OpenRouter (Primary)
- **Base URL:** `https://openrouter.ai/api/v1` (configurable via `OPENROUTER_BASE_URL`)
- **Authentication:** Bearer token via `OPENROUTER_API_KEY` environment variable
- **Endpoint:** `/chat/completions` (POST)
- **Model Info Endpoint:** `/models` (GET)

### llama.cpp (Local)
- **Base URL:** Configurable per model variant via `BASE_URL` setting
- **Authentication:** None required for local instances
- **Same API contract** as OpenRouter (chat completions format)

### Provider Abstraction
The system treats all providers uniformly through the `OpenRouterClient` class. Provider differentiation occurs at the `base_url` level:
- OpenRouter: `https://openrouter.ai/api/v1`
- Local llama.cpp: User-specified (e.g., `http://localhost:8080/v1`)

**Key Insight:** The codebase does not implement provider-specific logic beyond URL routing. All providers must conform to the OpenRouter chat completions API contract.

---

## 2. Request Lifecycle

### Sequential Flow

```
1. ExecutionEngine receives ExecutionPlan
2. For each PlanRun in plan.runs:
   3. Initialize randomizer with run seed
   4. For each PlanItem in run.items:
      5. Build question payload (stem + options)
      6. Apply answer randomization (if seed != None)
      7. Build user prompt with randomized options
      8. Build messages array [system, user]
      9. Build model config from variant settings
      10. Call OpenRouterClient.chat_completion()
      11. Parse response (extract answer, tokens, latency)
      12. Map randomized answer back to canonical letter
      13. Return ExecutionResult
14. ResultWriter persists all results
```

### Timing
- **Timeout:** 180 seconds default (configurable via `timeout` parameter)
- **Latency Tracking:** Measured from before API call to after response parsing
- **No Concurrent Execution:** V1 executes strictly sequentially (one item at a time)

### Connection Management
```python
# httpx.AsyncClient configuration
limits = httpx.Limits(
    max_keepalive_connections=0,  # Disable keepalive
    max_connections=10
)
```

**Rationale:** Forces connection cleanup after each request to avoid "Event loop is closed" errors in certain execution contexts.

---

## 3. Authentication & Headers

### Required Headers

```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://github.com/benchmark_llm",
    "X-Title": "benchmark_llm",
}
```

### API Key Handling

**Security Model:**
- API key **must** come from system environment variable `OPENROUTER_API_KEY`
- `.env` file is explicitly **not** trusted for API keys
- Validator enforces this at runtime:

```python
@model_validator(mode="after")
def validate_api_key_from_env(self) -> "Settings":
    env_api_key = os.getenv("OPENROUTER_API_KEY")
    if env_api_key:
        object.__setattr__(self, "openrouter_api_key", env_api_key)
    return self
```

### Authentication Errors

**HTTP 401 Handling:**
```python
if response.status_code == 401:
    raise httpx.HTTPStatusError(
        "Authentication failed: Invalid API key",
        request=response.request,
        response=response
    )
```

**Behavior:** Immediate failure, no retry. Authentication errors are considered non-retryable.

---

## 4. Payload Construction

### Request Structure

```python
payload = {
    "model": model_id,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt_text}
    ],
    # Optional parameters (only if not None)
    "max_tokens": int,
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "repeat_penalty": float,
    "reasoning": {
        "enabled": bool,
        "effort": str,  # "xhigh", "high", "medium", "low", "minimal", "none"
        "max_tokens": int
    },
    "response_format": { ... },  # For structured outputs
    "debug": { ... }  # Debug mode (blocked in EXPERIMENT mode)
}
```

### Message Building

**Text-Only:**
```python
MessageBuilder.build_user_message(content: str) -> {"role": "user", "content": content}
```

**Multimodal (Vision):**
```python
MessageBuilder.build_multimodal_message(text: str, image_path: Path) -> {
    "role": "user",
    "content": [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
    ]
}
```

**Image Encoding:**
- Reads image as bytes
- Encodes to base64
- Wraps in data URL format: `data:{mime_type};base64,{base64_data}`
- Supported formats: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`

### Prompt Construction

**Default System Prompt:**
```
"You are a helpful assistant."
```

**Default User Prompt:**
```
"Select the correct answer by providing only the letter (A, B, C, or D)."
```

**Full Prompt Structure:**
```
{stem}

{options_text}

{user_prompt}
```

Where:
- `stem`: Question stem from dataset
- `options_text`: Formatted as `"A) Option A\nB) Option B\n..."`
- `user_prompt`: Custom or default instruction

### Reasoning Configuration

**OpenRouter Standard Format:**
```python
reasoning = {
    "enabled": False,  # or True
    "effort": "high",  # xhigh, high, medium, low, minimal, none
    "max_tokens": 8000
}
```

**Special Case: `effort='none'`**
```python
if reasoning_effort == 'none':
    reasoning_config["enabled"] = False
```

**Rationale:** `"effort: none"` is equivalent to disabling reasoning. The field is still sent but with `enabled: False`.

### Structured Outputs

When `use_structured_outputs=True`:
```python
from src.utils.answer_schema import ANSWER_SCHEMA
payload["response_format"] = ANSWER_SCHEMA
```

**Schema (inferred):** JSON schema enforcing answer letter extraction (A/B/C/D format).

### Conditional Parameter Sending

**Critical Pattern:** Parameters are **only sent if explicitly set** (not None):

```python
if max_tokens is not None:
    payload["max_tokens"] = max_tokens
if temperature is not None:
    payload["temperature"] = temperature
if reasoning is not None:
    payload["reasoning"] = reasoning
```

**Rationale:** `None` means "use model/provider default". This allows the system to avoid overriding provider-side defaults unintentionally.

---

## 5. Retry & Backoff Strategy

### Retry Configuration

```python
@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retryable_status_codes: list[int] = [429, 500, 502, 503, 504]
```

### Retryable Conditions

**HTTP Status Codes:**
- `429` - Rate limit exceeded
- `500` - Internal server error
- `502` - Bad gateway
- `503` - Service unavailable
- `504` - Gateway timeout

**Exception Types:**
- `httpx.TimeoutException`
- `httpx.ConnectError`
- `httpx.NetworkError`

**Non-Retryable:**
- `401` - Authentication failure (immediate fail)
- `400` - Bad request
- `404` - Not found
- Client-side errors

### Exponential Backoff Calculation

```python
def _calculate_delay(self, attempt: int) -> float:
    delay = base_delay * (exponential_base ** attempt)
    return min(delay, max_delay)
```

**Example Delays (default config):**
- Attempt 0: 1.0s
- Attempt 1: 2.0s
- Attempt 2: 4.0s
- Attempt 3: 8.0s
- Attempt 4+: 60.0s (capped)

### Retry Decorator Usage

```python
retry_handler = RetryHandler(RetryConfig(max_retries=3))

@retry_handler.retry
async def chat_completion(...):
    ...
```

**Logging:**
```
INFO: Retry attempt 1/3 after 1.00s delay due to: Rate limit exceeded
INFO: Retry attempt 2/3 after 2.00s delay due to: Rate limit exceeded
INFO: Operation succeeded after 2 retry attempt(s)
```

### Error After All Retries

```python
raise RetryError(
    f"Max retries exceeded after {max_retries} attempts",
    last_exception=exc
) from exc
```

**Behavior:** Execution fails, error is logged and persisted to `errors` table.

---

## 6. Error Classification & Handling

### Error Normalization

```python
def normalize_openrouter_error(http_status: int, response_body: dict) -> dict:
    return {
        "error_type": str,  # e.g., "rate_limit", "authentication"
        "http_status": int,
        "message": str,
        "raw_body": dict  # Full response for debugging
    }
```

### Error Type Mapping

| HTTP Status | Error Type | Retry? |
|-------------|-----------|--------|
| 400 | `bad_request` | No |
| 401 | `authentication` | No |
| 403 | `forbidden` | No |
| 404 | `not_found` | No |
| 429 | `rate_limit` | **Yes** |
| 500 | `server_error` | **Yes** |
| 502 | `bad_gateway` | **Yes** |
| 503 | `service_unavailable` | **Yes** |
| 504 | `gateway_timeout` | **Yes** |
| 200 + error in body | `provider_error` | No |

### Special Case: HTTP 200 with Error in Body

Some providers return errors with HTTP 200 status:

```python
if http_status == 200 and "error" in response_body:
    error_type = "provider_error"
    logger.warning(f"HTTP 200 with error in body: {error_message}")
```

**Handling:** Treated as an error, not a success.

### Error Extraction from Raw Response

```python
def extract_error_from_raw(raw_response: dict) -> Optional[dict]:
    # Handles both wrapped (_debug) and unwrapped responses
    response_data = raw_response.get("response", raw_response)
    
    if "error" in response_data:
        return normalize_openrouter_error(200, response_data)
    
    # Check for error indicators in content
    content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if "error" in content.lower() or "failed" in content.lower():
        return {
            "error_type": "content_error",
            "http_status": 200,
            "message": content,
            "raw_body": raw_response
        }
    
    return None
```

### Error Persistence

Errors are stored in the `errors` table:

```python
Error(
    run_id=str,
    variant_id=str,
    question_id=str,
    error_type=str,
    error_message=str,
    stack_trace=str,
    attempt_count=int
)
```

**Idempotency:** Errors are deduplicated by `(run_id, variant_id, snapshot_id)` key.

---

## 7. Response Parsing & Normalization

### Response Structure Expected

```python
{
    "id": str,
    "model": str,
    "choices": [
        {
            "message": {
                "content": str,
                "reasoning_content": str  # Optional (reasoning models)
            },
            "finish_reason": str
        }
    ],
    "usage": {
        "prompt_tokens": int,
        "completion_tokens": int,
        "total_tokens": int,
        "cost": float  # Optional
    }
}
```

### Answer Extraction

**Primary Method:** `AnswerParser` module (external to API client)

```python
from src.core.answer_parser import AnswerParser

parser = AnswerParser()
parsed = parser.parse(content)
selected_answer = parsed.answer  # A, B, C, D or None
```

**Fallback (if parser fails):**
```python
import re

# Simple letter extraction
match = re.search(r'\b([A-D])\b', content.upper())
if match:
    return match.group(1)

# "Answer is X" pattern
match = re.search(r'answer\s+is\s+([A-D])', content.upper())
if match:
    return match.group(1)
```

### Parse Confidence

```python
parse_confidence = "clear" if selected_answer else "no_answer"
```

**Used for:** Determining `needs_review` flag in ResultWriter.

### Token Extraction

```python
def _extract_token_usage(api_response: dict) -> dict:
    usage = api_response.get("usage", {})
    return {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0)
    }
```

**Note:** `output_tokens` is deprecated alias for `completion_tokens` (backward compatibility).

### Reasoning Tokens (Emergent Feature)

Some models (e.g., Qwen with llama.cpp) return `completion_tokens_details`:

```python
completion_tokens_details = usage.get("completion_tokens_details", {})
reasoning_tokens = completion_tokens_details.get("reasoning_tokens", 0)
effective_tokens = input_tokens + response_tokens + reasoning_tokens
```

**Status:** Stubbed for future use in V1.

### Finish Reason Classification

**Success Reasons:**
- `"stop"` - Normal completion
- `"length"` - Hit max_tokens limit
- `"eos_token"` - End of sequence token

**Error Reasons:**
- `"content_filter"` - Content policy violation
- `"function_call"` - Unexpected function call

**Status Determination:**
```python
if finish_reason in ERROR_FINISH_REASONS:
    status = "error"
elif finish_reason in SUCCESS_FINISH_REASONS:
    status = "success"
elif content and content.strip():
    status = "success"  # Fallback: has content = success
else:
    status = "incomplete"
```

### Special Handling: Reasoning Models

For models that output reasoning separately:

```python
content = message.get("content", "")
if not content or not content.strip():
    reasoning_content = message.get("reasoning_content", "")
    if reasoning_content:
        content = reasoning_content
```

**Rationale:** Some reasoning models output primarily to `reasoning_content` field, leaving `content` empty.

---

## 8. Debugging & Observability

### Logging Architecture

**Hierarchical Loggers:**
```python
# Root logger (configured by setup_logging)
logger = logging.getLogger()

# Module loggers (inherit from root)
logger = logging.getLogger(__name__)

# Component loggers
logger = get_structured_logger('api')  # Creates child of root
```

### Log Levels

| Level | Console | File | Purpose |
|-------|---------|------|---------|
| DEBUG | ❌ | ✅ | Detailed API payloads, randomization details |
| INFO | ✅ | ✅ | Request/response summaries, completion status |
| WARNING | ✅ | ✅ | Non-critical issues (image not found, unknown model) |
| ERROR | ✅ | ✅ | API errors, failures |
| CRITICAL | ✅ | ✅ | System-level failures |

### Log Format

```
%(asctime)s - %(levelname)s - %(name)s - %(message)s
2026-03-30 14:30:00 - INFO - src.api.client - Sending API request: model=openai/gpt-4
```

### File Rotation

```python
FlushingRotatingFileHandler(
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
    delay=False  # Open immediately
)
```

**Flush Behavior:** Custom handler flushes after **every write** to ensure crash safety.

### Debug Mode (OpenRouter)

```python
if include_debug:
    payload["debug"] = {"echo_upstream_body": True}
```

**Response Structure (Debug):**
```python
{
    "_debug": {
        "request_payload": {...},  # What we sent to OpenRouter
        "upstream_body": {...}     # What OpenRouter sent to provider
    },
    "response": {...}  # Actual API response
}
```

**Restriction:** Debug mode is **blocked in EXPERIMENT mode** (config frozen, no debug allowed).

### Key Log Points

**Request:**
```python
logger.info(f"Sending API request: model={model}, max_tokens={max_tokens}, temperature={temperature}, structured_output={response_format is not None}, debug={include_debug}")
logger.debug(f"Sending chat completion request to {base_url}/chat/completions")
```

**Response:**
```python
logger.info(f"API response: model={model}, tokens={total_tokens}, finish_reason={finish_reason}, status={response.status_code}")
```

**Error:**
```python
logger.error(f"API error {status_code}: model={model}, message={error_message}")
logger.error(f"Error response body: {response.text}")
```

**Retry:**
```python
logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {delay:.2f}s delay due to: {exc}")
```

### Initialization Summary Log

```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : EXPERIMENT MODE
Experiment          : my_experiment
Persist data        : YES
Configuration       : FROZEN (config_hash=8f3a9c2e)
Seed                : 42
Models              : openai/gpt-4, anthropic/claude-3
Questions           : Q001-Q010 (10 questions)
============================================================
```

---

## 9. Known Edge Cases & Workarounds

### 1. Empty Content with Reasoning

**Problem:** Some reasoning models output to `reasoning_content` instead of `content`.

**Workaround:**
```python
if not content or not content.strip():
    reasoning_content = message.get("reasoning_content", "")
    if reasoning_content:
        content = reasoning_content
```

### 2. HTTP 200 with Error in Body

**Problem:** Some providers return errors with HTTP 200 status.

**Detection:**
```python
if http_status == 200 and "error" in response_body:
    error_type = "provider_error"
```

### 3. Concurrent Model Registration

**Problem:** Race condition when multiple processes register the same model.

**Workaround:**
```python
try:
    model_repo.create(model)
except sqlite3.IntegrityError:
    logger.debug(f"Base model registration conflict (ignored)")
```

### 4. Image Not Found

**Problem:** Question has `has_image=True` but file doesn't exist.

**Fallback:**
```python
if image_path.exists():
    user_message = build_multimodal_message(prompt, image_path)
else:
    logger.warning(f"Image not found for question {question_id}: {image_path}")
    user_message = build_user_message(prompt)  # Fallback to text-only
```

### 5. Unknown Model Vision Support

**Problem:** Model not in known vision/text-only lists.

**Safe Default:**
```python
if vision_support == VisionSupport.UNKNOWN:
    logger.warning(f"Model {model_id} has unknown vision support, marking as incompatible")
    return False  # Assume no vision support
```

### 6. Answer Parsing Failure

**Problem:** Model doesn't follow expected answer format.

**Fallback Chain:**
1. `AnswerParser` (primary)
2. Regex `\b([A-D])\b`
3. Regex `answer\s+is\s+([A-D])`
4. Return `None` (triggers `needs_review=True`)

### 7. Connection Cleanup

**Problem:** "Event loop is closed" errors in certain async contexts.

**Workaround:**
```python
limits = httpx.Limits(max_keepalive_connections=0, max_connections=10)
```

**Rationale:** Disables keepalive, forces connection cleanup after each request.

### 8. Seed=None Randomization

**Problem:** User wants original A,B,C,D order (no randomization).

**Solution:**
```python
if plan_run.seed_effective is not None:
    randomizer.reset_seed(plan_run.seed_effective)
    # Apply randomization
else:
    logger.debug("seed_effective is None, randomization disabled (natural order)")
    # Use original order
```

**Semantic:** `None` = "no randomization", not "random seed".

### 9. Experiment Protocol Mismatch

**Problem:** User runs experiment with different .env settings than creation.

**Resolution:**
```python
# Protocol settings are frozen (overwritten back to experiment values)
protocol_keys = {"default_prompt", "use_structured_outputs", "random_seed_policy"}
for key, value in frozen_config.items():
    if key in protocol_keys:
        setattr(settings, key, value)  # Restore frozen value
```

**Model Variants Preserved:**
- Temperature, max_tokens, reasoning, vision settings are **not** overwritten
- Allows testing different model configs within same experiment

---

## 10. Implicit Assumptions in V1

### Architectural Assumptions

1. **Single Provider Contract:** All providers (OpenRouter, llama.cpp) conform to OpenRouter API spec
2. **Sequential Execution:** No parallel/concurrent API calls (one item at a time)
3. **SQLite Only:** Database is always SQLite (in-memory or file-based)
4. **Python 3.10+:** Uses `|` union syntax, `ParamSpec`, `TypeVar`
5. **Async-Sync Hybrid:** API client is async, but execution engine supports both contexts

### Configuration Assumptions

1. **Environment Variable Priority:** System env > .env file > defaults
2. **API Key Security:** API key from `.env` is untrusted, must come from system env
3. **Null Semantics:** `None` means "don't send, use provider default"
4. **Experiment Immutability:** Protocol settings are frozen, model variants are not

### Data Model Assumptions

1. **Canonical Answers:** Database stores only canonical answer letters (A/B/C/D)
2. **Snapshot Immutability:** Question snapshots are never recreated once created
3. **Idempotency Key:** `(run_id, variant_id, snapshot_id)` uniquely identifies a response
4. **Run Status Progression:** `pending` → `running` → `completed`/`failed`/`partial_failed`

### Error Handling Assumptions

1. **Retryable vs Non-Retryable:** Clear distinction (auth errors never retry)
2. **Error Persistence:** Errors are first-class citizens (stored in `errors` table)
3. **Graceful Degradation:** Unknown models default to "no vision support"

### Logging Assumptions

1. **Crash Safety:** All log handlers flush after every write
2. **Console Restraint:** Console shows INFO+, file shows DEBUG+
3. **Component Isolation:** Each component has its own logger namespace

### Execution Assumptions

1. **No Implicit Execution:** Execution always requires explicit experiment/run context
2. **Planner Owns DB Reads:** ExecutionEngine does not access database
3. **ResultWriter Owns DB Writes:** ExecutionEngine does not persist results
4. **Determinism:** Same plan + same seed = same results (reproducible)

### Prompt Assumptions

1. **System Prompt Always Present:** Defaults to "You are a helpful assistant."
2. **User Prompt Instruction:** Must explicitly tell model to output letter (A/B/C/D)
3. **Prompt Inheritance:** Run prompts override experiment prompts

### Model Variant Assumptions

1. **Variant Identity:** Defined by `(model_id, reasoning_mode, vision, structured)`
2. **Global Variants:** Variants are not tied to specific experiments (TO-BE architecture)
3. **Variant Signature:** Hash of variant config for deduplication

### Randomization Assumptions

1. **Seed Policy:**
   - `None` = no randomization (natural order)
   - `"AUTO"` = unique seed per run
   - `int` = fixed seed for reproducibility
2. **Reverse Mapping:** Randomized answers mapped back to canonical for storage
3. **Correctness Evaluation:** Compared against randomized correct answer (model's view)

---

## Appendix: File Locations

| Component | File Path |
|-----------|-----------|
| API Client | `src_legacy/api/client.py` |
| Retry Handler | `src_legacy/api/retry.py` |
| Error Handler | `src_legacy/api/error_handler.py` |
| Response Parser | `src_legacy/api/parser.py` |
| Model Capabilities | `src_legacy/api/model_capabilities.py` |
| Execution Engine | `src_legacy/core/execution_engine.py` |
| Planner | `src_legacy/core/planner.py` |
| Result Writer | `src_legacy/core/result_writer.py` |
| Run Manager | `src_legacy/core/run_manager.py` |
| Settings | `src_legacy/utils/config.py` |
| Logging Config | `src_legacy/utils/logging_config.py` |
| Main Entry | `src_legacy/main.py` |

---

**Document Status:** Complete  
**Last Updated:** 2026-03-30  
**Maintainer:** V1 Codebase Analysis