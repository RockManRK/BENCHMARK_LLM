# Comando: --create-experiment

## 1. Visão Geral

Este comando cria um novo experimento com configuração congelada e snapshots de perguntas. Um experimento representa uma configuração de pesquisa específica que pode ser reproduzida através de múltiplas execuções.

O comando realiza duas operações principais:
- Cria um registro de experimento com configuração congelada (hash de configuração)
- Cria snapshots imutáveis das perguntas que serão usadas no experimento

**Importante:** Este comando NÃO cria execuções (runs) e NÃO executa nenhum benchmark. Ele apenas prepara a estrutura do experimento.

## 2. Pré-condições Observadas

- O banco de dados deve estar inicializado e acessível
- O arquivo de dataset de perguntas (JSON) deve existir no caminho configurado
- Se o caminho do dataset não for encontrado, um aviso é exibido mas a execução continua
- A chave de API do OpenRouter NÃO é necessária para este comando (não há chamadas à API)

## 3. Fluxo de Execução (Passo a Passo)

1. **Inicialização do Banco de Dados**
   - O gerenciador de banco de dados é inicializado
   - O schema é criado se não existir

2. **Validação do Nome do Experimento**
   - Verifica se já existe um experimento com o mesmo nome
   - Se existir, a operação é interrompida com erro

3. **Resolução das Perguntas**
   - Se perguntas foram especificadas via linha de comando (--questions), usa essas
   - Se NÃO foram especificadas perguntas, carrega TODAS as perguntas disponíveis no dataset JSON
   - Ranges de perguntas (ex: Q001-Q010) são expandidos para IDs individuais
   - As perguntas são persistidas no banco de dados (se já não existirem)

4. **Resolução do Seed**
   - Verifica seed especificada via linha de comando (--seed)
   - Se não especificada, verifica seed no arquivo .env
   - Se nenhuma estiver configurada, usa None (sem randomização, ordem original A,B,C,D)

5. **Criação do Registro do Experimento**
   - Gera um ID único para o experimento (prefixo "exp-" + 8 caracteres hex)
   - Constrói JSON de configuração congelada contendo:
     - Prompt padrão
     - Configuração de outputs estruturados
     - Política de seed
     - Caminho do questionário
     - URL base do OpenRouter
     - Iterações padrão
   - Calcula hash da configuração (SHA-256, primeiros 16 caracteres)
   - Insere registro na tabela `experiments`

6. **Criação dos Snapshots de Perguntas**
   - Para cada pergunta no filtro:
     - Carrega a pergunta completa do banco de dados
     - Constrói JSON da pergunta com todos os campos (id, stem, options, correct_answer, has_image, image_path, status)
     - Verifica se snapshot já existe para este par (experiment_id, question_id)
     - Se NÃO existir, cria novo snapshot na tabela `question_snapshots`
     - Se já existir, reutiliza o snapshot existente (idempotência)

7. **Exibição do Resumo**
   - Exibe mensagem de sucesso com:
     - Nome e ID do experimento
     - Hash de configuração
     - Quantidade de perguntas e snapshots criados
     - Política de seed utilizada
     - Próximos passos sugeridos

## 4. Decisões Implícitas (If / Else)

| Condição | Comportamento |
|----------|---------------|
| Nome do experimento já existe | Interrompe com erro "Experiment 'X' already exists" |
| Questions filter vazio | Carrega TODAS as perguntas do dataset JSON |
| Questions filter especificado | Usa apenas as perguntas especificadas |
| Dataset JSON não encontrado | Exibe aviso mas continua (pode falhar depois) |
| Snapshot já existe | Reutiliza snapshot existente (não duplica) |
| Pergunta não encontrada | Registra warning e pula para a próxima |
| Seed não especificada | Usa None (ordem original, sem randomização) |
| Seed = "AUTO" | Será gerado seed automático quando o run for criado |
| Seed = inteiro | Usa o valor fixo especificado |

## 5. Efeitos Colaterais

### Leituras no Banco de Dados
- Verifica existência do experimento pelo nome
- Verifica existência de snapshots para cada pergunta

### Escritas no Banco de Dados
- **Tabela `experiments`**: 1 registro inserido
- **Tabela `questions`**: Perguntas são persistidas (se não existirem)
- **Tabela `question_snapshots`**: N registros inseridos (um por pergunta)

### Entidades Criadas
- 1 Experiment (com ID único, config_json, config_hash)
- N QuestionSnapshots (cópias imutáveis das perguntas)

### Estado do Sistema Após Execução
- Experimento existe com status "criado"
- Snapshots de perguntas estão disponíveis para uso em runs futuros
- Nenhum run foi criado
- Nenhum modelo foi associado ao experimento
- Nenhuma execução foi realizada

## 6. Comportamentos Implícitos Observados

### Idempotência dos Snapshots
- Snapshots são criados apenas uma vez por par (experiment_id, question_id)
- Se o comando for executado múltiplas vezes, snapshots existentes são reutilizados
- O JSON da pergunta é capturno no momento da criação e NUNCA é alterado

### Carregamento Padrão de Perguntas
- Se --questions NÃO for especificado, o sistema carrega TODAS as perguntas disponíveis
- Este é o comportamento padrão intencional
- Segue o princípio: "O que um usuário esperaria se não configurasse nada?"

### Separação entre Criação e Execução
- Este comando apenas PREPARA o experimento
- Para executar benchmarks, é necessário:
  1. Adicionar modelos ao experimento (--add-model)
  2. Criar um run (--create-run)
  3. Executar o run (--run)

### Configuração Congelada
- O hash de configuração é calculado no momento da criação
- Configurações futuras não afetam experimentos existentes
- Runs criados sob este experimento herdam a configuração congelada

### Persistência de Perguntas
- Perguntas são persistidas na tabela `questions` ao serem carregadas do JSON
- Esta persistência é idempotente (não duplica se já existir)
- Garante trilha de auditoria independente da versão do arquivo JSON

### Validação de Integridade
- O experiment_id é SEMPRE requerido para snapshots
- Não há suporte para experiment_id = NULL
- Todo snapshot deve pertencer a um experimento válido
