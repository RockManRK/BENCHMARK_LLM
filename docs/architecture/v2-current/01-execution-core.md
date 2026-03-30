# Execution Core — V2 Current State

**Document Type:** Current State Analysis  
**Domain:** Execution Core  
**Source:** `src/` directory (TO-BE architecture)  
**Purpose:** Document what actually exists in V2 implementation  

---

## 1. Domain Overview

### 1.1 What Exists in V2

The V2 Execution Core implements the TO-BE architecture with the following components:

| Component | Status | Location |
|-----------|--------|----------|
| ExecutionEngine | ✅ Implemented | `src/core/execution_engine.py` |
| ResultWriter | ✅ Implemented | `src/core/result_writer.py` |
| Planner | ✅ Implemented | `src/core/planner.py` |
| ExecutionPlan | ✅ Implemented | `src/core/execution_plan.py` |
| OpenRouterClient | ✅ Implemented | `src/api/client.py` |
| RetryHandler | ✅ Implemented | `src/api/retry.py` |
| AnswerParser | ✅ Implemented | `src/core/answer_parser.py` |
| AnswerRandomizer | ⚠️ Partial | `src/core/randomizer.py` (needs verification) |
| Logging System | ❌ MISSING | Critical gap identified |

### 1.2 Architectural Alignment

V2 follows the TO-BE architecture principles:

- ✅ **Separation of Concerns**: ExecutionEngine has NO DB access; ResultWriter has DB write access only
- ✅ **Immutability**: ExecutionPlan dataclasses use `frozen=True`
- ✅ **Explicit Configuration**: Planner resolves all effective values before execution
- ✅ **Idempotency**: ResultWriter uses UNIQUE constraint + INSERT OR IGNORE
- ✅ **No Implicit Execution**: All work defined in ExecutionPlan

---

## 2. Component Status

### 2.1 ExecutionEngine

**Status**: ✅ Implemented (with caveats)

**What's Coded**:
- Pure execution engine with NO database access
- Executes all items in ExecutionPlan
- Applies answer randomization (if seed is set)
- Calls OpenRouter API via `OpenRouterClient`
- Parses responses with `AnswerParser`
- Returns `ExecutionResult` list (pure data)
- Built-in retry loop with configurable `max_attempts`

**Implementation Details**:
- `execute(plan: ExecutionPlan) -> list[ExecutionResult]`
- `_execute_run(run: PlanRun) -> list[ExecutionResult]`
- `_execute_item(item: PlanItem, run: PlanRun) -> ExecutionResult`
- `_call_api_sync(...)` — Synchronous wrapper for async API client
- `_build_user_prompt(...)` — Prompt construction from template
- `_classify_error(error: Exception) -> str` — Error type classification

**Caveats**:
- Retry logic is inline (not using `RetryHandler` from `src/api/retry.py`)
- `_call_api_sync()` uses `asyncio.run()` which may cause issues in async contexts
- Error classification is simplified (not using `ErrorClassifier` from `src/api/errors.py`)

---

### 2.2 ResultWriter

**Status**: ✅ Implemented (aligned with contract)

**What's Coded**:
- Persists `ExecutionResult` to database
- Calculates `needs_review` before INSERT per contract
- Idempotent writes using `INSERT OR IGNORE`
- Updates run status after all writes complete
- Writes success results to `responses` table
- Writes failure results to `errors` table

**Implementation Details**:
- `write_results(results: list[ExecutionResult]) -> WriteReport`
- `_calculate_needs_review(parse_confidence, selected_answer) -> bool`
- `_write_response(result: ExecutionResult) -> bool`
- `_write_error(result: ExecutionResult) -> None`
- `_determine_run_status(results: list[ExecutionResult]) -> str`
- `_update_run_status(run_id: str, status: str) -> None`
- `_get_model_id_from_variant(variant_id: str) -> str`

**Contract Alignment**:
- ✅ Calculates `needs_review` from `parse_confidence` and `selected_answer`
- ✅ Idempotent writes (UNIQUE constraint + INSERT OR IGNORE)
- ✅ Updates run status after all writes
- ✅ NO execution (only receives results)
- ✅ NO scope decisions

**Caveats**:
- Uses direct SQLite connection (not repository pattern from V1)
- `_get_model_id_from_variant()` requires DB lookup (could be optimized)

---

### 2.3 Planner

**Status**: ✅ Implemented (read-only, as designed)

**What's Coded**:
- Builds `ExecutionPlan` from database state
- Validates experiment exists and has models/snapshots
- Resolves effective prompts (run overrides experiment)
- Resolves effective seed (run overrides experiment)
- Applies filters (run_ids, question_ids, model_variant_ids)
- Builds deduplicated items per run

**Implementation Details**:
- `build_plan(experiment_name, run_ids, question_ids, model_variant_ids, retry_policy) -> ExecutionPlan`
- `_validate_experiment_exists(name: str) -> sqlite3.Row`
- `_validate_has_models(experiment_id: str) -> list[sqlite3.Row]`
- `_validate_has_snapshots(experiment_id: str) -> list[sqlite3.Row]`
- `_resolve_prompts_effective(...) -> Prompts`
- `_resolve_seed_effective(...) -> int | None`
- `_build_model_config(variant_row: sqlite3.Row) -> ModelConfig`
- `_build_items(...) -> list[PlanItem]`

**Validation**:
- ✅ Experiment must exist
- ✅ Experiment must have models
- ✅ Experiment must have snapshots
- ✅ Raises `PlannerValidationError` on validation failure

**Configuration Resolution**:
- **Prompts**: `run.config.SYSTEM_PROMPT/USER_PROMPT` → `experiment.config_json` (fallback)
- **Seed**: `run.config.RUN_RESPONSES_SEED` → `experiment.config.RUN_RESPONSES_SEED` (fallback)

---

### 2.4 ExecutionPlan

**Status**: ✅ Implemented (immutable dataclasses)

**What's Coded**:
- `ExecutionPlan` — Immutable, self-contained description of work
- `PlanRun` — Single run within execution plan
- `PlanItem` — Single executable task
- `PlanVariant` — Model variant with resolved configuration
- `Prompts` — Resolved prompt templates
- `RetryPolicy` — Per-run retry configuration
- `ModelConfig` — All parameters affecting model behavior
- `QuestionPayload` — Snapshotted question data

**Immutability**:
- ✅ All dataclasses use `frozen=True`
- ✅ No modification methods
- ✅ Only Planner creates instances

**Key Data Structures**:
```python
@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    created_at: datetime
    experiment_id: str
    runs: list[PlanRun]

@dataclass(frozen=True)
class PlanRun:
    run_id: str
    seed_effective: int | None
    prompts_effective: Prompts
    retry_policy: RetryPolicy
    variants: list[PlanVariant]
    items: list[PlanItem]
```

---

### 2.5 OpenRouterClient

**Status**: ✅ Implemented (provider-agnostic design)

**What's Coded**:
- Implements `CompletionProvider` abstract base
- Makes HTTP requests to OpenRouter API
- Supports text-only and multimodal messages (V1 has multimodal, V2 needs verification)
- Parses responses (content, tokens, latency)
- Classifies HTTP errors using `ErrorClassifier`

**Implementation Details**:
- `chat_completion(model_id, messages, temperature, top_p, max_tokens, stop, response_format) -> CompletionResponse`
- `_handle_http_error(response: httpx.Response) -> None`
- `close() -> None`

**Request Configuration**:
- Base URL: `https://openrouter.ai/api/v1`
- Timeout: 120 seconds (V1: 180 seconds)
- Authentication: `Authorization: Bearer {api_key}`
- Optional parameters: `temperature`, `top_p`, `max_tokens`, `stop`, `response_format`

**Differences from V1**:
- ⚠️ Timeout: 120s (V2) vs 180s (V1) — May be insufficient for reasoning models
- ⚠️ Multimodal support: Not explicitly implemented in V2 (needs verification)
- ✅ Provider-agnostic design (abstract base class)

---

### 2.6 RetryHandler

**Status**: ✅ Implemented (but NOT used by ExecutionEngine)

**What's Coded**:
- Policy-driven retry logic
- Executes `RetryPolicy` configuration
- Supports backoff strategies: exponential, linear, constant
- Checks if errors are retryable per policy

**Implementation Details**:
- `execute_with_retry(func, *args, **kwargs) -> T`
- `is_retryable(error: APIError) -> bool`
- `calculate_delay(attempt: int) -> float`

**Backoff Strategies**:
- `exponential`: `2^attempt` seconds
- `linear`: `attempt` seconds
- `constant`: 1 second (always)

**Gap**:
- ❌ ExecutionEngine does NOT use `RetryHandler`
- ❌ ExecutionEngine has inline retry loop instead
- ❌ Inconsistent retry behavior between components

---

### 2.7 AnswerParser

**Status**: ✅ Implemented (V1 parity achieved)

**What's Coded**:
- Hierarchical pattern matching (Explicit → Context → Structural → Fallback)
- Confidence classification: clear, ambiguous, no_answer, low_confidence
- Article filtering for Portuguese/Spanish "A"
- Case-insensitive matching

**Implementation Details**:
- `parse(response_text: str) -> ParsedAnswer`
- `_find_all_matches(text: str) -> list[str]`
- `_filter_ambiguous_articles(text: str, matches: list[str]) -> list[str]`
- `_extract_match(match: re.Match, has_group: bool) -> Optional[str]`

**Pattern Hierarchy**:
1. ✅ Explicit patterns (clear confidence)
2. ✅ Context patterns (clear confidence)
3. ✅ Structural patterns (clear confidence)
4. ✅ Fallback pattern (low_confidence)

**Alignment with V1**:
- ✅ Same pattern hierarchy
- ✅ Same confidence levels
- ✅ Same article filtering
- ✅ Same edge case handling

---

### 2.8 AnswerRandomizer

**Status**: ⚠️ Needs Verification

**What's Coded** (based on file listing):
- File exists: `src/core/randomizer.py`
- Content NOT read in this analysis

**V1 Behavior** (for reference):
- Fisher-Yates shuffle with seeded RNG
- Returns randomized options + new correct answer
- Seed=None means "no randomization"

**Verification Needed**:
- Does V2 randomizer support seed=None semantics?
- Does V2 randomizer return reverse mapping for canonical answer tracking?
- Is randomization applied per-item or per-run?

---

### 2.9 Logging System

**Status**: ❌ MISSING (Critical Gap)

**V1 Logging**:
- `logging` module used throughout
- DEBUG, INFO, WARNING, ERROR levels
- Component-specific loggers (e.g., `logging.getLogger(__name__)`)
- Structured log messages with context (model, run_id, item_id, etc.)

**V2 Logging**:
- ❌ No logging statements found in `src/core/execution_engine.py`
- ❌ No logging statements found in `src/core/result_writer.py`
- ❌ No logging statements found in `src/core/planner.py`
- ❌ No logging statements found in `src/api/client.py`

**Impact**:
- No visibility into execution progress
- No debugging capability
- No audit trail
- No error diagnostics

---

## 3. Implementation Details

### 3.1 What's Actually Coded

**Execution Flow**:
```python
# 1. Planner builds plan
planner = Planner(db_connection)
plan = planner.build_plan("my-experiment")

# 2. ExecutionEngine executes
engine = ExecutionEngine(api_client, randomizer, parser)
results = engine.execute(plan)

# 3. ResultWriter persists
writer = ResultWriter(db_connection)
report = writer.write_results(results)
```

**Data Flow**:
```
Database → Planner → ExecutionPlan → ExecutionEngine → ExecutionResult[] → ResultWriter → Database
```

**Key Invariants**:
- ✅ ExecutionEngine has NO DB access
- ✅ ResultWriter has DB write access ONLY
- ✅ ExecutionPlan is immutable
- ✅ ResultWriter calculates `needs_review`
- ✅ Idempotent writes (INSERT OR IGNORE)

---

## 4. Differences from V1

### 4.1 Architectural Changes

| Aspect | V1 | V2 |
|--------|----|----|
| **ExecutionEngine retry** | Uses `RetryHandler` | Inline retry loop |
| **API client timeout** | 180 seconds | 120 seconds |
| **Logging** | Comprehensive | MISSING |
| **Error handling** | `ErrorClassifier` module | Simplified inline |
| **Multimodal support** | Implemented | Needs verification |
| **Repository pattern** | Used in ResultWriter | Direct SQLite |

### 4.2 Design Philosophy

**V1**:
- Pragmatic, production-tested
- Comprehensive logging
- Tight integration between components

**V2**:
- Clean architecture (TO-BE)
- Provider-agnostic design
- Immutable dataclasses
- Contract-driven development

### 4.3 Implementation Approach

**V1**:
- Async-first (asyncio)
- Repository pattern for DB access
- Separate error handling module

**V2**:
- Sync wrapper for async API calls
- Direct SQLite in ResultWriter
- Inline error classification

---

## 5. Known Gaps

### 5.1 Critical Gaps (HIGH Priority)

1. **Logging System MISSING**
   - No visibility into execution
   - No debugging capability
   - **Impact**: BLOCKER for production use

2. **RetryHandler NOT Integrated**
   - ExecutionEngine has inline retry instead
   - Inconsistent with architecture
   - **Impact**: Technical debt, potential bugs

3. **API Timeout Reduced**
   - 120s (V2) vs 180s (V1)
   - May timeout reasoning models
   - **Impact**: Execution failures for slow models

### 5.2 Moderate Gaps (MEDIUM Priority)

4. **AnswerRandomizer NOT Verified**
   - File exists but content not checked
   - Seed=None semantics unclear
   - **Impact**: Potential randomization bugs

5. **Multimodal Support NOT Verified**
   - V1 supports images; V2 unclear
   - **Impact**: Vision models may not work

6. **ErrorClassifier NOT Used**
   - ExecutionEngine has simplified classification
   - **Impact**: Less precise error handling

### 5.3 Minor Gaps (LOW Priority)

7. **Repository Pattern Abandoned**
   - V2 uses direct SQLite
   - **Impact**: Harder to test, less abstraction

8. **No Debug Mode**
   - V1 had `include_debug` flag
   - **Impact**: Harder to debug API issues

---

## 6. Summary

### 6.1 V2 Current State Summary

**Implemented** (✅):
- ExecutionEngine (pure execution, NO DB)
- ResultWriter (idempotent, calculates needs_review)
- Planner (read-only, resolves effective config)
- ExecutionPlan (immutable dataclasses)
- OpenRouterClient (provider-agnostic)
- RetryHandler (standalone, not integrated)
- AnswerParser (V1 parity achieved)

**Partial** (⚠️):
- AnswerRandomizer (exists, needs verification)

**Missing** (❌):
- Logging System (CRITICAL)
- RetryHandler integration
- ErrorClassifier integration
- Debug mode
- Multimodal support (needs verification)

### 6.2 Architectural Alignment

V2 is **well-aligned** with TO-BE architecture principles:
- ✅ Separation of concerns
- ✅ Immutability
- ✅ Explicit configuration
- ✅ Idempotency
- ✅ No implicit execution

**Gaps are implementation details**, not architectural violations.

### 6.3 Next Steps

1. **Add Logging** (CRITICAL) — Instrument all components
2. **Integrate RetryHandler** — Replace inline retry in ExecutionEngine
3. **Verify Randomizer** — Check seed=None semantics
4. **Verify Multimodal** — Check image support
5. **Increase Timeout** — Restore 180s for reasoning models
6. **Integrate ErrorClassifier** — Use in ExecutionEngine

This document captures the current state of V2 implementation without proposing fixes (that's the Gap Report's job).
