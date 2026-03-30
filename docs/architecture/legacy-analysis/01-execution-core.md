# Execution Core — V1 Legacy Analysis

**Document Type:** Legacy Analysis (Read-Only)  
**Domain:** Execution Core  
**Source:** `src_legacy/` directory  
**Purpose:** Extract architectural concepts from V1 implementation for historical reference  

---

## 1. Domain Overview

### 1.1 Purpose

The Execution Core domain is responsible for executing LLM inference calls and persisting results in a reproducible, auditable manner. It transforms experimental configurations into concrete API calls and stores outcomes for analysis.

### 1.2 Core Responsibilities

- **Execution**: Make API calls to LLM providers (OpenRouter)
- **Parsing**: Extract structured answers from unstructured LLM responses
- **Persistence**: Store results with idempotency guarantees
- **Error Handling**: Classify and handle transient vs. fatal failures
- **Retry Logic**: Implement exponential backoff for transient errors
- **Randomization**: Optionally randomize answer option order for reproducibility

### 1.3 Design Principles

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Immutability**: Execution plans and snapshots are immutable after creation
3. **Idempotency**: Duplicate writes are skipped, not overwritten
4. **Reproducibility**: Seeded randomization ensures identical results across runs
5. **Explicit Configuration**: No implicit resolution during execution

---

## 2. System Functioning

### 2.1 Conceptual Flow

```
CLI Command
    ↓
Planner (reads DB, builds ExecutionPlan)
    ↓
ExecutionPlan (immutable, self-contained)
    ↓
ExecutionEngine (executes API calls, NO DB access)
    ↓
ResultWriter (persists results, NO execution)
    ↓
Database (responses, errors tables)
```

### 2.2 Key Characteristics

- **No ad-hoc execution**: All work is defined in an ExecutionPlan
- **No database access during execution**: ExecutionEngine is pure
- **No configuration inference**: All values resolved before execution
- **Append-only results**: Historical data is never modified

---

## 3. Components

### 3.1 ExecutionEngine

**Responsibility**: Execute API calls and return raw results (pure data, no persistence)

**Key Behaviors**:
- Receives fully-resolved ExecutionPlan from Planner
- Iterates through PlanItems and executes each one
- Builds prompts from question payloads and templates
- Applies answer randomization (if seed is set)
- Calls OpenRouter API for each item
- Parses responses to extract answer letters
- Returns ExecutionResult list (pure data)

**Constraints**:
- NO database access
- NO configuration resolution
- NO scope decisions
- Returns pure data only

**Dependencies**:
- OpenRouterClient: For API calls
- AnswerRandomizer: For option shuffling
- AnswerParser: For response parsing
- Settings: For model configuration

---

### 3.2 ResultWriter

**Responsibility**: Persist execution outcomes to database (idempotent writes)

**Key Behaviors**:
- Receives ExecutionResult list from ExecutionEngine
- Groups results by run_id
- For each result:
  - Success → Write to `responses` table
  - Failure → Write to `errors` table
- Calculates `needs_review` from `parse_confidence` and `selected_answer`
- Updates run status (`completed`, `partial_failed`, `failed`)
- Updates run_model status per variant

**Constraints**:
- NO execution (only receives results)
- NO scope decisions
- NO configuration resolution
- Idempotent writes (same input → same DB state)

**Idempotency Key**: `(run_id, variant_id, snapshot_id)`

**Review Field Calculation**:
```
needs_review = TRUE if (
    parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

---

### 3.3 Planner

**Responsibility**: Build immutable ExecutionPlan from database state

**Key Behaviors**:
- Reads experiment, runs, variants, snapshots from database
- Applies filters (model_filter, question_filter)
- Deduplicates items (excludes already-answered combinations)
- Resolves seeds and prompts (run overrides experiment)
- Builds immutable, self-contained ExecutionPlan

**Resolution Chains**:
- **Seed**: Run seed → Experiment default seed → None (no randomization)
- **Prompts**: Run prompts → Experiment templates → Defaults

**Constraints**:
- Read-only during execution cycle
- No plan persistence (in this version)
- All configuration resolved before execution

---

### 3.4 OpenRouterClient (API Client)

**Responsibility**: Make HTTP requests to OpenRouter API

**Key Behaviors**:
- Builds request payloads (messages, parameters)
- Handles authentication (Bearer token)
- Supports text-only and multimodal (image) messages
- Parses responses (content, tokens, finish reason)
- Classifies HTTP errors

**Request Construction**:
- Base URL: `https://openrouter.ai/api/v1`
- Timeout: 180 seconds (3 minutes)
- Authentication: `Authorization: Bearer {api_key}`
- Optional parameters: `max_tokens`, `temperature`, `reasoning`, `response_format`

**Response Parsing**:
- Extracts `choices[0].message.content`
- Extracts token usage (`prompt_tokens`, `completion_tokens`, `total_tokens`)
- Extracts finish reason (`stop`, `length`, `content_filter`, etc.)

---

### 3.5 RetryHandler

**Responsibility**: Execute operations with retry logic and exponential backoff

**Key Behaviors**:
- Retries on transient failures (timeout, network, 5xx, 429)
- Implements exponential backoff: `delay = base_delay * (2 ^ attempt)`
- Caps delay at `max_delay` (60 seconds)
- Fails immediately on non-retryable errors (400, 401, 403, 404)

**Retry Configuration**:
- `max_retries`: 3 (default)
- `base_delay`: 1.0 seconds
- `max_delay`: 60.0 seconds
- `exponential_base`: 2.0
- `retryable_status_codes`: [429, 500, 502, 503, 504]

**Delay Sequence**:
- Attempt 0: 1.0s
- Attempt 1: 2.0s
- Attempt 2: 4.0s
- Attempt 3: 8.0s
- Attempt 4+: 60.0s (capped)

---

### 3.6 AnswerParser

**Responsibility**: Extract answer letters from LLM responses with confidence classification

**Pattern Hierarchy** (highest to lowest priority):

1. **Explicit Patterns** (clear confidence):
   - `resposta: [A-D]`, `answer: [A-D]`
   - `alternativa correta é [A-D]`, `correta é [A-D]`

2. **Context Patterns** (clear confidence):
   - `a resposta é [A-D]`, `the correct answer is [A-D]`
   - `opção [A-D]`, `letra [A-D]`, `alternativa [A-D]`

3. **Structural Patterns** (clear confidence):
   - `**[A-D]**` (Markdown bold)
   - `[A-D]:`, `[A-D])`, `([A-D])`

4. **Fallback** (low_confidence):
   - Any isolated `[A-D]` word boundary match

**Confidence Levels**:
- `clear`: Single match from explicit/context/structural patterns
- `ambiguous`: Multiple different letters detected
- `no_answer`: No patterns matched
- `low_confidence`: Only fallback pattern matched

**Special Handling**:
- Portuguese/Spanish article "A" filtered when followed by nouns
- Case-insensitive matching
- Repeated same letter = clear (not ambiguous)

---

### 3.7 AnswerRandomizer

**Responsibility**: Randomize answer option order with seeded reproducibility

**Key Behaviors**:
- Fisher-Yates shuffle with seeded RNG
- Returns randomized options + new correct answer letter
- Supports seed=None (no randomization, natural order)

**Seed Semantics**:
- `None`: No randomization (original A,B,C,D order)
- `"AUTO"`: Automatic seed generation (hash of run_id)
- Integer: Fixed seed for reproducibility

**Resolution Priority**:
1. Run-level seed
2. Experiment default seed
3. None (no randomization)

---

## 4. Data Flow

### 4.1 Request Path

```
1. Planner reads from DB:
   - Experiment config
   - Run config
   - Model variants
   - Question snapshots

2. Planner builds ExecutionPlan:
   - Resolves effective prompts
   - Resolves effective seed
   - Deduplicates items
   - Freezes configuration

3. ExecutionEngine executes:
   - For each PlanItem:
     a. Build prompt (stem + options + template)
     b. Apply randomization (if seed set)
     c. Build messages array
     d. Call OpenRouterClient.chat_completion()
     e. Parse response with AnswerParser
     f. Build ExecutionResult

4. ExecutionEngine returns:
   - List[ExecutionResult] (pure data)
```

### 4.2 Response Path

```
1. ResultWriter receives ExecutionResult list

2. For each result:
   - Success:
     a. Check idempotency (response exists?)
     b. Calculate needs_review
     c. INSERT into responses (or skip)
   - Failure:
     a. Check idempotency (error exists?)
     b. INSERT into errors (or skip)

3. Update run status:
   - Count successes/failures
   - Set status: completed / partial_failed / failed

4. Update run_model status per variant
```

---

## 5. Error Handling

### 5.1 Error Classification

**Retryable Errors**:
- HTTP 429 (rate limit)
- HTTP 500, 502, 503, 504 (server errors)
- `httpx.TimeoutException`
- `httpx.ConnectError`
- `httpx.NetworkError`

**Fatal (Non-Retryable) Errors**:
- HTTP 400 (bad request)
- HTTP 401 (authentication)
- HTTP 403 (forbidden)
- HTTP 404 (not found)
- `ValueError`, `TypeError`, `KeyError` (programming errors)
- ParseError (invalid response structure)

### 5.2 Error Propagation

**ExecutionEngine Level**:
- Exceptions caught in `_execute_item()`
- Error converted to ExecutionResult with `status="failure"`
- Error details captured: `error_type`, `error_message`

**ResultWriter Level**:
- Failed results written to `errors` table (not `responses`)
- Error object includes: `run_id`, `variant_id`, `question_id`, `error_type`, `error_message`, `attempt_count`

**Run Status Updates**:
- Status calculated from result outcomes
- Prevented if run already in final state (`completed` or `failed`)

---

## 6. Key Design Decisions

### 6.1 Separation of Concerns

**Decision**: ExecutionEngine does NOT access database; ResultWriter does NOT execute

**Rationale**:
- Clear responsibility boundaries
- Testable in isolation
- Prevents accidental side effects
- Enables independent evolution

**Trade-offs**:
- Requires data passing between components
- ExecutionEngine returns pure data (caller persists)

---

### 6.2 Immutability

**Decision**: ExecutionPlan is immutable after creation

**Rationale**:
- Reproducibility (plan cannot change mid-execution)
- Auditability (historical plans preserved)
- Thread safety (immutable objects are inherently safe)
- Clear ownership (only Planner creates plans)

**Implementation**:
- `frozen=True` dataclasses
- No modification methods
- New plan created for each execution

---

### 6.3 Idempotency

**Decision**: ResultWriter is idempotent (same input → same DB state)

**Rationale**:
- Supports partial re-execution
- Prevents data loss from accidental re-runs
- Enables crash recovery
- Simplifies error handling

**Implementation**:
- Uniqueness constraint: `(run_id, variant_id, snapshot_id)`
- INSERT OR IGNORE (skip duplicates)
- Duplicate errors also skipped

---

### 6.4 Explicit Configuration

**Decision**: All configuration resolved before execution starts

**Rationale**:
- No implicit behavior during execution
- ExecutionPlan is self-contained
- Easier debugging (all values visible in plan)
- Reproducible executions

**Implementation**:
- Planner resolves all values
- ExecutionEngine receives effective config
- No fallback to globals during execution

---

### 6.5 Hierarchical Answer Parsing

**Decision**: Pattern hierarchy with confidence classification

**Rationale**:
- LLM responses are unstructured
- Different patterns have different reliability
- Confidence levels route results for manual review
- Transparent parsing logic

**Implementation**:
- Explicit → Context → Structural → Fallback
- Confidence: clear, ambiguous, no_answer, low_confidence
- `needs_review` calculated from confidence

---

## 7. Summary

The V1 Execution Core was built around these foundational concepts:

1. **Explicit, immutable execution plans** — All configuration resolved before execution; plans immutable after creation

2. **Separation of execution and persistence** — ExecutionEngine executed API calls without database access; ResultWriter persisted results without executing

3. **Comprehensive error handling** — Retry logic with exponential backoff for transient failures; immediate failure for non-retryable errors

4. **Idempotent result writing** — Duplicate results skipped, partial re-execution supported

5. **Reproducible randomization** — Seeded answer shuffling with explicit enable/disable control

6. **Hierarchical answer parsing** — Pattern matching with confidence classification for manual review routing

7. **Critical defaults** — Many "magic" values controlled correctness (timeouts, retry counts, connection limits)

This document captures the architectural essence of V1 without proposing improvements or comparing to V2 implementations.
