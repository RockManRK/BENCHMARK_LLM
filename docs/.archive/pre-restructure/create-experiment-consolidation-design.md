# CLI Consolidation Design: Phase 1 (create-experiment)

**Date:** 2026-03-26  
**Status:** Design Approved  
**Phase:** 1 of 6 (create-experiment only)  
**Principle:** Promotion-First — Zero behavior loss guarantee  

---

## 1. Problem Statement

Three entry points for `create-experiment` with divergent behavior:

| Divergence | Entry Point 1 (main.py) | Entry Point 2 (bcllm_experiment.py) | Entry Point 3 (experiment_commands.py) |
|------------|------------------------|-------------------------------------|---------------------------------------|
| **Config Hash** | 3 keys, 16 chars ✅ | 14 keys, 64 chars ❌ | 3 keys, 16 chars ✅ |
| **Database Path** | `settings.database_path` ✅ | `./data/bcllm.db` ❌ | `settings.database_path` ✅ |
| **.env Resolution** | Partial (pydantic settings) | Complete (ConfigResolver) | Partial (pydantic settings) |
| **Question Filtering** | ❌ Not supported | ✅ `--where`/`--exclude` | ❌ Not supported |
| **Validation** | Gaps (no empty name, bool, model ID) | Complete | Gaps |
| **Question Loader** | Pydantic (schema validation) | Dict-based (no validation) | Pydantic (schema validation) |
| **Question Selection** | Numeric positions | Numeric positions | Numeric positions |

**Critical Contract Mismatches Identified:**
1. ❌ Question selection uses textual IDs (Q001) in documentation — **CORRECTED**: numeric positions only
2. ❌ Test coverage insufficient — **CORRECTED**: explicit matrix added
3. ❌ Missing contract references — **CORRECTED**: authoritative contracts linked

---

## 2. Authoritative Contracts

This design complies with:

| Contract | Purpose | Key Requirements |
|----------|---------|------------------|
| [`configurarion_resolution_contract.md`](./architecture/contracts/configurarion_resolution_contract.md) | Configuration resolution order | `.env` only at creation time; NULL = "do not send"; no inference |
| [`comandos_tobe.md`](./architecture/to-be/comandos_simples.md) | CLI command specification | Numeric question positions; `--add-model` (singular); validation rules |
| [`execution-plan.md`](./architecture/contracts/execution-plan.md) | Execution plan structure | All model configs resolved at plan time; no inference during execution |

---

## 3. Key Contract Corrections

### 3.1 Question Selection Semantics (CRITICAL)

**PREVIOUSLY INCORRECT:**
```bash
--questions Q001-Q010  # ❌ Textual IDs do NOT exist
```

**CORRECT (PER CONTRACT):**
```bash
--questions 1-10       # ✅ Numeric positions (1-indexed from dataset order)
--questions 1 5 10     # ✅ Comma/space-separated positions
--questions 1-50 --where status=valid  # ✅ Filter by position + metadata
```

**Contract Reference:** `question_snapshots.question_position` is the authoritative selector.

### 3.2 Filtering Semantics (FORMAL DEFINITION)

| Filter Type | Syntax | Operates On | Example |
|-------------|--------|-------------|---------|
| **Position Range** | `1-10` | `question_position` (integer) | Selects positions 1 through 10 |
| **Position List** | `1 5 10` | `question_position` (integer) | Selects positions 1, 5, 10 |
| **Status Filter** | `--where status=valid` | `question.status` metadata | Filters by status field |
| **Exclude** | `--exclude 5` | `question_position` (integer) | Excludes position 5 |

**NO textual ID conversions** — positions are native integers from dataset order.

### 3.3 Config Resolution Order (PER CONTRACT TABLE)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ EXPERIMENT_CREATION (Resolved at experiment creation, stored in config)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ QUESTIONS_DATASET_PATH: experiment → .env → ERROR                          │
│ DEFAULT_QUESTIONS:      .env → NULL (all questions if NULL)                │
│ QUESTIONS_STATUS_ADD:   .env → NULL                                        │
│ QUESTIONS_STATUS_EXCLUDE: .env → NULL                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ MODEL_VARIANT_CREATION (Resolved at variant creation, stored in config)     │
├─────────────────────────────────────────────────────────────────────────────┤
│ BASE_URL:            model_variant → experiment → .env → ERROR             │
│ MODEL_* (all):       model_variant → experiment → .env → NULL              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ RUN_CREATION (Resolved at run creation, stored in config)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ RUN_RESPONSES_SEED:    run → experiment → .env → OFF                       │
│ SYSTEM_PROMPT:         run → experiment → .env → NULL                      │
│ USER_PROMPT:           run → experiment → .env → NULL                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Principle:** `.env` is ONLY read at creation time. After entity creation, `.env` is NEVER consulted.

---

## 4. Promotion Sequence

### Phase 1.1: ConfigResolver Integration

**Source:** `src/core/config_resolver.py` (Entry Point 2)

**Methods to Port:**
- `load_env()` — Complete .env loading with `dotenv.load_dotenv(override=True)`
- `build_experiment_config_dict()` — 14-key config dict per contract
- `resolve_seed()` — CLI > .env (RUN_RESPONSES_SEED) > "AUTO" string
- `resolve_prompt()` — CLI > .env (SYSTEM_PROMPT/USER_PROMPT) > NULL
- `_resolve_bool_cli_or_env()` — Boolean resolution with NULL support
- `_parse_int_env()`, `_parse_float_env()` — Type conversion with NULL handling

**Integration Point:** `ExperimentManager.create_experiment()` replaces `get_settings()` calls with `ConfigResolver`.

**Behavior Preserved:**
- Complete .env resolution (all 14 keys from contract)
- Explicit CLI > .env > NULL ordering
- NULL handling for optional configs
- Type conversion utilities

---

### Phase 1.2: Protocol Hash Preservation

**Source:** `src/cli/experiment_commands.py:715-726` (Entry Points 1 & 3)

**Method:** `_build_config_hash()` — **NO CHANGES REQUIRED**

```python
def _build_config_hash(self, settings: Settings, seed: Optional[str | int]) -> str:
    config = {
        "default_prompt": settings.default_prompt,
        "use_structured_outputs": settings.use_structured_outputs,
        "random_seed_policy": str(seed) if seed else "none",
    }
    config_json = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]
```

**Why Correct:**
- Hashes ONLY 3 protocol keys (not model configs)
- 16-character truncated SHA-256
- Allows experiment variant comparison (same protocol = same hash)

**DO NOT USE:** Entry Point 2's hash (14 keys, 64 chars) — breaks variant comparison.

---

### Phase 1.3: Question Filtering (WITH CONTRACT CORRECTIONS)

**Source:** `src/cli/bcllm_experiment.py:357-456` (Entry Point 2)

**Methods to Port:**
- `_create_question_snapshots()` — Core snapshotting logic
- `filter_questions()` — Filter application by numeric position
- `parse_filter()` — Filter syntax validation

**Contract Corrections Applied:**
1. ✅ Question selection by **numeric position only** (no Q00* prefix support)
2. ✅ Filters operate on `question_position` (integer) and metadata fields
3. ✅ `DEFAULT_QUESTIONS` from .env applied when `--questions` omitted
4. ✅ `QUESTIONS_STATUS_ADD/EXCLUDE` from .env applied as default filters

**Integration Point:** Called after `QuestionLoader.load()` in `ExperimentManager.create_experiment()`.

---

### Phase 1.4: Validation Completeness

**Source:** `src/cli/bcllm_experiment.py` (Entry Point 2)

**Validations to Port:**

| Validation | Location | Error Message |
|------------|----------|---------------|
| Empty experiment name | Line 275-278 | `Error: Experiment name cannot be empty` |
| Duplicate experiment name | Line 280-283 | `Error: Experiment '{name}' already exists` |
| Boolean value validation | Line 338 | `Error: Invalid value for --{flag}: {value}. Valid: true, false, null (case-insensitive)` |
| Model ID format | Line 347-351 | `Error: Invalid model ID format: {model_id}. Expected: provider/model-name` |
| Variant signature collision | Line 353-356 | `Error: Variant '{signature}' already exists in experiment '{name}'` |
| Filter syntax validation | Line 409-436 | `Error: Invalid filter syntax: {filter}. Expected: key=value` |
| Dataset existence | Line 379-386 | `Error: Questions dataset not found: {path}` |

**Integration Point:** Added to `ExperimentManager.create_experiment()` before any persistence.

---

### Phase 1.5: Database Path Unification

**Issue:** Entry Point 2 uses hardcoded `./data/bcllm.db`.

**Contract Reference:** `DATABASE_PATH` row in configuration resolution contract.

**Resolution:**
- Update `bcllm_experiment.py.get_database_connection()` to use `get_settings().database_path`
- Default: `./data/benchmark.db` (per contract)
- Remove hardcoded `./data/bcllm.db`

---

### Phase 1.6: Loader Unification

**Files:**
- `src/core/loader.py` (pydantic) — **RETAIN**
- `src/core/question_loader.py` (dict-based) — **DEPRECATE**

**Action:**
- Port `parse_question_spec()` regex support from dict loader to pydantic loader
- Port `assign_internal_ids()` method
- Port flat list dataset format support (`[...]` vs `{"questions": [...]}`)
- Remove dict-based loader after porting

**Why Pydantic Preferred:**
- Schema validation (required fields, types)
- Answer key uniqueness validation
- Structured error messages

---

## 5. Files Modified/Removed

### Modified Files

| File | Changes | Purpose |
|------|---------|---------|
| `src/main.py` | Add `--where`/`--exclude` CLI flags; update help text for numeric positions | User-facing CLI interface |
| `src/cli/experiment_commands.py` | Integrate ConfigResolver; port filtering; add validation; unify loader | Execution layer |

### Removed Files (AFTER VERIFICATION)

| File | Reason | Behavior Preserved In |
|------|--------|----------------------|
| `src/cli/bcllm_experiment.py` | Standalone script — all behavior promoted to `main.py` | `src/cli/experiment_commands.py` |
| `src/core/question_loader.py` | Dict-based loader — replaced by pydantic loader | `src/core/loader.py` |

### Unchanged Files

| File | Purpose |
|------|---------|
| `src/core/config_resolver.py` | Promoted as-is (complete .env resolution) |
| `src/core/loader.py` | Pydantic loader retained (schema validation) |
| `src/utils/config.py` | Settings class retained (pydantic-settings) |

---

## 6. Validation Test Matrix (PER CONTRACT)

### Test Coverage Requirements

| Test ID | Category | CLI Invocation | .env State | Expected Behavior |
|---------|----------|----------------|------------|-------------------|
| **T01** | No-argument | `bcllm --create-experiment test` | Full .env with `DEFAULT_QUESTIONS` | Uses `DEFAULT_QUESTIONS`, `QUESTIONS_STATUS_ADD/EXCLUDE` from .env |
| **T02** | Numeric positions | `bcllm --create-experiment test --questions 1-10` | Empty .env | Positions 1-10 selected from dataset |
| **T03** | Mixed syntax | `bcllm --create-experiment test --questions 1 5 10-15` | Empty .env | Positions 1, 5, 10, 11, 12, 13, 14, 15 |
| **T04** | Filter with where | `bcllm --create-experiment test --questions 1-50 --where status=valid` | Empty .env | Positions 1-50 filtered by `status=valid` |
| **T05** | Filter with exclude | `bcllm --create-experiment test --questions 1-10 --exclude 5` | Empty .env | Positions 1-10 except position 5 |
| **T06** | Explicit null | `bcllm --create-experiment test --questions null` | `DEFAULT_QUESTIONS=1-100` | **No questions** (null overrides .env) |
| **T07** | Omitted flag | `bcllm --create-experiment test` | `DEFAULT_QUESTIONS=1-100` | Positions 1-100 from .env |
| **T08** | Partial .env | Missing `DEFAULT_QUESTIONS` | Only `QUESTIONS_DATASET_PATH` set | All questions from dataset added |
| **T09** | Invalid .env | `QUESTIONS_DATASET_PATH=/nonexistent` | Invalid path | Error: dataset not found |
| **T10** | Empty filter | `bcllm --create-experiment test --where ""` | Empty .env | Error: invalid filter syntax |
| **T11** | Model ID format | `--add-model google/gemini-3.1-flash-lite-preview` | Empty .env | Accepted (any `provider/model_id`) |
| **T12** | Boolean case-insensitive | `--vision TRUE`, `--vision true`, `--vision True` | Empty .env | All accepted, normalized to boolean |
| **T13** | Numeric null | `--temperature null` | Empty .env | Stored as NULL (not sent to API) |
| **T14** | Config hash | (Internal inspection) | N/A | 16-char truncated hash, 3 protocol keys only |
| **T15** | Database path | (Internal inspection) | N/A | Uses `settings.database_path` (default `./data/benchmark.db`) |

### Test Execution Commands

```bash
# T01: No-argument (100% .env driven)
bcllm --create-experiment test_env_default

# T02: Explicit numeric positions
bcllm --create-experiment test_numeric --questions 1-10

# T03: Mixed list and range
bcllm --create-experiment test_mixed --questions "1 5 10-15"

# T04: Filter with where
bcllm --create-experiment test_where --questions 1-50 --where "status=valid"

# T05: Filter with exclude
bcllm --create-experiment test_exclude --questions 1-10 --exclude 5

# T06: Explicit null vs omitted
bcllm --create-experiment test_null --questions null
bcllm --create-experiment test_omitted  # Uses DEFAULT_QUESTIONS from .env

# T11: Model ID format (contract-compliant)
bcllm --create-experiment test_model --add-model google/gemini-3.1-flash-lite-preview

# T12: Boolean case-insensitive
bcllm --create-experiment test_vision --vision TRUE --structured False
```

---

## 7. Verification Checklist (PRE-REMOVAL)

Before removing standalone scripts, verify:

- [ ] **T01-T15 all pass** with expected behavior
- [ ] **Config hash** matches protocol-only format (3 keys, 16 chars)
- [ ] **Question payload** matches pydantic schema (7-key structure)
- [ ] **Filtering** behaves identically to Entry Point 2 (numeric positions only)
- [ ] **.env values** propagate correctly (DEFAULT_QUESTIONS, STATUS_ADD/EXCLUDE)
- [ ] **Database path** uses `settings.database_path` (no hardcoded paths)
- [ ] **No legacy CLI path** can be executed (standalone scripts unreachable)

---

## 8. Removal Rules (STRICT)

**AFTER verification complete:**

1. **Remove ALL argparse usage outside `main.py`**
   - `bcllm_experiment.py:create_parser()` — REMOVE
   - `bcllm_experiment.py:DuplicateFlagWarningParser` — REMOVE

2. **Remove standalone CLI scripts**
   - `src/cli/bcllm_experiment.py` — REMOVE (behavior promoted)
   - `src/cli/bcllm_model.py` — Phase 2 (out of scope for Phase 1)
   - `src/cli/bcllm_run.py` — Phase 2 (out of scope)
   - `src/cli/bcllm_execute.py` — Phase 2 (out of scope)

3. **Remove unused loaders/validators**
   - `src/core/question_loader.py` — REMOVE (dict-based, replaced by pydantic)
   - `src/core/loader.py` — RETAIN (pydantic)

**If code is not reachable from `main.py`, it MUST be deleted.**

---

## 9. Risk Mitigation

### Risk: Behavior Loss During Consolidation

**Mitigation:**
- Promotion-first approach (port behavior BEFORE removal)
- Explicit test matrix (T01-T15) for verification
- Contract references for authoritative behavior

### Risk: Contract Drift

**Mitigation:**
- Design explicitly references authoritative contracts
- Numeric position-only semantics enforced (no textual IDs)
- Config resolution order per contract table

### Risk: Incomplete Validation

**Mitigation:**
- Validation completeness table (all 7 validations ported)
- Error messages preserved verbatim

---

## 10. Deliverables

1. ✅ **Single unified create-experiment flow** via `main.py` → `ExperimentManager`
2. ✅ **No legacy entry points remain** (standalone scripts removed post-verification)
3. ✅ **Removed files list** with justification (behavior promoted, not lost)
4. ✅ **Confirmation** that no recent fixes lost (ConfigResolver, filtering, validation all preserved)

---

**DESIGN COMPLETE.** Ready for implementation planning.
