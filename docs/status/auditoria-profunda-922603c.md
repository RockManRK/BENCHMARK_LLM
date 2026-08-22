# Auditoria Profunda e Abrangente — BENCHMARK_LLM

**Commit exato:** `922603c61ee78592668e92eb9cd92170507b0caa`
**Método:** 8 subagentes independentes (um por área), reconciliados nesta entrega. Nenhum arquivo alterado, nenhum patch produzido, nenhum commit criado.

---

## 1. Resumo executivo

Das 8 áreas investigadas, **6 estão em bom estado** (poucos achados, todos de severidade baixa ou documentação). **2 achados de severidade alta** merecem atenção real:

- **ASY-01** — o achado mais importante de toda a auditoria, **confirmado por reprodução ao vivo**: quando `AsyncWriter` esgota as retentativas de um item e aborta, itens já computados que ainda estão na fila **nunca são drenados nem persistidos** — desaparecem silenciosamente, sem log de descarte, e `RunFinalizer` (corretamente implementado, consultando o banco) pode reportar o run como `completed` porque, do ponto de vista do banco, o item que sumiu nunca existiu. Isto é exatamente o risco de "falsa auditabilidade" que esta auditoria foi desenhada para achar.
- **ENT-02** — a entidade `Response` e seu repositório omitem silenciosamente 7 colunas reais que `ResultWriter` grava (`request_json`, `raw_response_consolidated`, `randomization_enabled`, `randomization_seed`, `options_presented`, `correct_option_presented`, `option_letter_map`). `export_service.py` lê exclusivamente por esse caminho incompleto — **toda exportação hoje carece de contexto de randomização e de fidelidade de request**, silenciosamente, sem erro.

Nenhuma violação confirmada de determinismo, segurança de segredos, ou corrupção de dados foi encontrada. A maior parte dos ~20 achados restantes são itens de manutenção de baixa severidade (documentação desatualizada, duplicação de fórmula, testes obsoletos) já bem delimitados e de correção mecânica segura.

**Reconciliação entre subagentes:** uma tentativa de subagente para a Área 2 retornou um resultado corrompido (confundiu sua própria identidade, alegou ter feito todas as 8 áreas) e foi descartada sem uso; a Área 2 foi relançada do zero e retornou achados válidos. Um achado da Área 8 (TST-05, suspeita de que os novos módulos Typer `provider.py`/`execute.py` seriam "conversão apenas de fachada") foi **verificado diretamente por mim** via `git show` no commit exato — a suspeita não se confirmou: os módulos antigos (`bcllm_provider.py`/`bcllm_execute.py`) de fato importam as funções de parsing dos novos módulos (`parse_provider_argv`, `parse_execute_argv`), então a migração é real e deliberada (parsing migrado, lógica de negócio ainda nos módulos antigos) — reclassificado como "verificado limpo", não um achado. Também verifiquei diretamente a hipótese cruzada de PLN-03 (se `raw_response` pode ser `NULL` numa resposta de sucesso) e não encontrei caminho ao vivo que produza isso no fluxo de streaming normal — a classificação de PLN-03 foi ajustada de "provável" para "possível" (risco estrutural real, gatilho ao vivo não confirmado).

---

## 2. Achados confirmados por severidade

### 🔴 Alta

#### ASY-01 — Itens computados são perdidos silenciosa e permanentemente quando o writer aborta em meio à fila
- **Área:** AsyncOrchestrator/AsyncWriter/retries/finalização
- **Arquivo e símbolo:** `src/core/async_writer.py::AsyncWriter.consume` (linhas 134-177, o `else: break` em 159-160), interagindo com `src/core/async_orchestrator.py::_execute_async` (linhas 195-197) e `_execute_run_with_semaphore` (linhas 370-405)
- **Comportamento esperado:** Todo resultado computado deve ser persistido ou ficar rastreável como perdido — nunca desaparecer sem traço (contratos de idempotência e auditabilidade).
- **Comportamento observado:** Quando `_write_result_with_retry` esgota as 3 tentativas para um item, `consume()` sai do laço imediatamente (`break`) **sem drenar o resto da fila**. Nada em `AsyncOrchestrator` chama `queue.join()`. Um item computado por uma chamada de API concorrente que chega à fila durante a janela de backoff (~1.5s) do item que está falhando fica na fila para sempre — o `writer_task` já retornou suas estatísticas finais.
- **Reprodução mínima:** Script isolado (sem rede, sem banco real): `AsyncWriter` com `write_result` sempre lançando exceção; item-1 chega imediatamente, item-2 é agendado para chegar durante o backoff do item-1.
- **Evidência (execução real, não apenas leitura de código):**
  ```
  write_result call count: 3
  stats: {'written': 0, 'errors': 1, 'aborted': True, 'abort_info': {...}}
  queue.qsize() APÓS writer_task completar: 1
  ```
  item-2 — um `ExecutionResult` totalmente computado — confirmado ainda na fila após o writer_task já ter terminado; nunca será processado.
- **Classificação:** confirmado (por execução ao vivo)
- **Impacto:** científico, auditabilidade, funcional
- **Severidade:** alta
- **Contrato relacionado:** `docs/contracts/idempotency.md` ("partial progress survives failures"), `docs/contracts/data-auditability.md` ("every request result is persisted immediately")
- **Recomendação:** (a) `AsyncOrchestrator` deveria drenar a fila após `writer_task` completar, logando explicitamente qualquer item descartado por abort, e/ou (b) `RunFinalizer`/CLI deveriam sinalizar um estado distinto de "completed" quando `writer.abort_info` está setado — hoje um run pode legitimamente reportar `completed` mesmo tendo perdido um item real, cobrado via API, cuja resposta foi computada e jogada fora.
- **Possibilidade de correção isolada:** parcial — drenar a fila e logar descartes é uma mudança pequena e isolada; decidir se `completed` deveria virar um novo status (`partial_failed_with_lost_items` ou similar) é decisão de produto.
- **Risco de regressão:** médio — toca o caminho de abort/encerramento, sensível a piorar se mal implementado (risco de contagem duplicada).

#### ENT-02 — `Response`/`ResponseRepository` omitem 7 colunas reais; Export não consegue mostrar contexto de randomização nem fidelidade de request
- **Área:** Entidades/schema/repositories/UoW
- **Arquivo e símbolo:** `src/db/models.py::Response` (linhas 109-165), `src/db/repository.py::ResponseRepository` (`save`, `get_by_id`, `list_by_run`, `list_needs_review`, `_row_to_response`), vs. `src/core/result_writer.py::ResultWriter._write_response` (INSERT direto, independente)
- **Comportamento esperado:** Uma forma canônica única para `Response`, consistente entre o que é escrito, o schema, e o que qualquer leitor recebe de volta.
- **Comportamento observado:** A tabela real `responses` tem `raw_response_consolidated`, `request_json`, `randomization_enabled`, `randomization_seed`, `options_presented`, `correct_option_presented`, `option_letter_map` — todas escritas diretamente pelo SQL próprio de `ResultWriter._write_response`. **Nenhuma dessas 7 colunas existe no dataclass `Response`, e nenhuma é lida por qualquer método de `ResponseRepository`.** `ResponseRepository.save()` é código morto (nunca chamado em produção — confirmado via grep) — a escrita real acontece só via `ResultWriter`, num INSERT paralelo e independente. Mas o lado de LEITURA está bem vivo: `export_service.py:186,205` chama `list_by_run(run_id)` para montar a exportação. **Toda resposta exportada hoje carece de quais opções foram de fato apresentadas ao modelo, a resposta correta no espaço apresentado (possivelmente randomizado), se a randomização estava ligada, e os campos de request/raw-response-consolidado auditados — silenciosamente, sem erro, porque as colunas nem entram no SELECT.**
- **Reprodução mínima:** Comparar a lista de 24 colunas do `INSERT OR IGNORE INTO responses (...)` em `result_writer.py` contra a lista de 18 campos do `SELECT`/`Response.__init__` em `repository.py` — a diferença de 7 colunas é exata e reproduzível por inspeção; `export_service.py:205` é o único ponto de leitura de respostas, e passa pelo caminho incompleto.
- **Evidência:** citada acima, ambos os arquivos lidos por completo neste commit.
- **Classificação:** confirmado
- **Impacto:** científico, auditabilidade, funcional
- **Severidade:** alta
- **Contrato relacionado:** `docs/contracts/data-auditability.md` (preservação de contexto experimental, fidelidade de request)
- **Recomendação:** Adicionar os 7 campos faltantes ao dataclass `Response` e a todo SELECT/`_row_to_response` de `ResponseRepository`, para que `export_service.py` (e qualquer outro leitor futuro) consiga de fato mostrá-los. Não "consertar" `ResponseRepository.save()` em si — está morto; decidir (não é chamada minha) se deve ser removido ou alinhado a `ResultWriter` caso vire o escritor canônico no futuro.
- **Possibilidade de correção isolada:** sim — campos aditivos no dataclass + lista de colunas do SELECT; nenhuma mudança no caminho de escrita é necessária, já que `ResultWriter` fica intocado.
- **Risco de regressão:** baixo — puramente aditivo do lado de leitura.

### 🟡 Média

#### ENT-01 — `schema.sql` está mais desatualizado do que o já documentado
- **Arquivo e símbolo:** `src/db/schema.sql` vs. `src/db/schema.py::get_schema_sql()`
- **Comportamento observado:** Além do já conhecido `ON DELETE CASCADE` ausente, confirmado: a tabela `errors` no `schema.sql` não tem coluna `response_id` nem `attempt_number` (todo o mecanismo de versionamento de erros está ausente do arquivo de referência); `runs.status` no `schema.sql` não aceita `'removed'` (o soft-delete de `--remove-run` não está refletido); `responses` no `schema.sql` não tem `raw_response_consolidated` nem `request_json`.
- **Classificação:** confirmado | **Impacto:** manutenção | **Severidade:** média (subiu de "baixa" — as colunas ausentes são exatamente as que este projeto trata como mais críticas para auditoria)
- **Contrato relacionado:** `docs/contracts/data-auditability.md`
- **Recomendação:** Regenerar `schema.sql` a partir de `schema.py`, ou apagá-lo e apontar leitores para `schema.py` diretamente (o próprio cabeçalho do arquivo já concede que `schema.py` é a autoridade).
- **Correção isolada:** sim (documentação, zero consumidores em runtime confirmados) | **Risco de regressão:** baixo

#### PLN-03 — Verificação de idempotência do Planner depende de uma única coluna anulável, sem sinal de conclusão independente
- **Arquivo e símbolo:** `src/core/planner.py:516-538` (`_get_executed_items`), `src/db/schema.py:114` (`raw_response TEXT`, sem `NOT NULL`)
- **Comportamento observado:** Um item só é considerado "já executado" se `responses.raw_response IS NOT NULL`. O schema permite uma linha de sucesso com `raw_response` nulo. Se isso acontecesse, o Planner re-executaria o item (chamada de API duplicada) e, como `_write_response` usa `INSERT OR IGNORE` com `response_id` determinístico, a segunda tentativa seria **silenciosamente descartada** — uma segunda geração do LLM, potencialmente diferente, jogada fora sem log.
- **Verificação cruzada feita nesta reconciliação:** tracei o caminho de escrita (`ExecutionEngine`→`ResultWriter`) e não encontrei um caminho ao vivo, no fluxo de streaming normal, que produza `raw_response=None` para um `status='success']` — o valor default é uma lista vazia `[]` (serializa para `"[]"`, não `NULL`), não um `None` bruto. **Por isso a classificação foi ajustada de "provável" para "possível":** o risco estrutural é real (não há segunda trava), mas nenhum gatilho ao vivo foi confirmado.
- **Classificação:** possível | **Impacto:** científico, auditabilidade | **Severidade:** média
- **Contrato relacionado:** `docs/contracts/idempotency.md`, `docs/contracts/data-auditability.md`
- **Recomendação:** Adicionar `NOT NULL` a `raw_response` (se de fato nunca deveria ser nulo para `status='success'`) ou adicionar uma segunda flag de conclusão independente do payload.
- **Correção isolada:** parcial — a query é uma mudança de uma linha, mas requer decisão sobre qual sinal usar.
- **Risco de regressão:** médio — mudar o filtro errado pode re-executar trabalho já feito ou pular trabalho pendente.

#### TST-01 — `ModelVariant` ainda construído com kwargs removidos (6 pontos, 2 arquivos) — reconfirmado
- **Arquivo e símbolo:** `tests/integration/conftest.py:159-169`, `tests/integration/test_end_to_end.py` (5 construções diretas)
- **Comportamento observado:** Todos os 6 pontos ainda passam `reasoning_mode=`, `reasoning_effort=`, `max_output_tokens=`, `vision_enabled=`, `structured_output=`, `web_access_enabled=` — campos que migraram para `config` no dataclass real. Já identificado (não corrigido, fora de escopo) numa investigação anterior; reconfirmado byte-a-byte presente neste commit exato.
- **Classificação:** confirmado — fixture ainda desatualizada | **Impacto:** funcional (bloqueia ~9 casos de teste) | **Severidade:** média
- **Recomendação:** `tests/factories/variant.py::VariantFactory` **já existe e já resolve isso corretamente** (dobra esses mesmos kwargs de conveniência em `config`) — trocar os 6 pontos para usar a factory existente, sem código novo.
- **Correção isolada:** sim | **Risco de regressão:** baixo

#### TST-03 — `ExecutionEngine.execute` não existe (~11 testes) — e a própria documentação de produção também está desatualizada
- **Arquivo e símbolo:** `src/core/execution_engine.py` só define `execute_async` (linha 252); ~11 testes chamam `engine.execute(plan)`.
- **Achado novo nesta rodada:** os próprios docstrings da classe (exemplo de módulo ~linha 41, exemplo de classe ~linha 217) mostram `results = engine.execute(plan)` — a documentação do próprio código de produção está desatualizada, não só os testes.
- **Classificação:** confirmado | **Impacto:** funcional (maior cluster isolado de testes quebrados) + manutenção (docstring em `src/`) | **Severidade:** média
- **Recomendação:** Renomear as chamadas de teste para `await engine.execute_async(plan)`; separadamente, corrigir os dois exemplos de docstring em `execution_engine.py` (fora da minha autoridade de tocar `src/` nesta auditoria — sinalizado, não corrigido).
- **Correção isolada:** parcial (o lado de teste é mecânico; tornar as funções de teste `async` pode tocar mais do corpo de cada teste do que uma troca de uma linha) | **Risco de regressão:** médio

### 🟢 Baixa

| ID | Título | Área | Severidade |
|---|---|---|---|
| CFG-01 | Texto de ajuda de `--vision`/`--structured` anuncia valor rejeitado e omite o aceito | Config | baixa |
| CFG-02 | `resolve_provider_lock` vaza o sentinel `FORCE_SYSTEM_DEFAULT` em vez de normalizar para `None`, ao contrário de todo o resto do arquivo | Config | baixa |
| PLN-01 | `ExecutionPlan`/`PlanRun` anunciam imutabilidade total mas usam `list` mutável (nada explora isso hoje) | Planner | baixa |
| PLN-02 | Docstring do `planner.py` contradiz o comportamento real de resolução de prompts (código está correto, só a prosa está desatualizada) | Planner | baixa |
| ENG-01 | `effective_tokens` computado de forma independente em duas camadas (hoje idênticas, risco de divergência futura) | Engine | baixa |
| ENG-02 | Conteúdo vazio ainda é gravado como `status="success"` — design deliberado, não bug | Engine | baixa |
| ASY-02 | `_write_error` não é idempotente contra um retry após commit bem-sucedido (janela estreita, não reproduzida ao vivo) | Async | baixa |
| CLI-01 | `--models system-default` não é rejeitado no novo módulo `execute` (assimetria com `--experiment`/`--run`) | CLI | baixa |
| CLI-02 | `--questions system-default` é rejeitado corretamente mas com mensagem de erro enganosa | CLI | baixa |
| LOG-01 | Redação de segredos só age dentro de `emit_event` — uma chamada direta de logger no futuro poderia vazar um segredo (não explorado hoje) | Logs | baixa |
| TST-02 | `ResultWriter._calculate_needs_review` renomeado para `_calculate_review_status`; 1 teste ainda chama o nome antigo | Testes | baixa |
| TST-04 | 3 blocos `except ImportError` de fallback inalcançáveis em `tests/conftest.py` ("Fase 4" que nunca existiu de fato) | Testes | baixa |

---

## 3. Suspeitas que exigem investigação (não confirmadas, mas plausíveis)

- **PLN-03** (acima) — risco estrutural real de idempotência; precisa que alguém confirme se `raw_response=NULL` é genuinamente impossível para `status='success'` em todos os caminhos (incluí verificação parcial nesta reconciliação, cobrindo só o caminho de streaming padrão).
- **ASY-02** — mecanismo confirmado por leitura de código, gatilho ao vivo não reproduzido (janela estreita: só dispararia se o próprio log de debug após o commit lançasse uma exceção).
- **LOG-01** — gap estrutural confirmado, mas nenhuma instância viva de vazamento de segredo encontrada nesta auditoria.

---

## 4. Divergências de teste/documentação

- **PLN-02** — `planner.py` (código de produção) tem dois relatos contraditórios de si mesmo sobre resolução de prompts; o código está certo, os docstrings de topo de arquivo estão errados.
- **TST-03** — os docstrings de exemplo do próprio `execution_engine.py` mostram uma API (`engine.execute`) que não existe mais.
- **TST-02** — teste chama um método de `ResultWriter` que foi renomeado.
- **Known-issues.md spot-check (Área 8):** toda alegação "✅ Resolvido" verificada diretamente (comportamento de `DATABASE_PATH`, `--remove-experiment` desabilitado, URL do `ProviderResolver` sem duplicação) se confirmou precisa neste commit. `--output`/`--format` seguem mortos mesmo após a migração Typer tocar os 4 módulos novos (parseados, encaminhados, nunca lidos).
- **CFG-01** — texto de ajuda do CLI desatualizado em relação ao parser real.

---

## 5. Mapa de código morto e duplicações

| Item | Local | Natureza |
|---|---|---|
| 3 blocos `except ImportError` inalcançáveis | `tests/conftest.py:87-88, 133-134, 164-165` | Stub de "Fase 4" que nunca roda; causa raiz de `test_infrastructure.py` testar uma API que não existe de verdade |
| `ResponseRepository.save()` | `src/db/repository.py` | Nunca chamado em produção — `ResultWriter` escreve direto via SQL próprio |
| `--output`/`--format` | `src/cli/commands/{experiment,model,questions,run}.py` | Parseados e encaminhados, nunca lidos por nenhum handler |
| `effective_tokens` (duplicação, não morte) | `src/api/response_parser.py:126` + `src/core/execution_engine.py:736-738` | Mesma fórmula mantida em dois lugares independentes |
| `schema.sql` | `src/db/schema.sql` | Zero consumidores em runtime confirmados; só referenciado por `Arquivos_Mortos/` (arquivado) e um comentário em `CLAUDE.md` |

**Não é código morto (verificado, descartado como suspeita):** os novos módulos `src/cli/commands/provider.py`/`execute.py` — são de fato importados e usados (para parsing) pelos módulos antigos `bcllm_provider.py`/`bcllm_execute.py`.

---

## 6. Gaps de cobertura

- **Nenhum teste comprova o comportamento real de abort do `AsyncWriter`** (ASY-01) — os testes existentes tentam provar o oposto (sobrevivência por item) e falham por motivos mecânicos de mock, nunca chegando a exercitar o caminho de abort real.
- **Nenhum teste cobre as 7 colunas ausentes de `Response`/`ResponseRepository`** (ENT-02) — a lacuna de leitura nunca foi pega porque nada testa `export_service.py` contra uma resposta com randomização/request_json populados e depois verifica se saíram na exportação.
- **`schema.sql` não tem nenhum teste de consistência contra `schema.py`** — a única forma de descobrir a divergência é leitura manual, como feito aqui.
- Cobertura da área de configuração (CFG) e de engine/API (ENG) é comparativamente forte — a maioria dos padrões de bug clássicos já foi encontrada e corrigida em sessões anteriores.

---

## 7. Lista priorizada

| Prioridade | Item | Por quê |
|---|---|---|
| **Imediata** | **ASY-01** | Perda de dados silenciosa com status "completed" enganoso — risco científico e de auditabilidade direto |
| **Alta** | **ENT-02** | Export está estruturalmente incompleto hoje, sem erro visível |
| **Alta** | **PLN-03** | Decisão sobre `NOT NULL`/segundo sinal de conclusão, antes que o gap estrutural vire um bug ao vivo |
| **Normal** | ENT-01, TST-01, TST-03 | Manutenção real, mecânica, sem risco científico |
| **Baixa/mecânica** | CFG-01, CFG-02, PLN-01, PLN-02, ENG-01, ENG-02, ASY-02, CLI-01, CLI-02, LOG-01, TST-02, TST-04 | Polimento, sem impacto funcional confirmado |

---

## 8. Itens seguros para correção mecânica (sem decisão de produto necessária)

CFG-01, PLN-02, ENG-01, TST-01 (trocar por `VariantFactory` já existente), TST-02, TST-04, ENT-01 (regenerar/apagar `schema.sql`), CLI-02 (mensagem de erro). Todos: mudança pequena, isolada, risco de regressão baixo, sem ambiguidade sobre o comportamento correto.

---

## 9. Itens que exigem decisão humana

1. **ASY-01:** o que deve acontecer quando o writer aborta com itens ainda na fila — drenar e logar como perdido? Introduzir um novo status de run? Re-enfileirar para uma futura re-execução?
2. **ENT-02:** `ResponseRepository.save()`/`get_by_id`/etc. devem ser alinhados a `ResultWriter` (viram canônicos) ou removidos, já que hoje são incompletos e não usados para escrita?
3. **PLN-03:** `raw_response` deveria ganhar `NOT NULL`, ou existe um caminho legítimo (fora do fluxo de streaming padrão que verifiquei) onde precisa ficar nulo para sucesso?
4. **CLI-01:** `--models system-default` deveria ser SUPPORTED (com semântica própria) ou FORBIDDEN (rejeitado) — hoje não é nenhum dos dois, cai como identificador literal.
5. **TST-03:** quem tem autoridade para corrigir os dois docstrings desatualizados dentro de `src/core/execution_engine.py` (fora do escopo desta auditoria, que não altera `src/`).

---

## 10. Limitações da auditoria

- O worktree isolado usado para grande parte da investigação (`/tmp/claude-1000-audit-922603c`) foi removido por limpeza de `/tmp` durante a execução dos subagentes em background — as duas verificações cruzadas finais desta reconciliação (roteamento real de `--resolve-providers`/`--execute`, e se `raw_response` pode ser nulo) foram refeitas via `git show <commit>:<path>` a partir do worktree principal, sem precisar do worktree isolado — método igualmente válido, mas registrado aqui por transparência.
- Múltiplos subagentes relataram inconsistências de ambiente (`.venv314` com symlink quebrado, apontando para diretórios de scratchpad de outras sessões) — a maioria dos achados vem de leitura direta de código, não de execução; onde execução foi necessária, cada subagente usou o venv que funcionava no seu próprio sandbox (3.12 ou 3.14 conforme disponível) — nenhum achado depende de uma diferença de versão Python.
- Uma tentativa de subagente para a Área 2 retornou um resultado corrompido/confuso e foi descartada sem uso; a Área 2 foi relançada do zero (ver §1).
- Área 8 não conseguiu obter números completos de `pytest` ao vivo (ambiente sem dependências no seu sandbox); os números de suíte mais recentes e confiáveis desta linha de investigação vêm da sessão anterior (comparação contra `a31d4a5`), não desta auditoria.
- Review UI (`src/review/`, `tests/unit/review/`) foi deliberadamente não reaberta, por instrução — limitações já documentadas (coluna `created_at` inexistente, UI de idioma único) não foram re-verificadas aqui.
- Nenhuma chamada de rede real foi feita; nada foi validado contra o comportamento real da API da OpenRouter além do que os testes mockados já cobrem.
- Como em toda auditoria estática, a ausência de um achado numa área não é prova de ausência de problema — é prova de que, dentro do escopo e do tempo desta rodada, nenhum foi encontrado com evidência suficiente para ser reportado.

---

*Nenhuma implementação foi feita. Aguardando aprovação antes de qualquer correção.*

---

> **Nota adicionada em 2026-08-22** (não altera o texto da auditoria acima,
> registrado aqui apenas como atualização de status): **ASY-01 foi
> posteriormente resolvido** via `docs/architecture/adr/adr-004-computed-result-persistence-failure-traceability.md`
> (status: accepted) e o checkpoint de implementação correspondente —
> incluindo a correção do caminho `except Exception:` em
> `async_orchestrator.py`, um segundo achado da mesma classe de risco
> encontrado pela revisão do Essence Guardian sobre a primeira parte da
> implementação. Ver `docs/status/known-issues.md` para o registro
> completo (causa raiz, correção, cobertura de teste). As demais seções
> desta auditoria (§2 Média/Baixa incluindo ENT-02, §3, §5, §6, §9)
> permanecem como registradas no momento original — resolvidas ou não,
> não reavaliadas por esta nota.
