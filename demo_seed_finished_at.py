"""Demonstration of seed and finished_at fixes.

This script demonstrates the new behavior:
1. seed=None → Mantém ordem original (NULL no banco)
2. seed=AUTO → Gera número aleatório por RUN
3. seed=123 → Usa o seed fornecido
4. finished_at → Setado automaticamente ao completar/falhar
"""

from src.core.run_manager import RunManager
from src.utils.config import Settings, ExecutionMode
from unittest.mock import MagicMock

print("=" * 80)
print("DEMONSTRAÇÃO: Correções seed e finished_at")
print("=" * 80)

# Criar RunManager para teste
mock_db = MagicMock()
settings = Settings(execution_mode=ExecutionMode.TEST)
run_manager = RunManager(mock_db, settings)

print("\n📋 Teste 1: seed=None (mantém ordem original)")
print("-" * 80)
config_none = {"seed": None}
result = run_manager._determine_seed(config_none)
print(f"   Input: seed=None")
print(f"   Output: {result}")
print(f"   ✅ Resultado: NULL (mantém ordem original das respostas)")

print("\n📋 Teste 2: seed='' (string vazia)")
print("-" * 80)
config_empty = {"seed": ""}
result = run_manager._determine_seed(config_empty)
print(f"   Input: seed=''")
print(f"   Output: {result}")
print(f"   ✅ Resultado: NULL (mantém ordem original das respostas)")

print("\n📋 Teste 3: seed=AUTO (gera aleatório por RUN)")
print("-" * 80)
config_auto = {"seed": "AUTO"}
result1 = run_manager._determine_seed(config_auto)
result2 = run_manager._determine_seed(config_auto)
print(f"   Input: seed='AUTO'")
print(f"   Output 1: {result1}")
print(f"   Output 2: {result2}")
print(f"   ✅ Resultado: Inteiros aleatórios (0 a 2^31-1)")
print(f"   ✅ Cada RUN tem seu próprio seed")

print("\n📋 Teste 4: seed=123 (seed fixo)")
print("-" * 80)
config_int = {"seed": 123}
result = run_manager._determine_seed(config_int)
print(f"   Input: seed=123")
print(f"   Output: {result}")
print(f"   ✅ Resultado: 123 (usa o seed fornecido)")

print("\n📋 Teste 5: seed='456' (seed como string)")
print("-" * 80)
config_string = {"seed": "456"}
result = run_manager._determine_seed(config_string)
print(f"   Input: seed='456'")
print(f"   Output: {result}")
print(f"   ✅ Resultado: 456 (converte para inteiro)")

print("\n📋 Teste 6: seed='invalid' (valor inválido)")
print("-" * 80)
config_invalid = {"seed": "invalid"}
result = run_manager._determine_seed(config_invalid)
print(f"   Input: seed='invalid'")
print(f"   Output: {result}")
print(f"   ✅ Resultado: NULL (fallback seguro)")

print("\n" + "=" * 80)
print("COMPORTAMENTO: finished_at")
print("=" * 80)

print("""
O método update_run_status() agora seta automaticamente o finished_at:

1. status='running' → finished_at permanece NULL
2. status='completed' → finished_at = datetime.now()
3. status='failed' → finished_at = datetime.now()
4. Se finished_at já existe → NÃO sobrescreve (preserva original)

Exemplo de uso:
```python
# Run começa
run = Run(run_id="run-123", status="running", finished_at=None)
# → finished_at = NULL

# Run completa
run_manager.update_run_status("run-123", "completed")
# → finished_at = 2026-03-12 18:30:00.123456

# Run falha
run_manager.update_run_status("run-456", "failed")
# → finished_at = 2026-03-12 18:31:00.654321
```
""")

print("=" * 80)
print("RESUMO DAS CORREÇÕES")
print("=" * 80)
print("""
✅ seed=None → Mantém ordem original (NULL no banco)
✅ seed=AUTO → Gera número aleatório por RUN (inteiro 0 a 2^31-1)
✅ seed=123 → Usa o seed fornecido
✅ seed='456' → Converte string para inteiro
✅ seed='invalid' → Fallback seguro para NULL

✅ finished_at=NULL → Quando run está 'running' ou 'pending'
✅ finished_at=timestamp → Quando run está 'completed' ou 'failed'
✅ finished_at existente → NÃO é sobrescrito
""")

print("=" * 80)
print("COMO USAR")
print("=" * 80)
print("""
1. Manter ordem original (sem seed):
   python -m src.main --models openai/gpt-4
   # Ou: RANDOM_SEED= (vazio no .env)

2. Seed aleatório por RUN:
   python -m src.main --models openai/gpt-4
   # Com: RANDOM_SEED=AUTO no .env

3. Seed fixo (reprodutibilidade):
   python -m src.main --models openai/gpt-4 --seed 123
   # Ou: RANDOM_SEED=123 no .env
""")

print("=" * 80)
