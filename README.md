# Benchmark LLM

Benchmark LLM is a **reproducible, experiment‑driven benchmarking system** for evaluating Large Language Models (LLMs).

The system is designed around **explicit experiments**, **immutable execution plans**, and **auditable results**.  
There is **no immediate or ad‑hoc execution mode** in the core system.

---

## Core Principles

- Experiments are explicit
- Execution is never implicit
- All results are auditable
- No mutable global state
- No execution without identity
- No inference during execution

If a result exists in the database, **it means something actually happened**.

---

## Conceptual Architecture

The system is structured around three immutable contracts:

- **ExecutionPlan** — what must be executed
- **ExecutionEngine** — executes exactly what the plan defines
- **ResultWriter** — persists outcomes without deciding scope

High‑level flow:

```
CLI
 ↓
Planner
 ↓
ExecutionPlan (immutable)
 ↓
ExecutionEngine
 ↓
ResultWriter
 ↓
Database
```

---

## Source of Truth

This project intentionally separates **architecture** from **implementation**.

### Architectural contracts (DO NOT MODIFY):
- `docs/architecture/execution-plan.md`
- `docs/architecture/result-writer.md`

### System mental model:
- `QWEN.md`

If documentation and code disagree, **the documents are correct**.

---

## Command Line Interface (CLI)

The CLI is **explicit and declarative**.

There is **no immediate execution mode**.

All executions belong to:
- an experiment
- a run
- a resolved execution plan

### Quick Start

```bash
# 1. Create experiment with questions
python bcllm.py --create-experiment my_exp --questions "1-10"

# 2. Add model variant
python bcllm.py --experiment my_exp --add-model openai/gpt-4 --reasoning low

# 3. Create run
python bcllm.py --experiment my_exp --add-run --seed 42

# 4. Execute (requires OPENROUTER_API_KEY)
python bcllm.py --experiment my_exp --execute
```

### CLI Commands

| Category | Command | Description |
|----------|---------|-------------|
| **Experiments** | `--create-experiment <name>` | Create new experiment |
| | `--experiment <name>` | Show experiment details |
| | `--list-experiments` | List all experiments |
| | `--remove-experiment <name>` | Remove experiment (soft delete) |
| **Models** | `--add-model <model_id>` | Add model variant to experiment |
| | `--list-models` | List models in experiment |
| | `--remove-model <variant_id>` | Remove model variant |
| **Questions** | `--add-questions <spec>` | Add questions to experiment |
| | `--list-questions` | List questions in experiment |
| | `--remove-question <id>` | Remove question snapshot |
| **Runs** | `--add-run` | Create new run |
| | `--list-runs` | List runs in experiment |
| | `--run <run_id>` | Show run details |
| | `--remove-run <run_id>` | Remove run |
| **Execution** | `--execute` | Execute pending runs |
| **Review** | `--review-experiment <name>` | Manual review of responses |

---

## CLI Format Reference

### `--add-questions` Format

The `--add-questions` (or `--questions`) flag accepts question specifications in these formats:

| Format | Example | Description |
|--------|---------|-------------|
| **Single ID** | `1` or `Q001` | Select single question |
| **Comma-separated** | `"1, 3, 5"` or `"Q001,Q003,Q005"` | Select multiple specific questions |
| **Range** | `"1-10"` or `"Q001-Q010"` | Select range of questions |
| **Mixed** | `"1, 3-5, Q010"` | Combine formats |

**IMPORTANT: Quoting Requirement**

Arguments with spaces **must be quoted**:

```bash
# ✓ CORRECT (quoted, spaces allowed)
python bcllm.py --create-experiment test --questions "1, 3, 5"

# ✓ CORRECT (no spaces, quotes optional)
python bcllm.py --create-experiment test --questions 1,3,5

# ✗ INCORRECT (unquoted with spaces - shell splits into multiple args)
python bcllm.py --create-experiment test --questions 1, 3, 5
```

### Boolean/Null Value Format

Boolean flags accept case-insensitive values:

| Valid Values | Description |
|--------------|-------------|
| `true`, `TRUE`, `True` | Enable feature |
| `false`, `FALSE`, `False` | Disable feature |
| `null`, `NULL`, `Null` | Use default/not set |

Examples:
```bash
python bcllm.py --experiment test --add-model openai/gpt-4 --vision true
python bcllm.py --experiment test --add-model openai/gpt-4 --structured FALSE
python bcllm.py --experiment test --add-model openai/gpt-4 --vision NULL
```

### Configuration Key Contract

The system uses three levels of configuration with strict key contracts:

| Level | Config Keys | Purpose |
|-------|-------------|---------|
| **Experiment** | 18 keys | Global defaults, prompts, seed |
| **Model Variant** | 10 keys | Model-specific generation parameters |
| **Run** | 3 keys | Execution-specific seed and prompts |

**Experiment Config Keys (18):**
- `default_temperature`, `default_top_p`, `default_max_output_tokens`
- `default_reasoning_mode`, `default_reasoning_effort`
- `system_prompt_template`, `user_prompt_template`
- Plus 11 additional keys for URL, tokens, vision, structured output, etc.

**Model Variant Config Keys (10):**
- `model_id`, `reasoning_mode`, `reasoning_effort`
- `vision_enabled`, `structured_output`, `web_access_enabled`
- `temperature`, `top_p`, `max_output_tokens`, `label`

**Run Config Keys (3):**
- `seed`, `system_prompt`, `user_prompt`

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `OPENROUTER_API_KEY` | API authentication | **Yes** (set via system env, not .env) |
| `QUESTIONS_DATASET_PATH` | Path to questions JSON | Yes (default: `data/enamed_questions.json`) |
| `OPENROUTER_BASE_URL` | API endpoint | No (default: `https://openrouter.ai/api/v1`) |

**Setting API Key (Windows):**
```powershell
# PowerShell
setx OPENROUTER_API_KEY "your-api-key-here"

# CMD
set OPENROUTER_API_KEY=your-api-key-here
```

---

## Database Philosophy

- Identity is immutable
- Results are append‑only
- Historical data is never deleted
- Reexecution always creates a new ExecutionPlan

---

## Documentation Status

The following documents are **known to be outdated** and should not be used as reference until rewritten:

- Legacy CLI examples
- Old execution flows
- Any reference to "quick tests", "direct flow", or "iterations"

They are intentionally excluded from this README.

---

## Final Note

This project prioritizes:

- clarity over convenience
- reproducibility over speed
- explicit intent over implicit behavior

If a feature conflicts with these principles, **the feature is wrong**.