# Evolução de Experimentos vs Imutabilidade de Runs

## Princípios Fundamentais

### 1. Experimentos PODEM EVOLUIR
- O conjunto de perguntas de um experimento pode ser expandido
- Novos modelos podem ser adicionados
- Configurações podem ser ajustadas

### 2. Runs SÃO IMUTÁVEIS
- Uma run criada captura o estado do experimento naquele momento
- Runs passadas NUNCA são alteradas retroativamente
- O passado é preservado para reprodutibilidade

### 3. Snapshots SÃO ÚNICOS
- Cada pergunta tem UM snapshot por experimento
- Snapshots existentes NUNCA são recriados
- Novos snapshots são criados apenas para perguntas novas

---

## Comportamento de Evolução

### Cenário: Expandir Conjunto de Perguntas

**Situação inicial:**
- Experimento criado com perguntas Q001–Q020
- Run #1 executada com Q001–Q020

**Evolução:**
```bash
bcllm --experiment my_exp --add-questions Q021-Q040
```

**Resultado:**
- ✅ Snapshots criados apenas para Q021–Q040 (20 novos)
- ✅ Snapshots de Q001–Q020 NÃO são recriados (preservados)
- ✅ Run #1 continua usando apenas Q001–Q020 (imutável)
- ✅ Run #2 (futura) usará Q001–Q040 (atualizado)

---

## Comandos de Evolução

### Adicionar Perguntas

```bash
# Adicionar range de perguntas
bcllm --experiment my_exp --add-questions Q021-Q040

# Adicionar perguntas específicas
bcllm --experiment my_exp --add-questions Q021,Q022,Q023

# Combinar range e específicas
bcllm --experiment my_exp --add-questions Q021-Q030,Q035,Q040
```

**Comportamento:**
- Cria snapshots apenas para perguntas NOVAS
- Ignora perguntas que já possuem snapshot
- Não altera runs existentes

### Adicionar Modelos

```bash
# Adicionar modelo ao experimento
bcllm --experiment my_exp --add-model openai/gpt-4

# Adicionar com configuração de reasoning
bcllm --experiment my_exp --add-model openai/o1 --reasoning-effort high
```

**Comportamento:**
- Registra variante do modelo no experimento
- Não altera runs existentes
- Próximas runs poderão usar o novo modelo

### Remover Modelos

```bash
# Remover modelo específico
bcllm --experiment my_exp --remove-model openai/gpt-4

# Modo interativo
bcllm --experiment my_exp --remove-model ?
```

**Comportamento:**
- Remove associação modelo-experimento
- Não remove snapshots ou dados históricos
- Runs existentes mantêm referência ao modelo

---

## Ciclo de Vida Típico

### Dia 1: Criar Experimento
```bash
bcllm --create-experiment exp_v1 --questions Q001-Q020
bcllm --experiment exp_v1 --add-model google/gemini-3.1-flash-lite-preview
bcllm --experiment exp_v1 --create-run --iterations 3
bcllm --experiment exp_v1 --run
```

**Estado:**
- Experimento: Q001–Q020, 1 modelo
- Run #1: 3 iterações, Q001–Q020

### Dia 2: Expandir Perguntas
```bash
bcllm --experiment exp_v1 --add-questions Q021-Q040
bcllm --experiment exp_v1 --create-run --iterations 3
bcllm --experiment exp_v1 --run
```

**Estado:**
- Experimento: Q001–Q040, 1 modelo (evoluído)
- Run #1: 3 iterações, Q001–Q020 (imutável)
- Run #2: 3 iterações, Q001–Q040 (usa evolução)

### Dia 3: Adicionar Modelo
```bash
bcllm --experiment exp_v1 --add-model openai/gpt-4
bcllm --experiment exp_v1 --create-run --iterations 3
bcllm --experiment exp_v1 --run
```

**Estado:**
- Experimento: Q001–Q040, 2 modelos (evoluído)
- Run #1: 3 iterações, Q001–Q020, 1 modelo (imutável)
- Run #2: 3 iterações, Q001–Q040, 1 modelo (imutável)
- Run #3: 3 iterações, Q001–Q040, 2 modelos (usa evolução)

---

## O Que NÃO Acontece

### ❌ Recriação de Snapshots
- Snapshots existentes NUNCA são recriados
- O comando `--add-questions` não toca em snapshots antigos
- Cada snapshot é criado UMA ÚNICA vez

### ❌ Alteração de Runs Passadas
- Runs completadas permanecem inalteradas
- Dados históricos são preservados
- Não há "atualização em cascata"

### ❌ Comportamento Implícito
- Evolução sempre EXPLÍCITA (--add-questions)
- Sem atualizações automáticas ou silenciosas
- Usuário tem controle total

---

## Fonte da Verdade

| Componente | Fonte da Verdade | Mutabilidade |
|------------|-----------------|--------------|
| **Perguntas disponíveis** | Dataset JSON (`QUESTIONS_DATASET_PATH`) | Externo |
| **Perguntas do experimento** | Snapshots no banco | Evolutivo |
| **Runs** | Tabela `runs` + `run_models` | Imutável |
| **Respostas** | Tabela `responses` | Imutável |

---

## Boas Práticas

### 1. Versionamento Implícito
Cada run captura o estado do experimento. Use isso para:
- Comparar desempenho entre versões do experimento
- Reproduzir resultados exatos
- Auditar mudanças

### 2. Evolução Gradual
Expanda experimentos em etapas:
```bash
# Fase 1: Q001-Q020
bcllm --create-experiment exp --questions Q001-Q020
bcllm --experiment exp --create-run --iterations 3
bcllm --experiment exp --run

# Fase 2: Q021-Q040
bcllm --experiment exp --add-questions Q021-Q040
bcllm --experiment exp --create-run --iterations 3
bcllm --experiment exp --run
```

### 3. Documentação
Mantenha registro das evoluções:
```bash
# Adicione descrição ao criar/run
bcllm --create-experiment exp_v1 --questions Q001-Q020
# Descrição: "Fase inicial - 20 perguntas"

bcllm --experiment exp_v1 --add-questions Q021-Q040
# Descrição: "Expansão para 40 perguntas"
```

---

## Resolução de Problemas

### "Minha run não está usando as novas perguntas"

**Causa:** Runs são imutáveis. A run foi criada antes da evolução.

**Solução:** Crie uma nova run:
```bash
bcllm --experiment my_exp --create-run --iterations 3
bcllm --experiment my_exp --run
```

### "Adicionei perguntas mas o número não mudou"

**Causa:** As perguntas já possuem snapshot (foram adicionadas antes).

**Solução:** Verifique os snapshots existentes:
```bash
bcllm --experiment my_exp
# Mostra "Total Questions: N"
```

### "Quero remover perguntas antigas"

**Resposta:** Não é possível. Snapshots são imutáveis.

**Alternativa:** Crie um novo experimento:
```bash
bcllm --create-experiment exp_v2 --questions Q001-Q010
```

---

## Resumo

| Ação | Afeta Runs Passadas? | Cria Novos Snapshots? |
|------|---------------------|----------------------|
| `--create-experiment` | N/A | Sim (todos) |
| `--add-questions` | ❌ Não | ✅ Apenas novos |
| `--add-model` | ❌ Não | ❌ Não |
| `--remove-model` | ❌ Não | ❌ Não |
| `--create-run` | N/A | ❌ Não (usa existentes) |
| `--run` | ❌ Não | ❌ Não (apenas executa) |

**Princípio:** O passado é sagrado. O futuro é flexível.
