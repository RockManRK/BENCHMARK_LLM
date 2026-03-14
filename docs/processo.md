## 📘 DOCUMENTAÇÃO FINAL — FLUXO DE ESTUDO (VERSÃO CURTA E USÁVEL)

### 🎯 Objetivo
Planejar, executar e analisar um estudo de benchmark de LLMs  
de forma **segura, incremental e sem refazer trabalho**.

---

### 1️⃣ Criar um experimento (planejamento)
```bash
python bcllm.py experiment create enamed_2025 \
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
python bcllm.py experiment enamed_2025
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
python bcllm.py experiment enamed_2025 add-model \
  openai/gpt-4 \
  anthropic/claude-3
```

✔ Registra variantes  
❌ Não cria run  
❌ Não executa

---

### 4️⃣ Configurar variações de modelo
```bash
python bcllm.py experiment enamed_2025 add-model \
  openai/gpt-4 --reasoning auto \
  openai/gpt-4 --reasoning off
```

✔ Cria variantes distintas  
✔ Permite comparação justa

---

### 5️⃣ Criar uma run (execução)
```bash
python bcllm.py run create enamed_2025 --iterations 1
```

✔ Cria run  
✔ Define seed  
✔ Associa modelos  
❌ Não executa ainda

---

### 6️⃣ Executar o experimento

**Executar tudo que falta**
```bash
python bcllm.py run execute enamed_2025
```

**Executar parcialmente**
```bash
python bcllm.py run execute enamed_2025 --models 2,4
```

Ou:
```bash
python bcllm.py run execute enamed_2025 --questions Q001-Q050
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