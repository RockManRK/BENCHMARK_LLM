# name: "cli_module_resolution.md"
# date: 31/03/2026
# version: 1.0
# Atenção!: nunca fazer alterações

# 📜 CLI Module Resolution Contract (V2)

---

## 1. Objetivo

Definir regras determinísticas e sem ambiguidade para resolução de **MODE**, **MODULE** e **fluxos compostos** na CLI do sistema V2.

Este contrato elimina dependência da ordem dos argumentos e permite comandos compostos válidos em um único invocation.

---

## 2. Conceitos Fundamentais

### 2.1 MODE

O MODE define **o tipo de operação principal**:

| MODE | Descrição |
|-----|----------|
| CREATE | Criação de entidades |
| MODIFY | Modificação de entidades existentes |
| EXECUTE | Execução de planos |
| QUERY | Listagem / inspeção |

O MODE **não define o módulo final**, apenas o contexto inicial.

---

### 2.2 MODULE

O MODULE define **a ação concreta** a ser executada:

Exemplos:
- `bcllm_experiment`
- `bcllm_model`
- `bcllm_questions`
- `bcllm_run`
- `bcllm_execute`

---

### 2.3 Flags de Contexto vs Flags de Ação

#### Flags de Contexto
Definem **escopo**, não ação:

- `--experiment`
- `--run-id`
- `--variant`
- `--snapshot`

#### Flags de Ação
Definem **operações concretas**:

- `--create-experiment`
- `--add-model`
- `--add-questions`
- `--add-run`
- `--execute`
- `--list-*`

---

## 3. Regra de Prioridade de Resolução

### 3.1 Princípio Geral

> **Flags de ação específicas sempre têm prioridade sobre flags genéricas ou de contexto.**

A ordem dos argumentos **NUNCA** deve influenciar a resolução final.

---

### 3.2 Resolução de MODULE

1. Identificar todas as **flags de ação presentes**
2. Se houver **uma única ação específica**, ela define o MODULE
3. Se houver múltiplas ações incompatíveis → erro explícito
4. Flags de contexto **nunca definem MODULE**

---

## 4. Fluxos Compostos (Regra Crítica)

### 4.1 CREATE + ADD\_\*

Durante `--create-experiment`, é **explicitamente permitido** executar ações adicionais no mesmo comando:

```bash
--create-experiment EXP \
--add-model MODEL \
--add-questions Q \
--add-run
```

### Regra:

> Se `--create-experiment` estiver presente, o sistema DEVE:
>
> 1. Criar o experimento
> 2. Propagar o contexto do experimento recém-criado
> 3. Executar todas as ações `--add-*` subsequentes

🚫 **É proibido bloquear `ADD_*` durante CREATE.**

---

### 4.2 Validação de MODE × MODULE

A validação **não pode ser feita isoladamente**.

❌ ERRADO:
```
(CREATE, bcllm_questions) → inválido
```

✅ CORRETO:
```
CREATE → cria experimento
ADD_QUESTIONS → executado dentro do contexto criado
```

---

## 5. Casos Inválidos

| Caso | Motivo |
|----|-------|
| `--add-questions` sem `--experiment` ou `--create-experiment` | Falta de contexto |
| `--add-model` + `--execute` | Ações incompatíveis |
| Múltiplos `--add-*` conflitantes | Ambiguidade |

---

## 6. Invariantes

- A resolução é **determinística**
- A ordem dos argumentos **não importa**
- O comportamento é **previsível**
- O usuário pode configurar tudo em **um único comando**