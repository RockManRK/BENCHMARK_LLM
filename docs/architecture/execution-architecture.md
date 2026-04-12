---
type: conceptual
audience: both
last-validated: 2026-04-11
status: active
---

# Execution Architecture

**Purpose:** Component relationships and data flow  
**Scope:** How Planner, ExecutionEngine, and ResultWriter work together

---

## Architectural Pattern

The system follows a **CQRS-inspired separation** between:

- **Read side (Planner):** Reads database state, builds execution plan
- **Write side (ResultWriter):** Writes execution results to database
- **Execution side (ExecutionEngine):** Pure execution; no database access

This ensures:
- Planning cannot modify data
- Execution cannot modify data directly
- Only ResultWriter writes to database
- Each component has clear, auditable responsibilities

---

## Component Overview

```
┌────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  bcllm.py → src/cli/bcllm_*.py                             │
│  Purpose: Parse arguments, dispatch to modules              │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                      Planner                                │
│  src/core/planner.py                                        │
│  Purpose: Read DB → Build immutable ExecutionPlan           │
│  Properties: Read-only, validates preconditions             │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                   ExecutionPlan                             │
│  src/core/execution_plan.py                                 │
│  Purpose: Immutable, self-contained description of work     │
│  Properties: frozen=True, auditable, reproducible           │
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                   ExecutionEngine                           │
│  src/core/execution_engine.py                               │
│  Purpose: Execute plan items against LLM APIs               │
│  Properties: No DB access, pure execution, returns results  │
│  Dependencies: OpenRouterClient, AnswerRandomizer, AnswerParser
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                   ResultWriter                              │
│  src/core/result_writer.py                                  │
│  Purpose: Persist execution results to database             │
│  Properties: ONLY DB write component, idempotent            │
│  Calculates: needs_review from parse_confidence + selected_answer
└──────────────────────────┬─────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                     Database                                │
│  SQLite (benchmark.db)                                      │
│  Purpose: Persistent storage of all entities and results    │
└────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Responsibilities

### 1. Planner (`src/core/planner.py`)

**Role:** Read-only plan builder

**Responsibilities:**
- Validate experiment exists and has prerequisites (models, snapshots)
- Read experiment configuration from database
- Read runs, model variants, question snapshots from database
- Resolve effective values (run overrides experiment)
- Build ExecutionPlan with deduplicated items
- Apply filters (run IDs, question IDs, model variant IDs)
- Support partial execution planning

**Does NOT:**
- Write to database
- Execute anything
- Make decisions about what should run
- Infer missing configuration

**Input:** Database connection + experiment name + optional filters  
**Output:** ExecutionPlan (immutable dataclass)

### 2. ExecutionEngine (`src/core/execution_engine.py`)

**Role:** Pure execution of plan items

**Responsibilities:**
- Execute each plan item against the LLM API
- Randomize answer options (if seed is set)
- Parse LLM responses for selected answer
- Return ExecutionResult for each item
- Handle errors gracefully
- Support parallel execution (via async)
- Support partial execution (resume from where left off)

**Does NOT:**
- Access database directly
- Resolve configuration (uses plan's effective values)
- Decide what to execute (plan determines scope)
- Write results (delegates to ResultWriter)

**Dependencies:**
- OpenRouterClient (or other API client)
- AnswerRandomizer
- AnswerParser

**Input:** ExecutionPlan  
**Output:** List of ExecutionResult dataclasses

### 3. ResultWriter (`src/core/result_writer.py`)

**Role:** ONLY database write component

**Responsibilities:**
- Write successful responses to `responses` table
- Write errors to `errors` table
- Calculate `needs_review` flag from `parse_confidence` and `selected_answer`
- Update run status (pending → running → completed/failed)
- Ensure idempotency (UNIQUE constraint + INSERT OR IGNORE)
- Write results incrementally (not batch-at-end)

**Does NOT:**
- Execute anything (receives results from ExecutionEngine)
- Make decisions about what to run
- Resolve configuration

**Input:** ExecutionResult from ExecutionEngine  
**Output:** Database records

---

## Data Flow Sequence

### Complete Execution Flow

```
1. User: bcllm --experiment my_exp --execute
2. CLI: Dispatches to bcllm_execute.py
3. Planner: Reads DB
   ├── Read experiment (config_json, etc.)
   ├── Read runs (config, status)
   ├── Read model variants (config)
   ├── Read question snapshots (payload)
   └── Read existing responses (for idempotency)
4. Planner: Builds ExecutionPlan
   ├── Resolve effective seed per run
   ├── Resolve effective prompts per run
   ├── Resolve effective model config per variant
   ├── Build PlanItem for each unique combination
   └── Deduplicate already-completed items
5. ExecutionEngine: Executes plan
   ├── For each PlanItem:
   │   ├── Randomize options (if seed set)
   │   ├── Build API request with effective config
   │   ├── Send to LLM API
   │   ├── Receive response
   │   ├── Parse answer (selected_answer, confidence)
   │   └── Return ExecutionResult
   └── Return all results
6. ResultWriter: Writes results
   ├── For each ExecutionResult:
   │   ├── Calculate needs_review
   │   ├── INSERT OR IGNORE into responses
   │   └── Update run status
   └── Commit to database
```

---

## Execution Plan Structure

```
ExecutionPlan
├── plan_id
├── created_at
├── experiment_id
└── runs[]
    ├── run_id
    ├── seed_effective
    ├── prompts_effective
    │   ├── system_prompt
    │   └── user_prompt
    ├── retry_policy
    └── variants[]
        ├── variant_id
        ├── model_id
        └── model_config_effective
            └── ... (temperature, reasoning, etc.)
    └── items[]
        ├── item_id
        ├── run_id
        ├── variant_id
        ├── snapshot_id
        ├── question_id
        └── question_payload
            ├── stem
            ├── options
            ├── answer_key
            └── has_image
```

---

## API Layer

The system integrates with LLM providers through an API client abstraction layer.

**Current Implementation:** `OpenRouterClient` (`src/api/client.py`) provides integration with the OpenRouter platform.

**Design Principle:** OpenRouter is a **current implementation**, not a conceptual dependency. The system is designed to be **provider-agnostic** by design:
- API client is an abstract interface
- Different providers can be supported by implementing the same interface
- Provider-specific details (authentication, endpoints, features) are encapsulated in the client implementation
- Local model serving (e.g., llama.cpp) is also supported via separate client implementation

**Architecture Requirement:** All API interactions must go through the client abstraction — never direct HTTP calls from ExecutionEngine or other components.

---

## Parallel Execution

The system supports parallel execution:

- **ExecutionEngine** can process multiple items concurrently (async)
- **ResultWriter** writes results incrementally (not batched)
- **Idempotency** ensures no duplicates from parallel runs
- **Determinism** applies to content, not temporal order (parallel completion order varies)

**Controls:**
- `CONCURRENCY` setting in `.env` controls parallelism level
- Retry policy applies per-item, not globally

---

## Error Handling Flow

```
API Call
    ↓
Success? ──Yes──→ Parse Response → Return ExecutionResult
    │
   No
    │
    ↓
Retry? ──Yes──→ Wait (exponential backoff) → Retry API Call
    │
   No
    │
    ↓
Return ExecutionResult with error status
```

**Error Classification:**
- Network errors → Retry
- API errors (rate limit, auth) → Retry
- Parsing errors → Return with error details
- All errors logged with experiment/run/model/question context

---

## Contracts in Action

| Contract | Where Enforced |
|----------|---------------|
| Determinism | ExecutionEngine randomizer (seed=None vs seed=int) |
| Idempotency | ResultWriter (INSERT OR IGNORE + UNIQUE constraint) |
| Immutability | ExecutionPlan (frozen=True), snapshots (immutable) |
| Configuration Hierarchy | Planner (run overrides experiment) |
| System-Default | ConfigResolver (FORCE_SYSTEM_DEFAULT bypass) |
| Auditability | All entities carry FK chain to experiment |

See [contracts/](../contracts/README.md) for full contract specifications.

---

## Related Documents

- [overview.md](overview.md) — System at a glance
- [conceptual-model.md](conceptual-model.md) — Entity relationships
- [design-principles.md](design-principles.md) — Philosophy and trade-offs
- [contracts/](../contracts/README.md) — System invariants
