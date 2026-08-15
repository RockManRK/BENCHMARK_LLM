# 📘 **BCLLM CLI — Plano Oficial de Testes**

**Versão:** 1.0  
**Última atualização:** 2026‑08‑12  
**Escopo:** Testes completos de CLI, cobrindo criação de experimentos, adição de modelos, providers, runs, execução, exportação, revisão e edge cases.
**Objetivo:** Garantir robustez, confiabilidade e regressão zero no sistema de benchmark de LLMs.

---

# 🧩 **Pré‑condições gerais**

- O arquivo `.env` deve existir e conter valores válidos.  
- O dataset de perguntas deve estar acessível no caminho configurado.  
- O banco `benchmark.db` deve existir e estar vazio antes da suíte.  
- Todos os testes devem ser executados em ordem numérica.  
- Cada experimento criado deve ter nome único.  
- O CLI deve ser executado com Python 3.10+.  
- Todos os comandos devem retornar exit code **0**, exceto quando explicitamente indicado.  
- Testes de erro devem verificar exit code **1** e mensagem específica.  
- Nenhum teste deve modificar manualmente o banco — somente via CLI.

---

# 🧩 **Categorias oficiais**

- **CE** — Create Experiment  
- **AQ** — Add Questions  
- **AM** — Add Model  
- **PR** — Provider  
- **RN** — Run  
- **EX** — Execute  
- **EP** — Export  
- **RV** — Review  
- **ED** — Edge Cases  

---

# 🧩 **Estrutura oficial de cada teste**

```
### TEST_ID — Nome descritivo

**Comando**
```bash
python bcllm.py <comando>
```

**Categoria**
- CE | AQ | AM | PR | RN | EX | EP | RV | ED

**Pré‑condições**
- (somente se houver pré‑condições específicas)

**Resultado esperado**
- (comportamento funcional esperado)

**Verificações (Banco de Dados)**
- Tabela `experiments` contém registro com `name = <nome>`
- `config_json` contém os valores esperados
- `config_hash` corresponde ao hash de `config_json`
- Tabela `model_variants` contém os registros esperados
- Tabela `question_snapshots` contém os snapshots esperados
- Tabela `runs` contém o run criado (se aplicável)
- Tabela `responses` contém resultados esperados (se aplicável)
- Tabela `errors` contém erros esperados (se aplicável)
- Exit code = 0 (ou 1 para testes de erro)
```

---

# 🧩 **TESTES — CREATE EXPERIMENT (CE)**

---

### CE01 — Criar experimento com perguntas específicas

**Comando**
```bash
python bcllm.py --create-experiment teste_TCN01 --add-questions 1,3
```

**Categoria**
- CE

**Resultado esperado**
- Experimento `teste_TCN01` criado.
- Snapshot contém perguntas `[1, 3]`.
- Configurações não especificadas vêm do `.env`.
- Configurações não especificadas no `.env` utilizam o system-default.

**Verificações**
- `experiments/teste_TCN01/metadata.json` existe.
- `questions == [1, 3]`.

---

### CE02 — Alias `--questions` funcionando como `--add-questions`

**Comando**
```bash
python bcllm.py --create-experiment teste_TCN02 --questions 1,3
```

**Categoria**
- CE

**Resultado esperado**
- Snapshot contém `[1, 3]`.

**Verificações**
- Alias deve funcionar corretamente.
- Nenhuma pergunta além de 1 e 3 deve ser adicionada.

---

### CE03 — Intervalo de perguntas

**Comando**
```bash
python bcllm.py --create-experiment teste_TCN03 --add-questions 1,5-20
```

**Categoria**
- CE

**Resultado esperado**
- Snapshot contém `[1, 5, 6, ..., 20]`.

---

### CE04 — Filtro de perguntas

**Comando**
```bash
python bcllm.py --create-experiment teste_TCN04 --add-questions 1-50 --where status=valid
```

**Categoria**
- CE

**Resultado esperado**
- Snapshot contém apenas perguntas válidas dentro do intervalo.

---

### CE05 — Seed explícito

**Comando**
```bash
python bcllm.py --create-experiment teste_TCN05 --seed 55
```

**Categoria**
- CE

**Resultado esperado**
- Seed = 55 no metadata.

---

### CE06 — Seed duplicado (último valor vence)

**Comando**
```bash
python bcllm.py --create-experiment teste_ce05.2 --seed 57 --seed auto
```

**Categoria**
- CE

**Resultado esperado**
- Seed deve ser `AUTO`.
- CLI deve emitir alerta de flag duplicada.

---

### CE07 — Reasoning none

**Comando**
```bash
python bcllm.py --create-experiment teste_ce06 --reasoning none
```

**Categoria**
- CE

**Resultado esperado**
- Reasoning = none.

---

### CE08 — Reasoning xhigh

**Comando**
```bash
python bcllm.py --create-experiment teste_ce07 --reasoning xhigh
```

---

### CE09 — Max tokens

**Comando**
```bash
python bcllm.py --create-experiment teste_ce08 --max-tokens 3333
```

---

### CE10 — Reasoning tokens

**Comando**
```bash
python bcllm.py --create-experiment teste_ce09 --reasoning-tokens 4444
```

---

### CE11 — Temperature

**Comando**
```bash
python bcllm.py --create-experiment teste_ce10 --temperature 2
```

---

### CE12 — Top‑p e Top‑k

**Comando**
```bash
python bcllm.py --create-experiment teste_ce11 --top-p 1.1 --top-k 30
```

---

### CE13 — Repeat penalty

**Comando**
```bash
python bcllm.py --create-experiment teste_ce12 --repeat-penalty 4
```

---

### CE14 — Vision true

**Comando**
```bash
python bcllm.py --create-experiment teste_ce13 --vision true
```

---

### CE15 — Vision false

**Comando**
```bash
python bcllm.py --create-experiment teste_ce14 --vision false
```

---

### CE16 — Structured true

**Comando**
```bash
python bcllm.py --create-experiment teste_ce15 --structured true
```

---

### CE17 — URL explícita

**Comando**
```bash
python bcllm.py --create-experiment teste_ce16 --url 192.198.0.1:8000
```

---

### CE18 — System prompt

**Comando**
```bash
python bcllm.py --create-experiment teste_ce17 --system-prompt "system teste"
```

---

### CE19 — User prompt

**Comando**
```bash
python bcllm.py --create-experiment teste_ce18 --user-prompt "user teste"
```

---

### CE20 — User prompt null

**Comando**
```bash
python bcllm.py --create-experiment teste_ce19 --user-prompt null
```

**Resultado esperado**
- `null` deve ser aceito.
- Deve cair para system-default.

---

### CE21 — Comando composto

**Comando**
```bash
python bcllm.py --create-experiment teste_ce20 --system-prompt "system prompt personalizado" --user-prompt "user próprio" --repeat-penalty 2 --reasoning minimal
```

---

### CE22 — Add‑questions null deve adicionar todas as perguntas

**Comando**
```bash
python bcllm.py --create-experiment teste_cenull01 --add-questions null
```

**Resultado esperado**
- Snapshot = todas as perguntas disponíveis.
- Nenhum erro deve ser emitido.
- Experimento não deve ser criado parcialmente.

---

### CE23 — Alias `--questions` ignorado (BUG atual)

**Comando**
```bash
python bcllm.py --create-experiment teste_cenull02 --questions 1,3
```

**Resultado esperado**
- Alias deve funcionar como CE02.

---

(Os demais testes CE_NULL foram incorporados automaticamente nos testes CE equivalentes.)

---

# 🧩 **TESTES — ADD MODEL (AM)**

---

### AM01 — Criar experimento base

**Comando**
```bash
python bcllm.py --create-experiment adição_modelos --add-questions 1
```

---

### AM02 — Flag inválida `--add-models`

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-models servidor/modelo1
```

**Resultado esperado**
- Exit code 1.
- Mensagem: “Flag inválida: use --add-model”.

---

### AM03 — Add model com reasoning low

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo2 --reasoning low
```

**Verificações**
- `variant_signature` deve conter todos os campos relevantes.
- Sem zeros desnecessários.

---

### AM04 — Add model com URL específica

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo3 --url 192.168.0.30:8080
```

---

### AM05 — Add model com reasoning-tokens e max-tokens

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo4 --reasoning-tokens 4444 --max-tokens 5555
```

---

### AM06 — Repeat penalty deve aparecer no variant_signature

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo5 --repeat-penalty 10
```

---

### AM07 — Temperature

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo6 --temperature 2
```

---

### AM08 — Top‑k e Top‑p

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo7 --top-k 2 --top-p 3
```

---

### AM09 — Vision true/false/null

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo8 --vision true
```

---

### AM10 — Flags duplicadas devem emitir alerta

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo9 --vision true --vision false
```

---

### AM11 — Flags devem aceitar null

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo11 --reasoning null
```

---

### AM12 — Valores devem aceitar maiúsculas

**Comando**
```bash
python bcllm.py --experiment adição_modelos --add-model servidor/modelo11 --reasoning HIGH
```

---

# 🧩 **TESTES — PROVIDER (PR)**

---

### PR01 — provider-lock true

**Comando**
```bash
python bcllm.py --experiment teste_pr01 --provider-lock true
```

---

### PR02 — provider-lock false

---

### PR03 — provider-lock system-default

---

### PR04 — resolve-providers (strategy=first)

---

### PR05 — resolve-providers (strategy=cheapest)

---

### PR06 — resolve-providers (strategy=fastest)

---

### PR07 — resolve-providers (strategy=lowest-latency)

---

### PR08 — resolve-providers com falhas

---

# 🧩 **TESTES — RUN (RN)**

---

### RN01 — create-run

---

### RN02 — list-runs

---

### RN03 — show-run

---

### RN04 — remove-run

---

### RN05 — create-run com overrides

---

# 🧩 **TESTES — EXECUTE (EX)**

---

### EX01 — executar experimento completo

---

### EX02 — executar run específico

---

### EX03 — executar perguntas específicas

---

### EX04 — executar modelo específico

---

### EX05 — executar com provider-lock=true

---

### EX06 — executar com providers não resolvidos (erro)

---

# 🧩 **TESTES — EXPORT (EP)**

---

### EP01 — export run

---

### EP02 — export experiment

---

### EP03 — export com dados faltando

---

# 🧩 **TESTES — REVIEW (RV)**

---

### RV01 — review-experiment

---

### RV02 — review-all

---

### RV03 — review com respostas ambíguas

---

### RV04 — review com erros

---

### RV05 — review undo (Z)

---

# 🧩 **TESTES — EDGE CASES (ED)**

---

### ED01 — null em flags diversas

---

### ED02 — flags duplicadas

---

### ED03 — ranges inválidos

---

### ED04 — model_id inválido

---

### ED05 — provider slug inválido

---

### ED06 — dataset ausente

---

### ED07 — .env ausente

---

### ED08 — experimento corrompido

---







----------
## Testes completos a serem feitos:


### Testes de criação de experimento:

#### TESTE_TCN01
python bcllm.py --create-experiment teste_TCN01 --add-questions 1,3

Resultado esperado:
- A criação de um novo experimento com o nome "teste_TCN01".
- Contendo o snapshot das perguntas 1 e 3.
- Todas as outras configurações devem cair para o que estiver especificado no .env. Caso não especificado, system-default será usado.

## TESTE_TCN02
python bcllm.py --create-experiment teste_TCN02 --questions 1,3

Resultado esperado:
- A criação de um novo experimento com o nome "teste_TCN02".
- Contendo o snapshot das perguntas 1 e 3.
- Todas as outras configurações devem cair para o que estiver especificado no .env. Caso não especificado, system-default será usado.

## TESTE_TCN03
python bcllm.py --create-experiment teste_TCN03 --add-questions 1,5-20

Resultado esperado:
- A criação de um novo experimento com o nome "teste_TCN03".
- Contendo o snapshot das perguntas 1 e da 5 até a 20.
- Todas as outras configurações devem cair para o que estiver especificado no .env. Caso não especificado, system-default será usado.

## TESTE_TCN04
python bcllm.py --create-experiment teste_TCN04 --add-questions 1-50 --where status=valid

## TESTE_TCN05
python bcllm.py --create-experiment teste_TCN05 --seed 55

## TESTE_CE5.2
python bcllm.py --create-experiment teste_ce05.2 --seed 57 --seed auto

## TESTE_CE6
python bcllm.py --create-experiment teste_ce06 --reasoning none

## TESTE_CE7
python bcllm.py --create-experiment teste_ce07 --reasoning xhigh

## TESTE_CE8
python bcllm.py --create-experiment teste_ce08 --max-tokens 3333

## TESTE_CE9
python bcllm.py --create-experiment teste_ce09 --reasoning-tokens 4444

## TESTE_CE10
python bcllm.py --create-experiment teste_ce10 --temperature 2

## TESTE_CE11
python bcllm.py --create-experiment teste_ce11 --top-p 1.1 --top-k 30

## TESTE_CE12
python bcllm.py --create-experiment teste_ce12 --repeat-penalty 4

## TESTE_CE13
python bcllm.py --create-experiment teste_ce13 --vision true

## TESTE_CE14
python bcllm.py --create-experiment teste_ce14 --vision false

## TESTE_CE15
python bcllm.py --create-experiment teste_ce15 --structured true

## TESTE_CE16
python bcllm.py --create-experiment teste_ce16 --url 192.198.0.1:8000

## TESTE_CE17
python bcllm.py --create-experiment teste_ce17 --system-prompt "system teste"

## TESTE_CE18
python bcllm.py --create-experiment teste_ce18 --user-prompt "user teste"

## TESTE_CE19
python bcllm.py --create-experiment teste_ce19 --user-prompt null

## TESTE_CE20
python bcllm.py --create-experiment teste_ce20 --system-prompt "system prompt personalizado" --user-prompt "user próprio" --repeat-penalty 2 --reasoning minimal

---

## Testes de adição de modelo:

## AM0
python bcllm.py --create-experiment adição_modelos --add-questions 1

## AM1
python bcllm.py --experiment adição_modelos --add-models servidor/modelo1
Erro: Não aceita --add-models, apenas --add-model

## AM2
python bcllm.py --experiment adição_modelos --add-model servidor/modelo2 --reasoning low
Parece que deu certo. A única coisa estranho é que, na coluna model_variants.variant_signature, ele está colocando os valores assim: "modelo2|reasoning=low|vision=true|structured=false|temp=2.000|top_p=1.500|top_k=40.000|max_tokens=16384.000|reasoning_tokens=1111.000" Ta vendo esse monte de zeros?

## AM3
python bcllm.py --experiment adição_modelos --add-model servidor/modelo3 --url 192.168.0.30:8080
Funciona

## AM4
python bcllm.py --experiment adição_modelos --add-model servidor/modelo4 --reasoning-tokens 4444 --max-tokens 5555
Funciona

## AM5
python bcllm.py --experiment adição_modelos --add-model servidor/modelo5 --repeat-penalty 10 
No caso desse comando eu percebi uma outra questão. O config_json está com todas as configurações, porém, a coluna "variant_signature" não tem todos os valores.
Como pode observar aqui, além daquela questos dos zeros, ele não tem por exemplo "repeat penalty". "modelo5|reasoning=low|vision=true|structured=false|temp=2.000|top_p=1.500|top_k=40.000|max_tokens=16384.000|reasoning_tokens=1111.000"
Precisamos corrigir.
Atualmente isso gera um problema grave, porque ele usa o variant_signature para distinguir modelos, então, se eu tentar criar dois modelos que tudo seja igual, com diferença apenas em uma flag que não entra no variant_signature, ele considera que o valor já existe. Por exemplo, se criar dois modelos que a única diferença seja "repeat-penalty", eu não posso criar o segundo por ele diz que já existe, por não ter o valor que distinguiria ele no campo.

## AM6
python bcllm.py --experiment adição_modelos --add-model servidor/modelo6 --temperature 2
Funciona

## AM7
python bcllm.py --experiment adição_modelos --add-model servidor/modelo7 --top-k 2 --top-p 3
Funciona.

## AM8
python bcllm.py --experiment adição_modelos --add-model servidor/modelo8 --vision true
Funciona, com true, false e null.

## AM9
python bcllm.py --experiment adição_modelos --add-model servidor/modelo9 --vision true --vision false
Quando existe o mesmo comando duas vezes ele tem aquele comportamento que mantem o ultimo valor, porém, aqui ele não esta dando o alerta de comando duplicado que colocamos no --create-experiment. Precisamos adicionar esse alerta.

## AM10
python bcllm.py --experiment adição_modelos --add-model servidor/modelo10 --structured false
Funcionou com false, true e null.

## AM11
python bcllm.py --experiment adição_modelos --add-model servidor/modelo11 --reasoning null
Ele não aceita colocar comandos com valor null, para forçar o padrão de sistema, que no caso de configurações de modelos, a maioria serve para não enviar a informação na requisição. A unica excessão é o comando --url, que ao setar para null cai para a URL do .env. Já que esse é sempre obrigatório ter.
O maior complicador disso é que, a gente mandou ele configurar muito dos valores como int ou float, se não me engano. Ao ter que aceitar "null", isso não causa problemas?
- Comandos que NÃO aceitam "null" e deveriam:
    - --url
    - --reasoning_tokens
    - --max-tokens
    - --reasoning
    - --repeat-penalty
    - --temperature
    - --top-p
    - --top-k

## AM12
python bcllm.py --experiment adição_modelos --add-model servidor/modelo11 --reasoning HIGH  
Esse comando não aceita se colocar o valor em maiusculo, e acredito que se testar 1 a 1, todos os comandos que aceitam texto é capaz de recusarem se não for tudo em minusculo, o que é uma falha. O erro que recebi foi o seguinte: "bcllm_model.py: error: argument --reasoning: invalid choice: 'HIGH' (choose from none, minimal, low, medium, high, xhigh)"
---


Alguns erros para corrigir:

Eu coloquei valores em todos os campos do .env para ver quais ele está puxando para o experimento, quais não, e quais que, mesmo puxando, ele ignora.

### DEFAULT_QUESTIONS=1-10
    - Completamente ignorado. Ele adicionou as 100 perguntas totais do arquivo.

### QUESTIONS_STATUS_ADD=status=valid
    - Completamente ignorado. Ele adicionou as 100 perguntas totais do arquivo.
    - Ele puxou a informação para o experiments.config_json, nesse formato: ""QUESTIONS_STATUS_ADD":"status=valid"".
    - Porém, dois problemas: Além de ser ignorada, essa configuração é igual a "DEFAULT_QUESTIONS". Ela cumpre sua função ao criar o experimento, ou seja, filtrar as perguntas, e após isso não precisa ser salvo.

### QUESTIONS_STATUS_EXCLUDE=has_image=true
    - Completamente ignorado. Ele adicionou as 100 perguntas totais do arquivo.
    - Ele puxou a informação para o experiments.config_json, nesse formato: ""QUESTIONS_STATUS_EXCLUDE":"has_image=true"".
    - Porém, dois problemas: Além de ser ignorada, essa configuração é igual a "DEFAULT_QUESTIONS". Ela cumpre sua função ao criar o experimento, ou seja, filtrar as perguntas, e após isso não precisa ser salvo.

### MODELS_DEFAULT_FOR_EXPERIMENTS=teste/teste
    - Esse é complexo. Primeiro que ele não está lendo essa informação. Na coluna experiments.config_json, temos o seguinte valor: ""MODELS_DEFAULT_FOR_EXPERIMENTS":null"
    - De qualquer forma, esse nem deve entrar no config_json, o processo correto seria:
        - Ao criar um experimento, o sistema verifica se tem modelos nessa flag do .env.
        - Se houve, ele adiciona os modelos ao experimento, com as configurações especificadas e pronto. O comando foi resolvido e não precisa salvar o valor.
    - Porém, acho que isso é de um grau de complexidade para esse momento que eu estou pensando em eliminar esse comando, e nesse momento só aceitar adição 1 a 1 posterior no experimento. Até porque ainda temos que ver se o próprio --add-models vai funcionar direito.

---

# Testes de criação de experimento com foco no NULL:

## TESTE_CE_NULL1
python bcllm.py --create-experiment teste_cenull01 --add-questions null
Não funcionou.
Para piorar o resultado foi o seguinte:
"""
python bcllm.py --create-experiment teste_cenull01 --add-questions null
✓ Experiment 'cenull01' created (ID: exp_30f27137)
Error: Invalid question specification: Invalid question spec format: null
Valid formats:
  --questions "1, 3, 5"    (comma-separated, quote if spaces)
  --questions "1-10"       (range)
  --questions "1, 3-5, Q10" (mixed)
"""
Ou seja, ele não aceita o null, retorna erro, MAS cria o experimento. Quando o correto é: Se não reconhece o comando, cancela tudo. Mas teria que reconhecer null e adicionar todas as perguntas disponíveis.

## TESTE_CE_NULL2
python bcllm.py --create-experiment teste_cenull02 --questions 1,3
O comando usando "--add-questions 1,3" funciona perfeitamente, porém ai usar o comando "--questions 1,3", ele ignora. E adiciona todas as perguntas ou basedo na config do .env. Ou seja, ele não está aceitando o comando --questions como um alias do --add-questions, mas também não aponta como erro, ele simplesmente ignora. O que é o pior dos cenários.

## TESTE_CE_NULL3
python bcllm.py --create-experiment teste_cenull03 --add-questions 1,5-20

## TESTE_CE_NULL4
python bcllm.py --create-experiment teste_cenull04 --add-questions 1-50 --where status=valid

## TESTE_CE_NULL5
python bcllm.py --create-experiment teste_cenull05 --seed 55

## TESTE_CE_NULL5.2
python bcllm.py --create-experiment teste_cenull05.2 --seed 57 --seed auto

## TESTE_CE_NULL6
python bcllm.py --create-experiment teste_cenull06 --reasoning none

## TESTE_CE_NULL7
python bcllm.py --create-experiment teste_cenull07 --reasoning xhigh

## TESTE_CE_NULL8
python bcllm.py --create-experiment teste_cenull08 --max-tokens 3333

## TESTE_CE_NULL9
python bcllm.py --create-experiment teste_cenull09 --reasoning-tokens 4444

## TESTE_CE_NULL10
python bcllm.py --create-experiment teste_cenull10 --temperature 2

## TESTE_CE_NULL11
python bcllm.py --create-experiment teste_cenull11 --top-p 1.1 --top-k 30

## TESTE_CE_NULL12
python bcllm.py --create-experiment teste_cenull12 --repeat-penalty 4

## TESTE_CE_NULL13
python bcllm.py --create-experiment teste_cenull13 --vision true

## TESTE_CE_NULL14
python bcllm.py --create-experiment teste_cenull14 --vision false

## TESTE_CE_NULL15
python bcllm.py --create-experiment teste_cenull15 --structured true

## TESTE_CE_NULL16
python bcllm.py --create-experiment teste_cenull16 --url 192.198.0.1:8000

## TESTE_CE_NULL17
python bcllm.py --create-experiment teste_cenull17 --system-prompt "system teste"

## TESTE_CE_NULL18
python bcllm.py --create-experiment teste_cenull18 --user-prompt "user teste"

## TESTE_CE_NULL19
python bcllm.py --create-experiment teste_cenull19 --user-prompt null

## TESTE_CE_NULL20
python bcllm.py --create-experiment teste_cenull20 --system-prompt "system prompt personalizado" --user-prompt "user próprio" --repeat-penalty 2 --reasoning minimal

---








# Organizar para gerar experimentos:

python bcllm.py --experiment teste1 --add-model openai/gpt-5-mini --reasoning-effort minimal --enable-vision

python bcllm.py --experiment teste1 --run

python bcllm.py --experiment teste1 --create-run --iterations 1

python bcllm.py --experiment teste1 --remove-model ?

python bcllm.py --experiment teste1 --add-model openai/gpt-5-mini --reasoning-effort low --enable-vision 

python bcllm.py --experiment teste1 --add-model google/gemini-2.5-flash-lite --reasoning-effort none --enable-vision

python bcllm.py --experiment teste1 --add-model google/gemini-3.1-flash-lite-preview --reasoning-effort none --enable-vision

python bcllm.py --create-experiment teste1 --questions Q001-Q004 

python bcllm.py --experiment teste1 --run

python bcllm.py --experiment teste1 --create-run --iterations 1 

---

python bcllm.py --experiment teste1 --questions Q001-Q004

python bcllm.py --create-experiment teste1 --questions Q001-Q004

python bcllm.py --experiment teste1 --add-model google/gemini-3.1-flash-lite-preview --reasoning-effort none --enable-vision

python bcllm.py --experiment teste1 --add-model google/gemini-2.5-flash-lite --reasoning-effort low --enable-vision

python bcllm.py --experiment teste1 --add-model openai/gpt-5-mini --reasoning-effort low --enable-vision

python bcllm.py --experiment teste1 --remove-model ?


Reasoning desligado = gemini-3.1-flash-lite-preview
Reasoning low = gemini-3.1-flash-lite-preview (low)
Reasoning xhigh = gemini-3.1-flash-lite-preview (xhigh)

