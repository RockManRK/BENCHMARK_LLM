# name: "configurarion_resolution_contract.md"
# date: 24/03/2026
# version: 1.0
# Atenção!: nunca fazer alterações

---

# 📘 Configuration Resolution Contract  
**Benchmark LLM CLI**

Este documento define **todas as configurações suportadas pelo sistema**, **onde são resolvidas**, **onde são armazenadas**, **quando são capturadas**, e **como se comportam quando ausentes**.

Ele é **normativo**: se algo não estiver descrito aqui, **não existe**.

---

## 🧠 Princípios Fundamentais

1. **`.env` é apenas fonte inicial**  
   Após a criação de uma entidade (Experiment, Run, Model Variant), o `.env` **nunca mais é consultado** para aquela entidade.

2. **Configurações são resolvidas e capturadas em momentos específicos**  
   Cada configuração possui um ponto explícito de resolução (*Resolved At*).

3. **Configurações não resolvidas são armazenadas como `NULL`**
   `NULL` é um estado válido e significa **"não enviar para a requisição"**.
   Para forçar explicitamente este comportamento via CLI, use `"system-default"`.

4. **Nada é inferido automaticamente**  
   Se uma configuração não puder ser resolvida conforme este contrato, o sistema **falha explicitamente**.

---

## 📋 Tabela de Configurações

| Key | Type | Resolved At | Final Scope | Stored In | Resolution Order | Default | Error if Missing | Description |
|----|----|----|----|----|----|----|----|----|
| DATABASE_PATH | string | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `./data/benchmark.db` | NO | Caminho do banco de dados. Se não existir, o sistema cria. Falha apenas se não puder criar. |
| EXECUTION_MODE | enum | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `normal` | NO | Modo de execução do CLI. |
| LOG_FILE_PATH | string\null | SYSTEM_START | SYSTEM | `.env` | `.env` | `NULL` | NO | Caminho do arquivo de log. `NULL` desativa logging em arquivo. |
| LOG_LEVEL | enum | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `INFO` | NO | Nível de detalhamento do log. |
| QUESTIONS_DATASET_PATH | string | EXPERIMENT_CREATION | EXPERIMENT | `experiment.config` | `experiment → .env` | none | YES | Caminho do dataset de perguntas usado pelo experimento. |
| OPENROUTER_DEBUG_ENABLED | bool | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `FALSE` | NO | Ativa dados extras de debug no retorno da API. |
| DEFAULT_QUESTIONS | list\null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Usado apenas na criação do experimento. Se ausente, todas as perguntas disponíveis são adicionadas. |
| QUESTIONS_STATUS_ADD | string\null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Filtra perguntas a serem adicionadas por flag. |
| QUESTIONS_STATUS_EXCLUDE | string\null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Exclui perguntas por flag. |
| BASE_URL | string | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | none | YES | Endpoint do modelo (OpenRouter, local ou outro). |
| MODEL_MAX_TOKENS_REASONING | int\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Máximo de tokens de raciocínio. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_MAX_TOKENS_TOTAL | int\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Máximo total de tokens (raciocínio + resposta). Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_REASONING_EFFORT | enum\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Nível de esforço de raciocínio do modelo. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_REPEAT_PENALTY | float\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Penalidade por repetição. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_TEMPERATURE | float\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Temperatura de amostragem. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_TOP_K | int\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Top‑K sampling. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_TOP_P | float\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Top‑P sampling. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| MODEL_VISION | bool\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Ativa suporte a visão no modelo. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| STRUCTURED_OUTPUTS | bool\null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Solicita saída estruturada (JSON). Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| RUN_RESPONSES_SEED | int\AUTO\OFF | RUN_CREATION | RUN | `run.config` | `run → experiment → .env → internal` | `OFF` | NO | Controla a ordem das alternativas (A, B, C, D). Fixo por RUN e compartilhado entre todos os modelos daquele RUN. Se `NULL`, ordem original será usada. Use `"system-default"` no CLI para forçar este comportamento. |
| SYSTEM_PROMPT | string\null | RUN_CREATION | RUN | `run.config` | `run → experiment → .env` | `NULL` | NO | Prompt de sistema aplicado ao RUN. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |
| USER_PROMPT | string\null | RUN_CREATION | RUN | `run.config` | `run → experiment → .env` | `NULL` | NO | Prompt do usuário aplicado ao RUN. Se `NULL`, não é enviado. Use `"system-default"` no CLI para forçar este comportamento. |

---

## 🧭 Resumo Operacional

- **SYSTEM configs** → resolvidas no startup, nunca persistidas em entidades.
- **EXPERIMENT configs** → resolvidas e capturadas na criação do experimento.
- **MODEL configs** → resolvidas e capturadas na criação do model_variant.
- **RUN configs** → resolvidas e capturadas na criação do run.
- **`.env` nunca afeta entidades já criadas.**

---

## 🎯 Objetivo do Documento

Este contrato existe para garantir que:
- o sistema seja determinístico
- o comportamento seja auditável
- nenhuma configuração seja inferida
- nenhuma mudança global afete dados históricos

---

Sim — e dá para transformar isso em um **texto de arquitetura claro, formal e não ambíguo**, exatamente do jeito que você precisa para documentação técnica (inclusive para leitura por IAs).

Abaixo está uma proposta de texto **pronto para documentação**, estruturado, com linguagem precisa e conceitos explícitos. Ele não depende do CLI atual e continua válido mesmo após a migração.

---

# Configuration Resolution Model

This system adopts an explicit **multi-phase configuration resolution model**.  
Each configuration variable is resolved at a specific phase of the system lifecycle and may or may not be persisted, depending on its semantic role.

The goal of this model is to:
- Eliminate ambiguity between configuration, actions, and execution parameters
- Prevent accidental persistence of transient values
- Make resolution behavior predictable for humans and automated systems (including AI agents)

---

## Resolution Phases Overview

Configuration variables are classified according to **when** they are resolved and **whether** they are persisted.

| Phase | Purpose | Persisted |
|---|---|---|
| System | Infrastructure and runtime setup | No |
| Experiment Bootstrap | One-time actions during experiment creation | No |
| Experiment Configuration | Persistent experiment behavior | Yes |
| Model Variant Configuration | Model-specific persistent behavior | Yes |
| Run Configuration | Execution-specific parameters | Yes (run scope only) |

---

## Phase 1 — System Configuration

System-level configuration defines infrastructure and runtime behavior.  
These values are resolved at application startup and never migrate into domain entities.

**Examples:**
```
EXECUTION_MODE
DATABASE_PATH
LOG_LEVEL
LOG_FILE_PATH
OPENROUTER_BASE_URL
OPENROUTER_DEBUG_ENABLED
```

**Characteristics:**
- Required for system operation
- Not related to experiments or runs
- Never persisted in domain storage

---

## Phase 2 — Experiment Bootstrap Configuration (Consumable)

Bootstrap configuration variables define **actions to be executed at experiment creation time**.  
They are **consumed**, not persisted.

These variables are semantically equivalent to explicit CLI actions and must be resolved immediately after experiment creation.

### Question Bootstrap

Resolved as if the following command were executed:
```
--add-questions <spec> --where <filter> --exclude <filter>
```

**Variables:**
```
DEFAULT_QUESTIONS
QUESTIONS_STATUS_ADD
QUESTIONS_STATUS_EXCLUDE
```

**Behavior:**
- Used to select and snapshot questions
- Applied once during experiment creation
- Explicitly removed from configuration after resolution
- Must never appear in `experiments.config_json`

---

## Phase 3 — Experiment Configuration (Persistent)

Experiment configuration defines long-lived behavior and defaults that apply to all runs unless overridden.

These values migrate from environment configuration into the experiment and may later be inherited by models or runs.

**Migration Path:**
```
.env → experiments.config_json → execution
```

**Examples:**
```
MODEL_MAX_TOKENS_REASONING
MODEL_MAX_TOKENS_TOTAL
MODEL_REASONING_EFFORT
MODEL_TEMPERATURE
MODEL_TOP_P
MODEL_TOP_K
MODEL_REPEAT_PENALTY
MODEL_VISION
STRUCTURED_OUTPUTS
BASE_URL
```

**Characteristics:**
- Persisted in `experiments.config_json`
- Define default behavior
- May be overridden at lower levels

---

## Phase 4 — Model Variant Configuration

Model variant configuration applies to a specific model within an experiment.

**Migration Path:**
```
.env → experiments.config_json → model_variants.config → execution
```

**Characteristics:**
- Persistent
- Scoped to a specific model
- Overrides experiment-level defaults

---

## Phase 5 — Run Configuration

Run configuration defines execution-specific parameters.  
These values apply only to a single run.

### Run Bootstrap

Resolved at run creation time.

**Example:**
```
RUN_RESPONSES_SEED
```

Equivalent to:
```
--add-run --seed <value>
```

---

### Run Persistent Configuration

**Migration Path:**
```
.env → experiments.config_json → runs.config → execution
```

**Examples:**
```
RUN_RESPONSES_SEED.RUNRESOLVED
SYSTEM_PROMPT
USER_PROMPT
```

**Characteristics:**
- Persisted at run scope only
- Never migrate back to experiment or model configuration

---

## Design Rules

1. **Action ≠ Configuration**  
   Variables that describe *what to do* are actions and must be consumed, not persisted.

2. **Persistence Requires Intent**  
   A value is only persisted if it defines long-term behavior.

3. **Resolution Is Phase-Bound**  
   Each variable must be resolved at exactly one phase.

4. **No Implicit Migration**  
   Configuration never migrates upward (run → experiment, model → system).

---

## Summary

This resolution model ensures:
- Clear separation between configuration and actions
- Predictable behavior across experiment lifecycle
- Clean persistence boundaries
- Reduced ambiguity for both human developers and AI systems

---

## System:
´´´
EXECUTION_MODE = Opcional
DATABASE_PATH = Obrigatório
LOG_LEVEL = Opcional
LOG_FILE_PATH = Opcional
OPENROUTER_BASE_URL = Obrigatório
OPENROUTER_DEBUG_ENABLED = Opcional
´´´

## System/experiments
´´´
QUESTIONS_DATASET_PATH = Obrigatório
´´´

## System/model_variants
´´´
BASE_URL
´´´

## Resolvidos no ´--create-experiment´, comando esquivalente: "--add-questions ## --where * --exclude *"
´´´
DEFAULT_QUESTIONS
QUESTIONS_STATUS_ADD
QUESTIONS_STATUS_EXCLUDE
´´´

## Resolvidos no momento da criação do Model Variant (comando `--add-model`)
```
BASE_URL
MODEL_MAX_TOKENS_REASONING
MODEL_MAX_TOKENS_TOTAL
MODEL_REASONING_EFFORT
MODEL_TEMPERATURE
MODEL_TOP_P
MODEL_TOP_K
MODEL_REPEAT_PENALTY
MODEL_VISION
STRUCTURED_OUTPUTS
```

## Resolvidos no ´--add-run´, comando esquivalente: "--add-run --seed ## --<outras flags>"
´´´
RUN_RESPONSES_SEED
´´´

## Migram de nível até o momento da execução. (.env > experiments.config_json > runs.config > execute)
´´´
RUN_RESPONSES_SEED.RUNRESOLVED
SYSTEM_PROMPT
USER_PROMPT
´´´