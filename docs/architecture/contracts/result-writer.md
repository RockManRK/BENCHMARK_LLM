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
- response_payload
- timing_info
- created_at
```

📌 **Chave lógica de unicidade:**

```
(run_id, variant_id, snapshot_id)
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
- error_type
- error_message
- stack_trace (opcional)
- attempt_count
- created_at
```

📌 Falhas **não impedem** persistência de outros resultados.

---

### 7. Atualização de Status do Run

#### Ciclo de vida completo do status

| Status | Quando ocorre | Transição seguinte |
|--------|---------------|-------------------|
| `pending` | Run criado pelo `--create-run` | → `running` (quando Planner emite ExecutionPlan) |
| `running` | ExecutionPlan emitido, execução em andamento | → `completed`, `partial_failed`, ou `failed` |
| `completed` | Todos os items processados com sucesso | (terminal) |
| `partial_failed` | Alguns items falharam, outros succeeded | → `running` (reexecução parcial) |
| `failed` | Todos os items falharam | → `running` (reexecução) |

#### Regras de atualização (após persistir resultados)

| Condição | Status |
|--------|--------|
| Nenhuma pendência, nenhuma falha | `completed` |
| Algumas falhas, mas houve sucesso | `partial_failed` |
| Todas falharam | `failed` |
| Ainda há itens pendentes | `running` |

📌 O ResultWriter **não cria novos runs**.

📌 **Transição `pending` → `running`**: Ocorre quando o Planner emite o ExecutionPlan com sucesso. Se o Planner falhar (ex: sem modelos, sem snapshots), o run permanece `pending` até que as condições sejam resolvidas.

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

### 10. Campos de Review (Manual Review Workflow)

O ResultWriter é responsável por calcular e persistir campos relacionados ao review manual de respostas.

#### Campos de review na tabela `responses`

| Campo | Tipo | Quem define | Quando |
|-------|------|-------------|--------|
| `parse_confidence` | TEXT | ExecutionEngine | Durante parsing da resposta |
| `selected_answer` | TEXT | ExecutionEngine | Durante parsing da resposta |
| `needs_review` | BOOLEAN | **ResultWriter** (derivado) | Antes do INSERT |
| `manual_answer` | TEXT | Reviewer humano | Pós-execução (opcional) |

#### Regra de cálculo: `needs_review`

O ResultWriter **calcula** `needs_review` antes de persistir:

```python
needs_review = (
    parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
    OR selected_answer IS NULL
)
```

| `parse_confidence` | `selected_answer` | `needs_review` |
|--------------------|-------------------|----------------|
| `'clear'` | não-NULL | FALSE |
| `'ambiguous'` | qualquer | TRUE |
| `'no_answer'` | qualquer | TRUE |
| `'low_confidence'` | qualquer | TRUE |
| qualquer | NULL | TRUE |

📌 **Importante**: O ExecutionEngine retorna `parse_confidence` e `selected_answer`. O ResultWriter **deriva** `needs_review` antes do INSERT. O campo `is_correct` é derivado em query-time baseado em `manual_answer` (se existir) ou `selected_answer`.

📄 Ver: `docs/architecture/contracts/domain-review-contract.md`

---