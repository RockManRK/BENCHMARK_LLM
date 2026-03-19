# name: "execution-plan.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

### 1. Propósito

O **ExecutionPlan** é uma representação **imutável e auto-suficiente** do trabalho a executar.  
Ele contém tudo que o ExecutionEngine precisa para rodar—e nada que permita “inferir” ou “resolver” coisas durante a execução.

---

### 2. Princípios invariantes

- **Plano é imutável:** depois de criado, não muda.
- **Plano é completo:** não depende de settings globais para identidade/config.
- **Plano é auditável:** pode ser salvo/serializado para reproduzir execução.
- **Plano não decide:** decisões (escopo/deduplicação) acontecem antes, no Planner.
- **Plano não cria identidade:** `variant_id` e `snapshot_id` já vêm resolvidos.
- **Plano não acessa DB:** DB é responsabilidade do Planner (leitura) e Writer (escrita).
- **All model behavior-affecting parameters** (e.g. temperature, top_p, max_output_tokens) MUST be resolved by the Planner and included in model_config_effective. ExecutionEngine MUST NOT assume defaults.”

---

### 3. Responsabilidades por componente

| Componente | Responsabilidade |
|---|---|
| **Planner** | Resolve experimento/runs/modelos/perguntas, aplica filtros, deduplica, monta o ExecutionPlan |
| **ExecutionEngine** | Executa cada item do plano com retry técnico e retorna resultados |
| **ResultWriter** | Persiste `responses`/`errors`, atualiza status de run, sem decidir escopo |

---

### 4. Estrutura do ExecutionPlan

#### 4.1 Campos obrigatórios

- **plan_id:** identificador único do plano (ex: timestamp + hash)
- **created_at:** quando o plano foi gerado
- **experiment_id:** id do experimento
- **runs:** lista de runs a executar (ordem definida pelo Planner)

#### 4.2 Estrutura por run

Cada run no plano deve conter:

- **run_id**
- **seed_effective:** seed final já resolvida (run → fallback experimento)
- **prompts_effective:** prompts finais já resolvidos (run sobrescreve experimento)
- **variants:** variantes a executar (já resolvidas por `variant_id`)
- **items:** lista plana (ou agrupada) de tarefas executáveis

---

### 5. Modelo de dados recomendado em YAML

**model_config_effective MUST include all parameters that affect model behavior, including sampling parameters such as temperature and top_p.**

> **Nota:** YAML aqui é o “contrato legível” para IA/humanos. O código pode usar dataclasses/JSON, mas deve ser isomórfico.

```yaml
plan_id: "plan-20260317-0045-abc123"
created_at: "2026-03-17T00:45:00-03:00"

experiment:
  experiment_id: "exp-a68530c1"
  name: "oitteste"

defaults:
  # Já resolvidos pelo Planner (não usar settings globais na execução)
  seed_default: 123
  prompts_default:
    system: "..."
    user: "..."

runs:
  - run_id: "run-20260315222541-f47e3c31"
    status_at_planning: "running"

    seed_effective: 42
    prompts_effective:
      system: "..."
      user: "..."

    retry_policy:
      max_attempts: 3
      backoff: "exponential"
      retry_on:
        - timeout
        - http_429
        - http_5xx
        - network_error

    variants:
      - variant_id: "var-5eb0bdca"
        model_id: "google/gemini-3.1-flash-lite-preview"
        model_config_effective:
          temperature: 0.7
          top_p: 0.95
          max_output_tokens: 1024
          enable_vision: true
          structured_output: false
          reasoning_mode: "off"
          reasoning_effort: null
          # + quaisquer outros campos que definem identidade/comportamento

      - variant_id: "var-93517b5b"
        model_id: "google/gemini-3.1-flash-lite-preview"
        model_config_effective:
          enable_vision: true
          structured_output: false
          reasoning_mode: "effort"
          reasoning_effort: "low"

    items:
      - item_id: "run-...::var-5eb0bdca::snap-55::it-1"
        run_id: "run-20260315222541-f47e3c31"
        variant_id: "var-5eb0bdca"
        model_id: "google/gemini-3.1-flash-lite-preview"

        snapshot_id: 55
        question_id: "Q055"
        
        question_payload:
          # snapshot JSON já carregado e validado pelo Planner
          stem: "..."
          options: ["A ...", "B ...", "C ...", "D ..."]
          answer_key: "CONTESTED"  # permitido existir; política definida fora do Engine

      - item_id: "run-...::var-93517b5b::snap-1::it-1"
        run_id: "run-20260315222541-f47e3c31"
        variant_id: "var-93517b5b"
        model_id: "google/gemini-3.1-flash-lite-preview"
        snapshot_id: 1
        question_id: "Q001"
        question_payload: { ... }
```

---

### 6. Regras de validade do plano

O Planner **só pode emitir** um plano válido se:

- **Toda `variant_id` existe no DB** (e pertence ao experimento)
- **Todo `snapshot_id` existe no DB** (e pertence ao experimento)
- **Todo `run_id` pertence ao experimento**
- **`items` não contém duplicatas** pela chave:
  - `run_id + variant_id + snapshot_id`
- **`model_config_effective` está resolvida** (sem depender de settings globais)

---

### 7. Interface do ExecutionEngine com o plano

O ExecutionEngine recebe:

- **um run do plano por vez** (recomendado) ou o plano inteiro
- executa `items` na ordem fornecida
- retorna `ExecutionResult[]` com a mesma chave do item

**O Engine não pode:**
- filtrar items
- criar items
- reordenar por conta própria
- “resolver” config faltante

---

### 8. Saída esperada por item

Cada item gera exatamente um resultado:

- **success:** payload + metadados (latência, tokens, etc.)
- **failure:** erro normalizado + metadados (tentativas, última exceção, etc.)

O Writer decide como persistir (ex: `responses` e `errors`), mas **não decide escopo**.

---