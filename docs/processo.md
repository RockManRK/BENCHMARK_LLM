## 📘 DOCUMENTAÇÃO FINAL — FLUXO DE ESTUDO (VERSÃO CURTA E USÁVEL)

### 🎯 Objetivo
Planejar, executar e analisar um estudo de benchmark de LLMs
de forma **segura, incremental e sem refazer trabalho**.

---

### 1️⃣ Criar um experimento (planejamento)
```bash
python bcllm.py --create-experiment enamed_2025 \
  --questions where status=active \
  --seed AUTO
```

✔ Cria o experimento
✔ Congela prompt e política de seed
✔ Cria snapshots das perguntas
❌ Não executa nada

---

### 2️⃣ Visualizar o experimento
```bash
python bcllm.py --experiment enamed_2025
```

Mostra:
- perguntas incluídas
- prompt
- modelos configurados
- runs existentes
- status geral

---

### 3️⃣ Adicionar modelos ao experimento
```bash
python bcllm.py --experiment enamed_2025 \
  --add-model openai/gpt-4 \
  --add-model anthropic/claude-3
```

✔ Registra variantes
❌ Não cria run
❌ Não executa

---

### 4️⃣ Configurar variações de modelo
```bash
python bcllm.py --experiment enamed_2025 \
  --add-model openai/gpt-4 --reasoning-effort high \
  --add-model anthropic/claude-3 --reasoning-effort medium
```

✔ Cria variantes distintas
✔ Permite comparação justa

**Valores válidos**: `xhigh`, `high`, `medium`, `low`, `minimal`, `none`

**Nota**: Se `--reasoning-effort` não for informado, o sistema **não envia nenhuma configuração de reasoning**, permitindo que o modelo use seu comportamento padrão.

**Especial**: Use `--reasoning-effort none` para desabilitar explicitamente o reasoning.

---

### 5️⃣ Criar uma run (execução)
```bash
python bcllm.py --experiment enamed_2025 \
  --create-run --iterations 1
```

✔ Cria run
✔ Define seed
✔ Associa modelos
❌ Não executa ainda

---

### 6️⃣ Executar o experimento

**Executar tudo que falta**
```bash
python bcllm.py --experiment enamed_2025 --run
```

**Executar parcialmente**
```bash
python bcllm.py --experiment enamed_2025 --run --models openai/gpt-4
```

Ou:
```bash
python bcllm.py --experiment enamed_2025 --run --questions Q001-Q050
```

✔ Sistema detecta pendências
✔ Nada é reexecutado

---

### 7️⃣ Fluxo rápido (continua existindo)
```bash
python bcllm.py --experiment quick_test \
  --models gpt-4 \
  --questions Q001-Q020
```

✔ Cria tudo
✔ Executa
✔ Pronto

---

## 🧠 Decisão importante: `.env` por experimento?
👉 **Não agora.**

Motivos:
- banco já é a fonte de verdade
- `.env` por experimento cria drift
- dificulta UI futura

📌 O sistema deve **ajudar a editar**, não delegar isso a arquivos.

---

## 📋 COMANDOS DISPONÍVEIS

### Gerenciamento de Experimentos

| Comando | Descrição |
|---------|-----------|
| `--create-experiment <name>` | Criar novo experimento |
| `--experiment <name>` | Ver detalhes do experimento |
| `--experiment <name> --add-model <model>` | Adicionar modelo (pode repetir) |
| `--experiment <name> --remove-model <id>` | Remover modelo |
| `--experiment <name> --create-run` | Criar run |
| `--experiment <name> --run` | Executar run |

### Parâmetros Comuns

| Parâmetro | Descrição |
|-----------|-----------|
| `--questions <ids>` | Filtrar perguntas (ex: `Q001-Q100`) |
| `--seed AUTO\|<int>` | Política de seed |
| `--iterations <n>` | Número de iterações |
| `--models <ids>` | Filtrar modelos na execução |
| `--reasoning-effort <level>` | Nível de reasoning: `xhigh`, `high`, `medium`, `low`, `minimal`, `none` |

**Nota sobre reasoning**: Se `--reasoning-effort` não for especificado, o sistema **não envia nenhuma configuração de reasoning** para a API, permitindo que o modelo use seu comportamento padrão.

---