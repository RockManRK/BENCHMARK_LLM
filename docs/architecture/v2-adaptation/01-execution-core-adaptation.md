# Execution Core — V2 Adaptation Guide

**Document Type:** Adaptation Guide  
**Domain:** Execution Core  
**Purpose:** Guide implementation from V2 Current State to TO-BE Architecture  
**Audience**: Developers implementing Execution Core components  

---

## 1. V2 Current State

### 1.1 What Exists

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| ExecutionEngine | ✅ Implemented | `src/core/execution_engine.py` | Pure execution, NO DB access |
| ResultWriter | ✅ Implemented | `src/core/result_writer.py` | Idempotent, calculates needs_review |
| Planner | ✅ Implemented | `src/core/planner.py` | Read-only, resolves effective config |
| ExecutionPlan | ✅ Implemented | `src/core/execution_plan.py` | Immutable dataclasses (frozen=True) |
| OpenRouterClient | ✅ Implemented | `src/api/client.py` | Provider-agnostic design |
| RetryHandler | ✅ Implemented | `src/api/retry.py` | Standalone, NOT integrated |
| AnswerParser | ✅ Implemented | `src/core/answer_parser.py` | V1 parity achieved |
| AnswerRandomizer | ⚠️ Exists | `src/core/randomizer.py` | Needs verification |
| ErrorClassifier | ✅ Implemented | `src/api/errors.py` | NOT used by ExecutionEngine |
| Logging | ❌ MISSING | N/A | Critical gap |

### 1.2 What Works

- ✅ Planner builds ExecutionPlan from database
- ✅ ExecutionEngine executes plans (pure, NO DB)
- ✅ ResultWriter persists results (idempotent)
- ✅ AnswerParser extracts answers with confidence
- ✅ ExecutionPlan is immutable (frozen dataclasses)
- ✅ Separation of concerns respected

### 1.3 What Doesn't Work

- ❌ No logging (no visibility into execution)
- ❌ RetryHandler not integrated (inline retry in ExecutionEngine)
- ❌ ErrorClassifier not used (simplified inline classification)
- ❌ API timeout reduced (120s vs 180s for reasoning models)
- ⚠️ AnswerRandomizer behavior unverified
- ⚠️ Multimodal support unverified

---

## 2. Target State (TO-BE Architecture)

### 2.1 Architecture Principles

1. **Separation of Concerns**: Each component has single responsibility
2. **Immutability**: ExecutionPlan immutable after creation
3. **Idempotency**: Duplicate writes skipped
4. **Explicit Configuration**: No implicit resolution during execution
5. **No DB Access During Execution**: ExecutionEngine is pure
6. **Policy-Driven Retry**: RetryHandler executes policy (doesn't decide)
7. **Comprehensive Logging**: Full visibility into execution

### 2.2 Target Component Behavior

**ExecutionEngine**:
- Pure execution (NO DB access)
- Uses RetryHandler for API calls
- Uses ErrorClassifier for error classification
- Comprehensive logging throughout
- 180s timeout for reasoning models

**ResultWriter**:
- Idempotent writes (INSERT OR IGNORE)
- Calculates needs_review before INSERT
- Updates run status after all writes
- Comprehensive logging

**Planner**:
- Read-only DB access
- Resolves effective config (prompts, seed)
- Validates preconditions
- Comprehensive logging

**OpenRouterClient**:
- 180s timeout (configurable)
- Multimodal support (text + image)
- Debug mode (optional request/response capture)
- Comprehensive logging

---

## 3. Gap Analysis

### 3.1 Critical Gaps (BLOCKERS)

| Gap | Current State | Target State | Impact |
|-----|---------------|--------------|--------|
| **Logging** | No logging | Comprehensive logging | BLOCKER: No visibility |
| **RetryHandler Integration** | Inline retry | Uses RetryHandler | Bug risk, tech debt |

### 3.2 Moderate Gaps (FEATURE)

| Gap | Current State | Target State | Impact |
|-----|---------------|--------------|--------|
| **API Timeout** | 120s | 180s (configurable) | Reasoning model timeouts |
| **ErrorClassifier Integration** | Inline classification | Uses ErrorClassifier | Less precise errors |
| **AnswerRandomizer** | Unverified | Verified seed=None semantics | Potential randomization bugs |
| **Multimodal Support** | Unverified | Verified image support | Vision models may fail |

### 3.3 Minor Gaps (TECH DEBT)

| Gap | Current State | Target State | Impact |
|-----|---------------|--------------|--------|
| **Debug Mode** | Not implemented | Optional debug capture | Harder to debug API issues |
| **Repository Pattern** | Direct SQLite | Optional abstraction | Harder to test |

---

## 4. Implementation Considerations

### 4.1 Adding Logging (CRITICAL)

**Best Practices**:
- Use `logging` module (standard library)
- Configure root logger in application entry point
- Use component-specific loggers: `logging.getLogger(__name__)`
- Log at appropriate levels:
  - `DEBUG`: Detailed technical info
  - `INFO`: Normal operation (start, complete)
  - `WARNING`: Recoverable issues
  - `ERROR`: Failures

**Key Operations to Log**:
- Planner: Plan build start/complete, validation errors
- ExecutionEngine: Item execution start/complete, API errors, retry attempts
- ResultWriter: Write start/complete, idempotency skips, status updates
- OpenRouterClient: Request start/complete, HTTP errors

**Example**:
```python
import logging

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def execute(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        logger.info(f"Starting execution of plan {plan.plan_id}")
        logger.info(f"Plan: {len(plan.runs)} run(s), experiment={plan.experiment_name}")
        
        for plan_run in plan.runs:
            logger.info(f"Executing run {plan_run.run_id}")
            # ... execute run
            logger.info(f"Completed run {plan_run.run_id}")
        
        logger.info(f"Execution completed for plan {plan.plan_id}")
        return all_results
```

**Gotchas**:
- Don't log sensitive data (API keys, tokens)
- Don't log at DEBUG in production (performance)
- Do include context (run_id, item_id, model_id)
- Do log exceptions with `logger.exception()`

---

### 4.2 Integrating RetryHandler (HIGH)

**Current State**:
```python
# ExecutionEngine has inline retry
for attempt in range(1, max_attempts + 1):
    try:
        response = self._call_api_sync(...)
        return result
    except Exception as e:
        if attempt < max_attempts:
            continue
        # All attempts failed
```

**Target State**:
```python
from src.api.retry import RetryHandler

class ExecutionEngine:
    def __init__(self, api_client, randomizer, parser):
        self.api_client = api_client
        self.randomizer = randomizer
        self.parser = parser
        self.retry_handler = RetryHandler()  # Use policy from PlanRun
    
    def _execute_item(self, item: PlanItem, run: PlanRun) -> ExecutionResult:
        try:
            # Use RetryHandler with run's retry policy
            retry_handler = RetryHandler(run.retry_policy)
            response = await retry_handler.execute_with_retry(
                self._call_api,
                item,
                run,
            )
            return result
        except Exception as e:
            # All attempts failed
            return ExecutionResult(status="failure", ...)
```

**Gotchas**:
- RetryHandler is async; ExecutionEngine._call_api_sync() needs refactoring
- Pass RetryPolicy from PlanRun to RetryHandler
- ErrorClassifier needed to determine retryable errors
- Test retry behavior thoroughly

---

### 4.3 Increasing API Timeout (MEDIUM)

**Current State**:
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 120):
        self.timeout = timeout  # 120 seconds
```

**Target State**:
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 180):
        self.timeout = timeout  # 180 seconds (for reasoning models)
```

**Alternative** (configurable per model):
```python
class OpenRouterClient:
    def __init__(self, api_key: str, timeout: int = 180):
        self.default_timeout = timeout
        self.model_timeouts = {
            "openai/o1": 300,  # 5 minutes for o1
            "anthropic/claude": 180,
        }
    
    async def chat_completion(self, model_id: str, ...):
        timeout = self.model_timeouts.get(model_id, self.default_timeout)
        # Use timeout for this request
```

**Gotchas**:
- httpx timeout applies to entire request (connection + read)
- Reasoning models can take 2-3 minutes
- Don't set timeout too high (resource exhaustion risk)

---

### 4.4 Integrating ErrorClassifier (LOW)

**Current State**:
```python
def _classify_error(self, error: Exception) -> str:
    error_str = str(error).lower()
    if "timeout" in error_str:
        return "timeout"
    if "429" in error_str:
        return "http_429"
    # ... simplified classification
```

**Target State**:
```python
from src.api.errors import ErrorClassifier

def _classify_error(self, error: Exception) -> str:
    # Use ErrorClassifier for precise classification
    classified = ErrorClassifier.classify(error)
    return classified.error_type
```

**Gotchas**:
- ErrorClassifier may need updates for V2 error types
- Ensure ErrorClassifier handles all exception types
- Test error classification thoroughly

---

### 4.5 Verifying AnswerRandomizer (MEDIUM)

**Verification Checklist**:
- [ ] File exists: `src/core/randomizer.py`
- [ ] Fisher-Yates shuffle implemented
- [ ] Seed=None means "no randomization" (natural order)
- [ ] Returns randomized options + new correct answer
- [ ] Returns reverse mapping for canonical answer tracking
- [ ] Seeded RNG is reproducible (same seed → same result)

**Test Cases**:
```python
def test_seed_none_no_randomization():
    randomizer = AnswerRandomizer()
    options = ["A", "B", "C", "D"]
    result = randomizer.randomize_options(options, seed=None)
    assert result["options"] == options  # No change

def test_seed_reproducible():
    randomizer = AnswerRandomizer()
    options = ["A", "B", "C", "D"]
    result1 = randomizer.randomize_options(options, seed=42)
    result2 = randomizer.randomize_options(options, seed=42)
    assert result1 == result2  # Same result
```

**Gotchas**:
- Seed=None is VALID (means "no randomization")
- Reverse mapping needed for canonical answer tracking
- Fisher-Yates must be properly implemented

---

### 4.6 Verifying Multimodal Support (MEDIUM)

**Verification Checklist**:
- [ ] `build_multimodal_message()` exists in OpenRouterClient
- [ ] Image encoding (base64) implemented
- [ ] Image format detection (PNG, JPG, etc.)
- [ ] Image path validation (file exists)
- [ ] Multimodal messages sent correctly to API

**Test Cases**:
```python
def test_multimodal_message():
    from pathlib import Path
    from src.api.client import MessageBuilder
    
    image_path = Path("test.png")
    message = MessageBuilder.build_multimodal_message(
        "What's in this image?",
        image_path,
    )
    assert "content" in message
    assert isinstance(message["content"], list)
    assert len(message["content"]) == 2  # text + image
```

**Gotchas**:
- Image encoding can be slow for large images
- Base64 increases payload size (~33%)
- API may have image size limits

---

## 5. Migration Path

### 5.1 Phase 1 (IMMEDIATE) — Critical Gaps

**Step 1.1: Add Logging to ExecutionEngine**
```bash
# Files to modify
- src/core/execution_engine.py
```

**Tasks**:
- [ ] Add `import logging`
- [ ] Create logger: `logger = logging.getLogger(__name__)`
- [ ] Log plan execution start/complete
- [ ] Log run execution start/complete
- [ ] Log item execution (answer, latency, status)
- [ ] Log errors with `logger.exception()`

**Step 1.2: Add Logging to ResultWriter**
```bash
# Files to modify
- src/core/result_writer.py
```

**Tasks**:
- [ ] Add `import logging`
- [ ] Create logger
- [ ] Log write start/complete
- [ ] Log idempotency skips
- [ ] Log status updates

**Step 1.3: Add Logging to Planner**
```bash
# Files to modify
- src/core/planner.py
```

**Tasks**:
- [ ] Add `import logging`
- [ ] Create logger
- [ ] Log plan build start/complete
- [ ] Log validation errors
- [ ] Log resolution chains (prompts, seed)

**Step 1.4: Add Logging to OpenRouterClient**
```bash
# Files to modify
- src/api/client.py
```

**Tasks**:
- [ ] Add `import logging`
- [ ] Create logger
- [ ] Log request start/complete
- [ ] Log HTTP errors
- [ ] Log latency

**Validation**:
- Run execution with logging enabled
- Verify logs show: plan start, run start, item start/complete, errors
- Verify no sensitive data logged

---

**Step 1.5: Integrate RetryHandler**
```bash
# Files to modify
- src/core/execution_engine.py
- src/api/retry.py (verify)
```

**Tasks**:
- [ ] Import RetryHandler in ExecutionEngine
- [ ] Refactor `_execute_item()` to use RetryHandler
- [ ] Pass RetryPolicy from PlanRun to RetryHandler
- [ ] Remove inline retry loop
- [ ] Test retry behavior

**Validation**:
- Simulate transient error (e.g., timeout)
- Verify retry attempts (1s, 2s, 4s delay)
- Verify max retries respected
- Verify non-retryable errors fail immediately

---

### 5.2 Phase 2 (SHORT-TERM) — Moderate Gaps

**Step 2.1: Increase API Timeout**
```bash
# Files to modify
- src/api/client.py
```

**Tasks**:
- [ ] Change default timeout from 120 to 180
- [ ] Or make timeout configurable per model

**Validation**:
- Test with slow model (reasoning model)
- Verify no timeout errors

---

**Step 2.2: Integrate ErrorClassifier**
```bash
# Files to modify
- src/core/execution_engine.py
```

**Tasks**:
- [ ] Import ErrorClassifier
- [ ] Replace `_classify_error()` with ErrorClassifier call
- [ ] Test error classification

**Validation**:
- Simulate various errors (timeout, 429, 500, 401)
- Verify correct error types

---

**Step 2.3: Verify AnswerRandomizer**
```bash
# Files to read
- src/core/randomizer.py
```

**Tasks**:
- [ ] Read randomizer implementation
- [ ] Verify seed=None semantics
- [ ] Verify Fisher-Yates implementation
- [ ] Add tests if missing

**Validation**:
- Run tests for seed=None
- Run tests for seeded randomization
- Verify reproducibility

---

**Step 2.4: Verify Multimodal Support**
```bash
# Files to read
- src/api/client.py
```

**Tasks**:
- [ ] Check for `build_multimodal_message()`
- [ ] Verify image encoding
- [ ] Add tests if missing

**Validation**:
- Test with image-based question
- Verify API receives image

---

### 5.3 Phase 3 (OPTIONAL) — Technical Debt

**Step 3.1: Add Debug Mode**
```bash
# Files to modify
- src/api/client.py
```

**Tasks**:
- [ ] Add `include_debug` parameter
- [ ] Capture request/response
- [ ] Return in `CompletionResponse.raw_response`

**Step 3.2: Consider Repository Pattern**
```bash
# Files to modify
- src/core/result_writer.py
```

**Tasks**:
- [ ] Evaluate cost/benefit
- [ ] Implement if justified

---

## 6. Validation Criteria

### 6.1 Functional Validation

**Execution Flow**:
- [ ] Planner builds ExecutionPlan successfully
- [ ] ExecutionEngine executes all items
- [ ] ResultWriter persists all results
- [ ] Run status updated correctly

**Error Handling**:
- [ ] Transient errors retried (429, 500, timeout)
- [ ] Fatal errors fail immediately (401, 400)
- [ ] Max retries respected
- [ ] Error details captured

**Idempotency**:
- [ ] Duplicate responses skipped
- [ ] Duplicate errors skipped
- [ ] Partial re-execution works

**Randomization**:
- [ ] Seed=None = no randomization
- [ ] Seeded randomization reproducible
- [ ] Canonical answer tracking works

---

### 6.2 Logging Validation

**Coverage**:
- [ ] ExecutionEngine logs execution
- [ ] ResultWriter logs writes
- [ ] Planner logs plan building
- [ ] OpenRouterClient logs requests

**Levels**:
- [ ] INFO: Normal operation
- [ ] WARNING: Recoverable issues
- [ ] ERROR: Failures
- [ ] DEBUG: Detailed technical info

**Context**:
- [ ] run_id in logs
- [ ] item_id in logs
- [ ] model_id in logs
- [ ] No sensitive data logged

---

### 6.3 Performance Validation

**Latency**:
- [ ] No significant regression from V1
- [ ] Timeout sufficient for reasoning models
- [ ] No resource exhaustion

**Throughput**:
- [ ] Concurrent executions work
- [ ] Database writes don't bottleneck
- [ ] Memory usage acceptable

---

### 6.4 Test Coverage

**Unit Tests**:
- [ ] ExecutionEngine tests
- [ ] ResultWriter tests
- [ ] Planner tests
- [ ] AnswerParser tests
- [ ] RetryHandler tests

**Integration Tests**:
- [ ] End-to-end execution test
- [ ] Error handling test
- [ ] Idempotency test
- [ ] Randomization test

---

## 7. Summary

### 7.1 Migration Checklist

**Phase 1 (CRITICAL)**:
- [ ] Add logging to ExecutionEngine
- [ ] Add logging to ResultWriter
- [ ] Add logging to Planner
- [ ] Add logging to OpenRouterClient
- [ ] Integrate RetryHandler into ExecutionEngine

**Phase 2 (MODERATE)**:
- [ ] Increase API timeout to 180s
- [ ] Integrate ErrorClassifier
- [ ] Verify AnswerRandomizer
- [ ] Verify multimodal support

**Phase 3 (OPTIONAL)**:
- [ ] Add debug mode
- [ ] Consider repository pattern

### 7.2 Success Criteria

Migration complete when:
- ✅ All Phase 1 tasks complete
- ✅ Logging provides full visibility
- ✅ Retry behavior matches V1
- ✅ All Phase 2 tasks complete or accepted as tech debt
- ✅ All tests pass
- ✅ No critical bugs

### 7.3 Next Steps

1. **Start with Phase 1** (logging, retry integration)
2. **Validate after each step** (don't batch changes)
3. **Run tests frequently** (catch regressions early)
4. **Document deviations** (if architecture changes needed)

---

**Document Version**: 1.0  
**Last Updated**: 2026-03-29  
**Next Review**: After Phase 1 implementation
