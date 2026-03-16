Rock, respira.  
O que você descreveu **não é caos**, é exatamente o que acontece quando um sistema deixa de ser “teoricamente correto” e começa a ser **exercitado de verdade**. A ansiedade é compreensível — mas a boa notícia é: **os problemas estão bem localizados e têm uma causa comum**.

Vou organizar isso em três camadas, para você sair desse estado de “perdidinho” com um **mapa claro**.

---

## 🧠 VISÃO GERAL — O QUE ESTÁ ACONTECENDO DE VERDADE

Quase **todos os problemas que você descreveu** convergem para **um único erro conceitual central**:

> **A identidade da variante de modelo está mal definida e mal aplicada ao longo do fluxo.**

Isso gera efeitos em cascata:
- respostas sendo atribuídas ao modelo errado
- variantes sendo “recriadas” durante execução
- deduplicação errada
- execução pulando modelos
- logs confusos
- banco parecendo “assombrado”

📌 **O sistema não sabe, de forma inequívoca, o que torna uma variante única.**

Vamos destrinchar ponto a ponto.

---

## 1️⃣ BUG CRÍTICO — POR QUE SÓ 100 RESPONSES EM VEZ DE 200

Você tinha:
- 100 perguntas
- 2 variantes do mesmo modelo base

Resultado esperado:
- **200 respostas**

Resultado real:
- **100 respostas**

### O que aconteceu
O sistema:
- executou corretamente o **primeiro modelo**
- ao iniciar o segundo, achou que **todas as perguntas já estavam respondidas**
- pulou a execução

### Por quê?
Porque o critério usado para verificar:
> “essa pergunta já foi respondida?”

**não está levando em conta a variante corretamente**.

Ele está tratando:
```
google/gemini-3.1-flash-lite-preview
```
como se fosse **um único modelo**, ignorando:
- reasoning_effort
- reasoning_mode
- outras flags

📌 Resultado: respostas do modelo A “valem” para o modelo B.

👉 **Isso é bug real, estrutural, e precisa ser corrigido primeiro.**

---

## 2️⃣ BUG E DECISÃO ARQUITETURAL — MODEL_VARIANTS ENTRE EXPERIMENTOS

> “Se eu adicionar exatamente o mesmo modelo, com as mesmas configurações, em dois experimentos diferentes, eles devem ser variantes diferentes?”

### Resposta correta
**NÃO.**

A regra saudável é:

- `model_variants` representam **configurações únicas de modelo**
- Elas são **globais**
- Experimentos apenas **referenciam** variantes

📌 Isso está certo no conceito.

### O problema
O sistema:
- tenta deduplicar variantes
- mas **não usa todos os campos relevantes**
- e pior: **cria variantes novas durante a execução**, o que nunca deveria acontecer

---

## 3️⃣ BUG GRAVÍSSIMO — VARIANTES SENDO CRIADAS DURANTE EXECUÇÃO

Esse trecho do log é a chave de tudo:

```
Registered model variant: var-4fadde11 | model=google/gemini-3.1-flash-lite-preview | signature=...reasoning=unspecified...
```

Isso acontece **durante a execução**, não na fase de setup.

### Isso é conceitualmente errado
Execução:
- **NUNCA cria variantes**
- **NUNCA resolve identidade**
- **NUNCA deduz configuração**

Ela **recebe** uma variante pronta e executa.

📌 Esse comportamento explica:
- variantes “unspecified”
- variantes duplicadas
- execução pulando modelos
- banco ficando incoerente

👉 **Esse é o bug mais importante do sistema hoje.**

---

## 4️⃣ A CAUSA RAIZ (FINALMENTE)

Você mesmo chegou muito perto da resposta, e está certo:

> “Como o sistema não está criando variantes iguais, eu acho que quando adicionei os dois, nenhum model variant foi criado, mas quando rodei o experimento, ele criou uma só duplicata…”

Exatamente isso.

### Em termos técnicos
- A identidade da variante está sendo calculada de forma inconsistente
- Em alguns pontos:
  - reasoning_effort entra
- Em outros:
  - reasoning_effort vira `None`
- Em outros:
  - vira `unspecified`

📌 **A assinatura da variante não é estável.**

---

## 5️⃣ SOBRE O NOME DA VARIANTE (UX, NÃO BUG)

Você está certo aqui também.

Isso:
```
google/gemini-3.1-flash-lite-preview::reasoning=effort:low::vision=true::structured=none
```

é ótimo como **signature técnica**, mas péssimo como **nome humano**.

O ideal é ter:
- `variant_signature` → técnica, completa, imutável
- `variant_display_name` → curta, legível

Exemplo:
```
Gemini 3.1 Flash Lite (low)
Gemini 3.1 Flash Lite (no reasoning)
```

📌 Isso é ajuste de UX, não bug.

---

## 6️⃣ QUESTÃO 55 — NÃO É BUG, É REGRA NÃO DEFINIDA

Aqui você tocou num ponto importante.

Campo:
```
"answer_key": "CONTESTED"
```

### O sistema hoje
- tenta randomizar
- não encontra resposta correta
- explode

### O que deveria acontecer
Isso precisa virar **regra explícita**.

Sugestão saudável:
- Se `answer_key` não for uma alternativa válida:
  - marcar a pergunta como **invalid**
  - registrar erro específico
  - **não contar para accuracy**
  - continuar execução

📌 Isso não é bug.  
📌 É **comportamento não especificado**.

---

## 🧩 PLANO DE AÇÃO (ORDEM CORRETA)

Agora vem a parte mais importante.

### 🔴 PRIORIDADE 1 — BLOQUEANTE
1. **Proibir criação de model_variants durante execução**
2. Garantir que:
   - toda execução recebe `variant_id` resolvido
   - nenhuma dedução acontece depois

### 🔴 PRIORIDADE 2 — IDENTIDADE
3. Definir formalmente:
   - quais campos fazem parte da identidade da variante
   - gerar signature única e estável
4. Usar essa signature:
   - para deduplicação
   - para lookup
   - para verificação de respostas existentes

### 🟡 PRIORIDADE 3 — UX E CLAREZA
5. Criar `variant_display_name`
6. Ajustar logs para sempre mostrar:
   - variant_id
   - display_name

### 🟢 PRIORIDADE 4 — DADOS IMPERFEITOS
7. Definir política para perguntas inválidas (`CONTESTED`, vazio, etc.)
8. Implementar tratamento explícito

---

## 🏁 CONCLUSÃO (IMPORTANTE)

Rock, vou ser muito honesto com você:

👉 **Nada aqui indica que o projeto está “bem quebrado”.**  
👉 Indica que ele **chegou no ponto em que erros reais aparecem**.

Você:
- identificou corretamente os sintomas
- leu logs com atenção
- conectou os pontos
- chegou muito perto da causa raiz sozinho

Isso é **engenharia de verdade**.

Se quiser, no próximo passo eu posso:
- te ajudar a escrever **um prompt único e cirúrgico** para corrigir tudo isso
- ou quebrar em 2–3 prompts menores, na ordem certa
- ou até te ajudar a escrever um “contrato de identidade de variante” para nunca mais ter esse problema

Você não está perdido.  
Você está **no meio da parte difícil** — e isso é um ótimo sinal.