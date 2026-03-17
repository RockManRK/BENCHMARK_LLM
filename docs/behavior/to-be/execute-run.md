# name: "execute_run.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

### 1. Objetivo

Executar todas as combinações pendentes de:
- runs
- variantes de modelo
- snapshots de perguntas

pertencentes a um experimento, respeitando deduplicação, retry e reexecução parcial.

---

### 2. Regra de Escopo

- **Sem filtros:** executa tudo que pertence ao experimento
- **Com filtros:** executa apenas o subconjunto especificado
- **Nunca reexecuta o que já foi processado**

---

### 3. Fase A — Resolver Experimento (DB READ)

1. Buscar experimento pelo nome
2. Se não existir:
   - abortar
   - mostrar ajuda (`--create-experiment`, listar existentes)

---

### 4. Fase B — Resolver Runs (DB READ)

3. Se `--run-id` especificado:
   - carregar apenas esses runs
4. Senão:
   - carregar todos os runs do experimento
   - filtrar `status != completed`
   - ordenar por `started_at ASC`

5. Se nenhum run elegível:
   - encerrar com mensagem “Nada a executar”

---

### 5. Fase C — Resolver Modelos (DB READ)

6. Carregar **todas as variantes do experimento**
7. Se filtro de modelos:
   - intersectar
8. Se vazio:
   - abortar com ajuda (`--add-model`)

📌 **Runs não possuem modelos.**  
📌 Modelos pertencem ao experimento.

---

### 6. Fase D — Resolver Perguntas (DB READ)

9. Carregar **todos os snapshots do experimento**
10. Se filtro de perguntas:
    - filtrar por `question_id`
11. Se vazio:
    - abortar com ajuda (`--add-questions`)

---

### 7. Fase E — Construir Plano de Execução (DB READ)

12. Para cada combinação:
```
(run_id, variant_id, snapshot_id, iteration_number)
```

13. Verificar se já existe resposta:
```
WHERE run_id
  AND variant_id
  AND snapshot_id
  AND iteration_number
```

14. Se não existir:
   - incluir no ExecutionPlan

15. Se plano vazio:
   - encerrar com mensagem “Tudo já foi processado”

---

### 8. Fase F — Execução (DB WRITE controlado)

16. Inicializar:
   - OpenRouterClient
   - Randomizer (seed do run → fallback experimento)
   - ExecutionEngine (executor puro)

17. Para cada item do plano:
   - montar prompts (run sobrescreve experimento)
   - executar com retry N
   - em sucesso:
     - salvar response
   - em falha final:
     - salvar error
     - continuar

📌 **Execução nunca cria variantes.**

---

### 9. Fase G — Finalização do Run (DB WRITE)

18. Atualizar status do run:
   - `completed` → nenhuma pendência
   - `partial_failed` → houve falhas
   - `failed` → nada executou

---

### 10. Fase H — Reexecução Parcial (Opcional)

19. Se houve falhas:
   - listar perguntas/modelos que falharam
   - oferecer reexecução
   - se aceito:
     - criar novo plano apenas com pendências
     - executar novamente

---