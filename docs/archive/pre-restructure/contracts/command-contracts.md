# name: "command-contracts.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## 1. Propósito

Definir os **contratos comportamentais** dos comandos do sistema.

Este documento especifica:
- o que cada comando PODE fazer
- o que cada comando NÃO PODE fazer
- quando o banco de dados pode ser modificado
- quais entidades podem ser criadas

Ele **não descreve fluxo**, apenas **efeitos permitidos**.

---

## 2. Princípios Invariantes

- Comandos nunca executam modelos implicitamente
- Comandos nunca inferem identidade
- Comandos nunca alteram dados históricos
- Execução e persistência são responsabilidades separadas
- Toda escrita no banco deve ser intencional

---

## 3. `--create-experiment`

### Cria
- `experiment`

### Grava no banco
- tabela `experiments`

### Não cria
- runs
- modelos
- snapshots
- respostas

### Observações
- Experimento nasce vazio
- Configuração inicial é congelada

---

## 4. `--add-model`

### Cria
- `model_variant`

### Grava no banco
- tabela `model_variants`

### Não cria
- runs
- respostas
- erros

### Observações
- Variante define identidade
- Variante nunca executa nada

---

## 5. `--add-questions`

### Cria
- `question_snapshots`

### Grava no banco
- tabela `question_snapshots`

### Não cria
- runs
- respostas
- erros

### Observações
- Snapshot é imutável
- Operação é idempotente

---

## 6. `--create-run`

### Cria
- `run`

### Grava no banco
- tabela `runs`

### Não cria
- respostas
- erros
- execution plan

### Observações
- Run não define escopo
- Run não executa nada

---

## 7. `--execute-run`

### Cria
- `ExecutionPlan` (em memória ou persistido como referência)

### Grava no banco
- `responses`
- `errors`
- atualização de status em `runs`

### Não cria
- experimentos
- modelos
- snapshots

### Observações
- Execução segue `execute-run.md`
- Persistência segue `result-writer.md`

---

## 8. Remoções (`--remove-*`)

### Permitido
- marcar entidades como inativas
- impedir novas execuções

### Proibido
- apagar dados históricos
- apagar respostas
- apagar erros

---

## 9. Regra de Ouro para Implementação

Se um comando:
- cria identidade → grava uma tabela
- executa → NÃO grava diretamente
- persiste resultado → usa ResultWriter

Se um comando fizer mais de uma dessas coisas, **está errado**.

---

## 10. Relação com Outros Documentos

- Fluxo de execução → `execute-run.md`
- Plano imutável → `execution-plan.md`
- Persistência → `result-writer.md`
- Modelo mental → `QWEN.md`
- Estado do código → `QWEN_TECH.md`