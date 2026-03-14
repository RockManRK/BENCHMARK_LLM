Rock, agora dá para responder **com precisão cirúrgica**, porque você trouxe exatamente o que faltava:  
o **modelo real do sistema** + o **modelo mental que você quer**.

Vou responder **direto**, sem floreio, focando em **como você termina isso hoje** e já roda seu primeiro experimento **sem quebrar nada**.

---

# 🧠 O FLUXO IDEAL (ALINHADO AO SEU RACIOCÍNIO E AO SISTEMA ATUAL)

A boa notícia primeiro:

> **Você NÃO precisa mudar o banco, nem o core.**  
> Tudo que você quer já é suportado.  
> O que falta é **organizar o fluxo humano**.

---

## 1️⃣ Criar experimento (planejamento, sem execução)

### Fluxo mental
> “Quero definir um estudo. Nada vai rodar ainda.”

### Fluxo ideal
```bash
python bcllm.py experiment create enamed_2025 \
  --questions where status=active \
  --prompt default \
  --seed-policy AUTO
```
[no lugar de "--seed-policy" usar só "--seed"?]
### O que acontece internamente
- Cria `experiment`
- Congela:
  - prompt
  - política de seed
  - política de structured outputs
- Cria `question_snapshots`
- **Não cria run**
- **Não executa nada**

📌 Isso já existe conceitualmente no sistema.  
Só não está exposto como comando separado.

---

## 2️⃣ Visualizar experimento (antes de rodar)

### Fluxo mental
> “Quero ver o que eu defini.”

### Fluxo ideal
```bash
python bcllm.py experiment show enamed_2025
```
[Também poder usar o comando "python bcllm.py experiment enamed_2025"? Sem o "show".]
### Mostra:
- perguntas incluídas
- prompt
- modelos (se houver)
- runs existentes
- status geral

📌 Isso reduz 80% da ansiedade cognitiva.

---

## 3️⃣ Escolher modelos (participantes)

### Fluxo mental
> “Quais modelos vão participar do estudo?”

### Fluxo ideal
```bash
python bcllm.py experiment add-model enamed_2025 \
  openai/gpt-4 \
  anthropic/claude-3 \
  google/gemini-1.5
```
[Para mim, esse comando "python bcllm.py experiment add-model enamed_2025 \" faz mais sentido com posições diferentes "python bcllm.py experiment enamed_2025 add-model \". Seria algo como "No experimento ENAMED_2025 eu quero ADICIONAR MODELOS". Existe algum motivo para aquela ordem em particular ou é arbitrário?]
### Internamente
- Registra `model_variants`
- **Não cria run**
- **Não executa**

📌 Modelos pertencem ao **estudo**, não à execução.

---

## 4️⃣ Configurar modelos (identidade, não execução)

### Fluxo mental
> “Quero comparar reasoning on vs off.”

### Fluxo ideal
```bash
python bcllm.py experiment add-model enamed_2025 \
  openai/gpt-4 --reasoning auto \
  openai/gpt-4 --reasoning off
```

### Resultado
- Duas `model_variants`
- IDs diferentes
- Mesmo modelo base

📌 Isso já está **perfeitamente alinhado** com seu schema atual.

---

## 5️⃣ Adicionar ou remover modelos depois

### Fluxo mental
> “Quero testar mais um modelo.”

### Fluxo ideal
```bash
python bcllm.py experiment add-model enamed_2025 qwen/qwen-2.5
```

Ou remover:
```bash
python bcllm.py experiment remove-model enamed_2025 model_id
```

📌 Isso **não afeta runs existentes**.

---

## 6️⃣ Configuração: CLI vs `.env`

### Regra simples (e correta)
- `.env` = **defaults globais**
- CLI = **override explícito**
- Banco = **fonte de verdade**

📌 **NÃO crie `.env` por experimento agora.**
Isso adiciona:
- sincronização difícil
- risco de drift
- complexidade desnecessária

Seu banco já é o lugar certo.

---

## 7️⃣ Adicionar runs (execução)

### Fluxo mental
> “Agora quero rodar.”

### Fluxo ideal
```bash
python bcllm.py run create enamed_2025 --iterations 1
```

Isso:
- cria `run`
- define seed
- associa modelos
- **não executa ainda**

---

## 8️⃣ Rodar tudo ou parcialmente

### Rodar tudo
```bash
python bcllm.py run execute enamed_2025
```

### Rodar parcial
```bash
python bcllm.py run execute enamed_2025 --models 3,5
```

Ou:
```bash
python bcllm.py run execute enamed_2025 --questions Q001-Q050
```

📌 O executor já sabe:
- o que falta
- o que pular
- o que não repetir

---

## 9️⃣ Fluxo rápido (não mexer muito)

Você está certo: **não mate isso**.

Isso continua válido:
```bash
python bcllm.py --experiment teste \
  --models gpt-4 \
  --questions Q001-Q050
```

Internamente:
- cria experimento
- cria run
- executa
- pronto

📌 Esse é o “modo impulso”.

---

# 🔴 O QUE NÃO FAZER AGORA (IMPORTANTE)

- ❌ Não criar UI agora
- ❌ Não criar `.env` por experimento
- ❌ Não refatorar schema
- ❌ Não tentar resolver tudo

---

# 🟢 O QUE FAZER HOJE (PARA RODAR SEU PRIMEIRO TESTE)

### Passo 1
Escolha **um experimento real** (ex: ENAMED 2025)

### Passo 2
Use o fluxo rápido **uma vez**, só para validar:
```bash
python bcllm.py --experiment enamed_test \
  --models gpt-4 \
  --questions Q001-Q020
```

### Passo 3
Depois disso, **pare** e implemente só:
- `experiment show`
- `run execute`

Nada mais.

---

# 🧠 Conclusão honesta

Rock, você não está perdido.  
Você está **exatamente no ponto onde o sistema ficou mais poderoso do que confortável**.

A solução não é técnica.  
É **organizar o caminho feliz**.

Se você quiser, no próximo passo eu posso:
- escrever a documentação final do “Fluxo de Estudo”
- ou te dizer exatamente **quais comandos mínimos** implementar hoje
- ou ajudar a decidir **o que fica escondido como avançado**

Você está a **uma boa noite de trabalho** de rodar seu primeiro benchmark sério.