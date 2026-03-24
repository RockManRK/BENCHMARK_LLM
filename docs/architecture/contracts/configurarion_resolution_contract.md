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
   `NULL` é um estado válido e significa **“não enviar para a requisição”**.

4. **Nada é inferido automaticamente**  
   Se uma configuração não puder ser resolvida conforme este contrato, o sistema **falha explicitamente**.

---

## 📋 Tabela de Configurações

| Key | Type | Resolved At | Final Scope | Stored In | Resolution Order | Default | Error if Missing | Description |
|----|----|----|----|----|----|----|----|----|
| DATABASE_PATH | string | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `./data/benchmark.db` | NO | Caminho do banco de dados. Se não existir, o sistema cria. Falha apenas se não puder criar. |
| EXECUTION_MODE | enum | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `normal` | NO | Modo de execução do CLI. |
| LOG_FILE_PATH | string \| null | SYSTEM_START | SYSTEM | `.env` | `.env` | `NULL` | NO | Caminho do arquivo de log. `NULL` desativa logging em arquivo. |
| LOG_LEVEL | enum | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `INFO` | NO | Nível de detalhamento do log. |
| QUESTIONS_DATASET_PATH | string | EXPERIMENT_CREATION | EXPERIMENT | `experiment.config` | `experiment → .env` | none | YES | Caminho do dataset de perguntas usado pelo experimento. |
| OPENROUTER_DEBUG_ENABLED | bool | SYSTEM_START | SYSTEM | `.env` | `.env → internal` | `FALSE` | NO | Ativa dados extras de debug no retorno da API. |
| DEFAULT_QUESTIONS | list \| null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Usado apenas na criação do experimento. Se ausente, todas as perguntas disponíveis são adicionadas. |
| QUESTIONS_STATUS_ADD | string \| null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Filtra perguntas a serem adicionadas por flag. |
| QUESTIONS_STATUS_EXCLUDE | string \| null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | `NULL` | NO | Exclui perguntas por flag. |
| MODELS_DEFAULT_FOR_EXPERIMENTS | list \| null | EXPERIMENT_CREATION | EXPERIMENT | *not persisted* | `.env` | none | NO | Modelos adicionados automaticamente ao criar o experimento. Usado apenas na criação. |
| BASE_URL | string | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | none | YES | Endpoint do modelo (OpenRouter, local ou outro). |
| MODEL_MAX_TOKENS_REASONING | int \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Máximo de tokens de raciocínio. Se `NULL`, não é enviado. |
| MODEL_MAX_TOKENS_TOTAL | int \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Máximo total de tokens (raciocínio + resposta). Se `NULL`, não é enviado. |
| MODEL_REASONING_EFFORT | enum \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Nível de esforço de raciocínio do modelo. Se `NULL`, não é enviado. |
| MODEL_REPEAT_PENALTY | float \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Penalidade por repetição. Se `NULL`, não é enviado. |
| MODEL_TEMPERATURE | float \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Temperatura de amostragem. Se `NULL`, não é enviado. |
| MODEL_TOP_K | int \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Top‑K sampling. Se `NULL`, não é enviado. |
| MODEL_TOP_P | float \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Top‑P sampling. Se `NULL`, não é enviado. |
| MODEL_VISION | bool \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Ativa suporte a visão no modelo. Se `NULL`, não é enviado. |
| STRUCTURED_OUTPUTS | bool \| null | MODEL_VARIANT_CREATION | RUN | `model_variant.config` | `model_variant → experiment → .env` | `NULL` | NO | Solicita saída estruturada (JSON). Se `NULL`, não é enviado. |
| RUN_RESPONSES_SEED | int \| AUTO \| OFF | RUN_CREATION | RUN | `run.config` | `run → experiment → .env → internal` | `OFF` | NO | Controla a ordem das alternativas (A, B, C, D). Fixo por RUN e compartilhado entre todos os modelos daquele RUN. Se `NULL`, ordem original será usada. |
| SYSTEM_PROMPT | string \| null | RUN_CREATION | RUN | `run.config` | `run → experiment → .env` | `NULL` | NO | Prompt de sistema aplicado ao RUN. Se `NULL`, não é enviado. |
| USER_PROMPT | string \| null | RUN_CREATION | RUN | `run.config` | `run → experiment → .env` | `NULL` | NO | Prompt do usuário aplicado ao RUN. Se `NULL`, não é enviado. |

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