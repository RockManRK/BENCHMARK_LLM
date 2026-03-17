# name: "db_plan.md"
# version: 0.8
# Atenção!: nunca fazer alterações

---

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
iteration_number

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