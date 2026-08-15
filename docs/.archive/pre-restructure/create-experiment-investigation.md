# COMPREHENSIVE CREATE-EXPERIMENT INVESTIGATION REPORT

**Date:** 2026-03-26  
**Status:** Investigation Complete  
**Type:** Investigation and Promotion Planning ONLY  
**Constraints:** No deletions, no consolidation, no refactoring, no behavior changes  

---

## Executive Summary

This investigation traces the `create-experiment` command through **THREE distinct entry points**, documenting execution paths, configuration resolution, validation logic, persistence behavior, and behavioral divergences. 

**Critical Findings:**
1. **Config Hash Divergence** - Entry Point 2 hashes 14 keys (64 chars), Entry Points 1&3 hash 3 keys (16 chars)
2. **Database Path Split** - Entry Point 2 uses `./data/bcllm.db`, others use `./data/benchmark.db`
3. **Question Payload Mismatch** - Pydantic loader (7-key) vs dict loader (6-key, different structure)
4. **.env Key Semantic Error** - Entry Point 2 uses `RUN_RESPONSES_SEED` (run-level) for experiment creation
5. **Validation Gaps** - Entry Points 1&3 skip empty name, boolean, and model ID validation
6. **Filter Support** - Only Entry Point 2 supports `--where`/`--exclude` filtering

---

## 1. EXECUTION FLOW DIAGRAMS

### Entry Point 1: `main.py` → `BenchmarkRunner._handle_create_experiment()`

```
CLI INVOCATION:
  bcllm.py --create-experiment <name> [--questions SPEC] [--seed VALUE]

EXECUTION FLOW:
  main.py:328 (run method)
    ↓
  main.py:330 (_handle_create_experiment)
    ↓
  main.py:340 ──→ get_settings() [src/utils/config.py:702]
    │              └─→ Settings() class with pydantic-settings
    │                 └─→ .env loaded at module import (config.py:26)
    │                 └─→ QUESTIONS_DATASET_PATH → settings.questions_dataset_path
    │                 └─→ DEFAULT_QUESTIONS → settings.default_questions
    │                 └─→ RANDOM_SEED → settings.random_seed
    │
  main.py:343 ──→ ExperimentManager(db_manager) [src/cli/experiment_commands.py:77]
    │
  main.py:353 ──→ resolve_with_feedback() [src/utils/config_hierarchy.py:29]
    │              └─→ CLI > .env > default hierarchy for questions
    │
  main.py:363 ──→ CLIParser()._expand_question_ranges() [src/cli/cli.py:507]
    │              └─→ Expands "Q001-Q010" → ["Q001", "Q002", ..., "Q010"]
    │
  main.py:380 ──→ resolve_with_feedback() for seed
    │
  main.py:392 ──→ exp_manager.create_experiment()
                 [src/cli/experiment_commands.py:108]
    │
    ├─→ self.experiment_repo.get_by_name() [DUPLICATE CHECK]
    │
    ├─→ get_settings() [ANOTHER CALL - config.py:702]
    │
    ├─→ _build_config_json() [line 698]
    │    └─→ Uses settings.default_prompt, settings.use_structured_outputs, etc.
    │
    ├─→ _build_config_hash() [line 715]
    │    └─→ Hashes ONLY protocol: default_prompt, use_structured_outputs, random_seed_policy
    │
    ├─→ ExperimentRepository.create() [NOT SHOWN - uses ModelVariantRepository]
    │
    └─→ Question Snapshotting:
         ├─→ QuestionLoader(str(settings.questionnaire_path)) [line 158]
         ├─→ loader.load() [src/core/loader.py:149]
         ├─→ _expand_question_filters() [line 737]
         ├─→ _build_question_json() [line 763]
         └─→ snapshot_repo.create_if_not_exists() [IDEMPOTENT]
```

**File Locations:**
- Entry: `src/main.py:328-419`
- ExperimentManager: `src/cli/experiment_commands.py:77-900`
- Settings: `src/utils/config.py:43-730`
- Config Hierarchy: `src/utils/config_hierarchy.py`

---

### Entry Point 2: `bcllm_experiment.py` → `handle_create_experiment()` (Standalone Script)

```
CLI INVOCATION:
  python src/cli/bcllm_experiment.py --create-experiment <name> 
    [--add-model MODEL] [--add-questions SPEC] [--where FILTER] 
    [--exclude FILTER] [--seed VALUE] [--vision VALUE] [--structured VALUE]
    [--temperature VALUE] [--max-tokens VALUE] [--reasoning VALUE]
    [--top-p VALUE] [--top-k VALUE] [--repeat-penalty VALUE]
    [--reasoning-tokens VALUE] [--url URL] [--system-prompt PROMPT]
    [--user-prompt PROMPT]

EXECUTION FLOW:
  bcllm_experiment.py:578 (main)
    ↓
  bcllm_experiment.py:582 (parse_args via create_parser)
    │          └─→ DuplicateFlagWarningParser [line 44]
    │             └─→ Warns on duplicate flags
    │
  bcllm_experiment.py:585 (get_database_connection)
    │          └─→ src/cli/database.py:38
    │             └─→ ./data/bcllm.db (PERSISTENT, different from main.py)
    │
  bcllm_experiment.py:588 (handle_create_experiment) [line 267]
    │
    ├─→ ExperimentRepository(conn)
    ├─→ repo.get_by_name() [DUPLICATE CHECK]
    ├─→ _validate_bool_value() for --vision/--structured [line 338]
    │
    ├─→ ConfigResolver() [line 313]
    │    └─→ resolver.load_env() [src/core/config_resolver.py:38]
    │       └─→ Loads .env via dotenv.load_dotenv(".env", override=True)
    │       └─→ Reads ALL os.environ into self.env_dict
    │
    ├─→ resolver.build_experiment_config_dict(args) [line 315]
    │    └─→ [src/core/config_resolver.py:274]
    │    ├─→ resolve_seed() [line 118] - CLI > .env > "AUTO" string
    │    ├─→ resolve_prompt() [line 58] - CLI > .env > default
    │    ├─→ _resolve_bool_cli_or_env() [line 483]
    │    ├─→ _parse_int_env() / _parse_float_env() [lines 520, 533]
    │    └─→ Returns 14-key dict:
    │        - QUESTIONS_DATASET_PATH
    │        - BASE_URL, MODEL_MAX_TOKENS_REASONING, MODEL_MAX_TOKENS_TOTAL,
    │          MODEL_REASONING_EFFORT, MODEL_REPEAT_PENALTY, MODEL_TEMPERATURE,
    │          MODEL_TOP_K, MODEL_TOP_P, MODEL_VISION, STRUCTURED_OUTPUTS
    │        - RUN_RESPONSES_SEED, SYSTEM_PROMPT, USER_PROMPT
    │
    ├─→ config_json = json.dumps(config_dict) [line 317]
    │    └─→ Compact JSON (no indentation)
    │
    ├─→ config_hash = hashlib.sha256(config_json.encode()).hexdigest() [line 318]
    │    └─→ Hashes ENTIRE 14-key config (DIFFERENT from main.py!)
    │
    ├─→ Experiment() dataclass [line 320]
    │    └─→ experiment_id=f"exp_{uuid.uuid4().hex[:8]}"
    │
    ├─→ repo.save(experiment) [INSERT OR REPLACE]
    │
    ├─→ [IF --add-model] _add_models_at_creation() [line 330]
    │    ├─→ resolver.build_model_config_dict() [line 437]
    │    │    └─→ CLI > .env > experiment > NULL
    │    ├─→ generate_variant_signature() [src/utils/variant_signature.py:35]
    │    │    └─→ Fixed field order: reasoning, vision, structured, temp, top_p, top_k, max_tokens, reasoning_tokens
    │    │    └─→ Float normalization: 3 decimal places
    │    └─→ VariantRepository.save() [INSERT OR REPLACE]
    │
    └─→ [IF --add-questions or DEFAULT_QUESTIONS] _create_question_snapshots() [line 357]
         ├─→ resolver.load_env() [line 372]
         ├─→ QuestionLoader().load_dataset(dataset_path) [line 379]
         │    └─→ [src/core/question_loader.py:54]
         │       └─→ Supports flat list OR wrapped {"questions": [...]}
         ├─→ loader.assign_internal_ids() [line 380]
         ├─→ loader.parse_question_spec() [line 385]
         │    └─→ Supports: "1, 3, 5", "1-10", "Q001,Q003", mixed
         ├─→ [IF no --where] QUESTIONS_STATUS_ADD from .env [line 419]
         ├─→ [IF no --exclude] QUESTIONS_STATUS_EXCLUDE from .env [line 432]
         ├─→ filter_questions() [src/cli/bcllm_questions.py:223]
         ├─→ SnapshotRepository.get_by_experiment_and_question() [IDEMPOTENCY CHECK]
         └─→ snapshot_repo.save() [INSERT OR REPLACE]
```

**File Locations:**
- Entry: `src/cli/bcllm_experiment.py:1-620`
- ConfigResolver: `src/core/config_resolver.py:1-550`
- QuestionLoader: `src/core/question_loader.py:1-270`
- VariantSignature: `src/utils/variant_signature.py:1-100`

---

### Entry Point 3: `experiment_commands.py` → `ExperimentManager.create_experiment()` (Internal Module)

```
CLI INVOCATION:
  bcllm.py experiment create <name> --questions Q001-Q010 --seed AUTO
  (via src/cli/cli.py subcommand parser)

EXECUTION FLOW:
  [Note: This path is used by experiment_commands.py handle_experiment_command()]
  
  src/cli/experiment_commands.py:108 (create_experiment method)
    │
    ├─→ self.experiment_repo.get_by_name() [DUPLICATE CHECK]
    │
    ├─→ get_settings() [line 132]
    │    └─→ Settings() from src/utils/config.py
    │    └─→ Same as Entry Point 1
    │
    ├─→ _build_config_json(settings, seed) [line 135]
    │    └─→ [line 698] Returns JSON with:
    │        default_prompt, use_structured_outputs, random_seed_policy,
    │        questionnaire_path, openrouter_base_url, default_iterations
    │
    ├─→ _build_config_hash(settings, seed) [line 136]
    │    └─→ [line 715] Hashes ONLY 3 protocol keys:
    │        default_prompt, use_structured_outputs, random_seed_policy
    │    └─→ Returns hash[:16] (TRUNCATED!)
    │
    ├─→ Experiment() dataclass [line 138]
    │    └─→ Uses system_prompt_template, user_prompt_template from settings
    │
    ├─→ self.experiment_repo.create() [line 145]
    │    └─→ [NOT SHOWN IN REPOSITORY - uses ModelVariantRepository.create()]
    │
    └─→ Question Snapshotting:
         ├─→ QuestionLoader(str(settings.questionnaire_path)) [line 158]
         │    └─→ [src/core/loader.py:149] - DIFFERENT loader than Entry Point 2!
         ├─→ loader.load() [pydantic-validated schema]
         ├─→ _expand_question_filters() [line 737]
         │    └─→ Expands Q001-Q010, skips "where" keyword
         ├─→ question_lookup = {q.question_id: q for q in all_questions}
         ├─→ _build_question_json() [line 763]
         │    └─→ Different payload structure than Entry Point 2!
         └─→ snapshot_repo.create_if_not_exists() [line 172]
              └─→ [NOT SHOWN IN REPOSITORY - uses QuestionSnapshotRepository.create_if_not_exists()]
```

**File Locations:**
- Entry: `src/cli/experiment_commands.py:108-180`
- QuestionLoader (pydantic): `src/core/loader.py:1-200`
- Note: Uses `src.core.loader.QuestionLoader` (pydantic) NOT `src.core.question_loader.QuestionLoader` (dict-based)

---

## 2. CONFIGURATION RESOLUTION MATRIX

### .env Keys and Resolution Behavior

| .env Key | Entry Point 1 (main.py) | Entry Point 2 (bcllm_experiment.py) | Entry Point 3 (experiment_commands.py) |
|----------|------------------------|-------------------------------------|---------------------------------------|
| **QUESTIONS_DATASET_PATH** | ✅ Via `settings.questions_dataset_path` (pydantic) | ✅ Via `ConfigResolver.load_env()` → `env_dict.get()` | ✅ Via `settings.questionnaire_path` (pydantic) |
| **DEFAULT_QUESTIONS** | ✅ Via `settings.default_questions` → `resolve_with_feedback()` | ✅ Via `env_dict.get('DEFAULT_QUESTIONS')` | ❌ NOT USED - requires explicit `--questions` |
| **RANDOM_SEED** | ✅ Via `settings.random_seed` → `resolve_with_feedback()` | ✅ Via `ConfigResolver.resolve_seed()` | ✅ Via `settings.random_seed` |
| **RUN_RESPONSES_SEED** | ❌ Not read directly | ✅ Via `ConfigResolver.build_experiment_config_dict()` | ❌ Not read directly |
| **SYSTEM_PROMPT_TEMPLATE** | ✅ Via `settings.system_prompt` (mapped in `__init__`) | ✅ Via `ConfigResolver.resolve_prompt()` | ✅ Via `settings.system_prompt` |
| **USER_PROMPT_TEMPLATE** | ✅ Via `settings.user_prompt_template` (mapped in `__init__`) | ✅ Via `ConfigResolver.resolve_prompt()` | ✅ Via `settings.user_prompt_template` |
| **MODEL_TEMPERATURE** | ❌ Not used at experiment creation | ✅ Via `ConfigResolver._parse_float_env()` | ❌ Not used |
| **MODEL_MAX_TOKENS_TOTAL** | ❌ Not used | ✅ Via `ConfigResolver._parse_int_env()` | ❌ Not used |
| **MODEL_REASONING_EFFORT** | ❌ Not used | ✅ Via `ConfigResolver.env_dict.get()` | ❌ Not used |
| **MODEL_VISION** | ❌ Not used | ✅ Via `ConfigResolver._parse_bool_env()` | ❌ Not used |
| **STRUCTURED_OUTPUTS** | ❌ Not used | ✅ Via `ConfigResolver._parse_bool_env()` | ❌ Not used |
| **QUESTIONS_STATUS_ADD** | ❌ Not used | ✅ Via `env_dict.get()` → filter application | ❌ Not used |
| **QUESTIONS_STATUS_EXCLUDE** | ❌ Not used | ✅ Via `env_dict.get()` → filter application | ❌ Not used |
| **BASE_URL** | ❌ Not used | ✅ Via `ConfigResolver.env_dict.get()` | ❌ Not used |

### Resolution Order Comparison

| Configuration | Entry Point 1 | Entry Point 2 | Entry Point 3 |
|--------------|---------------|---------------|---------------|
| **Questions** | CLI > .env (DEFAULT_QUESTIONS) > all from JSON | CLI > .env (DEFAULT_QUESTIONS) > all from JSON | CLI > all from JSON (no .env default) |
| **Seed** | CLI > .env (RANDOM_SEED) > None | CLI > .env (RUN_RESPONSES_SEED) > "AUTO" string | CLI > .env (RANDOM_SEED) > None |
| **Prompts** | CLI > .env (SYSTEM_PROMPT_TEMPLATE) > None | CLI > .env (SYSTEM_PROMPT) > None | CLI > .env (SYSTEM_PROMPT_TEMPLATE) > None |
| **Model Config** | N/A at creation | CLI > .env > NULL | N/A at creation |

### Critical Divergence: Config Hash Generation

| Aspect | Entry Point 1 & 3 (main.py, experiment_commands.py) | Entry Point 2 (bcllm_experiment.py) |
|--------|---------------------------------------------------|-------------------------------------|
| **Hash Input** | 3 protocol keys only | 14-key full config dict |
| **Keys Included** | `default_prompt`, `use_structured_outputs`, `random_seed_policy` | ALL 14 keys from `build_experiment_config_dict()` |
| **Hash Length** | 16 characters (truncated) | 64 characters (full SHA-256) |
| **JSON Format** | `sort_keys=True, default=str` | `indent=None, separators=(',', ':')` (compact) |
| **Behavioral Impact** | Same protocol = same hash (allows model variant comparison) | Any config change = different hash (prevents variant comparison) |

**CODE COMPARISON:**

```python
# Entry Point 1 & 3 (CORRECT - protocol-only hash)
# src/cli/experiment_commands.py:715-726
def _build_config_hash(self, settings: Settings, seed: Optional[str | int]) -> str:
    config = {
        "default_prompt": settings.default_prompt,
        "use_structured_outputs": settings.use_structured_outputs,
        "random_seed_policy": str(seed) if seed else "none",
    }
    config_json = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(config_json.encode()).hexdigest()[:16]
```

```python
# Entry Point 2 (INCORRECT - full config hash)
# src/cli/bcllm_experiment.py:317-318
config_dict = resolver.build_experiment_config_dict(args)  # 14 keys
config_json = json.dumps(config_dict, indent=None, separators=(',', ':'))
config_hash = hashlib.sha256(config_json.encode('utf-8')).hexdigest()  # 64 chars
```

---

## 3. VALIDATION COVERAGE TABLE

| Validation | Entry Point 1 | Entry Point 2 | Entry Point 3 |
|-----------|---------------|---------------|---------------|
| **Empty experiment name** | ❌ Not checked (assumes CLI provides) | ✅ Line 275-278 | ❌ Not checked |
| **Duplicate experiment name** | ✅ Via `ExperimentManager.create_experiment()` line 124 | ✅ Line 280-283 | ✅ Line 124 |
| **Boolean value validation (--vision/--structured)** | ❌ Not validated | ✅ Line 297-310 (`_validate_bool_value()`) | ❌ Not validated |
| **Model ID format validation** | ❌ Not validated | ✅ Line 347-351 (`validate_model_id()`) | ❌ Not validated |
| **Variant signature collision** | ❌ Not checked | ✅ Line 353-356 | ❌ Not checked |
| **Question spec parsing** | ✅ Via `CLIParser._expand_question_ranges()` | ✅ Via `QuestionLoader.parse_question_spec()` | ✅ Via `_expand_question_filters()` |
| **Question dataset existence** | ✅ Line 346-349 (warning only) | ✅ Line 379-386 (fails loudly) | ✅ Via `QuestionLoader.load()` |
| **Question payload validation** | ✅ Via `QuestionLoader.validate_payload()` (pydantic) | ❌ No validation (dict-based loader) | ✅ Via `QuestionLoader.validate_payload()` (pydantic) |
| **Answer key uniqueness** | ✅ Via `QuestionLoader.validate_answer_key_uniqueness()` | ❌ No validation | ✅ Via `QuestionLoader.validate_answer_key_uniqueness()` |
| **Snapshot idempotency** | ✅ Via `create_if_not_exists()` | ✅ Via manual `get_by_experiment_and_question()` check | ✅ Via `create_if_not_exists()` |
| **Filter syntax validation** | ❌ Not validated | ✅ Line 409-436 (`parse_filter()` with try/except) | ❌ Not validated |

### Validation Error Messages

| Entry Point | Error Format | Exit Code |
|-------------|-------------|-----------|
| **Entry Point 1** | Rich Console (`console.print(f"[red]Error: {e}[/red]")`) | 1 |
| **Entry Point 2** | stderr (`print(..., file=sys.stderr)`) | 1 |
| **Entry Point 3** | Rich Console | 1 |

---

## 4. PERSISTENCE COMPARISON

### Database Path

| Entry Point | Database Path | Notes |
|-------------|---------------|-------|
| **Entry Point 1** | `settings.database_path` (from pydantic) | Default: `./data/benchmark.db` |
| **Entry Point 2** | `./data/bcllm.db` (hardcoded in `get_database_connection()`) | **DIFFERENT DATABASE!** |
| **Entry Point 3** | `settings.database_path` (from pydantic) | Default: `./data/benchmark.db` |

### Data Written to `experiments` Table

| Field | Entry Point 1 & 3 | Entry Point 2 |
|-------|------------------|---------------|
| `experiment_id` | Auto-generated (repository) | `f"exp_{uuid.uuid4().hex[:8]}"` |
| `name` | From CLI | From CLI |
| `description` | Auto-generated timestamp | Empty string `""` |
| `config_json` | 6-key JSON (protocol + metadata) | 14-key JSON (full config) |
| `config_hash` | 16-char truncated SHA-256 | 64-char full SHA-256 |
| `created_at` | DB DEFAULT CURRENT_TIMESTAMP | DB DEFAULT CURRENT_TIMESTAMP |

### Data Written to `model_variants` Table

| Field | Entry Point 1 & 3 | Entry Point 2 |
|-------|------------------|---------------|
| `variant_id` | `VariantConfig.build_variant_id()` | `f"var_{uuid.uuid4().hex[:8]}"` |
| `experiment_id` | FK to experiment | FK to experiment |
| `model_id` | From CLI `--add-model` | From CLI `--add-model` |
| `variant_signature` | `VariantConfig.build_signature()` | `generate_variant_signature()` |
| `config` | Full variant config JSON | Full model config JSON (10 keys) |
| `created_at` | DB DEFAULT | DB DEFAULT |

**CRITICAL:** Entry Point 2 uses `experiment.experiment_id` for variants (tied to experiment), while Entry Point 1 & 3 use global variants (no experiment association in TO-BE architecture).

### Data Written to `question_snapshots` Table

| Field | Entry Point 1 & 3 | Entry Point 2 |
|-------|------------------|---------------|
| `snapshot_id` | Auto-generated | `f"snap_{uuid.uuid4().hex[:8]}"` |
| `experiment_id` | FK to experiment | FK to experiment |
| `json_question_id` | `question.question_id` | `question.get('source_id') or question.get('id')` |
| `question_position` | Internal numeric ID (1..N) | `question.get('internal_id')` |
| `question_payload` | JSON with: `id`, `stem`, `options`, `correct_answer`, `has_image`, `image_path`, `status` | JSON with: `stem`, `options`, `answer_key`, `meta`, `internal_id`, `source_id` |
| `created_at` | DB DEFAULT | DB DEFAULT |

**PAYLOAD STRUCTURE DIFFERENCE:**

```json
// Entry Point 1 & 3 (pydantic loader)
{
  "id": "Q001",
  "stem": "Question text...",
  "options": ["A", "B", "C", "D"],
  "correct_answer": "A",
  "has_image": false,
  "image_path": null,
  "status": "active"
}
```

```json
// Entry Point 2 (dict-based loader)
{
  "stem": "Question text...",
  "options": ["A", "B", "C", "D"],
  "answer_key": "A",
  "meta": {...},
  "internal_id": 1,
  "source_id": "Q001"
}
```

---

## 5. BEHAVIORAL DIVERGENCE ANALYSIS

### Question Loading & Filtering

| Aspect | Entry Point 1 | Entry Point 2 | Entry Point 3 |
|--------|---------------|---------------|---------------|
| **Loader Class** | `src.core.loader.QuestionLoader` (pydantic) | `src.core.question_loader.QuestionLoader` (dict-based) | `src.core.loader.QuestionLoader` (pydantic) |
| **Dataset Format Support** | Wrapped only (`{"dataset": {...}, "questions": [...]}`) | Flat list OR wrapped (`{"questions": [...]}`) | Wrapped only |
| **ID Assignment** | Auto-generated from pydantic schema | `assign_internal_ids()` method | Auto-generated from pydantic schema |
| **Range Parsing** | `_expand_question_filters()` (simple string split) | `parse_question_spec()` (regex-based) | `_expand_question_filters()` (simple string split) |
| **Filter Support** | ❌ No `--where`/`--exclude` support | ✅ Full support via `filter_questions()` | ❌ No `--where`/`--exclude` support |
| **Status Filtering** | ❌ Not applied | ✅ Via `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` | ❌ Not applied |

### Model Variant Creation

| Aspect | Entry Point 1 & 3 | Entry Point 2 |
|--------|------------------|---------------|
| **Variant ID Generation** | `VariantConfig.build_variant_id()` | `f"var_{uuid.uuid4().hex[:8]}"` (random) |
| **Signature Generation** | `VariantConfig.build_signature()` | `generate_variant_signature()` |
| **Config Keys** | Uses `VariantConfig` class fields | Uses 10-key model config dict |
| **Idempotency** | Check by `variant_id` | Check by `variant_signature` |
| **Experiment Association** | Global variants (no FK) | Tied to experiment (`experiment_id` FK) |

### Seed Resolution

| Aspect | Entry Point 1 | Entry Point 2 | Entry Point 3 |
|--------|---------------|---------------|---------------|
| **Resolution Method** | `resolve_with_feedback()` | `ConfigResolver.resolve_seed()` | `resolve_with_feedback()` |
| **AUTO Handling** | Returns "AUTO" string (not resolved) | Returns "AUTO" string (not resolved) | Returns "AUTO" string (not resolved) |
| **Env Key** | `RANDOM_SEED` | `RUN_RESPONSES_SEED` | `RANDOM_SEED` |
| **Default** | None (no randomization) | "AUTO" string | None (no randomization) |

**NOTE:** Entry Point 2 uses `RUN_RESPONSES_SEED` (run-level key) for experiment creation, which is semantically incorrect per the architecture contract.

---

## 6. CORRECT BEHAVIOR IDENTIFICATION

### Most Recent Behavior

**Entry Point 1 (`main.py` → `ExperimentManager`)** has the **MOST RECENT** behavior:
- Uses `config_hierarchy.py` for resolution feedback
- Uses pydantic-based `QuestionLoader` with schema validation
- Follows TO-BE architecture (global variants, protocol-only hash)
- Has Rich Console output formatting
- Integrated with new execution axis (Planner → ExecutionEngine → ResultWriter)

### Correct .env Resolution

**Entry Point 2 (`bcllm_experiment.py`)** has the **MOST COMPLETE** .env resolution:
- Reads ALL 14 config keys from `.env`
- Supports `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` filtering
- Properly handles `DEFAULT_QUESTIONS` fallback
- Uses `ConfigResolver` with explicit CLI > .env > NULL ordering

**HOWEVER**, Entry Point 2 has **INCORRECT** hash generation (full config vs. protocol-only).

### Complete Validation

**Entry Point 2 (`bcllm_experiment.py`)** has the **MOST COMPLETE** validation:
- Empty name check
- Boolean value validation
- Model ID format validation
- Variant signature collision detection
- Filter syntax validation
- Dataset existence check (fails loudly)

### Source of Truth for Promotion

**RECOMMENDATION:** Promote **Entry Point 2's `ConfigResolver` + Entry Point 1's `ExperimentManager`** as the unified source of truth:

1. **Use `ConfigResolver`** (Entry Point 2) for:
   - Complete .env resolution (14 keys)
   - Explicit CLI > .env > NULL ordering
   - Boolean parsing utilities
   - Type conversion utilities

2. **Use `ExperimentManager.create_experiment()`** (Entry Point 1) for:
   - Protocol-only config hash (3 keys, 16-char truncated)
   - Global variant architecture (no experiment FK)
   - Pydantic-based question validation
   - Rich Console feedback

3. **Use `bcllm_experiment.py._create_question_snapshots()`** (Entry Point 2) for:
   - `--where`/`--exclude` filter support
   - `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` application
   - Idempotency via manual check + save

---

## 7. RISK ASSESSMENT

### If Consolidating to Entry Point 1 (main.py → ExperimentManager)

**BEHAVIOR LOST:**
- ❌ `--where`/`--exclude` question filtering
- ❌ `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` auto-filtering
- ❌ `DEFAULT_QUESTIONS` from .env (only CLI `--questions` works)
- ❌ Model variant creation at experiment creation time
- ❌ Boolean value validation for `--vision`/`--structured`
- ❌ Model ID format validation
- ❌ Standalone script execution (no `bcllm_experiment.py` entry point)

**RISK LEVEL:** HIGH - Loses critical filtering and validation features

---

### If Consolidating to Entry Point 2 (bcllm_experiment.py)

**BEHAVIOR LOST:**
- ❌ Protocol-only config hash (breaks experiment variant comparison)
- ❌ Pydantic-based question validation (answer key uniqueness, required fields)
- ❌ Rich Console feedback formatting
- ❌ Integration with new execution axis (Planner/ExecutionEngine/ResultWriter)
- ❌ Global variant architecture (uses experiment-tied variants)
- ❌ Truncated hash (16 chars) for deduplication

**RISK LEVEL:** CRITICAL - Breaks core architectural contract (protocol hash)

---

### If Consolidating to Entry Point 3 (experiment_commands.py internal)

**BEHAVIOR LOST:**
- ❌ All Entry Point 1 losses (same code path)
- ❌ Standalone script execution
- ❌ Filtering support
- ❌ Validation completeness

**RISK LEVEL:** HIGHEST - Least complete implementation

---

## 8. PROMOTION PLAN

### Phase 1: Preserve ConfigResolver (from Entry Point 2)

**File:** `src/core/config_resolver.py`

**Methods to Preserve:**
- `load_env()` - Complete .env loading
- `build_experiment_config_dict()` - 14-key config dict
- `build_model_config_dict()` - 10-key model config
- `build_run_config_dict()` - 3-key run config
- `resolve_prompt()` - CLI > .env > default
- `resolve_seed()` - CLI > .env > "AUTO" string
- `resolve_seed_for_run()` - AUTO resolution at run level
- `_resolve_bool_cli_or_env()` - Boolean resolution
- `_parse_int_env()`, `_parse_float_env()` - Type conversion
- `_parse_bool_env()` - Boolean parsing

**Integration Point:** Use in `ExperimentManager.create_experiment()` for config dict generation, but NOT for hash calculation.

---

### Phase 2: Preserve Protocol Hash (from Entry Point 1/3)

**File:** `src/cli/experiment_commands.py`

**Method:** `_build_config_hash()` (lines 715-726)

**Preserve Exactly:**
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

**DO NOT USE:** Entry Point 2's hash generation (full config, 64 chars).

---

### Phase 3: Preserve Question Filtering (from Entry Point 2)

**File:** `src/cli/bcllm_experiment.py`

**Method:** `_create_question_snapshots()` (lines 357-456)

**Preserve:**
- `--where`/`--exclude` CLI flag parsing
- `QUESTIONS_STATUS_ADD`/`QUESTIONS_STATUS_EXCLUDE` from .env
- `filter_questions()` integration
- Idempotency via manual check

**Integration:** Merge into `ExperimentManager.create_experiment()` after question loading.

---

### Phase 4: Preserve Validation (from Entry Point 2)

**File:** `src/cli/bcllm_experiment.py`

**Validations to Preserve:**
- Empty name check (lines 275-278)
- `_validate_bool_value()` (line 338)
- Model ID validation via `validate_model_id()` (lines 347-351)
- Variant signature collision check (lines 353-356)
- Filter syntax validation (lines 409-436)

**Integration:** Add to `ExperimentManager.create_experiment()` and `_add_models_at_creation()`.

---

### Phase 5: Preserve QuestionLoader Duality

**Files:**
- `src/core/loader.py` (pydantic)
- `src/core/question_loader.py` (dict-based)

**Recommendation:**
- **Consolidate to pydantic loader** (`src.core.loader.QuestionLoader`)
- **Port features from dict-based loader:**
  - `parse_question_spec()` with regex support
  - `assign_internal_ids()` method
  - Flat list dataset format support
  - `filter_questions()` integration

**Deprecate:** `src.core.question_loader.QuestionLoader` (dict-based)

---

### Phase 6: Database Path Unification

**Issue:** Entry Point 2 uses `./data/bcllm.db`, while Entry Points 1 & 3 use `settings.database_path` (default `./data/benchmark.db`).

**Resolution:**
- **Standardize on `settings.database_path`** (pydantic settings)
- **Update `bcllm_experiment.py.get_database_connection()`** to use `get_settings().database_path`
- **Deprecate hardcoded `./data/bcllm.db`**

---

## 9. SAFETY CHECKLIST

### Recent Fixes Preservation

- [x] **Config Hierarchy Feedback** (`src/utils/config_hierarchy.py`) - Used by Entry Points 1 & 3
- [x] **Reasoning Effort Simplification** (`src/cli/cli.py:267-275`) - Applied to all entry points via shared CLIParser
- [x] **Protocol-Only Hash** (`src/cli/experiment_commands.py:715-726`) - Entry Point 2 NOT updated (MUST FIX)

### Behavior Loss Prevention

- [ ] **Question Filtering** - Must port from Entry Point 2 to Entry Point 1
- [ ] **Complete .env Resolution** - Must port ConfigResolver to Entry Point 1
- [ ] **Validation Completeness** - Must port validation from Entry Point 2 to Entry Point 1
- [ ] **Hash Generation** - Must fix Entry Point 2 to use protocol-only hash
- [ ] **Database Path** - Must unify to settings.database_path

### Legacy Behavior Prevention

- [ ] **RUN_RESPONSES_SEED at Experiment Level** - Entry Point 2 uses run-level key for experiments (SEMANTIC ERROR)
- [ ] **Full Config Hash** - Entry Point 2 hashes 14 keys (breaks variant comparison)
- [ ] **Experiment-Tied Variants** - Entry Point 2 uses FK to experiment (conflicts with TO-BE architecture)
- [ ] **Hardcoded Database Path** - Entry Point 2 uses `./data/bcllm.db`

---

## 10. FINAL RECOMMENDATIONS

### Immediate Actions (BEFORE Consolidation)

1. **DO NOT CONSOLIDATE** until behavioral gaps are addressed
2. **Port `ConfigResolver`** to Entry Point 1's `ExperimentManager`
3. **Port question filtering** from Entry Point 2 to Entry Point 1
4. **Fix Entry Point 2's hash generation** to use protocol-only hash
5. **Unify database paths** across all entry points
6. **Consolidate QuestionLoader** implementations (pydantic preferred)

### Long-Term Architecture

1. **Single Entry Point:** `main.py` → `BenchmarkRunner` → `ExperimentManager`
2. **Deprecate:** `bcllm_experiment.py` standalone script (or make it a thin wrapper)
3. **Centralize:** All config resolution in `ConfigResolver`
4. **Standardize:** Protocol-only hash for all experiment creation
5. **Preserve:** Filtering, validation, and idempotency features

---

**INVESTIGATION COMPLETE.** This report documents all observable entry points, execution flows, configuration resolution paths, validation behaviors, and persistence behaviors without proposing fixes or modifications.

**NEXT STEP:** Promotion planning approval required before any code changes.
