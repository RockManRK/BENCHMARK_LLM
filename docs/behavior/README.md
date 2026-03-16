# Índice — Documentação de Behavior AS-IS

## 📚 Visão Geral

Esta pasta contém a documentação do comportamento **ATUAL** (AS-IS) do sistema benchmark_llm.

**Importante:** Esta documentação descreve o que o sistema **FAZ**, não o que **DEVERIA FAZER**.

---

## 📁 Estrutura de Arquivos

```
docs/behavior/
├── README.md                      ← Este arquivo (índice)
├── EXECUTIVE-SUMMARY.md           ← Resumo executivo da investigação
├── investigation-report.md        ← Relatório completo de investigação
└── as-is/
    ├── create-experiment.md       ← Comando: --create-experiment
    ├── add-model.md               ← Comando: --add-model
    ├── add-questions.md           ← Comando: --add-questions
    ├── create-run.md              ← Comando: --create-run
    └── execute-run.md             ← Comando: --execute-run / --run
```

---

## 🔍 Como Usar Esta Documentação

### Para Entender um Comando Específico

1. **Comece pelo resumo:**
   - `EXECUTIVE-SUMMARY.md` — Visão geral das descobertas

2. **Leia o documento do comando:**
   - `as-is/<comando>.md` — Comportamento detalhado

3. **Consulte o relatório se necessário:**
   - `investigation-report.md` — Detalhes técnicos e evidências

---

## 📋 Resumo dos Comandos

### --create-experiment

**O que faz:** Cria experimento com configuração congelada + snapshots de perguntas

**Seção AS-IS:** [`as-is/create-experiment.md`](as-is/create-experiment.md)

**Comportamentos críticos:**
- ✅ Carrega TODAS as perguntas se --questions não especificado
- ✅ Snapshots são idempotentes (não duplicam)
- ✅ NÃO cria runs ou executa benchmarks
- ⚠️ Configuração é congelada com hash

---

### --add-model

**O que faz:** Adiciona modelos/variantes ao experimento

**Seção AS-IS:** [`as-is/add-model.md`](as-is/add-model.md)

**Comportamentos críticos:**
- ✅ Registra modelo base + cria variante com parâmetros
- ✅ Normaliza `reasoning_effort` (none → off, low/high → effort)
- ⚠️ **RISCO:** Normalização pode não ocorrer durante execução
- ⚠️ **RISCO:** Múltiplos pontos de criação de variantes

---

### --add-questions

**O que faz:** Adiciona novas perguntas a experimento existente

**Seção AS-IS:** [`as-is/add-questions.md`](as-is/add-questions.md)

**Comportamentos críticos:**
- ✅ Experimentos podem EVOLUIR, Runs são IMUTÁVEIS
- ✅ Runs existentes NÃO são afetados
- ✅ Apenas runs futuros usam novas perguntas
- ✅ Snapshots são idempotentes

---

### --create-run

**O que faz:** Cria nova execução (run) para experimento

**Seção AS-IS:** [`as-is/create-run.md`](as-is/create-run.md)

**Comportamentos críticos:**
- ✅ Copia variantes do experimento (não referencia)
- ✅ Cada run tem "foto" congelada das variantes
- ✅ Status inicial: "running"
- ⚠️ **IMPORTANTE:** Variantes são COPIADAS, não referenciadas

---

### --execute-run / --run

**O que faz:** Executa run de benchmark

**Seção AS-IS:** [`as-is/execute-run.md`](as-is/execute-run.md)

**Comportamentos críticos:**
- ⚠️ **CRÍTICO:** Cria variantes durante execução se não existirem
- ⚠️ **CRÍTICO:** Reconstrói variante das settings globais
- ⚠️ **BUG:** Deduplicação de perguntas pode falhar
- ⚠️ **BUG:** Respostas atribuídas à variante errada
- ✅ Executa run mais recente (ordenado por started_at DESC)
- ✅ Iterações fixas em 1

---

## 🔴 Bugs e Comportamentos Problemáticos

### Críticos (Prioridade 1)

| Bug | Descrição | Arquivo |
|-----|-----------|---------|
| **Criação de variantes durante execução** | Sistema cria variantes durante --execute-run | [`as-is/execute-run.md`](as-is/execute-run.md) |
| **Deduplicação falha** | Verificação usa critério incorreto | [`as-is/execute-run.md`](as-is/execute-run.md) |
| **Identidade instável** | Normalização inconsistente de reasoning_effort | [`as-is/add-model.md`](as-is/add-model.md) |

### Não Especificados (Prioridade 2)

| Comportamento | Descrição | Arquivo |
|---------------|-----------|---------|
| **Perguntas inválidas** | answer_key = "CONTESTED" ou vazio | [`as-is/execute-run.md`](as-is/execute-run.md) |
| **Dualidade variant_id/model_id** | Qual campo usar para verificações | [`as-is/execute-run.md`](as-is/execute-run.md) |

---

## 📊 Fluxo Completo do Sistema

```
1. --create-experiment
   ↓ Cria experimento + snapshots de perguntas

2. --add-model (pode ser executado múltiplas vezes)
   ↓ Adiciona variantes de modelo ao experimento

3. --add-questions (opcional, pode ser executado múltiplas vezes)
   ↓ Adiciona mais perguntas ao experimento
   ↓ Runs existentes NÃO são afetados

4. --create-run
   ↓ Cria run com "foto" congelada do experimento
   ↓ Copia variantes do experimento

5. --execute-run / --run
   ↓ Executa run mais recente
   ↓ ⚠️ PODE CRIAR variantes durante execução
   ↓ Persiste respostas e erros
```

---

## 📚 Documentos Relacionados

### Fora desta Pasta

- **`docs/Nao_Apagar-Temporarios_do_Usuario/erros_a_corrigir_v4.md`**
  - Contexto do usuário sobre bugs encontrados
  - Análise de causa raiz

- **`docs/log_parts/*.md`**
  - Logs reais de execução usados na investigação
  - Evidências dos comportamentos documentados

- **`conductor/tracks/`**
  - Planos de implementação e correção
  - Tracks de desenvolvimento

---

## 🔄 Atualizações Recentes

### [2026-03-16] Investigação de Logs

**O que mudou:**
- ✅ Adicionado comportamento de criação de variantes durante execução
- ✅ Adicionado critério de deduplicação de perguntas (bug potencial)
- ✅ Adicionado dualidade variant_id/model_id
- ✅ Adicionado normalização de reasoning_effort
- ✅ Adicionado tratamento de erros de randomização

**Documentos atualizados:**
- `as-is/execute-run.md`
- `as-is/add-model.md`
- `as-is/create-run.md`

**Novos documentos:**
- `EXECUTIVE-SUMMARY.md`
- `investigation-report.md`
- `README.md` (este arquivo)

---

## 🎯 Próximos Passos

### Para Revisão de Comportamento

1. **Ler EXECUTIVE-SUMMARY.md** — Visão geral
2. **Ler investigation-report.md** — Detalhes técnicos
3. **Revisar as-is/*.md** — Comportamentos atualizados
4. **Identificar TO-BE** — O que deveria acontecer

### Para Correção de Bugs

1. **Prioridade 1:** Remover criação de variantes durante execução
2. **Prioridade 2:** Corrigir critério de deduplicação
3. **Prioridade 3:** Estabilizar identidade de variantes

---

## 📞 Dúvidas?

Este índice deve guiá-lo pela documentação. Para mais detalhes:

- **Comportamento específico:** Ver `as-is/<comando>.md`
- **Detalhes técnicos:** Ver `investigation-report.md`
- **Visão geral:** Ver `EXECUTIVE-SUMMARY.md`
- **Evidências:** Ver `docs/log_parts/*.md`
