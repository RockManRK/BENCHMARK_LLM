# Relatório de Investigação — Comportamentos Não Documentados

## Contexto da Investigação

Este documento foi criado após análise dos logs de execução (arquivos em `docs/log_parts/`) comparados com os documentos AS-IS de behavior (arquivos em `docs/behavior/as-is/`).

**Objetivo:** Identificar comportamentos do sistema que não foram documentados originalmente e entender as causas raiz de bugs observados.

---

## 🔴 DESCOBERTA CRÍTICA #1 — Criação de Variantes Durante Execução

### Comportamento Observado

**Onde:** Durante a execução do comando `--execute-run`

**O que acontece:**
O sistema **CRIA** variantes de modelo durante a execução, não apenas durante `--add-model`.

**Evidência no Log (log1_execute-run.md):**
```
2026-03-15 22:27:38 - INFO - src.core.iteration_executor - Registered model variant: var-4fadde11 | model=google/gemini-3.1-flash-lite-preview | signature=google/gemini-3.1-flash-lite-preview::reasoning=unspecified::vision=true::structured=false
```

**Análise:**
- Esta mensagem aparece **DURANTE** a execução de um run
- A variante sendo criada tem `reasoning=unspecified`
- Esta variante **NÃO** foi criada via `--add-model`
- O sistema está **INFERINDO** a configuração da variante durante execução

### Causa Raiz

**Código:** `src/core/iteration_executor.py`, método `execute_iteration()` (linhas ~160-200)

**Fluxo:**
1. Durante execução, o sistema constrói um `VariantConfig` baseado nas **settings globais**
2. Gera `variant_id` e `variant_signature`
3. Verifica se variante existe no banco
4. **Se NÃO existir, CRIA uma nova variante**
5. Usa esta variante para persistir respostas

**Problema:**
```python
# Linhas 401-428 (iteration_executor.py)
variant_signature = variant_config.build_signature(self.model_id)
variant_id = variant_config.build_variant_id(self.model_id)

# Check if variant exists, if not create it
existing_variant = None
if variant_repository:
    existing_variant = variant_repository.get_by_id(variant_id)
    if not existing_variant:
        from src.db.models import ModelVariant
        variant = ModelVariant(
            variant_id=variant_id,
            model_id=self.model_id,
            reasoning_mode=variant_config.reasoning_mode,
            # ... outros campos
        )
        variant_repository.create(variant)  # ← CRIAÇÃO DURANTE EXECUÇÃO
```

### Impactos e Bugs Gerados

#### BUG #1: Respostas atribuídas à variante errada

**Cenário:**
1. Usuário executa `--add-model google/gemini-3.1-flash-lite-preview --reasoning-effort low --enable-vision`
   - Cria variante: `var-93517b5b` com `reasoning_mode=effort, reasoning_effort=low`
2. Usuário executa `--add-model google/gemini-3.1-flash-lite-preview --reasoning-effort none --enable-vision`
   - Cria variante: `var-5eb0bdca` com `reasoning_mode=off`
3. Usuário executa `--create-run` e `--execute-run`
4. **Durante execução:**
   - Sistema infere configuração das **settings globais**
   - Settings podem NÃO ter `reasoning_effort` configurado
   - Cria variante `var-4fadde11` com `reasoning_mode=unspecified`
5. **Respostas são salvas com `variant_id=var-4fadde11`**
   - NÃO com `var-93517b5b` ou `var-5eb0bdca`
   - **Perde-se o vínculo com a configuração original do modelo**

#### BUG #2: Deduplicação de respostas falha

**Cenário:**
1. Run tem 2 variantes do mesmo modelo base:
   - `var-93517b5b` (reasoning=low)
   - `var-5eb0bdca` (reasoning=off)
2. Sistema verifica "perguntas já respondidas" usando **apenas model_id**
   - NÃO usa variant_id na verificação
3. Ao executar segunda variante:
   - Sistema acha que todas perguntas já foram respondidas
   - **Pula execução da segunda variante**

**Evidência:** Documento `erros_a_corrigir_v4.md` descreve:
> "Resultado esperado: 200 respostas. Resultado real: 100 respostas"

#### BUG #3: Variantes duplicadas entre execuções

**Cenário:**
1. Primeira execução: cria `var-4fadde11` (unspecified)
2. Segunda execução: settings podem gerar configuração ligeiramente diferente
3. **Nova variante é criada** com ID diferente
4. Banco fica com múltiplas variantes "unspecified" para mesmo modelo

### Comportamento Não Documentado

Nos documentos AS-IS originais:

**execute-run.md afirma:**
> "Busca todas as variantes associadas ao run (tabela `run_models`)"
> "Para cada run_model, carrega a variante completa da tabela `model_variants`"

**O que NÃO foi documentado:**
> "Se a variante NÃO for encontrada no banco, **uma nova variante é criada** durante execução com base nas settings globais"

**Fluxo real (não documentado):**
1. Carrega run_models do run
2. Para cada run_model:
   - Extrai model_id
   - **Reconstrói variant_config das settings globais**
   - **Gera NOVO variant_id**
   - **Se não existir, CRIA variante**
   - Usa esta variante para execução

---

## 🔴 DESCOBERTA CRÍTICA #2 — Identidade da Variante Instável

### Comportamento Observado

**Onde:** Comandos `--add-model` e `--execute-run`

**Problema:**
A assinatura/identidade de uma variante pode ser **diferente** dependendo de **quando** e **como** é criada.

### Evidências

#### No `--add-model` (log1_add-model.md):
```
2026-03-15 22:25:02 - INFO - src.cli.experiment_commands - Variant already exists: var-5eb0bdca
2026-03-15 22:25:02 - INFO - src.cli.experiment_commands - Associating variant var-5eb0bdca with experiment exp-a68530c1
```

**Contexto:**
- Comando: `--add-model google/gemini-3.1-flash-lite-preview --reasoning-effort none --enable-vision`
- Variante já existia (criada anteriormente)
- Sistema **reutiliza** variante existente

#### No `--execute-run` (log1_execute-run.md):
```
2026-03-15 22:27:38 - INFO - src.core.iteration_executor - Registered model variant: var-4fadde11 | model=google/gemini-3.1-flash-lite-preview | signature=...reasoning=unspecified...
```

**Contexto:**
- Mesma base model: `google/gemini-3.1-flash-lite-preview`
- Mesma flag vision: `true`
- **MAS:** reasoning_mode foi inferido como `unspecified`
- **Resultado:** variante DIFERENTE

### Causa Raiz

**Campos que compõem identidade da variante:**
```python
# VariantConfig.build_variant_id()
identity_fields = [
    model_id,
    reasoning_mode,      # ← Pode ser inferido diferente!
    reasoning_effort,    # ← Pode ser None vs 'low' vs 'none'
    reasoning_max_tokens,
    vision_enabled,
    structured_enabled
]
```

**Fontes de configuração:**

| Contexto | Fonte de reasoning_mode | Fonte de reasoning_effort |
|----------|------------------------|---------------------------|
| `--add-model` | CLI (--reasoning-effort) | CLI (--reasoning-effort) |
| `--execute-run` | Settings globais (.env) | Settings globais (.env) |

**Problema:**
- `--add-model`: `reasoning_effort='none'` → `reasoning_mode='off'`
- `--execute-run`: `reasoning_effort` não configurado → `reasoning_mode='unspecified'`
- **Variantes diferentes para mesma intenção!**

### Comportamento Não Documentado

**add-model.md afirma:**
> "Constrói configuração da variante com parâmetros: reasoning_mode, reasoning_effort, etc."
> "Gera variant_signature (string legível que identifica a variante)"

**O que NÃO foi documentado:**
> "A identidade da variante depende **da origem dos parâmetros**:
> - CLI: normalização explícita (reasoning_effort='none' → reasoning_mode='off')
> - Execução: inferência das settings (pode gerar 'unspecified')"

**Regra implícita não documentada:**
```
SE reasoning_effort = 'none' → reasoning_mode = 'off'
SENÃO SE reasoning_effort especificado → reasoning_mode = 'effort'
SENÃO → reasoning_mode = 'unspecified'
```

Esta regra é aplicada no `--add-model`, mas **pode NÃO ser aplicada** durante execução.

---

## 🟡 DESCOBERTA #3 — Verificação de Perguntas Respondidas (Bug de Deduplicação)

### Comportamento Observado

**Onde:** Durante `--execute-run`

**Evidência:** Documento `erros_a_corrigir_v4.md`:
> "Resultado esperado: 200 respostas. Resultado real: 100 respostas"

### Causa Provável

**Hipótese:** O método `get_pending_questions()` em `iteration_executor.py` pode estar usando critério **incorreto** para verificar perguntas já respondidas.

**Código provável (não lido diretamente):**
```python
# Provável implementação com bug
def get_pending_questions(self, variant_id, questions, iteration_number):
    # Verifica se pergunta já foi respondida
    # BUG: Pode estar verificando apenas por (run_id, question_id)
    #      em vez de (run_id, variant_id, question_id, iteration_number)
    answered = db.query("""
        SELECT question_id FROM responses 
        WHERE run_id = ? AND question_id = ?
    """, (self.run_id, question_id))
```

**Critério CORRETO deveria ser:**
```sql
WHERE run_id = ? 
  AND variant_id = ? 
  AND question_id = ? 
  AND iteration_number = ?
```

### Comportamento Não Documentado

**execute-run.md NÃO menciona:**
> "Como o sistema verifica se uma pergunta já foi respondida"
> "Qual critério de deduplicação é usado"

**Fluxo não documentado:**
1. Para cada variante no run:
   - Lista perguntas do experimento
   - **Filtra perguntas "já respondidas"**
   - Executa apenas perguntas pendentes
2. **Critério de filtro:** NÃO documentado, provavelmente com bug

---

## 🟡 DESCOBERTA #4 — Resposta a Erro de Randomização (Questão 55)

### Comportamento Observado

**Onde:** Durante `--execute-run`, questão Q055

**Evidência no Log (log1_execute-run.md):**
```
2026-03-15 22:29:39 - ERROR - src.core.randomizer - Correct answer text '' not found in options
2026-03-15 22:29:39 - ERROR - src.core.question_executor - Unexpected error for question Q055: Correct answer not found in randomized options
ValueError: Correct answer not found in randomized options
```

**Contexto:**
- Pergunta Q055 tem `answer_key` inválido (provavelmente "CONTESTED" ou vazio)
- Randomizador tenta encontrar resposta correta nas opções
- **Não encontra → lança exceção**

### Comportamento Não Documentado

**execute-run.md afirma:**
> "Em caso de erro, persiste na tabela `errors`"

**O que acontece na realidade:**
1. Erro de randomização **NÃO é tratado** como erro de execução
2. Sistema **continua** para próxima pergunta
3. **Resposta NÃO é persistida** (ou é persistida incompleta)
4. **Erro NÃO é registrado** na tabela `errors`

**Evidência:**
```
2026-03-15 22:29:39 - INFO - src.db.repository - Saving response: run_id=..., snapshot_id=55, question_id=Q055, variant_id=...
2026-03-15 22:29:39 - INFO - src.db.repository - Response saved with ID 55
2026-03-15 22:29:39 - WARNING - src.core.iteration_executor - Question Q055 failed: Correct answer not found in randomized options
```

**Fluxo real:**
- Resposta é salva (ID 55)
- Mas provavelmente sem dados completos
- Warning é registrado, mas erro não é persistido

### Regra Não Especificada

**erros_a_corrigir_v4.md:**
> "Isso não é bug. É **comportamento não especificado**."

**Perguntas sem resposta:**
- O que fazer com perguntas com `answer_key` inválido?
- Devem ser puladas?
- Devem ser marcadas como "inválidas"?
- Devem contar para estatísticas?

---

## 🟡 DESCOBERTA #5 — Criação de Variantes em Múltiplos Pontos

### Comportamento Observado

**Onde:** Múltiplos arquivos de código

**Pontos de criação de variantes identificados:**

1. **`src/core/run_manager.py`** (linha ~533):
   - Método `_resolve_or_create_variant()` (ou similar)
   - Chamado durante `--add-model`
   - **Também pode ser chamado durante execução**

2. **`src/core/iteration_executor.py`** (linha ~421):
   - Método `execute_iteration()`
   - Cria variante se não existir
   - **Durante execução de run**

### Fluxo Não Documentado

**add-model.md descreve:**
> "Cria uma variante de modelo com parâmetros específicos"
> "Associa a variante ao experimento"

**O que NÃO descreve:**
> "A mesma lógica de criação de variantes está disponível em outros módulos"
> "Durante execução, variantes podem ser criadas 'sob demanda'"

**Implicação:**
- Variante pode ser criada em **dois contextos diferentes**:
  1. Setup (`--add-model`): com parâmetros explícitos do CLI
  2. Execução (`--execute-run`): com parâmetros inferidos das settings
- **Identidade pode divergir**

---

## 🟢 DESCOBERTA #6 — Separação Entre model_id e variant_id

### Comportamento Observado

**Onde:** Persistência de respostas

**Evidência no Log:**
```
2026-03-15 22:27:40 - INFO - src.db.repository - Saving response: run_id=run-..., snapshot_id=1, question_id=Q001, variant_id=var-4fadde11
```

**E depois:**
```
2026-03-15 22:27:40 - INFO - src.core.question_executor - Creating response: run_id=..., snapshot_id=1, model_id=google/gemini-3.1-flash-lite-preview
```

### Comportamento Não Documentado

**execute-run.md NÃO menciona:**
> "Respostas são associadas a BOTH `variant_id` E `model_id`"

**Esquema provável:**
```sql
CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY,
    run_id TEXT,
    variant_id TEXT,      -- ← Identidade da configuração
    model_id TEXT,        -- ← Modelo base (para referência)
    question_id TEXT,
    -- ... outros campos
)
```

**Implicação:**
- `variant_id` é a **identidade verdadeira** para deduplicação
- `model_id` é apenas **referência legível**
- Verificações devem usar `variant_id`, não `model_id`

---

## 🟢 DESCOBERTA #7 — Normalização de reasoning_effort

### Comportamento Observado

**Onde:** `--add-model`

**Evidência no Log:**
- log1_add-model.md: `--reasoning-effort none` → `reasoning_mode='off'`
- log2_add-model.md: `--reasoning-effort low` → `reasoning_mode='effort'`

**Regra de normalização (inferred):**
```
reasoning_effort = 'none'  → reasoning_mode = 'off', reasoning_effort = NULL
reasoning_effort = 'low'   → reasoning_mode = 'effort', reasoning_effort = 'low'
reasoning_effort = 'high'  → reasoning_mode = 'effort', reasoning_effort = 'high'
reasoning_effort não especificado → reasoning_mode = 'unspecified'
```

### Comportamento Não Documentado

**add-model.md menciona:**
> "Normalização de Reasoning Effort: Se reasoning_effort = 'none', define reasoning_mode = 'off'"

**O que NÃO menciona:**
> "Esta normalização ocorre **apenas** no contexto de --add-model"
> "Durante execução, a normalização pode NÃO ocorrer"

**Risco:**
- Inconsistência entre variantes criadas em contextos diferentes
- Variante `unspecified` vs `off` podem ser **diferentes**

---

## 📊 RESUMO DAS DESCOBERTAS

### Bugs Críticos Confirmados

| # | Bug | Impacto | Origem |
|---|-----|---------|--------|
| 1 | Criação de variantes durante execução | Respostas atribuídas à variante errada | `iteration_executor.py` |
| 2 | Identidade de variante instável | Variantes duplicadas, deduplicação falha | `VariantConfig.build_variant_id()` |
| 3 | Verificação de perguntas respondidas incorreta | Pula execução de variantes | `get_pending_questions()` |

### Comportamentos Não Especificados

| # | Comportamento | Risco |
|---|---------------|-------|
| 4 | Tratamento de perguntas com answer_key inválido | Erros silenciosos, dados incompletos |
| 5 | Múltiplos pontos de criação de variantes | Inconsistência de identidade |
| 6 | Dualidade variant_id vs model_id | Confusão em verificações |
| 7 | Normalização de reasoning_effort contextual | Variantes incompatíveis |

### Lacunas na Documentação AS-IS

**create-experiment.md:**
- ❌ Não menciona que snapshots são usados para identidade de respostas
- ❌ Não descreve como config_hash é calculado

**add-model.md:**
- ❌ Não menciona normalização de reasoning_effort
- ❌ Não descreve que identidade pode divergir em execução

**add-questions.md:**
- ✅ Bem documentado
- ⚠️ Poderia mencionar que snapshots têm IDs únicos usados em respostas

**create-run.md:**
- ❌ Não menciona que variantes são COPIADAS (não referenciadas)
- ❌ Não descreve resolução de seed em detalhe

**execute-run.md:**
- ❌❌ **Maioria das lacunas aqui**
- ❌ Não menciona criação de variantes durante execução
- ❌ Não descreve critério de "perguntas respondidas"
- ❌ Não menciona dualidade variant_id/model_id
- ❌ Não descreve tratamento de erros de randomização

---

## 🔍 POR QUE OS COMPORTAMENTOS NÃO FORAM IDENTIFICADOS ORIGINALMENTE

### Causas da Falha de Documentação

1. **Nível de abstração muito alto**
   - Documentos AS-IS focaram em "o que" o comando faz
   - Não exploraram "como" internamente funciona
   - Exemplo: "carrega variantes" vs "reconstrói variante das settings"

2. **Separação entre intenção e implementação**
   - Intenção: "usar variantes configuradas"
   - Implementação: "criar variante se não existir"
   - Documentação capturou intenção, não implementação

3. **Código com lógica implícita**
   - `iteration_executor.py` tem lógica de "criar se não existir"
   - Esta lógica não é óbvia da assinatura do método
   - Requer leitura detalhada do código

4. **Múltiplos caminhos de execução**
   - Caminho 1: `--add-model` → cria variante
   - Caminho 2: `--execute-run` → pode criar variante
   - Documentação focou no caminho "feliz" (caminho 1)

5. **Falta de visibilidade dos logs**
   - Logs contêm informações cruciais
   - Análise original não teve acesso aos logs
   - Logs revelam comportamento real, não apenas intenção

---

## 📋 RECOMENDAÇÕES PARA PRÓXIMOS PASSOS

### Prioridade 1: Corrigir Bugs Críticos

1. **Remover criação de variantes durante execução**
   - `iteration_executor.py` deve **apenas usar** variantes existentes
   - Se variante não existir: erro explícito
   - Forçar uso de `--add-model` antes de `--execute-run`

2. **Corrigir verificação de perguntas respondidas**
   - Usar critério completo: `(run_id, variant_id, question_id, iteration_number)`
   - Não apenas `(run_id, question_id)`

3. **Estabilizar identidade de variantes**
   - Garantir que `build_variant_id()` use **mesma lógica** em todos contextos
   - Centralizar lógica em `VariantConfig`
   - Remover duplicação de lógica

### Prioridade 2: Especificar Comportamentos Não Definidos

4. **Definir política para perguntas inválidas**
   - O que fazer com `answer_key` inválido?
   - Marcar como "invalid", pular, ou erro?

5. **Documentar dualidade variant_id/model_id**
   - Esclarecer quando usar cada um
   - Atualizar documentação AS-IS

### Prioridade 3: Atualizar Documentação AS-IS

6. **Revisar execute-run.md**
   - Adicionar passo: "reconstrói variante das settings"
   - Adicionar decisão: "cria variante se não existir"
   - Adicionar efeito: "respostas associadas a variant_id"

7. **Revisar add-model.md**
   - Adicionar nota sobre normalização de reasoning_effort
   - Adicionar aviso sobre divergência em execução

---

## 📌 CONCLUSÃO

A investigação revelou que:

1. **Sistema tem bugs reais e críticos** relacionados à identidade de variantes
2. **Comportamentos implícitos** não foram capturados na documentação AS-IS
3. **Logs foram essenciais** para identificar comportamentos reais
4. **Causa raiz é conceitual**: identidade de variante mal definida

**Próximo passo natural:**
- Usar este relatório como base para definir comportamento TO-BE
- Corrigir bugs identificados
- Atualizar documentação AS-IS com comportamentos descobertos
