# name: "comandos-simples.md"
# version: 2.0
# Atenção!: nunca fazer alterações

---

# Experimento:

bcllm --create-experiment <nome>

bcllm --create-experiment <nome> (Cria experimento com o nome indicado / O <nome> é o único campo obrigatório se o .env tiver configuração)

    --add-questions <valor / system-default> (system-default = Gerar snapshots de todas as questões disponíveis)
        **FORMATO OBRIGATÓRIO**: Use aspas para argumentos com espaços
        --questions "1, 3, 5" (Adiciona perguntas 1, 3 e 5 - com espaços, requer aspas)
        --questions "1, 5-20" (Adiciona pergunta 1 e da 5 até a 20)
        --questions "1-50" --where status=valid (Adiciona perguntas da 1 até a 50 onde a flag "status" for "valid")
        --questions "1-100" --exclude status=annulled (Adiciona todas exceto onde status="annulled")
        --questions 1-10 --where status=valid has_image=false (Adiciona perguntas de 1 até a 10 em que a flag "status" seja "valid" e a flag "has_image" seja "false")
        --where e --exclude <system-default> = Desativa filtragem configurada no .env.
        
        Formatos suportados:
        - Individual: "1"
        - Vírgula: "1, 3, 5"
        - Range: "1-10"
        - Misto: "1, 3-5"
        
        **IMPORTANTE**: Argumentos com espaços DEVEM ser quoted:
        ✓ CORRETO: --questions "1, 3, 5"
        ✓ CORRETO: --questions 1,3,5 (sem espaços)
        ✗ ERRADO: --questions 1, 3, 5 (sem aspas com espaços - shell divide em múltiplos args)
        
    --seed <AUTO / # / system-default> - (o seed de um experimento já criado poderá ser alterado, porém não afeta o seed de runs já criados) - ('system-default' = randomização de respostas desativadas, será utilizada a ordem original apresentada no dataset)
    --add-model <modelo> (´--add-questions´ e ´--questions´ são alias, e funcionam da mesma forma.)
        --reasoning <none, minimal, low, medium, high, xhigh / system-default> - (system-default = não enviar na requisição)
        --max-tokens <# / system-default>
        --reasoning-tokens <# / system-default>
        --temperature <# / system-default>
        --top-p <# / system-default>
        --top-k <# / system-default>
        --repeat-penalty <# / system-default>
        --vision <opção> (true / false / system-default)
        --structured <opção> (true / false / system-default)
        --url <base-url padrão do experimento>
    --system-prompt <"Frase entre aspas para ser usada como system prompt" / system-default> (Se não especificado, usa o do .env como padrão / system-default = não enviar na requisição)
    --user-prompt <"Frase entre aspas para ser usada como user prompt" / system-default> (Se não especificado, usa o do .env como padrão / system-default = não enviar na requisição)
    --retry-policy <#> (Configuração não vai mais existir. Configuração de retry-policy agora será apenas por .env)
    --url <base-url padrão do experimento>

    QUASE todos os comandos suportam "system-default", dessa forma são tradados como o padrão de sistema.
    **comandos estruturais não suportam:**
    --create-experiment (Não suporta system-default)
    --url (Não suporta system-default)
    --data-set (Não suporta system-default)
    --add-model (Não suporta system-default)
    --remove-model (Não suporta system-default)
    --add-run (Não suporta system-default)
    --remove-run (Não suporta system-default)
    --execute (Não suporta system-default)

    Todos as flags de modelos (exceto --url), ao receberem "system-default", são tradados como o padrão de sistema. Que nesse caso significa que a configuração não será enviada na requisição a API.

bcllm --experiment <nome> (Visualiza as especificações do experimento indicado)

    --add-questions <valor / system-default> (Pode adicionar perguntas a um experimento já criado - 'system-default' = Gerar snapshots de todas as questões disponíveis)
        **FORMATO OBRIGATÓRIO**: Use aspas para argumentos com espaços

        --questions "1, 3, 5" (Adiciona perguntas 1, 3 e 5)
        --questions "1, 5-20" (Adiciona pergunta 1 e da 5 até a 20)
        --questions "1-50" --where status=valid
        --questions "1-100" --exclude status=annulled

    --seed <AUTO / # / system-default> - (o seed de um experimento já criado poderá ser alterado, porém não afeta o seed de runs já criados) - ('system-default' = randomização de respostas desativadas, será utilizada a ordem original apresentada no dataset)
    --add-model <modelo> (pode ser adicionado modelos a um experimento já criado)
        --reasoning <none, minimal, low, medium, high, xhigh / system-default> - (system-default = não enviar na requisição)
        --max-tokens <# / system-default>
        --reasoning-tokens <# / system-default>
        --temperature <# / system-default>
        --top-p <# / system-default>
        --top-k <# / system-default>
        --repeat-penalty <# / system-default>
        --vision <opção> (true / false / system-default)
        --structured <opção> (true / false / system-default)
        --url <base-url padrão do experimento>
    --system-prompt <"Frase entre aspas" / system-default> (system prompt poderá ser alterado em experimento já criado, porém não afeta runs já criados)
    --user-prompt <"Frase entre aspas" / system-default> (user prompt poderá ser alterado em experimento já criado)
    --review (inícia o processo de revisão das perguntas)
    Todos os campos suportam "system-default" (exceto --url e --dataset-path), dessa forma o seu comportamento será o padrão de sistema.

---

# Modelos:

bcllm --experiment <nome> --add-model <modelo> # (adiciona modelo indicado em um experimento já criado)
bcllm --experiment <nome> --add-model <modelo> --reasoning none # (adiciona em um experimento já criado um modelo com pensamento desligado)
bcllm --experiment <nome> --add-model <modelo> --reasoning high # (adiciona em um experimento já criado um modelo com pensamento em effort high)

bcllm --experiment <nome> --remove-model <ID> (remove o modelo indicado do experimento especificado, usando o ID)
bcllm --experiment <nome> --remove-model ? (Apresenta uma lista dos modelos do experimento, com um número ao lado, para o usuário escolher quais dos modelos quer remover. Podendo escolher 1 ou mais)

## Configurações obrigatórias para adicionar modelo em um experimento:

    - <modelo> (Apenas o nome de um modelo é obrigatório, todo o resto é opcional)

## Valores Booleanos (vision, structured):

    Formato: true, false, system-default (case-insensitive)

    Exemplos válidos:
    --vision true
    --vision TRUE
    --vision True
    --vision false
    --vision system-default
    --vision system-default

---

# RUN:

bcllm --experiment <nome> --add-run

    --seed <AUTO / # / system-default> (SEED não poderá ser alterado em RUN já criado) ('system-default' = randomização de respostas desativadas, será utilizada a ordem original apresentada no dataset)
    --system-prompt <"Frase entre aspas para ser usada como system prompt" / system-default> (Se não especificado, usa a configuração registrada no 'experiment.config_json' como padrão / system-default = não enviar na requisição) (system prompt não poderá ser alterado em RUN já criado)
    --user-prompt <"Frase entre aspas para ser usada como user prompt" / system-default> (Se não especificado, usa a configuração registrada no 'experiment.config_json' como padrão / system-default = não enviar na requisição) (user prompt não poderá ser alterado em RUN já criado)

bcllm --experiment <nome> --remove-run <run> (remove RUNs indicados do experimento)
bcllm --experiment <nome> --remove-run ? (Apresenta uma lista dos RUNs do experimento, com um número ao lado, para o usuário escolher quais dos RUNs quer remover. Podendo escolher 1 ou mais. Dados já gerados não serão apagados do banco de dados)

---

# Execute:

bcllm --experiment <nome> --execute
    --run (selecionar um run especifico do experimento para rodar, se não especificado, roda todos)
    --questions (seleciona quais perguntas serão processadas, se não especificado, seleciona todas do experimento, se especificado, roda rodas as perguntas selecionadas de todos os runs selecionados)
    --model (seleciona quais modelos serão utilizados, só podendo escolher entre os modelos que já estejam no experimento)

**Atenção:** Filtros de execução não alteram o estado do experimento ou do run. Eles apenas limitam o escopo da execução atual.
Se nenhum filtro de execução for adicionado, serão processadas todas as requisições que ainda não tiverem sido executadas.

- Se um experimento for executado parcialmente, pelo usuário ter selecionado Run, questions ou model parciais, na próxima execução, o sistema deve ter inteligência para saber, entre a seleção, se existe algo que falta ser processado. Se não houver, um aviso será apresentado com a informação, se houver, apenas os itens não processados serão requisitados.

## Configurações obrigatórias para execução de experimento:

    - Possuir ao menos 1 RUN configurado
    - Possuir ao menos 1 modelo adicionado
    - Possuir ao menos 1 questão salva em snapshot

---

## Informações extras:
- Reasoning enabled não deve ser enviado, pois "effort: none" provêm o mesmo efeito.
- Segundo a openrouter, Effort e max-tokens não deve ser usado simultaneamente. Não aplicar nenhum código em relação a isso, apenas um aviso no .env.
- Será necessário ter a opção de --url por modelo, já que em um mesmo experimento eu vou precisar rodar, tanto modelos do openrouter, quanto local.

---

# Renomear:

--reasoning-effort = --reasoning

---

# Configurações padrão do sistema (system-default):

- questions = Configuração padrão de **questions** é usada quando não informado na configuração de experimento e no campo QUESTIONS_DATASET_PATH do .env.
    - Comportamento: Utiliza todas as perguntas disponíveis.
- where e exclude = Configuração padrão são usadas quando não informado na configuração de experimento e nos campos QUESTIONS_STATUS_ADD e QUESTIONS_STATUS_EXCLUDE do .env.
    - Comportamento: Não filtra nenhuma pergunta.
- seed = Configuração padrão de **seed** é usada quando não informado na configuração de experimento, de run, e em branco no campo RUN_RESPONSES_SEED do.env.
    - Comportamento: Desativa randomização e usa a ordem original das respostas.
- system-prompt = Configuração padrão de **system-prompt** é usada quando não informado na configuração de experimento, RUN e no campo SYSTEM_PROMPT do .env.
    - Comportamento: Ao não ser configurado o comportamento padrão é "não enviar esse comando na requisição.
- user-prompt = Configuração padrão de **user-prompt** é usada quando não informado na configuração de experimento, RUN e no campo USER_PROMPT do .env.
    - Comportamento: Ao não ser configurado o comportamento padrão é "não enviar esse comando na requisição.
- Todas as configurações de modelos, ao não serem definidas, serão ignoradas no envio da requisição, ativando a configuração padrão do servidor/modelo. O mesmo ocorre ao serem setadas como "system-default"
- A configuração padrão pode ser forçada pelo usuário ao preencher o comando com "system-default" Ex: --reasoning system-default

- dataset-path e url não podem receber "system-default", pois são comandos que precisam ser informados no .env ou na criação do experimento para o sistema funcionar.
- --add-model recebendo "system-default" na criação do experimento não adiciona nenhum modelo (comportamento padrão).

---

## Lista completa de comandos:

bcllm --create-experiment <name>
        ├──> --seed
        ├──> --system-prompt
        ├──> --user-prompt
        ├──> --url
        ├──> --data-set
        ├──> --add-questions
        │      ├──> --where
        │      └──> --exclude
        └──> --add-model
               ├──> --reasoning
               ├──> --max-tokens
               ├──> --reasoning-tokens
               ├──> --temperature
               ├──> --top-p
               ├──> --top-k
               ├──> --repeat-penalty
               ├──> --vision
               ├──> --structured
               └──> --url

bcllm --experiment <name>
        ├──> --seed
        ├──> --system-prompt
        ├──> --user-prompt
        ├──> --url
        ├──> --data-set
        ├──> --add-questions
        │      ├──> --where
        │      └──> --exclude
        ├──> --add-model
        │      ├──> --reasoning
        │      ├──> --max-tokens
        │      ├──> --reasoning-tokens
        │      ├──> --temperature
        │      ├──> --top-p
        │      ├──> --top-k
        │      ├──> --repeat-penalty
        │      ├──> --vision
        │      ├──> --structured
        │      └──> --url
        ├──> --remove-model
        ├──> --add-run
        │      ├──> --seed
        │      ├──> --system-prompt
        │      └──> --user-prompt
        ├──> --remove-run
        ├──> --execute
        │      ├──> --run
        │      ├──> --questions
        │      └──> --model
        └──> --review

---

## Hierarquia de configurações:

- RUNs e Modelos com configurações não definidas, herdam as configurações do Experimento.
    └── Experimentos com configurações não definidas, herdam as configurações do .env
        └── .env não configurado tem valores definido por padrões de sistema, que poder ser um valor fixo ou simplesmente ignorar a configuração na requisição.

- Ao criar um Experimento, todas as configurações são salvas no experimento e não mudam por alteração no .env.

---

# Revisão Manual:

Inicia revisão de todas as respostas pendentes de revisão de um experimento

bcllm --experiment <nome> --review

### Interface de Revisão

A interface mostra:

```
================================================================================
REVIEW MANUAL DE RESPOSTAS  |  Item 1/23
================================================================================
Pendentes: 23  |  Processadas: 0
Pergunta: 1 (Iteração 1, Modelo: liquid/lfm-2.5-1.2b-thinking)
Resposta Correta: "A"
Status: AMBIGUOUS
================================================================================

ENUNCIADO:
--------------------------------------------------------------------------------
Homem de 45 anos foi encontrado inconsciente por familiares junto a uma escada...

ALTERNATIVAS:
--------------------------------------------------------------------------------
  A) tomografia de crânio, face e coluna cervical; radiografia de membros...
  B) radiografia de crânio e face; radiografia de membros; internar...
  C) radiografia de crânio, coluna cervical e membros em duas posições...
  D) tomografia de crânio, face e radiografia de membros; liberar...

RESPOSTA DA LLM:
--------------------------------------------------------------------------------
Okay, let me tackle this question. So the scenario is a 45-year-old man...
ANSWER: \boxed{C}

================================================================================
CLASSIFICAÇÃO:
--------------------------------------------------------------------------------
  [A]  [B]  [C]  [D]  [N]enhuma  [E]rro não detectado

  [S] Pular  |  [Q] Sair e salvar  |  [Z] Desfazer última
================================================================================
```

### Atalhos de Teclado

| Tecla | Ação | Descrição |
|-------|------|-----------|
| **A/B/C/D** | Classificar | Seleciona a alternativa correta |
| **N** | Nenhuma | Marca como "sem resposta clara" |
| **E** | Erro | Marca como erro técnico (não foi possível revisar) |
| **S** | Pular | Pula para próxima (pode revisar depois) |
| **Q** | Sair | Sai e salva o progresso |
| **Z** | Desfazer | Desfaz a última classificação |

### Fluxo de Revisão

1. **Leia a resposta da LLM** - A resposta completa é mostrada (truncada se muito longa)
2. **Identifique a alternativa** - Procure por padrões como `\boxed{C}`, "Answer: C", etc.
3. **Pressione a tecla correspondente** - A/B/C/D para classificar
4. **Avanço automático** - Após classificar, avança para próxima questão
5. **Use Z para desfazer** - Se errar, pressione Z para voltar e corrigir

### O Que Acontece Após a Revisão?

As respostas revisadas são atualizadas no banco de dados:

- **`manual_answer`** - Alternativa selecionada pelo revisor
- **`review_status`** - Mudado de `auto` para `manual`
- **`reviewed_at`** - Timestamp da revisão
- **`selected_answer`** - Atualizado com a classificação manual
- **`is_correct`** - Recalculado com base na resposta manual

### Estatísticas de Revisão

Durante a revisão, o sistema mostra:

```
Pendentes: 23  |  Processadas: 10
```

Ao final:

```
Revisão concluída! 10 itens processados.
```

### Atenção

- Revisão não altera o resultado original.
- Revisão anota correções.
- O dado bruto permanece auditável.

### Dicas de Revisão

1. **Respostas longas** - Role para baixo se necessário (a resposta é truncada após 800 caracteres)
2. **Padrões comuns** - Procure por:
   - `\boxed{A}`, `\boxed{B}`, etc.
   - "Answer: A", "The answer is B"
   - "Letra C", "Alternativa D"
3. **Raciocínio vs Resposta** - Alguns modelos fazem raciocínio longo antes de dar a resposta final
4. **Use o contexto** - A pergunta e alternativas ajudam a identificar a resposta correta

---
