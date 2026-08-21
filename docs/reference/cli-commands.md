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
| `--randomization-seed <value>` | Randomization Seed — controls only `AnswerRandomizer`'s option shuffling, never sent to the API (`AUTO`, `<int>`, `system-default`) | From `.env` RANDOMIZATION_SEED |
| `--system-prompt <text>` | System prompt template | From `.env` SYSTEM_PROMPT |
| `--user-prompt <text>` | User prompt template with `{question}`, `{options}` placeholders | From `.env` USER_PROMPT |
| `--url <base_url>` | API base URL | From `.env` BASE_URL |
| `--data-set <path>` | Path to questions dataset | From `.env` QUESTIONS_DATASET_PATH |
| `--add-questions <spec>` | Questions to snapshot | All available |
| `--add-model <model_id>` | Model variant to add | None (must be explicit) |
| `--provider-lock <value>` | Enable/disable provider lock (`true`, `false`, `system-default`) | From `.env` AUTO_PROVIDER_LOCK |

**Text Flags Must Be Quoted:** Flags accepting multi-word text (e.g., `--system-prompt`, `--user-prompt`) must be quoted or provided via file:
```bash
# Correct: Quoted text
bcllm --create-experiment my_exp --system-prompt "You are a helpful assistant."

# Wrong: Unquoted text with spaces (shell splits arguments)
bcllm --create-experiment my_exp --system-prompt You are a helpful assistant.
```

**Composite Flow:** Can combine `--create-experiment` with `--add-questions` and `--add-run` in single command (corrected 2026-08-20 — `--create-run` was never a real flag, see `docs/status/known-issues.md`):
```bash
bcllm --create-experiment my_exp --add-questions 1-10 --add-run
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
- Can modify `--provider-lock` setting (requires `--experiment <name>`) — the one genuine exception to the freeze below; see `docs/status/known-issues.md` for the immutability tension this creates
- **Cannot** change the experiment's Randomization Seed or prompts after creation — corrected 2026-08-20: this table previously (incorrectly) listed both as changeable. No CLI path modifies them; the experiment's `config_json` is frozen at creation like everything else except `--provider-lock` above.
- Cannot change name

**Provider Lock Modification:**
```bash
# Enable provider lock
bcllm --experiment my_exp --provider-lock true

# Disable provider lock
bcllm --experiment my_exp --provider-lock false

# Reset to system default (bypass .env)
bcllm --experiment my_exp --provider-lock system-default
```

### List Experiments

```bash
bcllm --list-experiments
```

**Purpose:** List all experiments with basic info

### Remove Experiment

```bash
bcllm --remove-experiment <name>
```

**Status:** Disabled. Always exits 1 and touches nothing. The command was previously unreachable via a CLI routing bug; fixing that bug (2026-08-17) exposed that its implementation is a hard, cascading delete of the experiment's question snapshots, model variants, and runs — with no soft-delete mechanism anywhere in the schema — which conflicts with [contracts/immutability.md](../contracts/immutability.md) and [contracts/configuration-hierarchy.md](../contracts/configuration-hierarchy.md). Disabled pending a decision on the right removal semantics; see [status/known-issues.md](../status/known-issues.md).

---

## Provider Commands

### --resolve-providers

**Purpose**: Resolve and persist providers for all model variants with `PROVIDER=null`.

**Applies to**: `--experiment`

**Example**:
```bash
bcllm --experiment my_exp --resolve-providers
```

**Output**:
```
Provider Resolution Report for experiment 'my_exp':
  Resolved: 2
  Skipped:  1
  Failed:   0

Resolved providers:
  meta-llama/llama-3.3-70b-instruct -> deepinfra/turbo (via first)
  anthropic/claude-3.5-sonnet -> togetherai/turbo (via cheapest)
```

**Behavior**:
- Reads `PROVIDER_SELECTION_STRATEGY` from experiment config (default: `first`)
- Updates `model_variants.config.PROVIDER` for unresolved variants
- Skips variants with already-resolved providers
- Returns exit code 0 on success, 1 if any failed

**Strategies**:
- `first`: First endpoint listed by OpenRouter
- `cheapest`: Lowest prompt pricing
- `fastest`: Highest throughput
- `lowest-latency`: Lowest latency

**Note**: Run this before `--execute` when `PROVIDER_LOCK=true`.

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
| `--model-seed <int>` | Model Seed — sent as the API request's `seed` field for deterministic inference. Distinct from `--randomization-seed` (Run-level, controls only answer-option shuffling, never sent to the API) | Not sent in API request |
| `--vision <bool>` | Enable vision support (`true`, `false`) | Not sent in API request |
| `--structured <bool>` | Enable structured output (`true`, `false`) | Not sent in API request |
| `--url <base_url>` | Model-specific API URL | Experiment-level URL |

**`--reasoning`/`--reasoning-tokens` exclusivity (2026-08-21):** OpenRouter's `reasoning` object accepts only one of `effort`/`max_tokens` — never both. Passing both with concrete values on the same `--create-experiment`/`--add-model` command is a usage error (exit 2). A concrete value for either flag (including `--reasoning none`) suppresses the OTHER field's inheritance entirely, even from the experiment default; `system-default` on either only clears that field, leaving a validly-inherited sibling value untouched. `--reasoning-tokens` rejects `0` and negative values (exit 2) — use `--reasoning none` to disable reasoning explicitly. `--max-reasoning` (a former undocumented synonym of `--reasoning-tokens`) has been removed. Full normative detail: `docs/contracts/system-default-semantics.md`.

### --model-seed <int>

**Purpose**: Set Model Seed — sent as the API request's `seed` field for deterministic inference. See `docs/status/model-seed-checkpoint-b-design.md`.

**Applies to**: `--create-experiment` (Experiment-level default) and `--add-model` (per-variant)

**Example**:
```bash
bcllm --experiment my_exp --add-model openai/gpt-4 --model-seed 42
```

**Behavior**:
- Belongs to Experiment and model_variant — never to a Run.
- At Experiment creation: `CLI > .env MODEL_SEED > None`.
- At `--add-model`: `CLI > Experiment's own frozen MODEL_SEED > None` — never consults `.env` at this level.
- No `AUTO` state anywhere (unlike `--randomization-seed`).
- `system-default` breaks inheritance from the experiment and resolves to `None` (not sent).
- An integer, including `0`, is sent verbatim as `"seed"` in the API request; `None` omits the key entirely.
- Participates in `variant_signature` — two variants differing only by `--model-seed` never collide.
- Does not guarantee identical responses from the provider — only that the request asked for that seed.
- Never interferes with `--randomization-seed`/`AnswerRandomizer` — total separation between the two concepts.

### --provider <provider_slug>

**Purpose**: Specify OpenRouter provider for a model variant.

**Applies to**: `--add-model`

**Example**:
```bash
bcllm --experiment my_exp --add-model meta-llama/llama-3.3-70b-instruct --provider deepinfra/turbo
```

**Behavior**:
- Sets `PROVIDER` in the model variant's config
- Provider slug must match a valid OpenRouter provider endpoint (e.g., `deepinfra/turbo`)
- Use `system-default` to explicitly clear the provider (forces OpenRouter to choose)
- Without `--provider`, the variant has `PROVIDER=null` (unresolved)

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

**Mechanism:** Hard delete of the `model_variants` row itself (unlike `--remove-run`, which soft-deletes — see above; `model_variants` has no status-like column to reuse without a schema change, which was deliberately not done here). "Historical data preserved" refers specifically to `responses`/`errors`: they reference `variant_id` without cascade, so removing a variant that already has results fails with a foreign key error rather than destroying them — a variant with no results yet is removed cleanly, but its own config/`variant_signature` row does not survive. See [status/known-issues.md](../status/known-issues.md).

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
bcllm --experiment <name> --add-run [options]
```

**Purpose:** Create a new run (execution instance)

**Options:**
| Flag | Description | Inheritance |
|------|-------------|-------------|
| `--randomization-seed <value>` | Randomization Seed for this run (`AUTO`, `<int>`, `system-default`) — `AUTO` is resolved to a concrete integer once, here, at run creation | From experiment |
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

**Mechanism (as of 2026-08-17):** Soft delete — sets `status='removed'` rather than deleting the row, so the run's frozen config/Randomization Seed/prompts stay legible for audit. `Planner._get_runs()` excludes `status='removed'` both for `--execute` (no `--run` given) and for `--execute --run <id>` naming this run explicitly — the latter needed its own fix (`status != 'removed'` had to be added to that branch too; it originally had no status filter at all, see [status/known-issues.md](../status/known-issues.md)) and its own regression test, since the two code paths are independent.

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
- `--add-run`, `--remove-run` (structural)
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
