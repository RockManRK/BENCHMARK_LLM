# Guia de Testes - Benchmark LLM v1.1.0

## 📋 Funcionalidades Prontas para Teste

### 1. Configurações de Modelo via .env

**O que testar:**
```bash
# Teste 1: Sem configuração (padrão do modelo)
# .env:
MODEL_MAX_TOKENS=
MODEL_TEMPERATURE=

python bcllm.py --models Qwen --questions Q001 --test-mode

# Teste 2: Com configuração explícita
# .env:
MODEL_MAX_TOKENS=16384
MODEL_TEMPERATURE=0.0

python bcllm.py --models Qwen --questions Q001 --test-mode
```

**Resultado esperado:**
- Teste 1: Modelo usa padrão (llama.cpp: 100 tokens)
- Teste 2: Modelo usa 16384 tokens
- Logs mostram diferença no tempo e tokens gerados

---

### 2. Detecção Automática de Modelo

**O que testar:**
```bash
python bcllm.py --models Qwen --questions Q001 --test-mode --verbose
```

**Resultado esperado:**
```
INFO - Found model info for Qwen: Qwen
INFO - Model metadata: n_params=34660610688, size=21158128128
INFO - Model Qwen resolved to Qwen
```

**Verificar no banco:**
```sql
SELECT model_id, metadata, context_length FROM models;
```

---

### 3. Structured Outputs

**O que testar:**
```bash
# Teste A: Com structured outputs (modelo que suporta)
# .env:
USE_STRUCTURED_OUTPUTS=true

python bcllm.py --models openai/gpt-4o --questions Q001 --test-mode

# Teste B: Com structured outputs (modelo que não suporta)
# .env:
USE_STRUCTURED_OUTPUTS=true

python bcllm.py --models Qwen --questions Q001 --test-mode

# Teste C: Sem structured outputs
# .env:
USE_STRUCTURED_OUTPUTS=false

python bcllm.py --models Qwen --questions Q001 --test-mode
```

**Resultado esperado:**
- Teste A: ✅ Usa structured outputs, resposta JSON
- Teste B: ⚠️ Tenta, falha, fallback automático, log mostra fallback
- Teste C: ✅ Usa método tradicional

**Verificar metadata:**
```sql
SELECT response_id, metadata FROM responses LIMIT 5;
-- Deve mostrar: {"used_structured_outputs": true/false}
```

---

### 4. CLI Simplificada

**O que testar:**
```bash
# Opção 1: Python direto
python bcllm.py --help

# Opção 2: Após instalar pacote
pip install -e .
bcllm --help
```

**Resultado esperado:**
- Help mostra todas as flags
- Flags novas: `--vary-seed`, `--test-mode`

---

### 5. Vary Seed

**O que testar:**
```bash
python bcllm.py --models Qwen --iterations 3 --seed 42 --vary-seed --questions Q001-Q003 --test-mode --verbose
```

**Resultado esperado:**
```
INFO - Using seed 1042 for iteration 1 (base: 42)
INFO - Using seed 2042 for iteration 2 (base: 42)
INFO - Using seed 3042 for iteration 3 (base: 42)
```

---

### 6. Test Mode (Banco em Memória)

**O que testar:**
```bash
python bcllm.py --models Qwen --questions Q001 --test-mode
```

**Resultado esperado:**
- Executa sem erros
- Não cria arquivo `data/benchmark.db`
- Log mostra: `Using in-memory database for test mode`

---

## 🧪 Plano de Teste Completo

### **Teste 1: Configuração Básica**
```bash
# Configurar .env
cp .env.example .env
# Editar com suas configurações

# Teste básico
python bcllm.py --models Qwen --questions Q001 --test-mode --verbose
```

**Verificar:**
- [ ] Carrega questões
- [ ] Conecta na API
- [ ] Retorna resposta
- [ ] Extrai letra correta

---

### **Teste 2: Múltiplos Modelos**
```bash
python bcllm.py --models Qwen claude-3 --questions Q001-Q005 --iterations 2 --test-mode
```

**Verificar:**
- [ ] Executa ambos modelos
- [ ] 2 iterações por modelo
- [ ] Metadata salva corretamente

---

### **Teste 3: Structured Outputs**
```bash
# .env: USE_STRUCTURED_OUTPUTS=true
python bcllm.py --models Qwen --questions Q001 --test-mode --verbose
```

**Verificar:**
- [ ] Tenta com structured outputs
- [ ] Fallback se não suportar
- [ ] Log mostra tentativa e fallback
- [ ] Metadata: `used_structured_outputs: false`

---

### **Teste 4: Detecção de Modelo**
```bash
python bcllm.py --models Qwen --questions Q001 --test-mode --verbose
```

**Verificar:**
- [ ] Log mostra metadata do modelo
- [ ] `n_params`, `size`, `context_length` detectados
- [ ] Banco salva metadata completa

---

### **Teste 5: Vary Seed**
```bash
python bcllm.py --models Qwen --iterations 3 --seed 42 --vary-seed --questions Q001 --test-mode
```

**Verificar:**
- [ ] Seeds diferentes por iteração
- [ ] Log mostra seeds usadas
- [ ] Randomização diferente em cada iteração

---

## 📊 Checklist de Validação

### **Funcionalidade**
- [ ] Configurações .env funcionam
- [ ] Detecção automática de modelo funciona
- [ ] Structured outputs com fallback funciona
- [ ] CLI `bcllm.py` funciona
- [ ] `--vary-seed` funciona
- [ ] `--test-mode` funciona

### **Banco de Dados**
- [ ] Metadata do modelo salva
- [ ] `used_structured_outputs` salvo
- [ ] Test mode não cria arquivo
- [ ] Foreign keys funcionam

### **Logs**
- [ ] Logs detalhados com `--verbose`
- [ ] Detecção de modelo logada
- [ ] Fallback de structured outputs logado
- [ ] Seeds logadas

### **Documentação**
- [ ] `MANUAL.md` atualizado
- [ ] `README.md` atualizado
- [ ] `--help` correto
- [ ] `.env.example` completo

---

## 🐛 Problemas Conhecidos para Verificar

1. **llama.cpp não retorna detalhes do modelo**
   - Retorna apenas `id: "Qwen"` sem versão
   - Solução: Usar metadata do endpoint `/v1/models`

2. **Structured outputs podem falhar**
   - Nem todos modelos suportam
   - Sistema deve fazer fallback automático

3. **max_tokens padrão do llama.cpp é 100**
   - Insuficiente para reasoning models
   - Configurar `MODEL_MAX_TOKENS=16384`

---

## 📝 Scripts de Teste Rápidos

### **Teste 1: Hello World**
```bash
python bcllm.py --models Qwen --questions Q001 --test-mode --dry-run
# Esperado: "Configuration validated successfully"
```

### **Teste 2: Execução Real**
```bash
python bcllm.py --models Qwen --questions Q001 --test-mode --verbose
# Esperado: Executa questão, mostra resposta
```

### **Teste 3: Múltiplas Questões**
```bash
python bcllm.py --models Qwen --questions Q001-Q005 --test-mode
# Esperado: Executa 5 questões
```

### **Teste 4: Múltiplos Modelos**
```bash
python bcllm.py --models Qwen gpt-4 --questions Q001 --test-mode
# Esperado: Executa ambos modelos
```

---

## 🧪 Testes com Mock (Sem Servidor)

### Executar testes
```bash
python -m pytest tests/test_mock_basic.py -v
# Esperado: 3 testes passam em ~2 segundos
```

### Fixtures disponíveis
- `mock_chat_completion()` - Mock de resposta da API
- `mock_chat_completion_error()` - Mock de erro (500, 429)
- `mock_models_endpoint()` - Mock de models endpoint

### Vantagens
- ✅ Rápido (~0.5s por teste)
- ✅ Sem custo (zero créditos)
- ✅ Sem servidor necessário
- ✅ Controle total dos cenários

---

## ✅ Critérios de Aceite

O sistema está pronto quando:

1. ✅ Todos os testes acima passam
2. ✅ Logs mostram informações corretas
3. ✅ Banco de dados salva metadata
4. ✅ Fallback de structured outputs funciona
5. ✅ Documentação está correta
6. ✅ `--help` mostra todas as opções

---

**Próximo Passo:** Ligar servidor llama.cpp e executar testes! 🚀
