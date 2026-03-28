# Legacy UX Analysis

**Document Type:** UX Architectural Extraction (Read-Only)  
**Source:** `src_legacy/` directory  
**Focus:** CLI interaction, user feedback, and experience  
**Purpose:** Document the user experience for historical reference

---

## 1. CLI Interaction Patterns

### 1.1 Command Structure Philosophy

The legacy system employed a **hybrid CLI paradigm** that evolved over time:

**Original Pattern (Direct Execution):**
- Single-command execution: `--models`, `--iterations`, `--questions`
- Immediate execution upon invocation
- All configuration via flags
- No state persistence between runs

**Evolved Pattern (Experiment-Based):**
- Two-phase workflow: Create experiment → Create run → Execute
- Explicit context requirement: `--experiment <name>` for operations
- Stateful operations with database persistence
- Incremental model addition supported

**Command Help as Documentation:**
- Extensive epilog with copy-paste examples
- Scenario-based documentation (Day 1, Day 2, Day 3 workflows)
- Inline comments explaining behavior ("Completed models are automatically skipped")
- Multiple examples covering common use cases

### 1.2 How Commands Guided Users

**Progressive Disclosure:**
- Basic commands shown first in help
- Advanced options (reasoning parameters, vision, structured outputs) documented separately
- Incremental flow examples showed multi-day workflows explicitly

**Context Requirements:**
- Operation commands required `--experiment` context
- Error messages explicitly stated missing context:
  - "`--add-model` requires `--experiment <name>`"
  - "Example: `--experiment my_exp --add-model`"

**Default Behavior Transparency:**
- Configuration hierarchy module provided explicit feedback:
  - CLI values: No feedback (user was explicit)
  - Environment values: "using default from environment (.env)"
  - Internal defaults: "using all available questions (default)"

**Example Guidance Pattern:**
```
Questions: using all available questions from dataset (default)
Seed: using default from environment (.env)
```

### 1.3 Error Communication

**Error Message Structure:**

| Component | Format | Example |
|-----------|--------|---------|
| Error prefix | `[red]Error: [/red]` (Rich) or `Error: ` (plain) | `Error: Experiment 'test_exp' already exists` |
| Context | What was being done | `Create experiment failed: ...` |
| Cause | Specific error | `Experiment 'test_exp' already exists` |
| Guidance | How to fix (when applicable) | `Use --remove-model <ids> or --remove-model ? for assisted mode` |

**Error Output Channels:**
- Rich console output (colored) for interactive commands
- Plain stderr output for script-friendly error handling
- Both channels used simultaneously in many cases

**Error Categorization:**
- **ValueError**: User input errors (red, user-friendly)
- **Exception**: System errors (stderr, stack trace in logs)
- **KeyboardInterrupt**: User cancellation (info message, exit code 130)

**Common Error Patterns:**

| Error Type | Message Style | Guidance Included |
|------------|---------------|-------------------|
| Missing required argument | `Error: Experiment name required for create command` | No |
| Invalid value | `Error: Invalid seed value: abc. Use integer or AUTO.` | Yes |
| Resource not found | `Error: Experiment 'test_exp' not found` | No |
| Conflict | `Error: Experiment 'test_exp' already exists` | No |
| Configuration issue | `Warning: Questions dataset not found at ...` | Yes: `Set QUESTIONS_DATASET_PATH in .env` |

### 1.4 Success Confirmation

**Success Message Characteristics:**
- Green checkmark symbol (✓) for visual confirmation
- Brief summary of what was accomplished
- Next steps or follow-up actions when applicable

**Success Confirmation Patterns:**

| Operation | Confirmation Style |
|-----------|-------------------|
| Create experiment | `Created experiment: test_exp (hash=8f3a9c2e)` |
| Add models | `✓ Models added successfully to experiment test_exp` |
| Add questions | `✓ Questions added to experiment 'test_exp'` + note about existing runs |
| Create run | `Created run run-20260328-abc for experiment test_exp` |
| Execute run | `Execution completed for run run-123` |
| Remove model | `✓ Removed 2 model variant(s) from experiment` |

**Detailed Success Summaries:**
For complex operations, multi-line summaries were provided:

```
Models added:
  - openai/gpt-4
  - anthropic/claude-3

To execute the new models, run the benchmark again with the same parameters.
The system will automatically skip questions already answered by these models.
```

**Panel-Based Summaries:**
Rich Panel component used for important information:
- Experiment details
- Run status
- Configuration summaries
- Warning messages

---

## 2. Feedback Quality

### 2.1 Clarity of Error Messages

**Strengths:**

**Specific Identification:**
- Named the exact resource: `Experiment 'test_exp' not found`
- Included identifiers: `Run 'run-001' not found in experiment`
- Showed counts: `Removed 2 model variant(s)`

**Technical Precision:**
- Distinguished between similar concepts:
  - "Experiment" vs "Run" vs "Variant"
  - "Snapshot" vs "Question"
- Used consistent terminology throughout

**Contextual Information:**
- Included relevant parameters: `API error 429: model=openai/gpt-4, message=Rate limit exceeded`
- Showed expected vs actual when applicable
- Logged full error response bodies for debugging

**Weaknesses:**

**Inconsistent Guidance:**
- Some errors included fix suggestions, others did not
- No consistent pattern for when to include guidance
- User had to infer next steps for many errors

**Dual Output Confusion:**
- Same error printed to both Rich console and stderr
- Different formatting could cause confusion
- Stack traces only in logs, not visible to user

**Technical Leakage:**
- Some error messages exposed internal implementation:
  - `Variant registration conflict (ignored): var-abc123`
  - `Frozen experiment protocol mismatch`
- Users needed to understand variant/experiment architecture

### 2.2 Usefulness of Hints and Suggestions

**Configuration Hierarchy Feedback:**

The `config_hierarchy` module provided systematic feedback:

| Source | Feedback Message | Usefulness |
|--------|------------------|------------|
| CLI | (none) | High - user was explicit |
| .env | `using default from environment (.env)` | Medium - informed but not actionable |
| Internal | `using all available questions (default)` | High - clarified default behavior |

**Interactive Assistance:**

**Remove Model Interactive Mode:**
- `?` argument triggered interactive selection
- Listed available models with indices
- Required confirmation before destructive action

**Warning with Guidance:**
```
⚠ WARNING: Questions dataset not found at /path/to/questions.json
Set QUESTIONS_DATASET_PATH in .env to specify the correct path.
```

**Missing Argument Guidance:**
```
Error: --remove-model requires an argument.
Use --remove-model <ids> or --remove-model ? for assisted mode.
```

**Cancellation Feedback:**
- Interactive operations showed `[dim]Cancelled.[/dim]` on user abort
- Clear indication that no changes were made

### 2.3 Actionability of Messages

**Highly Actionable Messages:**

| Message | Why Actionable |
|---------|----------------|
| `Invalid seed value: abc. Use integer or AUTO.` | Shows valid options |
| `Run 'run-001' not found in experiment. Use --experiment my_exp --run` | Shows correct syntax |
| `Set QUESTIONS_DATASET_PATH in .env to specify the correct path` | Specific fix |
| `Completed models are automatically skipped` | Sets expectations |

**Moderately Actionable Messages:**

| Message | Limitation |
|---------|------------|
| `Experiment 'test_exp' already exists` | User must infer: use different name or view existing |
| `No questions found matching filter: Q001-Q010` | User must check question IDs |
| `Frozen experiment protocol mismatch` | Technical, requires architecture knowledge |

**Low Actionability Messages:**

| Message | Problem |
|---------|---------|
| `Variant registration conflict (ignored)` | What should user do? Is this a problem? |
| `Using frozen protocol settings: ...` | Informational, no action needed or possible |
| `CLI settings will override frozen protocol` | Warning without clear implications |

---

## 3. Flow and Ergonomics

### 3.1 Multi-Step Operation Presentation

**Experiment Creation Flow:**

1. **Validation**: Check dataset path, show warning if missing
2. **Resolution**: Resolve questions and seed with hierarchy
3. **Feedback**: Show configuration summary
4. **Execution**: Create experiment and snapshots
5. **Confirmation**: Show success with hash

**Example Flow:**
```
⚠ WARNING: Questions dataset not found at /path/to/questions.json
Set QUESTIONS_DATASET_PATH in .env to specify the correct path.

Configuration:
  Questions: using all available questions from dataset (default)
  Seed: using default from environment (.env)

Created experiment: test_exp (hash=8f3a9c2e)
```

**Run Execution Flow:**

1. **Initialization**: Load experiment, validate run
2. **Planning**: Build execution plan, deduplicate items
3. **Progress Display**: Rich progress bar with ETA
4. **Milestone Logging**: 25%, 50%, 75%, 100% progress
5. **Completion Summary**: Responses written, errors, status

**Manual Review Flow:**

1. **Pending Count**: Show total items pending review
2. **Item Display**: Question, options, LLM response, confidence
3. **Classification**: Keyboard shortcuts (A/B/C/D/N/E/S/Q/Z)
4. **Progress Tracking**: `Item 5/23 | Pendentes: 18 | Processadas: 5`
5. **Auto-Save**: Each classification saved immediately
6. **Exit Options**: Quit and save, or undo last

### 3.2 User Awareness ("What Happened")

**Initialization Summary:**
Fixed-width formatted header provided complete context:

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

**Execution Visibility:**

**Progress Bar (Rich):**
- Visual bar with percentage
- MofNCompleteColumn: `25/100`
- TimeRemainingColumn: `ETA: 120s`
- Status field: `openai/gpt-4 (Iter 1)`

**Milestone Logging:**
- Every 25%: `Progress: 25/100 (25.0%)`
- Model switches: `Switched to model claude-3 (2/3)`
- Iteration changes: `Starting iteration 2/3`

**Completion Summary:**
```
Write completed: 50 responses, 2 errors, 0 responses skipped, 1 runs updated
Execution completed for run run-123
```

**State Change Notifications:**
- `Updated run run-123 status to: completed`
- `Marked variant var-abc as completed in run run-001`
- `Added model openai/gpt-4 (variant var-abc) to run run-001`

### 3.3 Progress and Waiting Communication

**Progress Tracking Features:**

**Progress Bar Components:**
- Task description: "Benchmark Execution"
- Bar column: Visual progress
- M of N complete: `25/100`
- Task progress: `25%`
- Time remaining: `ETA: 120s`
- Status: Current model and iteration

**Logging During Execution:**
- API requests: `Sending API request: model=openai/gpt-4, max_tokens=2048`
- API responses: `API response: model=openai/gpt-4, tokens=150, finish_reason=stop`
- Item completion: `Item run-001::var-abc::123 completed: answer=B, correct=True, latency=1200ms`
- Retry attempts: `Retry attempt 1/3 after 1.00s delay due to: Rate limit exceeded`

**Waiting Indicators:**
- No explicit "waiting" or "thinking" messages
- API latency visible in completion messages
- Retry delays explicitly communicated

**Long-Running Operation Support:**
- Progress logged to file continuously
- Console progress bar updated in place
- ETA recalculated based on items/second
- Milestone logging at 25% intervals

---

## 4. Consistency

### 4.1 Terminology Consistency

**Core Concepts:**

| Term | Definition | Usage |
|------|------------|-------|
| Experiment | Frozen configuration + question snapshots | `--create-experiment`, `--experiment` |
| Run | Execution instance within an experiment | `--create-run`, `--run` |
| Variant | Model + configuration (reasoning, vision, structured) | `--add-model`, variant_id |
| Snapshot | Immutable question copy in experiment | Created during experiment creation |
| Plan | Immutable execution plan | Internal, not user-facing |
| Item | Single execution unit (variant + snapshot + iteration) | Internal, logged during execution |

**Consistent Usage:**
- "Experiment" always referred to frozen configuration container
- "Run" always referred to execution instance
- "Variant" always referred to model+configuration combination
- "Snapshot" always referred to question copies

**Potential Confusion:**
- "Model" used for both base model (`openai/gpt-4`) and variant
- "Question" used for both source question and snapshot
- "Iteration" concept present but fixed at 1 in later versions

### 4.2 Tone Consistency

**Formal Technical Tone:**
- Messages were direct and factual
- No humor or personality
- Passive voice common: "was created", "was updated"

**Error Tone:**
- Neutral, non-blaming
- Factual description of problem
- Occasional guidance when obvious fix existed

**Success Tone:**
- Positive but restrained
- Checkmark symbols for visual confirmation
- Brief summaries without celebration

**Inconsistencies:**

**Mixed Formality:**
- Most messages: Formal technical English
- Some messages: Portuguese (review UI)
  - `Iniciando revisão para o experimento`
  - `Nenhuma resposta pendente de revisão`
- Emoji usage in some warnings: `⚠ WARNING`

**Rich vs Plain Text:**
- Rich console: Colored, formatted, panels
- Stderr: Plain text, no formatting
- Same content, different presentation

### 4.3 Behavior Predictability

**Predictable Patterns:**

**Command Routing:**
- `--experiment <name>` alone → Show experiment details
- `--experiment <name> --add-model` → Add models
- `--experiment <name> --create-run` → Create run
- `--experiment <name> --run <name> --execute` → Execute run

**Configuration Resolution:**
- Consistent hierarchy: CLI > .env > default
- Consistent feedback pattern for each source
- Same resolution logic for all configuration values

**Idempotency:**
- Duplicate experiments: Error
- Duplicate variants: Warning, skip
- Duplicate responses: Skip (idempotent write)
- Re-execution: Skip completed items

**Unpredictable Elements:**

**Dual Error Output:**
- Some errors printed twice (Rich + stderr)
- Inconsistent which errors used which channel

**Silent Operations:**
- Some operations logged at DEBUG only
- User had no visibility without enabling debug logs
- Example: `Randomizer set seed=42` (DEBUG level)

**Warning vs Error:**
- Some failures logged as WARNING, others as ERROR
- No clear rule for severity classification
- Example: "Frozen experiment protocol mismatch" logged as WARNING but may be critical

---

## 5. Trust Signals

### 5.1 Reliability Indicators

**Explicit Persistence Communication:**
- `Persist data: YES` clearly stated data would be saved
- `Configuration: FROZEN (config_hash=8f3a9c2e)` showed immutability guarantee
- Hash values provided verifiable identity

**Idempotency Guarantees:**
- Duplicate operations handled gracefully
- "Already exists" messages indicated state was checked
- Re-execution safely skipped completed items

**Atomic Operations:**
- Database transactions used for writes
- Rollback on failure logged
- Partial state not exposed to user

**Configuration Hash:**
- Hash provided cryptographic identity for experiments
- Enabled verification that configuration matched
- Made experiments auditable and reproducible

### 5.2 Anxiety Reduction During Execution

**Progress Visibility:**
- Real-time progress bar reduced uncertainty
- ETA helped users plan wait time
- Milestone logging showed forward movement

**Item-Level Feedback:**
- Each question completion logged with answer and correctness
- Users could see work being done, not just waiting
- Latency information showed actual API interaction

**Error Handling Transparency:**
- Retry attempts logged explicitly
- Delay durations shown: `after 1.00s delay`
- Max retries exceeded clearly communicated

**State Preservation:**
- Interrupted executions could resume
- Completed items not re-executed on resume
- Run status persisted (pending, running, completed, failed)

### 5.3 Recovery from Mistakes

**Undo Mechanisms:**

**Manual Review Undo:**
- `Z` key undid last classification
- History tracked for undo operations
- Changes not committed until classification saved

**Cancellation:**
- `Q` key quit and saved progress in review UI
- `Ctrl+C` caught and logged: `Benchmark interrupted by user`
- Partial progress preserved on interruption

**Interactive Correction:**

**Remove Model Assisted Mode:**
- `?` argument triggered interactive selection
- Listed available models with indices
- Required explicit confirmation before removal
- Cancellation option at confirmation prompt

**Configuration Feedback:**
- Assumed values explicitly communicated
- User could verify configuration before execution
- Warnings for missing datasets or invalid paths

**Error Recovery Guidance:**

| Error | Recovery Path |
|-------|---------------|
| `Experiment already exists` | Use `--experiment <name>` to view, or choose different name |
| `Run not found` | Check run name with `--experiment <name>` first |
| `Invalid seed value` | Message shows valid options: integer or AUTO |
| `Questions dataset not found` | Explicit guidance: `Set QUESTIONS_DATASET_PATH in .env` |

**Dry Run Support:**
- `--dry-run` flag validated configuration without execution
- Users could verify setup before committing to long runs
- Message: `Configuration validated successfully (dry run)`

---

## 6. Summary

The legacy UX was characterized by:

1. **Hybrid CLI paradigm** - Evolved from direct execution to experiment-based workflow, with both patterns coexisting

2. **Extensive help documentation** - Copy-paste examples, scenario-based workflows, inline comments

3. **Dual output channels** - Rich console for interactive use, stderr for scripting, sometimes both simultaneously

4. **Configuration transparency** - Explicit feedback about assumed values, hierarchy resolution visible to user

5. **Progress visibility** - Rich progress bars, milestone logging, ETA calculations, item-level feedback

6. **Idempotent operations** - Safe re-execution, duplicate detection, state preservation

7. **Inconsistent error guidance** - Some errors included fix suggestions, others required user inference

8. **Mixed language and tone** - Primarily English technical tone, with Portuguese in review UI and emoji in warnings

9. **Trust through hashes** - Configuration hashes provided verifiable identity and auditability

10. **Recovery mechanisms** - Undo in review UI, interactive correction, dry-run validation, interruption resilience

This document captures the user experience without proposing improvements or comparing to newer implementations.
