# CLI System Gap Analysis

**Document Type:** Gap Report  
**Domain:** CLI System  
**Version:** 1.0  
**Date:** 2026-03-29  
**Status:** Actionable  

---

## 1. Executive Summary

This gap analysis compares the V1 legacy CLI system with the V2 current implementation, identifying:
- **Commands missing in V2** (regressions)
- **Commands improved in V2** (enhancements)
- **Features lost in migration** (regression risks)
- **Documentation gaps** (missing specifications)

### 1.1 Summary Matrix

| Category | Count | Severity |
|----------|-------|----------|
| Commands Missing in V2 | 4 | High |
| Commands Improved in V2 | 8 | Medium |
| Regression Risks | 6 | High |
| Documentation Gaps | 5 | Medium |

---

## 2. Commands Missing in V2

### 2.1 High Priority Regressions

#### GAP-001: Export Results Command

**V1 Command:**
```bash
bcllm --export-results <run_id>
```

**Purpose:** Export final results for a run, using `manual_answer` when present, otherwise `selected_answer`.

**V1 Implementation:**
- Located in `src_legacy/main.py:_handle_export_results()`
- Outputs JSON with response details including:
  - `selected_answer`, `manual_answer`, `final_answer`, `answer_source`
  - `is_correct`, `parse_confidence`, `latency_ms`, token counts
- Supports scripting and external analysis

**V2 Status:** ❌ Not implemented

**Impact:**
- Users cannot export results for external analysis
- No integration with reporting tools
- Manual database queries required

**Recommendation:** Implement in `bcllm_execute.py` or new `bcllm_export.py`

---

#### GAP-002: Add Models to Run Command

**V1 Command:**
```bash
bcllm --add-to-run <run_id> --add-models <model1> <model2>
```

**Purpose:** Add models to an existing run (run must be in 'running' status).

**V1 Implementation:**
- Located in `src_legacy/main.py:_handle_add_models_to_run()`
- Supports incremental benchmarking workflow
- Added models marked as 'pending', existing models preserved

**V2 Status:** ❌ Not implemented

**Impact:**
- Cannot add models to existing runs
- Must create new experiment/run for additional models
- Breaks multi-day benchmarking workflow

**Recommendation:** Implement in `bcllm_run.py` or `bcllm_model.py`

---

#### GAP-003: Complete Run Command

**V1 Command:**
```bash
bcllm --complete-run <run_id>
```

**Purpose:** Mark a run as completed. No more models can be added after this.

**V1 Implementation:**
- Located in `src_legacy/main.py:_handle_complete_run()`
- Changes run status from 'running' to 'completed'
- Prevents further model additions

**V2 Status:** ❌ Not implemented

**Impact:**
- No explicit run completion signal
- Cannot enforce "no more models" constraint
- Run lifecycle incomplete

**Recommendation:** Implement in `bcllm_run.py`

---

#### GAP-004: Dry Run Command

**V1 Command:**
```bash
bcllm --dry-run
```

**Purpose:** Validate configuration without executing benchmark.

**V1 Implementation:**
- Located in `src_legacy/main.py:run()`
- Validates configuration, database, models
- Returns early before execution
- Message: `Configuration validated successfully (dry run)`

**V2 Status:** ❌ Not implemented

**Impact:**
- Cannot validate configuration before long runs
- Must execute to verify setup
- Risk of wasted API calls on misconfiguration

**Recommendation:** Implement in `bcllm_execute.py`

---

### 2.2 Summary Table

| GAP ID | Command | V1 Location | V2 Status | Priority |
|--------|---------|-------------|-----------|----------|
| GAP-001 | `--export-results` | `main.py:_handle_export_results()` | ❌ Missing | High |
| GAP-002 | `--add-to-run` + `--add-models` | `main.py:_handle_add_models_to_run()` | ❌ Missing | High |
| GAP-003 | `--complete-run` | `main.py:_handle_complete_run()` | ❌ Missing | High |
| GAP-004 | `--dry-run` | `main.py:run()` | ❌ Missing | Medium |

---

## 3. Commands Improved in V2

### 3.1 Enhancements

#### IMP-001: Null Semantics

**V1 Behavior:**
- No distinction between "not set" and "explicitly null"
- `None` always fell back to .env or default

**V2 Enhancement:**
- `EXPLICIT_NULL` constant distinguishes explicit null from absent
- `--seed null` forces system default (skips .env)
- `--seed` (not provided) uses .env fallback

**Impact:** Higher
- Users can explicitly override .env defaults
- Clearer configuration intent

---

#### IMP-002: Variant Signatures

**V1 Behavior:**
- Model variants identified by generated IDs
- No duplicate detection based on configuration

**V2 Enhancement:**
- `generate_variant_signature(model_id, config)` creates unique signature
- Duplicate detection prevents identical variants
- Signature includes all configuration parameters

**Impact:** Medium
- Prevents accidental duplicate variants
- Enables configuration comparison

---

#### IMP-003: Question Spec Parsing

**V1 Behavior:**
- Basic range expansion: `Q001-Q010`
- Comma-separated: `Q001,Q002,Q003`

**V2 Enhancement:**
- Mixed formats: `"1, 3-5, Q010"`
- Internal ID assignment via `QuestionLoader.assign_internal_ids()`
- Better error messages for invalid specs

**Impact:** Medium
- More flexible question selection
- Better UX for partial question sets

---

#### IMP-004: Metadata Filtering

**V1 Behavior:**
- Basic `--where` and `--exclude` filters
- Flat field access only

**V2 Enhancement:**
- Nested field access: `--where meta.status=valid`
- Multiple filters: `--where status=valid has_image=false`
- `_get_nested_field()` supports dot notation

**Impact:** Medium
- More precise question filtering
- Supports complex metadata structures

---

#### IMP-005: Modular Architecture

**V1 Behavior:**
- Monolithic `main.py` (1379 lines)
- All routing in single file
- Hard to test individual commands

**V2 Enhancement:**
- One file per command domain
- Self-contained modules with own parsers
- Clear mode-based routing

**Impact:** High
- Easier maintenance
- Better testability
- Clearer responsibilities

---

#### IMP-006: Configuration Hierarchy

**V1 Behavior:**
- CLI > .env > default
- Feedback provided but implementation coupled

**V2 Enhancement:**
- `ConfigResolver` class encapsulates hierarchy
- Explicit NULL handling
- Configuration dict building per entity type

**Impact:** Medium
- Clearer separation of concerns
- Easier to extend

---

#### IMP-007: Database Connection Management

**V1 Behavior:**
- Connection management scattered across modules
- Schema initialization in multiple places

**V2 Enhancement:**
- Centralized `get_database_connection()` in `database.py`
- Persistent database file (`./data/bcllm.db`)
- Idempotent schema initialization
- Foreign keys enabled

**Impact:** Medium
- Consistent connection handling
- Better resource management

---

#### IMP-008: Repository Pattern

**V1 Behavior:**
- Direct database access in command handlers
- SQL queries inline with business logic

**V2 Enhancement:**
- Repository classes (`ExperimentRepository`, `VariantRepository`, etc.)
- Clean separation of data access and business logic
- Consistent CRUD interface

**Impact:** Medium
- Better testability
- Easier to swap database implementations

---

### 3.2 Summary Table

| IMP ID | Enhancement | Impact | V2 Module |
|--------|-------------|--------|-----------|
| IMP-001 | Null Semantics (`EXPLICIT_NULL`) | High | `null_semantics.py` |
| IMP-002 | Variant Signatures | Medium | `variant_signature.py` |
| IMP-003 | Question Spec Parsing | Medium | `QuestionLoader` |
| IMP-004 | Metadata Filtering (nested) | Medium | `bcllm_questions.py` |
| IMP-005 | Modular Architecture | High | All modules |
| IMP-006 | ConfigResolver | Medium | `config_resolver.py` |
| IMP-007 | Database Connection | Medium | `database.py` |
| IMP-008 | Repository Pattern | Medium | `repository.py` |

---

## 4. Regression Risks

### 4.1 High Priority Risks

#### RISK-001: No Progress Visibility

**V1 Feature:**
- Rich progress bar with ETA
- Milestone logging (25%, 50%, 75%, 100%)
- Item-level completion logging

**V2 Status:** ❌ Missing

**Risk:**
- Users have no visibility during long executions
- Cannot estimate completion time
- May interrupt thinking execution is stuck

**Mitigation:** Implement Rich progress in `bcllm_execute.py`

---

#### RISK-002: No Initialization Summary

**V1 Feature:**
```
============================================================
Benchmark LLM - Initialization
============================================================
Execution mode      : EXPERIMENT MODE
Experiment          : test_exp
Persist data        : YES
Configuration       : FROZEN (config_hash=8f3a9c2e)
System prompt       : You are a helpful assistant.
Seed                : 42
Models              : openai/gpt-4, anthropic/claude-3
Questions           : Q001-Q010 (10 questions)
============================================================
```

**V2 Status:** ❌ Missing

**Risk:**
- Users cannot verify configuration before execution
- No clear summary of what will run
- Increased risk of misconfiguration

**Mitigation:** Add initialization summary to `bcllm_execute.py`

---

#### RISK-003: No Output Format Options

**V1 Feature:**
- `--output console` (Rich table)
- `--output json` (JSON export)
- `--output csv` (CSV export)
- `--output markdown` (Markdown table)

**V2 Status:** ❌ Console only

**Risk:**
- Cannot export results in different formats
- No scripting integration
- Manual post-processing required

**Mitigation:** Implement `OutputFormatter` in V2 (can reuse V1 logic)

---

#### RISK-004: No Rich Formatting

**V1 Feature:**
- Colored output (green success, red errors)
- Tables with borders
- Panels for important information
- Progress bars

**V2 Status:** ❌ Plain text only

**Risk:**
- Poor user experience
- Harder to scan output
- Less professional appearance

**Mitigation:** Reintroduce Rich library selectively

---

#### RISK-005: Incomplete Run Lifecycle

**V1 Feature:**
- Run states: `pending` → `running` → `completed`
- `--complete-run` to finalize
- `--add-to-run` for incremental additions

**V2 Status:** ⚠️ Partial (no complete/add commands)

**Risk:**
- Runs cannot be explicitly completed
- Incremental workflow broken
- Lifecycle management incomplete

**Mitigation:** Implement missing run lifecycle commands

---

#### RISK-006: Minimal Help Text

**V1 Feature:**
- Extensive epilog with 15+ examples
- Scenario-based workflows ("Day 1, Day 2, Day 3")
- Inline comments explaining behavior

**V2 Status:** ⚠️ Minimal help text

**Risk:**
- Users don't know how to use commands
- No copy-paste examples
- Higher support burden

**Mitigation:** Enhance help text in all modules

---

### 4.2 Summary Table

| Risk ID | Feature Lost | Impact | Mitigation Priority |
|---------|--------------|--------|---------------------|
| RISK-001 | Progress Visibility | High | High |
| RISK-002 | Initialization Summary | High | High |
| RISK-003 | Output Format Options | Medium | Medium |
| RISK-004 | Rich Formatting | Medium | Low |
| RISK-005 | Run Lifecycle | High | High |
| RISK-006 | Help Text | Medium | Medium |

---

## 5. Documentation Gaps

### 6.1 Missing Specifications

#### DOC-001: Dispatcher Implementation

**Gap:** How `bcllm` command invokes individual modules is undocumented.

**Questions:**
- Is there a wrapper script?
- How is mode determined and passed?
- How are arguments forwarded?

**Impact:** Developers cannot understand or modify dispatch logic.

**Recommendation:** Document dispatcher in `docs/architecture/v2-current/`.

---

#### DOC-002: Mode System

**Gap:** Mode routing (`CREATE`, `MODIFY`, `EXECUTE`, `INVALID`) not fully documented.

**Questions:**
- How does dispatcher know which mode to pass?
- What happens if wrong mode is passed?
- Can modules handle multiple modes?

**Impact:** Mode validation appears magical.

**Recommendation:** Document mode system in architecture doc.

---

#### DOC-003: Configuration Keys

**Gap:** Complete list of configuration keys not documented.

**V1:** Had implicit documentation via argparse help.

**V2:** Configuration built via `ConfigResolver.build_*_dict()` but keys not listed.

**Impact:** Users don't know all available configuration options.

**Recommendation:** Document all configuration keys with hierarchy.

---

#### DOC-004: Error Messages

**Gap:** No error message specification or style guide.

**V1:** Had inconsistent guidance but dual-channel output.

**V2:** Plain stderr output, no style guide.

**Impact:** Inconsistent error messages across modules.

**Recommendation:** Create error message style guide.

---

#### DOC-005: Repository Interface

**Gap:** Repository methods not documented.

**V1:** Direct SQL queries visible in command handlers.

**V2:** Repository pattern abstracts SQL, but interface not documented.

**Impact:** Developers don't know available repository methods.

**Recommendation:** Document repository interface in `docs/architecture/contracts/`.

---

### 5.2 Summary Table

| Doc ID | Gap | Impact | Recommendation |
|--------|-----|--------|----------------|
| DOC-001 | Dispatcher Implementation | High | Document in v2-current |
| DOC-002 | Mode System | Medium | Document in architecture |
| DOC-003 | Configuration Keys | Medium | Create config reference |
| DOC-004 | Error Messages | Low | Create style guide |
| DOC-005 | Repository Interface | Medium | Document in contracts |

---

## 6. Command Coverage Matrix

### 6.1 Full Comparison

| Command Category | V1 Command | V2 Command | Status | Notes |
|------------------|------------|------------|--------|-------|
| **EXPERIMENTS** | | | | |
| Create | `--create-experiment <name>` | `--create-experiment <name>` | ✅ Parity | V2 has better null semantics |
| Show | `--experiment <name>` | `--experiment <name>` | ✅ Parity | Similar output |
| List | (via `--experiment`) | `--list-experiments` | ✅ Improved | Dedicated command |
| Remove | (not in V1) | `--remove-experiment <name>` | ✅ New | Soft delete |
| **MODELS** | | | | |
| Add | `--add-model <model>` | `--add-model <model_id>` | ✅ Parity | V2 has variant signatures |
| List | (in experiment view) | `--list-models` | ✅ Improved | Dedicated command |
| Remove | `--remove-model <model_id>` | `--remove-model <variant_id>` | ✅ Parity | V2 uses variant_id |
| Add to Run | `--add-to-run <run> --add-models` | ❌ Missing | ⚠️ Regression | GAP-002 |
| **QUESTIONS** | | | | |
| Add | `--add-questions <spec>` | `--add-questions <spec>` | ✅ Parity | V2 has better filtering |
| List | (in experiment view) | `--list-questions` | ✅ Improved | Dedicated command |
| Remove | (not in V1) | `--remove-question <snapshot_id>` | ✅ New | Soft delete |
| **RUNS** | | | | |
| Create | `--create-run` | `--add-run` | ✅ Parity | Renamed flag |
| List | (in experiment view) | `--list-runs` | ✅ Improved | Dedicated command |
| Show | `--run <run_name>` | `--run <run_id>` | ✅ Parity | Similar output |
| Remove | (not in V1) | `--remove-run <run_id>` | ✅ New | Soft delete |
| Complete | `--complete-run <run_id>` | ❌ Missing | ⚠️ Regression | GAP-003 |
| **EXECUTION** | | | | |
| Execute | `--run <name> --execute` | `--execute` | ✅ Improved | Standalone command |
| Dry Run | `--dry-run` | ❌ Missing | ⚠️ Regression | GAP-004 |
| **REVIEW** | | | | |
| Review Experiment | `--review-experiment <name>` | `--review-experiment <name>` | ✅ Parity | Same UI |
| Review All | `--review-all` | `--review-all` | ✅ Parity | Same UI |
| **EXPORT** | | | | |
| Export Results | `--export-results <run_id>` | ❌ Missing | ⚠️ Regression | GAP-001 |
| **OUTPUT** | | | | |
| Output Format | `--output console/json/csv/markdown` | ❌ Console only | ⚠️ Regression | RISK-003 |
| Output File | `--output-file <path>` | ❌ Missing | ⚠️ Regression | |

### 6.2 Coverage Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| Total V1 Commands | 24 | 100% |
| V2 Parity or Better | 18 | 75% |
| V2 Missing (Regressions) | 6 | 25% |
| V2 New Features | 4 | N/A |

---

## 7. Feature Coverage Matrix

### 7.1 UX Features

| Feature | V1 | V2 | Status |
|---------|-----|-----|--------|
| **Progress Bar** | ✅ Rich progress | ❌ Missing | ⚠️ Regression |
| **ETA Calculation** | ✅ Time remaining | ❌ Missing | ⚠️ Regression |
| **Milestone Logging** | ✅ 25%, 50%, 75%, 100% | ❌ Missing | ⚠️ Regression |
| **Initialization Summary** | ✅ Fixed-width header | ❌ Missing | ⚠️ Regression |
| **Rich Tables** | ✅ Bordered tables | ❌ Plain text | ⚠️ Regression |
| **Colored Output** | ✅ Green/Red/Yellow | ❌ Plain text | ⚠️ Regression |
| **Panels** | ✅ Bordered panels | ❌ Missing | ⚠️ Regression |
| **Help Examples** | ✅ 15+ examples | ⚠️ Minimal | ⚠️ Regression |

### 7.2 Technical Features

| Feature | V1 | V2 | Status |
|---------|-----|-----|--------|
| **Null Semantics** | ⚠️ Basic | ✅ `EXPLICIT_NULL` | ✅ Improved |
| **Configuration Hierarchy** | ✅ CLI > .env > default | ✅ CLI > .env > NULL | ✅ Improved |
| **Variant Signatures** | ❌ No | ✅ Yes | ✅ New |
| **Question Filtering** | ⚠️ Basic | ✅ Nested fields | ✅ Improved |
| **Retry Policy** | ✅ Per-experiment | ✅ Per-execution | ✅ Improved |
| **Repository Pattern** | ❌ No | ✅ Yes | ✅ New |
| **Modular Architecture** | ❌ Monolithic | ✅ Modular | ✅ Improved |
| **Persistent Database** | ✅ Yes | ✅ Yes | ✅ Parity |

---

## 8. Recommendations

### 8.1 High Priority (Blockers)

1. **Implement `--export-results`** (GAP-001)
   - Critical for data analysis
   - Can reuse V1 implementation logic
   - Add to `bcllm_execute.py` or new module

2. **Implement `--add-to-run` and `--complete-run`** (GAP-002, GAP-003)
   - Critical for incremental workflow
   - Required for multi-day benchmarking
   - Add to `bcllm_run.py`

3. **Add Progress Visibility** (RISK-001)
   - Reintroduce Rich progress bar
   - Add milestone logging
   - Implement in `bcllm_execute.py`

4. **Add Initialization Summary** (RISK-002)
   - Fixed-width configuration summary
   - Show before execution
   - Implement in `bcllm_execute.py`

### 8.2 Medium Priority

5. **Implement `--dry-run`** (GAP-004)
   - Validation without execution
   - Prevents wasted API calls
   - Add to `bcllm_execute.py`

6. **Add Output Format Options** (RISK-003)
   - Reuse V1 `OutputFormatter` class
   - Support JSON, CSV, Markdown
   - Add `--output` flag to relevant commands

7. **Enhance Help Text** (RISK-006)
   - Add epilog with examples to all modules
   - Include scenario-based workflows
   - Follow V1 pattern

### 8.3 Low Priority

8. **Reintroduce Rich Formatting** (RISK-004)
   - Optional enhancement
   - Can use plain text for scripting mode
   - Rich for interactive mode

9. **Document Dispatcher** (DOC-001)
   - Document how `bcllm` invokes modules
   - Include mode routing logic
   - Add to `docs/architecture/v2-current/`

10. **Create Configuration Reference** (DOC-003)
    - List all configuration keys
    - Document hierarchy for each
    - Include null semantics behavior

---

## 9. Migration Plan

### Phase 1: Critical Regressions (Week 1-2)
- [ ] Implement `--export-results`
- [ ] Implement `--add-to-run` and `--complete-run`
- [ ] Add progress bar to execution
- [ ] Add initialization summary

### Phase 2: UX Improvements (Week 3-4)
- [ ] Implement `--dry-run`
- [ ] Add output format options
- [ ] Enhance help text with examples
- [ ] Add Rich formatting (optional)

### Phase 3: Documentation (Week 5-6)
- [ ] Document dispatcher implementation
- [ ] Document mode system
- [ ] Create configuration reference
- [ ] Document repository interface

---

## 10. Conclusion

The V2 CLI system has **strong architectural foundations** (modular design, null semantics, repository pattern) but has **lost critical UX features** from V1 (progress visibility, export, incremental workflow).

**Priority Focus:**
1. Restore missing commands (export, add-to-run, complete-run, dry-run)
2. Restore progress visibility and initialization summary
3. Enhance documentation (dispatcher, configuration, repositories)

**Risk if Not Addressed:**
- Users cannot complete multi-day benchmarks
- No visibility during long executions
- Cannot export results for analysis
- Higher support burden due to minimal help text

---

**Next Document:** `docs/architecture/to-be/03-cli-system-architecture.md` — Architecture & Contracts
