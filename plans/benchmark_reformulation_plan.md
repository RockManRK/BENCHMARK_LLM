# Plano de Reformulação do Sistema de Benchmark LLM

## Visão Geral

Este plano detalha as etapas necessárias para reformular o sistema de benchmark LLM, implementando os novos conceitos de "experimentos", reorganizando o banco de dados e melhorando o sistema de logging.

## Objetivos Principais

1. Implementar três modos de execução: Test Mode, Dev Mode e Experiment Mode
2. Criar um sistema de experimentos com configuração congelada e auditável
3. Reorganizar completamente o schema do banco de dados
4. Melhorar o sistema de logging para eliminar ambiguidades
5. Garantir que o banco possa ser recriado do zero sem manter compatibilidade com versões anteriores

## Etapas Detalhadas

### 1. Análise da Estrutura Atual

#### 1.1. Banco de Dados Atual
- Tabelas existentes: runs, models, iterations, responses, errors, operational_logs
- Identificar campos e relações atuais
- Comparar com a nova estrutura planejada

#### 1.2. Código Atual
- Mapear como as configurações são gerenciadas
- Identificar onde ocorre o carregamento de perguntas
- Localizar o ponto de inicialização do sistema

### 2. Nova Estrutura de Banco de Dados

#### 2.1. Tabela `experiments`
```sql
experiment_id TEXT PRIMARY KEY,
name TEXT NOT NULL UNIQUE,
description TEXT,
config_json TEXT NOT NULL,
config_hash TEXT NOT NULL,
system_prompt TEXT,
user_prompt_template TEXT,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### 2.2. Tabela `runs`
```sql
run_id TEXT PRIMARY KEY,
experiment_id TEXT,
seed INTEGER,
is_dev BOOLEAN NOT NULL DEFAULT 0,
started_at TIMESTAMP,
finished_at TIMESTAMP,
status TEXT,
FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
```

#### 2.3. Tabela `models`
```sql
model_id TEXT PRIMARY KEY,
provider TEXT,
model_name TEXT,
supports_multimodal BOOLEAN,
metadata_json TEXT
```

#### 2.4. Tabela `questions`
```sql
question_id TEXT PRIMARY KEY,
stem TEXT NOT NULL,
options_json TEXT NOT NULL,
correct_answer TEXT,
has_image BOOLEAN,
image_path TEXT,
status TEXT
```

#### 2.5. Tabela `responses`
```sql
response_id INTEGER PRIMARY KEY AUTOINCREMENT,
run_id TEXT NOT NULL,
question_id TEXT NOT NULL,
model_id TEXT NOT NULL,
iteration INTEGER NOT NULL,
selected_answer TEXT,
response_text TEXT,
is_correct BOOLEAN,
status TEXT,
latency_ms INTEGER,
input_tokens INTEGER,
output_tokens INTEGER,
reasoning_tokens INTEGER,
answer_tokens INTEGER,
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (run_id) REFERENCES runs(run_id),
FOREIGN KEY (question_id) REFERENCES questions(question_id),
FOREIGN KEY (model_id) REFERENCES models(model_id)
```

#### 2.6. Tabela `errors`
```sql
error_id INTEGER PRIMARY KEY AUTOINCREMENT,
run_id TEXT,
question_id TEXT,
model_id TEXT,
error_type TEXT,
error_message TEXT,
stack_trace TEXT,
timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### 2.7. Tabela `schema_metadata`
```sql
table_name TEXT,
column_name TEXT,
description TEXT
```

### 3. Script de Schema SQL

```sql
-- Schema para o novo sistema de benchmark LLM
-- Tabelas: experiments, runs, models, questions, responses, errors, schema_metadata

-- Tabela: experiments
-- Armazena informações sobre experimentos com configuração congelada
CREATE TABLE experiments (
    experiment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    config_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    system_prompt TEXT,
    user_prompt_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela: runs
-- Armazena informações sobre execuções de benchmark
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    experiment_id TEXT,
    seed INTEGER,
    is_dev BOOLEAN NOT NULL DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

-- Tabela: models
-- Armazena informações sobre modelos LLM
CREATE TABLE models (
    model_id TEXT PRIMARY KEY,
    provider TEXT,
    model_name TEXT,
    supports_multimodal BOOLEAN,
    metadata_json TEXT
);

-- Tabela: questions
-- Armazena as perguntas do dataset
CREATE TABLE questions (
    question_id TEXT PRIMARY KEY,
    stem TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_answer TEXT,
    has_image BOOLEAN,
    image_path TEXT,
    status TEXT
);

-- Tabela: responses
-- Armazena as respostas dos modelos às perguntas
CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    selected_answer TEXT,
    response_text TEXT,
    is_correct BOOLEAN,
    status TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    reasoning_tokens INTEGER,
    answer_tokens INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(run_id),
    FOREIGN KEY (question_id) REFERENCES questions(question_id),
    FOREIGN KEY (model_id) REFERENCES models(model_id)
);

-- Tabela: errors
-- Armazena informações sobre erros ocorridos durante execuções
CREATE TABLE errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    question_id TEXT,
    model_id TEXT,
    error_type TEXT,
    error_message TEXT,
    stack_trace TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela: schema_metadata
-- Documentação viva do schema do banco de dados
CREATE TABLE schema_metadata (
    table_name TEXT,
    column_name TEXT,
    description TEXT
);

-- Índices para otimizar consultas comuns
CREATE INDEX idx_runs_experiment_id ON runs(experiment_id);
CREATE INDEX idx_runs_is_dev ON runs(is_dev);
CREATE INDEX idx_responses_run_id ON responses(run_id);
CREATE INDEX idx_responses_question_id ON responses(question_id);
CREATE INDEX idx_responses_model_id ON responses(model_id);
CREATE INDEX idx_responses_iteration ON responses(iteration);
CREATE INDEX idx_errors_run_id ON errors(run_id);
```

### 4. Implementação dos Modos de Execução

#### 4.1. Test Mode
- Ativado com flag `--test-mode`
- Não salva dados no banco
- Não cria run nem experiment
- Configuração vem de CLI/.env
- Usado apenas para validação rápida

#### 4.2. Dev Mode
- Ativado quando nenhum `--experiment` é informado
- Salva runs no banco
- `experiment_id = NULL`
- `is_dev = true`
- Configuração é mutável e não congelada

#### 4.3. Experiment Mode
- Ativado com flag `--experiment <nome>`
- Configuração congelada e auditável
- Criar experiment apenas quando explicitamente solicitado
- Salvar snapshot completo da configuração (JSON + hash)
- Reutilizar configuração congelada em execuções futuras

### 5. Sistema de Logging Aprimorado

#### 5.1. Log de Inicialização Padrão
O log deve conter informações claras sobre:
- Modo de execução
- Nome do experimento (se aplicável)
- Se os dados serão persistidos
- Se a configuração é mutável ou congelada
- Seed efetiva
- Modelos e questões sendo usados

Exemplo:
```
[INFO] Benchmark LLM - Initialization
[INFO] Execution mode      : DEV MODE
[INFO] Experiment          : None
[INFO] Persist data        : YES
[INFO] Configuration       : MUTABLE (CLI/.env)
[INFO] Seed                : 42
[INFO] Models              : Qwen
[INFO] Questions           : Q001-Q010
```

### 6. Atualizações Necessárias

#### 6.1. Atualizar modelos de dados
- Criar novas classes de modelo para refletir a nova estrutura
- Remover ou adaptar modelos antigos

#### 6.2. Atualizar repositórios de dados
- Implementar novos repositórios para as novas tabelas
- Adaptar métodos existentes para a nova estrutura

#### 6.3. Atualizar gerenciamento de execução
- Modificar o RunManager para lidar com experimentos
- Implementar lógica de criação e recuperação de experimentos

#### 6.4. Atualizar carregamento de perguntas
- Modificar o QuestionLoader para armazenar perguntas no banco
- Manter compatibilidade com o formato JSON existente

#### 6.5. Atualizar CLI
- Adicionar parâmetro `--experiment` para ativar o modo de experimento
- Atualizar a lógica de parsing de argumentos

### 7. Documentação

#### 7.1. Documentar o novo schema
- Criar arquivo schema.sql com o novo schema
- Criar documentação explicando cada tabela e coluna

#### 7.2. Atualizar manuais
- Atualizar MANUAL.md com as novas funcionalidades
- Explicar os diferentes modos de execução

## Riscos e Mitigação

1. **Perda de dados**: Como o banco será recriado do zero, não há risco de perda de dados existentes, pois não há dados relevantes.

2. **Incompatibilidade com versões anteriores**: Esta é uma decisão intencional, conforme especificado.

3. **Complexidade na implementação**: A abordagem será modular para facilitar o desenvolvimento e testes.

## Critérios de Sucesso

1. Os três modos de execução funcionam corretamente
2. O sistema de experimentos permite criar, salvar e reutilizar configurações congeladas
3. O logging é claro e elimina ambiguidades
4. O banco de dados segue o schema especificado
5. Todos os testes passam após as alterações
6. A documentação está atualizada

## Cronograma

As etapas devem ser implementadas sequencialmente, com testes após cada grande mudança para garantir que o sistema continue funcional.