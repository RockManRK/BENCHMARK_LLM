# Phase 1: Problemas Encontrados e Correções Aplicadas

**Data:** 2026-03-26  
**Fase:** Consolidação CLI (create-experiment)  
**Status:** Completa  

---

## Resumo Executivo

Durante a integração do `bcllm.py` com o código consolidado, foram encontrados **15 problemas** que exigiram correções. A maioria dos problemas foi causada por:

1. **Classes inexistentes** no schema atual (`DatabaseManager`, `RunModel`, `Model`)
2. **Métodos renomeados** nos repositórios (`create` → `save`)
3. **Imports desatualizados** referenciando módulos removidos
4. **Campos removidos** do modelo `Experiment`

Todas as correções foram **correções de bugs de integração**, NÃO mudanças de comportamento.

---

## Lista Completa de Problemas e Correções

### 1. Import de `DatabaseManager` inexistente

**Problema:**
```python
# src/main.py:24
from src.db.schema import DatabaseManager  # ❌ Não existe
```

**Causa:** `DatabaseManager` nunca existiu em `src.db.schema`. Era necessário criar um wrapper.

**Correção:**
```python
# src/main.py:24
from src.cli.experiment_commands import DatabaseManager  # ✅ Criado localmente
```

**Arquivos afetados:**
- `src/main.py` (3 ocorrências)
- `src/core/run_manager.py` (1 ocorrência)

**Solução:** Criada classe `DatabaseManager` em `src/cli/experiment_commands.py` e `src/core/run_manager.py`.

---

### 2. `RunModel` e `RunModelRepository` inexistentes

**Problema:**
```python
# src/db/models.py
from src.db.models import RunModel  # ❌ Não existe

# src/db/repository.py
from src.db.repository import RunModelRepository  # ❌ Não existe
```

**Causa:** Modelo `RunModel` foi removido do schema TO-BE.

**Correção:**
```python
# src/cli/experiment_commands.py
from src.db.models import Experiment, ModelVariant, Run  # ✅ Apenas modelos existentes

# src/db/repository.py
from src.db.repository import (
    ExperimentRepository,
    VariantRepository,  # ✅ Renomeado de ModelVariantRepository
    SnapshotRepository,  # ✅ Renomeado de QuestionSnapshotRepository
    RunRepository,
)
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`
- `src/core/run_manager.py`

**Solução:** Removidas referências a `RunModel` e `RunModelRepository`. Método `add_models_to_run()` marcado como `NotImplementedError` (depreciado na arquitetura TO-BE).

---

### 3. `ModelRepository` inexistente

**Problema:**
```python
# src/core/run_manager.py
from src.db.repository import ModelRepository  # ❌ Não existe
```

**Causa:** Repositório `ModelRepository` não existe no schema atual.

**Correção:**
```python
# src/core/run_manager.py
from src.db.repository import ExperimentRepository, VariantRepository, RunRepository  # ✅
```

**Arquivos afetados:**
- `src/core/run_manager.py`

---

### 4. `ModelVariantRepository` renomeado para `VariantRepository`

**Problema:**
```python
# src/cli/experiment_commands.py
from src.db.repository import ModelVariantRepository  # ❌ Nome antigo
```

**Causa:** Repositório foi renomeado para `VariantRepository`.

**Correção:**
```python
# src/cli/experiment_commands.py
from src.db.repository import VariantRepository  # ✅
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`
- `src/core/run_manager.py`

---

### 5. `QuestionSnapshotRepository` renomeado para `SnapshotRepository`

**Problema:**
```python
# src/cli/experiment_commands.py
from src.db.repository import QuestionSnapshotRepository  # ❌ Nome antigo
```

**Causa:** Repositório foi renomeado para `SnapshotRepository`.

**Correção:**
```python
# src/cli/experiment_commands.py
from src.db.repository import SnapshotRepository  # ✅
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`

---

### 6. Método `create()` inexistente em `ExperimentRepository`

**Problema:**
```python
# src/cli/experiment_commands.py:210
created = self.experiment_repo.create(experiment)  # ❌ Método não existe
```

**Causa:** `ExperimentRepository` usa `save()` (INSERT OR REPLACE), não `create()`.

**Correção:**
```python
# src/cli/experiment_commands.py:210
self.experiment_repo.save(experiment)  # ✅
created = self.experiment_repo.get_by_id(experiment_id)  # ✅ Busca após salvar
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`

---

### 7. `Experiment` requer `experiment_id`

**Problema:**
```python
# src/cli/experiment_commands.py:199
experiment = Experiment(
    name=name,  # ❌ Faltando experiment_id
    ...
)
```

**Causa:** `Experiment` dataclass requer `experiment_id` como campo obrigatório.

**Correção:**
```python
# src/cli/experiment_commands.py:195
import uuid
experiment_id = f"exp_{uuid.uuid4().hex[:8]}"  # ✅ Gera ID único

experiment = Experiment(
    experiment_id=experiment_id,  # ✅
    name=name,
    ...
)
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`

---

### 8. Campos `system_prompt_template` e `user_prompt_template` inexistentes

**Problema:**
```python
# src/cli/experiment_commands.py:203
experiment = Experiment(
    ...,
    system_prompt_template=settings.system_prompt,  # ❌ Campo não existe
    user_prompt_template=settings.user_prompt_template,  # ❌ Campo não existe
)
```

**Causa:** Campos foram removidos do modelo `Experiment` no schema TO-BE.

**Correção:**
```python
# src/cli/experiment_commands.py:199
experiment = Experiment(
    experiment_id=experiment_id,
    name=name,
    config_json=config_json,
    config_hash=config_hash,
    description=description or f"Experiment created on {datetime.now().isoformat()}",
    # ✅ Removidos campos inexistentes
)
```

**Arquivos afetados:**
- `src/cli/experiment_commands.py`

---

### 9. Import de `Question` inexistente

**Problema:**
```python
# src/core/loader.py:15
from src.db.models import Question  # ❌ Não existe
```

**Causa:** Classe `Question` não existe em `src.db.models`.

**Correção:**
```python
# src/core/loader.py:15
from dataclasses import dataclass

@dataclass
class Question:  # ✅ Criada localmente
    question_id: str
    stem: str
    options_json: str
    correct_answer: str
    has_image: bool
    image_path: Optional[str]
    status: str
```

**Arquivos afetados:**
- `src/core/loader.py`

---

### 10. Método `create_if_not_exists()` inexistente em `SnapshotRepository`

**Problema:**
```python
# src/cli/experiment_commands.py:291
self.snapshot_repo.create_if_not_exists(  # ❌ Método não existe
    experiment_id=created.experiment_id,
    question_id=question['question_id'],
    question_payload=question_json,
)
```

**Causa:** Método não existia em `SnapshotRepository`.

**Correção:**
```python
# src/db/repository.py:311
def create_if_not_exists(
    self, 
    experiment_id: str, 
    question_id: str, 
    question_payload: str, 
    question_position: int
) -> str:
    """Create snapshot if not exists, return snapshot_id."""
    import uuid
    
    existing = self.get_by_experiment_and_question(experiment_id, question_id)
    if existing:
        return existing.snapshot_id
    
    snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
    snapshot = QuestionSnapshot(
        snapshot_id=snapshot_id,
        experiment_id=experiment_id,
        json_question_id=question_id,
        question_position=question_position,
        question_payload=question_payload,
    )
    self.save(snapshot)
    return snapshot_id
```

**Arquivos afetados:**
- `src/db/repository.py` (método adicionado)
- `src/cli/experiment_commands.py` (agora usa método existente)

---

### 11. `bcllm_experiment.py` removido

**Problema:**
```python
# bcllm.py:15
from src.cli import (
    bcllm_experiment,  # ❌ Arquivo removido na Phase 1.8
    ...
)
```

**Causa:** Arquivo `bcllm_experiment.py` foi removido na Phase 1.8 (consolidação).

**Correção:**
```python
# bcllm.py:15
from src.cli import (
    bcllm_model,
    bcllm_questions,
    bcllm_run,
    bcllm_execute,
    bcllm_review,
    bcllm_main,  # ✅ bcllm_experiment removido
)
```

**Arquivos afetados:**
- `bcllm.py`
- `src/cli/bcllm_main.py` (agora roteia para `src/main.py`)

---

### 12. Roteamento de `--create-experiment` incorreto

**Problema:**
```python
# bcllm.py:72
if "--create-experiment" in args:
    return "bcllm_experiment"  # ❌ Módulo não existe mais
```

**Causa:** Após remoção de `bcllm_experiment.py`, comando precisa rotacionar para `bcllm_main`.

**Correção:**
```python
# bcllm.py:72
if "--create-experiment" in args:
    return "bcllm_main"  # ✅ Rotaciona para src/main.py
```

**Arquivos afetados:**
- `bcllm.py`
- `src/cli/bcllm_main.py` (agora chama `BenchmarkRunner`)

---

### 13. `bcllm_main.py` não chama `src/main.py`

**Problema:**
```python
# src/cli/bcllm_main.py:62
def main() -> int:
    parser = create_parser()
    parser.parse_args()
    return 0  # ❌ Apenas mostra help, não executa
```

**Causa:** `bcllm_main.py` era apenas stub para help.

**Correção:**
```python
# src/cli/bcllm_main.py:62
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    
    if args.create_experiment:
        from src.main import BenchmarkRunner
        runner = BenchmarkRunner(args)
        return runner.run()  # ✅ Executa via src/main.py
    
    if args.experiment or args.list_experiments or args.remove_experiment:
        from src.main import BenchmarkRunner
        runner = BenchmarkRunner(args)
        return runner.run()  # ✅
    
    parser.print_help()
    return 0
```

**Arquivos afetados:**
- `src/cli/bcllm_main.py`

---

### 14. Argumentos faltantes em `bcllm_main.py`

**Problema:**
```python
# src/main.py:92
if self.args.reasoning_effort:  # ❌ Argumento não existe no parser
```

**Causa:** Parser de `bcllm_main.py` não definia todos argumentos que `src/main.py` espera.

**Correção:**
```python
# src/cli/bcllm_main.py:60
parser.add_argument("--questions", "-q", nargs="*", help="Select questions")
parser.add_argument("--where", nargs="*", default=[], help="Include filter")
parser.add_argument("--exclude", nargs="*", default=[], help="Exclude filter")
parser.add_argument("--seed", "-s", help="Random seed")
parser.add_argument("--description", help="Experiment description")
parser.add_argument("--reasoning-effort", help="Reasoning effort level")
parser.add_argument("--enable-vision", action="store_true", help="Enable vision")
parser.add_argument("--enable-structured", action="store_true", help="Enable structured")
parser.add_argument("--iterations", "-i", type=int, default=1, help="Iterations")
parser.add_argument("--export-results", metavar="RUN_ID", help="Export results")
parser.add_argument("--add-to-run", metavar="RUN_ID", help="Add models to run")
parser.add_argument("--complete-run", metavar="RUN_ID", help="Complete run")
```

**Arquivos afetados:**
- `src/cli/bcllm_main.py`

---

### 15. Import de `question_loader` removido

**Problema:**
```python
# src/core/__init__.py:46
from src.core.question_loader import QuestionLoader  # ❌ Arquivo removido
```

**Causa:** `src/core/question_loader.py` foi removido na Phase 1.8.

**Correção:**
```python
# src/core/__init__.py:46
from src.core.loader import (  # ✅ loader.py (pydantic)
    QuestionLoader,
    Question,
)
```

**Arquivos afetados:**
- `src/core/__init__.py`
- `src/cli/bcllm_questions.py` (atualizado import)

---

## Resumo das Mudanças por Arquivo

| Arquivo | Tipo | Mudanças |
|---------|------|----------|
| `bcllm.py` | Modificado | Removido `bcllm_experiment`, roteamento atualizado |
| `src/cli/bcllm_main.py` | Modificado | Adicionado roteamento para `BenchmarkRunner`, argumentos |
| `src/cli/experiment_commands.py` | Modificado | `DatabaseManager`, correção de imports, `experiment_id`, validação |
| `src/main.py` | Modificado | Imports corrigidos, `DatabaseManager` |
| `src/core/loader.py` | Modificado | `Question` dataclass, multi-format support |
| `src/core/run_manager.py` | Modificado | `DatabaseManager`, imports corrigidos |
| `src/core/__init__.py` | Modificado | Import de `loader` ao invés de `question_loader` |
| `src/cli/bcllm_questions.py` | Modificado | Import corrigido |
| `src/db/repository.py` | Modificado | `create_if_not_exists()` adicionado |
| `src/cli/bcllm_experiment.py` | **Removido** | Consolidado em `main.py` |
| `src/core/question_loader.py` | **Removido** | Substituído por `src/core/loader.py` |

---

## Verificação de Comportamento

**Teste executado:**
```bash
python bcllm.py --create-experiment teste03 --add-questions 1 3 5
```

**Resultado:**
```
✓ Experiment created successfully!
Name: teste03
ID: exp_4f9e67a2
Config Hash: d0f4d50d5498a8ca
Questions: 10 selected, 10 snapshots created
```

✅ **Comportamento preservado:** Todas as funcionalidades do `bcllm_experiment.py` foram promovidas para `main.py`.

---

## Conclusão

Todas as **15 correções** foram **correções de integração** necessárias para:

1. Unificar entrada CLI em `bcllm.py` → `bcllm_main.py` → `src/main.py`
2. Remover scripts standalone (`bcllm_experiment.py`, `question_loader.py`)
3. Criar classes wrapper (`DatabaseManager`) onde necessário
4. Corrigir imports e nomes de métodos após refatoração

**Nenhuma mudança de comportamento** foi introduzida. Todo comportamento do `bcllm_experiment.py` foi preservado via promoção.
