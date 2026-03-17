Perfeito—vamos fazer isso do jeito “à prova de IA do VSC”: **ordem clara, entregáveis pequenos, e cada passo fechando uma ambiguidade**. E sim, já começamos o primeiro agora.

---

## Plano de ataque em ordem

### 1. Congelar o diagnóstico
- **Entregável:** `docs/behavior/EXECUTIVE-SUMMARY.md` e `investigation-report.md` ficam como **evidência histórica**.
- **Regra:** daqui pra frente, tudo novo vai para **TO‑BE** (não misturar).

---

### 2. Definir contratos TO‑BE do núcleo
- **Entregáveis:**
  - `docs/behavior/to-be/execute-run.md` (fluxo e decisões)
  - `docs/architecture/to-be/execution-engine.md` (responsabilidades e limites)
  - `docs/architecture/to-be/execution-plan.md` (estrutura do plano)
- **Objetivo:** tirar “poder” do ExecutionEngine e impedir criação de variantes na execução.

---

### 3. Ajustar o modelo de dados mínimo necessário
- **Entregáveis:**
  - `docs/db/to-be/uniqueness-and-keys.md` (chaves de deduplicação e constraints)
  - Migração(s) (se necessário)
- **Objetivo:** garantir que “já respondido” seja calculado com a chave correta.

---

### 4. Implementar correções críticas (em trilhas pequenas)
- **Trilha A:** execução **nunca** cria `model_variants`
- **Trilha B:** deduplicação correta (pendências por `run_id + variant_id + snapshot_id + iteration`)
- **Trilha C:** retry + reexecução parcial (somente pendências)
- **Trilha D:** status de run (ex: `running`, `completed`, `partial_failed`, `failed`)

---

### 5. Testes que realmente protegem
- **Unitários:** Planner / deduplicação / normalização de identidade
- **Integração (real OpenRouter):** 1–2 perguntas, modelo barato, 1 iteração
- **Objetivo:** impedir regressão dos bugs que você encontrou.

---

### 6. Diagramas “mapa para IA”
- **Entregáveis:**
  - `docs/diagrams/to-be/execute-run.mmd` (Mermaid)
  - `docs/diagrams/to-be/execute-run.yaml` (contrato de decisão)
- **Objetivo:** IA entender rápido e implementar sem inventar.

---

# Passo 1 agora: começar o TO‑BE do `--execute-run`

Abaixo vai uma **primeira versão TO‑BE** (bem “contrato”), já com **momentos explícitos de leitura/escrita no DB**, e já alinhada com suas definições (Experiment/Run/Model). Você pode colar isso num arquivo e ir refinando.

## `docs/behavior/to-be/execute-run.md` (primeiro rascunho)

### 1. Objetivo
Executar perguntas pendentes para um ou mais runs de um experimento, para um conjunto de variantes e snapshots, persistindo respostas/erros com deduplicação correta e suporte a retry/reexecução parcial.

### 2. Princípios invariantes
- **Execução nunca cria `model_variants`.**
- **Identidade de execução é sempre `variant_id` (não `model_id`).**
- **Snapshots são a unidade de pergunta executável** (não o JSON “vivo”).
- **Deduplicação usa chave completa**: `run_id + variant_id + snapshot_id + iteration_number`.
- **Planner decide o escopo; Engine apenas executa.**

### 3. Entradas e flags
- **Obrigatório:** `--experiment <name>`
- **Opcional:** `--run-id <id>` (um ou mais) ou “modo padrão”
- **Opcional:** `--models <variant_id...>` (ou alias/índice, mas resolve para `variant_id`)
- **Opcional:** `--questions <Qxxx...>` (resolve para `snapshot_id`)
- **Opcional:** `--retry <n>` (padrão 3)
- **Opcional:** `--retry-only-failed` (reexecuta apenas falhas registradas)
- **Opcional:** `--dry-run` (mostra plano, não executa)

### 4. Fase A — Resolver experimento e runs (somente leitura)
1. **DB READ:** buscar experimento por nome.
   - Se não existir: abortar com ajuda (`--create-experiment`, listar existentes).
2. **Resolver runs alvo:**
   - Se `--run-id` informado:
     - **DB READ:** buscar runs por id e validar pertencimento ao experimento.
   - Senão:
     - **DB READ:** listar runs do experimento.
     - Selecionar **o mais antigo não-completo** (ou todos não-completos, se você preferir—definir aqui).
3. Se nenhum run elegível: encerrar com mensagem “nada a executar”.

### 5. Fase B — Resolver modelos e perguntas (somente leitura)
4. **Modelos (sempre do experimento):**
   - **DB READ:** carregar variantes associadas ao experimento.
   - Se filtro de modelos: intersectar.
   - Se vazio: abortar com ajuda (`--add-model`, listar modelos do experimento).
5. **Perguntas (sempre snapshots do experimento):**
   - **DB READ:** carregar snapshots do experimento.
   - Se filtro de perguntas: filtrar por question_id e mapear para snapshot_id.
   - Se vazio: abortar com ajuda (`--add-questions`, listar perguntas do experimento).

### 6. Fase C — Construir plano de execução (somente leitura)
6. Para cada `(run_id, variant_id, snapshot_id, iteration_number)`:
   - **DB READ:** verificar se já existe response (ou “resultado final”) para essa chave.
   - Se existe: não incluir no plano.
   - Se não existe: incluir no plano.
7. Se plano vazio: encerrar com “tudo já executado”.

> **Nota:** aqui é onde a deduplicação correta vive—não dentro do Engine.

### 7. Fase D — Executar plano (escrita controlada)
8. Inicializar:
   - API client (OpenRouter)
   - Randomizer (seed do run; fallback seed do experimento se run não tiver)
   - ExecutionEngine (executor puro)
9. Para cada item do plano:
   - Montar prompts:
     - **System/User do run** sobrescrevem os do experimento
     - Config do modelo = variante (com fallback para defaults do experimento apenas onde fizer sentido e estiver definido)
   - Chamar API com **retry N** (exponencial/backoff simples).
   - Em sucesso:
     - **DB WRITE:** inserir response com `run_id, variant_id, snapshot_id, iteration_number, payload, timings, etc`.
   - Em falha final:
     - **DB WRITE:** inserir error (ou response marcada como erro—definir padrão único)
     - Continuar.

### 8. Fase E — Finalização e reexecução parcial
10. Calcular resumo:
   - total planejado, executado, sucesso, falha
11. **DB WRITE:** atualizar status do run:
   - `completed` se 0 falhas pendentes
   - `partial_failed` se houve falhas mas houve progresso
   - `failed` se nada executou e tudo falhou (opcional)
12. Se houve falhas:
   - Mostrar lista (limitada) de `(variant, question)` que falharam
   - Perguntar se deseja reexecutar agora (ou instruir comando `--retry-only-failed`)

---

## Para eu ajustar isso com você (1 pergunta só)
Você quer que o modo padrão (sem `--run-id`) execute:
- **A)** só o **run mais antigo não-completo** (mais simples e previsível), ou
- **B)** **todos** os runs não-completos em ordem (mais automático)?

Se você me disser A ou B, eu fecho a versão 1.0 desse TO‑BE e a gente parte pro contrato do **ExecutionEngine** em seguida.