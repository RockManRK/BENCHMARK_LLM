# Testes de criação de experimento:

## TESTE_CE1
python bcllm.py --create-experiment teste_ce01 --add-questions 1,3

## TESTE_CE2
python bcllm.py --create-experiment teste_ce02 --questions 1,3

## TESTE_CE3
python bcllm.py --create-experiment teste_ce03 --add-questions 1,5-20

## TESTE_CE4
python bcllm.py --create-experiment teste_ce04 --add-questions 1-50 --where status=valid

## TESTE_CE5
python bcllm.py --create-experiment teste_ce05 --seed 55

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


## Testes completos a serem feitos:

