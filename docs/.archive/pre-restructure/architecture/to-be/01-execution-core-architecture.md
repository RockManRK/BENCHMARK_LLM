# Execution Core — Architecture & Contracts (TO-BE)

**Document Type:** Target Architecture  
**Domain:** Execution Core  
**Version**: 1.0 (TO-BE)  
**Status**: Authoritative (source of truth for implementation)  

---

## 1. Domain Overview

### 1.1 Purpose

The Execution Core domain is responsible for executing LLM inference calls and persisting results in a reproducible, auditable manner. It transforms experimental configurations into concrete API calls and stores outcomes for analysis.

### 1.2 Core Responsibilities

- **Planning**: Build immutable ExecutionPlan from database state
- **Execution**: Make API calls to LLM providers (no database access)
- **Parsing**: Extract structured answers from unstructured LLM responses
- **Persistence**: Store results with idempotency guarantees (only DB write component)
- **Error Handling**: Classify and handle transient vs. fatal failures
- **Retry Logic**: Execute policy-driven retry for transient errors
- **Randomization**: Optionally randomize answer option order with seeded reproducibility

### 1.3 Design Principles

1. **Separation of Concerns**: Each component has a single, well-defined responsibility
2. **Immutability**: Execution plans and snapshots are immutable after creation
3. **Idempotency**: Duplicate writes are skipped, not overwritten
4. **Reproducibility**: Seeded randomization ensures identical results across runs
5. **Explicit Configuration**: No implicit resolution during execution
6. **No Database Access During Execution**: ExecutionEngine is pure
7. **No Execution Without Identity**: All work defined in ExecutionPlan

---

## 2. System Functioning

### 2.1 Conceptual Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Command                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                          Planner                                 │
│  (reads DB, validates, resolves effective config, builds plan)  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       ExecutionPlan                              │
│            (immutable, self-contained, frozen)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ExecutionEngine                             │
│         (executes API calls, NO DB access, pure data)           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       ResultWriter                               │
│        (persists results, calculates needs_review, NO exec)     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                         Database                                 │
│              (responses, errors tables, append-only)             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility | DB Access | Execution |
|-----------|---------------|-----------|-----------|
| **Planner** | Build ExecutionPlan from DB | Read-only | No |
| **ExecutionEngine** | Execute API calls | No | Yes |
| **ResultWriter** | Persist results | Write-only | No |
| **OpenRouterClient** | Make HTTP requests | No | Yes (API only) |
| **RetryHandler** | Execute retry policy | No | No |
| **AnswerParser** | Parse LLM responses | No | No |
| **AnswerRandomizer** | Randomize options | No | No |

### 2.3 Key Characteristics

- **No ad-hoc execution**: All work is defined in an ExecutionPlan
- **No database access during execution**: ExecutionEngine is pure
- **No configuration inference**: All values resolved before execution
- **Append-only results**: Historical data is never modified
- **Idempotent writes**: Same input produces same database state

---

## 3. Contracts

### 3.1 ExecutionPlan Contract

**Invariant**: ExecutionPlan is immutable after creation.

**Properties**:
- `frozen=True` dataclass
- No modification methods
- Only Planner creates instances
- Self-contained (no external dependencies during execution)

**Structure**:
```python
@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str                      # Unique identifier
    created_at: datetime              # Creation timestamp
    experiment_id: str                # Parent experiment
    runs: list[PlanRun]               # Runs to execute
```

**Usage Contract**:
- Planner creates ExecutionPlan from database
- ExecutionEngine consumes ExecutionPlan (never creates)
- ExecutionPlan passed by value (not modified)

---

### 3.2 ExecutionEngine Contract

**Invariant**: ExecutionEngine has NO database access.

**Preconditions**:
- ExecutionPlan is fully resolved (no external config needed)
- API client is initialized and authenticated
- Randomizer is available (if randomization needed)
- Parser is available

**Postconditions**:
- Returns `list[ExecutionResult]` (pure data)
- No side effects (no DB writes, no state changes)
- All items executed or failed

**Interface**:
```python
class ExecutionEngine:
    def execute(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        """Execute all items in plan. NO DB ACCESS."""
        ...
```

**Constraints**:
- NO database access
- NO configuration resolution
- NO scope decisions
- Returns pure data only

---

### 3.3 ResultWriter Contract

**Invariant**: ResultWriter does NOT execute (only persists).

**Preconditions**:
- ExecutionResult list from ExecutionEngine
- Database connection available
- Schema exists (responses, errors tables)

**Postconditions**:
- Success results written to `responses` table
- Failure results written to `errors` table
- Run status updated
- Idempotency guaranteed (same input → same DB state)

**Interface**:
```python
class ResultWriter:
    def write_results(self, results: list[ExecutionResult]) -> WriteReport:
        """Persist execution outcomes. Idempotent."""
        ...
```

**Constraints**:
- NO execution (only receives results)
- NO scope decisions
- NO configuration resolution
- Idempotent writes

**Idempotency Key**: `(run_id, variant_id, snapshot_id)`

---

### 3.4 Planner Contract

**Invariant**: Planner is read-only (no DB writes).

**Preconditions**:
- Database connection available
- Experiment exists
- Experiment has models and snapshots

**Postconditions**:
- Returns immutable ExecutionPlan
- All configuration resolved (effective values)
- Items deduplicated (already-answered excluded)

**Interface**:
```python
class Planner:
    def build_plan(
        self,
        experiment_name: str,
        run_ids: list[str] | None = None,
        question_ids: list[str] | None = None,
        model_variant_ids: list[str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> ExecutionPlan:
        """Build ExecutionPlan from DB. READ-ONLY."""
        ...
```

**Constraints**:
- Read-only database access
- No plan persistence (in this version)
- All configuration resolved before execution

---

### 3.5 AnswerParser Contract

**Invariant**: Parser is deterministic (same input → same output).

**Preconditions**:
- Response text (string)

**Postconditions**:
- Returns `ParsedAnswer` with answer and confidence
- Confidence reflects parsing reliability

**Interface**:
```python
class AnswerParser:
    def parse(self, response_text: str) -> ParsedAnswer:
        """Parse LLM response. Deterministic."""
        ...
```

**Confidence Levels**:
- `clear`: Single match from explicit/context/structural patterns
- `ambiguous`: Multiple different letters detected
- `no_answer`: No patterns matched
- `low_confidence`: Only fallback pattern matched

---

### 3.6 RetryHandler Contract

**Invariant**: RetryHandler executes policy (does not decide).

**Preconditions**:
- RetryPolicy configured
- Async function to execute
- Error classifier available

**Postconditions**:
- Function executed successfully OR
- All attempts exhausted OR
- Non-retryable error raised

**Interface**:
```python
class RetryHandler:
    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with retry policy."""
        ...
```

**Constraints**:
- Does not decide retryable errors (policy decides)
- Does not decide backoff strategy (policy decides)
- Only executes policy

---

## 4. Operations

### 4.1 Build ExecutionPlan

**Operation**: `Planner.build_plan()`

**What It Does**:
1. Validates experiment exists
2. Validates experiment has models
3. Validates experiment has snapshots
4. Reads runs (filtered by run_ids if provided)
5. Resolves effective prompts (run → experiment)
6. Resolves effective seed (run → experiment)
7. Builds PlanVariant list
8. Builds deduplicated PlanItem list
9. Creates immutable ExecutionPlan

**Inputs**:
- `experiment_name`: str
- `run_ids`: list[str] | None
- `question_ids`: list[str] | None
- `model_variant_ids`: list[str] | None
- `retry_policy`: RetryPolicy | None

**Outputs**:
- `ExecutionPlan`: Immutable execution plan

**Errors**:
- `PlannerValidationError`: Experiment not found
- `PlannerValidationError`: No models
- `PlannerValidationError`: No snapshots

---

### 4.2 Execute Plan

**Operation**: `ExecutionEngine.execute()`

**What It Does**:
1. Iterates through PlanRuns
2. For each run:
   a. Sets randomizer seed (if not None)
   b. Iterates through PlanItems
   c. For each item:
      - Builds prompt (stem + options + template)
      - Applies randomization (if seed set)
      - Calls API with retry
      - Parses response
      - Creates ExecutionResult
3. Returns ExecutionResult list

**Inputs**:
- `plan`: ExecutionPlan

**Outputs**:
- `list[ExecutionResult]`: Pure data (no persistence)

**Errors**:
- Component exceptions propagated (not caught)

---

### 4.3 Persist Results

**Operation**: `ResultWriter.write_results()`

**What It Does**:
1. Groups results by run_id
2. For each result:
   a. Success → `_write_response()`
   b. Failure → `_write_error()`
3. Updates run status
4. Returns WriteReport

**Inputs**:
- `results`: list[ExecutionResult]

**Outputs**:
- `WriteReport`: Summary of writes

**Errors**:
- Database exceptions propagated

---

### 4.4 Calculate needs_review

**Operation**: `ResultWriter._calculate_needs_review()`

**What It Does**:
- Derives `needs_review` flag before INSERT

**Rule**:
```python
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer is None
)
```

**Inputs**:
- `parse_confidence`: str | None
- `selected_answer`: str | None

**Outputs**:
- `bool`: True if manual review needed

---

### 4.5 Parse Answer

**Operation**: `AnswerParser.parse()`

**What It Does**:
1. Finds all letter matches
2. Filters ambiguous articles (Portuguese/Spanish "A")
3. Checks for ambiguity (multiple different letters)
4. Tries patterns by priority (Explicit → Context → Structural → Fallback)
5. Returns ParsedAnswer with confidence

**Inputs**:
- `response_text`: str

**Outputs**:
- `ParsedAnswer`: answer, confidence, raw_matches

---

## 5. Data Flow

### 5.1 Request Path

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Planner reads from DB:                                    │
│    - Experiment config                                       │
│    - Run config                                              │
│    - Model variants                                          │
│    - Question snapshots                                      │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. Planner builds ExecutionPlan:                             │
│    - Resolves effective prompts                              │
│    - Resolves effective seed                                 │
│    - Deduplicates items                                      │
│    - Freezes configuration                                   │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. ExecutionEngine executes:                                 │
│    For each PlanItem:                                        │
│    a. Build prompt (stem + options + template)               │
│    b. Apply randomization (if seed set)                      │
│    c. Build messages array                                   │
│    d. Call OpenRouterClient.chat_completion()                │
│    e. Parse response with AnswerParser                       │
│    f. Build ExecutionResult                                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. ExecutionEngine returns:                                  │
│    - list[ExecutionResult] (pure data)                       │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 Response Path

```
┌──────────────────────────────────────────────────────────────┐
│ 1. ResultWriter receives ExecutionResult list                │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. For each result:                                          │
│    Success:                                                  │
│    a. Check idempotency (response exists?)                   │
│    b. Calculate needs_review                                 │
│    c. INSERT into responses (or skip)                        │
│    Failure:                                                  │
│    a. Check idempotency (error exists?)                      │
│    b. INSERT into errors (or skip)                           │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. Update run status:                                        │
│    - Count successes/failures                                │
│    - Set status: completed / partial_failed / failed         │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. Update run_model status per variant                       │
└──────────────────────────────────────────────────────────────┘
```

### 5.3 Data Structures

**ExecutionResult**:
```python
@dataclass
class ExecutionResult:
    item_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    question_id: str
    status: Literal['success', 'failure']
    response_text: str | None
    selected_answer: str | None
    parse_confidence: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    error_type: str | None
    error_message: str | None
    attempt_count: int
```

**ExecutionPlan**:
```python
@dataclass(frozen=True)
class ExecutionPlan:
    plan_id: str
    created_at: datetime
    experiment_id: str
    runs: list[PlanRun]
```

**PlanRun**:
```python
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

## 6. Error Handling

### 6.1 Error Classification

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

### 6.2 Error Propagation

**ExecutionEngine Level**:
- Exceptions caught in `_execute_item()`
- Error converted to ExecutionResult with `status="failure"`
- Error details captured: `error_type`, `error_message`
- Execution continues (one failure doesn't stop entire run)

**ResultWriter Level**:
- Failed results written to `errors` table (not `responses`)
- Error object includes: `run_id`, `variant_id`, `question_id`, `error_type`, `error_message`, `attempt_count`
- Idempotency applies to errors too (duplicate errors skipped)

**Run Status Updates**:
- Status calculated from result outcomes
- Prevented if run already in final state (`completed` or `failed`)

### 6.3 Retry Behavior

**Retry Policy**:
```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    retry_on: tuple[str, ...] = (
        'timeout',
        'http_429',
        'http_5xx',
        'network_error',
    )
```

**Backoff Strategies**:
- `exponential`: `2^attempt` seconds
- `linear`: `attempt` seconds
- `constant`: 1 second (always)

**Default Delay Sequence** (exponential):
- Attempt 0: 1.0s
- Attempt 1: 2.0s
- Attempt 2: 4.0s
- Attempt 3: 8.0s
- Attempt 4+: Capped (configurable)

---

## 7. Cross-Reference

### 7.1 Related Domains

| Domain | Relationship | Dependency |
|--------|--------------|------------|
| **Experiment Management** | Upstream | Experiments, runs, variants, snapshots created before execution |
| **Database** | Downstream | Results persisted to database |
| **CLI** | Consumer | CLI initiates execution, displays results |
| **Configuration** | Upstream | Configuration resolved before execution |

### 7.2 External Dependencies

| Dependency | Purpose | Critical |
|------------|---------|----------|
| **OpenRouter API** | LLM inference | Yes |
| **SQLite** | Result persistence | Yes |
| **httpx** | HTTP client | Yes |
| **logging** | Observability | Yes |

### 7.3 Related Contracts

| Contract | Location | Purpose |
|----------|----------|---------|
| **ResultWriter Contract** | `docs/architecture/contracts/result-writer.md` | Detailed ResultWriter specification |
| **Domain Review Contract** | `docs/architecture/contracts/domain-review-contract.md` | Manual review workflow |
| **Execution Plan Contract** | This document | ExecutionPlan structure and invariants |

---

## 8. Summary

The Execution Core domain is built around these foundational concepts:

1. **Explicit, immutable execution plans** — All configuration resolved before execution; plans immutable after creation

2. **Separation of execution and persistence** — ExecutionEngine executes API calls without database access; ResultWriter persists results without executing

3. **Policy-driven error handling** — Retry logic executes policy; transient failures retried; fatal failures immediate

4. **Idempotent result writing** — Duplicate results skipped, partial re-execution supported

5. **Reproducible randomization** — Seeded answer shuffling with explicit enable/disable control

6. **Hierarchical answer parsing** — Pattern matching with confidence classification for manual review routing

7. **Contract-driven development** — Explicit interfaces, invariants, and rules

This document is the authoritative source of truth for Execution Core implementation.

---

**Document Version**: 1.0  
**Status**: Authoritative  
**Last Updated**: 2026-03-29  
**Next Review**: After implementation changes
