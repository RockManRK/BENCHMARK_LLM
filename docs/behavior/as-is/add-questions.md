# Comando: --add-questions

## 1. Visão Geral

Este comando adiciona novas perguntas a um experimento existente (evolução de experimento). Permite expandir o conjunto de perguntas de um experimento sem alterar execuções (runs) já existentes.

O comando realiza uma operação principal:
- Cria snapshots imutáveis das novas perguntas no experimento

**Princípio Fundamental:** Experimentos podem EVOLUIR, mas Runs são IMUTÁVEIS. O passado NUNCA é alterado.

**Importante:** Este comando NÃO altera runs existentes. Runs criados antes deste comando continuam usando o conjunto original de perguntas. Apenas runs criados DEPOIS deste comando usarão as novas perguntas.

## 2. Pré-condições Observadas

- O experimento deve existir (verificado pelo nome)
- O banco de dados deve estar inicializado
- Pelo menos uma pergunta deve ser especificada via --add-questions
- As perguntas devem existir no catálogo de perguntas do banco de dados
- A chave de API do OpenRouter NÃO é necessária (não há chamadas à API)

## 3. Fluxo de Execução (Passo a Passo)

1. **Verificação do Experimento**
   - Busca o experimento pelo nome fornecido
   - Se não encontrado, interrompe com erro

2. **Expansão do Filtro de Perguntas**
   - Converte ranges (ex: Q021-Q040) em IDs individuais
   - Converte listas separadas por vírgula em IDs individuais
   - Remove filtros de metadados (where) se presentes (não implementado)

3. **Contagem de Snapshots Existentes**
   - Conta quantos snapshots já existem para este experimento
   - Este valor é usado para calcular quantos snapshots novos foram criados

4. **Processamento de Cada Pergunta** (repetido para cada ID na lista)

   a. **Carregamento da Pergunta**
      - Busca a pergunta completa na tabela `questions` pelo ID
      - Se não encontrada, registra warning e pula para próxima

   b. **Construção do JSON da Pergunta**
      - Serializa todos os campos da pergunta:
        - id, stem, options, correct_answer
        - has_image, image_path, status

   c. **Criação do Snapshot (Idempotente)**
      - Chama método create_if_not_exists com:
        - experiment_id
        - question_id
        - question_json
      - Verifica se snapshot já existe para este par (experiment_id, question_id)
      - Se já existir, retorna snapshot_id existente (sem criar duplicata)
      - Se NÃO existir, cria novo snapshot na tabela `question_snapshots`

5. **Contagem Final de Snapshots**
   - Conta total de snapshots após a operação
   - Calcula quantos snapshots novos foram criados (diferença)

6. **Exibição do Resumo**
   - Exibe mensagem de sucesso com:
     - Nome do experimento
     - Quantidade de perguntas solicitadas
     - Quantidade de novos snapshots criados
     - Total de snapshots no experimento
   - Exibe nota sobre o princípio de imutabilidade:
     - Runs existentes NÃO são afetados
     - Apenas runs futuros usarão as novas perguntas

## 4. Decisões Implícitas (If / Else)

| Condição | Comportamento |
|----------|---------------|
| Experimento não encontrado | Interrompe com erro "Experiment 'X' not found" |
| Pergunta não encontrada | Registra warning e pula para próxima |
| Snapshot já existe | Reutiliza snapshot existente (não duplica) |
| Filtro de metadados presente | Ignora e registra warning (não implementado) |
| Perguntas duplicadas na entrada | Processa todas, mas snapshots previnem duplicação |
| Nenhuma pergunta válida | Completa sem erro, mas 0 snapshots criados |

## 5. Efeitos Colaterais

### Leituras no Banco de Dados
- Verifica existência do experimento pelo nome
- Conta snapshots existentes antes da operação
- Busca cada pergunta pelo ID na tabela `questions`
- Verifica existência de snapshots para cada pergunta

### Escritas no Banco de Dados
- **Tabela `question_snapshots`**: N registros inseridos (apenas perguntas novas)
- **Tabela `questions`**: Nenhuma escrita (perguntas já devem existir)

### Entidades Criadas
- N QuestionSnapshot (apenas para perguntas ainda não snapshotadas)

### Estado do Sistema Após Execução
- Experimento tem mais snapshots de perguntas disponíveis
- Snapshots existentes NÃO foram alterados
- Runs existentes NÃO foram alterados
- Runs futuros usarão o conjunto completo de perguntas (antigas + novas)

## 6. Comportamentos Implícitos Observados

### Imutabilidade de Snapshots Existentes
- Snapshots já criados NUNCA são recriados ou alterados
- O método create_if_not_exists garante idempotência
- Se uma pergunta for adicionada múltiplas vezes, apenas o primeiro snapshot persiste

### Imutabilidade de Runs Existentes
- Runs criados ANTES deste comando mantêm seu conjunto original de perguntas
- Não há atualização retroativa de runs
- Cada run é uma "foto" do experimento no momento de sua criação

### Evolução Explícita
- A evolução do experimento é SEMPRE explícita (--add-questions)
- Não há evolução automática ou implícita
- O usuário tem controle total sobre quando expandir o experimento

### Separação entre Experimento e Run
- Experimento: configuração evolutiva (pode mudar)
- Run: execução imutável (não muda após criação)
- Run copia snapshots do experimento no momento de sua criação

### Ordem das Perguntas
- Snapshots são criados na ordem em que são processados
- A ordem de processamento segue a ordem dos IDs fornecidos
- Não há reordenação automática de snapshots existentes

### Independência de Datasets
- As perguntas são carregadas do banco de dados, não do JSON
- Se o dataset JSON mudar após a criação do experimento, os snapshots permanecem inalterados
- Garante reprodutibilidade independente de mudanças externas

### Validação de Integridade
- experiment_id é SEMPRE requerido para snapshots
- question_id deve referenciar uma pergunta existente
- Foreign keys garantem integridade referencial

### Feedback sobre Impacto
- O comando informa explicitamente quantos snapshots NOVOS foram criados
- Informa o total de snapshots no experimento
- Explicita que runs existentes não são afetados
- Explicita que runs futuros usarão o conjunto atualizado

### Tolerância a Erros
- Se uma pergunta não for encontrada, as demais são processadas
- Erros em perguntas individuais não interrompem o processo
- Warnings são registrados para perguntas problemáticas
