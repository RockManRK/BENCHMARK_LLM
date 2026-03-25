# CLI Stabilization Plan — bcllm

**Status:** Draft — Ready for Execution  
**Scope:** Stabilize CLI behavior, persistence, and dataset handling to fully comply with TO‑BE specification  
**Codebase:** `/src_v2` only  
**Legacy:** `/src` read‑only reference

---

## 🎯 Objectives

1. Eliminate all hardcoded configuration and placeholder data
2. Ensure experiment creation freezes **real configuration state**
3. Make question handling dataset‑driven and schema‑agnostic
4. Align CLI routing and UX strictly with TO‑BE
5. Validate behavior through **human‑style workflows**, not synthetic tests

---

### A2. Real Configuration Freeze (`config_json`)
**Problem:** `config_json` is `{}` even when defaults exist.

**Actions**
- Resolve configuration at experiment creation:
  ```
  CLI > .env > system defaults
  ```
- Persist the resolved configuration into `config_json`

**Acceptance Criteria**
- `.env` with `SEED=AUTO` → `config_json.seed = "AUTO"`
- No experiment has `config_json = {}` unless truly empty

---

### A3. Mandatory Timestamps
**Problem:** `created_at` is `NULL` across multiple tables.

**Actions**
- Enforce `created_at` population for:
  - `experiments`
  - `model_variants`
  - `runs`
  - `question_snapshots`

**Acceptance Criteria**
- No persisted row has `created_at IS NULL`

---

### A4. Schema Cleanup
**Actions**
- Remove `experiments.description`
- Review `experiments.is_active`
  - Remove if unused
  - Otherwise document and test

**Acceptance Criteria**
- Schema contains only fields with defined behavior

---

## 🔴 CHECKPOINT B — Question System (BLOCKING)

### B1. Dataset Path via `.env`
**Problem:** Dataset path is hardcoded.

**Actions**
- Load dataset path from `.env`
- Support arbitrary datasets with:
  - Different tags
  - Different option counts
  - Missing flags
  - Future free‑text answers

**Acceptance Criteria**
- Changing dataset path in `.env` changes question source without code changes

---

### B2. Automatic Snapshot on Experiment Creation
**Problem:** `question_snapshots` remains empty.

**Actions**
- If no `--add-questions` is provided:
  - Select **all questions**
  - Generate snapshots immediately

**Acceptance Criteria**
- Creating an experiment always produces snapshots

---

### B3. Real Payload, No Placeholders
**Problem:** Placeholder stems and constant `answer_key`.

**Actions**
- Snapshot must include:
  - Real `stem`
  - Real `options`
  - Real `answer_key`
  - Full `meta`

**Acceptance Criteria**
- Different questions have different `answer_key` values
- No placeholder text exists

---

### B4. Internal Numeric Question IDs (DECISION)
**Decision**
- Introduce internal `question_number` (1..N)
- Preserve `source_question_id` (`Q001`) for reference only

**CLI Change**
- Migrate to:
  ```
  --add-questions 1-4
  ```
- Optional temporary support for `Q001-Q004`

**Acceptance Criteria**
- Internal IDs are stable regardless of dataset formatting

---

## 🔴 CHECKPOINT C — CLI Routing & UX (BLOCKING)

### C1. Fix `--help` and Entry Point
**Problem:** `--help` crashes due to legacy imports.

**Actions**
- Ensure CLI entrypoint imports **only** `/src_v2`
- Remove any residual `src.*` imports

**Acceptance Criteria**
- `python bcllm.py --help` runs cleanly

---

### C2. Restore Missing Commands
**Problem:** `--add-run` not recognized.

**Actions**
- Fix routing in `bcllm.py`

**Acceptance Criteria**
- All TO‑BE commands are reachable

---

### C3. Resolve Flag Ambiguity
**Problem:** `--reasoning` conflicts with other flags.

**Actions**
- Choose one canonical flag
- Remove or rename conflicting aliases

**Acceptance Criteria**
- `--reasoning none` works without ambiguity

---

### C4. Vision Flag UX
**Decision**
- Use either:
  - `--vision / --no-vision`
  - or `--vision true|false` with explicit parsing

**Acceptance Criteria**
- Value stored correctly in DB

---

## 🔴 CHECKPOINT D — Model Variants Identity

### Contract
| Field | Purpose |
|------|--------|
| `model_id` | Provider identifier (`google/gemini-3.1-flash-lite-preview`) |
| `variant_id` | Internal ID (`var_xxx`) |
| `variant_signature` | Human‑readable config identity |

**Examples**
- `gemini-3.1-flash-lite-preview`
- `gemini-3.1-flash-lite-preview (reasoning=low)`
- `gemini-3.1-flash-lite-preview (vision=true, reasoning=xhigh)`

**Acceptance Criteria**
- Same `model_id` + different configs → distinct variants

---

## 🧪 CHECKPOINT E — Human‑Style Validation

### Test Matrix (12 Experiments)
Vary **one axis per experiment**:
- Prompts: none / user / system / both
- Seed: empty / AUTO / fixed
- Questions: default / range / filter
- Models: remote / local / variants
- Runs: 1 / 3
- Vision: on / off
- Structured: on / off

### Mandatory DB Checklist
After each experiment:
- `created_at` populated
- `config_json` correct
- No hardcoded prompts
- Snapshots complete
- Variants correct

---

## 🚫 Out of Scope
- Parallelism
- Distributed execution
- Full V1 compatibility
- Websearch

---

## 📌 Notes on Directory Renaming
- **Do NOT rename `/src_v2` yet**
- First pass all checkpoints
- Then consider:
  - `/src_v2 → /src`
  - `/src → /src_old`

---

## 🏁 Definition of Done

- All checkpoints A–E pass
- At least 3 full workflows run end‑to‑end
- No placeholder data
- No hardcoded configuration
- CLI behavior matches TO‑BE exactly