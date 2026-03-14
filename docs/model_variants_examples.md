# Model Variant System - Examples

This document provides concrete examples of model variant identity generation and OpenRouter payloads.

## Variant Signature Examples

### Example 1: Gemini with Auto Reasoning

**Configuration:**
```python
config = VariantConfig(
    reasoning_mode="auto",
    vision_enabled=False,
    structured_enabled=False,
)
model_id = "google/gemini-2.0-flash-thinking"
```

**Generated Identity:**
- `variant_signature`: `google/gemini-2.0-flash-thinking::reasoning=auto::vision=false::structured=false`
- `variant_id`: `var-<hash>` (deterministic hash)

**OpenRouter Payload:**
```json
{
  "model": "google/gemini-2.0-flash-thinking",
  "messages": [
    {"role": "user", "content": "What is the capital of France?"}
  ]
}
```
**Note:** No `reasoning` field sent - uses model default.

---

### Example 2: Claude with Reasoning Budget

**Configuration:**
```python
config = VariantConfig(
    reasoning_mode="budget",
    reasoning_max_tokens=8000,
    vision_enabled=True,
    structured_enabled=False,
)
model_id = "anthropic/claude-3-5-sonnet"
```

**Generated Identity:**
- `variant_signature`: `anthropic/claude-3-5-sonnet::reasoning=budget:8000::vision=true::structured=false`
- `variant_id`: `var-<hash>` (deterministic hash)

**OpenRouter Payload:**
```json
{
  "model": "anthropic/claude-3-5-sonnet",
  "messages": [
    {"role": "user", "content": "Solve this problem..."}
  ],
  "reasoning": {
    "max_tokens": 8000
  }
}
```

---

### Example 3: Qwen with Reasoning Effort

**Configuration:**
```python
config = VariantConfig(
    reasoning_mode="effort",
    reasoning_effort="high",
    vision_enabled=False,
    structured_enabled=True,
)
model_id = "qwen/qwen-2.5-72b"
```

**Generated Identity:**
- `variant_signature`: `qwen/qwen-2.5-72b::reasoning=effort:high::vision=false::structured=true`
- `variant_id`: `var-<hash>` (deterministic hash)

**OpenRouter Payload:**
```json
{
  "model": "qwen/qwen-2.5-72b",
  "messages": [
    {"role": "user", "content": "Answer this question..."}
  ],
  "reasoning": {
    "effort": "high"
  },
  "response_format": {
    "type": "json_object"
  }
}
```

---

### Example 4: Reasoning Disabled

**Configuration:**
```python
config = VariantConfig(
    reasoning_mode="off",
    vision_enabled=False,
    structured_enabled=False,
)
model_id = "openai/o1-preview"
```

**Generated Identity:**
- `variant_signature`: `openai/o1-preview::reasoning=off::vision=false::structured=false`
- `variant_id`: `var-<hash>` (deterministic hash)

**OpenRouter Payload:**
```json
{
  "model": "openai/o1-preview",
  "messages": [
    {"role": "user", "content": "Answer this question..."}
  ],
  "reasoning": {
    "enabled": false
  }
}
```

---

### Example 5: Unspecified Reasoning (Default)

**Configuration:**
```python
config = VariantConfig(
    reasoning_mode="unspecified",
    vision_enabled=False,
    structured_enabled=False,
)
model_id = "meta/llama-3-70b"
```

**Generated Identity:**
- `variant_signature`: `meta/llama-3-70b::reasoning=unspecified::vision=false::structured=false`
- `variant_id`: `var-<hash>` (deterministic hash)

**OpenRouter Payload:**
```json
{
  "model": "meta/llama-3-70b",
  "messages": [
    {"role": "user", "content": "Answer this question..."}
  ]
}
```
**Note:** No `reasoning` field sent - uses model default.

---

## Database Schema

### models Table (Base Models)
```sql
CREATE TABLE models (
    model_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Example Record:**
```
model_id: "openai/gpt-4"
provider: "openai"
model_name: "gpt-4"
```

---

### model_variants Table
```sql
CREATE TABLE model_variants (
    variant_id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL,
    reasoning_mode TEXT NOT NULL,
    reasoning_effort TEXT,
    reasoning_max_tokens INTEGER,
    vision_enabled BOOLEAN NOT NULL DEFAULT 0,
    structured_enabled BOOLEAN NOT NULL DEFAULT 0,
    variant_signature TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id)
);
```

**Example Records:**
```
variant_id: "var-a1b2c3d4"
model_id: "openai/gpt-4"
reasoning_mode: "auto"
reasoning_effort: NULL
reasoning_max_tokens: NULL
vision_enabled: 0
structured_enabled: 0
variant_signature: "openai/gpt-4::reasoning=auto::vision=false::structured=false"

variant_id: "var-e5f6g7h8"
model_id: "openai/gpt-4"
reasoning_mode: "effort"
reasoning_effort: "high"
reasoning_max_tokens: NULL
vision_enabled: 0
structured_enabled: 1
variant_signature: "openai/gpt-4::reasoning=effort:high::vision=false::structured=true"
```

---

### responses Table (uses variant_id)
```sql
CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    iteration INTEGER NOT NULL DEFAULT 1,
    -- ... other fields ...
    FOREIGN KEY (variant_id) REFERENCES model_variants(variant_id)
);
```

**Example Record:**
```
response_id: 1
run_id: "run-20260313-abc12345"
snapshot_id: 1
question_id: "Q001"
variant_id: "var-a1b2c3d4"
iteration: 1
selected_answer: "A"
is_correct: 1
-- ...
```

---

## Logging Examples

### INFO Level - Variant Registration
```
INFO: Registered model variant: var-a1b2c3d4 | model=openai/gpt-4 | signature=openai/gpt-4::reasoning=auto::vision=false::structured=false
```

### DEBUG Level - Reasoning Payload
```
DEBUG: Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
DEBUG: Model: openai/gpt-4, Messages: 2, Reasoning: {'effort': 'high'}
```

### INFO Level - Request Summary
```
INFO: Sending API request: model=openai/gpt-4, max_tokens=16384, temperature=0.0, structured_output=True, debug=False
```

---

## Key Principles

1. **variant_id is stable**: Same configuration always produces the same variant_id (deterministic hash)
2. **variant_signature is human-readable**: Easy to understand what a variant represents
3. **Reasoning is never inferred**: Always explicit (off/auto/effort/budget/unspecified)
4. **Unspecified = don't send**: When reasoning_mode is "unspecified", no reasoning field is sent to API
5. **Non-identity parameters excluded**: temperature, top_p, max_tokens (generation) are NOT part of variant identity
6. **Variant isolation**: Statistics and queries can be filtered by variant_id to ensure accurate comparisons
