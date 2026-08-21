# Benchmark LLM — Manual de Uso

**Versão:** 2.0 (Arquitetura TO-BE)
**Data:** 2026-03-18

---

## 1. MODELO MENTAL DO SISTEMA

### 1.1 Conceitos Fundamentais

| Conceito | O que é | Por que existe |
|----------|---------|----------------|
| **Experimento** | Configuração congelada de pesquisa | Reprodutibilidade |
| **Variante de Modelo** | Configuração intencional de um modelo (razão, visão, structured) | Identidade clara do que está sendo executado |
| **Snapshot de Questão** | Cópia imutável da questão no momento do uso | Auditoria e reprodutibilidade |
| **Run** | Unidade concreta de execução | Agrupa execuções com mesma seed e prompts |
| **ExecutionPlan** | Plano imutável de trabalho a executar | Separa decisão (Planner) de execução (Engine) |

### 1.2 Fluxo de Execução (ÚNICO)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Planner (DB Read-Only)                                   │
│    - Resolve experimento, runs, variantes, snapshots        │
│    - Aplica filtros (--models, --questions)                 │
│    - Deduplica (exclui já respondidos)                      │
│    - Resolve seeds e prompts                                │
│    - Constrói ExecutionPlan (imutável)                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ExecutionPlan (Dados Imutáveis)                          │
│    - Contém TODAS as tarefas a executar                     │
│    - Sem inferência durante execução                        │
│    - Serializável para auditoria                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. ExecutionEngine (API Calls, NO DB)                       │
│    - Executa chamadas à API                                 │
│    - Retorna ExecutionResult[]                              │
│    - NÃO acessa banco de dados                              │
│    - NÃO decide escopo                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. ResultWriter (DB Write-Only)                             │
│    - Persiste respostas e erros                             │
│    - Atualiza status do run                                 │
│    - Garante idempotência                                   │
│    - NÃO executa                                            │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Princípios Arquiteturais

| Princípio | Significado |
|-----------|-------------|
| **Experiments are explicit** | Todo experimento é criado explicitamente |
| **Execution is never implicit** | Não há modo de execução imediata |
| **All results are auditable** | Respostas referenciam snapshots imutáveis |
| **No mutable global state** | Configuração congelada por experimento |
| **No execution without identity** | Variantes criadas antes da execução |
| **No inference during execution** | ExecutionEngine não decide nada |

---

## 2. WORKFLOW PASSO A PASSO

### 2.1 Criar Experimento

```bash
bcllm --create-experiment <nome> --questions <faixa> --seed <valor>
```

**Exemplos:**

```bash
# Criar experimento com questões Q001-Q050 e seed 42
bcllm --create-experiment meu_exp --questions Q001-Q050 --seed 42

# Criar experimento com todas as questões e seed automático
bcllm --create-experiment meu_exp --seed AUTO

# Criar experimento com questões específicas
bcllm --create-experiment meu_exp --questions Q001,Q005,Q010
```

**O que acontece:**
1. Cria registro em `experiments` com config congelada
2. Cria snapshots em `question_snapshots` para cada questão
3. Snapshots são idempotentes (não duplicam)

---

### 2.2 Adicionar Modelos ao Experimento

```bash
bcllm --experiment <nome> --add-model <model_id>
```

**Exemplos:**

```bash
# Adicionar um modelo
bcllm --experiment meu_exp --add-model openai/gpt-4

# Adicionar múltiplos modelos
bcllm --experiment meu_exp \
  --add-model openai/gpt-4 \
  --add-model anthropic/claude-3 \
  --add-model google/gemini-pro
```

**O que acontece:**
1. Registra modelo base em `models` (se não existir)
2. Cria variante em `model_variants` com configuração atual
3. Variante define identidade (razão, visão, structured)

**Configuração de Variante:**
- `reasoning_mode`: off/auto/effort/budget/unspecified
- `reasoning_effort`: xhigh/high/medium/low/minimal (quando mode=effort)
- `vision_enabled`: true/false
- `structured_output`: true/false

---

### 2.3 Adicionar Questões ao Experimento (Evolução)

```bash
bcllm --experiment <nome> --add-questions <faixa>
```

**Exemplos:**

```bash
# Adicionar questões Q051-Q100 ao experimento existente
bcllm --experiment meu_exp --add-questions Q051-Q100
```

**Princípios:**
- Experimentos podem EVOLUIR
- Runs são IMUTÁVEIS
- Passado NUNCA é alterado
- Snapshots existentes NÃO são recriados
- Apenas NOVAS questões criam snapshots

**Impacto:**
- Runs existentes continuam usando questões originais
- Runs futuros usarão questões atualizadas

---

### 2.4 Criar Run

```bash
bcllm --experiment <nome> --add-run --seed <valor>
```

**Exemplos:**

```bash
# Criar run com seed do experimento
bcllm --experiment meu_exp --add-run

# Criar run com seed específico
bcllm --experiment meu_exp --add-run --seed 123
```

**O que acontece:**
1. Cria registro em `runs`
2. Associa ao experimento
3. Seed é resolvida (run → experimento → default)

---

### 2.5 Executar Run

```bash
bcllm --experiment <nome> --run
```

**Exemplos:**

```bash
# Executar todas as runs pendentes do experimento
bcllm --experiment meu_exp --run

# Executar com filtro de modelos
bcllm --experiment meu_exp --run --models openai/gpt-4

# Executar com filtro de questões
bcllm --experiment meu_exp --run --questions Q001-Q020
```

**O que acontece:**
1. Planner constrói ExecutionPlan
2. ExecutionEngine executa (API calls)
3. ResultWriter persiste resultados

**Deduplicação:**
- Combinações já respondidas são puladas
- Chave de deduplicação: `(run_id, variant_id, snapshot_id, iteration)`

---

### 2.6 Revisão Manual

```bash
bcllm --review-experiment <nome>
bcllm --review-run <run_id>
bcllm --review-all
```

**Quando usar:**
- `parse_confidence` = 'ambiguous', 'no_answer', ou 'low_confidence'
- `selected_answer` = NULL (parsing falhou)

**Interface de Revisão:**
```
================================================================================
REVIEW MANUAL DE RESPOSTAS  |  Item 1/23
================================================================================
Pendentes: 23  |  Processadas: 0
Pergunta: Q001 (Iteração 1, Modelo: var-abc123)
Resposta: A
Status: AMBIGUOUS
================================================================================

ENUNCIADO:
--------------------------------------------------------------------------------
Qual é a capital da França?

ALTERNATIVAS:
--------------------------------------------------------------------------------
  A) Londres
  B) Paris
  C) Berlim
  D) Madrid

RESPOSTA DA LLM:
--------------------------------------------------------------------------------
A resposta correta é Paris, que é a capital da França...

================================================================================
CLASSIFICAÇÃO:
--------------------------------------------------------------------------------
  [A]  [B]  [C]  [D]  [N]enhuma  [E]rro não detectado

  [S] Pular  |  [Q] Sair e salvar  |  [Z] Desfazer última
================================================================================
```

**Teclas:**
- `A/B/C/D` — Selecionar alternativa
- `N` — Nenhuma resposta clara
- `E` — Erro não detectado (questão técnica)
- `S` — Pular (revisar depois)
- `Q` — Sair e salvar progresso
- `Z` — Desfazer última classificação

---

### 2.7 Exportar Resultados

```bash
bcllm --export-results <run_id>
```

**Exemplo:**

```bash
bcllm --export-results run-20260318-abc123
```

**Saída (JSON):**

```json
{
  "run_id": "run-20260318-abc123",
  "total_responses": 100,
  "manual_answers": 15,
  "automatic_answers": 85,
  "responses": [
    {
      "response_id": 1,
      "question_id": "Q001",
      "variant_id": "var-abc123",
      "model_id": "openai/gpt-4",
      "iteration": 1,
      "selected_answer": "B",
      "manual_answer": "C",
      "final_answer": "C",
      "answer_source": "manual",
      "is_correct": true,
      "parse_confidence": "ambiguous",
      "latency_ms": 1200,
      "input_tokens": 50,
      "output_tokens": 10
    }
  ]
}
```

**Regra de Exportação:**
- `final_answer` = `manual_answer` se presente, senão `selected_answer`
- `answer_source` = "manual" ou "automatic"

---

## 3. REVISÃO MANUAL — EXPLICAÇÃO DETALHADA

### 3.1 Por que Revisão Manual é Necessária

**Parsing automático é FALLÍVEL por design:**

| `parse_confidence` | Significado | Ação |
|--------------------|-------------|------|
| `'clear'` | Resposta inequívoca | Nenhum review necessário |
| `'ambiguous'` | Múltiplas letras detectadas | Review necessário |
| `'no_answer'` | Nenhuma letra encontrada | Review necessário |
| `'low_confidence'` | Padrão fraco detectado | Review recomendado |

**Exemplos de Falha de Parsing:**

```
# Ambiguous (múltiplas letras)
LLM: "A resposta pode ser A ou B dependendo da interpretação"
→ parse_confidence = "ambiguous"

# No Answer (nenhuma letra)
LLM: "Paris é a capital da França"
→ parse_confidence = "no_answer"

# Low Confidence (apenas menção)
LLM: "A alternativa correta parece ser a letra C"
→ parse_confidence = "low_confidence"
```

### 3.2 Como a Revisão Funciona

**Fluxo:**

```
1. ExecutionEngine._parse_answer()
   ↓
2. Define parse_confidence
   ↓
3. ResultWriter.write_results()
   ↓
4. Calcula needs_review:
   needs_review = (
     parse_confidence in ('ambiguous', 'no_answer', 'low_confidence')
     OR selected_answer IS NULL
   )
   ↓
5. ReviewUI consulta: WHERE needs_review = TRUE
   ↓
6. Usuário fornece manual_answer
   ↓
7. is_correct recalculado:
   is_correct = (manual_answer == correct_answer)
```

### 3.3 Campos de Revisão

| Campo | Tipo | Definido Por |
|-------|------|--------------|
| `parse_confidence` | TEXT | ExecutionEngine |
| `needs_review` | BOOLEAN | ResultWriter (derivado) |
| `manual_answer` | TEXT | Revisor (opcional) |

**Campos NÃO implementados (por design):**
- `review_status` — Substituído por `needs_review` + `(manual_answer IS NOT NULL)`
- `reviewed_at` — Timestamp não necessário
- `reviewer_id` — Identidade não necessária
- `review_notes` — Notas não necessárias

---

## 4. O QUE NÃO É SUPORTADO (DECISÃO DE DOMÍNIO)

### 4.1 Modos de Execução

| Feature | Status | Racional |
|---------|--------|----------|
| Execução direta (`--models`) | NÃO SUPORTADO | Viola "no implicit execution" |
| Test mode (DB em memória) | NÃO SUPORTADO | Não necessário; use experimento |
| Dev mode (shadow experiments) | NÃO SUPORTADO | Toda execução requer experimento explícito |

### 4.2 Estrutura de Banco

| Tabela/Campo | Status | Racional |
|--------------|--------|----------|
| `models` (tabela) | NÃO EXISTE | `model_id` é identificador lógico |
| `run_models` (tabela) | NÃO EXISTE | Associação run-variante é em memória (ExecutionPlan) |
| `review_status` | NÃO EXISTE | Substituído por `needs_review` |
| `reviewed_at` | NÃO EXISTE | Timestamp não necessário |
| `reviewer_id` | NÃO EXISTE | Identidade não necessária |

### 4.3 Recursos de Exportação

| Feature | Status | Racional |
|---------|--------|----------|
| JSON export | ✅ Implementado | Suficiente para caso de uso atual |
| CSV export | NÃO IMPLEMENTADO | Pode ser adicionado se necessário |
| Markdown export | NÃO IMPLEMENTADO | Pode ser adicionado se necessário |

---

## 5. ARMADILHAS COMUNS E PADRÕES CORRETOS

### 5.1 Armadilha: Tentar Executar sem Experimento

**ERRADO:**
```bash
bcllm --models openai/gpt-4 --questions Q001-Q010
# → NotImplementedError: Direct execution is no longer supported
```

**CORRETO:**
```bash
# 1. Criar experimento
bcllm --create-experiment meu_exp --questions Q001-Q010

# 2. Adicionar modelos
bcllm --experiment meu_exp --add-model openai/gpt-4

# 3. Criar run
bcllm --experiment meu_exp --add-run

# 4. Executar
bcllm --experiment meu_exp --run
```

---

### 5.2 Armadilha: Esperar que `--add-questions` Altere Runs Existentes

**EXPECTATIVA ERRADA:**
```bash
# Run criado com Q001-Q050
bcllm --experiment meu_exp --add-run

# Adicionar Q051-Q100
bcllm --experiment meu_exp --add-questions Q051-Q100

# Espera-se que run existente use Q001-Q100
# → NÃO ACONTECE! Run é imutável.
```

**COMPORTAMENTO CORRETO:**
- Runs existentes continuam usando questões originais (Q001-Q050)
- Runs FUTUROS usarão questões atualizadas (Q001-Q100)

---

### 5.3 Armadilha: Esperar que `manual_answer` Seja Obrigatório

**EXPECTATIVA ERRADA:**
- "Todas as respostas precisam de revisão manual"

**COMPORTAMENTO CORRETO:**
- Apenas respostas com `needs_review = TRUE` precisam de revisão
- `parse_confidence = 'clear'` → `needs_review = FALSE`
- Revisão é OPCIONAL para respostas claramente parseadas

---

### 5.4 Armadilha: Confundir `selected_answer` com `final_answer`

**EXPECTATIVA ERRADA:**
- "Export usa sempre `selected_answer`"

**COMPORTAMENTO CORRETO:**
```python
final_answer = manual_answer if manual_answer else selected_answer
```

- Se `manual_answer` existe → usa `manual_answer`
- Senão → usa `selected_answer`
- `answer_source` indica origem ("manual" ou "automatic")

---

### 5.5 Padrão Correto: Filtrar Variantes Durante Execução

**PERMITIDO (Planner-level filter):**

```bash
bcllm --experiment meu_exp --run --models openai/gpt-4
```

**Por que é permitido:**
- Filtro aplicado pelo Planner (DB read, scope resolution)
- ExecutionEngine recebe ExecutionPlan já filtrado
- NÃO viola princípios (Engine não decide escopo)

---

## 6. COMANDOS DISPONÍVEIS (RESUMO)

### 6.1 Experimentos

| Comando | Descrição |
|---------|-----------|
| `--create-experiment <nome>` | Criar experimento |
| `--experiment <nome>` | Mostrar experimento |
| `--experiment <nome> --add-model <id>` | Adicionar modelo |
| `--experiment <nome> --remove-model <id>` | Remover modelo |
| `--experiment <nome> --add-questions <faixa>` | Adicionar questões |

### 6.2 Runs

| Comando | Descrição |
|---------|-----------|
| `--experiment <nome> --add-run` | Criar run |
| `--experiment <nome> --run` | Executar run |

### 6.3 Revisão

| Comando | Descrição |
|---------|-----------|
| `--review-experiment <nome>` | Revisar experimento |
| `--review-run <run_id>` | Revisar run específico |
| `--review-all` | Revisar todos pendentes |

### 6.4 Exportação

| Comando | Descrição |
|---------|-----------|
| `--export-results <run_id>` | Exportar resultados (JSON) |

---

## 7. NOTAS FINAIS

### 7.1 Sobre Este Documento

Este manual reflete o sistema **COMPLETO POR DESIGN**.

- Não há "funcionalidades faltando" — há decisões de domínio
- Não há "dívida técnica" — há simplificação intencional
- Não há "modo legado" — há arquitetura TO-BE

### 7.2 Princípios para Extensões Futuras

Antes de adicionar qualquer feature, avalie:

1. Viola algum contrato arquitetural?
2. É necessário para o caso de uso pretendido?
3. Adiciona complexidade sem valor proporcional?

Se a resposta for "sim" para qualquer uma, **NÃO ADICIONE** sem revisitar as premissas de domínio.

---

**Fim do Manual**
