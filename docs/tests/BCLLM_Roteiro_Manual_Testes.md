# BCLLM CLI: Roteiro Manual de Testes

## Como usar

Execute os testes na ordem indicada. Para cada caso, registre o código de saída, a mensagem exibida, o estado do SQLite e eventuais logs. O banco pode ser consultado, mas nunca alterado diretamente.

**Resultados permitidos:** `NÃO TESTADO`, `APROVADO`, `PARCIAL`, `REPROVADO`, `BLOQUEADO`, `NÃO IMPLEMENTADO`.

## Valores a configurar

```text
<DATASET_VALIDO>    Dataset pequeno e conhecido
<DATASET_INVALIDO>  Arquivo ausente ou malformado
<URL_TESTE>         URL configurada para testes
<MODELO_BARATO>     Modelo externo de baixo custo
<MODELO_LOCAL>      Modelo local, se disponível
<PROVIDER_VALIDO>   Provider válido para o modelo
```

## Preparação

- Use banco e logs exclusivos para a rodada.
- Faça backup dos dados existentes.
- Registre commit, Python, sistema operacional, dataset e `.env` usados.
- Não registre chaves de API nas evidências.

---

# 1. Experimentos

### CE-001: criação mínima pelo `.env`
```bash
python bcllm.py --create-experiment manual_ce_001
```
Esperado: exit code 0; um experimento; `config_json` resolvido; `config_hash` presente; nenhum registro indevido.

**Resultado:** NÃO TESTADO

### CE-002: URL explícita vence o `.env`
```bash
python bcllm.py --create-experiment manual_ce_002 --url <URL_TESTE>
```
Verificar a URL persistida.

**Resultado:** NÃO TESTADO

### CE-003: URL ausente no CLI e no `.env`
```bash
python bcllm.py --create-experiment manual_ce_003
```
Esperado: erro; nenhum experimento parcial.

**Resultado:** NÃO TESTADO

### CE-004: nome duplicado
```bash
python bcllm.py --create-experiment manual_ce_001
```
Esperado: erro; registro original inalterado.

**Resultado:** NÃO TESTADO

### CE-005: seed inteira
```bash
python bcllm.py --create-experiment manual_ce_005 --seed 44
```

### CE-006: seed zero
```bash
python bcllm.py --create-experiment manual_ce_006 --seed 0
```
Verificar que `0` é preservado como seed válida.

### CE-007: seed AUTO
```bash
python bcllm.py --create-experiment manual_ce_007 --seed AUTO
```
Verificar que `AUTO` permanece no experimento.

### CE-008: seed system-default
Com seed definida no `.env`:
```bash
python bcllm.py --create-experiment manual_ce_008 --seed system-default
```
Verificar que o `.env` é ignorado e a randomização fica desativada.

### CE-009: prompts explícitos
```bash
python bcllm.py --create-experiment manual_ce_009 --system-prompt "System manual" --user-prompt "Responda: {question} {options}"
```

### CE-010: prompts system-default
Com prompts no `.env`:
```bash
python bcllm.py --create-experiment manual_ce_010 --system-prompt system-default --user-prompt system-default
```
Verificar que os prompts não serão enviados.

### CE-011: combinação representativa
```bash
python bcllm.py --create-experiment manual_ce_011 --url <URL_TESTE> --seed 51 --system-prompt "Sistema combinado" --user-prompt "Pergunta: {question} Opções: {options}" --provider-lock false
```

### CE-012: inspeção
```bash
python bcllm.py --experiment manual_ce_011
```
Esperado: mostrar configuração, modelos, Runs e números das perguntas, sem alterar o banco.

### CE-013: experimento inexistente
```bash
python bcllm.py --experiment experimento_que_nao_existe
```

---

# 2. Perguntas

### AQ-001: pergunta individual
```bash
python bcllm.py --experiment manual_ce_001 --add-questions 1
```

### AQ-002: lista
```bash
python bcllm.py --experiment manual_ce_001 --add-questions "2, 4, 6"
```

### AQ-003: intervalo
```bash
python bcllm.py --experiment manual_ce_002 --add-questions "1-5"
```

### AQ-004: seleção mista
```bash
python bcllm.py --experiment manual_ce_005 --add-questions "1, 3-5"
```

### AQ-005: todas as perguntas
```bash
python bcllm.py --experiment manual_ce_006 --add-questions
```

### AQ-006: filtro de inclusão
```bash
python bcllm.py --experiment manual_ce_007 --add-questions "1-20" --where status=valid
```

### AQ-007: filtro de exclusão
```bash
python bcllm.py --experiment manual_ce_008 --add-questions "1-20" --exclude has_image=true
```

### AQ-008: filtro sem resultados
```bash
python bcllm.py --experiment manual_ce_009 --add-questions "1-20" --where status=valor_inexistente
```
Registrar o comportamento atual e confirmar ausência de gravação parcial.

### AQ-009: pergunta inexistente
```bash
python bcllm.py --experiment manual_ce_009 --add-questions 999999
```

### AQ-010: formato inválido
```bash
python bcllm.py --experiment manual_ce_009 --add-questions "1--5"
```

### AQ-011: duplicidade
```bash
python bcllm.py --experiment manual_ce_001 --add-questions 1
```
Verificar que não há segundo snapshot indevido.

### AQ-012: dataset inválido em fluxo composto
```bash
python bcllm.py --create-experiment manual_aq_012 --data-set <DATASET_INVALIDO> --url <URL_TESTE> --add-questions 1
```
Esperado: nenhuma entidade parcial.

---

# 3. Variantes de modelos

Execute cada teste isoladamente, usando experimentos adequados quando configurações diferentes criarem variantes distintas.

### AM-001: modelo mínimo
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO>
```

### AM-002 a AM-010: parâmetros unitários
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --reasoning low
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --max-tokens 512
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --reasoning-tokens 256
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --temperature 0.5
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --top-p 0.8
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --top-k 20
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --repeat-penalty 1.1
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --vision true
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --structured true
```
Verificar campo persistido, herança dos demais e assinatura da variante.

### AM-011: URL específica
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_LOCAL> --url <URL_TESTE>
```

### AM-012: provider explícito
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --provider <PROVIDER_VALIDO>
```

### AM-013: system-default
```bash
python bcllm.py --experiment manual_ce_011 --add-model <MODELO_BARATO> --reasoning system-default --temperature system-default --vision system-default
```
Verificar interrupção da herança.

### AM-014: combinação representativa
```bash
python bcllm.py --experiment manual_ce_011 --add-model <MODELO_BARATO> --reasoning low --max-tokens 512 --temperature 0.2 --top-p 0.9 --top-k 20 --repeat-penalty 1.1 --vision false --structured false
```

### AM-015: distinção por repeat penalty
```bash
python bcllm.py --experiment manual_ce_005 --add-model <MODELO_BARATO> --repeat-penalty 1.0
python bcllm.py --experiment manual_ce_005 --add-model <MODELO_BARATO> --repeat-penalty 1.2
```
Esperado: duas variantes distintas.

### AM-016: variante idêntica duplicada
Repita exatamente um comando já aprovado. Verificar que não há duplicata.

### AM-017: limites inválidos
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --temperature 2.1
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --top-p 1.1
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --top-k -1
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --max-tokens 0
```
Cada comando deve falhar sem criar variante parcial.

### AM-018: flag duplicada
```bash
python bcllm.py --experiment manual_ce_002 --add-model <MODELO_BARATO> --vision true --vision false
```
Registrar aviso e valor persistido.

---

# 4. Runs

### RN-001: Run mínimo
```bash
python bcllm.py --experiment manual_ce_002 --add-run
```
Verificar status `pending`, herança e congelamento.

### RN-002: seed explícita
```bash
python bcllm.py --experiment manual_ce_005 --add-run --seed 77
```

### RN-003: seed zero
```bash
python bcllm.py --experiment manual_ce_005 --add-run --seed 0
```

### RN-004: AUTO herdido
```bash
python bcllm.py --experiment manual_ce_007 --add-run
```
Verificar resolução para inteiro e ausência de `AUTO` no Run.

### RN-005: system-default
```bash
python bcllm.py --experiment manual_ce_005 --add-run --seed system-default
```
Verificar que não herda seed `44`.

### RN-006: prompts explícitos
```bash
python bcllm.py --experiment manual_ce_009 --add-run --system-prompt "System do Run" --user-prompt "Run: {question} {options}"
```

### RN-007: prompts system-default
```bash
python bcllm.py --experiment manual_ce_009 --add-run --system-prompt system-default --user-prompt system-default
```

### RN-008: Runs diferentes
```bash
python bcllm.py --experiment manual_ce_011 --add-run --seed 10
python bcllm.py --experiment manual_ce_011 --add-run --seed 20
```

### RN-009: inspeção
```bash
python bcllm.py --experiment manual_ce_011 --run <RUN_ID>
```

### RN-010: experimento inexistente
```bash
python bcllm.py --experiment experimento_que_nao_existe --add-run
```

---

# 5. Providers

### PR-001: lock false
```bash
python bcllm.py --create-experiment manual_pr_001 --url <URL_TESTE> --provider-lock false --add-questions 1
```

### PR-002: lock true
```bash
python bcllm.py --create-experiment manual_pr_002 --url <URL_TESTE> --provider-lock true --add-questions 1
```

### PR-003: resolução
```bash
python bcllm.py --experiment manual_pr_002 --resolve-providers
```
Verificar persistência, variantes ignoradas e relatório.

### PR-004: lock com provider ausente
```bash
python bcllm.py --experiment manual_pr_002 --execute
```
Esperado: execução bloqueada antes de requisições.

### PR-005: provider inválido
```bash
python bcllm.py --experiment manual_pr_001 --add-model <MODELO_BARATO> --provider provider_inexistente
```
Registrar em qual etapa ocorre a validação.

---

# 6. Execução

Prepare um experimento pequeno com duas perguntas, uma variante e dois Runs.

### EX-001: pré-requisitos ausentes
```bash
python bcllm.py --experiment <EXPERIMENTO_INCOMPLETO> --execute
```
Executar separadamente sem perguntas, sem modelos e sem Runs.

### EX-002: execução mínima completa
```bash
python bcllm.py --experiment <EXPERIMENTO_PRONTO> --execute
```
Verificar uma resposta ou erro por item, proveniência completa e status dos Runs.

### EX-003 a EX-006: filtros
```bash
python bcllm.py --experiment <EXPERIMENTO_PRONTO> --execute --run <RUN_ID>
python bcllm.py --experiment <EXPERIMENTO_PRONTO> --execute --questions 1
python bcllm.py --experiment <EXPERIMENTO_PRONTO> --execute --models <VARIANT_ID>
python bcllm.py --experiment <EXPERIMENTO_PRONTO> --execute --run <RUN_ID> --questions 1 --models <VARIANT_ID>
```
Verificar exatamente o escopo selecionado.

### EX-007: repetição
Repita execução concluída. Verificar ausência de respostas duplicadas.

### EX-008: parcial e retomada
Execute uma pergunta e depois execute sem filtros. Verificar que somente o restante é processado.

### EX-009: seed system-default
Verificar `randomization_enabled=false`, seed nula e ordem original.

### EX-010: seed zero
Verificar randomização habilitada, seed `0` e apresentação reproduzível.

### EX-011: falha externa
Use configuração controladamente indisponível. Verificar erro auditável, preservação dos sucessos e ausência de segredos.

---

# 7. Contratos e banco

### CT-001: hash da configuração
Confirmar que `config_hash` corresponde ao `config_json` persistido.

### CT-002: `.env` após criação
Crie experimento, altere o `.env`, adicione variante e Run. Confirmar herança exclusiva do experimento congelado.

### CT-003: snapshot imutável
Adicione pergunta, altere o dataset e confirme que o snapshot existente não muda.

### CT-004: proveniência
Para uma resposta, confirme vínculos com Run, variante, snapshot, pergunta e experimento.

### CT-005: integridade referencial
Confirmar ausência de respostas e erros órfãos.

### CT-006: logs sem segredos
Pesquisar chaves, tokens e cabeçalhos de autenticação nos logs.

### CT-007: atomicidade de criação
Executar fluxo composto inválido e confirmar ausência de entidades parciais.

---

# 8. Reservado para expansão

Adicionar posteriormente:

- comandos `--list-*`;
- `--help`;
- exportação;
- revisão manual;
- relatórios, gráficos e analytics;
- validação avançada de URL;
- execução por mock;
- regressões de cada bug confirmado.

## Resumo da rodada

```text
Executados:
Aprovados:
Parciais:
Reprovados:
Bloqueados:
Não implementados:
Bugs críticos:
Bugs altos:
Bugs médios:
Bugs baixos:
```
