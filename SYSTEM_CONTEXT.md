# Benchmark LLM - System Context (LLM-Optimized)

**Version:** 1.0 | **Date:** 2026-03-14 | **Schema:** v3 (Model Variants)

---

## A. ENTIDADES E SCHEMA

### Core Entities (8 tables)

#### 1. `experiments` - Configuração Congelada
```
experiment_id (PK) | name (UNIQUE) | config_json | config_hash | 
system_prompt_template | user_prompt_template | created_at
```
- **Imutáveis:** `config_json`, `config_hash`, prompts
- **Hash inclui APENAS protocolo:** `default_prompt`, `use_structured_outputs`, `random_seed_policy`
- **NÃO inclui:** model variants (temperature, reasoning, vision)
- **Regra:** TODO run DEVE ter `experiment_id` (NULL não permitido)

#### 2. `runs` - Execuções de Benchmark
```
run_id (PK) | experiment_id (FK) | seed | is_dev | 
started_at | finished_at | status
```
- **Status:** `pending` → `running` → `completed` | `failed`
- **Imutáveis:** `experiment_id`, `seed`, `is_dev`, `started_at`
- **Mutáveis:** `status`, `finished_at`
- **Geração run_id:** `run-{YYYYMMDDHHMMSS}-{uuid8}`

#### 3. `run_models` - Modelos na Run (Incremental)
```
run_id (PK,FK) | variant_id (PK,FK) | status | added_at | completed_at
```
- **Status:** `pending` → `running` → `completed` | `removed`
- **Chave composta:** `(run_id, variant_id)`
- **Permite:** Adicionar modelos após criação da run
- **Regra:** Run deve estar `running` para adicionar modelos

#### 4. `model_variants` - Variantes com Parâmetros
```
variant_id (PK) | model_id (FK) | reasoning_mode | reasoning_effort | 
reasoning_max_tokens | vision_enabled | structured_enabled | 
variant_signature | created_at
```
- **Identity fields (definem variant_id):**
  - `reasoning_mode`: `unspecified`, `auto`, `off`, `effort`, `budget`
  - `reasoning_effort`: `xhigh`, `high`, `medium`, `low`, `minimal`
  - `reasoning_max_tokens`: int
  - `vision_enabled`: bool
  - `structured_enabled`: bool
- **NÃO-identity (NÃO afetam variant_id):** temperature, max_tokens, top_p, top_k, repeat_penalty
- **Signature format:** `{model_id}::reasoning={mode}::vision={bool}::structured={bool}`

#### 5. `models` - Registro de Modelos Base
```
model_id (PK) | provider | model_name | created_at
```
- **Ex:** `openai/gpt-4` → provider=`openai`, model_name=`gpt-4`
- **Imutável:** Todos campos

#### 6. `questions` - Catálogo Canônico
```
question_id (PK) | stem | options_json | correct_answer | 
has_image | image_path | status
```
- **Status:** `active`, `draft`, `archived`, `annulled`
- **Mutáveis:** `stem`, `options_json`, `correct_answer`, `status`
- **Imutáveis:** `has_image`, `image_path`
- **Regra:** Pode atualizar sem afetar snapshots existentes

#### 7. `question_snapshots` - Snapshots Imutáveis
```
snapshot_id (PK) | experiment_id (FK, NOT NULL) | question_id (FK) | 
question_json | created_at
```
- **Imutável:** Todos campos
- **Regra:** Criado UMA vez por (experiment_id, question_id)
- **Regra:** TODO snapshot DEVE ter experiment_id (NULL não permitido)
- **Garante:** Reprodutibilidade mesmo se `questions` mudar

#### 8. `responses` - Respostas de Modelos
```
response_id (PK) | run_id (FK) | snapshot_id (FK) | question_id (FK) | 
variant_id (FK) | iteration | selected_answer | response_text | 
is_correct | status | finish_reason | error_details | latency_ms | 
input_tokens | response_tokens | total_tokens | reasoning_tokens | 
effective_tokens | cost | raw_response_json | timestamp | 
parse_confidence | review_status | reviewed_at | manual_answer
```
- **FK para `model_variants`** (NÃO base models)
- **Imutáveis:** IDs, métricas, `raw_response_json`, `timestamp`
- **Mutáveis:** `selected_answer`, `is_correct`, `status`, review fields
- **Derivados:** `effective_tokens` = input + response + reasoning
- **Revisão manual:** `manual_answer` sobrescreve `selected_answer`

---

## B. ESTADOS E TRANSIÇÕES

### `runs` States
```
pending → running → completed (terminal)
                → failed (terminal)
```

### `run_models` States
```
pending → running → completed (terminal)
        → removed (terminal, só se sem respostas)
```

### `responses` States
```
pending → success (terminal)
        → error → pending (retry)
        → unsupported (terminal)
```

---

## C. OPERAÇÕES POR ESTADO

### `runs` - Operações Permitidas

| Operação | pending | running | completed | failed |
|----------|---------|---------|-----------|--------|
| Add modelos | ✅ | ✅ | ❌ | ❌ |
| Remover modelos | ✅ | ⚠️* | ❌ | ❌ |
| Mudar seed | ❌ | ❌ | ❌ | ❌ |
| Re-executar | ✅ | ✅ (pending only) | ✅ (pending only) | ✅ |
| Complete run | ✅ | ✅ | (já) | ✅ |

*⚠️ Só se nenhuma resposta ainda

### `experiments` - Imutabilidade
- **NÃO pode mudar:** `config_json`, `config_hash`, prompts
- **Reutilização com config diferente:** Protocolo sobrescrito (com warning)
- **Model variants preservados:** temperature, reasoning, vision NÃO afetam hash

---

## D. CONFIGURAÇÃO vs EXECUÇÃO

### Configuração (Imutável)

| Escopo | Item | Fonte |
|--------|------|-------|
| **Experimento** | `config_json` (protocolo) | `--experiment` + Settings |
| **Experimento** | `config_hash` | Derivado (SHA-256) |
| **Experimento** | `system_prompt_template` | `SYSTEM_PROMPT_TEMPLATE` env |
| **Experimento** | `user_prompt_template` | `USER_PROMPT_TEMPLATE` env |
| **Run** | `seed` | `--seed` CLI ou `RANDOM_SEED` env |
| **Variante** | Identity fields | CLI args + Settings |

### Protocolo (afeta hash) vs Variantes (NÃO afetam)

**Protocolo (afeta `config_hash`):**
- `default_prompt`
- `use_structured_outputs`
- `random_seed_policy` (AUTO, FIXED, NONE)

**Variantes (NÃO afetam hash, pode mudar entre runs):**
- `model_temperature`, `model_max_tokens`, `top_p`, `top_k`, `repeat_penalty`
- `reasoning_effort`, `reasoning_max_tokens`
- `enable_vision`, `enable_structured` (definam variante, mas não protocolo)

### Execução (Mutável)

| Item | Quando Muda |
|------|-------------|
| `run.status` | Durante execução |
| `run_models.status` | Durante execução |
| `responses.*` | Durante execução/revisão |

---

## E. DECISÕES IMPLÍCITAS DO CLI

### 1. Criação de Run/Experimento

| CLI | Decisão Implícita |
|-----|-------------------|
| `--models <m>` (sem `--run-id`) | **Cria nova run** |
| `--experiment <name>` | **Cria/reusa experimento** (config congelado) |
| `--run-id <id>` | **Ignora `--models`**, carrega do `run_models` |
| `--test-mode` | **DB em memória**, sem persistência |

### 2. Seed Policy (Prioridade)

1. `--seed <int>` CLI (mais alta)
2. `RANDOM_SEED=AUTO` env → gera seed única por run
3. `RANDOM_SEED=<int>` env → seed fixa
4. Nenhum → None (ordem original A,B,C,D)

### 3. Modos de Execução

| Flags | Modo | Persistência |
|-------|------|--------------|
| `--test-mode` | test | ❌ Em memória |
| `--mode dev` | dev | ✅ Completa |
| `--experiment <name>` | experiment | ✅ + config congelado |
| Nenhum | dev (default) | ✅ Completa |

**Shadow Experiment (Dev Mode):**
- Todo run DEVE ter `experiment_id`
- Dev mode cria `shadow-{run_id}` automaticamente
- Config congelada como experimento normal

### 4. Expansão de Questões

```
--questions Q001-Q003 → ["Q001", "Q002", "Q003"]
--where status=valid → {"status": "valid"}
--where has_image=false → {"has_image": False}
```

### 5. Variant Config (Prioridade)

1. `reasoning_mode` explícito → usa valor
2. `reasoning_enabled=False` → `mode="off"`
3. `reasoning_effort` definido → `mode="effort"`
4. `reasoning_max_tokens` definido → `mode="budget"`
5. Nenhum → `mode="unspecified"`

### 6. Fallbacks

- `user_prompt_template=None` + `default_prompt` definido → usa `default_prompt`
- `--experiment` sem `--mode` → força `experiment` mode
- `--test-mode` + `--experiment` → `test-mode` prevalece (warning)

---

## F. REGRAS CRÍTICAS

### Integridade de Chaves Estrangeiras

```
experiments ← runs ← run_models ← responses
                  ↓                ↓
            question_snapshots ← questions
                  ↓
            model_variants ← models
```

### Regras de Negócio

1. **TODO run DEVE ter `experiment_id`** (NULL não permitido)
2. **TODO snapshot DEVE ter `experiment_id`** (NULL não permitido)
3. **Seed é imutável** após criação da run
4. **Config de experimento é congelada** (hash não muda)
5. **Model variants podem variar** dentro do mesmo experimento
6. **Run deve estar `running`** para adicionar modelos
7. **Run `completed` não aceita** novos modelos
8. **Responses referenciam `model_variants`** (NÃO base models)
9. **`snapshot_id` é autoritativo** (question_id é redundância)

### Invariantes

```
- experiment.config_hash = SHA256(protocol_config)
- response.effective_tokens = input + response + reasoning_tokens
- run_models.status ∈ {pending, running, completed, removed}
- runs.status ∈ {pending, running, completed, failed}
- model_variants.reasoning_mode ∈ {unspecified, auto, off, effort, budget}
```

---

## G. FLUXO TÍPICO

### Criar e Executar Benchmark

```
1. CLI: --models gpt-4 claude-3 --iterations 3
2. RunManager.initialize_run()
   → Gera run_id
   → Cria/reusa experiment (se mode=experiment)
   → Determina seed (CLI > AUTO > FIXED > NONE)
   → Cria run no DB
   → Registra models + variants
   → Cria run_models (status=pending)
3. QuestionLoader.load() → persiste questions
4. QuestionFilter.apply() → cria snapshots (se não existem)
5. Para cada run_model (pending):
   → Para cada iteration:
     → AnswerRandomizer.shuffle() (usa run.seed)
     → OpenRouterClient.call()
     → ResponseRepository.create()
   → RunModel.status = completed
6. Run.status = completed
```

### Adicionar Modelos à Run Existente

```
1. CLI: --add-to-run run-123 --add-models qwen/2.5
2. RunManager.add_models_to_run()
   → Verifica run.status == "running"
   → Registra model + variant
   → Cria run_model (status=pending)
3. Re-executar: --run-id run-123
   → Carrega run_models existentes
   → Executa APENAS pending/running
   → Completed são ignorados
```

---

## H. TABELA DE IMUTABILIDADE (Resumo)

| Entidade | Imutáveis | Mutáveis | Derivados |
|----------|-----------|----------|-----------|
| experiments | config, hash, prompts | description | hash |
| runs | experiment_id, seed, is_dev, started_at | status, finished_at | - |
| run_models | run_id, variant_id, added_at | status, completed_at | - |
| models | todos | - | - |
| model_variants | identity fields | - | variant_id, signature |
| questions | has_image, image_path | stem, options, status | - |
| question_snapshots | todos | - | - |
| responses | IDs, métricas, raw_json | selected_answer, review_* | effective_tokens, is_correct |

---

## I. REFERÊNCIAS RÁPIDAS

### Files
- **Schema:** `src/db/schema.sql`
- **Models:** `src/db/models.py`
- **RunManager:** `src/core/run_manager.py`
- **CLI:** `src/cli/cli.py`
- **Settings:** `src/utils/config.py`

### Execution Mode Matrix

| Mode | DB | Config | Use Case |
|------|----|--------|----------|
| test | :memory: | Flexível | Validação rápida |
| dev | File | Flexível | Desenvolvimento |
| experiment | File | Congelado | Pesquisa reprodutível |

### Seed Policy Matrix

| Config | Behavior | Use Case |
|--------|----------|----------|
| `--seed 42` | Fixa 42 | Reprodutibilidade |
| `RANDOM_SEED=AUTO` | Única por run | Diversidade |
| `RANDOM_SEED=42` | Fixa 42 | Reprodutibilidade |
| Nenhum | None (A,B,C,D) | Original order |

---

**End of Context Document**
