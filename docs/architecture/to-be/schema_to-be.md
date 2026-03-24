# name: "@docs\architecture\to-be\schema_to-be.md"
# date: 24/03/2026
# version: 1.0
# Atenção!: nunca fazer alterações

---

# Detalhes das mudanças:

- Colunas experiment.system_prompt e experiment.user_prompt devem ser eliminadas, essas configurações serão gravadas junto com as outras configurações (18 configurações) em experiment.config_json
- Coluna experiment.is_active deve ser eliminada. Assim como qualquer código que faça referência a ela.

- Coluna model_variants.is_active deve ser eliminada. Assim como qualquer código que faça referência a ela.

- Coluna question_snapshots.is_active deve ser eliminada. Assim como qualquer código que faça referência a ela.
- Coluna question_snapshots.question_id deve ser renomeada para question_snapshots.json_question_id, pois esse é o ID no database com as questão originais.
- Criar a coluna question_snapshots.question_position, que representa a posição da pergunta no documento original, e passará a ser o valor usado para representar as perguntas de um experimento em todo o sistema. Ou seja, para adicionar perguntar por exemplo, no lugar de dizer "Q001-Q005", passaremos a usar apenas o número da sua posição, por exemplo "1-5". Muito mais simples. E em todo o sistema as perguntas serão representadas dessa forma, o ID do database original será apenas para referência interna. Para saber que a questão de posição X é a que tem o json_question_id Y.

- Criar a coluna runs.config para salvar todas as configurações da run (SEED resolvido, system prompt e user prompt)
- Coluna runs.is_active deve ser eliminada. Assim como qualquer código que faça referência a ela.
- Colunas runs.seed, runs.system_prompt e runs.user_prompt devem ser eliminadas, essas configurações serão gravadas junto com as outras configurações (3 configurações) em runs.config
- Trocar as colunas runs.started_at e runs.finished_at, por apenas uma, runs.duration . Motivo: Como runs podem ser processados parcialmente, como por exemplo, ao ter 100 perguntas, você executalo com apenas 50 das perguntas, ou apenas com alguns dos modelos configurados, precisamos de um valor que possa ser somado a cada parte da execução. Dessa forma. Se você rodar parcialmente, quando rodar o resto, ou mais alguma parte, a duração da nova execução se soma a anterior, até que todo o experimento seja concluído e se tenha o tempo total da duração.

- Criar a coluna responses.status, para indicar se foi processada corretamente, se deu erro, ou qualquer coisa importante
- Criar a coluna responses.finish_reason, valor do json que vem como "finish_reason", indicando o finish reason da solicitação.
- Criar a coluna responses.error_details, qualquer erro que ocorrer ou for retornado no json
- Criar a coluna responses.raw_response, o json completo da resposta
- Criar a coluna responses.cost, o valor de custo retornado no json como "cost".
- Criar a coluna responses.latency_ms, valor retornado no json
- Criar a coluna responses.review_status, que indica se o review manual de perguntas que precisam de review, já foi feito ou não.
- Criar as colunas responses.started_at e responses.finished_at, para medirem o modelo em que a requisição é enviado por nós, e o momento que recebemos completamente a resposta do servidor. Para dessa forma podemos, posteriormente, mensurar o tempo de processamento.
- Remover a coluna responses.created_at. As colunas started_at e finished_at poderão cumprir esse papel. O calculo é diferente, porém suficiente próximo para tornar a "created_at" redundante.
- Criar as colunas responses.effective_tokens. É a soma das colunas `input_tokens` + `responde_tokens` + `reasoning_tokens`.
- Criar a coluna responses.reasoning_tokens, valor retornado no json como "reasoning_tokens".
- Criar a coluna responses.response_tokes, valor retornado no json como "completion_tokens".

- Alterar a coluna errors.model_id para errors.variant_id. Tornará a informação mais exata.
- Renomear a coluna errors.created_at para errors.occurred_at. Apenas um ajuste para melhor entendimento. Atualizar códigos que forem necessários.


# Novo formato do banco de dados (Visão Completa):

## Entity Definitions

### experiments
`experiment_id`
`name`
`description`
`config_json`
`config_hash`
`created_at`

### model_variants
`variant_id`
`experiment_id`
`model_id`
`variant_signature`
`config`
`created_at`

### question_snapshots
`snapshot_id`
`experiment_id`
`json_question_id`
`question_position`
`question_payload`
`created_at`

### runs
`run_id`
`experiment_id`
`config`
`status`
`duration`
`created_at`

### responses
`response_id`
`run_id`
`variant_id`
`snapshot_id`
`model_id`
`question_id`
`status`
`finish_reason`
`error_details`
`response_text`
`selected_answer`
`is_correct`
`parse_confidence`
`review_status`
`manual_answer`
`raw_response`
`cost`
`input_tokens`
`response_tokens`
`reasoning_tokens`
`effective_tokens` (Soma, `input_tokens` + `responde_tokens` + `reasoning_tokens`)
`latency_ms`
`started_at` (Medido de forma local, entre envio da requisição e concluir o recebimento completo)
`finished_at` (Medido de forma local, entre envio da requisição e concluir o recebimento completo)

### errors
`error_id`
`run_id`
`variant_id`
`snapshot_id`
`model_id` (Substituir por variant_id)
`question_id`
`error_type`
`error_message`
`attempt_count`
`stack_trace`
`occurred_at`

---

Atenção! Caso tenha dúvidas sobre como coletar algum desses dados, sobre onde ele deve ser usado, ou qualquer outra dúvida, pare tudo e questione o usuário.