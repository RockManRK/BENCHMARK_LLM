# Question Snapshots - Guia Completo

## Visão Geral

**Question Snapshots** são cópias imutáveis das perguntas usadas em cada experimento, garantindo reprodutibilidade e comparabilidade mesmo quando as perguntas originais sofrem alterações futuras.

## Problema Resolvido

### Cenário sem Snapshots

1. Você executa um experimento com 100 perguntas em Janeiro
2. Em Março, corrige um erro gramatical na pergunta Q042
3. Em Junho, re-executa o "mesmo" experimento
4. **Problema**: Os resultados de Janeiro e Junho não são comparáveis!
   - As perguntas são ligeiramente diferentes
   - Modelos diferentes responderam versões diferentes
   - A comparabilidade científica é comprometida

### Solução com Snapshots

1. Você executa um experimento com 100 perguntas em Janeiro
2. **Snapshots são criados** para cada pergunta usada
3. Em Março, corrige o erro gramatical na pergunta Q042
   - O catálogo canonical é atualizado
   - **Snapshots existentes permanecem inalterados**
4. Em Junho, re-executa o experimento
   - **Reutiliza os snapshots de Janeiro** (mesmo experiment_id)
   - Resultados são **perfeitamente comparáveis**
   - Integridade científica preservada

## Arquitetura

```
┌─────────────────┐         ┌───────────────────┐         ┌─────────────────┐
│   questions     │         │question_snapshots │         │    responses    │
│  (catálogo)     │────────▶│   (imutável)      │────────▶│                 │
├─────────────────┤         ├───────────────────┤         ├─────────────────┤
│ question_id (PK)│         │ snapshot_id (PK)  │         │ response_id (PK)│
│ stem            │  1:N    │ experiment_id (FK)│  1:N    │ snapshot_id (FK)│
│ options_json    │         │ question_id (FK)  │         │ question_id     │
│ correct_answer  │         │ question_json     │         │ model_id (FK)   │
│ status          │         │ created_at        │         │ selected_answer │
└─────────────────┘         └───────────────────┘         │ is_correct      │
         ▲                                                        │
         │                                                        │
         └────────────────── (referência) ────────────────────────┘

Legenda:
- questions: Catálogo canônico (pode ser atualizado)
- question_snapshots: Versões congeladas (NUNCA atualizadas)
- responses: Referencia snapshots para imutabilidade
```

## Ciclo de Vida de um Snapshot

### 1. Criação (Primeiro Uso)

```python
# Quando uma pergunta é executada pela primeira vez em um experimento
snapshot_id = snapshot_repo.create_if_not_exists(
    experiment_id="exp-001",
    question_id="Q001",
    question_json='{"id": "Q001", "stem": "...", "options": {...}}'
)
# snapshot_id = 1 (novo snapshot criado)
```

### 2. Reutilização (Execuções Posteriores)

```python
# Mesma pergunta, mesmo experimento
snapshot_id = snapshot_repo.create_if_not_exists(
    experiment_id="exp-001",
    question_id="Q001",
    question_json='{"id": "Q001", "stem": "...", "options": {...}}'
)
# snapshot_id = 1 (REUTILIZA snapshot existente!)
```

### 3. Isolamento (Experimentos Diferentes)

```python
# Mesma pergunta, experimento diferente
snapshot_id = snapshot_repo.create_if_not_exists(
    experiment_id="exp-002",  # Experimento diferente!
    question_id="Q001",
    question_json='{"id": "Q001", "stem": "...", "options": {...}}'
)
# snapshot_id = 2 (NOVO snapshot para novo experimento)
```

## Isolamento por Experimento

### Regra Fundamental

**TODO snapshot DEVE pertencer a um experimento válido.**

- `experiment_id = NULL` **NÃO É PERMITIDO**
- Cada experimento tem seus próprios snapshots
- Snapshots **NUNCA** são compartilhados entre experimentos

### Shadow Experiments (Dev Mode)

Em dev mode, um "shadow experiment" é criado automaticamente:

```python
# Dev mode cria shadow experiment automaticamente
experiment_name = f"shadow-{run_id}"
# Exemplo: "shadow-run-20260308123456-abc123"
```

**Benefícios:**
- Garante isolamento total mesmo em dev mode
- Cada run tem seus próprios snapshots
- Permite debugging sem poluir experimentos reais

## Estrutura do Snapshot

### JSON Armazenado

```json
{
  "id": "Q001",
  "stem": "Qual é a capital da França?",
  "options": {
    "A": "Paris",
    "B": "Londres",
    "C": "Berlim",
    "D": "Madrid"
  },
  "answer_key": "A",
  "has_image": false,
  "image_path": null
}
```

### Campos do Snapshot

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `snapshot_id` | INTEGER | ID único (auto-incremento) |
| `experiment_id` | TEXT | ID do experimento (OBRIGATÓRIO) |
| `question_id` | TEXT | ID da pergunta no catálogo |
| `question_json` | TEXT | JSON completo da pergunta |
| `created_at` | TIMESTAMP | Quando foi criado |

## Integridade e Validação

### Validação de Consistência

O sistema valida que:
1. `question_id` do snapshot == `question_json->>'$.id'`
2. `question_id` em `responses` == `snapshot.question_id`
3. `snapshot_id` em `responses` é válido e existe

### Método de Validação

```python
# Validar integridade de um snapshot
is_valid, error = snapshot_repo.validate_snapshot_integrity(snapshot_id)
if not is_valid:
    print(f"Erro de integridade: {error}")
```

## Queries Comuns

### 1. Obter Respostas com Detalhes da Pergunta

```sql
SELECT 
    r.response_id,
    r.selected_answer,
    r.is_correct,
    qs.question_json,
    json_extract(qs.question_json, '$.stem') as question_stem,
    json_extract(qs.question_json, '$.answer_key') as correct_answer
FROM responses r
JOIN question_snapshots qs ON r.snapshot_id = qs.snapshot_id
WHERE r.run_id = 'run-123'
ORDER BY r.iteration, qs.question_id;
```

### 2. Obter Todos Snapshots de um Experimento

```sql
SELECT 
    snapshot_id,
    question_id,
    question_json,
    created_at
FROM question_snapshots
WHERE experiment_id = 'exp-001'
ORDER BY question_id;
```

### 3. Comparar Versões de uma Pergunta

```sql
SELECT 
    qs.experiment_id,
    qs.question_id,
    qs.created_at,
    json_extract(qs.question_json, '$.stem') as stem
FROM question_snapshots qs
WHERE qs.question_id = 'Q001'
ORDER BY qs.created_at;
```

### 4. Contar Snapshots por Experimento

```sql
SELECT 
    experiment_id,
    COUNT(*) as snapshot_count
FROM question_snapshots
GROUP BY experiment_id;
```

## Execução Incremental

### Cenário

1. **Dia 1**: Executa experimento com perguntas Q001-Q050
2. **Dia 2**: Adiciona perguntas Q051-Q100 ao catálogo
3. **Dia 3**: Re-executa experimento com todas 100 perguntas

### Comportamento Esperado

```
Dia 1 (Q001-Q050):
  - Snapshots 1-50 criados para exp-001
  
Dia 3 (Q001-Q100):
  - Q001-Q050: REUTILIZA snapshots 1-50 (mesmo experiment_id)
  - Q051-Q100: CRIA snapshots 51-100 (novas perguntas)
  
Resultado:
  - Snapshots 1-50: Imutáveis, idênticos ao Dia 1
  - Snapshots 51-100: Novos, para perguntas adicionais
  - Comparabilidade preservada para Q001-Q050
```

## Boas Práticas

### 1. Nunca Modificar Snapshots

```python
# ❌ ERRADO: Tentar atualizar snapshot
cursor.execute(
    "UPDATE question_snapshots SET question_json = ? WHERE snapshot_id = ?",
    (new_json, snapshot_id)
)

# ✅ CERTO: Snapshots são imutáveis por design
# Se precisa mudar, crie novo experimento
```

### 2. Sempre Usar experiment_id

```python
# ❌ ERRADO: experiment_id = None
snapshot_id = repo.create_if_not_exists(
    experiment_id=None,  # NÃO PERMITIDO!
    question_id="Q001",
    question_json=json
)

# ✅ CERTO: Sempre usar experiment_id válido
snapshot_id = repo.create_if_not_exists(
    experiment_id="exp-001",  # OBRIGATÓRIO
    question_id="Q001",
    question_json=json
)
```

### 3. Validar Integridade Periodicamente

```python
# Validar todos snapshots de um experimento
snapshots = repo.get_by_experiment("exp-001")
for snapshot in snapshots:
    is_valid, error = repo.validate_snapshot_integrity(snapshot.snapshot_id)
    if not is_valid:
        logger.error(f"Snapshot {snapshot.snapshot_id} inválido: {error}")
```

## Migration Notes

### Schema v2.0 → v2.1

**Mudanças:**
- Adicionado `question_id TEXT NOT NULL` em `responses`
- Alterado `experiment_id TEXT` → `TEXT NOT NULL` em `question_snapshots`
- Adicionado índice `idx_responses_question`
- Alterado FK delete rule: `ON DELETE SET NULL` → `ON DELETE CASCADE` (experiments)

**Breaking Changes:**
- `experiment_id = NULL` não é mais permitido
- Banco de dados deve ser recriado (sem migration path)

**Ação Requerida:**
```bash
# Para desenvolvimento (dados não críticos)
rm data/benchmark.db
python -m src.main --models openai/gpt-4 --iterations 1
```

## Resumo

| Conceito | Descrição |
|----------|-----------|
| **Imutabilidade** | Snapshots nunca são modificados após criação |
| **Isolamento** | Cada experimento tem seus próprios snapshots |
| **Reutilização** | Mesma pergunta + mesmo experimento = mesmo snapshot |
| **Shadow Experiments** | Dev mode cria experimento automático para isolamento |
| **Validação** | Consistência entre question_id e snapshot JSON |
| **Ergonomia** | question_id em responses para queries fáceis |

## Próximos Passos

1. Execute benchmarks reais para validar o mecanismo
2. Monitore performance de queries com JOINs
3. Considere adicionar versionamento semântico às perguntas
4. Implemente ferramentas de análise de drift entre snapshots

---

**Documento criado**: 2026-03-08  
**Versão**: 1.0  
**Schema**: v2.1
