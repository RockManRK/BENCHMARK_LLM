# Debugging Guide

This guide explains how to use the debugging and error handling features in `benchmark_llm`.

## Overview

The benchmark tool provides two main debugging capabilities:

1. **Error Normalization**: Consistent error details for all failures
2. **Debug Mode**: Capture request/response payloads for inspection

## Error Handling

### Automatic Error Details

All errors during benchmark execution automatically populate the `error_details` column in the `responses` table. This field is **never NULL** when `status='error'`.

#### Error Types

The system normalizes errors into these categories:

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `rate_limit` | 429 | API rate limit exceeded |
| `authentication` | 401 | Invalid API key |
| `forbidden` | 403 | Access forbidden |
| `not_found` | 404 | Model/endpoint not found |
| `server_error` | 500 | Internal server error |
| `bad_gateway` | 502 | Bad gateway from provider |
| `service_unavailable` | 503 | Service temporarily unavailable |
| `provider_error` | 200 | Error in response body (provider-specific) |
| `timeout` | N/A | Request timed out |
| `request_error` | N/A | Network/request error |
| `unexpected_error` | N/A | Unexpected exception |

### Inspecting Error Details

Error details are stored as JSON in the `error_details` column:

```sql
SELECT 
    question_id,
    error_type,
    json_extract(error_details, '$.message') as error_message,
    json_extract(error_details, '$.http_status') as http_status
FROM responses
WHERE status = 'error';
```

Example error_details JSON:
```json
{
  "error_type": "rate_limit",
  "http_status": 429,
  "message": "Rate limit exceeded",
  "raw_body": {
    "error": {
      "message": "Rate limit exceeded"
    }
  }
}
```

## Debug Mode

Debug mode captures the complete request payload and upstream response body for inspection.

### Enabling Debug Mode

**⚠️ WARNING: Debug mode is BLOCKED in EXPERIMENT mode to prevent data leakage and ensure clean experimental conditions.**

Set the environment variable in your `.env` file:

```env
OPENROUTER_DEBUG_ENABLED=true
```

Or pass it programmatically:

```python
from src.utils.config import Settings

settings = Settings(
    openrouter_api_key="your_key",
    execution_mode="dev",  # Must be DEV, not EXPERIMENT
    openrouter_debug_enabled=True,
)
```

### What Is Captured

When debug mode is enabled, the following data is stored in `raw_response_json`:

```json
{
  "_debug": {
    "request_payload": {
      "model": "openai/gpt-4",
      "messages": [...],
      "max_tokens": 16384,
      "temperature": 0.0,
      "debug": {
        "echo_upstream_body": true
      }
    },
    "upstream_body": {
      "provider": "OpenAI",
      "provider_response": {...}
    }
  },
  "response": {
    "id": "chatcmpl-123",
    "choices": [...],
    "usage": {...}
  }
}
```

## Debug Data Structure

### Conceptual Separation

The debug data captures two distinct payloads:

| Field | Description | Direction |
|-------|-------------|-----------|
| `_debug.request_payload` | What **your system** sent to OpenRouter | You → OpenRouter |
| `_debug.upstream_body` | What **OpenRouter** sent to the upstream provider | OpenRouter → Provider |

**Why this matters:**
- `request_payload`: Shows your exact request (messages, parameters, schema)
- `upstream_body`: Shows how OpenRouter transformed your request for the specific provider

**Example scenario:**
```json
{
  "_debug": {
    "request_payload": {
      "model": "openai/gpt-4",
      "messages": [...],
      "temperature": 0.0
    },
    "upstream_body": {
      "provider": "OpenAI",
      "provider_request": {
        "model": "gpt-4-0613",
        "messages": [...],
        "temperature": 0.0
      }
    }
  }
}
```

In this example:
- You requested `openai/gpt-4` (OpenRouter model ID)
- OpenRouter transformed to `gpt-4-0613` (actual provider model ID)

### Important Notes

**`_debug` is internal metadata only.** Downstream consumers should access only `response` for model data:

```python
# Correct: Access response data
response_text = api_response["response"]["choices"][0]["message"]["content"]

# Incorrect: Don't use _debug for model data
# _debug is for debugging/inspection only
```

The wrapper structure ensures:
- **Compatibility**: Code works with or without debug enabled
- **Clarity**: Clear separation between debug metadata and response data
- **Safety**: Debug data doesn't interfere with response processing

### Inspecting Debug Data

Use SQLite's JSON functions to extract debug information:

```sql
-- Extract request payload
SELECT 
    question_id,
    json_extract(raw_response_json, '$._debug.request_payload.model') as model,
    json_extract(raw_response_json, '$._debug.request_payload.max_tokens') as max_tokens
FROM responses
WHERE json_extract(raw_response_json, '$._debug') IS NOT NULL;

-- Extract upstream body (provider-specific data)
SELECT 
    question_id,
    json_extract(raw_response_json, '$._debug.upstream_body') as upstream_body
FROM responses
WHERE json_extract(raw_response_json, '$._debug.upstream_body') IS NOT NULL;

-- Export full debug data for a specific question
SELECT 
    json_extract(raw_response_json, '$._debug') as debug_data
FROM responses
WHERE question_id = 'Q001';
```

### Debug Mode Behavior

| Mode | Debug Allowed | Notes |
|------|---------------|-------|
| `TEST` | ✅ Yes | In-memory, no persistence |
| `DEV` | ✅ Yes | Full debug capabilities |
| `EXPERIMENT` | ⚠️ **WARNING** | Emits warning and ignores flag (no ValueError) |

**Behavior in EXPERIMENT mode:**

When debug is enabled in EXPERIMENT mode, the system:
1. ✅ Emits a warning in the logs
2. ✅ Sets `openrouter_debug_enabled` to `False` silently
3. ✅ Continues execution normally (no hard failure)
4. ❌ Does NOT raise `ValueError`

This prevents hard failures in long-running pipelines while still ensuring debug mode is not used in experiments.

Example:
```python
Settings(
    execution_mode=ExecutionMode.EXPERIMENT,
    experiment_name="my_experiment",
    openrouter_debug_enabled=True,  # Emits warning, sets to False, continues
)
```

Warning message:
```
WARNING: openrouter_debug_enabled is BLOCKED in EXPERIMENT mode. 
Debug flag will be ignored. Debug mode cannot be used for experimental runs. 
Execution will continue without debug.
```

## Use Cases

### Debugging API Errors

When you encounter unexpected API errors:

1. Enable debug mode: `OPENROUTER_DEBUG_ENABLED=true`
2. Run the benchmark
3. Query the error details:

```sql
SELECT 
    question_id,
    json_extract(error_details, '$.error_type') as error_type,
    json_extract(error_details, '$.message') as message,
    json_extract(raw_response_json, '$._debug.request_payload') as request
FROM responses
WHERE status = 'error';
```

### Analyzing Provider Behavior

To understand how OpenRouter communicates with upstream providers:

1. Enable debug mode in DEV mode
2. Run a small test: `python -m src.main --models openai/gpt-4 --questions Q001-Q005`
3. Inspect upstream_body:

```sql
SELECT 
    json_extract(raw_response_json, '$._debug.upstream_body') as provider_data
FROM responses
LIMIT 1;
```

### Reproducing Issues

When reporting issues or debugging locally:

1. Enable debug mode
2. Run the failing scenario
3. Export the full raw_response_json:

```sql
SELECT 
    question_id,
    raw_response_json
FROM responses
WHERE question_id = 'Q001';
```

4. Save to file for analysis:

```bash
sqlite3 data/benchmark.db "SELECT raw_response_json FROM responses WHERE question_id='Q001'" > debug_output.json
```

## Security Warnings

### ⚠️ Production Use

**DO NOT enable debug mode in production environments.**

Debug mode captures:
- Complete request payloads (including prompts)
- Upstream provider responses
- Potentially sensitive data

### ⚠️ Data Privacy

When sharing debug data:
- Review captured prompts for sensitive information
- Redact API keys and credentials
- Consider data privacy regulations

### ⚠️ Performance Impact

Debug mode adds overhead:
- Larger payloads stored in database
- Additional processing for debug extraction
- Increased database size

Use only for debugging, not for production benchmarks.

## Troubleshooting

### Debug Not Working

**Problem**: Debug data not appearing in `raw_response_json`

**Solutions**:
1. Verify `OPENROUTER_DEBUG_ENABLED=true` in `.env`
2. Check you're not in EXPERIMENT mode
3. Restart the application after changing settings
4. Verify settings loaded: `print(settings.openrouter_debug_enabled)`

### Error Details NULL

**Problem**: `error_details` is NULL for error responses

**Solutions**:
1. This should not happen - all errors populate `error_details`
2. Check logs for unexpected exceptions
3. Verify database schema has `error_details` column
4. Report as a bug if consistently NULL

### ValueError: BLOCKED in EXPERIMENT Mode

**Problem**: Can't enable debug in experiment mode

**Solution**: This is intentional. Use DEV mode for debugging:

```env
EXECUTION_MODE=dev
OPENROUTER_DEBUG_ENABLED=true
```

## API Reference

### Error Handler Functions

```python
from src.api.error_handler import (
    normalize_openrouter_error,
    extract_error_from_raw,
    format_error_details,
)

# Normalize an API error
error = normalize_openrouter_error(
    http_status=429,
    response_body={"error": {"message": "Rate limit exceeded"}}
)

# Extract error from raw response
error = extract_error_from_raw(raw_response)

# Format for storage
details_json = format_error_details(error)
```

### Client Debug Parameter

```python
from src.api.client import OpenRouterClient

async with OpenRouterClient(api_key="key") as client:
    # With debug
    response = await client.chat_completion(
        model="openai/gpt-4",
        messages=[...],
        include_debug=True,  # Enable debug
    )
    
    # Access debug data
    debug_info = response["_debug"]
    actual_response = response["response"]
```

## Related Documentation

- [CONFIGURATION.md](CONFIGURATION.md) - Configuration reference
- [USAGE.md](USAGE.md) - Usage guide
- [SCHEMA.md](SCHEMA.md) - Database schema reference
