# BCLLM CLI: Especificação para Automação de Testes

## 1. Objetivo

Construir uma suíte automatizada baseada no roteiro manual do BCLLM. (docs\tests\BCLLM_Roteiro_Manual_Testes.md)
A suíte deve executar comandos, capturar evidências, consultar o SQLite, verificar contratos e gerar um relatório reproduzível.

Este documento não substitui os contratos nem decide comportamentos pendentes. Casos sem expectativa estável devem ser marcados como `PENDING_SPEC`.

## 2. Regras obrigatórias

1. Nunca alterar funcionalmente o SQLite fora do CLI.
2. É permitido criar e restaurar bancos de fixture antes dos testes.
3. Cada teste deve usar diretório, banco, `.env`, dataset e logs isolados.
4. Capturar comando, exit code, stdout, stderr, duração e exceções.
5. Capturar o estado relevante do banco antes e depois.
6. Não comparar respostas textuais de LLMs como se fossem determinísticas.
7. Comparar requisições, opções apresentadas, seed, IDs e persistência quando determinismo for exigido.
8. Mascarar chaves, tokens, URLs privadas e cabeçalhos de autenticação nos relatórios.
9. Um comando que falha durante criação não pode deixar registros parciais.
10. Execução incremental pode preservar resultados concluídos antes de uma falha.
11. Nenhuma diferença observada pode redefinir automaticamente a expectativa.
12. Todo bug corrigido deve receber um teste de regressão.

## 3. Estados

```text
PASS              Todas as verificações passaram
PARTIAL           Parte verificável passou, mas há limitação conhecida
FAIL              Uma ou mais expectativas falharam
BLOCKED           Dependência externa ou fixture impediu a execução
NOT_IMPLEMENTED   Comando ou comportamento ausente
PENDING_SPEC      Expectativa ainda não definida
SKIPPED           Caso deliberadamente não executado
ERROR             Falha da própria infraestrutura de testes
```

## 4. Estrutura de um caso

```yaml
id: CE-001
name: criar experimento mínimo
area: experiment
status: active
priority: critical
tags: [cli, sqlite, creation]

fixture:
  env: env_valid_minimal
  dataset: dataset_small_valid
  database: empty
  network: none

command:
  argv:
    - python
    - bcllm.py
    - --create-experiment
    - auto_ce_001

expect:
  exit_code: 0
  stdout_contains: []
  stderr_contains: []
  no_traceback: true

sqlite:
  assertions:
    - query: "SELECT COUNT(*) FROM experiments WHERE name = ?"
      params: [auto_ce_001]
      equals: 1
  unchanged_tables:
    - model_variants
    - question_snapshots
    - runs
    - responses
    - errors

artifacts:
  save_stdout: true
  save_stderr: true
  save_database_diff: true
  save_logs: true
```

A sintaxe é ilustrativa. A implementação pode usar Python, pytest, JSON ou YAML, desde que preserve os mesmos conceitos.

## 5. Fixtures mínimas

### Ambientes

- `env_valid_minimal`: dataset e URL válidos, demais opções vazias.
- `env_full`: todos os defaults configurados.
- `env_no_url`: sem URL.
- `env_seed_44`: seed 44.
- `env_prompts`: system e user prompts definidos.
- `env_provider_lock`: lock habilitado.
- `env_invalid_values`: valores deliberadamente inválidos.

### Datasets

- `dataset_small_valid`: conjunto pequeno com posições conhecidas.
- `dataset_filters`: contém múltiplos status e perguntas com e sem imagem.
- `dataset_missing_image`: declara imagem ausente.
- `dataset_invalid_json`: JSON malformado.
- `dataset_invalid_schema`: JSON válido com estrutura inválida.
- `dataset_empty`: vazio.
- `dataset_changed_v2`: versão modificada para testar snapshots.

### APIs

- `fake_api_success`: resposta previsível e campos de uso.
- `fake_api_ambiguous`: resposta que exige revisão.
- `fake_api_rate_limit`: falha recuperável.
- `fake_api_auth_error`: falha não recuperável.
- `fake_api_timeout`: timeout.
- `fake_api_partial`: sucessos e falhas misturados.
- `real_api_smoke`: modelo externo barato, executado opcionalmente.

Enquanto o mock não estiver pronto, marque os testes dependentes como `BLOCKED` ou execute-os no perfil `real_api_smoke`.

## 6. Perfis de execução

### `smoke`

Criação mínima, pergunta, modelo, Run, execução de um item e inspeção do banco.

### `cli-unit`

Todos os comandos e flags isolados, sem API real.

### `contracts`

Determinismo, idempotência, imutabilidade, hierarquia, system-default e auditabilidade.

### `integration-mock`

Fluxo completo usando API simulada.

### `integration-real`

Poucos casos com serviço real e orçamento controlado.

### `regression`

Bugs confirmados e corrigidos.

### `full`

Todos os perfis compatíveis com o ambiente.

## 7. Matriz automatizada de comandos

Todos os casos do roteiro manual devem ser importados. Acrescentar os grupos abaixo.

### Experimentos

- Criação com cada flag isolada.
- Três estados de flags herdáveis: omitida, explícita, `system-default`.
- Seed: `AUTO`, `0`, positiva, negativa, texto inválido.
- Prompts: vazio, texto simples, espaços, Unicode, placeholders, arquivo se suportado.
- URL: CLI, `.env`, ausente, override e formatos registrados como pendentes.
- Nome: duplicado, vazio, Unicode, espaços e caracteres especiais conforme especificação.
- Fluxo simples e fluxo composto válido ou inválido.
- Confirmação de que o `.env` posterior não afeta o experimento.

### Perguntas

- Individual, lista, intervalo, seleção mista e todas.
- Limites inferior e superior.
- Repetições e sobreposições no mesmo spec.
- Posições inexistentes.
- `where` e `exclude` isolados e em conjunto.
- Filtro sem resultado.
- Dataset ausente, vazio, inválido e estruturalmente incorreto.
- Snapshot idêntico após alteração do dataset.
- Pergunta que declara imagem inexistente.

### Modelos

Para cada parâmetro, testar:

- omitido;
- valor válido típico;
- mínimo;
- máximo, quando definido;
- abaixo do mínimo;
- acima do máximo;
- tipo inválido;
- `system-default`, quando permitido;
- duplicação da flag.

Parâmetros:

- reasoning;
- max-tokens;
- reasoning-tokens;
- temperature;
- top-p;
- top-k;
- repeat-penalty;
- vision;
- structured;
- URL;
- provider.

Testar ainda:

- mesma variante duplicada;
- mesmo modelo com apenas um parâmetro diferente;
- assinatura contendo todos os campos relevantes;
- normalização numérica sem colisões;
- herança do experimento;
- `system-default` interrompendo herança;
- URL da variante sem modificar o experimento.

### Runs

- Criação mínima.
- Seed herdada, explícita, `0`, `AUTO` e `system-default`.
- Prompts herdados, explícitos e `system-default`.
- Dois Runs equivalentes.
- Dois Runs com apenas uma diferença.
- Congelamento após criação.
- Inspeção por ID válido e inválido.
- Estado inicial e transições observadas.

### Providers

- Lock falso e verdadeiro.
- Variante com provider explícito.
- Variante sem provider.
- `system-default` para provider, se confirmado.
- Resolução com todas as estratégias documentadas.
- Variantes já resolvidas.
- Resolução parcial.
- Falha de rede e resposta inválida.
- Execução bloqueada com lock e provider ausente.
- Payload com provider fixado quando lock estiver ativo.

### Execução

- Falta de perguntas, modelos ou Runs.
- Escopo completo.
- Filtros individuais e combinados.
- IDs válidos e inválidos.
- Execução repetida.
- Execução parcial e retomada.
- Sucesso total, falha total e falha parcial.
- Retry recuperável e erro não recuperável.
- Execução sequencial e paralela.
- Escrita incremental.
- Estado final do Run.
- Contagem de itens planejados versus persistidos.
- Ausência de acesso direto do ExecutionEngine ao banco, quando verificável por teste de componente.

### Contratos

- Mesma configuração produz requests equivalentes.
- Seed `None` desativa randomização.
- Seed `0` ativa randomização.
- `AUTO` é resolvido somente na criação do Run.
- Respostas preservam opções apresentadas.
- Correção usa `correct_option_presented`.
- Nenhuma duplicata por Run, variante e snapshot.
- Snapshots e configurações congeladas não mudam.
- Respostas e erros possuem proveniência completa.
- Revisão não sobrescreve dados originais.
- Logs não contêm segredos.

## 8. Verificações padrão no SQLite

Criar helpers somente de leitura para:

- obter experimento por nome;
- decodificar JSON de configurações;
- recalcular hash;
- listar snapshots por experimento;
- listar variantes e Runs;
- contar respostas e erros por combinação;
- detectar duplicatas;
- detectar chaves estrangeiras órfãs;
- comparar estado antes e depois;
- validar timestamps e transições sem exigir valores exatos;
- verificar payloads de request e contexto de randomização.

Executar também:

```sql
PRAGMA foreign_key_check;
PRAGMA integrity_check;
```

## 9. Saídas e mensagens

Enquanto o texto do CLI não estiver estabilizado:

- exigir exit code correto;
- exigir ausência de traceback para erros esperados;
- procurar termos essenciais, não frases completas;
- salvar stdout e stderr integralmente;
- marcar como `PENDING_SPEC` qualquer mensagem ainda não definida.

Quando a interface for estabilizada, preferir uma saída estruturada, se o projeto decidir implementá-la.

## 10. Relatório

Gerar Markdown e JSON contendo:

- identificação do ambiente e commit;
- fixture utilizada;
- casos por estado;
- comando sanitizado;
- duração;
- stdout e stderr sanitizados;
- diferenças relevantes no banco;
- logs associados;
- falhas agrupadas por contrato ou área;
- casos bloqueados e motivo;
- regressões;
- cobertura por comando e por flag.

O relatório não deve conter credenciais ou dados sensíveis.

## 11. Extensão futura

Novos testes devem:

1. Receber ID estável.
2. Declarar fixture e dependências.
3. Ser independentes de ordem sempre que possível.
4. Declarar explicitamente alterações esperadas e proibidas.
5. Ser adicionados ao perfil apropriado.
6. Referenciar bug ou decisão quando forem regressões.
7. Evitar dependência de mensagens textuais instáveis.
8. Permanecer legíveis para execução humana.

## 12. Áreas reservadas

- comandos `--list-*`;
- `--help`;
- exportação;
- revisão manual;
- analytics e gráficos;
- validação avançada de URL;
- interface gráfica;
- migrações futuras do banco.
