# name: "cli.md"
# version: 1.0
# Atenção!: nunca fazer alterações

---

# ✅ Decisão sobre `--add-questions` (fechada)

Você está **100% certo** em simplificar para:

```bash
EXE --experiment exp1 --add-questions 1-10
EXE --experiment exp1 --add-questions q11,q12,q13
```

### Por que isso é bom
- Zero flags extras
- Sem ambiguidade
- Fácil de digitar
- Fácil de documentar
- Fácil de implementar
- Fácil de explicar

📌 Regra clara:
- Se o argumento for numérico → intervalo
- Se for texto → IDs
- Se não passar nada → todas do arquivo padrão

### Fonte do arquivo
- Se passar arquivo explicitamente → usa ele
- Se não passar → usa o arquivo do `.env`
- Depois do snapshot → o arquivo **não importa mais**

👉 **Modelo aprovado. Não mudaria nada aqui.**

---

# 🚀 Agora sim: CONTRATO INTERNO DE TODOS OS COMANDOS

Vou dividir em três níveis, como você pediu:

1️⃣ CLI (o que o usuário digita)  
2️⃣ Service (regra de negócio)  
3️⃣ Repository (persistência)

---

## 1️⃣ EXPERIMENTOS

### CLI
```bash
EXE --create-experiment <name>
```

### Service
```python
create_experiment(
    name: str,
    description: Optional[str],
    defaults: dict,
    prompt_templates: dict
) -> Experiment
```

### Repository
```python
insert_experiment(experiment: Experiment)
get_experiment_by_name(name: str) -> Experiment
list_experiments() -> list[Experiment]
delete_experiment(name: str)
```

📌 `delete_experiment`:
- só permitido se **não houver runs**
- ou exige `--force`

---

## 2️⃣ MODELOS (VARIANTES)

### CLI
```bash
EXE --experiment <exp> --add-model <model_id>
```

### Service
```python
add_model_variant(
    experiment_id: str,
    model_id: str,
    overrides: dict
) -> ModelVariant
```

📌 Cria:
- variant_signature
- variant_id
- **não executa nada**

### Repository
```python
insert_model_variant(variant: ModelVariant)
list_model_variants(experiment_id: str)
get_model_variant(variant_id: str)
disable_model_variant(variant_id: str)
```

📌 `remove-model`:
- **não apaga respostas**
- apenas impede novos runs

---

## 3️⃣ PERGUNTAS / SNAPSHOTS

### CLI
```bash
EXE --experiment <exp> --add-questions [selection]
```

### Service
```python
add_question_snapshots(
    experiment_id: str,
    selection: Optional[str],
    source_file: Path
) -> AddQuestionsResult
```

### Repository
```python
insert_question_snapshot(snapshot: QuestionSnapshot)
list_question_snapshots(experiment_id: str)
snapshot_exists(experiment_id: str, question_id: str) -> bool
```

📌 Idempotente por design  
📌 Nunca remove snapshots automaticamente

---

## 4️⃣ RUNS

### CLI
```bash
EXE --experiment <exp> --create-run <run_name>
```

### Service
```python
create_run(
    experiment_id: str,
    run_name: str,
    seed: int,
    prompt_overrides: dict
) -> Run
```

### Repository
```python
insert_run(run: Run)
list_runs(experiment_id: str)
get_run(run_id: str)
update_run_status(run_id: str, status: str)
```

---

## 5️⃣ EXECUÇÃO DO RUN

### CLI
```bash
EXE --experiment <exp> --run <run_name> --execute
```

### Service
```python
execute_run(run_id: str)
```

Internamente:
- gera ExecutionPlan
- resolve hierarquia de config
- grava responses
- grava errors
- atualiza status do run

📌 **Execução nunca cria entidades.**

---

## 6️⃣ RESULTADOS

### CLI
```bash
EXE --experiment <exp> --run <run_name>
```

### Service
```python
get_run_results(run_id: str) -> RunResults
```

### Repository
```python
list_responses(run_id: str)
list_errors(run_id: str)
```

---

# 🧠 CLI → SERVICE → REPOSITORY (resumo visual)

```text
CLI
 ↓
Service (regras, validações, identidade)
 ↓
Repository (SQL puro, sem lógica)
 ↓
Database
```

📌 Nenhuma regra de negócio no Repository  
📌 Nenhuma SQL no Service  
📌 CLI só orquestra

---

# 🧹 Agora: REVISÃO DO TODO (o que ficou para trás)

Você sentiu certo. Eis o que ainda falta fechar:

### 🔲 Pendências reais
- Definir `ExecutionPlan` formalmente
- Definir `ResultWriter`
- Revisar `repository.py` para alinhar com TO‑BE
- Criar DTOs em `models.py`
- Atualizar docstrings e README
- Remover código morto (dev mode, immediate run)

### 🔲 Pendências opcionais
- `--dry-run`
- `--force`
- Exportação de resultados
- Visualização simples

---

# 🏁 Conclusão honesta

Você está **no ponto perfeito** para começar a codar:

- Banco fechado
- CLI racional
- Contratos claros
- Escopo controlado
- Sem atalhos perigosos

---