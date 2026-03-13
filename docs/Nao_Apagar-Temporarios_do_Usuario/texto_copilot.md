Amigo, ele terminou a implementação. Antes de mais nada, abaixo está a mensagem de conclusão da IA:
"""
## Resumo da Implementação

Todas as mudanças metodológicas foram implementadas com sucesso. Aqui está o resumo:

### ✅ O que foi implementado:

#### 1. **Separação de Protocolo e Variantes de Modelo** (`src/utils/config.py`)

- **`get_protocol_config()`**: Novo método que retorna apenas as configurações de protocolo congeladas:
  - `default_prompt`
  - `use_structured_outputs`
  - `random_seed_policy`

- **`get_config_hash()`**: Agora usa apenas o protocolo para calcular o hash
  - Variantes de modelo (temperature, reasoning, vision) **NÃO** afetam o hash
  - Permite comparar variantes dentro do mesmo experimento

- **`get_config_dict()`**: Estruturado com comentários claros:
  - Protocolo (usado no hash)
  - Metadados (informativo, não afeta hash)
  - Variantes de Modelo (podem variar por run)

#### 2. **Respeito a Variantes de Modelo no Conflito** (`src/core/run_manager.py`)

- **`_get_or_create_experiment()`**: Agora apenas configurações de **protocolo** são sobrescritas
  - `default_prompt`, `use_structured_outputs`, `random_seed_policy` → sobrescritos
  - `model_temperature`, `reasoning_effort`, `enable_vision` → **preservados**

#### 3. **Geração de Seed Único por RUN** (`src/core/run_manager.py`)

- **`_determine_seed()`**: Implementa precedência clara:
  1. CLI `--seed` explícito → usa seed fixo
  2. `RANDOM_SEED=AUTO` no .env → gera seed único por RUN
  3. `RANDOM_SEED=<int>` no .env → usa seed fixo
  4. Nenhum seed → mantém ordem original (None)

#### 4. **Configurações em Branco no `.env`**

- `MODEL_MAX_TOKENS=` (vazio)
- `MODEL_TEMPERATURE=` (vazio)
- `REASONING_EFFORT=` (vazio)
- Todos parâmetros de modelo e reasoning agora são vazios
- Comentário claro: "Blank = do not send parameter; use server default"

#### 5. **Documentação em `docs/SCHEMA.md`**

Nova seção "**Política de Configurações**" com:
- Configurações em Branco
- Congelamento por Experimento
- Question Snapshots como Fonte da Verdade
- Conflito de Configurações

### ✅ Validação

Todos os testes de validação passaram:
- ✓ `get_protocol_config()` retorna apenas 3 chaves corretas
- ✓ Hash é estável mesmo mudando temperature, reasoning, vision
- ✓ `get_config_dict()` tem todos os 22 campos
- ✓ Valores em branco no .env são convertidos para None

### 📋 Nota sobre Testes Existentes

Alguns testes existentes falharam porque:
1. **`test_initialize_run_stores_configuration`**: Esperava `seed=None`, mas agora `RANDOM_SEED=AUTO` gera seed por run (comportamento **correto** após mudanças)
2. **Testes com `question_text`**: Usam nome antigo do campo (`stem` é o correto)
3. **Testes sem `experiment_id`**: Agora é obrigatório (exigência metodológica)

Estas falhas são **esperadas** e refletem as mudanças comportamentais intencionais.
"""

Agora eu estou fazendo uma analise geral, e já percebi algumas coisas que, ou já estavam erradas antes, ou ficaram agora, e talvez seja necessário pedir um reajuste.
Eu fiz um teste simples, com apenas uma pergunta em um experimente novo, e estou analisando os dados.
Vou primeiro listar as tabelas e as colunas que eu tenha alguma dúvida.

## Tabelas:

### Tabela: "experiments"

#### Coluna: "experiment_id"
Minha dúvida começa na primeira coluna, experiment_id. Os ids são nomes como "exp-01d50ba3" ou "exp-d2ce6b2b". Você sabe se existe algum bom motivo para ser assim, e não simplesmente exp-1, exp-2, exp-3 etc.?

#### Coluna: "config_json"
Eu acredito que essa seja a coluna onde ele anota as configs que são congeladas no experimento, será que isso?
Porém, olhe os dados:
´´´
{"default_iterations": 1, "default_prompt": "Digite APENAS a LETRA da resposta correta (A, B, C, D):", "enable_vision": true, "execution_mode": "experiment", "experiment_name": "teste_gemini_1", "model_max_tokens": 10000, "model_repeat_penalty": null, "model_temperature": null, "model_top_k": null, "model_top_p": null, "openrouter_base_url": "https://openrouter.ai/api/v1", "openrouter_debug_enabled": true, "questionnaire_path": "data\\enamed_questions.json", "random_seed": "AUTO", "random_seed_policy": "AUTO", "reasoning_effort": null, "reasoning_enabled": null, "reasoning_exclude": null, "reasoning_max_tokens": null, "system_prompt": null, "use_structured_outputs": false, "user_prompt_template": null}
´´´
Muitas fazem sentido, mas muitas eu não vejo motivo de estar aqui.
- Entre elas: "experiment_name", "default_prompt" e "system_prompt". Motivo: Nessa tabela temos as colunas "name", "system_prompt" e "user_prompt_template". Aliás, a user prompt está vazia, o que acho que é um bug.
- "execution_mode", "openrouter_base_url", "openrouter_debug_enabled" e "questionnaire_path" são configurações do sistema. Não vejo motivo para estar aqui.
- Configs que decidimos que não precisam ser salvas: "enable_vision", "reasoning_enabled", "reasoning_max_tokens", entre outras.
- Por fim vi que temos "random_seed" e "random_seed_policy", me parece ser um erro, talvez no código nós temos os dois, o que seria mais grave ainda.

E aqui fica a dúvida. A coluna "config_json" deve ter todos os dados, mesmo os que não serão congelados? Ou só os que serão congelados? Se forem todos, não pode complicar o código? Ou é irrelevante?

#### Coluna: "config_hash"
Essa eu não entendi o que é. Ela tem números como "025ad8f66e74d81c" e "012c05164da28f80"

#### Colunas: "system_prompt" e "user_prompt_template"
As duas estão com NULL.
System prompt eu realmente não tenho configurado. Agora se "user_prompt_template", foi o prompt que eu configuro, para responder as perguntas, ele está errado, porque está NULL. O que provavelmente mereceria uma checagem nos dois.

---

### Tabela: "models"

#### Colunas: "model_id" e "model_name"
Nessas duas colunas, no ultimo teste por exemplo, tivemos os seguintes dados: "google/gemini-3.1-flash-lite-preview", que é o nome que eu preencho no campo do modelo na API, e "gemini-3.1-flash-lite-preview", que o nome do modelo sozinho.
Mas fiquei me perguntando, nessa tabela já deveria entrar em alguma coluna o nome composto do nome do modelo + reasoning e/ou vision?

#### Coluna: "supports_multimodal"
Essa coluna merece uma investigação. Eu não sei exatamente o que ela representa. Mas, ela esta com o valor 0, o que eu entendo como "não". Porém, o teste estava configurado para aceitar imagem. E esse modelo aceita imagem. Ou seja, ele é multimodal, certo? Ou será que essa coluna representa outra coisa?

#### Coluna: "metadata-json"
Não sei o que é essa coluna, todas as linhas estão NULL.

---

### Tabela: "runs"

#### Coluna: "run_id"
A mesma questão do ID do "experiments". Nomes estranhos, como "run-20260312194518-1228175f" e "run-20260312232821-246a9d3c".

#### Coluna: "seed"
O seed está corretamente representado nessa coluna, porém, ainda acredito que tenha algum problema.
- Eu fiz dois testes
- Respostas do 1: A) espironolactona. B) clortalidona. C) hidralazina. D) clonidina.
- Respostas do 2: A) clonidina. B) hidralazina. C) espironolactona. D) clortalidona.

Porém no log eu encontro informações que se contradizem:
- 2026-03-13 00:11:30 - INFO - src.main - Seed : None
- 2026-03-13 00:11:30 - INFO - src.core.run_manager - AUTO seed generated for this run: 1105835674
- 2026-03-13 00:11:31 - INFO - src.main - Using AUTO seed 517506204 (from run_id hash)
- 2026-03-13 00:11:31 - INFO - src.core.randomizer - AnswerRandomizer initialized with seed 517506204

Claramente tem algo errado no código.

#### Coluna: "