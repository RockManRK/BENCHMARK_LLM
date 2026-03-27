# name: "configuration_violations.md"
# date: 24/03/2026
# version: 1.0
# Atenção!: nunca fazer alterações

---

# 📕 Configuration Contract Violations  
**Benchmark LLM CLI**

Este documento lista **todas as violações conhecidas** do  
`configuration_resolution_contract.md`.

Cada item abaixo descreve:
- o comportamento atual do sistema
- o comportamento esperado segundo o contrato
- os arquivos e funções envolvidos
- a natureza exata da violação

Este documento é **normativo**:  
qualquer correção deve alinhar o código **explicitamente** ao contrato.

---

## 🔴 V1 — `created_at` NULL em múltiplas tabelas

**Tabelas afetadas**
- `experiments`
- `runs`
- `model_variants`
- `question_snapshots`

**Arquivos**
- `src/repositories/experiment_repository.py`
- `src/repositories/run_repository.py`
- `src/repositories/model_variant_repository.py`
- `src/repositories/question_snapshot_repository.py`

**Comportamento atual**
- A coluna `created_at` é persistida como `NULL`

**Comportamento esperado**
- `created_at` deve ser preenchido automaticamente pelo banco de dados
- O código **não deve** passar `created_at` explicitamente no insert

**Violação do contrato**
- Entidades devem ser fotografias auditáveis no tempo
- O momento de criação é parte essencial da identidade da entidade

**Causa provável**
- O repository passa `None`, sobrescrevendo o `DEFAULT CURRENT_TIMESTAMP` do schema

---

## 🔴 V2 — Seed `AUTO` resolvido prematuramente no experimento

**Arquivo**
- `src/core/config_resolver.py`

**Função**
- Resolução de seed durante criação do experimento

**Comportamento atual**
- `AUTO` é convertido em valor numérico no experimento
- RUN herda um número fixo

**Comportamento esperado**
- Experimento deve persistir `"AUTO"`
- A resolução numérica deve ocorrer **apenas no RUN**
- Cada RUN resolve seu próprio valor quando necessário

**Violação do contrato**
- `RUN_RESPONSES_SEED` deve ser resolvido somente em `RUN_CREATION`

---

## 🔴 V3 — `model_variants.config` incompleto ou `{}`

**Arquivos**
- `src/cli/bcllm_model.py`
- `src/core/config_resolver.py`

**Comportamento atual**
- Apenas flags explicitamente passadas são salvas
- Defaults do experimento e `.env` são ignorados
- `config` pode ser `{}`

**Comportamento esperado**
- Todas as configurações de escopo MODEL devem ser resolvidas
- Todas devem ser persistidas, mesmo como `NULL`
- `{}` nunca é um estado válido

**Violação do contrato**
- Configuração de modelo deve ser completa e capturada no momento da criação

---

## 🔴 V4 — `.env` ignorado na criação de `model_variant`

**Arquivo**
- `src/cli/bcllm_model.py`

**Comportamento atual**
- `.env` não é usado como fonte inicial
- Configuração não herda valores do experimento

**Comportamento esperado**
- `.env → experiment → model_variant`
- Toda resolução deve seguir a ordem definida no contrato

**Violação do contrato**
- `.env` é fonte inicial obrigatória na criação de entidades

---

## 🔴 V5 — `question_snapshots.question_id` usa ID do dataset (`Q***`)

**Arquivo**
- `src/core/question_snapshot.py`

**Comportamento atual**
- `question_id` recebe valores como `Q001`, `Q002`

**Comportamento esperado**
- Snapshot deve possuir ID próprio
- ID do dataset deve existir apenas como referência externa
- Usuário não deve interagir com `Q***`

**Violação do contrato**
- Identidade interna ≠ referência de origem

---

## 🟠 V6 — Prompt `None` enviado para API

**Arquivo**
- `src/core/execution_engine.py`

**Comportamento atual**
```json
{"role": "system", "content": null}
```

**Comportamento esperado**
- Mensagens com conteúdo `NULL` não devem ser enviadas

**Violação do contrato**
- `NULL` significa “não enviar”

---

## 🟠 V7 — Questões inexistentes aceitas silenciosamente

**Arquivo**
- `src/core/question_loader.py`

**Comportamento atual**
- Perguntas inexistentes são aceitas
- Snapshot pode ficar inconsistente

**Comportamento esperado**
- Falha explícita
- Erro claro para o usuário

**Violação do contrato**
- Snapshot deve ser consistente e válido

---

## 🟠 V8 — `variant_signature` com default hardcoded

**Arquivo**
- `src/utils/variant_signature.py`

**Comportamento atual**
- Caminho de dataset hardcoded

**Comportamento esperado**
- Resolução via contrato de configuração
- Nenhum default oculto

**Violação do contrato**
- Nenhuma configuração pode ser inferida fora do contrato

---

## 🟠 V9 — Testes sem validação real

**Arquivos**
- `tests/validation/checkpoint_e_workflows.py`

**Problemas**
- Testes interativos sem assertion
- Casos documentados mas não validados

**Violação do contrato**
- Comportamento documentado deve ser validado

---

## 🟠 V10 — Docstrings e código divergentes

**Arquivos**
- `src/core/planner.py`

**Comportamento atual**
- Docstring afirma que RUN não possui prompts

**Comportamento esperado**
- Documentação deve refletir o schema real

**Violação do contrato**
- Código e documentação devem estar alinhados

---

## 🟠 V11 — Ausência de teste para `.env` sem chaves de prompt

**Arquivo**
- `tests/validation/checkpoint_a_workflows.py`

**Comportamento atual**
- Testa prompt vazio, mas não ausência total

**Comportamento esperado**
- Teste explícito para ausência completa

**Violação do contrato**
- `NULL` deve ser tratado corretamente

---

## 🧭 Observação Final

Este documento existe para garantir que:
- nenhuma correção seja parcial
- nenhuma regra seja inferida
- nenhuma configuração seja resolvida fora do contrato

Qualquer mudança futura deve:
1. Atualizar o contrato
2. Atualizar este documento
3. Atualizar o código