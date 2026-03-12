# Correções: seed e finished_at

## Resumo

Foram implementadas correções para garantir que as colunas `seed` e `finished_at` na tabela `runs` sejam preenchidas corretamente.

## Problemas Identificados

### 1. Coluna `seed` sempre NULL

**Causa:** O método `initialize_run()` estava passando `config.get("seed")` diretamente para o objeto `Run`, sem tratar os diferentes cenários:
- `None` → Não gerava seed
- `"AUTO"` (string) → Não convertia para inteiro
- `int` → Funcionava corretamente

### 2. Coluna `finished_at` sempre NULL

**Causa:** O método `update_run_status()` apenas atualizava o campo `status`, mas nunca setava o campo `finished_at` quando uma run era completada ou falhava.

## Soluções Implementadas

### 1. Novo método `_determine_seed()`

**Arquivo:** `src/core/run_manager.py`

Adicionado um novo método que implementa a seguinte lógica:

| Valor de Entrada | Comportamento | Valor no Banco |
|-----------------|---------------|----------------|
| `None` | Mantém ordem original | `NULL` |
| `""` (vazio) | Mantém ordem original | `NULL` |
| `"AUTO"` | Gera número aleatório por RUN | `inteiro (0 a 2^31-1)` |
| `123` (int) | Usa o seed fornecido | `123` |
| `"456"` (string) | Converte para inteiro | `456` |
| `"invalid"` | Fallback seguro | `NULL` |

**Código:**
```python
def _determine_seed(self, config: dict[str, Any]) -> Optional[int]:
    """Determine the seed value based on configuration.

    Rules:
    - None/empty → Keep original order (seed = None)
    - "AUTO" → Generate random seed per RUN
    - int → Use provided seed
    """
    seed_config = config.get("seed")

    # Case 1: None or empty → Keep original order
    if seed_config is None or seed_config == "":
        logger.debug("No seed configured, keeping original answer order")
        return None

    # Case 2: "AUTO" → Generate random seed for this RUN
    if seed_config == "AUTO":
        auto_seed = random.randint(0, 2**31 - 1)
        logger.info(f"AUTO seed generated: {auto_seed}")
        return auto_seed

    # Case 3: int → Use provided seed
    if isinstance(seed_config, int):
        logger.info(f"Using fixed seed: {seed_config}")
        return seed_config

    # Fallback: try to convert to int
    try:
        seed_int = int(seed_config)
        logger.info(f"Using seed from string: {seed_int}")
        return seed_int
    except (ValueError, TypeError):
        logger.warning(f"Invalid seed value: {seed_config}, using None")
        return None
```

### 2. Atualização do método `update_run_status()`

**Arquivo:** `src/core/run_manager.py`

Adicionado lógica para setar `finished_at` automaticamente:

```python
run.status = status

# Set finished_at when completing or failing a run
if status in ("completed", "failed") and run.finished_at is None:
    run.finished_at = datetime.now()
    logger.debug(f"Run {run_id} finished_at set to {run.finished_at}")

self._run_repository.update(run)
```

**Comportamento:**
- `status='running'` → `finished_at` permanece `NULL`
- `status='completed'` → `finished_at = datetime.now()`
- `status='failed'` → `finished_at = datetime.now()`
- Se `finished_at` já existe → **NÃO** sobrescreve (preserva original)

## Arquivos Modificados

| Arquivo | Mudanças |
|---------|----------|
| `src/core/run_manager.py` | - Adicionado `import random`<br>- Criado método `_determine_seed()`<br>- Atualizado `initialize_run()` para usar `_determine_seed()`<br>- Atualizado `update_run_status()` para setar `finished_at` |
| `tests/test_seed_finished_at_fix.py` | - Criados 10 testes unitários para validar as correções |

## Como Usar

### 1. Manter ordem original (sem seed)

```bash
# Via CLI (sem parâmetro seed)
python -m src.main --models openai/gpt-4 --iterations 1

# Ou via .env (vazio)
RANDOM_SEED=
```

**Resultado no banco:** `seed = NULL`

### 2. Seed aleatório por RUN

```bash
# Via .env
RANDOM_SEED=AUTO

python -m src.main --models openai/gpt-4 --iterations 1
```

**Resultado no banco:** `seed = <inteiro aleatório>` (ex: `848762521`)

### 3. Seed fixo (reprodutibilidade)

```bash
# Via CLI
python -m src.main --models openai/gpt-4 --iterations 1 --seed 123

# Ou via .env
RANDOM_SEED=123
```

**Resultado no banco:** `seed = 123`

## Testes

Todos os testes foram aprovados:

```bash
pytest tests/test_seed_finished_at_fix.py -v

# Resultado:
# 10 passed in 0.49s
```

### Casos de Teste

1. ✅ `seed=None` → retorna `None`
2. ✅ `seed=""` → retorna `None`
3. ✅ `seed="AUTO"` → gera inteiro aleatório
4. ✅ `seed=123` → retorna `123`
5. ✅ `seed="456"` → converte e retorna `456`
6. ✅ `seed="invalid"` → retorna `None` (fallback seguro)
7. ✅ `status='completed'` → seta `finished_at`
8. ✅ `status='failed'` → seta `finished_at`
9. ✅ `status='running'` → NÃO seta `finished_at`
10. ✅ `finished_at` existente → NÃO sobrescreve

## Benefícios

1. **Reprodutibilidade:** Seeds fixos permitem reproduzir exatamente a mesma sequência de randomização
2. **Flexibilidade:** Seed `AUTO` gera um seed diferente para cada RUN automaticamente
3. **Controle:** Seed `None` mantém a ordem original das respostas (sem randomização)
4. **Auditoria:** `finished_at` permite saber quando cada run foi completada
5. **Métricas:** Permite calcular duração das runs (`finished_at - started_at`)
6. **Debug:** Facilita identificar runs travados (status `running` por muito tempo)

## Compatibilidade

- ✅ **Backward compatible:** Runs antigas com `seed=NULL` continuam funcionando
- ✅ **Não quebra existing code:** A lógica é aditiva, não altera comportamento existente
- ✅ **Fallback seguro:** Valores inválidos de seed retornam `None` ao invés de causar erro

## Próximos Passos (Opcional)

1. Executar benchmark real para validar em produção
2. Verificar se todas as runs novas estão com `seed` e `finished_at` preenchidos
3. Adicionar validação no `.env` para `RANDOM_SEED` (opcional)
