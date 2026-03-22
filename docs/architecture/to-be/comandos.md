# name: "cli.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

## Criar Experimento:
Comando inícial para criar um experimento.

### Valores Obrigatórios:
 - Apenas o nome do experimento.


### Opcionais:
 - Perguntas (--add-questions / --questions):
    - Aceitando escolher por faixa, uma a uma, grupos etc.
    - Ao não colocar esse comando, o padrão é adicionar todas as perguntas disponíveis.

 - Filtros de perguntas por flag no json

 - Configurar Seed de aleatoriedade das respostas (--seed)
    - Se configurado durante o experimento, se torna o padrão do experimento, se não configurado, o padrão é o que estiver no .env. Se não tiver no .env, o padrão é nulo, não randomizar respostas.

 - Adicionar modelos do experimento (--add-model / --model)
    - Se não adicionado durante a criação, pode ser adicionado no pós.

### Exemplos

#### Criar experimento simples:
bcllm --create-experiment <nome>
- Resultado: Cria experimento com o nome definido pelo usuário. Usa por padrão as configurações que estão no .env, e se não tiverem no .env, usa padrão de sistema.

#### Criar experimento com grupo de perguntas definido:
bcllm --create-experiment <nome> --add-questions Q001 - Q005 / bcllm --create-experiment <nome> --questions Q001 - Q005
- Resultado: Cria experimento com o nome definido pelo usuário e adiciona ao experimento snapshots da questão 1 até a 5. E serão processadas apenas elas ao rodar o experimento, a não ser que o usuário filtre um grupo menor ao rodar o experimento. O resto das configurações virão do .env, e se não tiverem, usa padrão do sistema.

#### Criar experimento com 2 modelos e seed definidos:
- bcllm --create-experiment <nome> --add-model <modelo> --reasoning-effort none --seed AUTO **********

---

## Adicionar modelos:
Comando para adicionar modelos a um experimento.
Podendo ser usado durante a criação do experimento

### Valores Obrigatórios:
 - Apenas o nome de um ou mais modelos.

### Opcionais:
 - Raciocinio (--reasoning-effort)
    - Permite escolher o nível de raciocinio do modelo.
    - Opções: none, minimal, low, medium, high, xhigh (verificar)(Precisa mesmo ter opções pré definidas?)

- Temperatura

- Visão (--enable-vision)
    - Opções: true, false
    - Permite ativar ou desativar a capacidade de analisar imagens dos modelos que permitam essa configuração.

- 

### Exemplos

#### Adicionar um modelo durante a criação de um experimento:
bcllm --create-experiment <nome> --add-model <modelo> / bcllm --create-experiment <nome> --add-model <modelo>













## Configurações padrão do sistema:
Definição de qual configuração é levada em conta quando um valor não é informado no experimento, no run e no .env

- questions = Configuração padrão de **questions** é usada quando não informado na configuração de experimento, e em branco no .env. Utiliza todas as perguntas disponíveis.
- seed = Configuração padrão de **seed** é usada quando não informado na configuração de experimento e run, e em branco no .env. Desativa randomização de respostas e usa sempre a ordem original.
- reasoning-effort = Não será enviado para a API, ativando a configuração padrão do servidor/modelo








## Configurações obrigatórias para execução de experimento:

- run (Ao menos 1 RUN adicionado ao experimento)
- model (Ao menos 1 modelo adicionado ao experimento)

