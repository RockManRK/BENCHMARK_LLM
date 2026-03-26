# name: "configurarion_resolution_contract.md"
# date: 24/03/2026
# version: 1.0
# Atenção!: nunca fazer alterações

---

## 📄 Documento reorganizado — *CLI Specification*

> **Nota**: Este documento define o comportamento desejado do CLI.  
> Nenhuma decisão implícita deve ser tomada fora do que está explicitamente descrito aqui.

---

### 🔧 Correção obrigatória — Validação de Model ID

**BUG IDENTIFICADO**

O validador atual de modelos é restritivo demais e rejeita IDs válidos do OpenRouter.

#### Comportamento esperado:
- Aceitar qualquer string no formato:
  ```
  <provider>/<model_id>
  ```
- Não validar internamente o nome do modelo
- Não impor regras sobre hífens, números ou sufixos

#### Exemplos válidos:
- `google/gemini-3.1-flash-lite-preview`
- `openai/gpt-4.1-mini`
- `anthropic/claude-3.5-sonnet`
- `stepfun/step-3.5-flash:free`
- `nvidia/nemotron-3-super-120b-a12b:free`

> Esta correção é **obrigatória** para permitir uso real do sistema.

---

# 1. Conceitos Fundamentais

## 1.1 Entidades

- **Experimento**
  - Entidade base do sistema
  - Contém configurações, modelos, perguntas e RUNs

- **Models**
  - Pertencem a um experimento
  - Podem ter configurações próprias
  - Herdam configurações do experimento quando não definidas

- **Questions**
  - Pertencem a um snapshot do experimento
  - São imutáveis após salvas

- **RUN**
  - Pertence a um experimento
  - Representa uma execução lógica
  - Possui seed próprio (imutável após criação)

---

# 2. Regras Gerais do Sistema

- Execução **nunca é implícita**
- Nenhuma entidade é criada automaticamente
- Alterações em experimento **não afetam RUNs já criados**
- Dados executados **nunca são apagados**
- Revisão manual é parte do fluxo oficial

---

# 3. Hierarquia de Configurações

```
RUN
 └── Experimento
      └── .env
           └── Defaults do sistema
```

### Regras:
- Valores não definidos herdam do nível acima
- `.env` só é lido no momento da criação do experimento
- Alterações no `.env` não afetam experimentos existentes

---

# 4. Comandos do CLI

## 4.1 Experimentos

### Criar experimento

```bash
bcllm --create-experiment <nome>
```

#### Flags opcionais:
- `--add-questions`
- `--seed`
- `--add-model`
- `--system-prompt`
- `--user-prompt`

> **Nota**: O suporte a múltiplas flags no mesmo comando é desejado, mas não obrigatório para a implementação inicial.

---

### Visualizar experimento

```bash
bcllm --experiment <nome>
```

---

### Adicionar perguntas ao experimento

```bash
bcllm --experiment <nome> --add-questions
```

#### Formatos aceitos:
- 1 5 10
- 5-20
- 1-50 --where status=valid
- --exclude status=annulled
- Combinações com múltiplos filtros

---

### Seed do experimento

```bash
bcllm --experiment <nome> --seed <AUTO | vazio | número>
```

- `AUTO`: gera seed fixo por RUN
- Seed do experimento **não altera RUNs existentes**

---

## 4.2 Models

### Adicionar model ao experimento

```bash
bcllm experiment <nome> --add-model <model_id>
```

- O comando adiciona **um único modelo por invocação**
- Para adicionar múltiplos modelos, repetir o comando
- Flags subsequentes se aplicam **apenas ao modelo informado**

#### Flags opcionais por model:
- `--reasoning`
- `--max-tokens`
- `--reasoning-tokens`
- `--temperature`
- `--top-p`
- `--top-k`
- `--vision`
- `--structured`
- `--base-url`

> **Nota**: O sistema pode aceitar `--add-models` como alias interno, mas o comando documentado e recomendado é `--add-model`.

---

### Remover models

```bash
bcllm experiment <nome> --remove-models <model1> <model2>
```

```bash
bcllm experiment <nome> --remove-models ?
```

---

## 4.3 Structured — Comportamento esperado

- A flag `--structured` deve seguir o **mesmo comportamento funcional da versão anterior do sistema**
- Caso necessário, revisar a implementação antiga para entender o sistema. APENAS para referência tecnica.
- O objetivo é preservar o comportamento já validado anteriormente, porém deve ser reimplementado pensando no modelo do sistema novo, nunca do sistema antigo.

> Structured afeta o formato da resposta e **não deve ser tratado como detalhe opcional**.

---

## 4.4 RUNs

### Criar RUN

```bash
bcllm experiment <nome> --add-run
```

#### Flags:
- `--seed`
- `--system-prompt`
- `--user-prompt`

> Após criado, nenhum desses valores pode ser alterado.

---

### Remover RUN

```bash
bcllm experiment <nome> --remove-run <id>
```

```bash
bcllm experiment <nome> --remove-run ?
```

---

## 4.5 Execução

```bash
bcllm experiment <nome> --execute
```

#### Filtros opcionais:
- `--run`
- `--questions`
- `--models`

### Regras:
- Execuções parciais só processam itens pendentes
- Se nada estiver pendente, exibir aviso

---

## 4.6 Ordem de Execução — Status

- A execução pode suportar diferentes estratégias de ordenação:
  - `run` (padrão)
  - `model`
  - `question`

> **Nota**:  
> A implementação inicial **pode suportar apenas a estratégia padrão**.  
> As demais estratégias ficam documentadas para implementação futura.

---

# 5. Revisão Manual

```bash
bcllm --review-experiment <nome>
```

### Interface:
- Navegação por teclado
- Classificação A/B/C/D/N/E
- Persistência incremental
- Estatísticas em tempo real

*(Interface conforme descrita no documento original)* @docs\architecture\to-be\comandos_simples.md

---

# 6. Itens Fora de Escopo (Por Enquanto)

- Websearch
- Paralelismo
- Execução distribuída
- Compatibilidade com V1 (De forma alguma, V1 foi um experimento conceitual, apenas isso)

---

# 7. Decisões Fechadas

- Usar **`models`** no plural
- Seed é imutável após criação do RUN
- Execução nunca é implícita
- Configurações não definidas são ignoradas na requisição