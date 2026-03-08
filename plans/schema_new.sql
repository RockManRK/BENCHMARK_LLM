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
