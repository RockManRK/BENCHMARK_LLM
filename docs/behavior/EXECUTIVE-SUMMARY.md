# Resumo Executivo — Investigação de Comportamentos

## 🎯 Objetivo da Investigação

Comparar logs reais de execução com documentos AS-IS de behavior para identificar:
- Comportamentos não documentados
- Bugs críticos
- Lacunas entre intenção e implementação

---

## 🔴 DESCOBERTA CRÍTICA PRINCIPAL

### Sistema Cria Variantes Durante Execução

**O que deveria acontecer:**
- Variantes são criadas via `--add-model` (setup)
- Execução (`--execute-run`) apenas USA variantes existentes

**O que realmente acontece:**
- Durante execução, sistema **RECONSTRÓI** variante das settings globais
- Se variante NÃO existir no banco, **CRIA NOVA variante**
- Variante criada pode ser **DIFERENTE** da configurada via `--add-model`

**Impacto:**
```
1. --add-model google/gemini-3.1-flash-lite-preview --reasoning-effort low
   → Cria var-93517b5b (reasoning_mode=effort, reasoning_effort=low)

2. --execute-run (settings sem reasoning_effort)
   → Cria var-4fadde11 (reasoning_mode=unspecified)
   → Respostas salvas com var-4fadde11, NÃO var-93517b5b

RESULTADO: Perde-se vínculo com configuração original!
```

**Arquivos afetados:**
- `src/core/iteration_executor.py` (linhas ~401-428)
- `src/core/run_manager.py` (linhas ~501-540)

---

## 📋 Bugs Confirmados

### BUG #1: Respostas Atribuídas à Variante Errada

**Causa:** Criação de variantes durante execução

**Sintoma:**
- Respostas associadas a variante `unspecified`
- Não à variante configurada com `reasoning_effort`

**Impacto:**
- Impossível distinguir respostas de variantes diferentes
- Estatísticas de accuracy incorretas

---

### BUG #2: Deduplicação de Perguntas Falha

**Causa:** Critério de verificação usa apenas `(run_id, question_id)`

**Sintoma:**
- 2 variantes do mesmo modelo base
- Segunda variante pula execução
- **Esperado: 200 respostas. Obtido: 100 respostas**

**Impacto:**
- Dados incompletos
- Modelos não executados

---

### BUG #3: Identidade de Variante Instável

**Causa:** Normalização de `reasoning_effort` inconsistente

**Sintoma:**
```
--add-model --reasoning-effort none
  → reasoning_mode = 'off'

--execute-run (sem reasoning_effort nas settings)
  → reasoning_mode = 'unspecified'
```

**Impacto:**
- Mesma intenção → variantes diferentes
- Deduplicação falha entre contextos

---

## ⚠️ Comportamentos Não Especificados

### 1. Perguntas com answer_key Inválido

**Cenário:**
- Pergunta Q055 tem `answer_key = "CONTESTED"` ou vazio
- Randomizador lança `ValueError`
- Sistema continua execução

**Não especificado:**
- Deve pular pergunta?
- Deve marcar como "inválida"?
- Deve contar para estatísticas?

---

### 2. Dualidade variant_id vs model_id

**Observado:**
- Respostas têm BOTH `variant_id` E `model_id`
- `variant_id`: identidade verdadeira (deduplicação)
- `model_id`: referência legível

**Não especificado:**
- Qual campo usar para verificações?
- O que acontece se divergirem?

---

## 📊 Lacunas na Documentação AS-IS

### execute-run.md (MAIS AFETADO)

**Não documentado:**
- ❌ Criação de variantes durante execução
- ❌ Reconstrução de variante das settings globais
- ❌ Critério de verificação de perguntas respondidas
- ❌ Dualidade variant_id/model_id
- ❌ Tratamento de erros de randomização

### add-model.md

**Não documentado:**
- ❌ Normalização de reasoning_effort
- ❌ Risco de inconsistência com execução
- ❌ Múltiplos pontos de criação de variantes

### create-run.md

**Não documentado:**
- ❌ Que variantes são COPIADAS (não referenciadas)
- ⚠️ Parcialmente documentado, mas sem detalhes de implementação

---

## 🔍 Por Que os Comportamentos Não Foram Identificados

### Causas Raiz

1. **Nível de abstração muito alto**
   - Documentação focou em "o que", não "como"
   - Ex: "carrega variantes" vs "reconstrói variante das settings"

2. **Lógica implícita no código**
   - `iteration_executor.py` tem "criar se não existir"
   - Não óbvio da assinatura do método

3. **Múltiplos caminhos de execução**
   - Caminho 1: `--add-model` (setup)
   - Caminho 2: `--execute-run` (execução)
   - Documentação focou apenas no caminho 1

4. **Falta de acesso aos logs**
   - Logs revelam comportamento real
   - Análise original não teve acesso aos logs

---

## ✅ Atualizações Realizadas

### Documentos AS-IS Atualizados

1. **execute-run.md**
   - ✅ Adicionado: criação de variantes durante execução
   - ✅ Adicionado: dualidade variant_id/model_id
   - ✅ Adicionado: critério de perguntas respondidas (bug potencial)
   - ✅ Adicionado: tratamento de erros de randomização

2. **add-model.md**
   - ✅ Adicionado: normalização de reasoning_effort
   - ✅ Adicionado: risco de inconsistência
   - ✅ Adicionado: múltiplos pontos de criação

3. **create-run.md**
   - ✅ Adicionado: cópia vs referência de variantes

### Novo Documento Criado

4. **investigation-report.md**
   - 📄 Relatório completo da investigação
   - 📄 Todas as descobertas detalhadas
   - 📄 Recomendações para próximos passos

---

## 🎯 Próximos Passos Recomendados

### Prioridade 1: Corrigir Bugs Críticos

1. **Remover criação de variantes durante execução**
   - `iteration_executor.py` deve apenas USAR variantes existentes
   - Se variante não existir: erro explícito
   - Forçar uso de `--add-model` antes de `--execute-run`

2. **Corrigir critério de deduplicação**
   - Usar `(run_id, variant_id, question_id, iteration_number)`
   - Não apenas `(run_id, question_id)`

3. **Estabilizar identidade de variantes**
   - Centralizar lógica em `VariantConfig.build_variant_id()`
   - Garantir mesma lógica em todos contextos

### Prioridade 2: Especificar Comportamentos

4. **Definir política para perguntas inválidas**
   - Regra explícita para `answer_key` inválido
   - Implementar tratamento adequado

5. **Documentar dualidade variant_id/model_id**
   - Esclarecer uso de cada campo
   - Atualizar schema do banco se necessário

### Prioridade 3: Validação

6. **Testar correções com logs reais**
   - Re-executar cenários dos logs
   - Verificar se bugs foram corrigidos
   - Validar documentação atualizada

---

## 📌 Conclusão

**Investigação bem-sucedida:**
- ✅ Bugs críticos identificados e documentados
- ✅ Comportamentos implícitos tornados explícitos
- ✅ Documentos AS-IS atualizados
- ✅ Base sólida para definição do TO-BE

**Próximo passo natural:**
- Usar este resumo + investigation-report.md para:
  1. Definir comportamento TO-BE
  2. Planejar correções de bugs
  3. Implementar mudanças
  4. Validar com novos testes

---

**Arquivos de Referência:**
- `docs/behavior/investigation-report.md` — Relatório completo
- `docs/behavior/as-is/*.md` — Documentos AS-IS atualizados
- `docs/log_parts/*.md` — Logs analisados
- `docs/Nao_Apagar-Temporarios_do_Usuario/erros_a_corrigir_v4.md` — Contexto do usuário
