# Database Layer — Gap Report

**Document Type:** Gap Analysis
**Domain:** Database Layer
**Comparison:** V1 (Legacy) → V2 (Current)
**Purpose:** Identify schema differences, missing features, and migration priorities

---

## 1. Feature Parity Matrix

| V1 Feature | V2 Status | Gap Severity | Notes |
|------------|-----------|--------------|-------|
| **experiments table** | ✅ Implemented | NONE | Same structure (removed global defaults) |
| **models table** | ❌ Removed | LOW | Intentional (model registry abandoned) |
| **model_variants table** | ✅ Implemented | NONE | Now scoped to experiments |
| **runs table** | ✅ Implemented | NONE | Simplified (removed grouping fields) |
| **question_snapshots table** | ✅ Implemented | NONE | Enhanced (json_question_id, question_position) |
| **responses table** | ✅ Implemented | NONE | Enhanced (more token fields, review_status) |
| **errors table** | ✅ Implemented | NONE | Simplified (removed some audit fields) |
| **Partial indexes** | ✅ Implemented | NONE | Same indexes (runs, responses) |
| **Foreign keys** | ✅ Implemented | NONE | CASCADE/RESTRICT rules preserved |
| **Connection manager** | ❌ Missing | MEDIUM | No DatabaseManager class |
| **Repository pattern** | ✅ Implemented | NONE | All 6 repositories implemented |

---

## 2. Schema Differences (V1 vs V2)

### 2.1 Table Count

| Aspect | V1 | V2 | Change |
|--------|----|----|--------|
| **Total tables** | 7 | 6 | -1 |
| **Removed** | — | `models` | Intentional |

### 2.2 experiments Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `experiment_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `name` | ✅ TEXT UNIQUE | ✅ TEXT UNIQUE | Same |
| `description` | ✅ TEXT | ✅ TEXT | Same |
| `default_temperature` | ✅ REAL | ❌ Removed | Removed (moved to config_json) |
| `default_top_p` | ✅ REAL | ❌ Removed | Removed (moved to config_json) |
| `default_max_output_tokens` | ✅ INTEGER | ❌ Removed | Removed (moved to config_json) |
| `default_reasoning_mode` | ✅ TEXT | ❌ Removed | Removed (moved to config_json) |
| `default_reasoning_effort` | ✅ TEXT | ❌ Removed | Removed (moved to config_json) |
| `system_prompt_template` | ✅ TEXT | ❌ Removed | Removed (moved to config_json) |
| `user_prompt_template` | ✅ TEXT | ❌ Removed | Removed (moved to config_json) |
| `config_json` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `config_hash` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `created_at` | ✅ TIMESTAMP | ✅ TIMESTAMP | Same |

**Assessment**: V2 simplified `experiments` by removing explicit global default columns. All configuration is now stored in `config_json`.

**Gap Severity**: **LOW** — Intentional simplification, not a regression.

---

### 2.3 models Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `model_id` | ✅ TEXT PK | ❌ Removed | Table removed |
| `provider` | ✅ TEXT NOT NULL | ❌ Removed | Table removed |
| `model_name` | ✅ TEXT NOT NULL | ❌ Removed | Table removed |
| `created_at` | ✅ TIMESTAMP | ❌ Removed | Table removed |

**Assessment**: V2 removed the `models` table entirely. Model variants now reference `model_id` as a string identifier without a foreign key to a models table.

**Rationale**:
- Simplifies schema (one less table)
- Models are external identities (provider/model-name)
- No need for a canonical registry

**Gap Severity**: **LOW** — Intentional simplification.

**Trade-offs**:
- ✅ Simpler schema
- ✅ No FK maintenance for models
- ❌ No model metadata storage (provider, name)
- ❌ No validation of model_id values

---

### 2.4 model_variants Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `variant_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `model_id` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `experiment_id` | ❌ Not in V1 schema | ✅ TEXT NOT NULL FK | **Added** (now scoped to experiments) |
| `reasoning_mode` | ✅ TEXT | ❌ Removed (moved to config) | Moved to config JSON |
| `reasoning_effort` | ✅ TEXT | ❌ Removed (moved to config) | Moved to config JSON |
| `vision_enabled` | ✅ BOOLEAN NOT NULL | ❌ Removed (moved to config) | Moved to config JSON |
| `structured_output` | ✅ BOOLEAN NOT NULL | ❌ Removed (moved to config) | Moved to config JSON |
| `web_access_enabled` | ✅ BOOLEAN NOT NULL | ❌ Removed (moved to config) | Moved to config JSON |
| `temperature` | ✅ REAL | ❌ Removed (moved to config) | Moved to config JSON |
| `top_p` | ✅ REAL | ❌ Removed (moved to config) | Moved to config JSON |
| `max_output_tokens` | ✅ INTEGER | ❌ Removed (moved to config) | Moved to config JSON |
| `variant_signature` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `created_at` | ✅ TIMESTAMP | ✅ TIMESTAMP | Same |

**Constraints**:
- V1: No FK to experiments (variants were global)
- V2: FK to `experiments(experiment_id)` with CASCADE delete
- V2: UNIQUE `(experiment_id, variant_signature)`

**Assessment**: V2 scoped model variants to experiments (not global). Identity fields moved to `config` JSON.

**Gap Severity**: **NONE** — Intentional architectural change.

---

### 2.5 runs Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `run_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `experiment_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `run_group_id` | ✅ TEXT | ❌ Removed | Removed (grouping abandoned) |
| `seed` | ✅ INTEGER | ❌ Removed (moved to config) | Moved to config JSON |
| `system_prompt` | ✅ TEXT | ❌ Removed (moved to config) | Moved to config JSON |
| `user_prompt` | ✅ TEXT | ❌ Removed (moved to config) | Moved to config JSON |
| `status` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `started_at` | ✅ TIMESTAMP | ❌ Removed | Removed (only `created_at`) |
| `finished_at` | ✅ TIMESTAMP | ❌ Removed | Removed |
| `created_by` | ✅ TEXT | ❌ Removed | Removed |
| `notes` | ✅ TEXT | ❌ Removed | Removed |
| `config` | ❌ Not in V1 | ✅ TEXT NOT NULL | **Added** (JSON config) |
| `duration` | ❌ Not in V1 | ✅ INTEGER DEFAULT 0 | **Added** (for partial runs) |
| `created_at` | ✅ TIMESTAMP | ✅ TIMESTAMP | Same |

**Constraints**:
- V2: CHECK `status IN ('pending', 'running', 'completed', 'failed', 'partial_failed')`

**Assessment**: V2 simplified `runs` by moving configuration to `config` JSON. Removed grouping fields.

**Gap Severity**: **LOW** — Intentional simplification.

---

### 2.6 question_snapshots Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `snapshot_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `experiment_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `question_id` | ✅ TEXT NOT NULL | ❌ Renamed to `json_question_id` | Renamed for clarity |
| `question_position` | ❌ Not in V1 | ✅ INTEGER NOT NULL | **Added** (1-based position) |
| `question_payload` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `created_at` | ✅ TIMESTAMP | ✅ TIMESTAMP | Same |

**Constraints**:
- V2: UNIQUE `(experiment_id, question_position)` — Prevent duplicate positions

**Assessment**: V2 enhanced `question_snapshots` with `question_position` for user-facing ordering.

**Gap Severity**: **NONE** — Enhancement, not a regression.

---

### 2.7 responses Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `response_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `run_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `variant_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `snapshot_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `model_id` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `question_id` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `status` | ✅ TEXT NOT NULL DEFAULT 'success' | ✅ TEXT | Changed (no default, nullable) |
| `finish_reason` | ✅ TEXT | ✅ TEXT | Same |
| `error_details` | ✅ TEXT | ✅ TEXT | Same |
| `response_text` | ✅ TEXT | ✅ TEXT | Same |
| `selected_answer` | ✅ TEXT | ✅ TEXT | Same |
| `is_correct` | ✅ BOOLEAN | ✅ BOOLEAN | Same |
| `parse_confidence` | ✅ TEXT DEFAULT 'unknown' | ✅ TEXT DEFAULT 'unknown' | Same |
| `review_status` | ❌ Not in V1 | ✅ TEXT | **Added** (more expressive) |
| `manual_answer` | ✅ TEXT | ✅ TEXT | Same |
| `raw_response` | ❌ Not in V1 | ✅ TEXT | **Added** (complete API response) |
| `provider_model_resolved` | ✅ TEXT | ❌ Removed | Removed |
| `provider_parameters_effective` | ✅ TEXT | ❌ Removed | Removed |
| `provider_thinking_level` | ✅ TEXT | ❌ Removed | Removed |
| `provider_debug_payload` | ✅ TEXT | ❌ Removed | Removed |
| `cost` | ✅ REAL | ✅ REAL | Same |
| `input_tokens` | ✅ INTEGER | ✅ INTEGER | Same |
| `output_tokens` | ✅ INTEGER | ❌ Renamed to `response_tokens` | Renamed |
| `total_tokens` | ✅ INTEGER | ❌ Removed | Replaced by `effective_tokens` |
| `reasoning_tokens` | ❌ Not in V1 | ✅ INTEGER | **Added** |
| `effective_tokens` | ❌ Not in V1 | ✅ INTEGER | **Added** (sum of all tokens) |
| `latency_ms` | ✅ INTEGER | ✅ INTEGER | Same |
| `started_at` | ❌ Not in V1 | ✅ TIMESTAMP | **Added** |
| `finished_at` | ❌ Not in V1 | ✅ TIMESTAMP | **Added** |
| `created_at` | ✅ TIMESTAMP | ❌ Removed | Replaced by `started_at`/`finished_at` |

**Assessment**: V2 enhanced `responses` with better token tracking and timing fields.

**Gap Severity**: **NONE** — Enhancements, not regressions.

**Key Changes**:
- `review_status` replaces `needs_review` (more expressive: 'needs_review', 'reviewed', 'auto')
- `effective_tokens` = `input_tokens` + `response_tokens` + `reasoning_tokens`
- `started_at` / `finished_at` for execution timing

---

### 2.8 errors Table

| Column | V1 | V2 | Change |
|--------|----|----|--------|
| `error_id` | ✅ TEXT PK | ✅ TEXT PK | Same |
| `run_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `variant_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `snapshot_id` | ✅ TEXT NOT NULL FK | ✅ TEXT NOT NULL FK | Same |
| `model_id` | ✅ TEXT NOT NULL | ❌ Removed | Removed (denormalization reduced) |
| `question_id` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `error_type` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `error_code` | ✅ TEXT | ❌ Removed | Removed |
| `error_message` | ✅ TEXT NOT NULL | ✅ TEXT NOT NULL | Same |
| `stack_trace` | ✅ TEXT | ✅ TEXT | Same |
| `attempt_count` | ✅ INTEGER NOT NULL | ✅ INTEGER NOT NULL DEFAULT 1 | Same |
| `is_retryable` | ✅ BOOLEAN NOT NULL | ❌ Removed | Removed |
| `provider_model_resolved` | ✅ TEXT | ❌ Removed | Removed |
| `provider_error_payload` | ✅ TEXT | ❌ Removed | Removed |
| `occurred_at` | ✅ TIMESTAMP | ✅ TIMESTAMP | Same |
| `created_at` | ✅ TIMESTAMP | ❌ Removed | Replaced by `occurred_at` |

**Assessment**: V2 simplified `errors` by removing provider-specific audit fields.

**Gap Severity**: **LOW** — Intentional simplification.

---

## 3. Missing Features

### 3.1 Connection Manager (MEDIUM)

**V1 Behavior**:
- `DatabaseManager` class handles connection lifecycle
- Automatic foreign key enablement
- Row factory configuration
- In-memory vs file database detection
- Context manager support (`__enter__`, `__exit__`)

**V2 Status**:
- ❌ No centralized connection manager
- ❌ Manual connection setup in each caller
- ❌ No in-memory database support

**Impact**:
- Code duplication (connection setup)
- Risk of forgetting `PRAGMA foreign_keys = ON`
- Harder to test (no in-memory support)

**Migration Priority**: **MEDIUM**

**Recommended Approach**:
- Create `DatabaseManager` class in `src/db/manager.py`
- Support both file and in-memory databases
- Auto-enable foreign keys
- Provide context manager support

---

### 3.2 models Table (LOW)

**V1 Behavior**:
- Canonical model registry
- Stores `model_id`, `provider`, `model_name`
- FK from `model_variants.model_id`

**V2 Status**:
- ❌ Table removed entirely
- ❌ `model_id` is now just a string identifier

**Impact**:
- ✅ Simpler schema
- ❌ No model metadata storage
- ❌ No validation of model_id values

**Migration Priority**: **LOW** — Intentional removal.

**Note**: This is an architectural decision, not a gap. If model metadata is needed, it can be added back.

---

## 4. Constraint Differences

### 4.1 Foreign Key Rules

| Relationship | V1 | V2 | Change |
|--------------|----|----|--------|
| `model_variants` → `experiments` | ❌ No FK | ✅ FK with CASCADE | **Added** |
| `question_snapshots` → `experiments` | ✅ FK with CASCADE | ✅ FK with CASCADE | Same |
| `runs` → `experiments` | ✅ FK with CASCADE | ✅ FK with CASCADE | Same |
| `responses` → `runs` | ✅ FK with CASCADE | ✅ FK with CASCADE | Same |
| `responses` → `model_variants` | ✅ FK with RESTRICT | ✅ FK with RESTRICT | Same |
| `responses` → `question_snapshots` | ✅ FK with RESTRICT | ✅ FK with RESTRICT | Same |
| `errors` → `runs` | ✅ FK with CASCADE | ✅ FK with CASCADE | Same |
| `errors` → `model_variants` | ✅ FK with RESTRICT | ✅ FK with RESTRICT | Same |
| `errors` → `question_snapshots` | ✅ FK with RESTRICT | ✅ FK with RESTRICT | Same |

**Assessment**: V2 added FK from `model_variants` to `experiments` (variants are now scoped to experiments).

---

### 4.2 UNIQUE Constraints

| Table | V1 | V2 | Change |
|-------|----|----|--------|
| `experiments` | `name` | `name` | Same |
| `model_variants` | `variant_signature` (global) | `(experiment_id, variant_signature)` | **Changed** (scoped to experiment) |
| `question_snapshots` | None | `(experiment_id, question_position)` | **Added** |
| `responses` | `(run_id, variant_id, snapshot_id)` | `(run_id, variant_id, snapshot_id)` | Same |

**Assessment**: V2 improved uniqueness constraints by scoping to experiments and preventing duplicate question positions.

---

### 4.3 CHECK Constraints

| Table | V1 | V2 | Change |
|-------|----|----|--------|
| `runs` | ❌ None | ✅ `status IN (...)` | **Added** |

**Assessment**: V2 added CHECK constraint for valid status values.

---

## 5. Index Coverage

### 5.1 Index Comparison

| Table | Index | V1 | V2 | Change |
|-------|-------|----|----|--------|
| `experiments` | `idx_experiments_name` | ✅ | ❌ Removed | Removed |
| `experiments` | `idx_experiments_hash` | ✅ | ❌ Removed | Removed |
| `model_variants` | `idx_model_variants_model` | ✅ | ❌ Removed | Removed |
| `model_variants` | `idx_model_variants_signature` | ✅ (UNIQUE) | ❌ Removed | Removed |
| `model_variants` | `idx_variants_by_experiment` | ❌ | ✅ **Added** | **Added** |
| `runs` | `idx_runs_experiment` | ✅ | ✅ `idx_runs_by_experiment` | Renamed |
| `runs` | `idx_runs_group` | ✅ | ❌ Removed | Removed (grouping abandoned) |
| `runs` | `idx_runs_status` | ✅ | ❌ Removed | Replaced by partial index |
| `runs` | `idx_runs_pending` | ❌ | ✅ **Added** (PARTIAL) | **Added** |
| `question_snapshots` | `idx_question_snapshots_experiment` | ✅ | ✅ `idx_snapshots_by_experiment` | Renamed |
| `question_snapshots` | `idx_question_snapshots_question` | ✅ | ❌ Removed | Removed |
| `responses` | `idx_responses_unique` | ✅ (UNIQUE) | ✅ (UNIQUE constraint) | Same |
| `responses` | `idx_responses_run` | ✅ | ✅ `idx_responses_by_run` | Renamed |
| `responses` | `idx_responses_variant` | ✅ | ❌ Removed | Removed |
| `responses` | `idx_responses_snapshot` | ✅ | ❌ Removed | Removed |
| `responses` | `idx_responses_needs_review` | ✅ (PARTIAL) | ✅ (PARTIAL) | Same |
| `errors` | `idx_errors_run` | ✅ | ✅ `idx_errors_by_run` | Renamed |
| `errors` | `idx_errors_variant` | ✅ | ❌ Removed | Removed |
| `errors` | `idx_errors_type` | ✅ | ❌ Removed | Removed |

**Assessment**: V2 has fewer indexes overall, focusing on the most common query patterns.

**Removed Indexes Rationale**:
- `idx_experiments_name/hash` — Experiments are looked up by ID, not name/hash
- `idx_model_variants_model` — Variants are scoped to experiments
- `idx_runs_group` — Grouping abandoned
- `idx_responses_variant/snapshot` — Less common query patterns
- `idx_errors_variant/type` — Less common query patterns

**Gap Severity**: **LOW** — Intentional optimization.

---

## 6. Migration Priority

### 6.1 HIGH Priority (BLOCKERS)

None identified. V2 database layer is functionally complete.

---

### 6.2 MEDIUM Priority (IMPROVEMENTS)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **Connection Manager** | Low | Low | Create `DatabaseManager` class |

**Rationale**: Improves code quality and testability.

---

### 6.3 LOW Priority (OPTIONAL)

| Gap | Effort | Risk | Recommendation |
|-----|--------|------|----------------|
| **models table** | Medium | Low | Re-add only if model metadata is needed |
| **Removed indexes** | Low | Low | Re-add only if query performance requires |

**Rationale**: These are intentional simplifications, not regressions.

---

## 7. Summary

### 7.1 Gap Summary by Severity

| Severity | Count | Components |
|----------|-------|------------|
| **CRITICAL** | 0 | None |
| **HIGH** | 0 | None |
| **MEDIUM** | 1 | Connection Manager |
| **LOW** | 2 | models table, Removed indexes |

### 7.2 Overall Assessment

**V2 Architecture**: ✅ **SOUND**
- Follows TO-BE principles
- Clean schema design
- Proper constraints and indexes
- Immutability enforced

**V2 Implementation**: ✅ **COMPLETE**
- All 6 tables implemented
- All constraints enforced
- All indexes created
- Repository pattern implemented

**Migration Readiness**: ✅ **READY**
- No critical gaps
- Schema is simpler than V1
- Backward compatibility not required (greenfield)

### 7.3 Key Improvements in V2

1. **Simplified schema** — Removed `models` table, consolidated configuration in JSON
2. **Scoped variants** — Model variants now belong to experiments (not global)
3. **Better token tracking** — Added `reasoning_tokens`, `effective_tokens`
4. **Enhanced review** — `review_status` replaces `needs_review` boolean
5. **Partial indexes** — Optimized for execution and review queues
6. **CHECK constraints** — Valid status values enforced

### 7.4 Recommended Next Steps

1. **Optional**: Add `DatabaseManager` class for connection lifecycle management
2. **Optional**: Monitor query performance, add indexes if needed
3. **Optional**: Consider re-adding `models` table if model metadata is needed

---

**Document Version**: 1.0
**Last Updated**: 2026-03-29
**Comparison**: V1 (Legacy) → V2 (Current)
