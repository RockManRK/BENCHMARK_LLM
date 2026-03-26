# GLOBAL AUDIT: CLI Command Entry Points and Execution Paths

**Date:** 2026-03-26  
**Status:** Audit Complete  
**Scope:** `src/` codebase only  
**Type:** Investigation and Documentation ONLY  

---

## 1. Executive Summary

This audit identifies **significant entry point proliferation** across the CLI codebase. Multiple parallel entry points exist for the same logical commands, creating potential for inconsistent behavior, state divergence, and maintenance burden.

### Key Findings:

| Finding | Severity | Description |
|---------|----------|-------------|
| **Dual CLI Paradigms** | HIGH | Two complete CLI systems coexist: `main.py` (new paradigm) and standalone `bcllm_*.py` scripts (legacy) |
| **Experiment Commands** | HIGH | 3+ entry points for experiment creation/management with different validation and persistence logic |
| **Model Commands** | MEDIUM | 2 entry points with different config resolution paths |
| **Question Commands** | MEDIUM | 2 entry points with different filtering logic |
| **Run Commands** | MEDIUM | 2 entry points with different seed resolution |
| **Execute Commands** | HIGH | 2 completely different execution flows (new Planner/Engine/Writer vs legacy) |

### Entry Point Count by Command:

| Command | Entry Points | Files Involved |
|---------|--------------|----------------|
| create-experiment | 3 | `main.py`, `bcllm_experiment.py`, `experiment_commands.py` |
| add-model | 3 | `main.py`, `bcllm_model.py`, `experiment_commands.py` |
| remove-model | 2 | `main.py`, `bcllm_model.py` |
| list-models | 2 | `main.py` (via show), `bcllm_model.py` |
| add-questions | 3 | `main.py`, `bcllm_questions.py`, `experiment_commands.py` |
| list-questions | 2 | `main.py` (via show), `bcllm_questions.py` |
| create-run | 3 | `main.py`, `bcllm_run.py`, `experiment_commands.py` |
| execute | 2 | `main.py`, `bcllm_execute.py` |

---

## 2. Per-Command Analysis

### 2.1 CREATE-EXPERIMENT

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_create_experiment()` | `main.py` | ~400 | User-accessible via `--create-experiment` |
| 2 | `handle_create_experiment()` | `bcllm_experiment.py` | ~267 | User-accessible via standalone script |
| 3 | `ExperimentManager.create_experiment()` | `experiment_commands.py` | ~104 | Internal (called by main.py) |

#### Execution Flow Diagrams:

**Path 1: main.py (New Paradigm)**
```
CLI: --create-experiment NAME
  ↓
main.py:BenchmarkRunner.run() → line 335
  ↓
main.py:_handle_create_experiment() → line 400
  ↓
ConfigResolver.load_env() → line 421
  ↓
ExperimentManager(db_manager) → line 425
  ↓
ExperimentManager.create_experiment() → line 437
  ↓
  ├─→ ExperimentRepository.create() → DB INSERT
  ├─→ QuestionLoader.load() → Load questions from JSON
  ├─→ QuestionSnapshotRepository.create_if_not_exists() → DB INSERT (idempotent)
  └─→ Console output
```

**Path 2: bcllm_experiment.py (Standalone)**
```
CLI: python bcllm_experiment.py --create-experiment NAME
  ↓
bcllm_experiment.py:main() → line 632
  ↓
bcllm_experiment.py:handle_create_experiment() → line 267
  ↓
ConfigResolver.load_env() → line 285
  ↓
ConfigResolver.build_experiment_config_dict() → line 287
  ↓
ConfigResolver.build_config_hash() → line 288
  ↓
ExperimentRepository.save() → DB INSERT
  ↓
  ├─→ _add_models_at_creation() (if --add-model) → line 312
  └─→ _create_question_snapshots() → line 322
       ├─→ QuestionLoader.load_dataset()
       ├─→ filter_questions() → Apply --where/--exclude
       └─→ SnapshotRepository.save() → DB INSERT
```

**Path 3: experiment_commands.py (Internal Module)**
```
Called from main.py:_handle_create_experiment()
  ↓
experiment_commands.py:ExperimentManager.create_experiment() → line 104
  ↓
  ├─→ ExperimentRepository.create() → line 154
  ├─→ QuestionLoader.load() → line 162
  ├─→ _build_question_json() → line 334
  └─→ QuestionSnapshotRepository.create_if_not_exists() → line 178
```

#### Configuration Resolution Comparison:

| Aspect | Path 1 (main.py) | Path 2 (bcllm_experiment.py) | Path 3 (experiment_commands.py) |
|--------|------------------|------------------------------|---------------------------------|
| .env Loading | `ConfigResolver.load_env()` | `ConfigResolver.load_env()` | Via `get_settings()` |
| Seed Resolution | `resolve_with_feedback()` | `resolve_seed()` | `resolve_seed()` |
| Config Hash | Via `ExperimentManager` | `build_config_hash()` | Via `ExperimentManager` |
| Questions Source | `settings.questions_dataset_path` | `QUESTIONS_DATASET_PATH` env | `settings.questionnaire_path` |
| Default Questions | All if not specified | All if not specified | All if not specified |

#### Validation Behavior:

| Validation | Path 1 | Path 2 | Path 3 |
|------------|--------|--------|--------|
| Duplicate experiment name | ✓ (ExperimentManager) | ✓ (repo.get_by_name) | ✓ (repo.get_by_name) |
| Empty name | ✗ | ✓ (line 274) | ✗ |
| Vision/Structured bool | ✗ | ✓ (lines 277-283) | ✗ |
| Model ID format | ✗ | ✗ | ✗ |
| Question spec parsing | Via `CLIParser._expand_question_ranges()` | Via `QuestionLoader.parse_question_spec()` | Via `_expand_question_filters()` |

#### Persistence Behavior:

| Aspect | Path 1 | Path 2 | Path 3 |
|--------|--------|--------|--------|
| Experiment INSERT | `config_json`, `config_hash` | `config_json`, `config_hash` | `config_json`, `config_hash` |
| Snapshot INSERT | `question_payload` JSON | `question_payload` JSON | `question_payload` JSON |
| Idempotency | `create_if_not_exists()` | Manual check + save | `create_if_not_exists()` |
| Config JSON keys | 14 keys (contract) | 14 keys (contract) | 14 keys (contract) |

#### Authoritative Path:
**Path 1 (main.py → experiment_commands.py)** is the documented authoritative path per QWEN.md. Path 2 (bcllm_experiment.py) is a legacy standalone script that duplicates functionality.

#### Risks:
1. **Config hash divergence**: Path 2 uses `ConfigResolver.build_config_hash()` directly, while Path 1/3 delegate to ExperimentManager
2. **Question filtering inconsistency**: Path 2 applies `--where/--exclude` filters; Path 1/3 do not at creation time
3. **Validation gaps**: Path 1/3 skip empty name and bool validation that Path 2 performs

---

### 2.2 ADD-MODEL

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_add_models_to_experiment()` | `main.py` | ~547 | User-accessible via `--experiment NAME --add-model` |
| 2 | `handle_add_model()` | `bcllm_model.py` | ~145 | User-accessible via standalone script |
| 3 | `ExperimentManager.add_models_to_experiment()` | `experiment_commands.py` | ~425 | Internal (called by main.py) |

#### Execution Flow Diagrams:

**Path 1: main.py → experiment_commands.py**
```
CLI: --experiment NAME --add-model MODEL_ID
  ↓
main.py:BenchmarkRunner.run() → line 338
  ↓
main.py:_handle_experiment_context() → line 467
  ↓
main.py:_handle_add_models_to_experiment() → line 547
  ↓
ExperimentManager.add_models_to_experiment() → line 561
  ↓
  ├─→ _create_model_variant() → line 677
  ├─→ VariantRepository (GLOBAL - not experiment-scoped)
  └─→ Console output
```

**Path 2: bcllm_model.py (Standalone)**
```
CLI: python bcllm_model.py --experiment NAME --add-model MODEL_ID
  ↓
bcllm_model.py:main() → line 296
  ↓
bcllm_model.py:handle_add_model() → line 145
  ↓
  ├─→ validate_model_id() → line 147
  ├─→ _validate_bool_value(vision/structured) → lines 153-162
  ├─→ ExperimentRepository.get_by_name() → line 167
  ├─→ ConfigResolver.build_model_config_dict() → line 175
  ├─→ generate_variant_signature() → line 179
  ├─→ VariantRepository.get_by_signature() → line 181
  └─→ VariantRepository.save() → line 191
```

#### Configuration Resolution Comparison:

| Aspect | Path 1 (main.py) | Path 2 (bcllm_model.py) |
|--------|------------------|-------------------------|
| .env Loading | `get_settings()` | `ConfigResolver.load_env()` |
| Config Dict | `ExperimentManager._create_model_variant()` | `ConfigResolver.build_model_config_dict()` |
| Resolution Order | CLI > .env > experiment | CLI > .env > NULL |
| Vision/Structured | From `self.args.enable_vision` | From `args.vision` string parsing |

#### Validation Behavior:

| Validation | Path 1 | Path 2 |
|------------|--------|--------|
| Model ID format | ✗ | ✓ (`validate_model_id()`) |
| Vision bool | ✗ | ✓ (`_validate_bool_value()`) |
| Structured bool | ✗ | ✓ (`_validate_bool_value()`) |
| Duplicate variant | ✗ (GLOBAL variants) | ✓ (`get_by_signature()`) |
| Experiment exists | ✓ | ✓ |

#### Persistence Behavior:

| Aspect | Path 1 | Path 2 |
|--------|--------|--------|
| Variant INSERT | GLOBAL (no experiment_id tie) | experiment-scoped (has experiment_id) |
| Config JSON | 10 model keys | 10 model keys |
| Signature | Generated via `generate_variant_signature()` | Generated via `generate_variant_signature()` |
| Duplicate handling | Not checked | Returns error if exists |

#### Authoritative Path:
**Path 1 (main.py → experiment_commands.py)** per QWEN.md architecture. However, Path 2 has **better validation**.

#### Risks:
1. **Architecture mismatch**: Path 1 treats variants as GLOBAL; Path 2 treats them as experiment-scoped
2. **Validation gap**: Path 1 skips model ID format and bool validation
3. **Duplicate detection**: Path 1 does not check for duplicate signatures; Path 2 does

---

### 2.3 ADD-QUESTIONS

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_add_questions_to_experiment()` | `main.py` | ~503 | User-accessible via `--experiment NAME --add-questions` |
| 2 | `handle_add_questions()` | `bcllm_questions.py` | ~254 | User-accessible via standalone script |
| 3 | `ExperimentManager.add_questions_to_experiment()` | `experiment_commands.py` | ~192 | Internal (called by main.py) |

#### Configuration Resolution:

| Aspect | Path 1 (main.py) | Path 2 (bcllm_questions.py) |
|--------|------------------|----------------------------|
| .env Loading | `get_settings()` | `ConfigResolver.load_env()` |
| Dataset Path | `settings.questions_dataset_path` | `QUESTIONS_DATASET_PATH` env or `--source-file` |
| Question Parsing | `_expand_question_filters()` | `QuestionLoader.parse_question_spec()` |
| Filtering | ✗ | ✓ (`--where/--exclude` support) |

#### Validation Behavior:

| Validation | Path 1 | Path 2 |
|------------|--------|--------|
| Experiment exists | ✓ | ✓ |
| Question spec format | ✗ | ✓ (try/except parse) |
| Question exists in dataset | ✓ (warning) | ✓ (error) |
| Internal ID present | ✗ | ✓ |
| Filter format | N/A | ✓ (`parse_filter()`) |

#### Persistence Behavior:

| Aspect | Path 1 | Path 2 |
|--------|--------|--------|
| Snapshot INSERT | `create_if_not_exists()` (idempotent) | Manual check + `save()` |
| Payload structure | `_build_question_json()` | Inline JSON build |
| Duplicate handling | Returns existing ID | Skipped with message |

#### Authoritative Path:
**Path 1 (main.py → experiment_commands.py)** per architecture. Path 2 has more features (filtering).

#### Risks:
1. **Feature divergence**: Path 2 supports `--where/--exclude` filtering; Path 1 does not
2. **Payload structure**: Different JSON construction methods may produce different payloads
3. **Error handling**: Path 1 logs warnings; Path 2 returns errors

---

### 2.4 CREATE-RUN

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_create_run()` | `main.py` | ~737 | User-accessible via `--experiment NAME --create-run` |
| 2 | `handle_add_run()` | `bcllm_run.py` | ~94 | User-accessible via standalone script |
| 3 | `RunManager.create_run()` | `experiment_commands.py` | ~724 | Internal |

#### Seed Resolution (CRITICAL):

| Path | Method | Resolution Order | AUTO Handling |
|------|--------|------------------|---------------|
| Path 1 | `resolve_with_feedback()` | CLI > .env > None | Returns "AUTO" string |
| Path 2 | `ConfigResolver.resolve_seed_for_run()` | CLI > .env > generated | Resolves AUTO to hash |
| Path 3 | Via RunManager | CLI > .env > None | Returns "AUTO" string |

**CRITICAL DIVERGENCE**: Path 2 resolves AUTO to a number at creation time; Path 1/3 store "AUTO" string.

#### Validation Behavior:

| Validation | Path 1 | Path 2 | Path 3 |
|------------|--------|--------|--------|
| Experiment exists | ✓ | ✓ | ✓ |
| Has models | ✗ | ✗ | ✗ |
| Has snapshots | ✗ | ✗ | ✗ |
| Seed format | ✗ | ✗ | ✗ |

#### Persistence Behavior:

| Aspect | Path 1 | Path 2 | Path 3 |
|--------|--------|--------|--------|
| Run INSERT | `RunRepository.save()` | `RunRepository.save()` | `RunRepository.save()` |
| Config JSON | 3 keys (seed, prompts) | 3 keys (seed, prompts) | 3 keys (seed, prompts) |
| Status | "pending" | "pending" | "pending" |

#### Authoritative Path:
**Path 1 (main.py → experiment_commands.py)** per architecture.

#### Risks:
1. **CRITICAL - Seed resolution divergence**: Path 2 resolves AUTO immediately; Path 1/3 defer resolution
2. **Missing preconditions**: No path validates experiment has models/snapshots before run creation
3. **Prompt inheritance**: All paths handle differently

---

### 2.5 EXECUTE

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_execute_run()` | `main.py` | ~838 | User-accessible via `--experiment NAME --run NAME --execute` |
| 2 | `handle_execute()` | `bcllm_execute.py` | ~203 | User-accessible via standalone script |

#### Execution Flow Comparison:

**Path 1: main.py (New Execution Axis)**
```
CLI: --experiment NAME --run NAME --execute
  ↓
main.py:_handle_execute_run() → line 838
  ↓
  ├─→ Planner(db_manager).build_plan() → line 877
  │    ├─→ Validate experiment exists
  │    ├─→ Validate has models/snapshots
  │    ├─→ Get runs (pending or specific)
  │    ├─→ Resolve effective prompts (run > experiment)
  │    └─→ Resolve effective seed (run > experiment)
  ├─→ ExecutionEngine(api_client, randomizer, parser).execute(plan) → line 895
  │    ├─→ NO DB ACCESS
  │    ├─→ Apply randomization
  │    ├─→ Call API
  │    ├─→ Parse response
  │    └─→ Return ExecutionResult list
  └─→ ResultWriter(db_manager).write_results(results) → line 903
       ├─→ Calculate needs_review
       ├─→ INSERT OR IGNORE responses
       ├─→ INSERT errors
       └─→ UPDATE run status
```

**Path 2: bcllm_execute.py (Legacy)**
```
CLI: python bcllm_execute.py --experiment NAME --execute
  ↓
bcllm_execute.py:handle_execute() → line 203
  ↓
  ├─→ Planner(conn).build_plan() → line 258
  │    ├─→ Validate experiment exists
  │    ├─→ Validate has models/snapshots
  │    ├─→ Apply filters (run_ids, question_ids, model_variant_ids)
  │    └─→ Build PlanRun items
  ├─→ ExecutionEngine(api_client, randomizer, parser).execute(plan) → line 275
  │    └─→ Same as Path 1
  └─→ ResultWriter(conn).write_results(results) → line 280
       └─→ Same as Path 1
```

#### Configuration Resolution:

| Aspect | Path 1 | Path 2 |
|--------|--------|--------|
| Planner | `src.core.planner.Planner` | `src.core.planner.Planner` |
| Engine | `src.core.execution_engine.ExecutionEngine` | `src.core.execution_engine.ExecutionEngine` |
| Writer | `src.core.result_writer.ResultWriter` | `src.core.result_writer.ResultWriter` |
| API Client | `src.api.client.OpenRouterClient` | Placeholder `OpenRouterClient` (local) |
| Randomizer | `AnswerRandomizer(run_id=None)` | `AnswerRandomizer(seed=plan.runs[0].seed_effective)` |

#### Validation Behavior:

| Validation | Path 1 | Path 2 |
|------------|--------|--------|
| Experiment exists | ✓ (Planner) | ✓ (Planner) |
| Has models | ✓ (Planner) | ✓ (Planner) |
| Has snapshots | ✓ (Planner) | ✓ (Planner) |
| Filter validity | ✗ | ✓ (`validate_filters()`) |
| Run belongs to experiment | ✗ | ✓ |
| Question exists in experiment | ✗ | ✓ |
| Model variant exists in experiment | ✗ | ✓ |

#### Persistence Behavior:

| Aspect | Path 1 | Path 2 |
|--------|--------|--------|
| Response INSERT | `needs_review` calculated | `needs_review` calculated |
| Error INSERT | ✓ | ✓ |
| Run status UPDATE | ✓ | ✓ |
| Idempotency | Via UNIQUE constraint | Via UNIQUE constraint |

**Note**: ResultWriter implementation differs between files read - repository.py version calculates `needs_review`, but bcllm_execute.py uses a different ResultWriter.

#### Authoritative Path:
**Path 1 (main.py)** per QWEN.md architecture document.

#### Risks:
1. **API Client divergence**: Path 1 uses `src.api.client`; Path 2 uses local placeholder
2. **Randomizer seeding**: Path 1 initializes with `run_id=None`; Path 2 uses `seed=plan.runs[0].seed_effective`
3. **Filter validation**: Path 2 validates filters before execution; Path 1 relies on Planner
4. **ResultWriter version**: Different ResultWriter implementations may calculate `needs_review` differently

---

### 2.6 REMOVE-MODEL

#### Entry Point Inventory:

| # | Entry Point | File | Line | Accessibility |
|---|-------------|------|------|---------------|
| 1 | `BenchmarkRunner._handle_remove_model_from_experiment()` | `main.py` | ~680 | User-accessible |
| 2 | `handle_remove_model()` | `bcllm_model.py` | ~237 | User-accessible |

#### Behavior Comparison:

| Aspect | Path 1 (main.py) | Path 2 (bcllm_model.py) |
|--------|------------------|-------------------------|
| Implementation | Calls `ExperimentManager.remove_model_from_experiment()` | Direct repository operations |
| Validation | ✗ | ✓ (experiment exists, variant exists, belongs check) |
| Behavior | **Always raises ValueError** (line 517 in experiment_commands.py) | Actually removes variant |

**CRITICAL**: Path 1 is **non-functional** - it always raises:
```python
raise ValueError(
    "Removing models from experiments is not supported in TO-BE architecture. "
    "Variants are global and filtered at execution time via --models flag."
)
```

Path 2 actually performs the removal.

#### Risks:
1. **Command broken in main.py**: Users cannot remove models via the documented CLI
2. **Architecture inconsistency**: QWEN.md says variants are GLOBAL, but bcllm_model.py treats them as experiment-scoped

---

### 2.7 LIST-MODELS / SHOW-EXPERIMENT

#### Entry Points:

| Command | Path 1 (main.py) | Path 2 (Standalone) |
|---------|------------------|---------------------|
| list-models | `_handle_show_experiment()` → `_show_experiment_models()` | `handle_list_models()` in bcllm_model.py |
| show-experiment | `_handle_show_experiment()` | `handle_show_experiment()` in bcllm_experiment.py |

#### Behavior Divergence:

| Aspect | main.py | bcllm_model.py |
|--------|---------|----------------|
| Model scope | GLOBAL (`variant_repo.get_all()`) | Experiment-scoped (`list_by_experiment()`) |
| Output format | Rich Panel + Table | Plain text table |
| Config display | Shows reasoning/vision/structured flags | Shows full config JSON |

---

## 3. Comparison Tables

### 3.1 Configuration Resolution Order

| Command | Path | .env Source | CLI Precedence | Default Fallback |
|---------|------|-------------|----------------|------------------|
| create-experiment | main.py | `get_settings()` | Yes | None |
| create-experiment | bcllm_experiment.py | `ConfigResolver.load_env()` | Yes | NULL |
| add-model | main.py | `get_settings()` | Yes | NULL |
| add-model | bcllm_model.py | `ConfigResolver.load_env()` | Yes | NULL |
| create-run | main.py | `get_settings()` | Yes | None |
| create-run | bcllm_run.py | `ConfigResolver.load_env()` | Yes | NULL |

### 3.2 Validation Coverage

| Command | Path | Duplicate Check | Format Validation | Type Validation | Existence Check |
|---------|------|-----------------|-------------------|-----------------|-----------------|
| create-experiment | main.py | ✓ (name) | ✗ | ✗ | ✗ |
| create-experiment | bcllm_experiment.py | ✓ (name) | ✗ | ✓ (bool) | ✗ |
| add-model | main.py | ✗ | ✗ | ✗ | ✓ (exp) |
| add-model | bcllm_model.py | ✓ (signature) | ✓ (model ID) | ✓ (bool) | ✓ (exp) |
| add-questions | main.py | ✓ (idempotent) | ✗ | ✗ | ✓ (exp) |
| add-questions | bcllm_questions.py | ✓ (manual) | ✓ (spec) | ✓ (internal ID) | ✓ (exp) |
| create-run | main.py | ✗ | ✗ | ✗ | ✓ (exp) |
| create-run | bcllm_run.py | ✗ | ✗ | ✗ | ✓ (exp) |

### 3.3 Persistence Behavior

| Command | Path | Idempotency | Config Keys | Signature/Hash |
|---------|------|-------------|-------------|----------------|
| create-experiment | main.py | `create_if_not_exists()` | 14 | SHA-256 |
| create-experiment | bcllm_experiment.py | Manual check | 14 | SHA-256 |
| add-model | main.py | ✗ | 10 | variant_signature |
| add-model | bcllm_model.py | ✓ (signature check) | 10 | variant_signature |
| add-questions | main.py | `create_if_not_exists()` | N/A (payload) | N/A |
| add-questions | bcllm_questions.py | Manual check | N/A (payload) | N/A |
| create-run | main.py | ✗ | 3 | N/A |
| create-run | bcllm_run.py | ✗ | 3 | N/A |

---

## 4. Risk Assessment

### HIGH RISK - Commands with Multiple Active Paths

| Command | Risk Description | Impact |
|---------|------------------|--------|
| **create-experiment** | 3 paths with different validation, filtering, and config hash calculation | State inconsistency, hash mismatches between runs |
| **add-model** | 2 paths with different validation and architecture (GLOBAL vs experiment-scoped) | Duplicate variants, invalid configs persisted |
| **execute** | 2 paths with different API client, randomizer seeding, and filter validation | Execution failures, inconsistent results |
| **remove-model** | Path 1 is non-functional; Path 2 works but conflicts with architecture | User confusion, inability to manage variants |

### MEDIUM RISK

| Command | Risk Description | Impact |
|---------|------------------|--------|
| **add-questions** | Different filtering support and payload construction | Inconsistent question payloads |
| **create-run** | Seed AUTO resolution divergence (immediate vs deferred) | Different seeds for same run |
| **list-models** | Different scope (GLOBAL vs experiment-scoped) | Confusing user output |

### LOW RISK

| Command | Risk Description | Impact |
|---------|------------------|--------|
| **list-experiments** | Single path (main.py), standalone scripts don't implement | None |
| **show-run** | Single effective path | None |

---

## 5. Safe Commands (Single-Path)

The following commands have **single, authoritative entry points** and are considered safe:

| Command | Entry Point | File | Notes |
|---------|-------------|------|-------|
| `--review-experiment` | `handle_review_experiment()` | `bcllm_review.py` | Single standalone script |
| `--review-all` | `handle_review_all()` | `bcllm_review.py` | Single standalone script |
| `--list-experiments` | `handle_list_experiments()` | `bcllm_experiment.py` | Single standalone script |
| `--remove-experiment` | `handle_remove_experiment()` | `bcllm_experiment.py` | Single standalone script |
| `--remove-question` | `handle_remove_question()` | `bcllm_questions.py` | Single standalone script |
| `--remove-run` | `handle_remove_run()` | `bcllm_run.py` | Single standalone script |

**Note**: These commands are "safe" only in the sense that they have single entry points. They may still have other issues not covered by this audit.

---

## 6. Recommendations

### 6.1 Consolidation Priority

| Command | Consolidation Need | Recommended Action |
|---------|-------------------|-------------------|
| create-experiment | **REQUIRED** | Deprecate bcllm_experiment.py; route all through main.py → experiment_commands.py |
| add-model | **REQUIRED** | Deprecate bcllm_model.py; add validation to main.py path |
| execute | **REQUIRED** | Deprecate bcllm_execute.py; fix randomizer seeding in main.py |
| remove-model | **REQUIRED** | Implement functional removal or remove command entirely |
| add-questions | **OPTIONAL** | Add filtering support to main.py path |
| create-run | **OPTIONAL** | Align seed resolution between paths |
| list-models | **NOT NEEDED** | Document scope difference |

### 6.2 Specific Issues to Address

1. **Seed AUTO Resolution** (CRITICAL)
   - Path 2 (bcllm_run.py) resolves AUTO at creation time
   - Path 1/3 defer resolution
   - **Impact**: Same run could have different seeds depending on entry point

2. **Variant Architecture** (CRITICAL)
   - main.py treats variants as GLOBAL
   - bcllm_model.py treats variants as experiment-scoped
   - **Impact**: Database schema inconsistency, duplicate variants

3. **Validation Gaps** (HIGH)
   - main.py skips model ID format validation
   - main.py skips bool validation for vision/structured
   - **Impact**: Invalid data persisted

4. **Filter Support** (MEDIUM)
   - bcllm_questions.py supports `--where/--exclude`
   - main.py does not
   - **Impact**: Feature unavailable in documented CLI

5. **ResultWriter Divergence** (MEDIUM)
   - Different ResultWriter implementations in different files
   - **Impact**: `needs_review` calculation may differ

### 6.3 Architectural Recommendations

1. **Single Entry Point Policy**: All user-facing commands should route through `main.py`
2. **Deprecate Standalone Scripts**: `bcllm_*.py` scripts should be removed or converted to internal modules
3. **Validation Layer**: Centralize validation in a dedicated module
4. **Configuration Contract**: Enforce config key counts and names via validation
5. **Integration Tests**: Add tests that verify all entry points produce identical state

---

## 7. File Citation Index

| File | Purpose | Lines of Interest |
|------|---------|-------------------|
| `src/main.py` | Primary CLI entry point | 335-1000 (command handlers) |
| `src/cli/bcllm_experiment.py` | Standalone experiment CLI | 267-350 (create), 574-628 (show) |
| `src/cli/bcllm_model.py` | Standalone model CLI | 145-210 (add), 237-260 (remove) |
| `src/cli/bcllm_questions.py` | Standalone question CLI | 254-350 (add) |
| `src/cli/bcllm_run.py` | Standalone run CLI | 94-130 (create) |
| `src/cli/bcllm_execute.py` | Standalone execute CLI | 203-300 (execute) |
| `src/cli/experiment_commands.py` | Internal experiment logic | 104-190 (create), 425-520 (add-model) |
| `src/core/config_resolver.py` | Configuration resolution | 200-500 (resolution methods) |
| `src/core/planner.py` | Execution planning | 100-250 (build_plan) |
| `src/core/execution_engine.py` | Pure execution | 100-200 (execute) |
| `src/core/result_writer.py` | Result persistence | 80-180 (write_results) |
| `src/db/repository.py` | Database CRUD | All (repository implementations) |
| `src/db/schema.py` | Database schema | All (table definitions) |

---

## 8. Relationship to Previous Investigations

This global audit builds upon the `add-model-investigation.md` report and extends the analysis to ALL CLI commands. The findings confirm and expand:

1. **Entry Point Proliferation**: The dual-path pattern identified for `--add-model` exists across ALL commands
2. **Validation Inconsistency**: The null handling issues identified for `--add-model` are symptomatic of a broader validation layer fragmentation
3. **Signature Generation**: The `VariantConfig` vs `generate_variant_signature()` divergence affects multiple commands

---

**Audit Complete.** This report documents all observable entry points, execution flows, configuration resolution paths, validation behaviors, and persistence behaviors without proposing fixes or modifications.
