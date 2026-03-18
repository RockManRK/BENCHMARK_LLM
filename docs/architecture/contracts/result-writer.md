# name: "result-writer.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## ResultWriter — Contrato TO‑BE

### 1. Propósito

Persistir os resultados da execução de um `ExecutionPlan` no banco de dados, garantindo:

- integridade
- deduplicação
- consistência de status
- suporte a reexecução parcial

O ResultWriter **não executa**, **não decide escopo** e **não cria identidade**.

---

### 2. Responsabilidades (O QUE FAZ)

O ResultWriter é responsável por:

- Persistir resultados de execução (`responses`)
- Persistir falhas (`errors`)
- Atualizar status de runs
- Registrar metadados de execução
- Suportar reexecução parcial baseada em falhas

---

### 3. Não‑Responsabilidades (O QUE NÃO FAZ)

O ResultWriter **NUNCA** deve:

- Executar chamadas à API
- Criar ou modificar `model_variants`
- Resolver quais perguntas executar
- Inferir configuração de modelo
- Reordenar execução
- Reexecutar automaticamente tarefas

📌 Ele **apenas grava o que aconteceu**.

---

### 4. Entrada Esperada

O ResultWriter recebe uma coleção de `ExecutionResult` produzidos pelo ExecutionEngine.

#### Estrutura conceitual do ExecutionResult

```text
ExecutionResult
- run_id
- variant_id
- model_id
- snapshot_id
- question_id
- iteration_number
- status: success | failure
- payload | error
- timing_info
- attempt_count
```

📌 Cada resultado corresponde **exatamente a um item do ExecutionPlan**.

---

### 5. Persistência de Sucesso

Para cada `ExecutionResult` com `status = success`:

#### DB WRITE — `responses`

Campos mínimos recomendados:

```text
responses
- response_id (PK)
- run_id
- variant_id
- model_id
- snapshot_id
- question_id
- iteration_number
- response_payload
- timing_info
- created_at
```

📌 **Chave lógica de unicidade:**

```
(run_id, variant_id, snapshot_id, iteration_number)
```

📌 Se já existir:
- **NÃO sobrescrever**
- **NÃO duplicar**
- Registrar como “já persistido” (idempotência)

---

### 6. Persistência de Falha

Para cada `ExecutionResult` com `status = failure`:

#### DB WRITE — `errors`

Campos mínimos recomendados:

```text
errors
- error_id (PK)
- run_id
- variant_id
- snapshot_id
- iteration_number
- error_type
- error_message
- stack_trace (opcional)
- attempt_count
- created_at
```

📌 Falhas **não impedem** persistência de outros resultados.

---

### 7. Atualização de Status do Run

Após persistir todos os resultados de um run:

#### Regras de status

| Condição | Status |
|--------|--------|
| Nenhuma pendência, nenhuma falha | `completed` |
| Algumas falhas, mas houve sucesso | `partial_failed` |
| Todas falharam | `failed` |
| Ainda há itens pendentes | `running` |

📌 O ResultWriter **não cria novos runs**.

---

### 8. Suporte a Reexecução Parcial

O ResultWriter deve permitir identificar **pendências** com base em:

```text
Itens do ExecutionPlan
MENOS
Itens com response persistida
```

Isso permite:

- `--retry-only-failed`
- reexecução manual
- auditoria clara

📌 Reexecução **sempre gera um novo ExecutionPlan**.

---

### 9. Invariantes Arquiteturais

- ResultWriter é **idempotente**
- ResultWriter é **determinístico**
- ResultWriter não depende de settings globais
- ResultWriter não conhece ExecutionEngine
- ResultWriter não conhece CLI

---