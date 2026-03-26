# Testes de criação de experimento:

## CE1
python bcllm.py --create-experiment ce01 --add-questions 1,3

## CE2
python bcllm.py --create-experiment ce02 --questions 1,3

## CE3
python bcllm.py --create-experiment ce03 --add-questions 1,5-20

## CE4
python bcllm.py --create-experiment ce04 --add-questions 1-50 --where status=valid

## CE5
python bcllm.py --create-experiment ce05 --seed 55

## CE5.2
python bcllm.py --create-experiment ce05.2 --seed 57 --seed auto

## CE6
python bcllm.py --create-experiment ce06 --reasoning none

## CE7
python bcllm.py --create-experiment ce07 --reasoning xhigh

## CE8
python bcllm.py --create-experiment ce08 --max_tokens 3333

## CE9
python bcllm.py --create-experiment ce09 --reasoning-tokens 4444

## CE10
python bcllm.py --create-experiment ce10 --temperature 2

## CE11
python bcllm.py --create-experiment ce11 --top_p 1.1 --top_k 1.2

## CE12
python bcllm.py --create-experiment ce12 --repeat_penalty 2

## CE13
python bcllm.py --create-experiment ce13 --vision true

## CE14
python bcllm.py --create-experiment ce14 --vision false

## CE15
python bcllm.py --create-experiment ce15 --structured true

## CE16
python bcllm.py --create-experiment ce16 --url 192.198.0.1:8000

## CE17
python bcllm.py --create-experiment ce17 --system_prompt system teste

## CE18
python bcllm.py --create-experiment ce18 --user_prompt "user teste"

## CE19
python bcllm.py --create-experiment ce19 --retry_policy 3

## CE20
python bcllm.py --create-experiment ce20 --system_prompt "system prompt personalizado" --user_prompt "user próprio" --repeat_penalty 2 --reasoning minimal

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
python bcllm.py --experiment adição_modelos --add-model servidor/modelo4 --reasoning_tokens 4444 --max_tokens 5555
Esse aqui me fez perceber uma falha que acho que foi minha. O comando não funcionou, mas funcionou quando no lugar de colocar do jeito que tá, com "_" separando as palavras do comando, eu coloquei "-" separando as palavras do comando. E eu vi que alguns comandos o texto é separado por "-" e outros por "_".
E com isso eu deixo duas dúvidas: Devemos padronizar, certo? E se padronizar, qual você acha que é o mais adequado?

## AM5
python bcllm.py --experiment adição_modelos --add-model servidor/modelo5 --repeat_penalty 10 
Esse é outro comando que para funcionar eu tive que trocar "--repeat_penalty" por "--repeat-penalty". E isso me fez pensar, em comandos que o texto é como uma frase, acho que devemos usar "_". Como no caso de "repeat_penalty", porém, eu comandos que o texto é mais a ideia de dois comandos combinados, como no caso de "--add-model", ai sim usamos o "-". O que você acha?
No caso desse comando eu percebi uma outra questão. O config_json está com todas as configurações, porém, a coluna "variant_signature" não tem todos os valores.
Como pode observar aqui, além daquela questos dos zeros, ele não tem por exemplo "repeat penalty". "modelo5|reasoning=low|vision=true|structured=false|temp=2.000|top_p=1.500|top_k=40.000|max_tokens=16384.000|reasoning_tokens=1111.000"
E fica a dúvida. variant_signature deve ter todos os comandos? Se sim, precisamos corrigir, e se não, quais entrariam? Qual a lógica?
Atualmente isso gera um problema grave, porque ele usa o variant_signature para distinguir modelos, então, se eu tentar criar dois modelos que tudo seja igual, com diferença apenas em uma flag que não entra no variant_signature, ele considera que o valor já existe. Por exemplo, se criar dois modelos que a única diferença seja "repeat-penalty", eu não posso criar o segundo por ele diz que já existe, por não ter o valor que distinguiria ele no campo.

## AM6
python bcllm.py --experiment adição_modelos --add-model servidor/modelo6 --temperature 2
Funciona

## AM7
python bcllm.py --experiment adição_modelos --add-model servidor/modelo7 --top_k 2 --top_p 3
Funciona, mas novamente, só se colocar "top-k" e "top-p", ou seja, separado por "-".

## AM8
python bcllm.py --experiment adição_modelos --add-model servidor/modelo8 --vision true
Funciona, tanto com true, quanto com false, e curiosamente, esse é o único que achei até agora que recebe também "null".

## AM9
python bcllm.py --experiment adição_modelos --add-model servidor/modelo9 --vision true --vision false
Quando existe o mesmo comando duas vezes ele tem aquele comportamento que mantem o ultimo, porém, aqui ele não esta dando o alerta de comando duplicado que colocamos no --create-experiment.

## AM10
python bcllm.py --experiment adição_modelos --add-model servidor/modelo10 --structured false
Esse também funcionou com false, true e null.

## AM11
python bcllm.py --experiment adição_modelos --add-model servidor/modelo11 --reasoning null
Ele não aceita colocar comandos com valor null, para forçar o padrão de sistema, que no caso de configurações de modelos, a maioria serve para não enviar a informação na requisição. A unica excessão é o comando --url, que ao setar para null cai para a URL do .env. Já que esse é sempre obrigatório ter.
O maior complicador disso é que, a gente mandou ele configurar muito dos valores como int ou float, se não me engano. Ao ter que aceitar "null", isso não causa problemas?
- Comandos que NÃO aceitam "null":
    - --URL
    - --reasoning_tokens
    - --max-tokens
    - --reasoning
    - --repeat-penalty
    - --temperature
    - --top-p
    - --top-k

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