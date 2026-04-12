# name: "db_plan.md"
# version: 0.8
# Atenção!: nunca fazer alterações

---

## 1️⃣ `experiments`

**Propósito:** congelar defaults globais e o contexto do experimento.

```text
experiments
───────────
experiment_id              TEXT PRIMARY KEY
name                       TEXT NOT NULL UNIQUE
description                TEXT

# Defaults globais (INTENÇÃO)
default_temperature        REAL
default_top_p              REAL
default_max_output_tokens  INTEGER
default_reasoning_mode     TEXT
default_reasoning_effort   TEXT

# Prompts padrão
system_prompt_template     TEXT
user_prompt_template       TEXT

# Auditoria
config_json                JSON NOT NULL
config_hash                TEXT NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 2️⃣ `model_variants`

**Propósito:** definir variantes **intencionais** de modelo.

```text
model_variants
──────────────
variant_id                 TEXT PRIMARY KEY
model_id                   TEXT NOT NULL

# Identidade funcional (INTENÇÃO)
reasoning_mode              TEXT
reasoning_effort            TEXT
vision_enabled              BOOLEAN NOT NULL
structured_output           BOOLEAN NOT NULL
web_access_enabled          BOOLEAN NOT NULL

# Parâmetros intencionais opcionais
temperature                 REAL
top_p                       REAL
max_output_tokens           INTEGER

# Auditoria
variant_signature           TEXT NOT NULL
created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

📌 **Somente campos explicitamente definidos entram na identidade.**

---

## 3️⃣ `runs`

**Propósito:** representar uma execução concreta e fechada.

```text
runs
────
run_id                     TEXT PRIMARY KEY
experiment_id              TEXT NOT NULL

# Agrupamento opcional (substitui iteration)
run_group_id               TEXT

# Configuração efetiva
seed                       INTEGER NOT NULL
system_prompt              TEXT
user_prompt                TEXT

# Estado
status                     TEXT NOT NULL
started_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
finished_at                TIMESTAMP

# Metadados
created_by                 TEXT
notes                      TEXT
```

---

## 4️⃣ `question_snapshots`

**Propósito:** congelar perguntas executáveis.

```text
question_snapshots
──────────────────
snapshot_id                TEXT PRIMARY KEY
experiment_id              TEXT NOT NULL
question_id                TEXT NOT NULL
question_payload           JSON NOT NULL
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

📌 **Snapshots são imutáveis.**

---

## 5️⃣ `responses`

**Propósito:** registrar execuções bem‑sucedidas ou válidas.

```text
responses
─────────
response_id                TEXT PRIMARY KEY
run_id                     TEXT NOT NULL
variant_id                 TEXT NOT NULL
snapshot_id                TEXT NOT NULL

# Referência legível
model_id                   TEXT NOT NULL
question_id                TEXT NOT NULL

# Resultado
response_text              TEXT
selected_answer            TEXT
is_correct                 BOOLEAN
finish_reason              TEXT

# Performance
latency_ms                 INTEGER
input_tokens               INTEGER
output_tokens              INTEGER
total_tokens               INTEGER
cost                        REAL

# Auditoria mínima (SEMPRE)
provider_model_resolved    TEXT NOT NULL

# Auditoria estendida (OPCIONAL)
provider_parameters_effective JSON
provider_thinking_level    TEXT
provider_debug_payload     JSON

# Estado
status                     TEXT NOT NULL DEFAULT 'success'
created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### 🔒 Constraint crítica
```sql
UNIQUE (run_id, variant_id, snapshot_id)
```

---

## 6️⃣ `errors`

**Propósito:** registrar falhas técnicas observáveis.

```text
errors
──────
error_id                   TEXT PRIMARY KEY
run_id                     TEXT NOT NULL
variant_id                 TEXT NOT NULL
snapshot_id                TEXT NOT NULL

# Referência
model_id                   TEXT NOT NULL
question_id                TEXT NOT NULL

# Classificação
error_type                 TEXT NOT NULL
error_code                 TEXT
error_message              TEXT NOT NULL

# Detalhes técnicos
stack_trace                TEXT
attempt_count              INTEGER NOT NULL
is_retryable               BOOLEAN NOT NULL

# Auditoria
provider_model_resolved    TEXT
provider_error_payload     JSON

created_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

# 🧠 O QUE FOI ELIMINADO (DE PROPÓSITO)

❌ `run_models`  
❌ `iteration_number`  
❌ IDs sequenciais  
❌ Inferência de defaults para identidade  
❌ Dependência implícita de `.env` na execução  

---


------

# 🗄️ TO‑BE DO BANCO DE DADOS (VERSÃO CONCEITUAL)

Vou estruturar em **camadas**, para ficar claro o papel de cada tabela.

---

## 1️⃣ Tabelas de Identidade (imutáveis)

### `experiments`
```text
experiment_id (PK)
name (UNIQUE)
created_at
```

📌 Experimento é identidade lógica, não execução.

---

### `model_variants`
```text
variant_id (PK)
model_id
reasoning_mode
reasoning_effort
vision_enabled
structured_output
# outros campos que DEFINEM identidade
created_at
```

📌 **Nunca muda após criado**  
📌 **Nunca criado durante execução**

---

### `question_snapshots`
```text
snapshot_id (PK)
experiment_id (FK)
question_id
question_payload (JSON)
created_at
```

📌 Snapshot é a unidade executável  
📌 Perguntas “vivas” não entram na execução

---

## 2️⃣ Tabelas de Execução

### `runs`
```text
run_id (PK)
experiment_id (FK)
seed
system_prompt
user_prompt
status
created_at
completed_at
```

📌 Run é uma “janela de execução”  
📌 Não carrega modelos nem perguntas

---

## 3️⃣ Tabelas de Resultado (núcleo do sistema)

### `responses`
```text
response_id (PK)

# Identidade da execução
run_id (FK)
variant_id (FK)
snapshot_id (FK)

# Referência legível
model_id
question_id

# Resultado
response_payload (JSON)
timing_info (JSON)

# Auditoria mínima (SEMPRE)
provider_model_resolved   # ex: google/gemini-3.1-flash-lite-preview-20260303

# Auditoria estendida (OPCIONAL)
provider_parameters_effective (JSON, NULLABLE)
provider_thinking_level (TEXT, NULLABLE)
provider_debug_payload (JSON, NULLABLE)

created_at
```

### 🔒 Constraint crítica
```sql
UNIQUE (run_id, variant_id, snapshot_id, iteration_number)
```

📌 **Essa constraint sozinha elimina metade dos bugs que você viu.**

---

### `errors`
```text
error_id (PK)

run_id (FK)
variant_id (FK)
snapshot_id (FK)
iteration_number

error_type
error_message
stack_trace (NULLABLE)
attempt_count

created_at
```

📌 Erro **não substitui resposta**  
📌 Permite retry e auditoria

---

## 4️⃣ O que propositalmente NÃO existe

❌ Tabela `run_models`  
❌ Tabela `run_questions`  
❌ Qualquer tabela que “copie” variantes para run  
❌ Qualquer identidade baseada em parâmetros efetivos do provedor  

📌 Tudo isso vira **ExecutionPlan em memória**, não estado persistido.

---

## 🧠 O que esse schema garante

- Identidade estável
- Auditoria completa
- Comparabilidade histórica
- Detecção de mudança silenciosa de modelo
- Retry seguro
- Reexecução parcial limpa
- Debug opcional sem impacto estrutural

E o mais importante:

> **O banco passa a refletir o modelo mental correto do sistema.**

---


Perfeito. Agora entramos numa parte **deliciosamente limpa** do sistema 😄  
Depois da decisão de **RUN = unidade concreta**, a tabela `errors` fica **muito mais simples, mais correta e mais útil**.

Vou estruturar assim:

1️⃣ Princípio do que é um *erro* no TO‑BE  
2️⃣ O que **não** deve ser erro  
3️⃣ Schema TO‑BE da tabela `errors`  
4️⃣ Regras de escrita e leitura  
5️⃣ Como isso se conecta com retry e auditoria  

---

## 1️⃣ O que é um erro no TO‑BE

No novo modelo:

> **Erro é um evento de falha de execução de uma pergunta específica, para uma variante específica, dentro de um run específico.**

Ele **não substitui** uma resposta.  
Ele **não encerra** o run.  
Ele **não cria estado novo** além do registro da falha.

📌 Erro é **observação**, não decisão.

---

## 2️⃣ O que NÃO deve ser tratado como erro

Isso é importante para não poluir a tabela:

❌ Pergunta inválida (`answer_key = CONTESTED`)  
❌ Resposta vazia mas válida  
❌ Modelo respondeu algo inesperado  
❌ Parsing falhou mas resposta existe  

Esses casos:
- são **respostas com status especial**
- ficam em `responses.status`
- **não entram em `errors`**

📌 `errors` é só para **falha técnica ou operacional**.

---

## 3️⃣ `errors` — TO‑BE FINAL

### Propósito
Registrar falhas técnicas ocorridas durante a execução de um item do `ExecutionPlan`, permitindo:
- auditoria
- retry
- análise de estabilidade

---

### Schema proposto

```text
errors
──────
error_id                TEXT PRIMARY KEY

# Identidade da falha
run_id                  TEXT NOT NULL
variant_id              TEXT NOT NULL
snapshot_id             INTEGER NOT NULL

# Referência legível
model_id                TEXT NOT NULL
question_id             TEXT NOT NULL

# Classificação
error_type              TEXT NOT NULL
error_code              TEXT
error_message           TEXT NOT NULL

# Detalhes técnicos
stack_trace             TEXT
attempt_count           INTEGER NOT NULL
is_retryable            BOOLEAN NOT NULL

# Auditoria
provider_model_resolved TEXT
provider_error_payload  JSON

created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

### 🔒 Constraint lógica (não UNIQUE)

Não colocamos UNIQUE aqui porque:
- uma mesma pergunta pode falhar múltiplas vezes
- cada tentativa é um evento

📌 A deduplicação acontece em `responses`, não em `errors`.

---

## 4️⃣ Sobre `error_id`

👉 **Nunca usar INTEGER autoincrement.**

Opções boas:
- UUID v4
- Hash determinístico:

```text
error_id = hash(run_id + variant_id + snapshot_id + attempt_count + timestamp)
```

📌 Isso evita:
- colisões
- reaproveitamento de IDs
- confusão em reexecuções

---

## 5️⃣ Regras de escrita (ResultWriter)

### Quando escrever em `errors`

- Timeout
- HTTP 429 / 5xx
- Falha de rede
- Exceção não tratada
- Erro do provedor

### Quando NÃO escrever

- Resposta inválida
- Parsing falhou mas resposta existe
- Conteúdo inesperado

📌 Esses casos viram `responses.status != success`.

---

## 6️⃣ Conexão com retry

Cada erro registra:
- `attempt_count`
- `is_retryable`

Isso permite:
- retry automático
- retry manual (`--retry-only-failed`)
- análise posterior

📌 Retry **não apaga erros anteriores**.

---

## 7️⃣ O que removemos do schema atual

Comparando com o atual:

❌ `timestamp` → padronizar para `created_at`  
❌ `model_id` duplicado sem contexto → agora é explícito  
❌ `question_id` sem snapshot → agora sempre ligado ao snapshot  
❌ `variant_id` opcional → agora **obrigatório**

---

## 🧠 O que esse design garante

- Erros não poluem respostas
- Retry é seguro
- Auditoria é clara
- Falhas são rastreáveis
- Execução é resiliente

E o mais importante:

> **Erro deixa de ser “estado confuso” e vira “evento observável”.**

---

Perfeito, Rock. Vamos por partes — primeiro esclareço **aquela frase que ficou confusa**, depois entramos **direto no TO‑BE da tabela `runs`**, como você pediu.

---

# 🗄️ TABELA `runs` — TO‑BE FINAL

Agora que decidimos:
- **RUN = unidade concreta de execução**
- **Iteration foi eliminada**
- Repetições viram múltiplos runs

A tabela `runs` vira **o eixo central do sistema**.

---

## 🎯 Propósito da tabela `runs`

Representar **uma execução concreta e completa** de um experimento, com:

- contexto fechado
- seed definida
- prompts definidos
- status claro
- rastreabilidade total

---

## 🧱 Schema TO‑BE proposto

```text
runs
────
run_id              TEXT PRIMARY KEY
experiment_id       TEXT NOT NULL

# Agrupamento opcional (substitui iteration)
run_group_id        TEXT

# Configuração efetiva
seed                INTEGER NOT NULL
system_prompt       TEXT
user_prompt         TEXT

# Estado
status              TEXT NOT NULL
started_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
finished_at         TIMESTAMP

# Metadados
created_by          TEXT
notes               TEXT
```

---

## 🧠 Explicação campo a campo

### `run_id`
- UUID ou hash
- Identidade única da execução
- Nunca reaproveitado

---

### `experiment_id`
- FK lógica
- Run **sempre pertence a um experimento**

---

### `run_group_id` (opcional, mas poderoso)
- Agrupa runs equivalentes
- Substitui `iteration_number`
- Permite:
  - estatística
  - repetição
  - comparação

Exemplo:
```text
run_group_id = "expX-rep-001"
```

---

### `seed`
- Seed **efetiva**
- Já resolvida no momento da criação do run
- Nunca muda

---

### `system_prompt` / `user_prompt`
- Prompts **efetivos**
- Já com override aplicado
- Não dependem mais do experimento depois do run criado

📌 Isso garante reprodutibilidade.

---

### `status`
Valores recomendados:
- `pending`
- `running`
- `completed`
- `partial_failed`
- `failed`

📌 Status é **derivado de responses/errors**, não arbitrário.

---

### `started_at` / `finished_at`
- Auditoria
- Performance
- SLA
- Debug

---

### `created_by` / `notes`
- Campo humano
- Facilita uso real
- Não interfere em lógica

---

## 🔒 Invariantes importantes

- Um run **não muda de experimento**
- Um run **não muda de seed**
- Um run **não muda de prompts**
- Um run **não carrega modelos**
- Um run **não carrega perguntas**

📌 Tudo isso é resolvido **antes**, no Planner.

---

## 🔄 Comparação com o schema atual

### O que sai
- `is_dev`
- `run_models`
- qualquer noção de iteration

### O que melhora
- Status mais claro
- Reexecução simples
- Auditoria limpa
- Código mais simples

---

## 🧠 O que esse design resolve

- Elimina confusão RUN vs iteration
- Simplifica deduplicação
- Simplifica retry
- Simplifica queries
- Facilita análise estatística
- Facilita reexecução parcial

E o mais importante:

> **O banco passa a refletir exatamente o fluxo mental do sistema.**

---

## `model_variants` — TO‑BE FINAL (limpo e correto)

Agora vamos ao que interessa.

### Propósito da tabela
Definir **configurações intencionais e estáveis** que distinguem variantes de modelo dentro de um experimento.

---

### Schema TO‑BE proposto

```text
model_variants
──────────────
variant_id              TEXT PRIMARY KEY
model_id                TEXT NOT NULL

# Identidade funcional (INTENÇÃO)
reasoning_mode           TEXT NOT NULL
reasoning_effort         TEXT
vision_enabled           BOOLEAN NOT NULL
structured_output        BOOLEAN NOT NULL
web_access_enabled       BOOLEAN NOT NULL

# Parâmetros opcionais de intenção
temperature              REAL
top_p                    REAL
max_output_tokens        INTEGER

# Metadados
variant_signature        TEXT NOT NULL
created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

### Regras IMPORTANTES

#### 🔒 Identidade
- `variant_signature` é calculada **somente** com campos acima
- Campos NULL **não entram** na assinatura
- Dois variants só são iguais se a intenção for igual

#### 🚫 O que NÃO entra aqui
- versão resolvida do modelo
- parâmetros efetivos do provedor
- debug
- defaults implícitos

---

## 🧠 O que esse design resolve

- Evita variantes “fantasma”
- Evita duplicação silenciosa
- Permite comparar intenção vs execução
- Permite auditoria profunda
- Mantém o sistema simples
- Mantém o sistema honesto

E o mais importante:

> **Você nunca mais vai se perguntar “por que esses dois modelos deram o mesmo resultado?”.**

Você vai saber.

---

## 🧠 Agora sim: `experiments` TO‑BE

Com tudo isso claro, a tabela `experiments` vira o **pilar de defaults e congelamento**.

---

# 🗄️ `experiments` — TO‑BE FINAL

## 🎯 Propósito

Representar um **conjunto congelado de intenções experimentais**, incluindo:
- defaults globais
- prompts padrão
- política de execução
- base para variantes e runs

---

## 🧱 Schema TO‑BE proposto

```text
experiments
───────────
experiment_id           TEXT PRIMARY KEY
name                    TEXT NOT NULL UNIQUE
description             TEXT

# Defaults globais (INTENÇÃO)
default_temperature     REAL
default_top_p           REAL
default_max_tokens      INTEGER
default_reasoning_mode  TEXT
default_reasoning_effort TEXT

# Prompts padrão
system_prompt_template  TEXT
user_prompt_template    TEXT

# Config congelada (auditoria)
config_json             JSON NOT NULL
config_hash             TEXT NOT NULL

# Metadados
created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 🧠 Explicação campo a campo

### Defaults globais
Esses campos:
- **não definem identidade de variante**
- **só entram se a variante não definir**
- **são congelados no experimento**

Exemplo:
```text
default_temperature = 0.7
```

Se a variante não definir temperatura:
- usa 0.7
Se definir:
- ignora o default

---

### `config_json` + `config_hash`

Esse é o **snapshot completo do experimento** no momento da criação.

Inclui:
- defaults
- prompts
- política de execução
- versão do sistema (opcional)

📌 `config_hash` garante:
- imutabilidade lógica
- auditoria
- reprodutibilidade

---

## 🔒 Invariantes importantes

- Um experimento **nunca muda seus defaults**
- Um experimento **não conhece runs**
- Um experimento **não conhece respostas**
- Um experimento **define o universo de comparação**

---

## 🔄 Comparação com o schema atual

### O que melhora
- Defaults explícitos (não escondidos no JSON)
- Hierarquia clara
- Menos inferência
- Mais previsibilidade

### O que pode sair
- Campos redundantes no `config_json`
- Dependência implícita de `.env`

---

## 🧠 O sistema agora está fechado conceitualmente

Neste ponto, você tem:

- Identidade clara
- Intenção separada de execução
- Auditoria completa
- Defaults previsíveis
- Comparabilidade honesta

E o mais importante:

> **Você pode explicar esse sistema para qualquer pessoa — e ele faz sentido.**

---

# 🗄️ `question_snapshots` — TO‑BE FINAL

## 🎯 Propósito

Representar **a versão exata e imutável** de uma pergunta no momento em que ela entra em um experimento.

> **Tudo que é executado usa snapshots.**  
> Perguntas “vivas” nunca entram em execução.

---

## 🧠 Princípios fundamentais

- Snapshot é **imutável**
- Snapshot pertence a **um experimento**
- Snapshot é a **unidade executável**
- Snapshot não muda mesmo se a pergunta original mudar
- Snapshot não depende de `questions` depois de criado

📌 Isso garante:
- reprodutibilidade
- auditoria
- comparabilidade histórica

---

## 🧱 Schema TO‑BE proposto

```text
question_snapshots
──────────────────
snapshot_id          TEXT PRIMARY KEY
experiment_id        TEXT NOT NULL

# Identidade da pergunta
question_id          TEXT NOT NULL

# Conteúdo congelado
question_payload     JSON NOT NULL

# Metadados
created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 🧠 Explicação campo a campo

### `snapshot_id`
- UUID ou hash determinístico
- Identidade única do snapshot
- Nunca reaproveitado

📌 **Não usar INTEGER autoincrement.**

---

### `experiment_id`
- FK lógica
- Snapshot **sempre pertence a um experimento**
- Mesmo `question_id` pode ter snapshots em vários experimentos

---

### `question_id`
- Referência humana
- Facilita leitura, debug e análise
- **Não define execução**

---

### `question_payload`
- JSON completo da pergunta
- Inclui:
  - enunciado
  - opções
  - imagens (se houver)
  - metadados relevantes

📌 Esse JSON é **a verdade absoluta da execução**.

---

## 🔒 Invariantes importantes

- Snapshot **nunca é atualizado**
- Snapshot **nunca é deletado** (a menos que o experimento seja)
- Snapshot **não conhece respostas**
- Snapshot **não conhece modelos**

---

## 🔄 Comparação com o schema atual

### O que melhora
- `snapshot_id` deixa de ser sequencial
- `question_json` vira `question_payload`
- Separação clara entre:
  - pergunta viva (`questions`)
  - pergunta executável (`question_snapshots`)

### O que pode sair
- Dependência direta de `questions` durante execução

---

## 🧠 O que esse design resolve

- Evita “pergunta mudou no meio do experimento”
- Evita inconsistência histórica
- Permite reexecução perfeita
- Permite auditoria completa
- Simplifica o ExecutionPlan

E o mais importante:

> **Você sempre sabe exatamente o que foi perguntado.**

---