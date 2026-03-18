# name: "execute-run.md"
# version: 1.1
# Atenção!: nunca fazer alterações

---

## 1. Objetivo

Executar todas as combinações **pendentes** de:

- runs
- variantes de modelo
- snapshots de perguntas

pertencentes a um experimento, respeitando:

- deduplicação
- retry técnico
- reexecução parcial
- imutabilidade de identidade

---

## 2. Regra de Escopo

- **Sem filtros:** executa tudo que pertence ao experimento
- **Com filtros:** executa apenas o subconjunto especificado
- **Nunca reexecuta** combinações já persistidas

📌 Execução **não cria identidade**  
📌 Execução **não altera escopo**

---

## 3. Conceitos Importantes

### Iteration Number

- `iteration_number` **não é um conceito de primeira classe**
- No modelo atual, seu valor é sempre `1`
- Existe apenas como campo técnico para compatibilidade futura
- Não representa loops, repetições ou múltiplas execuções conceituais

---

## 4. Fase A — Resolver Experimento (DB READ)

1. Buscar experimento pelo nome
2. Se não existir:
   - abortar
   - mostrar ajuda (`--create-experiment`, listar existentes)

---

## 5. Fase B — Resolver Runs (DB READ)

3. Se `--run-id` especificado:
   - carregar apenas esses runs
4. Senão:
   - carregar todos os runs do experimento
   - filtrar `status != completed`
   - ordenar por `created_at ASC`

5. Se nenhum run elegível:
   - encerrar com mensagem “Nada a executar”

---

## 6. Fase C — Resolver Modelos (DB READ)

6. Carregar **todas as variantes ativas do experimento**
7. Se filtro de modelos:
   - intersectar
8. Se vazio:
   - abortar com ajuda (`--add-model`)

📌 Runs **não possuem modelos**  
📌 Modelos pertencem exclusivamente ao experimento

---

## 7. Fase D — Resolver Perguntas (DB READ)

9. Carregar **todos os snapshots do experimento**
10. Se filtro de perguntas:
    - filtrar por `question_id`
11. Se vazio:
    - abortar com ajuda (`--add-questions`)

📌 Snapshots são **imutáveis**

---

## 8. Fase E — Construir ExecutionPlan (DB READ)

12. Para cada combinação:

```
(run_id, variant_id, snapshot_id, iteration_number)
```

13. Verificar se já existe resposta persistida:

```
WHERE run_id
  AND variant_id
  AND snapshot_id
  AND iteration_number
```

14. Se não existir:
   - incluir item no ExecutionPlan

15. Se o plano estiver vazio:
   - encerrar com mensagem “Tudo já foi processado”

📌 O ExecutionPlan é **imutável e auto‑suficiente**

---

## 9. Fase F — Execução e Coleta de Resultados

16. Inicializar:
   - ExecutionEngine (executor puro)
   - OpenRouterClient
   - Randomizer (seed do run → fallback experimento)

17. Para cada item do ExecutionPlan:
   - montar prompts efetivos (run sobrescreve experimento)
   - executar com retry técnico
   - coletar `ExecutionResult`

📌 O ExecutionEngine **não grava no banco**

---

## 10. Fase G — Persistência (ResultWriter)

18. Para cada `ExecutionResult`:
   - sucesso → persistir em `responses`
   - falha final → persistir em `errors`

19. Garantir:
   - idempotência
   - deduplicação
   - consistência de chaves

📌 Persistência é responsabilidade exclusiva do ResultWriter

---

## 11. Fase H — Finalização do Run (DB WRITE)

20. Atualizar status do run:
   - `completed` → nenhuma pendência
   - `partial_failed` → houve falhas
   - `failed` → nenhuma execução bem‑sucedida

---

## 12. Fase I — Reexecução Parcial (Opcional)

21. Se houve falhas:
   - identificar combinações pendentes
   - criar **novo ExecutionPlan** apenas com pendências
   - executar novamente

📌 Reexecução **nunca reutiliza** o plano anterior

---