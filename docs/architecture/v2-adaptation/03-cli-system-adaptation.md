# CLI System V2 Adaptation Plan

**Document Type:** Adaptation Plan  
**Domain:** CLI System  
**Version:** 1.0  
**Date:** 2026-03-29  
**Status:** Actionable  

---

## 1. Overview

This document outlines the adaptation plan for the V2 CLI system, addressing gaps identified in the gap analysis and defining the migration path from V1 patterns to V2 architecture.

### 1.1 Current State Summary

**V2 Strengths:**
- ✅ Modular architecture (one file per command)
- ✅ Explicit null semantics (`EXPLICIT_NULL`)
- ✅ Configuration hierarchy (CLI > .env > NULL)
- ✅ Variant signatures for duplicate detection
- ✅ Advanced question filtering (nested fields)
- ✅ Repository pattern for data access

**V2 Gaps:**
- ❌ Missing commands: `--export-results`, `--add-to-run`, `--complete-run`, `--dry-run`
- ❌ No progress visibility during execution
- ❌ No initialization summary
- ❌ Minimal help text
- ❌ Console-only output (no JSON/CSV/Markdown)
- ❌ No Rich formatting

---

## 2. Current Command Coverage

### 2.1 Implemented Commands

| Module | Commands | Status |
|--------|----------|--------|
| **bcllm_experiment.py** | `--create-experiment`, `--experiment`, `--list-experiments`, `--remove-experiment` | ✅ Complete |
| **bcllm_model.py** | `--add-model`, `--list-models`, `--remove-model` | ✅ Complete |
| **bcllm_questions.py** | `--add-questions`, `--list-questions`, `--remove-question` | ✅ Complete |
| **bcllm_run.py** | `--add-run`, `--list-runs`, `--run`, `--remove-run` | ✅ Complete |
| **bcllm_execute.py** | `--execute` | ⚠️ Partial (missing filters, dry-run) |
| **bcllm_review.py** | `--review-experiment`, `--review-all` | ✅ Complete |

### 2.2 Missing Commands

| Command | Priority | Target Module | Effort |
|---------|----------|---------------|--------|
| `--export-results <run_id>` | High | `bcllm_execute.py` or new module | Medium |
| `--add-to-run <run_id> --add-models` | High | `bcllm_run.py` or `bcllm_model.py` | Medium |
| `--complete-run <run_id>` | High | `bcllm_run.py` | Low |
| `--dry-run` | Medium | `bcllm_execute.py` | Low |

---

## 3. Missing Commands Implementation Plan

### 3.1 GAP-001: Export Results

**Target:** `bcllm_execute.py` or new `bcllm_export.py`

**Specification:**
```bash
bcllm --export-results <run_id>
bcllm --experiment <name> --export-results <run_id> --output json
```

**Behavior:**
- Export final results for a run
- Use `manual_answer` when present, otherwise `selected_answer`
- Output format: JSON (default), CSV, Markdown
- Include: response_id, question_id, variant_id, model_id, iteration, answers, is_correct, latency, tokens

**Implementation:**
```python
def handle_export_results(args, conn) -> int:
    run_id = args.export_results
    
    # Fetch responses
    response_repo = ResponseRepository(conn)
    responses = response_repo.get_by_run(run_id)
    
    if not responses:
        print(f"No responses found for run {run_id}", file=sys.stderr)
        return 1
    
    # Build export data
    export_data = []
    for r in responses:
        final_answer = r.manual_answer if r.manual_answer else r.selected_answer
        answer_source = "manual" if r.manual_answer else "automatic"
        
        export_data.append({
            "response_id": r.response_id,
            "question_id": r.question_id,
            "variant_id": r.variant_id,
            "model_id": r.model_id,
            "iteration": r.iteration,
            "selected_answer": r.selected_answer,
            "manual_answer": r.manual_answer,
            "final_answer": final_answer,
            "answer_source": answer_source,
            "is_correct": r.is_correct,
            "parse_confidence": r.parse_confidence,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        })
    
    # Output
    output = {
        "run_id": run_id,
        "total_responses": len(responses),
        "manual_answers": sum(1 for r in responses if r.manual_answer),
        "automatic_answers": sum(1 for r in responses if not r.manual_answer),
        "responses": export_data,
    }
    
    print(json.dumps(output, indent=2, default=str))
    return 0
```

**Acceptance Criteria:**
- [ ] Exports all responses for a run
- [ ] Uses `manual_answer` when present
- [ ] Supports `--output json` (default), `--output csv`, `--output markdown`
- [ ] Includes all required fields
- [ ] Error on run not found

---

### 3.2 GAP-002: Add Models to Run

**Target:** `bcllm_run.py` or `bcllm_model.py`

**Specification:**
```bash
bcllm --add-to-run <run_id> --add-models <model1> <model2>
bcllm --experiment <name> --add-to-run <run_id> --add-models <model1>
```

**Behavior:**
- Add models to an existing run (run must be in 'running' status)
- Added models marked as 'pending'
- Existing models preserved
- Supports incremental benchmarking workflow

**Preconditions:**
- Run must exist
- Run status must be 'running' (not 'completed')
- Models must not already be in run

**Implementation:**
```python
def handle_add_to_run(args, conn) -> int:
    run_id = args.add_to_run
    model_ids = args.add_models
    
    # Validate run exists
    run_repo = RunRepository(conn)
    run = run_repo.get_by_id(run_id)
    if not run:
        print(f"Error: Run not found: {run_id}", file=sys.stderr)
        return 1
    
    # Validate run status
    if run.status != 'running':
        print(f"Error: Run '{run_id}' is not in 'running' status (current: {run.status})", file=sys.stderr)
        return 1
    
    # Add models to run
    run_model_repo = RunModelRepository(conn)
    added_count = 0
    
    for model_id in model_ids:
        # Check if model already in run
        existing = run_model_repo.get_by_run_and_model(run_id, model_id)
        if existing:
            print(f"Model '{model_id}' already in run '{run_id}' (skipped)")
            continue
        
        # Add model to run
        run_model_repo.add(run_id, model_id, status='pending')
        added_count += 1
        print(f"✓ Model '{model_id}' added to run '{run_id}'")
    
    print(f"\nSummary: {added_count} model(s) added to run '{run_id}'")
    return 0
```

**Acceptance Criteria:**
- [ ] Validates run exists
- [ ] Validates run status is 'running'
- [ ] Adds models as 'pending'
- [ ] Skips duplicate models
- [ ] Shows summary of added models

---

### 3.3 GAP-003: Complete Run

**Target:** `bcllm_run.py`

**Specification:**
```bash
bcllm --complete-run <run_id>
bcllm --experiment <name> --complete-run <run_id>
```

**Behavior:**
- Mark run as completed
- No more models can be added
- Changes status from 'running' to 'completed'

**Preconditions:**
- Run must exist
- Run status must be 'running' or 'partial_failed'

**Implementation:**
```python
def handle_complete_run(args, conn) -> int:
    run_id = args.complete_run
    
    # Validate run exists
    run_repo = RunRepository(conn)
    run = run_repo.get_by_id(run_id)
    if not run:
        print(f"Error: Run not found: {run_id}", file=sys.stderr)
        return 1
    
    # Validate run status
    if run.status not in ('running', 'partial_failed'):
        print(f"Error: Run '{run_id}' cannot be completed (current status: {run.status})", file=sys.stderr)
        return 1
    
    # Update status
    run_repo.update_status(run_id, 'completed')
    print(f"✓ Run '{run_id}' marked as completed")
    print(f"  No more models can be added to this run.")
    return 0
```

**Acceptance Criteria:**
- [ ] Validates run exists
- [ ] Validates run can be completed
- [ ] Updates status to 'completed'
- [ ] Shows confirmation message

---

### 3.4 GAP-004: Dry Run

**Target:** `bcllm_execute.py`

**Specification:**
```bash
bcllm --experiment <name> --execute --dry-run
```

**Behavior:**
- Validate configuration without executing
- Check experiment exists
- Check run exists (if specified)
- Check models exist
- Check questions exist
- Build execution plan (don't execute)
- Show what would be executed

**Implementation:**
```python
def handle_execute(args, conn) -> int:
    # ... existing validation ...
    
    # Check dry run
    if args.dry_run:
        print("Dry run mode - validation only")
        
        # Build plan to show what would be executed
        planner = Planner(conn)
        plan = planner.build_plan(
            args.experiment,
            run_ids=[run_id] if run_id else None,
            question_ids=question_ids,
            model_variant_ids=model_variant_ids,
        )
        
        # Show summary
        total_items = sum(len(run.items) for run in plan.runs)
        print(f"\nConfiguration validated successfully.")
        print(f"  Would execute: {total_items} items")
        print(f"  Runs: {len(plan.runs)}")
        for run_plan in plan.runs:
            print(f"    - {run_plan.run_id}: {len(run_plan.items)} items")
        
        return 0
    
    # ... normal execution ...
```

**Acceptance Criteria:**
- [ ] Validates all configuration
- [ ] Builds execution plan (doesn't execute)
- [ ] Shows what would be executed
- [ ] Returns 0 on successful validation
- [ ] Returns 1 on validation error

---

## 4. UX Improvements Plan

### 4.1 RISK-001: Progress Visibility

**Target:** `bcllm_execute.py`

**Specification:**
- Rich progress bar during execution
- ETA calculation
- Milestone logging (25%, 50%, 75%, 100%)
- Item-level completion logging

**Implementation:**
```python
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, MofNCompleteColumn

# In handle_execute:
with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeRemainingColumn(),
) as progress:
    task = progress.add_task("Benchmark Execution", total=total_items)
    
    for item in items:
        # Execute item
        result = engine.execute_item(item)
        
        # Update progress
        progress.update(task, advance=1)
        
        # Log milestone
        current = progress.tasks[task].completed
        if current % (total_items // 4) == 0:
            percent = (current / total_items) * 100
            print(f"Progress: {current}/{total_items} ({percent:.1f}%)")
```

**Acceptance Criteria:**
- [ ] Progress bar displayed during execution
- [ ] ETA shown and updated
- [ ] Milestones logged at 25% intervals
- [ ] Item completion logged

---

### 4.2 RISK-002: Initialization Summary

**Target:** `bcllm_execute.py`

**Specification:**
- Fixed-width header before execution
- Show experiment, run, models, questions, configuration
- Clear "what will run" summary

**Implementation:**
```python
def print_initialization_summary(experiment, run, plan):
    print("=" * 60)
    print("Benchmark LLM - Initialization")
    print("=" * 60)
    print(f"Experiment          : {experiment.name}")
    print(f"Run                 : {run.run_id}")
    print(f"Configuration Hash  : {experiment.config_hash}")
    
    total_items = sum(len(run.items) for run in plan.runs)
    print(f"Total Items         : {total_items}")
    print(f"Runs                : {len(plan.runs)}")
    
    for run_plan in plan.runs:
        print(f"  - {run_plan.run_id}: {len(run_plan.items)} items")
    
    print("=" * 60)
```

**Acceptance Criteria:**
- [ ] Summary printed before execution
- [ ] Shows experiment name, run ID, config hash
- [ ] Shows total items to execute
- [ ] Clear, scannable format

---

### 4.3 RISK-003: Output Format Options

**Target:** `bcllm_execute.py` or shared `output_formatter.py`

**Specification:**
- `--output console` (default) — Rich table
- `--output json` — JSON export
- `--output csv` — CSV export
- `--output markdown` — Markdown table

**Implementation:**
Reuse V1 `OutputFormatter` class from `src_legacy/cli/output_formatter.py`:
```python
from src.cli.output_formatter import create_formatter

formatter = create_formatter(args.output)

if args.output == 'json':
    print(formatter.to_json(statistics))
elif args.output == 'csv':
    print(formatter.to_csv(statistics))
elif args.output == 'markdown':
    print(formatter.to_markdown(statistics))
else:
    formatter.display_table(statistics)
```

**Acceptance Criteria:**
- [ ] Supports console, json, csv, markdown
- [ ] Default is console
- [ ] Consistent output across formats

---

### 4.4 RISK-006: Enhanced Help Text

**Target:** All CLI modules

**Specification:**
- Add epilog with 5+ examples per module
- Include scenario-based workflows
- Add inline comments explaining behavior
- Show valid values for all flags

**Example (bcllm_experiment.py):**
```python
parser = argparse.ArgumentParser(
    prog="bcllm_experiment.py",
    description="Experiment lifecycle management",
    epilog="""
Examples:
  # Create experiment with questions 1-10
  %(prog)s --create-experiment my_exp --add-questions 1-10

  # Create experiment with specific questions
  %(prog)s --create-experiment my_exp --add-questions "1, 3, 5"

  # Create experiment with AUTO seed
  %(prog)s --create-experiment my_exp --seed AUTO

  # View experiment details
  %(prog)s --experiment my_exp

  # Add models to existing experiment
  %(prog)s --experiment my_exp --add-model google/gemini-3.1-flash-lite-preview

  # List all experiments
  %(prog)s --list-experiments
    """,
)
```

**Acceptance Criteria:**
- [ ] All modules have epilog with examples
- [ ] Examples are copy-paste ready
- [ ] Valid values shown for all flags
- [ ] Scenario-based workflows included

---

## 5. Documentation Plan

### 5.1 DOC-001: Dispatcher Implementation

**Target:** `docs/architecture/v2-current/dispatcher.md`

**Content:**
- How `bcllm` command invokes modules
- Mode determination logic
- Argument forwarding mechanism
- File structure

**Outline:**
```markdown
# CLI Dispatcher

## Overview
How the `bcllm` command invokes individual modules.

## Dispatch Mechanism
[Document wrapper script or entry point]

## Mode Routing
How mode is determined and passed to modules.

## Argument Forwarding
How arguments are forwarded to modules.
```

---

### 5.2 DOC-002: Mode System

**Target:** `docs/architecture/v2-current/mode-system.md`

**Content:**
- Mode enum definition
- Mode validation pattern
- Mode expectations per module
- Error handling for invalid modes

**Outline:**
```markdown
# Mode System

## Mode Enum
CREATE, MODIFY, EXECUTE, INVALID

## Validation Pattern
_validate_expected_mode() function

## Mode by Module
Table of expected modes per module

## Error Handling
What happens on mode mismatch
```

---

### 5.3 DOC-003: Configuration Reference

**Target:** `docs/architecture/contracts/configuration-reference.md`

**Content:**
- Complete list of configuration keys
- Hierarchy for each key
- Null semantics behavior
- Default values

**Outline:**
```markdown
# Configuration Reference

## Experiment Configuration
- seed
- system_prompt
- user_prompt
- [all keys with hierarchy]

## Model Configuration
- url
- max_reasoning
- max_tokens
- reasoning_effort
- [all keys with hierarchy]

## Run Configuration
- seed
- system_prompt
- user_prompt
- [all keys with hierarchy]

## Null Semantics
How null is handled for each key
```

---

## 6. Migration Timeline

### Phase 1: Critical Regressions (Week 1-2)

**Goals:**
- Restore missing commands
- Enable incremental workflow

**Tasks:**
- [ ] Implement `--export-results` (GAP-001)
- [ ] Implement `--add-to-run` (GAP-002)
- [ ] Implement `--complete-run` (GAP-003)
- [ ] Test all new commands

**Success Criteria:**
- All V1 commands have V2 equivalent
- Incremental workflow works
- Results can be exported

---

### Phase 2: UX Improvements (Week 3-4)

**Goals:**
- Restore progress visibility
- Improve user feedback

**Tasks:**
- [ ] Implement `--dry-run` (GAP-004)
- [ ] Add progress bar to execution (RISK-001)
- [ ] Add initialization summary (RISK-002)
- [ ] Add output format options (RISK-003)
- [ ] Enhance help text (RISK-006)

**Success Criteria:**
- Users can validate before executing
- Progress visible during execution
- Multiple output formats available
- Help text is comprehensive

---

### Phase 3: Documentation (Week 5-6)

**Goals:**
- Document architecture
- Create configuration reference

**Tasks:**
- [ ] Document dispatcher (DOC-001)
- [ ] Document mode system (DOC-002)
- [ ] Create configuration reference (DOC-003)
- [ ] Document repository interface (DOC-005)

**Success Criteria:**
- Developers can understand dispatch logic
- Configuration keys are documented
- Repository methods are documented

---

## 7. Validation Criteria

### 7.1 Command Coverage

**Target:** 100% V1 command parity

| Command | Status | Validation |
|---------|--------|------------|
| `--export-results` | ❌ → ✅ | Export JSON for run |
| `--add-to-run` | ❌ → ✅ | Add models to running run |
| `--complete-run` | ❌ → ✅ | Complete run, prevent additions |
| `--dry-run` | ❌ → ✅ | Validate without executing |

### 7.2 UX Features

**Target:** Restore critical UX features

| Feature | Status | Validation |
|---------|--------|------------|
| Progress Bar | ❌ → ✅ | Visible during execution |
| Initialization Summary | ❌ → ✅ | Printed before execution |
| Output Formats | ❌ → ✅ | JSON, CSV, Markdown work |
| Help Examples | ❌ → ✅ | 5+ examples per module |

### 7.3 Documentation

**Target:** Complete architecture documentation

| Document | Status | Validation |
|----------|--------|------------|
| Dispatcher | ❌ → ✅ | Document created |
| Mode System | ❌ → ✅ | Document created |
| Configuration Reference | ❌ → ✅ | Document created |
| Repository Interface | ❌ → ✅ | Document created |

---

## 8. Risk Mitigation

### 8.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking changes | Low | High | Backward-compatible implementations |
| Performance regression | Low | Medium | Benchmark before/after |
| Rich dependency issues | Medium | Low | Optional Rich, fallback to plain text |

### 8.2 UX Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Users confused by changes | Medium | Medium | Clear migration guide, help text |
| Missing muscle memory commands | High | High | Implement all V1 commands first |
| Documentation lag | Medium | Medium | Documentation as part of Definition of Done |

---

## 9. Success Metrics

### 9.1 Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Command parity | 100% | V1 vs V2 command count |
| Test coverage | 80%+ | Unit test coverage |
| Help text examples | 5+ per module | Count examples |
| Documentation pages | 4 new | Count new docs |

### 9.2 Qualitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| User satisfaction | Improved | User feedback |
| Developer onboarding | Faster | Time to first contribution |
| Support burden | Reduced | Issue count |

---

## 10. Conclusion

This adaptation plan addresses the gaps between V1 and V2 CLI systems:

**Phase 1 (Critical):** Restore missing commands to enable full workflow
**Phase 2 (UX):** Improve user experience with progress, summaries, formats
**Phase 3 (Docs):** Document architecture for maintainability

**Success = V1 parity + V2 improvements + complete documentation**

---

**All 5 CLI System documents completed:**
1. ✅ `docs/architecture/legacy-analysis/03-cli-system.md` — V1 Analysis
2. ✅ `docs/architecture/v2-current/03-cli-system.md` — V2 Current State
3. ✅ `docs/architecture/gap-reports/03-cli-system-gap.md` — Gap Report
4. ✅ `docs/architecture/to-be/03-cli-system-architecture.md` — Architecture & Contracts
5. ✅ `docs/architecture/v2-adaptation/03-cli-system-adaptation.md` — V2 Adaptation Plan
