# name: "comandos-simples.md"
# version: 2.0
# Atenção!: nunca fazer alterações

---

# Experimento:

bcllm --create-experiment <nome>

bcllm --create-experiment <nome> (Cria experimento com o nome indicado / O <nome> é o único campo obrigatório se o .env tiver configuração)

    --add-questions <valor>
        **FORMATO OBRIGATÓRIO**: Use aspas para argumentos com espaços
        
        --questions "1, 3, 5" (Adiciona perguntas 1, 3 e 5 - com espaços, requer aspas)
        --questions "1, 5-20" (Adiciona pergunta 1 e da 5 até a 20)
        --questions "1-50" --where status=valid (Adiciona perguntas da 1 até a 50 onde "status" for "valid")
        --questions "1-100" --exclude status=annulled (Adiciona todas exceto onde status="annulled")
        
        Formatos suportados:
        - Individual: "1" ou "Q001"
        - Vírgula: "1, 3, 5" ou "Q001,Q003,Q005"
        - Range: "1-10" ou "Q001-Q010"
        - Misto: "1, 3-5, Q010"
        
        **IMPORTANTE**: Argumentos com espaços DEVEM ser quoted:
        ✓ CORRETO: --questions "1, 3, 5"
        ✓ CORRETO: --questions 1,3,5 (sem espaços)
        ✗ ERRADO: --questions 1, 3, 5 (sem aspas com espaços - shell divide em múltiplos args)
        
    --seed <opção>
        EM BRANCO, AUTO, # (número)
    --add-model <modelo>
        --reasoning <opção>
        --max-tokens <#>
        --reasoning-tokens <#>
        --temperature <#>
        --top-p <#>
        --top-k <#>
        --repeat-penalty <#>
        --vision <opção> (true/false/NULL - case-insensitive)
        --structured <opção> (true/false/NULL - case-insensitive)
        --url <configura o base-url padrão do experimento>
    --system-prompt <"Frase entre aspas para ser usada como system prompt"> (Se não especificado, usa o do .env como padrão)
    --user-prompt <"Frase entre aspas para ser usada como user prompt"> (Se não especificado, usa o do .env como padrão)
    --retry-policy <#> (Configuração não vai mais existir. Configuração de retry-policy agora será apenas por .env)

bcllm --experiment <nome> (Visualiza as especificações do experimento indicado)

    --add-questions <valor> (Pode adicionar perguntas a um experimento já criado)
        **FORMATO OBRIGATÓRIO**: Use aspas para argumentos com espaços
        
        --questions "1, 3, 5" (Adiciona perguntas 1, 3 e 5)
        --questions "1, 5-20" (Adiciona pergunta 1 e da 5 até a 20)
        --questions "1-50" --where status=valid
        --questions "1-100" --exclude status=annulled
        
    --seed <opção> (seed poderá ser adicionado ou alterado em experimento já criado, porém não afeta o seed dos runs já criados)
        EM BRANCO, AUTO, #
    --add-model <modelo> (pode ser adicionado modelos a um experimento já criado)
        --reasoning <opção> (none, minimal, low, medium, high, xhigh)
        --max-tokens <#>
        --reasoning-tokens <#>
        --temperature <#>
        --top-p <#>
        --top-k <#>
        --vision <opção> (true/false/NULL - case-insensitive)
        --base-url
    --system-prompt <"Frase entre aspas"> (system prompt poderá ser alterado em experimento já criado, porém não afeta runs já criados)
    --user-prompt <"Frase entre aspas"> (user prompt poderá ser alterado em experimento já criado)
    --retry-policy <#> (Retry policy poderá ser alterado e afeta questões não processadas)

---

# Modelos:

bcllm experiment <nome> --add-model <modelo> (Adiciona modelo indicado em um experimento já criado)
bcllm experiment <nome> --add-model <modelo> <modelo> (Adiciona todos os modelos indicados)
bcllm experiment <nome> --add-model <modelo> --reasoning none <modelo> --reasoning high (Adiciona dois modelos com configurações diferentes)

bcllm experiment <nome> --remove-model <modelo> <modelo> (remove todos os modelos indicados do experimento)
bcllm experiment <nome> --remove-model ? (Apresenta lista dos modelos para escolher quais remover)

## Configurações obrigatórias para adicionar modelo em um experimento:

    - <modelo> (Apenas o nome do modelo é obrigatório, todo o resto é opcional)

## Valores Booleanos (vision, structured):

    Formato: true, false, NULL (case-insensitive)
    
    Exemplos válidos:
    --vision true
    --vision TRUE
    --vision True
    --vision false
    --vision NULL
    --vision null

---

# RUN:

bcllm experiment <nome> --add-run

    --seed <EM BRANCO/AUTO/#> (SEED não poderá ser alterado em RUN já criado)
    --system-prompt <"Frase entre aspas"> (system prompt não poderá ser alterado em RUN já criado)
    --user-prompt <"Frase entre aspas"> (user prompt não poderá ser alterado em RUN já criado)

bcllm experiment <nome> --remove-run <run> (remove RUNs indicados do experimento)
bcllm experiment <nome> --remove-run ? (Apresenta lista dos RUNs para escolher quais remover)

---

# Execute:

bcllm experiment <nome> --execute
    --run (selecionar um run específico do experimento para rodar)
    --questions (seleciona quais perguntas serão processadas)
    --models (seleciona quais modelos serão utilizados)
    --retry-policy (definir configuração de retry para esta execução)

- Se um experimento for executado parcialmente, na próxima execução o sistema identifica itens pendentes.

## Configurações obrigatórias para execução de experimento:

    - Possuir ao menos 1 RUN configurado
    - Possuir ao menos 1 modelo adicionado
    - Possuir ao menos 1 questão salva em snapshot

---

## Informações extras:
- Reasoning enabled não deve ser enviado, pois "effort: none" provêm o mesmo efeito.
- Segundo a openrouter, Effort e max-tokens não deve ser usado simultaneamente.
- Será necessário ter a opção de --base-url por modelo.

---

# Renomear:

--reasoning-effort = --reasoning

---

# Configurações padrão do sistema:

- questions = Configuração padrão de **questions** é usada quando não informado na configuração de experimento. Utiliza todas as perguntas disponíveis.
- seed = Configuração padrão de **seed** é usada quando não informado. Desativa randomização e usa ordem original.
- system-prompt = Se não configurado, não é enviado na requisição.
- user-prompt = A decidir
- Todas as configurações de modelos, ao não serem definidas, serão ignoradas no envio da requisição, ativando a configuração padrão do servidor/modelo.

## Hierarquia de configurações:

- RUNs e Modelos com configurações não definidas, herdam as configurações do Experimento.
    └── Experimentos com configurações não definidas, herdam as configurações do .env
        └── .env não configurado tem valores definidos por padrões de sistema.

- Ao criar um Experimento, todas as configurações são salvas no experimento e não mudam por alteração no .env.

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
| **E** | Erro | Marca como erro técnico |
| **S** | Pular | Pula para próxima |
| **Q** | Sair | Sai e salva o progresso |
| **Z** | Desfazer | Desfaz a última classificação |

### Fluxo de Revisão

1. **Leia a resposta da LLM** - A resposta completa é mostrada
2. **Identifique a alternativa** - Procure por padrões como `\boxed{C}`, "Answer: C", etc.
3. **Pressione a tecla correspondente** - A/B/C/D para classificar
4. **Avanço automático** - Após classificar, avança para próxima questão
5. **Use Z para desfazer** - Se errar, pressione Z para voltar e corrigir

### O Que Acontece Após a Revisão?

As respostas revisadas são atualizadas no banco de dados:

- **`manual-answer`** - Alternativa selecionada pelo revisor
- **`review-status`** - Mudado de `auto` para `manual`
- **`reviewed-at`** - Timestamp da revisão
- **`selected-answer`** - Atualizado com a classificação manual
- **`is-correct`** - Recalculado com base na resposta manual

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
