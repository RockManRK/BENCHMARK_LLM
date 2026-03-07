# Benchmark LLM - Manual de Uso

## Início Rápido

### Comando Simplificado
```bash
# Após instalação (recomendado)
bcllm --models Qwen --questions Q001-Q010

# Ou usando Python diretamente
python bcllm.py --models Qwen --questions Q001-Q010

# Ou método tradicional
python -m src.main --models Qwen --questions Q001-Q010
```

## Comandos Disponíveis

### Selecionar Modelos
```bash
bcllm --models openai/gpt-4
bcllm --models Qwen claude-3 llama-3
```

### Filtrar Questões
```bash
# Questão específica
bcllm --questions Q001

# Múltiplas questões
bcllm --questions Q001 Q005 Q010

# Faixa de questões
bcllm --questions Q001-Q020

# Combinado
bcllm --questions Q001 Q005-Q010
```

### Iterações
```bash
# Uma iteração (padrão)
bcllm --models Qwen

# Múltiplas iterações
bcllm --models Qwen --iterations 3
```

### Configurações do Modelo

#### max-tokens (CRÍTICO para reasoning models)
```bash
# Para Qwen, o1, modelos com reasoning
bcllm --models Qwen --max-tokens 16384

# Para modelos padrão
bcllm --models gpt-4 --max-tokens 4096

# Usar padrão do servidor (não recomendado para llama.cpp)
bcllm --models Qwen
```

**O que é:** Número máximo de tokens que o modelo pode gerar.

**Por que importa:**
- llama.cpp padrão: 100 tokens (insuficiente para reasoning)
- OpenRouter padrão: 4096-8192 tokens
- Reasoning models precisam de 10000+ tokens

**Valores recomendados:**
- Qwen, o1, modelos com CoT: `16384`
- GPT-4, Claude: `4096` ou `8192`
- Modelos locais simples: `2048`

#### temperature
```bash
# Determinístico (recomendado para benchmark)
bcllm --models Qwen --temperature 0.0

# Mais criativo
bcllm --models Qwen --temperature 0.7

# Máxima criatividade
bcllm --models Qwen --temperature 1.0
```

**O que é:** Controla aleatoriedade da geração.

**Valores:**
- `0.0`: Determinístico, sempre mesma resposta (recomendado)
- `0.5`: Balanceado
- `1.0`: Máxima criatividade/variabilidade

#### seed (reprodutibilidade)
```bash
# Usar seed específica
bcllm --models Qwen --seed 42

# Mesma seed = mesmas respostas
bcllm --models Qwen --seed 42 --iterations 3
```

**O que é:** Seed para randomização das opções de resposta.

**Por que usar:** Garante que testes sejam reprodutíveis.

#### vary-seed (consistência entre iterações)
```bash
# Usar seed diferente para cada iteração
bcllm --models Qwen --iterations 3 --seed 42 --vary-seed
```

**O que é:** Varia a seed automaticamente para cada iteração.

**Quando usar:**
- Testar consistência do modelo
- Evitar viés de randomização fixa
- Estudos estatísticos

**Como funciona:**
- Iteração 1: seed = 42
- Iteração 2: seed = 1042
- Iteração 3: seed = 2042

### Structured Outputs (Experimental)

```bash
# Habilitar structured outputs (via .env)
# USE_STRUCTURED_OUTPUTS=true

bcllm --models openai/gpt-4o --questions Q001
```

**O que é:** Força o modelo a responder em JSON estruturado.

**Vantagens:**
- ✅ Resposta sempre no formato correto
- ✅ Sem necessidade de parser complexo
- ✅ Inclui metadados (confiança, etc.)

**Modelos suportados:**
- ✅ OpenAI GPT-4o e posteriores
- ✅ Google Gemini 2.x
- ✅ Anthropic Sonnet 4.5+, Opus 4.1+
- ✅ Fireworks (todos)
- ⚠️ Qwen/llama.cpp: Provavelmente não suporta (fallback automático)

**Como funciona:**
1. Sistema tenta com structured outputs
2. Se modelo não suportar → fallback automático
3. Metadata salva: `used_structured_outputs: true/false`

**Schema usado:**
```json
{
  "answer": "A"
}
```

### Reasoning Tokens (Opcional)

```bash
# Com reasoning effort
bcllm --models openai/o3-mini --reasoning-effort high --questions Q001

# Com max tokens
bcllm --models anthropic/claude-sonnet-4.5 --reasoning-tokens 2000 --questions Q001

# Excluir reasoning da resposta
bcllm --models openai/o1 --reasoning-exclude --questions Q001
```

### Modos de Execução

#### Test Mode (não salva no banco)
```bash
bcllm --models Qwen --questions Q001 --test-mode
```

**Quando usar:**
- Testar configuração
- Validar questões
- Testar LLMs locais
- Desenvolvimento

#### Dry Run (valida sem executar)
```bash
bcllm --models Qwen --dry-run
```

**Quando usar:**
- Validar configuração
- Testar conexão
- Verificar se API key está configurada

#### Verbose (logs detalhados)
```bash
bcllm --models Qwen --verbose
```

**Quando usar:**
- Debug de problemas
- Ver detalhes da execução
- Monitorar progresso

### Output Format

```bash
# Console (padrão)
bcllm --models Qwen --output console

# JSON (para análise)
bcllm --models Qwen --output json

# CSV (para Excel/planilhas)
bcllm --models Qwen --output csv

# Markdown (para relatórios)
bcllm --models Qwen --output markdown

# Salvar em arquivo
bcllm --models Qwen --output json --output-file resultados.json
```

## Exemplos de Uso

### Benchmark Básico
```bash
# Testar GPT-4 com 10 questões
bcllm --models openai/gpt-4 --questions Q001-Q010
```

### Comparar Múltiplos Modelos
```bash
# Testar 3 modelos com mesmas questões
bcllm --models openai/gpt-4 anthropic/claude-3 google/gemini-pro \
  --questions Q001-Q020 --iterations 3
```

### Testar LLM Local
```bash
# Configurar no .env primeiro:
# OPENROUTER_BASE_URL=http://localhost:8080/v1

# Executar
bcllm --models Qwen --questions Q001-Q010 --max-tokens 16384
```

### Teste Rápido (sem salvar)
```bash
bcllm --models Qwen --questions Q001 --test-mode --max-tokens 16384
```

### Benchmark Completo
```bash
# Configurar .env:
# OPENROUTER_API_KEY=sua-chave-aqui
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# MODEL_MAX_TOKENS=16384
# MODEL_TEMPERATURE=0.0

# Executar
bcllm --models openai/gpt-4 anthropic/claude-3 \
  --iterations 5 --output json --output-file benchmark.json
```

## Configuração via .env

### Configuração Mínima
```env
OPENROUTER_API_KEY=sua-chave-aqui
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

### Configuração para Reasoning Models
```env
OPENROUTER_API_KEY=sua-chave-aqui
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MODEL_MAX_TOKENS=16384
MODEL_TEMPERATURE=0.0
```

### Configuração para LLM Local
```env
OPENROUTER_API_KEY=local-key
OPENROUTER_BASE_URL=http://192.168.1.107:8080/v1
MODEL_MAX_TOKENS=16384
MODEL_TEMPERATURE=0.0
```

### Configuração Completa (Todas Opções)
```env
# OpenRouter API
OPENROUTER_API_KEY=sua-chave-aqui
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Database
DATABASE_PATH=./data/benchmark.db

# Logging
LOG_LEVEL=INFO
LOG_FILE_PATH=./logs/benchmark.log

# Test Configuration
DEFAULT_ITERATIONS=1

# Model Generation (Opcionais, em branco = padrão do modelo)
MODEL_MAX_TOKENS=16384
MODEL_TEMPERATURE=0.0
MODEL_TOP_P=
MODEL_TOP_K=
MODEL_REPEAT_PENALTY=

# Reprodutibilidade
RANDOM_SEED=

# Structured Outputs (Experimental)
USE_STRUCTURED_OUTPUTS=false
```

### Detecção Automática de Modelo

O sistema automaticamente:
1. Consulta a API para obter informações do modelo
2. Salva metadados no banco (n_params, size, context_length)
3. Usa o nome exato retornado pela API

**Exemplo:**
```bash
# Usuário digita
bcllm --models Qwen

# Sistema detecta e salva
model_id: "Qwen"
metadata: {
  "n_params": 34660610688,
  "size": 21158128128,
  "n_ctx_train": 262144
}
```

## Troubleshooting

### Resposta Cortada
**Problema:** `finish_reason: "length"` nos logs
**Solução:** `bcllm --max-tokens 16384`

### Erro de API Key
**Problema:** `OpenRouter API key not configured`
**Solução:** Configurar `OPENROUTER_API_KEY` no `.env`

### Timeout
**Problema:** `Request timed out`
**Solução:** Verificar conexão, reduzir questões, ou aumentar timeout

## Referência Rápida

### Flags de Comando

| Flag | Descrição | Exemplo |
|------|-----------|---------|
| `--models` | Modelos para testar | `--models Qwen gpt-4` |
| `--questions` | Questões para testar | `--questions Q001-Q010` |
| `--iterations` | Iterações por modelo | `--iterations 3` |
| `--seed` | Seed para reprodução | `--seed 42` |
| `--vary-seed` | Varia seed por iteração | `--vary-seed` |
| `--reasoning-effort` | Reasoning effort level | `--reasoning-effort high` |
| `--reasoning-tokens` | Max reasoning tokens | `--reasoning-tokens 2000` |
| `--reasoning-exclude` | Exclude reasoning | `--reasoning-exclude` |
| `--test-mode` | Não salva no banco | `--test-mode` |
| `--dry-run` | Valida sem executar | `--dry-run` |
| `--verbose` | Logs detalhados | `--verbose` |
| `--output` | Formato de saída | `--output json` |
| `--output-file` | Salvar em arquivo | `--output-file results.json` |

### Testes com Mock

```bash
# Rodar testes sem servidor
python -m pytest tests/test_mock_basic.py -v

# 3 testes em ~2 segundos, zero custo
```
| `--reasoning-effort` | Reasoning effort level | `--reasoning-effort high` |
| `--reasoning-tokens` | Max reasoning tokens | `--reasoning-tokens 2000` |
| `--reasoning-exclude` | Exclude reasoning from response | `--reasoning-exclude` |

### Configurações via .env

| Variável | Descrição | Padrão | Recomendado |
|----------|-----------|--------|-------------|
| `OPENROUTER_API_KEY` | Chave da API | - | Obrigatório |
| `OPENROUTER_BASE_URL` | URL base | `openrouter.ai` | Local: `http://localhost:8080/v1` |
| `MODEL_MAX_TOKENS` | Máximo de tokens | Padrão do modelo | `16384` (reasoning) |
| `MODEL_TEMPERATURE` | Temperatura | Padrão do modelo | `0.0` (determinístico) |
| `MODEL_TOP_P` | Nucleus sampling | Padrão do modelo | Deixar em branco |
| `MODEL_TOP_K` | Top-k sampling | Padrão do modelo | Deixar em branco |
| `MODEL_REPEAT_PENALTY` | Penalidade repetição | Padrão do modelo | Deixar em branco |
| `RANDOM_SEED` | Seed global | `None` | `42` ou outro |
| `USE_STRUCTURED_OUTPUTS` | JSON estruturado | `false` | `true` (se suportado) |
| `REASONING_EFFORT` | Reasoning effort level | `None` | `high` para modelos reasoning |
| `REASONING_MAX_TOKENS` | Max reasoning tokens | `None` | `2000` ou conforme necessário |
| `REASONING_EXCLUDE` | Exclude reasoning | `false` | `true` para usar internamente |
| `REASONING_ENABLED` | Enable reasoning | `false` | `true` para habilitar |

### Metadados Salvos

O sistema salva automaticamente:

```json
{
  "model_id": "Qwen",
  "model_metadata": {
    "n_params": 34660610688,
    "size": 21158128128,
    "n_ctx_train": 262144,
    "owned_by": "llamacpp"
  },
  "used_structured_outputs": false,
  "latency_ms": 15234,
  "tokens": {
    "input": 315,
    "output": 1837,
    "total": 2152
  }
}
```
