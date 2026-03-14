# Preciso fazer um experimento.

## O que eu tenho:
- Banco de dados com 100 perguntas. (DEVEMOS supor que isso não é uma constante, podem ser 3 perguntas, 150, 500)
- Essas perguntas possuem caracteristicas distantas:
    - "stem" (Acredito que deva ser uma constante)
    - "options" No caso temos 4 opções, A, B, C e D. (Porém, acredito que isso não deva ser uma constante do sistema. Ele deve poder aceitar um número diferente de opções de respostas, e talvez nem ter as letras no banco de dados, ou nem mesmo precisar ser letra, talvez no banco de dados se coloque apenas as opções, e o sistema faz o resto, e mais futuramente, até sistema com respostas por extenso com verificação por outra LLM(Muito futuro))
    - "answer_key" Se bem que temos a letra da resposta certa, não sei ao certo como ajustas isso com o pensamento anterior.
    - "status" Essa é uma das flags mais importantes para essa questão, pois posso escolher que o estudo ignore perguntas com um status X, como no caso do questionário que tenho as de status "annulled".

## O estudo que quero fazer:
- Questionário Enamed 2025/2026
- Avaliar o resultado de umas 4 a 6 LLMs diferentes.
- Talvez em níveis de raciocinio diferentes.
- Talvez rodando cada modelo mais de uma vez, para analisar consistência. (Se possível decidindo isso após)
- Talvez até fornecendo acesso a internet para algumas, para avaliar o quanto isso altera o resultado. (Com essas não necessáriamente precisando rodar multiplos RUNs)

## Como eu acho que eu gostaria de criar isso, da forma mais fácil e racional possível (De acordo com minha cabeça)
- Primeiro acho que talvez um comando para criar um experimento.
    - No momento o comando para criar experimento já é o comando para roda-lo. Talvez seja necessário ter um comando para criar o esperimento que não necessáriamente roda ele.
    - No momento, um dos comandos que mais uso é: "python bcllm.py --experiment teste_gemini_1 --models google/gemini-3.1-flash-lite-preview --questions Q001-Q010 --verbose". Em que cria ou usa as configurações do experimento mencionado, seta o modelo, diz quais perguntas quero processar, e tem milhares de outros comandos que posso adicionar. Mas sempre vai rodar em seguida.
    - Talvez seja ideal um comando em que cria um experimento sem necessáriamente roda-lo. Algo como "python bcllm.py --creat-experiment experimento_bench --temperature 0.7 --seed AUTO". Em que, se eu colocar na linha de comando alguma configuração, ele usa da linha de comando, as que eu não colocar ele pega do .env, ou talvez um arquivo de configuração separado do .env? Não sei onde seria o ideal.

- Assim ele poderia já adicionária os modelos que tem nas configurações (.env ou outro lugar), a não ser que você já defina o modelo na linha de comando ao criar o experimento.
    - Mas se adicionar modelo por linha de comando, tem que ter como configurar cada modelo individualmente. Por exemplo: "--models google/gemini-3.1-pro --reasoning_effort high vision=true, gemini-3.1-flash --reasoning_effort low vision=false", algo assim. Mas não sei se funcionaria bem se tiver que adicionar 10 modelos. Talvez até devemos permitir assim, mas idealmente ter um lugar no .env ou outro arquivo que permita você configurar de forma simples a lista de modelos para ser puxado quando criar um experimento. No momento o .env funciona bem apenas se todos os modelos tiverem exatamente as mesmas configurações. Se você quiser configurações diferentes por modelo, não tem como.
    - Também precisamos de um comando para adicionar modelos depois. Talvez, se temos o comando "--creat-experiment", poderiamos ter o "--change_experiment"? Dai se executar o sistema com o "--change_experiment", você poderia usar o mesmo comando "--models", e todo modelo que colocar lá é adicionado a lista? Talvez também poderia servir para alterar configurações que seja permitido. Como adicionar número de runs. Você criou com apenas 1 run, mas quer fazer 3. Não sei.
    - Talvez também uma opção para deletar modelos, caso você não queira mais algum que esteja lá?

- Acho que seria também importante uma forma de visualizar as configurações. Talvez ao acionar apenas "python bcllm.py --experiment nome_experimento", se ele existir, o sistema imprimi as configurações do experimento, modelos, data de criação, perguntas selecionadas, talvez até dados do que já foi feito ou não.

- E por fim, um comando para rodar o experimento. Talvez algo como "python bcllm.py --run --experiment nome_experimento". Dessa forma seria para rodar ele completamente. Tudo que foi configurado, todos os modelos, todos os runs etc.
    - E o mesmo comando também seria usado para rodar parcialmente. Talvez algo como "python bcllm.py --run --experiment nome_experimento --o que você quiser rodar no momento" Podendo selecionar só um modelo para rodar naquele modelo, só um run dos 3 configurados, só metade das perguntas, coisas do tipo.

- Acho que seria interessante, cada modelo também ter um id simples dentro do experimento, por exemplo "model google/gemini-3.1-flash-lite-preview -reasoning-high etc. etc. etc" tem a ID "3", por ser o terceiro da lista. Então ao rodar, em vez de precisar colocar todo o nome do modelo, você colocaria apenas "--models 3", ou "--models 3,6", para rodar o ID 3 e o ID 6. E esse ID apareceria ao executar o comando para visualizar as configurações do experimento.

## Comandos atuais:
- Eu acredito que isso pode sim conviver com os comandos que temos atualmente. Mas a sensação que tenho é que os comandos atuais são bons para executar testes menores que você quer rodar instantaneamente. Mas não são bons para o planejamento de um estudo maior, que exige um tempo de maturação, pode exigir idas e vindas em ideias, e pode exigir execuções parciais.