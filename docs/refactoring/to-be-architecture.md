# TO-BE Architecture Specification — Phase 3

**Session**: refactoring-2026-03-19
**Phase**: 3/11
**Date**: 2026-03-20

---

## Executive Summary

This specification defines the **clean-slate architecture** for the Benchmark LLM system. The TO-BE architecture preserves the core execution flow (Planner → ExecutionEngine → ResultWriter) while addressing critical issues identified in Phase 1 and Phase 2:

- **Oversized files** → Command-per-module CLI with strict file size limits
- **Mixed concerns** → Clear layer boundaries with import rules
- **Legacy code paths** → Complete removal of iteration-based execution
- **Missing retry policy** → Per-run retry configuration in ExecutionPlan
- **Schema inconsistencies** → Breaking changes to enforce experiment ownership

**Key Decisions**:
- Breaking changes allowed (no backward compatibility with legacy)
- Test-first implementation (domain rules as architectural anchors)
- Phased file size discipline (400-500 lines initial, 200/30 hard limits later)
- Soft deletes for auditability (`is_active` flags)

---

## Module Structure

### Directory Layout

```
src_v2/
├── cli/
│   ├── __init__.py
│   ├── bcllm_experiment.py      # Experiment lifecycle commands
│   ├── bcllm_model.py           # Model variant commands
│   ├── bcllm_questions.py       # Question snapshot commands
│   ├── bcllm_run.py             # Run lifecycle commands
│   └── bcllm_execute.py         # Execution entry point
├── core/
│   ├── __init__.py
│   ├── planner.py               # DB read → ExecutionPlan
│   ├── execution_engine.py      # Pure execution (no DB)
│   ├── result_writer.py         # Persistence (no execution)
│   ├── execution_plan.py        # Immutable data structures
│   ├── randomizer.py            # Fisher-Yates answer randomization
│   └── answer_parser.py         # Response parsing with confidence
├── db/
│   ├── __init__.py
│   ├── schema.py                # Schema creation/migration
│   ├── models.py                # Dataclasses for entities
│   └── repository.py            # CRUD operations
├── api/
│   ├── __init__.py
│   ├── client.py                # OpenRouterClient
│   ├── parser.py                # API response parsing
│   ├── retry.py                 # RetryHandler with policies
│   └── error_handler.py         # Error classification
└── utils/
    ├── __init__.py
    ├── config.py                # Settings management
    └── logging.py               # Logging setup
```

### Responsibility Boundaries

| Module | Responsibility | Forbidden |
|--------|---------------|-----------|
| `cli/*` | Argument parsing, command routing, output formatting | Business logic, DB access, API calls |
| `core/*` | Domain logic, execution orchestration, plan building | Direct CLI concerns, DB access (except Planner read) |
| `db/*` | Schema definitions, data access, CRUD operations | Business logic, API calls, CLI concerns |
| `api/*` | External API integration, retry, error handling | Business logic, DB access, CLI concerns |
| `utils/*` | Cross-cutting concerns (config, logging) | Domain logic, business rules |

### Import Rules

**Enforced via linting and code review**:

```
cli/*       → can import: core/*, db/*, utils/*
              cannot import: api/* (indirect via core)

core/*      → can import: api/*, db/*, utils/*
              cannot import: cli/*

db/*        → can import: utils/*
              cannot import: cli/*, core/*, api/*

api/*       → can import: utils/*
              cannot import: cli/*, core/*, db/*

utils/*     → cannot import: any internal module
```

**Circular Dependency Prevention**:
- Dependency direction is strictly acyclic
- `utils` is the leaf (no internal dependencies)
- `db` and `api` are independent (both depend only on `utils`)
- `core` orchestrates `db` and `api` but never vice-versa
- `cli` is the consumer (depends on everything, depended on by nothing)

---

## CLI Design (Command-Per-Module)

### bcllm_experiment.py

**Purpose**: Experiment lifecycle management

**Commands**:

| Command | Arguments | Validation | Side Effects |
|---------|-----------|------------|--------------|
| `--create-experiment` | `<name>`, `--description`, `--config` | Name uniqueness | INSERT `experiments`, snapshot default questions |
| `--experiment` | `<name>`, `--output` | Experiment exists | None (read-only) |
| `--list-experiments` | `--status`, `--output` | None | None (read-only) |
| `--remove-experiment` | `<name>` | Experiment exists | UPDATE `is_active = FALSE` (soft delete) |

**Output Format**:
- Console by default (human-readable)
- `--output json|csv|markdown` for export

**Error Handling**:
```python
try:
    experiment = repo.get_by_name(name)
except ExperimentNotFoundError:
    print_error(f"Experiment not found: {name}")
    sys.exit(1)
except ExperimentNameCollisionError:
    print_error(f"Experiment already exists: {name}")
    sys.exit(1)
```

**Exit Codes**:
- `0`: Success
- `1`: Validation error (not found, collision, invalid input)

---

### bcllm_model.py

**Purpose**: Model variant management within experiments

**Commands**:

| Command | Arguments | Validation | Side Effects |
|---------|-----------|------------|--------------|
| `--add-model` | `<experiment>`, `<model_id>`, `--variant-signature`, `--reasoning-mode`, `--reasoning-effort`, `--vision`, `--structured-output` | Experiment exists, model ID format | INSERT `model_variants` |
| `--list-models` | `<experiment>`, `--status`, `--output` | Experiment exists | None (read-only) |
| `--remove-model` | `<experiment>`, `<variant_id>` | Experiment exists, variant exists | UPDATE `is_active = FALSE` |

**Validation Rules**:
- Model ID format: `<provider>/<model-name>` (e.g., `openai/gpt-4`)
- Variant signature uniqueness within experiment
- Reasoning mode: `off`, `auto`, `effort`, `budget`, `unspecified`
- Reasoning effort: `xhigh`, `high`, `medium`, `low`, `minimal`

**Error Handling**:
```python
if not re.match(r'^[a-z0-9-]+/[a-z0-9-]+$', model_id):
    print_error(f"Invalid model ID format: {model_id}")
    print_hint("Expected: provider/model-name (e.g., openai/gpt-4)")
    sys.exit(1)
```

---

### bcllm_questions.py

**Purpose**: Question snapshot management

**Commands**:

| Command | Arguments | Validation | Side Effects |
|---------|-----------|------------|--------------|
| `--add-questions` | `<experiment>`, `<spec>`, `--source-file` | Experiment exists, spec format | INSERT `question_snapshots` (idempotent) |
| `--list-questions` | `<experiment>`, `--output` | Experiment exists | None (read-only) |
| `--remove-question` | `<experiment>`, `<snapshot_id>` | Experiment exists, snapshot exists | UPDATE `is_active = FALSE` |

**Question Spec Format**:
```
# Single question
--add-questions q11

# Range
--add-questions 1-10

# Comma-separated list
--add-questions q11,q12,q13

# Mixed
--add-questions 1-5,q10,q15-q20
```

**Idempotency**:
- If snapshot already exists for `(experiment_id, question_id)`, skip silently
- Log: "Question {question_id} already snapped to {experiment_name}"

---

### bcllm_run.py

**Purpose**: Run lifecycle management

**Commands**:

| Command | Arguments | Validation | Side Effects |
|---------|-----------|------------|--------------|
| `--create-run` | `<experiment>`, `--seed`, `--name` | Experiment has ≥1 model, ≥1 snapshot | INSERT `runs` with status=`pending` |
| `--list-runs` | `<experiment>`, `--status`, `--output` | Experiment exists | None (read-only) |
| `--run` | `<experiment>`, `<run_name>`, `--output` | Run exists | None (read-only) |
| `--remove-run` | `<experiment>`, `<run_name>` | Run exists, status=`pending` | DELETE `runs` (only pending runs) |

**Preconditions for `--create-run`**:
```python
if experiment.model_count == 0:
    print_error(f"Experiment '{name}' has no models. Add models first:")
    print_hint(f"  bcllm_model.py --experiment {name} --add-model <model_id>")
    sys.exit(1)

if experiment.snapshot_count == 0:
    print_error(f"Experiment '{name}' has no questions. Add questions first:")
    print_hint(f"  bcllm_questions.py --experiment {name} --add-questions <spec>")
    sys.exit(1)
```

---

### bcllm_execute.py

**Purpose**: Execution entry point

**Commands**:

| Command | Arguments | Validation | Side Effects |
|---------|-----------|------------|--------------|
| `--execute` | `<experiment>`, `--run`, `--retry-only-failed` | Experiment exists, run exists and is pending/failed/partial_failed | INSERT `responses`, INSERT `errors`, UPDATE `runs.status` |

**Execution Flow**:
```
1. Validate experiment and run exist
2. Planner.build_plan(experiment_name, run_ids=[run_id])
   → Returns ExecutionPlan (immutable)
3. ExecutionEngine.execute(plan)
   → Returns list[ExecutionResult]
4. ResultWriter.write_results(results)
   → Persists to DB, updates run status
5. Report summary to console
```

**Validation**:
- Run status must be `pending`, `running`, `failed`, or `partial_failed`
- Experiment must have active models and snapshots
- API key must be configured

**Error Handling**:
```python
try:
    plan = planner.build_plan(experiment_name, run_ids=[run_id])
except PlannerValidationError as e:
    print_error(f"Cannot build execution plan: {e}")
    sys.exit(1)

try:
    results = engine.execute(plan)
except APIAuthenticationError:
    print_error("API authentication failed. Check OPENROUTER_API_KEY")
    sys.exit(1)
```

---

## Database Schema

### Tables

#### experiments

```sql
CREATE TABLE experiments (
    experiment_id     TEXT PRIMARY KEY,
    name              TEXT UNIQUE NOT NULL,
    description       TEXT,
    config_json       TEXT NOT NULL,           -- Frozen configuration snapshot
    config_hash       TEXT NOT NULL,           -- SHA-256 of protocol config
    system_prompt     TEXT NOT NULL,           -- Prompt template
    user_prompt       TEXT NOT NULL,           -- Prompt template
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_experiments_active ON experiments(is_active) WHERE is_active = TRUE;
```

#### model_variants

```sql
CREATE TABLE model_variants (
    variant_id        TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    model_id          TEXT NOT NULL,           -- Base model (e.g., "openai/gpt-4")
    variant_signature TEXT NOT NULL,           -- Human-readable identity
    reasoning_mode    TEXT NOT NULL DEFAULT 'off',
    reasoning_effort  TEXT,                    -- 'xhigh', 'high', 'medium', 'low', 'minimal'
    max_output_tokens INTEGER,                 -- When mode='budget'
    vision_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    structured_output BOOLEAN NOT NULL DEFAULT FALSE,
    web_access_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(experiment_id, variant_signature)
);

CREATE INDEX idx_variants_by_experiment ON model_variants(experiment_id) WHERE is_active = TRUE;
```

#### question_snapshots

```sql
CREATE TABLE question_snapshots (
    snapshot_id       TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    question_id       TEXT NOT NULL,
    question_payload  TEXT NOT NULL,           -- Complete question JSON
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(experiment_id, question_id)
);

CREATE INDEX idx_snapshots_by_experiment ON question_snapshots(experiment_id) WHERE is_active = TRUE;
```

#### runs

```sql
CREATE TABLE runs (
    run_id            TEXT PRIMARY KEY,
    experiment_id     TEXT NOT NULL REFERENCES experiments(experiment_id),
    seed              INTEGER,                 -- Nullable (None = no randomization)
    status            TEXT NOT NULL DEFAULT 'pending',
    started_at        TIMESTAMP,
    finished_at       TIMESTAMP,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(status IN ('pending', 'running', 'completed', 'failed', 'partial_failed'))
);

CREATE INDEX idx_runs_by_experiment ON runs(experiment_id);
CREATE INDEX idx_runs_pending ON runs(status) WHERE status = 'pending';
```

#### responses

```sql
CREATE TABLE responses (
    response_id       TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
    snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
    model_id          TEXT NOT NULL,           -- Redundant for querying
    question_id       TEXT NOT NULL,           -- Redundant for querying
    response_text     TEXT,                    -- Full model response
    selected_answer   TEXT,                    -- Parsed answer (A/B/C/D)
    is_correct        BOOLEAN,                 -- Derived (may be NULL)
    parse_confidence  TEXT DEFAULT 'unknown',  -- 'unknown', 'clear', 'ambiguous', 'no_answer', 'low_confidence'
    needs_review      BOOLEAN NOT NULL DEFAULT FALSE,  -- Derived by ResultWriter
    manual_answer     TEXT,                    -- Human override (optional)
    latency_ms        INTEGER,
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, variant_id, snapshot_id)
);

CREATE INDEX idx_responses_needs_review ON responses(needs_review) WHERE needs_review = TRUE;
CREATE INDEX idx_responses_by_run ON responses(run_id);
```

#### errors

```sql
CREATE TABLE errors (
    error_id          TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs(run_id),
    variant_id        TEXT NOT NULL REFERENCES model_variants(variant_id),
    snapshot_id       TEXT NOT NULL REFERENCES question_snapshots(snapshot_id),
    error_type        TEXT NOT NULL,           -- 'api_error', 'timeout', 'parse_error', 'config_error'
    error_message     TEXT NOT NULL,
    attempt_count     INTEGER NOT NULL DEFAULT 1,
    stack_trace       TEXT,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_errors_by_run ON errors(run_id);
```

### Breaking Changes from Legacy

| Change | Legacy | TO-BE | Rationale | Impact |
|--------|--------|-------|-----------|--------|
| `model_variants.experiment_id` | NULL (global variants) | NOT NULL FK | Variants belong to experiments | **Breaking**: Legacy variants must be migrated or discarded |
| `question_snapshots.experiment_id` | NULL (optional association) | NOT NULL FK | Snapshots belong to experiments | **Breaking**: Legacy snapshots must be migrated or discarded |
| `responses.variant_id` | NULL (inferred from execution context) | NOT NULL FK | Explicit variant tracking | **Breaking**: Legacy responses cannot be migrated automatically |
| `responses.snapshot_id` | NULL (inferred) | NOT NULL FK | Explicit snapshot tracking | **Breaking**: Legacy responses cannot be migrated automatically |
| Soft deletes | None (hard delete only) | `is_active` flag on all entities | Preserve history, prevent new usage | **Non-breaking**: Legacy data treated as active |
| Review fields | None | `parse_confidence`, `needs_review`, `manual_answer` | Manual review workflow | **Additive**: Existing queries unaffected |

### Migration Strategy

**No automatic migration**. Legacy data remains in `src/` database. TO-BE schema is fresh:

1. Export needed data from legacy (experiments, models, questions)
2. Re-import into TO-BE via CLI commands
3. Legacy responses/errors remain archived (read-only access for historical reports)

---

## Core Contracts Implementation

### ExecutionPlan

**Structure** (immutable dataclasses):

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass(frozen=True)
class ExecutionPlan:
    """Immutable, self-contained description of work to execute."""
    plan_id: str
    created_at: datetime
    experiment_id: str
    runs: list['PlanRun']

@dataclass(frozen=True)
class PlanRun:
    """Single run within an execution plan."""
    run_id: str
    seed_effective: int | None
    prompts_effective: Prompts
    retry_policy: RetryPolicy
    variants: list[PlanVariant]
    items: list[PlanItem]

@dataclass(frozen=True)
class Prompts:
    """Resolved prompt templates."""
    system: str
    user: str

@dataclass(frozen=True)
class RetryPolicy:
    """Per-run retry configuration."""
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    retry_on: tuple[str, ...] = ('timeout', 'http_429', 'http_5xx', 'network_error')

@dataclass(frozen=True)
class PlanVariant:
    """Model variant with resolved configuration."""
    variant_id: str
    model_id: str
    model_config_effective: ModelConfig

@dataclass(frozen=True)
class ModelConfig:
    """All parameters that affect model behavior."""
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    enable_vision: bool = False
    structured_output: bool = False
    reasoning_mode: str = 'off'
    reasoning_effort: str | None = None

@dataclass(frozen=True)
class PlanItem:
    """Single executable task."""
    item_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    question_id: str
    question_payload: QuestionPayload

@dataclass(frozen=True)
class QuestionPayload:
    """Snapshotted question data."""
    stem: str
    options: list[str]
    answer_key: str
```

**Immutability Guarantees**:
- All dataclasses use `frozen=True`
- No methods that modify instance state
- Passed by value, not reference
- Planner is the only creator

---

### ExecutionEngine

**Interface**:

```python
class ExecutionEngine:
    """Pure execution engine with no database access."""

    def __init__(
        self,
        api_client: OpenRouterClient,
        randomizer: AnswerRandomizer,
        parser: AnswerParser,
    ) -> None:
        """
        Initialize engine with dependencies.

        Args:
            api_client: OpenRouter API client
            randomizer: Answer option randomizer (seeded)
            parser: Response parser with confidence levels
        """

    def execute(self, plan: ExecutionPlan) -> list['ExecutionResult']:
        """
        Execute all items in the plan.

        Args:
            plan: Immutable execution plan from Planner

        Returns:
            List of ExecutionResult (one per item)

        Constraints:
            - NO database access
            - NO configuration resolution
            - NO scope decisions
            - Returns pure data only
        """
```

**ExecutionResult Structure**:

```python
@dataclass
class ExecutionResult:
    """Result of executing a single PlanItem."""
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

---

### ResultWriter

**Interface**:

```python
class ResultWriter:
    """Persists execution outcomes to database."""

    def __init__(self, db_connection: sqlite3.Connection) -> None:
        """Initialize with database connection."""

    def write_results(
        self,
        results: list[ExecutionResult],
    ) -> WriteReport:
        """
        Persist execution results.

        Args:
            results: List of ExecutionResult from ExecutionEngine

        Returns:
            WriteReport with counts and run status updates

        Responsibilities:
            - Calculate needs_review before INSERT
            - Idempotent writes (UNIQUE constraint + INSERT OR IGNORE)
            - Update run status after all writes
        """
```

**WriteReport Structure**:

```python
@dataclass
class WriteReport:
    """Summary of write operations."""
    responses_written: int
    responses_skipped: int  # Already existed (idempotency)
    errors_written: int
    runs_updated: list[tuple[str, str]]  # (run_id, new_status)
```

**Idempotency Mechanism**:

```python
def _write_response(self, result: ExecutionResult) -> bool:
    """
    Write single response with idempotency.

    Returns:
        True if written, False if already existed
    """
    needs_review = self._calculate_needs_review(
        result.parse_confidence,
        result.selected_answer,
    )

    cursor.execute("""
        INSERT OR IGNORE INTO responses (
            response_id, run_id, variant_id, snapshot_id,
            model_id, question_id, response_text, selected_answer,
            parse_confidence, needs_review, latency_ms,
            input_tokens, output_tokens
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        generate_id(),
        result.run_id,
        result.variant_id,
        result.snapshot_id,
        result.variant_id,  # model_id from variant
        result.question_id,
        result.response_text,
        result.selected_answer,
        result.parse_confidence,
        needs_review,
        result.latency_ms,
        result.input_tokens,
        result.output_tokens,
    ))

    return cursor.rowcount > 0
```

---

### Planner

**Interface**:

```python
class Planner:
    """Builds immutable ExecutionPlan from database state."""

    def __init__(self, db_connection: sqlite3.Connection) -> None:
        """Initialize with database connection."""

    def build_plan(
        self,
        experiment_name: str,
        run_ids: list[str] | None = None,
    ) -> ExecutionPlan:
        """
        Build execution plan for experiment.

        Args:
            experiment_name: Human-readable experiment name
            run_ids: Optional list of specific runs (default: all pending)

        Returns:
            Immutable ExecutionPlan

        Raises:
            PlannerValidationError: If experiment has no models/snapshots
            ExperimentNotFoundError: If experiment doesn't exist
        """
```

**Responsibilities**:
- Read experiment, runs, variants, snapshots from DB
- Resolve `prompts_effective` (run overrides experiment)
- Resolve `seed_effective` (run overrides experiment)
- Build ExecutionPlan with resolved values
- Deduplicate by `(run_id, variant_id, snapshot_id)` per run
- Apply filters if provided

**Validation Rules**:
```python
def _validate_experiment(self, experiment: Experiment) -> None:
    if not experiment.variants:
        raise PlannerValidationError(
            f"Experiment '{experiment.name}' has no models. "
            "Add models before creating runs."
        )
    if not experiment.snapshots:
        raise PlannerValidationError(
            f"Experiment '{experiment.name}' has no questions. "
            "Add questions before creating runs."
        )
```

---

## API Layer

### OpenRouterClient

**Interface**:

```python
class OpenRouterClient:
    """OpenRouter API client with retry support."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        """Initialize with API credentials."""

    async def chat_completion(
        self,
        model_id: str,
        messages: list[Message],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: list[str] | None = None,
    ) -> CompletionResponse:
        """
        Call OpenRouter chat completion API.

        Args:
            model_id: Model identifier (e.g., "openai/gpt-4")
            messages: List of messages (system, user)
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            max_tokens: Maximum output tokens
            stop: Stop sequences

        Returns:
            CompletionResponse with content and metadata

        Raises:
            APIError: HTTP errors, rate limits
            TimeoutError: Request timeouts
        """
```

**Message Structure**:

```python
@dataclass
class Message:
    """Single message in chat completion."""
    role: Literal['system', 'user', 'assistant']
    content: str
```

**CompletionResponse Structure**:

```python
@dataclass
class CompletionResponse:
    """Parsed API response."""
    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
```

---

### Retry Policy

**Per-run configuration** (in ExecutionPlan):

```python
@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff: Literal['exponential', 'linear', 'constant'] = 'exponential'
    retry_on: tuple[str, ...] = ('timeout', 'http_429', 'http_5xx', 'network_error')
```

**RetryHandler Implementation**:

```python
class RetryHandler:
    """Handles retry logic with configurable policies."""

    def __init__(self, policy: RetryPolicy) -> None:
        self.policy = policy

    async def execute_with_retry(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        **kwargs,
    ) -> T:
        """
        Execute function with retry policy.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all attempts fail
        """
        last_exception: Exception | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if not self._is_retryable(e):
                    raise
                if attempt < self.policy.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt} failed: {e}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

        raise last_exception  # type: ignore

    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable based on policy."""
        error_type = self._classify_error(error)
        return error_type in self.policy.retry_on

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay based on backoff strategy."""
        if self.policy.backoff == 'exponential':
            return 2 ** attempt
        elif self.policy.backoff == 'linear':
            return attempt
        else:  # constant
            return 1
```

---

### Response Parsing

**Strategy**: Hierarchical pattern matching

```python
class AnswerParser:
    """Parses LLM response to extract answer letter."""

    def parse(self, response_text: str) -> ParseResult:
        """
        Extract answer letter from response.

        Args:
            response_text: Full model response

        Returns:
            ParseResult with selected_answer and confidence
        """
        # Strategy 1: Explicit letter pattern (e.g., "Answer: B")
        match = re.search(r'\b(?:answer(?:\s*:)?\s*)([A-D])\b', response_text, re.IGNORECASE)
        if match:
            return ParseResult(selected_answer=match.group(1).upper(), confidence='clear')

        # Strategy 2: Letter in parentheses (e.g., "(B)")
        match = re.search(r'\(([A-D])\)', response_text, re.IGNORECASE)
        if match:
            return ParseResult(selected_answer=match.group(1).upper(), confidence='clear')

        # Strategy 3: Standalone letter at line start
        match = re.search(r'^([A-D])\b', response_text, re.MULTILINE | re.IGNORECASE)
        if match:
            return ParseResult(selected_answer=match.group(1).upper(), confidence='ambiguous')

        # No answer found
        return ParseResult(selected_answer=None, confidence='no_answer')
```

**ParseResult Structure**:

```python
@dataclass
class ParseResult:
    """Result of answer parsing."""
    selected_answer: str | None
    confidence: Literal['clear', 'ambiguous', 'no_answer', 'low_confidence']
```

---

### Error Classification

**Error Types**:

```python
class APIError(Exception):
    """HTTP errors from API (4xx, 5xx)."""

class TimeoutError(Exception):
    """Request timeout."""

class ParseError(Exception):
    """Response parsing failure."""

class ConfigurationError(Exception):
    """Invalid model/variant configuration."""
```

**ErrorHandler Implementation**:

```python
class APIErrorHandler:
    """Classifies API errors for retry decisions."""

    @staticmethod
    def classify(response: httpx.Response) -> str:
        """
        Classify HTTP response error.

        Returns:
            Error type string for retry policy
        """
        if response.status_code == 429:
            return 'http_429'
        elif 500 <= response.status_code < 600:
            return 'http_5xx'
        elif 400 <= response.status_code < 500:
            return 'http_4xx'  # Not retryable
        else:
            return 'unknown'
```

---

## Test Strategy

### Test File Structure

```
tests/
├── conftest.py                    # Shared fixtures, pytest configuration
├── factories/
│   ├── experiment.py              # ExperimentFactory
│   ├── variant.py                 # VariantFactory
│   ├── snapshot.py                # SnapshotFactory
│   ├── run.py                     # RunFactory
│   └── response.py                # ResponseFactory
├── unit/
│   ├── core/
│   │   ├── test_planner.py
│   │   ├── test_execution_engine.py
│   │   ├── test_result_writer.py
│   │   ├── test_execution_plan.py
│   │   ├── test_randomizer.py
│   │   └── test_answer_parser.py
│   ├── api/
│   │   ├── test_client.py
│   │   ├── test_retry.py
│   │   └── test_error_handler.py
│   ├── db/
│   │   ├── test_repository.py
│   │   └── test_schema.py
│   └── cli/
│       ├── test_experiment.py
│       ├── test_model.py
│       ├── test_questions.py
│       ├── test_run.py
│       └── test_execute.py
└── integration/
    ├── test_end_to_end.py
    ├── test_cli_workflow.py
    └── test_review_workflow.py
```

### Unit Test Focus

**Domain Rules** (highest priority — test first):

| Component | Rule | Test Example |
|-----------|------|--------------|
| ExecutionPlan | Immutability (frozen dataclass) | `test_plan_is_immutable()` |
| ExecutionEngine | No DB access | `test_engine_has_no_db_access()` |
| ResultWriter | Calculates needs_review | `test_writer_calculates_needs_review()` |
| Planner | Deduplication per run | `test_planner_deduplicates_within_run()` |
| RetryHandler | Exponential backoff | `test_retry_exponential_backoff()` |
| AnswerParser | Confidence levels | `test_parser_confidence_levels()` |

**Contracts** (second priority):

| Component | Contract | Test Example |
|-----------|----------|--------------|
| CLI commands | Validation errors | `test_create_run_without_models_fails()` |
| API client | Interface compliance | `test_client_returns_completion_response()` |
| Repository | CRUD operations | `test_repository_crud_experiment()` |

### Fixture Strategy

**Factories** (custom implementation, no factory_boy dependency):

```python
# tests/factories/experiment.py
class ExperimentFactory:
    """Factory for creating Experiment instances."""

    @staticmethod
    def create(
        name: str | None = None,
        description: str | None = None,
        system_prompt: str = "You are a helpful assistant.",
        user_prompt: str = "Answer the question.",
        **overrides,
    ) -> Experiment:
        """Create an Experiment with defaults."""
        return Experiment(
            experiment_id=overrides.get('experiment_id', f"exp-{uuid4().hex[:8]}"),
            name=name or f"experiment-{uuid4().hex[:8]}",
            description=description,
            config_json=overrides.get('config_json', '{}'),
            config_hash=overrides.get('config_hash', 'abc123'),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
```

**In-Memory Database Fixture**:

```python
# tests/conftest.py
import pytest
import sqlite3

@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database with schema."""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row

    # Load and execute schema
    schema_sql = load_schema_sql()
    conn.executescript(schema_sql)
    conn.commit()

    yield conn

    conn.close()
```

**Mock API Client**:

```python
# tests/conftest.py
from unittest.mock import MagicMock

@pytest.fixture
def mock_api_client():
    """Mock OpenRouterClient for unit tests."""
    client = MagicMock(spec=OpenRouterClient)
    client.chat_completion.return_value = CompletionResponse(
        content="The answer is (B).",
        model_id="openai/gpt-4",
        input_tokens=50,
        output_tokens=10,
        latency_ms=500,
    )
    return client
```

### Mocking Strategy

**API Client** (unit tests):
```python
def test_execution_engine_calls_api(mock_api_client):
    engine = ExecutionEngine(mock_api_client, randomizer, parser)
    results = engine.execute(plan)
    mock_api_client.chat_completion.assert_called_once()
```

**Database** (unit tests):
```python
def test_result_writer_persists_results(in_memory_db):
    writer = ResultWriter(in_memory_db)
    report = writer.write_results(results)
    assert report.responses_written > 0
```

**Integration Tests** (real DB, mocked API):
```python
def test_end_to_end_execution(in_memory_db, mock_api_client):
    # Seed database with experiment, models, snapshots, run
    # Build plan with Planner (real DB)
    # Execute with ExecutionEngine (mocked API)
    # Write with ResultWriter (real DB)
    # Assert responses and errors exist
```

### Coverage Targets

**Initial** (Phases 4-7 — foundation):
- No enforced thresholds
- Focus: Domain rules and contracts (100% of core logic)
- Accept: CLI and integration gaps

**Eventual** (Phase 10 — stabilization):

| Module | Target | Rationale |
|--------|--------|-----------|
| `src_v2/core/` | 80% line coverage | Domain logic is critical |
| `src_v2/api/` | 70% line coverage | External integration, harder to test |
| `src_v2/db/` | 70% line coverage | CRUD is straightforward |
| `src_v2/cli/` | 60% line coverage | Thin wrappers, integration tested |

---

## File Size Discipline

### Phase 1 (Rewrite: Phases 4-9)

**Purpose**: Avoid artificial fragmentation during domain modeling. Focus on correct boundaries first.

| Metric | Limit | Enforcement | Action |
|--------|-------|-------------|--------|
| File size | 400-500 lines | Warning only | Log warning, continue |
| Function size | 50 lines | Warning only | Log warning, continue |
| Class size | 200 lines | Warning only | Log warning, continue |

**Tooling**:
```python
# scripts/check_file_size.py
import ast
import sys

MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 50
MAX_CLASS_LINES = 200

def check_file(filepath: str) -> list[str]:
    warnings = []
    with open(filepath) as f:
        lines = f.readlines()

    if len(lines) > MAX_FILE_LINES:
        warnings.append(
            f"⚠️  {filepath}: {len(lines)} lines (limit: {MAX_FILE_LINES})"
        )

    tree = ast.parse(''.join(lines))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_lines = node.end_lineno - node.lineno + 1
            if func_lines > MAX_FUNCTION_LINES:
                warnings.append(
                    f"⚠️  {filepath}:{node.lineno} function {node.name}() "
                    f"has {func_lines} lines (limit: {MAX_FUNCTION_LINES})"
                )
        elif isinstance(node, ast.ClassDef):
            class_lines = node.end_lineno - node.lineno + 1
            if class_lines > MAX_CLASS_LINES:
                warnings.append(
                    f"⚠️  {filepath}:{node.lineno} class {node.name} "
                    f"has {class_lines} lines (limit: {MAX_CLASS_LINES})"
                )

    return warnings
```

### Phase 2 (Stabilization: Phase 10)

**Purpose**: Enforce maintainability through strict size limits.

| Metric | Limit | Enforcement | Action |
|--------|-------|-------------|--------|
| File size | 200 lines | Linting failure | CI/CD blocks merge |
| Function size | 30 lines | Linting failure | CI/CD blocks merge |
| Class size | 100 lines | Linting failure | CI/CD blocks merge |

**Refactoring Triggers**:
- File > 200 lines → Split by responsibility (extract module)
- Function > 30 lines → Extract helper methods
- Class > 100 lines → Extract value objects, services

**Pylint Configuration**:

```ini
# .pylintrc
[MESSAGES CONTROL]
disable=
    duplicate-code,          # Accept some duplication during refactor
    too-few-public-methods,  # Dataclasses are OK
    missing-docstring,       # Enforced separately
enable=
    too-many-locals,
    too-many-statements,
    too-many-branches,

[DESIGN]
max-args = 5
max-locals = 15
max-returns = 6
max-branches = 12
max-statements = 30          # Hard limit in Phase 10
max-module-lines = 200       # Hard limit in Phase 10
max-attributes = 7
max-public-methods = 20
```

---

## Migration Path

### Phase 4-5: Foundation

**Deliverables**:
- Test infrastructure (conftest, factories, fixtures)
- Core domain: ExecutionPlan, ExecutionEngine, ResultWriter, Planner
- Unit tests for domain rules

**Validation**:
- All domain rule tests pass
- ExecutionPlan immutability verified
- ExecutionEngine has no DB access (static analysis)

---

### Phase 6: Database

**Deliverables**:
- New schema (TO-BE tables)
- Repository layer (CRUD operations)
- Dataclasses for entities

**Validation**:
- Schema creation script works
- Repository CRUD tests pass
- Foreign key constraints enforced

---

### Phase 7: CLI

**Deliverables**:
- Command-per-module scripts (5 entry points)
- One command at a time, test-first
- Output formatters (console, JSON, CSV, Markdown)

**Validation**:
- Each command validated in isolation
- Integration tests for common workflows

---

### Phase 8: API

**Deliverables**:
- OpenRouter client
- Retry handler
- Response parser
- Error classifier

**Validation**:
- Mocked API tests pass
- Retry policy behavior verified
- Parser confidence levels correct

---

### Phase 9: Integration

**Deliverables**:
- End-to-end tests
- Full workflow validation (create experiment → execute → review)
- Performance profiling

**Validation**:
- All integration tests pass
- Execution time within acceptable bounds

---

### Phase 10: Hard Limits

**Deliverables**:
- Code review against 200/30 limits
- Refactoring to split oversized files
- Final coverage report

**Validation**:
- All files ≤ 200 lines
- All functions ≤ 30 lines
- Coverage targets met

---

### Phase 11: Cutover (Deferred)

**Steps**:
1. Archive `src/` → `Arquivos_Mortos/_archived/legacy-src/`
2. Move `src_v2/` → `src/`
3. Update `bcllm.py` entry point to new CLI modules
4. Update documentation references
5. Tag release: `v2.0.0`

---

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **AI confusion (old vs new code)** | High | Medium | Legacy is read-only reference; never read `src/` during TO-BE implementation; use `src_v2/` namespace |
| **Scope creep** | Medium | Medium | Strict adherence to contracts; one file at a time; test-first discipline; reject features not in specification |
| **Test debt accumulation** | Medium | Medium | Test-first for domain rules; coverage gates in Phase 10; CI/CD integration |
| **File size creep** | Low | High | Warnings in Phase 1; hard linting limits in Phase 10; refactoring triggers documented |
| **Dual execution paths** | Medium | Low | Remove legacy code as each new command is validated; no coexistence |
| **Breaking change resistance** | Medium | Low | Clean-slate mindset; legacy data archived, not migrated; fresh start |
| **API rate limits during testing** | Low | Medium | Mocked API for unit tests; rate-limited integration tests; backoff policies |

---

**Specification Completed**: 2026-03-20
**Next Phase**: Phase 4 — Test Infrastructure Setup
