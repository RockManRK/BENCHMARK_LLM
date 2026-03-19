# name: "execution-engine.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## ExecutionEngine — Contrato TO‑BE

### 1. Propósito

Executar chamadas à API de LLM para um conjunto **pré‑resolvido** de tarefas, retornando resultados ou erros, **sem tomar decisões de escopo ou identidade**.

---

### 2. Responsabilidades (O QUE FAZ)

O ExecutionEngine é responsável por:

- Executar chamadas à API de LLM
- Aplicar política de retry técnico
- Processar respostas brutas
- Retornar sucesso ou falha por tarefa
- Emitir eventos/resultados para persistência externa

---

### 3. Não‑Responsabilidades (O QUE NÃO FAZ)

O ExecutionEngine **NUNCA** deve:

- Criar ou modificar `model_variants`
- Resolver identidade de variantes
- Decidir quais perguntas executar
- Verificar se algo já foi respondido
- Ler ou escrever diretamente no banco de dados
- Inferir configurações a partir de settings globais
- Conhecer conceitos como:
  - Experimento
  - Run
  - Snapshot
  - Deduplicação

📌 **Qualquer tentativa de fazer isso é bug arquitetural.**

---

### 4. Entrada Esperada

O ExecutionEngine recebe **apenas** um `ExecutionPlan` já resolvido.

#### Estrutura conceitual do ExecutionPlan

```text
ExecutionPlan
- run_id
- experiment_id
- seed
- system_prompt
- user_prompt
- retry_policy
- steps:
    - variant_id
      model_id
      model_config
      questions:
        - snapshot_id
          question_payload
```

📌 O plano é:
- Imutável
- Completo
- Auto‑suficiente
- Serializável

---

### 5. Fluxo Interno de Execução

Para cada `step` do plano:

1. Montar payload da API usando:
   - model_id
   - model_config
   - prompts já resolvidos
   - question_payload

2. Executar chamada à API
3. Aplicar retry conforme política
4. Emitir resultado:
   - `Success(result_payload)`
   - `Failure(error_payload)`

📌 O engine **não persiste nada**.

---

### 6. Política de Retry

- Retry é **técnico**, não lógico
- Exemplo:
  - Timeout
  - Erro 5xx
  - Falha transitória de rede

- Retry **não**:
  - Recria variantes
  - Altera identidade
  - Duplica respostas

---

### 7. Saída Esperada

O ExecutionEngine retorna uma coleção de resultados:

```text
ExecutionResult
- run_id
- variant_id
- snapshot_id
- status: success | failure
- payload | error
- timing_info
```

📌 Persistência é responsabilidade de outro componente.

---

### 8. Invariantes Arquiteturais

- ExecutionEngine é **stateless**
- ExecutionEngine é **determinístico** dado o mesmo plano
- ExecutionEngine é **testável sem banco**
- ExecutionEngine é **reutilizável fora do CLI**

---