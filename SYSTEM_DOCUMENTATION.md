## 🔹 A. Entidades Centrais (Modelo de Dados Real)

### Visão Geral do Schema

O sistema utiliza **SQLite** com 8 tabelas principais, 2 views e as seguintes entidades:

"""
experiments ──┬── runs ──┬── run_models ──┬── responses
              │          │                │
              │          │                └── model_variants ──┬── models
              │          │
              │          └── question_snapshots ──┬── questions
              │
              └── (config_json frozen)
"""

---

### 1. `experiments`

**Propósito:** Armazenar configurações de experimentos com snapshots **congelados e imutáveis**.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `experiment_id` | TEXT (PK) | ✅ Sim | ID único gerado (ex: `exp-a1b2c3d4`) |
| `name` | TEXT (UNIQUE) | ✅ Sim | Nome legível do experimento |
| `description` | TEXT | ❌ Não | Descrição opcional |
| `config_json` | TEXT | ✅ Sim | JSON congelado da configuração do protocolo |
| `config_hash` | TEXT | ✅ Sim | SHA-256 hash do protocolo (16 chars) |
| `system_prompt_template` | TEXT | ✅ Sim | Template do system prompt (congelado) |
| `user_prompt_template` | TEXT | ✅ Sim | Template do user prompt (congelado) |
| `created_at` | TIMESTAMP | ✅ Sim | Data de criação |

**Imutáveis:**
- `config_json` - Protocolo congelado (default_prompt, use_structured_outputs, random_seed_policy)
- `config_hash` - Hash derivado do protocolo
- `system_prompt_template` - Template do system prompt
- `user_prompt_template` - Template do user prompt

**Mutáveis:**
- `description` - Pode ser atualizada (não afeta hash)

**Derivados:**
- `config_hash` - Derivado de `config_json` (protocolo apenas)

**Observações:**
- **Model variants NÃO estão no hash** - temperatura, reasoning, vision podem variar entre runs do mesmo experimento
- **Protocolo é sobrescrito** ao reutilizar experimento com config diferente (com warning)

---

### 2. `runs`

**Propósito:** Rastrear execuções individuais de benchmark.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `run_id` | TEXT (PK) | ✅ Sim | ID único com timestamp (ex: `run-20260314120000-a1b2c3d4`) |
| `experiment_id` | TEXT (FK) | ✅ Sim | FK para experiments (NÃO pode ser NULL) |
| `seed` | INTEGER | ✅ Sim | Seed aleatória usada nesta run |
| `is_dev` | BOOLEAN | ✅ Sim | True se run é modo desenvolvimento |
| `started_at` | TIMESTAMP | ✅ Sim | Quando a run começou |
| `finished_at` | TIMESTAMP | ❌ Não | Quando a run terminou (NULL se em andamento) |
| `status` | TEXT | ❌ Não | `pending`, `running`, `completed`, `failed` |

**Imutáveis:**
- `experiment_id` - Não pode mudar após criação
- `seed` - Seed é fixa por run (single source of truth)
- `is_dev` - Define se é shadow experiment
- `started_at` - Timestamp de início

**Mutáveis:**
- `status` - Transita entre estados
- `finished_at` - Setado quando status = completed/failed

**Derivados:**
- Nenhum campo é derivado em tempo real

**Observações:**
- **TODO run DEVE ter experiment_id** - Não há suporte para NULL
- Em **DEV mode**, cria-se "shadow experiment" automaticamente
- `run_id` é gerado com timestamp + UUID (8 chars)

---

### 3. `run_models`

**Propósito:** Associar model variants a runs. Permite adicionar modelos dinamicamente.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `run_id` | TEXT (PK, FK) | ✅ Sim | FK para runs |
| `variant_id` | TEXT (PK, FK) | ✅ Sim | FK para model_variants |
| `status` | TEXT | ❌ Não | `pending`, `running`, `completed`, `removed` |
| `added_at` | TIMESTAMP | ✅ Sim | Quando modelo foi adicionado |
| `completed_at` | TIMESTAMP | ❌ Não | Quando todas iterações completaram |

**Imutáveis:**
- `run_id` + `variant_id` - Chave composta, não pode mudar

**Mutáveis:**
- `status` - Transita entre estados
- `completed_at` - Setado quando status = completed

**Derivados:**
- Nenhum

**Observações:**
- **Chave primária composta:** `(run_id, variant_id)`
- **Status `removed`:** Modelo removido da run (sem respostas ainda)
- Permite **execução incremental** - adicionar modelos após criação da run

---

### 4. `model_variants`

**Propósito:** Registrar variantes de modelos com parâmetros de execução.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `variant_id` | TEXT (PK) | ✅ Sim | ID curto hash-based (ex: `var-a1b2c3d4`) |
| `model_id` | TEXT (FK) | ✅ Sim | FK para models (base model) |
| `reasoning_mode` | TEXT | ✅ Sim | `off`, `auto`, `effort`, `budget`, `unspecified` |
| `reasoning_effort` | TEXT | ✅ Sim | `xhigh`, `high`, `medium`, `low`, `minimal` |
| `reasoning_max_tokens` | INTEGER | ✅ Sim | Máximo tokens para reasoning |
| `vision_enabled` | BOOLEAN | ✅ Sim | Vision habilitado |
| `structured_enabled` | BOOLEAN | ✅ Sim | Structured outputs habilitados |
| `variant_signature` | TEXT (UNIQUE) | ✅ Sim | Signature legível (única por model_id + identidade) |
| `created_at` | TIMESTAMP | ✅ Sim | Quando variante foi registrada |

**Campos de Identidade (definem `variant_signature`):**
- `reasoning_mode`
- `reasoning_effort` (quando mode='effort')
- `reasoning_max_tokens` (quando mode='budget')
- `vision_enabled`
- `structured_enabled`

**Campos NÃO-Identidade (NÃO afetam variant_id):**
- `temperature`, `top_p`, `top_k`, `max_tokens`, `repeat_penalty`
- Estes são parâmetros de execução que **não definem identidade da variante**

**Imutáveis:**
- Todos os campos de identidade são **imutáveis** após criação

**Mutáveis:**
- Nenhum campo é mutável após criação

**Derivados:**
- `variant_id` - Derivado do hash da signature
- `variant_signature` - String legível construída dos campos de identidade

**Signature Format:**
"""
{model_id}::reasoning={mode}::vision={bool}::structured={bool}
Ex: openai/gpt-4::reasoning=auto::vision=false::structured=false
"""

**Observações:**
- **Única variante por (model_id + identidade)** - unique index
- **Identity fields definem variant_id** - mesma identidade = mesmo variant_id
- **Execution params NÃO definem identidade** - temperatura pode mudar sem criar nova variante

---

### 5. `models`

**Propósito:** Registro de modelos base (LLMs) usados nos benchmarks.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `model_id` | TEXT (PK) | ✅ Sim | ID único (ex: `openai/gpt-4`) |
| `provider` | TEXT | ✅ Sim | Provedor (ex: `openai`, `anthropic`) |
| `model_name` | TEXT | ✅ Sim | Nome do modelo (ex: `gpt-4`) |
| `created_at` | TIMESTAMP | ✅ Sim | Quando modelo foi registrado |

**Imutáveis:**
- Todos os campos são imutáveis após criação

**Mutáveis:**
- Nenhum

**Derivados:**
- Nenhum

**Observações:**
- **Armazena APENAS informação do modelo base** - sem parâmetros de execução
- **Provider extraído do model_id** - se `openai/gpt-4`, provider=`openai`
- **Unique index em (provider, model_name)**

---

### 6. `questions`

**Propósito:** Catálogo canônico de perguntas do questionário.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `question_id` | TEXT (PK) | ✅ Sim | ID único (ex: `Q001`) |
| `stem` | TEXT | ❌ Não | Texto da pergunta |
| `options_json` | TEXT | ❌ Não | JSON com opções de resposta |
| `correct_answer` | TEXT | ❌ Não | Resposta correta (ex: `A`) |
| `has_image` | BOOLEAN | ✅ Sim | Se possui imagem |
| `image_path` | TEXT | ✅ Sim | Caminho do arquivo de imagem |
| `status` | TEXT | ❌ Não | `active`, `archived`, `draft`, `annulled` |

**Imutáveis:**
- `has_image` - Definido no carregamento inicial
- `image_path` - Caminho da imagem (se houver)

**Mutáveis:**
- `stem` - Pode ser atualizado (não afeta snapshots existentes)
- `options_json` - Pode ser atualizado (não afeta snapshots existentes)
- `correct_answer` - Pode ser atualizado (ex: questão anulada)
- `status` - Pode mudar (ex: `active` → `annulled`)

**Derivados:**
- Nenhum

**Observações:**
- **Catálogo CANÔNICO** - pode ser atualizado sem afetar experimentos existentes
- **Experimentos usam `question_snapshots`** - snapshots são imutáveis
- **Status `annulled`:** Questão anulada (não conta para accuracy)

---

### 7. `question_snapshots`

**Propósito:** Snapshots **imutáveis** de perguntas usadas em cada experimento.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `snapshot_id` | INTEGER (PK) | ✅ Sim | Auto-incremento único |
| `experiment_id` | TEXT (FK) | ✅ Sim | FK para experiments (NÃO pode ser NULL) |
| `question_id` | TEXT (FK) | ✅ Sim | FK para questions |
| `question_json` | TEXT | ✅ Sim | JSON completo da pergunta (snapshot) |
| `created_at` | TIMESTAMP | ✅ Sim | Quando snapshot foi criado |

**Imutáveis:**
- **Todos os campos são imutáveis** após criação

**Mutáveis:**
- Nenhum

**Derivados:**
- Nenhum

**Observações:**
- **Snapshot criado UMA VEZ por (experiment_id, question_id)**
- **TODO snapshot DEVE ter experiment_id** - NÃO há suporte para NULL
- **Único index em (experiment_id, question_id)** - previne duplicatas
- **Garante reprodutibilidade** - mesmo que `questions` mude, snapshot permanece

---

### 8. `responses`

**Propósito:** Armazenar respostas individuais de modelos a perguntas.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `response_id` | INTEGER (PK) | ✅ Sim | Auto-incremento único |
| `run_id` | TEXT (FK) | ✅ Sim | FK para runs |
| `snapshot_id` | INTEGER (FK) | ✅ Sim | FK para question_snapshots (autoritativo) |
| `question_id` | TEXT (FK) | ✅ Sim | FK para questions (redundância semântica) |
| `variant_id` | TEXT (FK) | ✅ Sim | FK para model_variants (NÃO base models) |
| `iteration` | INTEGER | ✅ Sim | Número da iteração (1-based) |
| `selected_answer` | TEXT | ❌ Não | Letra da resposta selecionada |
| `response_text` | TEXT | ❌ Não | Texto completo da resposta |
| `is_correct` | BOOLEAN | ❌ Não | Se resposta está correta |
| `status` | TEXT | ❌ Não | `pending`, `success`, `error`, `unsupported` |
| `finish_reason` | TEXT | ❌ Não | Razão da terminação (ex: `stop`, `length`, `eos`, `error`) |
| `error_details` | TEXT | ❌ Não | Detalhes do erro (se status=error) |
| `latency_ms` | INTEGER | ✅ Sim | Tempo de resposta em ms |
| `input_tokens` | INTEGER | ✅ Sim | Tokens de entrada |
| `response_tokens` | INTEGER | ✅ Sim | Tokens de resposta (completion) |
| `total_tokens` | INTEGER | ✅ Sim | Total tokens (input + response, exclui reasoning) |
| `reasoning_tokens` | INTEGER | ✅ Sim | Tokens de reasoning (NÃO incluídos em total_tokens) |
| `effective_tokens` | INTEGER | ✅ Sim | Custo computacional total (input + response + reasoning) |
| `cost` | REAL | ✅ Sim | Custo em créditos |
| `raw_response_json` | TEXT | ✅ Sim | Resposta bruta da API (JSON) |
| `timestamp` | TIMESTAMP | ✅ Sim | Quando resposta foi recebida |
| `parse_confidence` | TEXT | ❌ Não | `unknown`, `clear`, `ambiguous`, `no_answer`, `low_confidence` |
| `review_status` | TEXT | ❌ Não | `auto`, `manual`, `skipped` |
| `reviewed_at` | TIMESTAMP | ❌ Não | Quando revisão manual ocorreu |
| `manual_answer` | TEXT | ❌ Não | Resposta atribuída na revisão manual |

**Imutáveis (após escrita):**
- Todos os campos de identificação (`run_id`, `snapshot_id`, `question_id`, `variant_id`, `iteration`)
- Todos os campos de métricas (`latency_ms`, tokens, `cost`, `timestamp`)
- `raw_response_json` - Resposta bruta não pode mudar

**Mutáveis:**
- `selected_answer` - Pode mudar em revisão manual
- `is_correct` - Pode mudar se `selected_answer` mudar
- `status` - Pode transitar (ex: `pending` → `success`)
- `parse_confidence` - Pode mudar em revisão
- `review_status` - `auto` → `manual`
- `reviewed_at` - Setado quando revisado
- `manual_answer` - Setado na revisão manual

**Derivados:**
- `effective_tokens` = `input_tokens` + `response_tokens` + `reasoning_tokens`
- `is_correct` - Derivado de `selected_answer` vs `correct_answer` (do snapshot)

**Observações:**
- **Referencia `model_variants`** - NÃO base models (para rastreamento preciso)
- **`snapshot_id` é autoritativo** - `question_id` é redundância semântica
- **Revisão manual:** `manual_answer` sobrescreve `selected_answer` para análise

---

### 9. `errors`

**Propósito:** Rastrear erros encontrados durante execução.

| Campo | Tipo | Imutável? | Descrição |
|-------|------|-----------|-----------|
| `error_id` | INTEGER (PK) | ✅ Sim | Auto-incremento único |
| `run_id` | TEXT (FK) | ✅ Sim | FK para runs |
| `question_id` | TEXT (FK) | ✅ Sim | FK para questions |
| `variant_id` | TEXT (FK) | ✅ Sim | FK para model_variants |
| `error_type` | TEXT | ✅ Sim | Tipo/categoria do erro |
| `error_message` | TEXT | ✅ Sim | Mensagem legível do erro |
| `stack_trace` | TEXT | ✅ Sim | Stack trace completo |
| `timestamp` | TIMESTAMP | ✅ Sim | Quando erro ocorreu |

**Imutáveis:**
- Todos os campos são imutáveis após escrita

**Mutáveis:**
- Nenhum

**Derivados:**
- Nenhum

---

## 🔹 B. Estados Possíveis de Cada Entidade

### `experiments`

| Estado | Descrição | Transições Permitidas |
|--------|-----------|----------------------|
| `active` | Experimento ativo, pode ter runs associadas | → `archived` |
| `archived` | Experimento arquivado, somente leitura | (nenhuma) |

**Estado Implícito:**
- O estado não é armazenado explicitamente na tabela
- É inferido do uso: experimentos com `config_hash` reutilizado são "ativos"

---

### `runs`

| Estado | Descrição | Transições Permitidas |
|--------|-----------|----------------------|
| `pending` | Run criada, execução não começou | → `running` |
| `running` | Run em execução (modelos sendo testados) | → `completed`, `failed` |
| `completed` | Run completada com sucesso | (nenhuma, terminal) |
| `failed` | Run falhou (erro crítico) | (nenhuma, terminal) |

**Regras de Transição:**
"""
pending → running → completed
                      → failed
"""

**Quando cada estado é setado:**
- `pending`: Ao criar a run (estado inicial)
- `running`: Ao começar execução do primeiro modelo
- `completed`: Ao completar todos os modelos OU usar `--complete-run`
- `failed`: Ao ocorrer erro crítico não recuperável

---

### `run_models`

| Estado | Descrição | Transições Permitidas |
|--------|-----------|----------------------|
| `pending` | Modelo adicionado, execução não começou | → `running` |
| `running` | Modelo em execução (algumas iterações feitas) | → `completed`, `removed` |
| `completed` | Todas iterações completadas | (nenhuma, terminal) |
| `removed` | Modelo removido da run (sem respostas) | (nenhuma, terminal) |

**Regras de Transição:**
"""
pending → running → completed
         → removed
"""

**Quando cada estado é setado:**
- `pending`: Ao adicionar modelo à run com `--add-to-run`
- `running`: Ao começar execução do modelo
- `completed`: Ao completar todas iterações do modelo
- `removed`: Ao remover modelo da run (antes de responder)

---

### `questions`

| Estado | Descrição | Transições Permitidas |
|--------|-----------|----------------------|
| `active` | Questão ativa, usada em benchmarks | → `archived`, `draft`, `annulled` |
| `draft` | Questão em rascunho, não usada | → `active`, `archived` |
| `archived` | Questão arquivada, não usada | → `active` |
| `annulled` | Questão anulada (erro/correção) | (nenhuma, terminal) |

**Observações:**
- **Estado `annulled` é terminal** - questão anulada não pode ser "des-anulada"
- **Snapshots existentes NÃO são afetados** - mudar status não altera snapshots

---

### `responses`

| Estado | Descrição | Transições Permitidas |
|--------|-----------|----------------------|
| `pending` | Resposta ainda não processada | → `success`, `error`, `unsupported` |
| `success` | Resposta processada com sucesso | (nenhuma, terminal) |
| `error` | Erro ao processar resposta | → `pending` (retry) |
| `unsupported` | Modelo não suporta tipo de pergunta | (nenhuma, terminal) |

**Regras de Transição:**
"""
pending → success (terminal)
        → error → pending (retry)
        → unsupported (terminal)
"""

---

## 🔹 C. Operações Permitidas por Estado

### `runs` - Operações por Estado

| Operação | `pending` | `running` | `completed` | `failed` |
|----------|-----------|-----------|-------------|----------|
| Adicionar modelos (`--add-to-run`) | ✅ Sim | ✅ Sim | ❌ Não | ❌ Não |
| Remover modelos | ✅ Sim | ⚠️ Parcial | ❌ Não | ❌ Não |
| Mudar seed | ❌ Não | ❌ Não | ❌ Não | ❌ Não |
| Mudar dataset/questions | ❌ Não | ❌ Não | ❌ Não | ❌ Não |
| Re-executar run (`--run-id`) | ✅ Sim | ⚠️ Parcial | ⚠️ Parcial | ✅ Sim |
| Marcar como completed (`--complete-run`) | ✅ Sim | ✅ Sim | (já está) | ✅ Sim |
| Deletar run | ✅ Sim | ✅ Sim | ✅ Sim | ✅ Sim |

**Detalhes:**

**Adicionar modelos:**
- **`running`:** Permitido - modelos entram como `pending`
- **`completed`:** **Bloqueado** - run completada não pode receber modelos
- **Regra:** `run.status != "running"` → erro ao usar `--add-to-run`

**Remover modelos:**
- **`pending`:** Permitido - se nenhuma resposta ainda
- **`running`:** Permitido **apenas se** nenhuma resposta ainda (status → `removed`)
- **`completed`:** **Bloqueado** - respostas já existem

**Mudar seed:**
- **Nunca permitido** - seed é imutável após criação da run
- **Regra:** `run.seed` é definido em `RunManager._determine_seed()` e nunca muda

**Re-executar run:**
- **`running`:** Executa apenas modelos `pending` ou `running`
- **`completed`:** Executa apenas modelos `pending` ou `running` (se houver)
- **`failed`:** Re-executa modelos `pending` ou `running`

---

### `run_models` - Operações por Estado

| Operação | `pending` | `running` | `completed` | `removed` |
|----------|-----------|-----------|-------------|-----------|
| Executar iterações | ✅ Sim | ✅ Sim | ❌ Não | ❌ Não |
| Cancelar execução | ✅ Sim | ✅ Sim | ❌ Não | ❌ Não |
| Marcar como completed | ❌ Não | ✅ Sim | (já está) | ❌ Não |
| Marcar como removed | ✅ Sim | ✅ Sim* | ❌ Não | (já está) |

*Somente se nenhuma resposta ainda

---

### `experiments` - Operações

| Operação | Permitida? | Condições |
|----------|------------|-----------|
| Mudar `config_json` | ❌ Não | Imutável após criação |
| Mudar `system_prompt_template` | ❌ Não | Imutável após criação |
| Mudar `user_prompt_template` | ❌ Não | Imutável após criação |
| Adicionar runs | ✅ Sim | Sempre permitido |
| Reutilizar com config diferente | ⚠️ Parcial | Protocolo sobrescrito (com warning) |

**Reutilização de Experimento:**
"""
# Se config_hash diferente:
# 1. Protocol settings (default_prompt, use_structured_outputs, random_seed_policy)
#    → SOBRESCRITAS pelos valores congelados
# 2. Model variants (temperature, reasoning, vision)
#    → PRESERVADAS (não afetam hash)
"""

---

## 🔹 D. Configuração vs Execução

### O que é **Configuração** (definido uma vez)

| Item | Onde é Definido | Imutável? | Escopo |
|------|-----------------|-----------|--------|
| `experiment.config_json` | `--mode experiment --experiment <name>` | ✅ Sim | Experimento |
| `experiment.config_hash` | Derivado de `config_json` | ✅ Sim | Experimento |
| `experiment.system_prompt_template` | `SYSTEM_PROMPT_TEMPLATE` env ou CLI | ✅ Sim | Experimento |
| `experiment.user_prompt_template` | `USER_PROMPT_TEMPLATE` env ou CLI | ✅ Sim | Experimento |
| `run.seed` | `--seed` CLI ou `RANDOM_SEED` env | ✅ Sim | Run |
| `run.experiment_id` | `RunManager.initialize_run()` | ✅ Sim | Run |
| `model_variants.identity_fields` | CLI args + Settings | ✅ Sim | Variante |
| `questions` (catálogo) | Arquivo JSON externo | ❌ Não | Global |

**Protocolo do Experimento (afeta `config_hash`):**
- `default_prompt` - Instrução padrão para todas as questões
- `use_structured_outputs` - Política para JSON schema
- `random_seed_policy` - Política de seed (AUTO, FIXED, NONE)

**NÃO afetam `config_hash` (podem variar dentro do experimento):**
- `questionnaire_path` - Apenas metadado (snapshots são a verdade)
- `model_temperature`, `model_max_tokens`, `top_p`, `top_k`, `repeat_penalty`
- `reasoning_effort`, `reasoning_max_tokens`, `reasoning_exclude`
- `enable_vision`, `enable_structured` (estes definem variante, não protocolo)

---

### O que é **Execução** (pode mudar)

| Item | Quando é Definido | Mutável? | Escopo |
|------|-------------------|----------|--------|
| `run.status` | Durante execução | ✅ Sim | Run |
| `run.finished_at` | Ao completar/falhar | ✅ Sim | Run |
| `run_models.status` | Durante execução | ✅ Sim | Run-Model |
| `run_models.completed_at` | Ao completar modelo | ✅ Sim | Run-Model |
| `responses.*` | Durante execução | ✅ Parcial | Resposta |
| `errors.*` | Durante execução | ❌ Não | Erro |

**Parâmetros de Execução (não definem identidade):**
- `temperature` - Pode mudar entre runs do mesmo experimento
- `max_tokens` - Pode mudar entre runs
- `top_p`, `top_k`, `repeat_penalty` - Podem mudar entre runs

---

### O que é **Parâmetro de Execução** (só afeta aquela execução)

| Parâmetro | CLI Flag | Env Var | Padrão |
|-----------|----------|---------|--------|
| Temperatura | `--temperature` | `MODEL_TEMPERATURE` | Model default |
| Max Tokens | `--max-tokens` | `MODEL_MAX_TOKENS` | Model default |
| Top-P | `--top-p` | `MODEL_TOP_P` | Model default |
| Top-K | `--top-k` | `MODEL_TOP_K` | Model default |
| Repeat Penalty | `--repeat-penalty` | `MODEL_REPEAT_PENALTY` | Model default |
| Reasoning Effort | `--reasoning-effort` | `REASONING_EFFORT` | None |
| Reasoning Tokens | `--reasoning-tokens` | `REASONING_MAX_TOKENS` | None |
| Reasoning Exclude | `--reasoning-exclude` | `REASONING_EXCLUDE` | None |
| Vision | `--enable-vision` | `ENABLE_VISION` | False |
| Structured | `--enable-structured` | `USE_STRUCTURED_OUTPUTS` | False |

**Regra:** Se deixado em branco no `.env`, **NÃO é enviado para API** (usa model default)

---

## 🔹 E. Onde o CLI Decide Coisas Implicitamente

### 1. **Criação de Experimento/Run**

| Cenário | CLI | Decisão Implícita |
|---------|-----|-------------------|
| `--models <models>` (sem `--run-id`) | `python -m src.main --models gpt-4` | **Cria nova run** automaticamente |
| `--experiment <name>` | `--experiment my-exp --models gpt-4` | **Cria/reusa experimento** com config congelado |
| `--mode experiment` sem `--experiment` | `--mode experiment --models gpt-4` | **Erro:** `--experiment` obrigatório |
| `--test-mode` ou `--mode test` | `--test-mode --models gpt-4` | **DB em memória**, sem persistência |
| `--run-id <id>` | `--run-id run-20260314-abc` | **Ignora `--models`**, carrega do `run_models` |

**Código relevante (`src/main.py`):**
"""
# Validação de configuração
has_run_id = hasattr(self.args, 'run_id') and self.args.run_id
if not self.args.models and not has_run_id:
    print("Error: At least one model must be specified with --models, or use --run-id")
    return False
"""

---

### 2. **Inferência de Seed**

| Cenário | CLI/Env | Seed Resultante |
|---------|---------|-----------------|
| `--seed 42` | CLI explícito | **42** (fixa) |
| `RANDOM_SEED=AUTO` no `.env` | Env var | **Gerada automaticamente** por run |
| `RANDOM_SEED=42` no `.env` | Env var | **42** (fixa) |
| Nenhum seed configurado | - | **None** (ordem original A,B,C,D) |

**Prioridade:**
1. `--seed` CLI (mais alta)
2. `RANDOM_SEED=AUTO` env
3. `RANDOM_SEED=<int>` env
4. Nenhum (None)

**Código relevante (`src/run_manager.py`):**
"""
def _determine_seed(self, config: dict[str, Any]) -> Optional[int]:
    seed_config = config.get("seed")
    
    # 1. CLI --seed explicit
    if seed_config is not None and isinstance(seed_config, int):
        return seed_config
    
    # 2. RANDOM_SEED=AUTO
    if self.settings and self.settings.random_seed == "AUTO":
        return random.randint(0, 2**31 - 1)
    
    # 3. RANDOM_SEED=<int>
    if self.settings and isinstance(self.settings.random_seed, int):
        return self.settings.random_seed
    
    # 4. Nenhum seed
    return None
"""

---

### 3. **Normalização de Modo de Execução**

| CLI Flags | Modo Resultante | Persistência |
|-----------|-----------------|--------------|
| `--test-mode` | `test` | ❌ Em memória |
| `--mode test` | `test` | ❌ Em memória |
| `--mode dev` | `dev` | ✅ Completa |
| `--mode experiment --experiment <name>` | `experiment` | ✅ Completa + config congelado |
| `--experiment <name>` (sem `--mode`) | `experiment` | ✅ Completa + config congelado |
| Nenhum | `dev` (default) | ✅ Completa |

**Código relevante (`src/cli/cli.py`):**
"""
def _normalize_execution_mode(self, args: argparse.Namespace) -> argparse.Namespace:
    if args.test_mode:
        execution_mode = "test"
        if args.experiment:
            print("Warning: --test-mode has precedence. --experiment will be ignored.")
    elif args.experiment:
        execution_mode = "experiment"
        if args.mode and args.mode != "experiment":
            print(f"Warning: --experiment forces EXPERIMENT MODE. Ignoring --mode {args.mode}")
    elif args.mode:
        execution_mode = args.mode
    else:
        execution_mode = "dev"
    
    args.execution_mode = execution_mode
    return args
"""

---

### 4. **Expansão de Ranges de Questões**

| CLI Input | Expansão |
|-----------|----------|
| `--questions Q001` | `["Q001"]` |
| `--questions Q001-Q003` | `["Q001", "Q002", "Q003"]` |
| `--questions Q001 Q003-Q005` | `["Q001", "Q003", "Q004", "Q005"]` |

**Código relevante (`src/cli/cli.py`):**
"""
def _expand_question_ranges(self, questions: list[str]) -> list[str]:
    expanded = []
    for question in questions:
        if "-" in question and question.count("-") == 1:
            start, end = question.split("-")
            start_num = int(start[1:])
            end_num = int(end[1:])
            padding = len(start) - 1
            for num in range(start_num, end_num + 1):
                expanded.append(f"Q{num:0{padding}d}")
        else:
            expanded.append(question)
    return expanded
"""

---

### 5. **Filtro de Metadata de Questões**

| CLI Input | Filtro Resultante |
|-----------|-------------------|
| `--where status=valid` | `{"status": "valid"}` |
| `--where has_image=false` | `{"has_image": False}` |
| `--where count=5` | `{"count": 5}` |
| `--exclude status=annulled` | Exclui questões com `status=annulled` |

**Conversão de Tipos:**
- `"true"`/`"false"` → `bool`
- Tenta `int` → se falhar, tenta `float` → se falhar, mantém `str`

---

### 6. **Criação de Shadow Experiment (Dev Mode)**

| Cenário | Experimento Criado |
|---------|-------------------|
| `--mode dev --models gpt-4` | `shadow-run-20260314-abc` |

**Por quê?**
- **Todo run DEVE ter `experiment_id`** (não há NULL)
- Em dev mode, cria-se "shadow experiment" automaticamente
- Shadow experiment é único por run (`shadow-{run_id}`)
- Config é congelada como experimento normal

**Código relevante (`src/run_manager.py`):**
"""
def _create_shadow_experiment(self, run_id: str, config: dict[str, Any]) -> Experiment:
    shadow_name = f"shadow-{run_id}"
    
    # Verifica se já existe (não deveria)
    existing = self._experiment_repository.get_by_name(shadow_name)
    if existing:
        return existing
    
    # Cria shadow experiment com config congelada
    experiment = Experiment(
        name=shadow_name,
        config_json=json.dumps(...),
        config_hash=...,
        description=f"Shadow experiment for dev mode run {run_id}",
    )
    
    return self._experiment_repository.create(experiment)
"""

---

### 7. **Resolução de Model ID**

| CLI Input | Resolução |
|-----------|-----------|
| `--models gpt-4` | Usa `gpt-4` como model_id |
| `--models openai/gpt-4` | Usa `openai/gpt-4` como model_id |
| `--models Qwen/Qwen-2.5-72B` | Usa `Qwen/Qwen-2.5-72B` como model_id |

**Provider extraído implicitamente:**
"""
if "/" in model_id:
    parts = model_id.split("/", 1)
    provider = parts[0]
    model_name = parts[1]
else:
    provider = "unknown"
    model_name = model_id
"""

---

### 8. **Variant Config a partir de Settings**

| Settings | Variant Config Resultante |
|----------|--------------------------|
| `reasoning_enabled=False` | `reasoning_mode="off"` |
| `reasoning_effort="high"` | `reasoning_mode="effort"`, `reasoning_effort="high"` |
| `reasoning_max_tokens=1000` | `reasoning_mode="budget"`, `reasoning_max_tokens=1000` |
| `reasoning_enabled=True` (sem effort/tokens) | `reasoning_mode="auto"` |
| Nenhum reasoning config | `reasoning_mode="unspecified"` |

**Prioridade:**
1. `reasoning_mode` explícito (mais alta)
2. `reasoning_enabled`/`reasoning_effort`/`reasoning_max_tokens` (legado)
3. Default: `unspecified`

---

### 9. **Complete Run Implícito**

| Cenário | Comportamento |
|---------|---------------|
| `--complete-run <id>` | Marca run como `completed` + todos `run_models` `pending` → `completed` |
| Run com todos modelos `completed` | Status ainda é `running` até `--complete-run` explícito |

**Por quê?**
- Permite **adicionar modelos** mesmo após todos atuais completarem
- **Explicito é melhor que implícito** - usuário decide quando run está "fechada"

---

### 10. **Fallback de User Prompt Template**

| Config | Resultado |
|--------|-----------|
| `user_prompt_template` definido | Usa valor definido |
| `user_prompt_template=None`, `default_prompt` definido | Usa `default_prompt` como fallback |
| Ambos None | Usa built-in default |

**Código relevante (`src/utils/config.py`):**
"""
if self.user_prompt_template is None and self.default_prompt is not None:
    self.user_prompt_template = self.default_prompt
    logger.debug(f"Using default_prompt as user_prompt_template fallback")
"""

---

## Resumo das Entidades e Estados

"""
┌─────────────────────────────────────────────────────────────────────────┐
│                        HIERARQUIA DE ENTIDADES                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  experiments (config congelado)                                         │
│  ├── runs (execuções)                                                   │
│  │   ├── run_models (modelos na run)                                    │
│  │   │   └── responses (respostas)                                      │
│  │   └── question_snapshots (perguntas usadas)                          │
│  │                                                                      │
│  models (base)                                                          │
│  └── model_variants (variantes com params)                              │
│      └── responses (referenciam variante, não base)                     │
│                                                                         │
│  questions (catálogo canônico)                                          │
│  └── question_snapshots (snapshots imutáveis)                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
"""

### Tabela de Imutabilidade

| Entidade | Campos Imutáveis | Campos Mutáveis | Campos Derivados |
|----------|------------------|-----------------|------------------|
| `experiments` | `config_json`, `config_hash`, `system_prompt`, `user_prompt` | `description` | `config_hash` |
| `runs` | `experiment_id`, `seed`, `is_dev`, `started_at` | `status`, `finished_at` | Nenhum |
| `run_models` | `run_id`, `variant_id`, `added_at` | `status`, `completed_at` | Nenhum |
| `models` | Todos | Nenhum | Nenhum |
| `model_variants` | Todos (identidade) | Nenhum | `variant_id`, `variant_signature` |
| `questions` | `has_image`, `image_path` | `stem`, `options`, `correct_answer`, `status` | Nenhum |
| `question_snapshots` | Todos | Nenhum | Nenhum |
| `responses` | IDs, métricas, `raw_response_json` | `selected_answer`, `review_*`, `status` | `effective_tokens`, `is_correct` |
| `errors` | Todos | Nenhum | Nenhum |

---

## Referências

- **Schema SQL:** `src/db/schema.sql`
- **Models:** `src/db/models.py`
- **Repository:** `src/db/repository.py`
- **Run Manager:** `src/core/run_manager.py`
- **CLI Parser:** `src/cli/cli.py`
- **Settings:** `src/utils/config.py`
- **Main Runner:** `src/main.py`
