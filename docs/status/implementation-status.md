---
type: status
audience: both
last-validated: 2026-04-11
status: active
---

# Implementation Status

**Purpose:** What exists, what's partial, what's planned  
**Scope:** Current system state validated against code

---

## Implementation vs UX — Clarification

**Functional completeness** means the capability exists and produces correct data.

**UX quality** is tracked separately via notes and known issues.

**Rule:** Poor UI alone does not downgrade a capability to Partial unless it blocks usage.

**Examples:**
- "List model variants" is ✅ Complete functionally (returns correct data), but has a note: "Output/UI is minimal and needs improvement"
- "Review UI" is ⚠️ Partial because it **cannot be used** due to routing issues (blocks usage, not just poor UX)

This distinction is critical for future AI agents to correctly assess implementation status.

---

## Implemented Capabilities

### ✅ Experiment Management

| Capability | Status | Notes |
|------------|--------|-------|
| Create experiment | ✅ Complete | With frozen configuration |
| Show experiment | ⚠️ Partial | Command exists but output is incomplete; insufficient for real inspection |
| List experiments | ❌ Not implemented | Command not implemented |
| Remove experiment | ❌ Not implemented | Command not implemented |
| Modify experiment | ⚠️ Partial | Can add questions/models (works correctly); **cannot** change Randomization Seed, system prompt, or user prompt (not implemented) |

**Module:** `src/cli/bcllm_experiment.py`

### ✅ Model Variant Management

| Capability | Status | Notes |
|------------|--------|-------|
| Add model variant | ✅ Complete | One per command |
| List model variants | ✅ Complete | All variants in experiment; **Note:** Output/UI is minimal and needs improvement |
| Remove model variant | ✅ Complete | Prevents future use; historical data preserved |
| Configure model params | ✅ Complete | Reasoning, tokens, temperature, vision, structured, etc. |

**Module:** `src/cli/bcllm_model.py`

### ✅ Question Snapshot Management

| Capability | Status | Notes |
|------------|--------|-------|
| Add questions | ✅ Complete | Individual, range, mixed, filtered |
| List questions | ✅ Complete | All snapshots in experiment; **Note:** Output/UI is minimal and needs improvement |
| Filter questions | ✅ Complete | `--where`, `--exclude` support |
| Remove questions | ❌ Not supported | Questions are immutable |

**Module:** `src/cli/bcllm_questions.py`

### ✅ Run Management

| Capability | Status | Notes |
|------------|--------|-------|
| Create run | ✅ Complete | With Randomization Seed and prompt overrides |
| List runs | ✅ Complete | All runs with status |
| Show run | ✅ Complete | Configuration and status |
| Remove run | ✅ Complete | Prevents future execution; historical data preserved |

**Module:** `src/cli/bcllm_run.py`

### ✅ Execution

| Capability | Status | Notes |
|------------|--------|-------|
| Execute experiment | ✅ Complete | Planner → Engine → Writer flow |
| Execute specific run | ✅ Complete | `--run` filter |
| Execute specific questions | ✅ Complete | `--questions` filter |
| Execute specific models | ✅ Complete | `--models` filter |
| Partial execution | ✅ Complete | Skips completed items automatically |
| Parallel execution | ✅ Complete | Semaphore-based concurrency control |
| Async orchestration | ✅ Complete | Single event loop, shared client, sliding window |

**Module:** `src/cli/bcllm_execute.py`

### ✅ Answer Parsing

| Capability | Status | Notes |
|------------|--------|-------|
| Parse LLM responses | ✅ Complete | Multiple patterns recognized |
| Calculate confidence | ✅ Complete | `clear`, `ambiguous`, `no_answer`, `low_confidence`, `unknown` |
| Track experimental context | ✅ Complete | Randomization seed, options presented, letter map |

**Module:** `src/core/answer_parser.py`

### ✅ Answer Randomization

| Capability | Status | Notes |
|------------|--------|-------|
| Fisher-Yates shuffle | ✅ Complete | Deterministic with Randomization Seed |
| Seed control | ✅ Complete | `None` = off, `AUTO` = random, `int` = fixed |
| Experimental truth tracking | ✅ Complete | Options saved exactly as presented |

**Module:** `src/core/answer_randomizer.py`

### ⚠️ Manual Review

| Capability | Status | Notes |
|------------|--------|-------|
| Review UI (TUI) | ⚠️ Partial | **Blocked:** Review commands fail due to MODE × MODULE routing issues; flow cannot be validated in practice |
| Classification (A/B/C/D/N/E) | ⚠️ Partial | Implemented but untestable due to routing issues |
| Undo last | ⚠️ Partial | Single-level undo; untestable due to routing issues |
| Skip item | ⚠️ Partial | Implemented but untestable due to routing issues |
| Save progress | ⚠️ Partial | Implemented but untestable due to routing issues |
| Progress tracking | ⚠️ Partial | Implemented but untestable due to routing issues |
| Multi-language (PT/EN) | ❌ Not implemented | UI is currently single-language |
| Batch classification | ❌ Not implemented | One at a time only |
| Multi-level undo | ❌ Not implemented | Single-level only |

**Module:** `src/review/review_ui.py`

### ⚠️ Export

| Capability | Status | Notes |
|------------|--------|-------|
| Export results | ⚠️ Partial | **Requires validation:** Code exists but requires careful validation and redesign before being relied upon; not safe to mark Complete |
| Export by run | ⚠️ Partial | Single run export; requires validation |
| Computed fields | ⚠️ Partial | final_answer, answer_source, effective_tokens; requires validation |
| CSV export | ❌ Not implemented | JSON only currently |

**Module:** `src/core/export_service.py`

### ✅ Configuration System

| Capability | Status | Notes |
|------------|--------|-------|
| Configuration hierarchy | ✅ Complete | System → .env → Experiment → Run/Model |
| system-default semantics | ✅ Complete | Bypasses inheritance |
| Configuration freezing | ✅ Complete | At experiment/run creation |
| Null semantics | ✅ Complete | `None` = "not sent in API request" |
| FORCE_SYSTEM_DEFAULT | ✅ Complete | Explicit bypass constant |

**Module:** `src/core/config_resolver.py`

### ✅ Database Layer

| Capability | Status | Notes |
|------------|--------|-------|
| Schema creation | ✅ Complete | 6 tables, constraints, indexes |
| Repository pattern | ✅ Complete | CRUD operations via repositories |
| Entity dataclasses | ✅ Complete | All entities defined |
| Idempotent writes | ✅ Complete | UNIQUE constraint + INSERT OR IGNORE |
| Foreign key enforcement | ✅ Complete | SQLite FK constraints |

**Module:** `src/db/schema.py`, `src/db/models.py`, `src/db/repository.py`

### ✅ API Integration

| Capability | Status | Notes |
|------------|--------|-------|
| OpenRouter client | ✅ Complete | Async httpx-based |
| Streaming responses | ✅ Complete | Stream aggregator |
| Error classification | ✅ Complete | Network, auth, rate_limit, server, bad_request |
| Provider-agnostic interface | ✅ Complete | Abstract design |
| Local model serving | ✅ Partial | Supported via separate URL config |

**Module:** `src/api/client.py`

### ✅ Provider Locking (OpenRouter)

| Capability | Status | Notes |
|------------|--------|-------|
| Provider resolution | ✅ Complete | Via `--resolve-providers` command |
| Provider strategies | ✅ Complete | first, cheapest, fastest, lowest-latency |
| Provider locking | ✅ Complete | `--provider-lock true|false|system-default` |
| Pre-execution validation | ✅ Complete | Planner blocks execution if lock enabled and unresolved |
| Provider in API request | ✅ Complete | `provider.only` + `allow_fallbacks: false` |
| Provider persistence | ✅ Complete | Stored in `model_variants.config.PROVIDER` |
| ExecutionPlan inclusion | ✅ Complete | `resolved_provider` in `PlanVariant` |
| Idempotent resolution | ✅ Complete | Skips already-resolved variants |

**Modules:** `src/api/provider_resolver.py`, `src/cli/bcllm_provider.py`, `src/core/planner.py`, `src/core/execution_engine.py`, `src/core/execution_plan.py`

### ✅ Retry Safety

| Capability | Status | Notes |
|------------|--------|-------|
| Centralized retry | ✅ Complete | All API calls go through retry |
| Exponential backoff | ✅ Complete | Policy-driven |
| Linear backoff | ✅ Complete | Policy-driven |
| Max delay cap | ✅ Complete | Configurable |
| Retry logging | ✅ Complete | All attempts logged |

**Module:** `src/core/retry.py`

### ✅ Logging System

| Capability | Status | Notes |
|------------|--------|-------|
| Configurable logging | ✅ Complete | Via .env settings |
| File + console output | ✅ Complete | Separate levels |
| Log rotation | ✅ Complete | RotatingFileHandler with flush |
| Crash-safe logging | ✅ Complete | Immediate flush on every write |
| Structured logging | ✅ Partial | Standard format; context in messages |
| Experiment/run/model/question context | ✅ Partial | Included in log messages where applicable |

**Module:** `src/utils/logging_config.py`

---

## Partially Implemented Capabilities

### ⚠️ Review UI Enhancements

**What exists:** Single-language TUI with single-level undo  
**What's missing:** Batch classification, multi-level undo  
**Status:** Planned for future enhancement

### ⚠️ Export Formats

**What exists:** JSON export with computed fields  
**What's missing:** CSV export, other formats  
**Status:** Planned for future enhancement

### ⚠️ Local Model Serving

**What exists:** URL configuration for local servers  
**What's missing:** Dedicated llama.cpp client implementation  
**Status:** Supported via generic URL config; dedicated client not implemented

---

## Planned Capabilities

### 📝 Batch Classification

**Description:** Classify multiple items at once in review UI  
**Priority:** Medium  
**Dependencies:** Review UI refactor  

### 📝 Multi-Level Undo

**Description:** Undo history beyond last action in review UI  
**Priority:** Low  
**Dependencies:** Review UI state management  

### 📝 CSV Export

**Description:** Export results in CSV format for spreadsheet analysis  
**Priority:** Low  
**Dependencies:** Export service extension  

### 📝 Dedicated Local Model Client

**Description:** Native llama.cpp client implementation  
**Priority:** Low  
**Dependencies:** API client abstraction refinement  

---

## Not Implemented (Explicitly Not Goals)

| Capability | Rationale |
|------------|-----------|
| Real-time model serving | Batch-oriented system |
| Model training/fine-tuning | Evaluates existing models only |
| Automated research insights | Data collection only; analysis is downstream |
| Built-in visual dashboards | Export enables external visualization |
| Multi-user collaboration | Single-user research tool |
| Cloud-native deployment | Local execution with SQLite |
| Automatic experiment design | Human controls research intent |

---

## Related Documents

- [contracts/](../contracts/README.md) — System invariants
- [architecture/overview.md](../architecture/overview.md) — System at a glance
- [status/known-issues.md](known-issues.md) — What needs attention
- [status/roadmap.md](roadmap.md) — Intent and priorities
