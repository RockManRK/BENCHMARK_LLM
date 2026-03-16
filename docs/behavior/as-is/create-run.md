# Comando: --create-run

## 1. Visão Geral

Este comando cria uma nova execução (run) para um experimento existente. Um run representa uma instância específica de benchmark que será executada com configuração específica.

O comando realiza três operações principais:
- Cria um registro de run com configuração específica
- Copia todas as variantes de modelo do experimento para o run
- Prepara a estrutura para execução futura

**Importante:** Este comando NÃO executa o benchmark. Ele apenas cria a estrutura do run. A execução é feita separadamente via --run ou --execute-run.

## 2. Pré-condições Observadas

- O experimento deve existir (verificado pelo nome)
- O banco de dados deve estar inicializado
- O experimento deve ter pelo menos uma variante de modelo configurada
- O experimento deve ter pelo menos um snapshot de pergunta configurado
- A chave de API do OpenRouter NÃO é necessária (não há chamadas à API neste comando)

## 3. Fluxo de Execução (Passo a Passo)

1. **Verificação do Experimento**
   - Busca o experimento pelo nome fornecido
   - Se não encontrado, interrompe com erro

2. **Geração do Run ID**
   - Gera timestamp atual (formato: YYYYMMDDHHMMSS)
   - Gera ID único (8 caracteres hex via UUID)
   - Combina: run-{timestamp}-{unique_id}
   - Ex: run-20260316143022-a1b2c3d4

3. **Resolução do Seed**
   - Verifica seed especificada via linha de comando (--seed)
   - Se não especificada, verifica seed no arquivo .env
   - Se nenhuma estiver configurada, usa None (sem randomização)
   - Se seed = "AUTO", gera número aleatório (0 a 2^31-1)
   - Se seed = inteiro, usa o valor fixo especificado

4. **Criação do Registro do Run**
   - Cria objeto Run com:
     - run_id: ID gerado no passo 2
     - experiment_id: ID do experimento
     - seed: valor resolvido no passo 3
     - is_dev: False (run de produção)
     - started_at: timestamp atual
     - status: "running"
   - Insere registro na tabela `runs`

5. **Cópia das Variantes de Modelo**
   - Busca todas as variantes associadas ao experimento (tabela `experiment_models`)
   - Para cada variante encontrada:
     - Tenta associar variante ao run na tabela `run_models`
     - Define status inicial como "pending"
     - Se associação já existir, registra erro e continua

6. **Exibição do Resumo**
   - Exibe mensagem de sucesso com:
     - Run ID criado
     - Nome do experimento
     - Seed utilizada (com origem)
     - Status do run
   - Exibe próximos passos sugeridos:
     - Adicionar modelos (se necessário)
     - Executar o run

## 4. Decisões Implícitas (If / Else)

| Condição | Comportamento |
|----------|---------------|
| Experimento não encontrado | Interrompe com erro "Experiment 'X' not found" |
| Seed = None | Usa None (ordem original A,B,C,D, sem randomização) |
| Seed = "AUTO" | Gera número aleatório único para este run |
| Seed = inteiro | Usa o valor fixo especificado |
| Variante já associada ao run | Registra erro e continua (não duplica) |
| Experimento sem modelos | Cria run, mas não terá modelos para executar |
| Experimento sem perguntas | Cria run, mas execução falhará (sem perguntas) |
| Associação falha | Registra erro no log mas não interrompe |

## 5. Efeitos Colaterais

### Leituras no Banco de Dados
- Verifica existência do experimento pelo nome
- Busca todas as variantes associadas ao experimento
- Verifica associações existentes em run_models

### Escritas no Banco de Dados
- **Tabela `runs`**: 1 registro inserido
- **Tabela `run_models`**: N registros inseridos (um por variante do experimento)

### Entidades Criadas
- 1 Run (com status "running")
- N RunModel (associações com status "pending")

### Estado do Sistema Após Execução
- Run existe com status "running"
- Variantes de modelo estão associadas ao run
- Todas as variantes têm status "pending"
- Nenhuma resposta foi gerada
- Nenhuma execução foi realizada

## 6. Comportamentos Implícitos Observados

### ⚠️ VARIANTES SÃO COPIADAS, NÃO REFERENCIADAS (IMPORTANTE)

**Comportamento crítico:**
- Variantes são **COPIADAS** do experimento para o run
- Não é uma referência, é uma associação independente
- **Cada run tem sua própria "foto" das variantes no momento da criação**

**Fluxo de cópia:**
1. Busca todas as variantes associadas ao experimento
2. Para cada variante:
   - **Cria associação run_model com variant_id**
   - Define status inicial como "pending"
   - **NÃO cria nova variante** (usa variant_id existente)

**Impacto:**
- Mudanças futuras nas variantes do experimento **NÃO afetam** runs existentes
- Run pode ser executado mesmo se variante for deletada do experimento
- Garante reprodutibilidade: run usa configuração congelada

### Cópia de Variantes do Experimento
- Variantes são COPIADAS do experimento para o run
- Não é uma referência, é uma associação independente
- Mudanças futuras nas variantes do experimento NÃO afetam runs existentes
- Cada run tem sua própria "foto" das variantes no momento da criação

### Status Inicial "Running"
- Run é criado com status "running"
- Indica que o run está pronto para execução
- Status será atualizado para "completed" ou "failed" após execução
- Status "running" permite adição de modelos (--add-models)

### Status Inicial "Pending" para Modelos
- Cada modelo associado ao run inicia com status "pending"
- Indica que o modelo ainda não foi executado
- Status será atualizado para "running" durante execução
- Status será atualizado para "completed" após execução

### Geração de Run ID Único
- Run ID é baseado em timestamp + UUID
- Garante unicidade mesmo para execuções simultâneas
- Formato legível: run-YYYYMMDDHHMMSS-xxxxxxxx
- Timestamp permite ordenação cronológica

### Resolução de Seed com Origem
- Seed pode vir de CLI, .env, ou ser gerada automaticamente
- O sistema informa a origem da seed no feedback
- Seed "AUTO" gera valor diferente para cada run
- Seed fixa garante reprodutibilidade entre runs

### Separação entre Criação e Execução
- Este comando apenas PREPARA o run
- Para executar o benchmark, é necessário:
  - Usar --run ou --execute-run separadamente
- Esta separação permite:
  - Revisão da configuração antes de executar
  - Adição de modelos antes de executar
  - Execução em momento diferente da criação

### Múltiplos Runs por Experimento
- Um experimento pode ter múltiplos runs
- Cada run é independente
- Cada run pode ter seed diferente
- Runs são ordenados por started_at DESC (mais recente primeiro)

### Validação de Integridade
- Run deve referenciar experimento existente
- RunModel deve referenciar run e variante existentes
- Foreign keys garantem integridade referencial
- Status deve ser um dos valores válidos

### Persistência de Configuração
- Seed é persistida no momento da criação
- Não pode ser alterada após criação
- Garante reprodutibilidade do run
- Seed é registrada no banco de dados

### Tolerância a Erros na Associação
- Se uma associação de modelo falhar, as demais são processadas
- Erros são registrados no log mas não interrompem
- Run é criado mesmo se algumas associações falharem

### Feedback sobre Seed
- Exibe valor da seed e sua origem
- Origem pode ser: "auto-generated", "fixed (X)", "using default (off)"
- Feedback claro sobre política de randomização utilizada
