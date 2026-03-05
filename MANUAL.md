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

| Flag | Descrição | Exemplo |
|------|-----------|---------|
| `--models` | Modelos para testar | `--models Qwen gpt-4` |
| `--questions` | Questões para testar | `--questions Q001-Q010` |
| `--iterations` | Iterações por modelo | `--iterations 3` |
| `--max-tokens` | Máximo de tokens | `--max-tokens 16384` |
| `--temperature` | Temperatura (0-1) | `--temperature 0.0` |
| `--seed` | Seed para reprodução | `--seed 42` |
| `--test-mode` | Não salva no banco | `--test-mode` |
| `--dry-run` | Valida sem executar | `--dry-run` |
| `--verbose` | Logs detalhados | `--verbose` |
| `--output` | Formato de saída | `--output json` |
| `--output-file` | Salvar em arquivo | `--output-file results.json` |
