# Changelog - Benchmark LLM

## Versão 1.1.0 (Em Desenvolvimento)

### Breaking Changes

#### 1. Reorganização do Schema da Tabela `responses`
- **Remoção da coluna `output_tokens`**: Consolidado em `response_tokens`
- **Mudança de `parse_confidence` DEFAULT**: De `'clear'` para `'unknown'` (mais conservador)
- **Documentação explícita de tokens**:
  - `total_tokens = input_tokens + response_tokens` (exclui reasoning_tokens)
  - `effective_tokens = input_tokens + response_tokens + reasoning_tokens`
- **Modelo de revisão manual fechado**: 5 colunas finais (parse_confidence, review_status, reviewed_by, reviewed_at, manual_answer)

**Arquivos:** `src/db/schema.sql`, `src/db/models.py`, `src/db/repository.py`, `src/core/question_executor.py`, `src/cli/statistics.py`, `src/cli/output_formatter.py`, `src/cli/review_ui.py`

**Migração:** Execute `migrations/001_remove_output_tokens.sql` para bancos existentes.

**Justificativa:**
- `output_tokens` e `response_tokens` eram duplicados
- `response_tokens` é semanticamente mais correto (tokens de resposta/completion)
- `parse_confidence='unknown'` evita falsos positivos (assume "não avaliado" ao invés de "clear")

#### 2. Consolidação da Extração de Tokens
- **Nova função `_extract_token_usage()`**: Centraliza toda extração de tokens
- **Remoção de código duplicado**: Token extraction em 3 lugares → 1 lugar só
- **Logging estruturado**: Logs de tokens agora são parseáveis

**Arquivos:** `src/core/question_executor.py`

**Benefícios:**
- Menos duplicação de código
- Mais fácil de manter e testar
- Logs estruturados para debugging

### Documentação Atualizada

- **README.md**: Schema atualizado com `response_tokens` e fórmulas de tokens
- **docs/SCHEMA.md**: Documentação completa da tabela `responses` com fórmulas
- **docs/MIGRATION.md**: Guia de migração v1.1.0 com exemplos de código
- **CHANGELOG.md**: Este arquivo

### Novas Funcionalidades

#### 1. Configurações de Modelo via .env
- `MODEL_MAX_TOKENS`: Controle de tokens máximos
- `MODEL_TEMPERATURE`: Controle de temperatura/criatividade
- `MODEL_TOP_P`: Nucleus sampling
- `MODEL_TOP_K`: Top-k sampling
- `MODEL_REPEAT_PENALTY`: Penalidade de repetição

**Arquivos:** `src/utils/config.py`, `.env.example`

#### 2. Detecção Automática de Modelo
- Consulta API para obter informações completas do modelo
- Salva metadados no banco: `n_params`, `size`, `context_length`, etc.
- Usa nome exato retornado pela API

**Arquivos:** `src/api/client.py`, `src/main.py`, `src/db/schema.py`

#### 3. Structured Outputs (Experimental)
- JSON schema para respostas estruturadas
- Fallback automático se modelo não suportar
- Metadata `used_structured_outputs` salva no banco

**Arquivos:** `src/utils/answer_schema.py`, `src/core/question_executor.py`, `src/utils/config.py`

#### 4. CLI Simplificada
- `bcllm.py` como entry point
- `setup.py` para instalação como pacote
- Comando `bcllm` disponível após `pip install -e .`

**Arquivos:** `bcllm.py`, `setup.py`

#### 5. Vary Seed
- Flag `--vary-seed` para variar seed por iteração
- Útil para testes de consistência

**Arquivos:** `src/cli/cli.py`, `src/main.py`

#### 6. Reasoning Tokens Support
- OpenRouter standard reasoning parameters
- CLI flags: `--reasoning-effort`, `--reasoning-tokens`, `--reasoning-exclude`
- Database fields: `reasoning_details`, `reasoning_tokens`
- Graceful fallback for models without reasoning support

### Melhorias

#### 1. Documentação
- `MANUAL.md` completo com todos os comandos
- Exemplos de uso para diferentes cenários
- Troubleshooting expandido

#### 2. Banco de Dados
- Tabela `models` com metadata
- Tabela `responses` com campo `metadata`
- Suporte a `context_length` e `max_completion_tokens`

**Arquivos:** `src/db/schema.py`, `src/db/models.py`, `src/db/repository.py`

#### 3. Robustez
- Fallback automático para métodos tradicionais
- Logs detalhados de todas as operações
- Tratamento de erro para structured outputs

### Correções

#### 1. Parser de Respostas
- Suporte a múltiplos formatos de resposta
- Regex melhorado para extração de letras
- Fallback para `reasoning_content` se `content` vazio

**Arquivos:** `src/core/question_executor.py`, `src/api/parser.py`

#### 2. Banco em Memória (--test-mode)
- Correção de foreign keys para bancos em memória
- Reuso de conexão para preservar dados
- Modelos registrados automaticamente

**Arquivos:** `src/db/schema.py`, `src/db/repository.py`, `src/core/run_manager.py`

### Configurações Quebradas (Breaking Changes)

Nenhuma. Todas as mudanças são backward compatible.

### Upgrade Guide

1. Atualizar dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Copiar novas configurações:
   ```bash
   cp .env.example .env
   # Editar .env com suas configurações
   ```

3. (Opcional) Instalar como pacote:
   ```bash
   pip install -e .
   bcllm --help
   ```

### Notas de Versão

- **Structured Outputs** é experimental e desabilitado por padrão
- **MODEL_MAX_TOKENS** é crítico para modelos com reasoning (Qwen, o1)
- **Detecção automática** funciona com OpenRouter, llama.cpp, Ollama
- **Test Mode** agora usa banco em memória corretamente

---

## Versão 1.0.0 (Lançada)

### Funcionalidades Principais

- Benchmark de múltiplos modelos LLM
- Questionário de 100 questões médicas
- Suporte a questões com imagem
- Randomização de respostas
- Múltiplas iterações
- Armazenamento SQLite
- Logs operacionais
- CLI completa

### Requisitos

- Python 3.10+
- OpenRouter API key (ou servidor local)

### Instalação

```bash
pip install -r requirements.txt
python -m src.main --help
```
