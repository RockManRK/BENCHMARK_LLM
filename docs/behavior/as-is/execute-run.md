# Comando: --execute-run (ou --run)

## 1. Visão Geral

Este comando executa um run de benchmark pendente. Realiza as chamadas à API de LLM para obter respostas das perguntas e persiste os resultados no banco de dados.

O comando realiza as seguintes operações principais:
- Localiza o run mais recente do experimento
- Carrega variantes de modelo e perguntas do run
- Executa chamadas à API para cada combinação (modelo, pergunta, iteração)
- Persiste respostas e erros no banco de dados
- Atualiza status do run ao final

**Importante:** Este comando requer a chave de API do OpenRouter configurada, pois realiza chamadas reais à API.

## 2. Pré-condições Observadas

- O experimento deve existir (verificado pelo nome)
- Deve existir pelo menos um run para o experimento
- O run mais recente deve ter status "running"
- O run deve ter pelo menos uma variante de modelo associada
- O experimento deve ter pelo menos um snapshot de pergunta
- A chave de API do OpenRouter DEVE estar configurada
- Conexão com a internet deve estar disponível

## 3. Fluxo de Execução (Passo a Passo)

1. **Verificação do Experimento**
   - Busca o experimento pelo nome fornecido
   - Se não encontrado, interrompe com erro

2. **Localização do Run**
   - Busca todos os runs do experimento
   - Ordena por started_at DESC (mais recente primeiro)
   - Seleciona o primeiro run (mais recente)
   - Se não houver runs, interrompe com erro

3. **Carregamento das Variantes de Modelo**
   - Busca todas as variantes associadas ao run (tabela `run_models`)
   - Se models_filter especificado, filtra por IDs de modelo
   - Para cada run_model, carrega a variante completa da tabela `model_variants`

4. **Carregamento das Perguntas**
   - Busca todos os snapshots do experimento (tabela `question_snapshots`)
   - Se questions_filter especificado, filtra por IDs de pergunta
   - Para cada snapshot:
     - Parseia o JSON da pergunta
     - Reconstrói objeto Question completo
     - Associa snapshot_id ao contexto da pergunta

5. **Validação de Dados**
   - Verifica se há variantes de modelo (depois do filtro)
   - Verifica se há perguntas (depois do filtro)
   - Se nenhum dos dois, interrompe com erro

6. **Exibição do Contexto de Execução**
   - Exibe painel com informações do run:
     - Nome do experimento
     - Run ID
     - Status atual
     - Seed utilizada
     - Quantidade de modelos
     - Quantidade de perguntas

7. **Configuração do Client de API**
   - Cria instância do OpenRouterClient
   - Configura com API key e base URL das configurações
   - Cria instância do AnswerRandomizer com seed

8. **Configuração do ExecutionEngine**
   - Cria instância do ExecutionEngine
   - Injeta client de API, randomizer, settings e db_manager
   - db_manager permite persistência durante execução

9. **Execução do Benchmark**
   - Chama engine.execute() com:
     - model_variants: lista de variantes completas
     - questions: lista de perguntas com contexto (snapshot_id)
     - iterations: 1 (padrão para execução de run)
     - run_id: ID real do run (para persistência)
     - experiment_id: ID real do experimento (para persistência)
   - ExecutionEngine itera sobre todas as combinações:
     - Para cada variante de modelo
     - Para cada pergunta
     - Para cada iteração
     - Chama API do OpenRouter
     - Processa resposta
     - Persiste na tabela `responses`
     - Em caso de erro, persiste na tabela `errors`

10. **Atualização do Status do Run**
    - Agrega total de erros de todos os resultados
    - Se total_errors > 0:
      - Atualiza status do run para "failed"
    - Se total_errors = 0:
      - Atualiza status do run para "completed"

11. **Exibição do Resumo**
    - Exibe mensagem de conclusão
    - Total de iterações executadas
    - Total de erros encontrados

## 4. Decisões Implícitas (If / Else)

| Condição | Comportamento |
|----------|---------------|
| Experimento não encontrado | Interrompe com erro "Experiment 'X' not found" |
| Nenhum run encontrado | Interrompe com erro "No runs found for experiment 'X'" |
| Nenhuma variante no run | Interrompe com erro "No models configured for run" |
| Nenhuma pergunta no experimento | Interrompe com erro "No questions found" |
| models_filter especificado | Filtra variantes por IDs de modelo |
| questions_filter especificado | Filtra snapshots por IDs de pergunta |
| Erros durante execução | Continua execução, acumula erros |
| total_errors > 0 | Define status do run como "failed" |
| total_errors = 0 | Define status do run como "completed" |
| Variante não encontrada | Filtra para None e ignora |
| Snapshot JSON inválido | Pode causar erro de parsing |

## 5. Efeitos Colaterais

### Leituras no Banco de Dados
- Verifica existência do experimento pelo nome
- Busca todos os runs do experimento
- Busca variantes associadas ao run (run_models)
- Busca detalhes completos de cada variante (model_variants)
- Busca snapshots do experimento (question_snapshots)
- Busca detalhes de cada pergunta (questions)

### Escritas no Banco de Dados
- **Tabela `responses`**: N registros inseridos (um por resposta)
- **Tabela `errors`**: M registros inseridos (um por erro)
- **Tabela `runs`**: 1 registro atualizado (status)
- **Tabela `run_models`**: N registros atualizados (status)

### Entidades Criadas/Atualizadas
- N Response (respostas das chamadas de API)
- M Error (erros encontrados durante execução)
- 1 Run (status atualizado para "completed" ou "failed")
- N RunModel (status atualizado para "completed" ou "running")

### Estado do Sistema Após Execução
- Run tem status "completed" ou "failed"
- Respostas estão persistidas no banco de dados
- Erros (se houver) estão persistidos no banco de dados
- Modelos têm status atualizado em run_models
- Resultados disponíveis para análise e estatísticas

## 6. Comportamentos Implícitos Observados

### ⚠️ CRIAÇÃO DE VARIANTES DURANTE EXECUÇÃO (CRÍTICO)

**Comportamento crítico identificado:**
- Durante execução, o sistema **PODE CRIAR** novas variantes de modelo
- Isso ocorre quando a variante configurada no run NÃO é encontrada no banco
- A variante é criada com base nas **settings globais** (.env/CLI), não na configuração original do experimento

**Fluxo de criação:**
1. Carrega run_models do run
2. Para cada modelo no run:
   - Extrai model_id
   - **Reconstrói variant_config das settings globais** (não da configuração original)
   - Gera NOVO variant_id baseado nas settings atuais
   - **Se variante NÃO existir: CRIA nova variante**
   - Usa esta variante para persistir respostas

**Impacto:**
- Respostas podem ser associadas a uma variante **DIFERENTE** da configurada via --add-model
- Variantes criadas durante execução podem ter `reasoning_mode=unspecified`
- Perde-se o vínculo com a configuração original do modelo

**Exemplo do problema:**
```
--add-model google/gemini-3.1-flash-lite-preview --reasoning-effort low
  → Cria variante var-93517b5b (reasoning_mode=effort, reasoning_effort=low)

--execute-run (sem reasoning_effort nas settings)
  → Cria variante var-4fadde11 (reasoning_mode=unspecified)
  → Respostas salvas com var-4fadde11, NÃO var-93517b5b
```

### Seleção do Run Mais Recente
- Sempre executa o run MAIS RECENTE do experimento
- Ordenação: started_at DESC
- Runs antigos não são executados implicitamente
- Para executar run específico, usar --run-id

### Dualidade variant_id vs model_id
- Respostas são associadas a **BOTH** `variant_id` E `model_id`
- `variant_id`: identidade verdadeira da configuração (usada para deduplicação)
- `model_id`: referência legível ao modelo base
- **Importante:** Verificações de "perguntas respondidas" devem usar `variant_id`, não apenas `model_id`

### Critério de Verificação de Perguntas Respondidas (BUG POTENCIAL)
- Antes de executar cada pergunta, sistema verifica se já foi respondida
- **Critério observado (potencialmente incorreto):**
  - Verifica por `(run_id, question_id)`
  - **Pode NÃO estar usando** `(run_id, variant_id, question_id, iteration_number)`
- **Bug resultante:**
  - Se múltiplas variantes do mesmo modelo base existem
  - Segunda variante acha que perguntas já foram respondidas
  - **Pula execução da segunda variante**

### Tratamento de Erros de Randomização (COMPORTAMENTO NÃO ESPECIFICADO)
- Se pergunta tem `answer_key` inválido (ex: "CONTESTED", vazio):
  - Randomizador lança `ValueError: Correct answer not found in randomized options`
  - Erro é capturado e registrado como warning
  - **Resposta PODE ser persistida incompleta**
  - **Erro NÃO é registrado na tabela `errors`**
  - Execução continua para próxima pergunta
- **Comportamento não especificado:** não há regra clara para perguntas inválidas

### Iteração Fixa em 1
- Execução de run usa iterations = 1
- Diferente do fluxo direto (--models) que usa iterations configurável
- Cada combinação (modelo, pergunta) é executada uma vez

### Contexto de Snapshot para Respostas
- Respostas são associadas ao snapshot_id, não apenas question_id
- Garante rastreabilidade da versão exata da pergunta usada
- Permite que perguntas mudem sem afetar respostas antigas

### Persistência Durante Execução
- Respostas são persistidas IMEDIATAMENTE após cada chamada
- Não há buffer ou batch
- Garante que dados não sejam perdidos em caso de falha

### Acumulação de Erros
- Erros não interrompem a execução
- São acumulados e persistidos
- Execução continua para próximas combinações
- Status final reflete se houve algum erro

### Atualização de Status do Run
- Status é atualizado APENAS ao final da execução
- Não há atualização progressiva durante execução
- "completed" = zero erros
- "failed" = um ou mais erros

### Filtros Opcionais
- models_filter e questions_filter são opcionais
- Se especificados, limitam o escopo da execução
- Útil para reexecutar subconjuntos específicos
- Filtros não alteram dados persistidos, apenas escopo de execução

### Dependência de Configuração Global
- Usa settings globais para configuração de API
- temperature, max_tokens, etc. vêm das configurações
- Parâmetros de geração são globais, não por variante

### Separação entre Identidade e Execução
- Variantes definem IDENTIDADE (reasoning_mode, vision, etc.)
- Settings definem PARÂMETROS DE EXECUÇÃO (temperature, etc.)
- Mesma variante pode ser executada com parâmetros diferentes

### Validação de Integridade
- Run deve existir e estar em status executável
- Variantes devem existir e ser válidas
- Snapshots devem existir e ter JSON válido
- Foreign keys garantem integridade referencial

### Tolerância a Falhas de API
- Falhas de API são capturadas e registradas como erros
- Execução continua para próximas combinações
- Erros são persistidos com stack trace quando disponível

### Uso de Variantes Completas
- Carrega objetos completos de variantes (todos os campos)
- Não usa apenas IDs
- Permite acesso a todos os parâmetros durante execução

### Associação com Run e Experimento
- Respostas são associadas a run_id E experiment_id
- Permite consultas por run ou por experimento
- Facilita agregação e análise de resultados

### Feedback de Execução
- Exibe contexto antes de iniciar
- Exibe resumo após conclusão
- Feedback inclui quantidades e status
- Não exibe progresso detalhado durante execução (isso é feito pelo ExecutionEngine)

---