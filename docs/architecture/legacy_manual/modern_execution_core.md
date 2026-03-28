# Modern Execution Core Architecture

**Document Type:** Architectural Design Specification  
**Version:** 2.0  
**Based On:** New CLI specification (comandos_simples.md v2.0)  
**Design Philosophy:** Simplicity, configurability, robustness, and best practices  
**Date:** March 2026

---

## Executive Summary

This document defines a completely reimagined execution core for the benchmark_llm system. The design addresses all limitations of the legacy system while embracing the simplified yet more powerful CLI specification. The architecture is built from first principles with focus on:

- **Simplicity** - Reduced cognitive load through clear abstractions
- **Configurability** - Hierarchical configuration with explicit overrides
- **Robustness** - Production-grade error handling, retry strategies, and recovery
- **Auditability** - Complete audit trail with cryptographic integrity
- **Performance** - Optimized API interactions, connection pooling, parallel execution

---

## 1. API Client Architecture (Redesigned)

### 1.1 Modern Request Construction

**Unified Message Builder:**
- Single `MessageBuilder` class with strategy pattern for content types
- **Text-only:** `build_text_message(content)` → `{"role": "user", "content": content}`
- **Multimodal:** `build_vision_message(text, image_path)` → Content array with text + image_url
- **Structured:** `build_structured_message(text, schema)` → Message with response_format hint
- Image encoding uses streaming base64 to avoid memory issues with large files
- Automatic image format detection with validation against supported types (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`)
- System prompts injected as separate message: `{"role": "system", "content": system_prompt}`

**Intelligent Payload Assembly:**
- Base payload: `model`, `messages` (always present)
- **Conditional parameters** (only included when explicitly configured):
  - `max_tokens`: When not NULL and not default
  - `temperature`: When not NULL and not default
  - `top_p`, `top_k`, `repeat_penalty`: Sampling parameters
  - `reasoning`: Only when effort ≠ "none" (per OpenRouter guidance)
  - `response_format`: When structured output enabled
- **Per-model URL override:** Each model can specify custom `base_url` for hybrid cloud/local execution
- **Null propagation:** Explicit `NULL` values treated as "use system default" (not sent to API)

**Connection Management (Modern Best Practices):**
- **Connection pooling:** Reuse connections across requests (unlike legacy `max_keepalive_connections=0`)
- **Configurable pool size:** Default 20 concurrent connections (tunable via .env)
- **HTTP/2 support:** When server supports it, enables multiplexing
- **Timeout strategy:**
  - Connection timeout: 30 seconds (fast failure for network issues)
  - Read timeout: 300 seconds (5 minutes, accommodates reasoning models)
  - Write timeout: 60 seconds (sufficient for request upload)
- **Base URL:** `https://openrouter.ai/api/v1` (default, overridable per-experiment and per-model)

### 1.2 Authentication Architecture

**Multi-Layer Authentication:**
- **Primary:** API key from environment variable (`OPENROUTER_API_KEY`)
- **Fallback:** API key from .env file (for development only)
- **Per-model override:** Custom API keys for different providers in same experiment
- **Key rotation support:** Multiple keys with automatic rotation on rate limit

**Authentication Flow:**
```
1. Check model-specific API key (if configured)
2. Check experiment-level API key (if configured)
3. Check environment variable OPENROUTER_API_KEY
4. Check .env file OPENROUTER_API_KEY
5. If all fail → AuthenticationError before execution starts
```

**Error Classification:**
- HTTP 401: `authentication_error` (non-retryable, immediate failure)
- HTTP 403: `authorization_error` (non-retryable, check permissions)
- Invalid key format: `invalid_key_format` (validation error, caught before API call)

**Security Enhancements:**
- API keys never logged (masked as `sk-****...****abcd`)
- Keys stored in memory only (never written to database)
- Automatic key rotation on 429 (rate limit) with multiple keys configured

### 1.3 Response Parsing (Enhanced)

**Multi-Stage Validation Pipeline:**

**Stage 1: HTTP Response Validation**
- Status code check (200 = success)
- Content-Type validation (`application/json` expected)
- Response size limits (prevent DoS via huge responses)

**Stage 2: Structure Validation**
- Required fields: `choices` (non-empty array), `choices[0].message`, `choices[0].message.content`
- Optional fields: `usage`, `model`, `id`, `created`
- Graceful degradation: Missing optional fields logged but don't fail

**Stage 3: Content Extraction**
- Primary: `choices[0].message.content`
- Fallback for reasoning models: `choices[0].message.reasoning_content` if content empty
- Structured output parsing: JSON schema validation when response_format used

**Token Usage Tracking (Comprehensive):**
```
input_tokens = usage.prompt_tokens
output_tokens = usage.completion_tokens
total_tokens = usage.total_tokens
cost = usage.cost (when available from OpenRouter)

reasoning_tokens = usage.completion_tokens_details.reasoning_tokens (when available)
effective_tokens = input_tokens + output_tokens + reasoning_tokens
```

**Finish Reason Classification (Expanded):**
| Finish Reason | Classification | Action |
|---------------|----------------|--------|
| `stop` | SUCCESS | Normal completion |
| `length` | PARTIAL | Response truncated, may need retry with higher max_tokens |
| `eos_token` | SUCCESS | Model reached end of sequence |
| `content_filter` | ERROR | Content policy violation, non-retryable |
| `function_call` | ERROR | Unexpected function call, non-retryable |
| `tool_calls` | ERROR | Unexpected tool calls, non-retryable |
| `provider_error` | RETRYABLE | Upstream provider failure, retry with backoff |
| `unknown` | WARNING | Log and treat as success if content present |

**Answer Extraction (ML-Enhanced Pattern Matching):**

**Confidence Levels (Unchanged from legacy, improved patterns):**
- `clear`: Single high-confidence pattern match (safe for automatic use)
- `ambiguous`: Multiple conflicting answers detected (requires manual review)
- `no_answer`: No answer patterns found (requires manual review)
- `low_confidence`: Only fallback pattern matched (requires manual review)

**Pattern Hierarchy (Improved with regex optimizations):**
1. **Explicit patterns** (highest confidence):
   - `\b(?:resposta|answer)\s*:\s*([A-D])\b`
   - `\b(?:alternativa\s+)?correta\s*(?:é|is)\s*([A-D])\b`
   - `\\boxed\{([A-D])\}` (LaTeX notation)

2. **Context patterns** (high confidence):
   - `\ba\s+resposta\s+(?:correta\s+)?(?:é|is)\s*([A-D])\b`
   - `\bthe\s+correct\s+answer\s+(?:is)?\s*([A-D])\b`
   - `\b(?:opção|option|letra|letter)\s*([A-D])\b`

3. **Structural patterns** (medium confidence):
   - `^\s*\*\*([A-D])\*\*` (Markdown bold at line start)
   - `^\s*([A-D])\s*[:\)]` (Letter followed by colon or paren at line start)
   - `^\s*\(\s*([A-D])\s*\)` (Parenthesized letter at line start)

4. **Fallback** (low confidence):
   - `\b([A-D])\b` (Any isolated letter, filtered for articles)

**Article Filtering (Enhanced):**
- Portuguese: Filters "A" when followed by nouns (alternativa, opção, resposta, letra, etc.)
- Spanish: Filters "A" when followed by nouns (alternativa, opción, respuesta, etc.)
- English: Filters "A" when used as article (not common in answer contexts)

**Latency Measurement (Granular):**
- `connection_latency_ms`: Time to establish connection
- `ttft_ms`: Time to first token (when streaming available)
- `total_latency_ms`: End-to-end request time
- `api_latency_ms`: Server-side processing time (from OpenRouter headers when available)

### 1.4 Error Surfacing (Production-Grade)

**Error Normalization Pipeline:**

**Step 1: HTTP Error Classification**
```
normalize_http_error(status_code, response_body):
  400 → bad_request (non-retryable)
  401 → authentication_error (non-retryable)
  403 → authorization_error (non-retryable)
  404 → not_found (non-retryable)
  429 → rate_limit_error (retryable with backoff)
  500 → server_error (retryable with backoff)
  502 → bad_gateway (retryable with backoff)
  503 → service_unavailable (retryable with backoff)
  504 → gateway_timeout (retryable with backoff)
  200 + error in body → provider_error (retryable)
```

**Step 2: Error Enrichment**
```
enrich_error(base_error, request_context, response_context):
  - Add model_id, experiment_id, run_id, question_id
  - Add request payload (masked for sensitive data)
  - Add response body (truncated if >10KB)
  - Add timestamp, retry_count, latency_ms
  - Add correlation_id for tracing
```

**Step 3: Error Serialization**
- JSON format with consistent schema
- Sensitive data masking (API keys, personal information)
- Truncation with flag for large payloads
- Stack traces included only in debug mode

**Error Extraction from Responses:**
- Handles wrapped responses (`{"_debug": {...}, "response": {...}}`)
- Handles unwrapped responses (direct API response)
- Checks for error indicators in message content
- Flags potential errors for manual review

---

## 2. Error Handling Strategy (Production-Ready)

### 2.1 Comprehensive Error Taxonomy

**API Errors (Provider-Side):**
- `invalid_response`: Malformed JSON, missing required fields
- `parsing_error`: Content extraction failures
- `provider_error`: Upstream model provider failures
- `rate_limit`: HTTP 429, quota exceeded
- `timeout`: Request exceeded timeout threshold
- `content_filter`: Content policy violation

**Network Errors (Transport-Side):**
- `connection_error`: DNS failures, refused connections, SSL errors
- `network_interruption`: Socket errors during request/response
- `proxy_error`: Proxy configuration issues

**Validation Errors (Client-Side):**
- `schema_validation`: Input data fails schema validation
- `configuration_error`: Invalid configuration (caught before execution)
- `missing_required_field`: Required field not provided

**Database Errors (Persistence-Side):**
- `constraint_violation`: Unique constraint, foreign key violations
- `connection_lost`: Database connection interrupted
- `disk_full`: Storage exhausted (critical alert)

**Execution Errors (Runtime-Side):**
- `timeout`: Item execution exceeded time limit
- `memory_limit`: Response exceeded memory limits
- `interrupted`: User interrupted execution (Ctrl+C)

### 2.2 Retryable vs Fatal Errors (Clear Classification)

**Retryable Errors (Transient, Automatic Retry):**
| Error Type | Retry Strategy | Max Attempts |
|------------|----------------|--------------|
| HTTP 429 (rate_limit) | Exponential backoff with jitter | 5 |
| HTTP 500 (server_error) | Exponential backoff with jitter | 3 |
| HTTP 502 (bad_gateway) | Exponential backoff with jitter | 3 |
| HTTP 503 (service_unavailable) | Exponential backoff with jitter | 3 |
| HTTP 504 (gateway_timeout) | Exponential backoff with jitter | 3 |
| `httpx.TimeoutException` | Exponential backoff with jitter | 3 |
| `httpx.ConnectError` | Exponential backoff with jitter | 3 |
| `httpx.NetworkError` | Exponential backoff with jitter | 3 |
| `provider_error` | Exponential backoff with jitter | 3 |

**Fatal Errors (Non-Retryable, Immediate Failure):**
| Error Type | Reason | User Action Required |
|------------|--------|---------------------|
| HTTP 400 (bad_request) | Client error, retry won't fix | Fix request payload |
| HTTP 401 (authentication) | Invalid credentials | Update API key |
| HTTP 403 (forbidden) | Permission denied | Check permissions/quotas |
| HTTP 404 (not_found) | Resource doesn't exist | Fix model ID or endpoint |
| `content_filter` | Policy violation | Modify prompt/content |
| `ValueError`, `TypeError`, `KeyError` | Programming errors | Fix code/configuration |
| `schema_validation` | Invalid input data | Fix input data |
| `configuration_error` | Invalid configuration | Fix configuration |

**Decision Logic (Implemented as State Machine):**
```
classify_error(error):
  if error.type in RETRYABLE_ERRORS:
    return RETRY
  
  if error.type in FATAL_ERRORS:
    return FAIL_IMMEDIATELY
  
  if error.type == "timeout":
    if retry_count < max_retries:
      return RETRY
    else:
      return FAIL_AFTER_RETRIES
  
  if error.type == "rate_limit":
    if has_alternative_api_key():
      return ROTATE_KEY_AND_RETRY
    else:
      return RETRY_WITH_BACKOFF
  
  return FAIL_IMMEDIATELY  # Default to safe behavior
```

### 2.3 Error Propagation (End-to-End Visibility)

**Execution Engine Level:**
- Catch all exceptions at item boundary
- Classify error (retryable vs fatal)
- Attempt retry if applicable
- On final failure: Create `ExecutionResult` with status="failure"
- Capture: `error_type`, `error_message`, `error_details`, `retry_count`, `stack_trace` (debug only)

**Result Writer Level:**
- Failed results written to `errors` table (append-only)
- Error record includes:
  - Identifiers: `run_id`, `variant_id`, `snapshot_id`, `question_id`
  - Classification: `error_type`, `error_category` (retryable/fatal)
  - Details: `error_message`, `error_context` (JSON)
  - Metadata: `retry_count`, `latency_ms`, `timestamp`
  - Correlation: `correlation_id` for distributed tracing

**Run Status Updates (State Machine):**
```
Run Status Transitions:
  pending → running (execution started)
  running → completed (all items succeeded)
  running → partial_failed (some succeeded, some failed)
  running → failed (all items failed)
  running → pending (user interrupted, can resume)
  
  NO transitions from: completed, failed (terminal states)
```

**CLI Output (Multi-Channel):**
- **Console (Rich):** Progress bars, color-coded status, real-time updates
- **File Logs:** Complete audit trail with DEBUG level detail
- **Error Summary:** Post-execution report with breakdown by category, type, model

---

## 3. Retry Behavior (Modern Best Practices)

### 3.1 Retry Configuration (Hierarchical)

**Configuration Hierarchy:**
```
CLI --retry-policy (highest priority, execution-specific)
  ↓
Experiment.retry_policy (experiment-level override)
  ↓
.env RETRY_POLICY (global default)
  ↓
System default (max_retries=3, base_delay=1.0, max_delay=60.0)
```

**RetryConfig Schema:**
```yaml
max_retries: integer (default: 3)
base_delay: float in seconds (default: 1.0)
max_delay: float in seconds (default: 60.0)
exponential_base: float (default: 2.0)
jitter: boolean (default: true)  # NEW: Adds randomness to prevent thundering herd
retryable_status_codes: list[int] (default: [429, 500, 502, 503, 504])
retryable_error_types: list[str] (default: ["timeout", "connection_error", "network_error"])
```

**Per-Error-Type Configuration (Advanced):**
```yaml
error_specific_retries:
  rate_limit:
    max_retries: 5
    base_delay: 2.0
    max_delay: 120.0
  server_error:
    max_retries: 3
    base_delay: 1.0
    max_delay: 60.0
  timeout:
    max_retries: 2
    base_delay: 5.0
    max_delay: 30.0
```

### 3.2 Retry Trigger Conditions (Explicit)

**Automatic Retry Triggers:**
1. HTTP 429 response (rate limit) → Retry with backoff + optional key rotation
2. HTTP 5xx response (server error) → Retry with backoff
3. `httpx.TimeoutException` → Retry with backoff
4. `httpx.ConnectError` → Retry with backoff
5. `httpx.NetworkError` → Retry with backoff
6. `provider_error` in response body → Retry with backoff

**Conditional Retry (Circuit Breaker Pattern):**
```
if consecutive_failures >= circuit_breaker_threshold:
  open_circuit()  # Stop retrying, fail fast
  wait(cooldown_period)
  half_open_circuit()  # Allow one test request
  if test_request_succeeds:
    close_circuit()  # Resume normal operation
  else:
    open_circuit()  # Continue cooldown
```

**Retry Decision Flow (State Machine):**
```
on_error(error, retry_count):
  if not is_retryable(error):
    return FAIL_IMMEDIATELY
  
  if retry_count >= max_retries:
    return FAIL_AFTER_EXHAUSTING_RETRIES
  
  if circuit_breaker_is_open():
    return FAIL_FAST (circuit breaker tripped)
  
  delay = calculate_backoff(retry_count, error.type)
  log_retry_attempt(retry_count, delay, error)
  wait(delay)
  return RETRY
```

### 3.3 Backoff Strategy (Exponential with Jitter)

**Improved Backoff Formula (with Jitter):**
```
calculate_backoff(attempt, error_type):
  base = get_base_delay(error_type)
  exponential = base * (exponential_base ^ attempt)
  capped = min(exponential, max_delay)
  
  if jitter_enabled:
    # Add up to 25% randomness to prevent thundering herd
    jitter_range = capped * 0.25
    jitter = random.uniform(-jitter_range, +jitter_range)
    return capped + jitter
  else:
    return capped
```

**Delay Sequence (with Jitter, example for rate_limit):**
| Attempt | Base Delay | Exponential | Capped | With Jitter (±25%) |
|---------|------------|-------------|--------|-------------------|
| 0 | 2.0s | 2.0s | 2.0s | 1.5s - 2.5s |
| 1 | 2.0s | 4.0s | 4.0s | 3.0s - 5.0s |
| 2 | 2.0s | 8.0s | 8.0s | 6.0s - 10.0s |
| 3 | 2.0s | 16.0s | 16.0s | 12.0s - 20.0s |
| 4 | 2.0s | 32.0s | 32.0s | 24.0s - 40.0s |
| 5+ | 2.0s | 64.0s | 60.0s (capped) | 45.0s - 60.0s |

**Why Jitter Matters:**
- Prevents "thundering herd" problem (all clients retry simultaneously)
- Reduces load spikes on recovering services
- Industry standard (AWS, Google Cloud, Azure all use jitter)

**Logging (Transparent Retry Behavior):**
```
INFO: Retry attempt 1/3 for model openai/gpt-4 after 2.3s delay (rate_limit)
INFO: Retry attempt 2/3 for model openai/gpt-4 after 4.1s delay (rate_limit)
INFO: Request succeeded after 2 retry attempts
```

### 3.4 Retry Execution Flow (Robust)

**RetryHandler with Circuit Breaker:**
```
execute_with_retry(func, error_context):
  retry_count = 0
  last_error = None
  
  while retry_count <= max_retries:
    if circuit_breaker_is_open():
      raise CircuitBreakerOpenError()
    
    try:
      result = await func()
      
      if retry_count > 0:
        log_success_after_retries(retry_count)
      
      close_circuit()  # Reset circuit breaker on success
      return result
    
    except Exception as exc:
      last_error = exc
      record_failure(exc)  # For circuit breaker
      
      if not is_retryable(exc):
        log_non_retryable_error(exc)
        raise
      
      retry_count += 1
      
      if retry_count > max_retries:
        log_max_retries_exceeded(retry_count, exc)
        raise MaxRetriesExceededError(last_error)
      
      delay = calculate_backoff(retry_count - 1, exc.type)
      log_retry_attempt(retry_count, max_retries, delay, exc)
      
      await asyncio.sleep(delay)
  
  # Unreachable, but included for type safety
  raise MaxRetriesExceededError(last_error)
```

**Circuit Breaker State Machine:**
```
States:
  CLOSED: Normal operation, requests flow through
  OPEN: Circuit tripped, requests fail fast
  HALF_OPEN: Testing if service recovered
  
Transitions:
  CLOSED → OPEN: When failure_threshold exceeded
  OPEN → HALF_OPEN: After cooldown_period expires
  HALF_OPEN → CLOSED: If test request succeeds
  HALF_OPEN → OPEN: If test request fails
```

**Error Preservation:**
- `MaxRetriesExceededError` includes `last_exception` for debugging
- Full retry history logged (timestamps, delays, error messages)
- Correlation ID tracks retry chain across logs

---

## 4. Configuration Architecture (Hierarchical & Explicit)

### 4.1 Configuration Hierarchy (Clear Precedence)

**Three-Tier Hierarchy:**
```
┌─────────────────────────────────────────┐
│  RUN (highest priority, execution-time) │
│  - seed (immutable after creation)      │
│  - system_prompt (immutable)            │
│  - user_prompt (immutable)              │
└─────────────────────────────────────────┘
           ↓ inherits from
┌─────────────────────────────────────────┐
│  EXPERIMENT (mid priority, design-time) │
│  - models[] (with per-model config)     │
│  - questions (snapshots)                │
│  - seed (default for runs)              │
│  - system_prompt (default for runs)     │
│  - user_prompt (default for runs)       │
│  - retry_policy                         │
│  - base_url                             │
└─────────────────────────────────────────┘
           ↓ inherits from
┌─────────────────────────────────────────┐
│  .env (lowest priority, global default) │
│  - MODELS_DEFAULT_FOR_EXPERIMENTS       │
│  - QUESTIONS_DATASET_PATH               │
│  - QUESTIONS_STATUS_ADD/EXCLUDE         │
│  - RUN_RESPONSES_SEED                   │
│  - SYSTEM_PROMPT                        │
│  - USER_PROMPT                          │
│  - RETRY_POLICY                         │
│  - OPENROUTER_API_KEY                   │
└─────────────────────────────────────────┘
           ↓ falls back to
┌─────────────────────────────────────────┐
│  SYSTEM DEFAULTS (hardcoded fallbacks)  │
│  - Use all questions if none specified  │
│  - No filtering (where/exclude)         │
│  - seed=None (no randomization)         │
│  - No prompts (don't send to API)       │
│  - Model params: use provider defaults  │
└─────────────────────────────────────────┘
```

**Configuration Resolution Algorithm:**
```
resolve_config_value(config_name, run, experiment, env):
  # Priority 1: Run-level (if exists and not NULL)
  if run and has_value(run[config_name]) and run[config_name] != "NULL":
    return run[config_name]
  
  # Priority 2: Experiment-level (if exists and not NULL)
  if experiment and has_value(experiment[config_name]) and experiment[config_name] != "NULL":
    return experiment[config_name]
  
  # Priority 3: .env-level (if exists and not NULL)
  if env and has_value(env[config_name]) and env[config_name] != "NULL":
    return env[config_name]
  
  # Priority 4: System default
  return SYSTEM_DEFAULTS[config_name]
```

**NULL Semantics (Explicit Default Usage):**
- `NULL` (case-insensitive) = "Use system default"
- Treated as if value was never specified
- Allows overriding .env defaults with system defaults
- Example: `--reasoning NULL` → Don't send reasoning field (use model default)

### 4.2 Model Configuration (Per-Model Granularity)

**Model Identity Parameters (Immutable):**
- `model_id`: Provider/model identifier (e.g., `openai/gpt-4`, `local/llama-3`)
- `vision_enabled`: Boolean (true/false/NULL)
- `structured_enabled`: Boolean (true/false/NULL)
- `reasoning_effort`: none/minimal/low/medium/high/xhigh

**Model Execution Parameters (Mutable per-request):**
- `max_tokens`: Maximum completion tokens
- `temperature`: Sampling temperature (0.0-2.0)
- `top_p`: Nucleus sampling (0.0-1.0)
- `top_k`: Top-k sampling (integer)
- `repeat_penalty`: Repetition penalty (float)

**Per-Model URL Override:**
```yaml
models:
  - model_id: openai/gpt-4
    base_url: https://openrouter.ai/api/v1  # Use OpenRouter
  - model_id: local/llama-3
    base_url: http://localhost:8080/v1  # Use local server
  - model_id: anthropic/claude-3
    base_url: https://openrouter.ai/api/v1  # Use OpenRouter
```

**Configuration Validation:**
- Validate at experiment creation time (fail fast)
- Check model compatibility (e.g., vision requires vision-capable model)
- Warn on suspicious configurations (e.g., temperature=0 with top_p=1.0)

### 4.3 Question Configuration (Flexible Filtering)

**Question Specification Formats:**
- Individual: `"1"` → Question 1
- Comma-separated: `"1, 3, 5"` → Questions 1, 3, 5
- Range: `"1-10"` → Questions 1 through 10
- Mixed: `"1, 3-5, 10"` → Questions 1, 3, 4, 5, 10

**Metadata Filtering:**
```
--questions "1-50" --where status=valid has_image=false
  → Questions 1-50 WHERE status='valid' AND has_image='false'

--questions "1-100" --exclude status=annulled has_image=true
  → Questions 1-100 WHERE NOT (status='annulled' OR has_image='true')
```

**Filter Resolution:**
```
resolve_questions(experiment_config, env_config):
  # Priority 1: Experiment-level questions
  if experiment.questions:
    question_ids = parse_questions(experiment.questions)
  # Priority 2: .env QUESTIONS_DATASET_PATH
  elif env.questions_dataset_path:
    question_ids = load_all_questions(env.questions_dataset_path)
  # Priority 3: System default (all questions)
  else:
    question_ids = load_all_questions(SYSTEM_DEFAULT_PATH)
  
  # Apply where filter
  if experiment.where or env.where:
    question_ids = apply_where_filter(question_ids, experiment.where or env.where)
  
  # Apply exclude filter
  if experiment.exclude or env.exclude:
    question_ids = apply_exclude_filter(question_ids, experiment.exclude or env.exclude)
  
  return question_ids
```

### 4.4 Seed Configuration (Reproducible Randomization)

**Seed Values:**
- `EM BRANCO` (blank) or `NULL`: No randomization (original A,B,C,D order)
- `AUTO`: Automatic seed generation (hash of run_id for uniqueness)
- `<integer>`: Fixed seed for reproducibility (e.g., 42)

**Seed Hierarchy:**
```
RUN.seed (immutable after creation)
  ↓
EXPERIMENT.seed (default for new runs)
  ↓
.env RUN_RESPONSES_SEED (global default)
  ↓
SYSTEM DEFAULT: None (no randomization)
```

**Randomization Behavior:**
```
if seed is None:
  # No randomization
  execute_questions_in_natural_order()
elif seed == "AUTO":
  # Generate unique seed per run
  effective_seed = hash(run_id)
  randomize_with_seed(effective_seed)
else:
  # Use fixed seed
  randomize_with_seed(seed)
```

---

## 5. Database Architecture (Audit-Trail Focused)

### 5.1 Immutability Principles

**Append-Only Design:**
- All tables are append-only (no UPDATE, no DELETE)
- Changes recorded as new rows with version/timestamp
- Historical state always queryable

**Cryptographic Integrity:**
- Each record includes `created_at` timestamp (UTC)
- Sequential IDs prevent reordering
- Optional: SHA-256 hash of previous record for chain integrity (blockchain-inspired)

**Audit Trail Tables:**
- `experiment_audit`: All experiment changes
- `run_audit`: All run state transitions
- `response_audit`: All response modifications (e.g., manual review)

### 5.2 Core Schema (Normalized)

**Experiments Table:**
```sql
CREATE TABLE experiments (
  experiment_id TEXT PRIMARY KEY,  -- UUID format
  name TEXT UNIQUE NOT NULL,
  config_hash TEXT NOT NULL,  -- SHA-256 of frozen config
  config_json TEXT NOT NULL,  -- Full configuration snapshot
  description TEXT,
  system_prompt_template TEXT,
  user_prompt_template TEXT,
  retry_policy TEXT,  -- JSON
  base_url TEXT,
  created_at TEXT NOT NULL,  -- ISO 8601 UTC
  created_by TEXT,  -- User identifier
  status TEXT NOT NULL DEFAULT 'active'  -- active/archived
);
```

**Runs Table:**
```sql
CREATE TABLE runs (
  run_id TEXT PRIMARY KEY,  -- UUID format
  experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
  seed INTEGER,  -- NULL = no randomization
  system_prompt TEXT,
  user_prompt TEXT,
  status TEXT NOT NULL DEFAULT 'pending',  -- pending/running/completed/failed/partial_failed
  started_at TEXT,
  finished_at TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT
);
```

**Model Variants Table:**
```sql
CREATE TABLE model_variants (
  variant_id TEXT PRIMARY KEY,  -- UUID format
  experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
  model_id TEXT NOT NULL,
  reasoning_effort TEXT,  -- none/minimal/low/medium/high/xhigh
  max_tokens INTEGER,
  temperature REAL,
  top_p REAL,
  top_k INTEGER,
  repeat_penalty REAL,
  vision_enabled INTEGER,  -- 0=false, 1=true, NULL=default
  structured_enabled INTEGER,
  base_url TEXT,  -- Per-model URL override
  created_at TEXT NOT NULL
);
```

**Question Snapshots Table:**
```sql
CREATE TABLE question_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
  question_id TEXT NOT NULL,
  question_payload TEXT NOT NULL,  -- JSON (stem, options, answer_key, image_path)
  created_at TEXT NOT NULL
);
```

**Run-Model Association Table:**
```sql
CREATE TABLE run_models (
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  variant_id TEXT NOT NULL REFERENCES model_variants(variant_id),
  status TEXT NOT NULL DEFAULT 'pending',  -- pending/running/completed/failed/partial_failed
  started_at TEXT,
  finished_at TEXT,
  PRIMARY KEY (run_id, variant_id)
);
```

**Responses Table (Append-Only):**
```sql
CREATE TABLE responses (
  response_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  variant_id TEXT NOT NULL REFERENCES model_variants(variant_id),
  snapshot_id INTEGER NOT NULL REFERENCES question_snapshots(snapshot_id),
  question_id TEXT NOT NULL,
  model_id TEXT NOT NULL,
  iteration INTEGER NOT NULL DEFAULT 1,
  
  -- Response content
  selected_answer TEXT,  -- A/B/C/D or NULL
  manual_answer TEXT,  -- Set by manual review
  response_text TEXT NOT NULL,
  is_correct INTEGER,  -- 0=false, 1=true, NULL=unknown
  
  -- Status tracking
  status TEXT NOT NULL DEFAULT 'success',  -- success/error
  finish_reason TEXT,  -- stop/length/content_filter/etc.
  error_details TEXT,  -- JSON (if error)
  
  -- Review tracking
  parse_confidence TEXT NOT NULL,  -- clear/ambiguous/no_answer/low_confidence
  needs_review INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
  review_status TEXT DEFAULT 'auto',  -- auto/manual/skipped
  reviewed_at TEXT,
  reviewed_by TEXT,
  
  -- Metrics
  latency_ms INTEGER NOT NULL,
  input_tokens INTEGER,
  response_tokens INTEGER,
  total_tokens INTEGER,
  reasoning_tokens INTEGER,
  effective_tokens INTEGER,
  cost REAL,  -- In credits (from OpenRouter)
  
  -- Raw data (for debugging)
  raw_response_json TEXT,
  
  -- Audit trail
  created_at TEXT NOT NULL,
  correlation_id TEXT  -- For distributed tracing
);
```

**Errors Table (Append-Only):**
```sql
CREATE TABLE errors (
  error_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(run_id),
  variant_id TEXT NOT NULL REFERENCES model_variants(variant_id),
  snapshot_id INTEGER NOT NULL REFERENCES question_snapshots(snapshot_id),
  question_id TEXT NOT NULL,
  
  -- Error classification
  error_type TEXT NOT NULL,  -- rate_limit/server_error/etc.
  error_category TEXT NOT NULL,  -- retryable/fatal
  error_message TEXT NOT NULL,
  error_context TEXT,  -- JSON (request/response details)
  
  -- Retry tracking
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL,
  
  -- Audit trail
  created_at TEXT NOT NULL,
  correlation_id TEXT
);
```

### 5.3 Idempotency Guarantees

**Uniqueness Constraints:**
```sql
-- Prevent duplicate responses for same (run, variant, snapshot)
CREATE UNIQUE INDEX idx_responses_unique 
ON responses(run_id, variant_id, snapshot_id);

-- Prevent duplicate errors for same (run, variant, snapshot)
CREATE UNIQUE INDEX idx_errors_unique 
ON errors(run_id, variant_id, snapshot_id);
```

**Idempotent Write Logic:**
```
write_response(response):
  # Check if already exists (idempotency key)
  existing = db.query(
    "SELECT 1 FROM responses WHERE run_id=? AND variant_id=? AND snapshot_id=?",
    response.run_id, response.variant_id, response.snapshot_id
  )
  
  if existing:
    log_debug("Response already exists, skipping (idempotent)")
    return SKIPPED
  
  # Insert new response
  db.execute("INSERT INTO responses ...", response)
  log_info("Response written successfully")
  return INSERTED
```

**Partial Re-execution Support:**
- Query for missing responses before execution
- Skip already-answered combinations
- Resume interrupted runs without duplication

---

## 6. Component Architecture (Clean Separation)

### 6.1 Component Responsibilities

**CLI Layer:**
- Parse command-line arguments
- Validate configuration
- Initialize database
- Route commands to appropriate handlers
- Display progress and results

**Experiment Manager:**
- Create/update experiments
- Manage models and variants
- Manage question snapshots
- Validate experiment configuration

**Run Manager:**
- Create/update runs
- Manage run-model associations
- Track run status
- Handle run lifecycle (pending → running → completed/failed)

**Planner:**
- Build ExecutionPlan from database state
- Resolve all configuration (hierarchy: Run → Experiment → .env → System)
- Deduplicate items (exclude already-answered)
- Generate immutable, self-contained plan

**Execution Engine:**
- Execute ExecutionPlan (pure function, no side effects)
- Make API calls with retry logic
- Parse responses
- Return ExecutionResults (pure data, no persistence)
- NO database access

**Result Writer:**
- Persist ExecutionResults to database
- Update run and run_model status
- Ensure idempotency
- NO API calls, NO execution

**Review UI:**
- Query responses needing review (needs_review=TRUE)
- Display interactive review interface
- Save manual classifications
- Track review statistics

### 6.2 Data Flow (End-to-End)

**Execution Flow:**
```
User Command (CLI)
  ↓
Validate Configuration
  ↓
Initialize Database
  ↓
Planner.build_plan(experiment_name, run_name, filters)
  ↓
ExecutionPlan (immutable, self-contained)
  ↓
ExecutionEngine.execute(plan)
  ↓
List[ExecutionResult] (pure data)
  ↓
ResultWriter.write_results(plan, results)
  ↓
Database (responses, errors, run status)
  ↓
CLI Output (progress, summary)
```

**Request Path (Detailed):**
1. **Planner reads from database:**
   - Experiment config
   - Run config
   - Model variants
   - Question snapshots
   - Existing responses (for deduplication)

2. **Planner builds ExecutionPlan:**
   - Resolve configuration hierarchy
   - Apply filters (models, questions)
   - Deduplicate items
   - Generate plan_id

3. **ExecutionEngine iterates PlanItems:**
   - For each item:
     - Build prompt (system + user + question)
     - Apply answer randomization (if seed set)
     - Build API request payload
     - Call API with retry logic
     - Parse response (answer extraction, token counting)
     - Build ExecutionResult

4. **ResultWriter persists results:**
   - For each result:
     - Check idempotency (already exists?)
     - Write to `responses` or `errors` table
     - Update run status
     - Update run_model status

### 6.3 Separation of Concerns (Strict)

**ExecutionEngine (Pure Execution):**
- ✅ Executes API calls
- ✅ Applies retry logic
- ✅ Parses responses
- ✅ Returns results
- ❌ NO database access
- ❌ NO persistence
- ❌ NO configuration resolution
- ❌ NO scope decisions

**ResultWriter (Pure Persistence):**
- ✅ Writes to database
- ✅ Updates status
- ✅ Ensures idempotency
- ❌ NO execution
- ❌ NO API calls
- ❌ NO scope decisions
- ❌ NO identity creation

**Planner (Pure Planning):**
- ✅ Reads database
- ✅ Resolves configuration
- ✅ Builds execution plan
- ✅ Deduplicates items
- ❌ NO execution
- ❌ NO persistence (except plan audit)

---

## 7. Design Principles (Modern Best Practices)

### 7.1 Immutability

**Immutable Entities:**
- ExecutionPlan: Immutable after creation
- Question Snapshots: Immutable after creation
- Model Variants: Immutable after creation (create new variant for changes)
- Experiment Config: Frozen (hash ensures integrity)
- Run Config: Immutable after creation (seed, prompts)

**Mutable State (Explicit):**
- Run Status: pending → running → completed/failed
- Response Review Status: auto → manual
- Experiment Status: active → archived

**Benefits:**
- Reproducibility: Same input → same output
- Auditability: Full history preserved
- Debugging: State at time of execution always available
- Concurrency: No race conditions on immutable data

### 7.2 Explicit Configuration

**No Implicit Behavior:**
- All configuration resolved before execution
- No fallback to globals during execution
- NULL explicitly means "use system default"
- Configuration hierarchy documented and enforced

**Fail Fast:**
- Validate configuration at creation time
- Catch errors before execution starts
- Clear error messages with actionable guidance

**Self-Contained Plans:**
- ExecutionPlan includes all resolved configuration
- No external dependencies during execution
- Serializable for audit/replay

### 7.3 Idempotency

**Idempotent Operations:**
- Response writes: Same input → same database state
- Error writes: Same input → same database state
- Plan execution: Re-execution skips completed items

**Benefits:**
- Safe retries: No duplicate results
- Partial re-execution: Resume interrupted runs
- Crash recovery: No manual cleanup needed

### 7.4 Reproducibility

**Reproducible Execution:**
- Seeded randomization (same seed → same randomization)
- Frozen experiment configuration (hash ensures integrity)
- Complete audit trail (reconstruct execution context)
- Serializable plans (replay exact execution)

**Audit Trail:**
- All state changes logged
- Correlation IDs for distributed tracing
- Timestamps for ordering (not wall clock time)

### 7.5 Observability

**Multi-Channel Logging:**
- Console (Rich): Real-time progress, color-coded status
- File Logs: Complete audit trail (DEBUG level)
- Structured Logs: JSON format for log aggregation

**Metrics:**
- Latency (connection, TTFT, total)
- Token usage (input, output, reasoning, effective)
- Error rates (by type, model, question)
- Retry statistics (attempts, success rate)

**Tracing:**
- Correlation IDs across components
- Request/response logging (masked for sensitivity)
- Distributed tracing support (OpenTelemetry-compatible)

### 7.6 Robustness

**Error Handling:**
- Comprehensive error taxonomy
- Clear retryable vs fatal classification
- Circuit breaker pattern for cascading failures
- Graceful degradation (partial results better than no results)

**Retry Strategy:**
- Exponential backoff with jitter
- Per-error-type configuration
- API key rotation on rate limit
- Maximum protection against thundering herd

**Recovery:**
- Interruptible execution (Ctrl+C saves progress)
- Resume from interruption (no duplication)
- Database transactions (atomic writes)
- Backup and restore support

---

## 8. Summary

The modern execution core represents a complete reimagining of the benchmark_llm system, addressing all limitations of the legacy implementation while embracing the simplified yet more powerful CLI specification.

**Key Improvements:**

1. **Hierarchical Configuration** - Clear three-tier hierarchy (Run → Experiment → .env → System) with explicit NULL semantics

2. **Production-Grade Error Handling** - Comprehensive error taxonomy, circuit breaker pattern, exponential backoff with jitter

3. **Immutable Audit Trail** - Append-only database design with cryptographic integrity guarantees

4. **Clean Separation of Concerns** - ExecutionEngine (pure execution), ResultWriter (pure persistence), Planner (pure planning)

5. **Per-Model Flexibility** - Hybrid cloud/local execution with per-model URL overrides

6. **Idempotent Operations** - Safe retries, partial re-execution, crash recovery without duplication

7. **Observability** - Multi-channel logging, metrics, distributed tracing support

8. **Reproducibility** - Seeded randomization, frozen configurations, serializable plans

This architecture is designed for production use at scale, with focus on reliability, auditability, and maintainability.
