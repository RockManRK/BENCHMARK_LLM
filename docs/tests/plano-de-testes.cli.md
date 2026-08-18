# BCLLM CLI: Plano de Testes

## INDICE

1. Propósito
2. Escopo atual
3. Fontes de verdade
4. Convenções e terminologia
5. Estados dos testes
6. Classificação dos resultados
7. Regras de execução
8. Fixtures
9. Modelo de caso de teste
10. Inventário do CLI
11. Criação e inspeção de experimentos
12. Adição de perguntas
13. Adição de modelos
14. Adição e inspeção de Runs
15. Execução
16. Providers
17. Revisão
18. Exportação
19. Logs e segurança
20. Contratos transversais
21. Funcionalidades planejadas
22. Decisões pendentes
23. Registro de bugs encontrados

---

## 1. Propósito

Este documento define o plano de testes manuais do CLI do BCLLM.

Seus objetivos são:

1. Verificar sistematicamente os comandos atualmente implementados.
2. Identificar comandos ausentes, incompletos ou parcialmente funcionais.
3. Detectar erros, regressões, inconsistências e alterações indevidas no banco de dados.
4. Verificar se os resultados apresentados pelo CLI correspondem aos dados persistidos.
5. Validar os contratos fundamentais do sistema, incluindo:
   - determinismo;
   - idempotência;
   - imutabilidade;
   - hierarquia de configurações;
   - semântica de `system-default`;
   - auditabilidade dos dados.
6. Registrar evidências e problemas encontrados durante a execução manual.
7. Criar um padrão claro para adicionar, revisar e atualizar testes.
8. Servir futuramente como especificação para a construção de uma suíte automatizada.

Este documento também funcionará como levantamento do estado real do CLI. Portanto, todos os casos começam com estado `NÃO TESTADO`, mesmo quando o comando é considerado implementado.

Um teste não deve ser considerado aprovado apenas porque o comando terminou sem apresentar uma exceção. Sua aprovação também depende da verificação do exit code, das mensagens apresentadas, dos registros persistidos e da ausência de efeitos colaterais indevidos.

---

## 2. Escopo

### 2.1 Escopo atual

A primeira versão deste plano cobre prioritariamente:

- criação e inspeção de experimentos;
- congelamento das configurações do experimento;
- adição e inspeção de perguntas;
- criação de snapshots de perguntas;
- adição e inspeção de variantes de modelos;
- herança das configurações do experimento;
- adição e inspeção de Runs;
- sobrescritas permitidas em Runs;
- execução completa e filtrada de experimentos;
- execução apenas de itens pendentes;
- resolução e bloqueio de providers;
- persistência de respostas e erros;
- integridade e auditabilidade do banco SQLite;
- idempotência;
- determinismo;
- tratamento de entradas inválidas;
- prevenção de gravações parciais;
- logs e proteção de informações sensíveis;
- regressões de bugs encontrados anteriormente.

### 2.2 Escopo parcial ou futuro

As seguintes áreas podem receber apenas testes básicos, marcadores ou casos ainda não executáveis:

- comandos de listagem ainda não implementados;
- exportação;
- revisão manual;
- ajuda por `--help`;
- relatórios;
- estatísticas;
- gráficos;
- analytics;
- interfaces pós-execução;
- validação avançada de URLs;
- execução completamente isolada por mock;
- funcionalidades ainda não definidas ou estabilizadas.

A ausência de implementação não representa automaticamente uma falha. O teste correspondente deve ser classificado como `NÃO IMPLEMENTADO`, `BLOQUEADO` ou `DECISÃO PENDENTE`, conforme o caso.

### 2.3 Fora do escopo atual

Não fazem parte do objetivo inicial:

- testar todas as combinações matematicamente possíveis de flags;
- avaliar a qualidade geral ou capacidade intelectual das LLMs;
- exigir respostas textuais determinísticas de serviços externos;
- implementar analytics completos;
- alterar diretamente dados do SQLite para simular operações normais;
- testar uma interface gráfica ainda não existente;
- permitir remoção de experimentos, modelos, perguntas ou Runs;
- definir funcionalidades futuras apenas para completar artificialmente a cobertura.

A cobertura inicial deve priorizar:

1. testes isolados dos comandos e parâmetros;
2. testes negativos das validações importantes;
3. estados especiais, herança e `system-default`;
4. combinações representativas baseadas em risco;
5. contratos fundamentais do sistema;
6. regressões de bugs efetivamente encontrados.

---

## 3. Fontes de verdade

As fontes devem ser consultadas na seguinte ordem.

### 3.1 Contratos normativos

Os documentos em `docs/contracts/` definem invariantes obrigatórios do sistema.

Exemplos:

- `determinism.md`;
- `idempotency.md`;
- `immutability.md`;
- `configuration-hierarchy.md`;
- `system-default-semantics.md`;
- `data-auditability.md`.

Quando um comportamento viola um contrato normativo, o teste deve registrar uma violação de contrato. A expectativa não deve ser alterada silenciosamente apenas para coincidir com o comportamento observado.

### 3.2 ADRs

Architecture Decision Records podem formalmente substituir ou esclarecer decisões arquiteturais anteriores.

Quando existir um ADR aplicável, ele deve ser considerado junto aos contratos.

### 3.3 Código-fonte

O código representa o comportamento atualmente implementado.

Quando documentação de referência e código divergirem, o código deve ser usado para determinar o estado atual da implementação, salvo quando isso representar violação de um contrato ou de um ADR.

Nessa situação, o teste deve registrar separadamente:

- comportamento documentado;
- comportamento implementado;
- comportamento observado;
- contrato possivelmente violado;
- decisão necessária.

### 3.4 Documentação de referência

Os documentos em `docs/reference/` descrevem a implementação conhecida, incluindo:

- comandos do CLI;
- configurações;
- esquema do banco;
- integração com APIs;
- organização dos módulos.

Esses documentos orientam a criação inicial dos testes, mas podem apresentar divergências ou desatualizações.

### 3.5 Documentação de status

Os documentos em `docs/status/` registram:

- funcionalidades implementadas;
- problemas conhecidos;
- limitações;
- trabalho planejado.

Eles ajudam a interpretar resultados, mas não substituem contratos, ADRs ou o comportamento real do código.

### 3.6 Documentos históricos e rascunhos

Documentos antigos, anotações exploratórias e rascunhos podem ser usados para localizar possíveis regressões e bugs anteriormente observados.

Eles não devem ser considerados especificações oficiais sem confirmação nas fontes superiores.

### 3.7 Resultados dos testes

Os resultados desta suíte são evidências do comportamento observado em determinada versão do sistema.

Um resultado observado não altera automaticamente a especificação. Divergências devem ser registradas para posterior decisão entre:

- corrigir o código;
- corrigir a documentação;
- atualizar o teste;
- criar ou atualizar um ADR;
- manter o item como decisão pendente.

---

## 4. Terminologia

### 4.1 CLI

Interface de linha de comando do BCLLM, acessada normalmente por:

```bash
python bcllm.py <argumentos>
```

----------------


## 4. Terminologia

### 4.1 CLI

Interface de linha de comando do BCLLM, acessada normalmente por:

```bash
python bcllm.py <argumentos>
```

4.2 Experimento

Entidade principal que define a intenção e o universo de um benchmark.

O experimento contém:

configuração congelada;
snapshots de perguntas;
variantes de modelos;
Runs.

Alterações posteriores no .env não podem afetar um experimento já criado.

O experimento pode crescer pela adição de perguntas, variantes e Runs, mas sua configuração congelada não deve ser modificada.

4.3 Variante de modelo

Configuração intencional de um modelo-base dentro de um experimento.

Duas variantes podem usar o mesmo model_id, desde que tenham configurações intencionalmente diferentes.

A configuração de uma variante é congelada quando ela é adicionada.

Neste documento, o termo modelo pode representar o nome usado pelo CLI. O termo variante de modelo representa a entidade persistida com uma configuração específica.

4.4 Snapshot de pergunta

Cópia imutável de uma pergunta adicionada ao experimento.

O snapshot preserva o conteúdo executável da pergunta no momento da adição. Mudanças posteriores no dataset original não devem modificar snapshots existentes.

4.5 Run

Instância configurada de execução pertencente a um experimento.

Um Run pode sobrescrever apenas as configurações permitidas, como seed e prompts. Quando não houver sobrescrita, ele herda os valores congelados do experimento.

A configuração do Run é congelada em sua criação.

O comando canônico para criação é:

--add-run


O comando antigo --create-run deve ser tratado como obsoleto, salvo se futuramente for mantido explicitamente como alias.

4.6 Execução

Ato de processar combinações pendentes de Runs, variantes e perguntas.

A execução é iniciada por:

--execute


Execução e Run não são sinônimos:

--add-run cria uma entidade Run;
--run <run_id> identifica ou filtra um Run;
--execute inicia o processamento.
4.7 Item de execução

Combinação específica de:

Run;
variante de modelo;
snapshot de pergunta.

Cada combinação deve ser processada no máximo uma vez como resultado persistido, respeitando o contrato de idempotência.

4.8 Item pendente

Item de execução para o qual ainda não existe resultado concluído e persistido.

Filtros de execução limitam o escopo da execução atual, mas não alteram permanentemente a composição do experimento ou do Run.

4.9 Execução parcial

Execução limitada por filtros de Run, pergunta ou variante, ou interrompida antes de concluir todos os itens aplicáveis.

Este conceito não deve ser confundido automaticamente com partial_failed. O estado exato do Run após uma execução parcial permanece sujeito à verificação da implementação e às decisões registradas neste documento.

4.10 Configuração congelada

Configuração persistida em uma entidade e que não pode ser modificada após sua criação.

Novas entidades podem herdar valores de uma entidade anterior, mas entidades já existentes não podem ser alteradas retroativamente.

4.11 Herança

Uso do valor configurado no nível imediatamente aplicável quando nenhum valor explícito foi fornecido no nível atual.

De forma simplificada:

Criação do experimento:
CLI → .env → padrão interno

Adição de variante:
CLI da variante → experimento → padrão interno

Adição de Run:
CLI do Run → experimento → padrão interno


Variantes e Runs não devem consultar novamente o .env.

4.12 system-default

Diretiva explícita que interrompe a herança e utiliza o comportamento interno do sistema para o parâmetro.

Para muitos parâmetros enviados à API, isso significa omitir o parâmetro da requisição.

Para seed:

system-default → None → randomização desativada


system-default não significa:

consultar o .env;
herdar do experimento;
usar a string literal "system-default";
utilizar a string literal "null".
4.13 URL

Endereço-base utilizado para conexão com o serviço de modelos.

Na criação do experimento, a resolução definida é:

URL explícita no CLI → URL do .env → erro


Não existe URL hard-coded como padrão interno.

Uma variante pode fornecer URL explícita própria. Caso contrário, herda a URL congelada do experimento.

system-default não é aceito para URL, pois não existe endereço interno universal que possa ser utilizado.

A validação avançada do formato da URL não faz parte do escopo inicial.

4.14 Fixture

Conjunto controlado de dados e configurações preparado para um ou mais testes.

Exemplos:

arquivo .env;
dataset de perguntas;
banco SQLite vazio;
experimento-base;
resposta simulada;
credenciais ou modelo externo de baixo custo.
4.15 Resultado esperado

Comportamento que deveria ocorrer segundo contratos, decisões vigentes e documentação aplicável.

4.16 Resultado observado

Comportamento efetivamente identificado durante a execução do teste.

4.17 Invariante negativa

Condição que expressa algo que não pode acontecer.

Exemplos:

não criar experimento parcial após erro;
não duplicar respostas;
não alterar snapshots existentes;
não consultar novamente o .env;
não registrar credenciais nos logs.
4.18 Regressão

Falha em um comportamento que anteriormente funcionava ou havia sido corrigido.

4.19 Banco de dados

Banco SQLite utilizado pelo sistema para persistir experimentos, variantes, snapshots, Runs, respostas e erros.

Os testes podem consultar o banco diretamente, mas não devem alterá-lo para executar operações funcionais do sistema.

4.20 Não testado

Indica que o comportamento ainda não foi verificado por esta suíte.

Não significa que a funcionalidade esteja ausente ou quebrada.


### Fundamentação

A redação preserva a separação entre Experimento, Variante, Snapshot, Run e Execução descrita na arquitetura do projeto. 【1-2a2d80】【2-eaa5f1】

As regras de congelamento, herança e ausência de nova consulta ao `.env` por Runs e variantes seguem a referência de configuração. 【3-e44e67】

A definição de `system-default` segue o contrato que o caracteriza como interrupção explícita da herança. 【4-66409a】

A separação entre resultado esperado, observado e decisão posterior evita transformar bugs atuais em especificações oficiais.