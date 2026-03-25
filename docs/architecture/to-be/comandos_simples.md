# name: "comandos_simples.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

# Experimento:

bcllm --create-experiment <nome> 

bcllm --create-experiment <nome> (Cria experimento com o nome indicado / O <nome> é o único campo obrigatório se o .env tiver configuração de)

    --add-questions <valor>
        --questions 1, 5, 10 (Adiciona perguntas 1, 5 e 10)
        --questions 1, 5-20 (Adiciona perguntas 1, e da 5 até a 20)
        --questions 1-50 --where status=valid (Adiciona perguntas da 1 até a 50 em que a flag "status" seja valor "valid")
        --questions --exclude status=annulled (Adiciona todas as perguntas em que a flag "status" não seja "annulled")
        --questions 1-10 --where status=valid has_image=false (Adiciona perguntas de 1 até a 10 em que a flag "status" seja "valid" e a flag "has_image" seja "false")
    --seed <opção>
        EM BRANCO,AUTO,#
    --add-model <modelo>
        --reasoning <opção>
        --max_tokens <#>
        --reasoning-tokens <#>
        --temperature <#>
        --top_p <#>
        --top_k <#>
        --repeat_penalty <#>
        --vision <opção> (true/false)
        --structured <opção> (true/false)
        --url <configura o base_url padrão do experimento, se não configurado, puxa do .env, se não tiver no .env, apresenta um alerta e explica a situação e como corrigir>
    --system_prompt <"Frase entre aspas para ser usada como system prompt"> (Se não especificado, usa o do .env como padrão. Se não tiver no .env, não envia a informação na requisição)
    --user_prompt <"Frase entre aspas para ser usada como user prompt"> (Se não especificado, usa o do .env como padrão. Se não tiver no .env, retorna um aviso de que deve ser corrigido (Ou será que pode enviar sem?))
    --retry_policy <#> (Configuração não vai mais existir. Configuração de retry_policy agora será apenas por .env. Será uma configuração de sistema, e não mais de experimento)

bcllm --experiment <nome> (Visualiza as especificações do experimento indicado)

    --add-questions <valor> (Pode ser adicionado perguntas a um experimento já criado, com perguntas ou sem)
        --questions 1 5 10 (Adiciona perguntas 1, 5 e 10)
        --questions 1 5-20 (Adiciona perguntas 1, e da 5 até a 20)
        --questions 1-50 --where status=valid (Adiciona perguntas da 1 até a 50 em que a flag "status" seja valor "valid")
        --questions --exclude status=annulled (Adiciona todas as perguntas em que a flag "status" não seja "annulled")
        --questions 1-10 --where status=valid has_image=false (Adiciona perguntas de 1 até a 10 em que a flag "status" seja "valid" e a flag "has_image" seja "false")
    --seed <opção> (seed poderá ser adicionado ou alterado em experimento já criado, porém, não afeta o seed dos runs já criados)
        <EM BRANCO,AUTO,#>
    --add-model <modelo> (pode ser adicionado modelos a um experimento já criado)
        --reasoning <opção> (none, minimal, low, medium, high, xhigh)
        --max-tokens <#>
        --reasoning-tokens <#>
        --temperature <#>
        --top_p <#>
        --top_k <#>
        --vision <opção> (true/false)
        --base_url
    --system_prompt <"Frase entre aspas para ser usada como system prompt"> (system prompt poderá ser alterado em experimento já criado, porém, não afeta o system prompt dos runs já criados)
    --user_prompt <"Frase entre aspas para ser usada como user prompt"> (user prompt poderá ser alterado em experimento já criado, porém, não afeta o system prompt dos runs já criados)
    --retry_policy <#> (Retry policy poderá ser alterado em experimento já criado, e afeta todas as questões que não foram processadas)

---

# Modelos:

bcllm experiment <nome> --add-model <modelo> (Adiciona modelo indicado em um experimento já criado)
bcllm experiment <nome> --add-model <modelo> <modelo> (Adiciona todos os modelos indicados em um experimento já criado)
bcllm experiment <nome> --add-model <modelo> --reasoning none <modelo> --reasoning high (Adiciona em um experimento já criado, dois modelos, o primeiro com pensamento desligado e o segundo com pensamento em effort high)


bcllm experiment <nome> --remove-model <modelo> <modelo> (remove todos os modelos indicados do experimento especificado, podendo usar nome ou ID)
bcllm experiment <nome> --remove-model ? (Apresenta uma lista dos modelos do experimento, com um número ao lado, para o usuário escolher quais dos modelos quer remover. Podendo escolher 1 ou mais)

## Configurações obrigatórias para adicionar modelo em um experimento:
    
    - <modelo> (Apenas o nome de um modelo é obrigatório, todo o resto é opcional)

---

# RUN:

bcllm experiment <nome> --add-run

    --seed <EM BRANCO/AUTO/#> (SEED não poderá ser alterado em RUN já criado)
    --system_prompt <"Frase entre aspas para ser usada como system prompt"> (system prompt não poderá ser alterado em RUN já criado)
    --user_prompt <"Frase entre aspas para ser usada como user prompt"> (user prompt não poderá ser alterado em RUN já criado)

bcllm experiment <nome> --remove-run <run> (remove todos os RUNs indicados do experimento especificado, porém aqui eu não sei se usa ID ou outro valor)
bcllm experiment <nome> --remove-run ? (Apresenta uma lista dos RUNs do experimento, com um número ao lado, para o usuário escolher quais dos RUNs quer remover. Podendo escolher 1 ou mais. Dados já gerados não serão apagados do banco de dados)

---

# Execute:

bcllm experiment <nome> --execute
    --run (selecionar um run especifico do experimento para rodar, se não especificado, roda todos)
    --questions (seleciona quais perguntas serão processadas, se não especificado, seleciona todas do experimento, se especificado, roda rodas as perguntas selecionadas de todos os runs selecionados)
    --models (seleciona quais modelos serão utilizados, só podendo escolher entre os modelos que já estejam no experimento)
    --retry_policy (definir configuração de retry para essa execução, independente do valor configurado no projeto)

- Se um experimento for executado parcialmente, selecionado Run, questions ou models parciais, na próxima execução, o sistema deve ter inteligência para saber, entre a seleção, se existe algo que falta ser processado. Se não houver, um aviso será apresentado com a informação, se houver, apenas os itens não processados serão requisitados.

## Configurações obrigatórias para execução de experimento:

    - Possuir ao menos 1 RUN configurado
    - Possuir ao menos 1 modelo adicionado
    - Possuir ao menos 1 questão salva em snapshot

---

## Informações extras:
- Reasoning enabled não deve ser enviado, pois "effort: none" provêm o mesmo efeito.
- Segundo a openrouter, Effort e max_tokens não deve ser usado simultaneamente. Não aplicar nenhum código em relação a isso, apenas um aviso no .env.
- Será necessário ter a opção de --base_url por modelo, já que em um mesmo experimento eu vou precisar rodar, tanto modelos do openrouter, quanto local.

---

# Renomear:

--reasoning-effort = --reasoning

---

# Duvidas:

- Usar o comando como "model" ou "models"? - Estou começando a achar que models faz mais sentido.
- Verificar sobre websearch
- Modelo por modelo, ou t
- Adicionar uma opção ao executar um experimento que organiza a execução das requisições por RUN(padrão), por modelo ou por question.
    - Por padrão a ordem seria: RUN mais antiga, todas as perguntas (em ordem crescente) do modelo adicionado primeiro, depois todas do próximo modelo, e assim até acabar a RUN.
    - Por modelo, processa todas as perguntas em ordem crescente de todos os runs, primeiro do modelo adicionado primeiro (o mais antigo), e só passa para o segundo modelo quando processar todas as perguntas pertencentem ao primeiro.
    - Por question, processa todas as perguntas 1 (ou de menor número), e vai em sequencia por todas as perguntas do mesmo número em ordem crescente.

---

# Regra:

- Experimento é a base.
- Modelos pertencem ao experimento.
- RUNs pertencem ao experimento.
- Seed pode pertencer ao experimento, aos RUN, ou mesmo ser desativado em todos.

---

# Configurações padrão do sistema:
Definição de qual configuração é levada em conta quando um valor não é informado no experimento, no run e no .env

- questions = Configuração padrão de **questions** é usada quando não informado na configuração de experimento, e em branco no .env. Utiliza todas as perguntas disponíveis.
- seed = Configuração padrão de **seed** é usada quando não informado na configuração de experimento e run, e em branco no .env. Desativa randomização de respostas e usa sempre a ordem original.
- system_prompt = Se não configurado em nenhum lugar, não é enviado na requisição.
- user_prompt = A decidir
- Todas as configurações de modelos, ao não serem preenchidas, serão completamente ignoradas no envio da requisição, dessa forma, ativando a configuração padrão do servidor/modelo.

## Hierarquia de configurações:

- RUNs e Modelos com configurações não definidas, herdam as configurações do Experimento.
    └── Experimentos com configurações não definidas, herdam as configurações do .env
        └── .env não configurado tem valores definido por padrões de sistema, que poder ser um valor fixo ou simplesmente ignorar a configuração na requisição.

- Ao criar um Experimento, todas as configurações são salvas no experimento, e não mudam mais por alteração no .env.

---


# Revisão Manual:
Inicia revisão de todas as respostas pendentes de revisão de um experimento

bcllm --review-experiment <nome>

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

### Dicas de Revisão

1. **Respostas longas** - Role para baixo se necessário (a resposta é truncada após 800 caracteres)
2. **Padrões comuns** - Procure por:
   - `\boxed{A}`, `\boxed{B}`, etc.
   - "Answer: A", "The answer is B"
   - "Letra C", "Alternativa D"
3. **Raciocínio vs Resposta** - Alguns modelos fazem raciocínio longo antes de dar a resposta final
4. **Use o contexto** - A pergunta e alternativas ajudam a identificar a resposta correta

---