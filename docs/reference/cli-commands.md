---
type: reference
audience: ai
last-validated: 2026-04-11
status: active
---

# CLI Commands Reference

**Purpose:** Complete CLI command reference  
**Source:** Validated against `src/cli/` modules and `bcllm.py` dispatcher

---

## Command Structure

```
bcllm <command> [options]
```

All commands require `--experiment <name>` or `--create-experiment <name>` to identify the target experiment.

---

## Experiment Commands

### Create Experiment

```bash
bcllm --create-experiment <name> [options]
```

**Purpose:** Create a new experiment with frozen configuration

**Required:**
- `<name>` — Human-readable unique experiment name

**Options:**
| Flag | Description | System-Default |
|------|-------------|----------------|
| `--seed <value>` | Seed for randomization (`AUTO`, `<int>`, `system-default`) | From `.env` RUN_RESPONSES_SEED |
| `--system-prompt <text>` | System prompt template | From `.env` SYSTEM_PROMPT |
| `--user-prompt <text>` | User prompt template with `{question}`, `{options}` placeholders | From `.env` USER_PROMPT |
| `--url <base_url>` | API base URL | From `.env` BASE_URL |
| `--data-set <path>` | Path to questions dataset | From `.env` QUESTIONS_DATASET_PATH |
| `--add-questions <spec>` | Questions to snapshot | All available |
| `--add-model <model_id>` | Model variant to add | None (must be explicit) |

**Text Flags Must Be Quoted:** Flags accepting multi-word text (e.g., `--system-prompt`, `--user-prompt`) must be quoted or provided via file:
```bash
# Correct: Quoted text
bcllm --create-experiment my_exp --system-prompt "You are a helpful assistant."

# Correct: Using file (if supported)
bcllm --create-experiment my_exp --system-prompt @prompt.txt

# Wrong: Unquoted text with spaces (shell splits arguments)
bcllm --create-experiment my_exp --system-prompt You are a helpful assistant.
```

**Composite Flow:** Can combine `--create-experiment` with `--add-questions` and `--create-run` in single command:
```bash
bcllm --create-experiment my_exp --add-questions 1-10 --create-run
```

**Model Variants Must Be Added Separately:** Creating an experiment and adding model variants in the same command is **NOT supported**. Model variants must be added after experiment creation, one per command:
```bash
# Step 1: Create experiment
bcllm --create-experiment my_exp --add-questions 1-10

# Step 2: Add model variant (separate command)
bcllm --experiment my_exp --add-model openai/gpt-4

# Step 3: Add another model variant (separate command)
bcllm --experiment my_exp --add-model google/gemini-pro
```

**Constraints:**
- Name must be unique
- Cannot use `system-default` for this command
- Only one model variant may be added per `--add-model` command

### Show Experiment

```bash
bcllm --experiment <name> [options]
```

**Purpose:** Display experiment configuration

**Options:** Same as create (for modification)

**Modification Rules:**
- Can add questions: `--add-questions <spec>`
- Can add models: `--add-model <model_id>`
- Can change seed (doesn't affect existing runs)
- Can change prompts (doesn't affect existing runs)
- Cannot change name

### List Experiments

```bash
bcllm --list-experiments
```

**Purpose:** List all experiments with basic info

### Remove Experiment

```bash
bcllm --remove-experiment <name>
```

**Purpose:** Remove experiment (soft delete; historical data preserved)

---

## Model Commands

### Add Model Variant

```bash
bcllm --experiment <name> --add-model <model_id> [options]
```

**Purpose:** Add a model variant to experiment

**Required:**
- `<model_id>` — Base model identifier (e.g., `openai/gpt-4`, `google/gemini-pro`)

**Model Configuration Options:**
| Flag | Description | System-Default |
|------|-------------|----------------|
| `--reasoning <effort>` | Reasoning effort (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`) | Not sent in API request |
| `--max-tokens <int>` | Max tokens for generation (1 or above) | Not sent in API request |
| `--reasoning-tokens <int>` | Max reasoning tokens (1 or above) | Not sent in API request |
| `--temperature <float>` | Temperature (0.0-2.0) | Not sent in API request |
| `--top-p <float>` | Top-P sampling (0.0-1.0) | Not sent in API request |
| `--top-k <int>` | Top-K sampling (0 or above) | Not sent in API request |
| `--repeat-penalty <float>` | Repeat penalty (0.0-2.0) | Not sent in API request |
| `--vision <bool>` | Enable vision support (`true`, `false`) | Not sent in API request |
| `--structured <bool>` | Enable structured output (`true`, `false`) | Not sent in API request |
| `--url <base_url>` | Model-specific API URL | Experiment-level URL |

**Boolean Values:** `true`, `false`, `system-default` (case-insensitive)

### List Models

```bash
bcllm --experiment <name> --list-models
```

**Purpose:** List all model variants in experiment

### Remove Model Variant

```bash
bcllm --experiment <name> --remove-model <variant_id>
```

**Purpose:** Remove model variant (prevents future use; historical data preserved)

**Note:** Use `?` as `<variant_id>` to see interactive selection menu

---

## Question Commands

### Add Questions

```bash
bcllm --experiment <name> --add-questions [spec] [options]
```

**Purpose:** Snapshot questions into experiment

**Spec Formats:**
- Individual: `"1"`
- Comma-separated: `"1, 3, 5"` (quote if spaces)
- Range: `"1-10"`
- Mixed: `"1, 3-5"`
- No spec: All available questions

**Filter Options:**
| Flag | Description |
|------|-------------|
| `--where <key=value>` | Include only questions matching criteria |
| `--exclude <key=value>` | Exclude questions matching criteria |

**Examples:**
```bash
bcllm --experiment my_exp --add-questions "1-10"
bcllm --experiment my_exp --add-questions "1, 3-5" --where status=valid
bcllm --experiment my_exp --add-questions "1-100" --exclude status=annulled
```

### List Questions

```bash
bcllm --experiment <name> --list-questions
```

**Purpose:** List all question snapshots in experiment

**Note:** Questions are immutable once added to an experiment. To change questions, create a new experiment with the desired question set.

---

## Run Commands

### Create Run

```bash
bcllm --experiment <name> --create-run [options]
```

**Purpose:** Create a new run (execution instance)

**Options:**
| Flag | Description | Inheritance |
|------|-------------|-------------|
| `--seed <value>` | Seed for this run (`AUTO`, `<int>`, `system-default`) | From experiment |
| `--system-prompt <text>` | System prompt override | From experiment |
| `--user-prompt <text>` | User prompt override | From experiment |

**Constraints:**
- Run configuration is frozen after creation
- Seed AUTO resolved to random int at creation time
- Prompts override experiment-level for this run only

### List Runs

```bash
bcllm --experiment <name> --list-runs
```

**Purpose:** List all runs with status

### Show Run

```bash
bcllm --experiment <name> --run <run_id>
```

**Purpose:** Display run configuration and status

### Remove Run

```bash
bcllm --experiment <name> --remove-run <run_id>
```

**Purpose:** Remove run (prevents future execution; historical data preserved)

**Note:** Use `?` as `<run_id>` to see interactive selection menu

---

## Execution Commands

### Execute Experiment

```bash
bcllm --experiment <name> --execute [options]
```

**Purpose:** Execute pending runs or specific run

**Filters:**
| Flag | Description |
|------|-------------|
| `--run <run_id>` | Execute specific run only |
| `--questions <spec>` | Execute specific questions only |
| `--models <variant_id>` | Execute specific model variants only |

**Partial Execution:** System automatically skips already-completed items

**Retry Policy:** Retry is configured via `.env` only (see [configuration-reference.md](configuration-reference.md)). Retry policy cannot be overridden via CLI.

**Prerequisites:**
- At least 1 run configured
- At least 1 model variant added
- At least 1 question snapshotted

---

## Export Commands

### Export Results

```bash
bcllm --experiment <name> --run <run_id> --export
```

**Purpose:** Export execution results for downstream analysis

---

## Review Commands

### Review Experiment

```bash
bcllm --review-experiment <name>
```

**Purpose:** Review ambiguous responses in TUI

### Review All

```bash
bcllm --review-all
```

**Purpose:** Review all pending items across all experiments

**Review UI Keys:**
- `A/B/C/D` — Select answer
- `N` — None (no clear answer)
- `E` — Error (technical issue)
- `S` — Skip
- `Q` — Quit and save
- `Z` — Undo last

---

## System-Default Support

Most configuration flags support `system-default` value, which bypasses inheritance and uses system built-in default (typically "not sent in API request").

**Commands that do NOT support `system-default`:**
- `--create-experiment`, `--experiment` (structural)
- `--url`, `--data-set` (must be explicit)
- `--add-model`, `--remove-model` (require explicit model ID)
- `--create-run`, `--remove-run` (structural)
- `--execute` (structural)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (validation, not found, invalid input, execution failure) |

---

## Related Documents

- [contracts/system-default-semantics.md](../contracts/system-default-semantics.md) — system-default behavior
- [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md) — Inheritance rules
- [reference/configuration-reference.md](configuration-reference.md) — .env settings
