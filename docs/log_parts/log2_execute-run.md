2026-03-15 23:14:41 - INFO - src.main - BenchmarkRunner initialized
2026-03-15 23:14:41 - DEBUG - src.main - Arguments: Namespace(create_experiment=None, add_models=None, remove_model=None, add_questions=None, create_run=False, execute_run=True, models=None, run_id=None, iterations=1, questions=None, where=[], exclude=[], config=None, output='console', output_file=None, seed=None, verbose=False, dry_run=False, mode=None, experiment='nonteste', test_mode=False, vary_seed=False, temperature=None, max_tokens=None, top_p=None, top_k=None, repeat_penalty=None, reasoning_effort=None, enable_vision=None, enable_structured=None, add_to_run=None, complete_run=None, review_run=None, review_experiment=None, review_all=False, execution_mode='experiment', experiment_name='nonteste')
2026-03-15 23:14:41 - DEBUG - src.db.schema - Database initialized at data\benchmark.db
2026-03-15 23:14:41 - INFO - src.cli.experiment_commands - RunManager initialized
2026-03-15 23:14:41 - INFO - src.cli.experiment_commands - Executing run run-20260315231413-e4dae222 for experiment nonteste
2026-03-15 23:14:41 - INFO - src.api.client - OpenRouterClient initialized with base_url=https://openrouter.ai/api/v1
2026-03-15 23:14:41 - DEBUG - src.core.randomizer - AnswerRandomizer initialized with seed AUTO
2026-03-15 23:14:41 - DEBUG - src.core.execution_engine - ExecutionEngine initialized
2026-03-15 23:14:41 - INFO - src.core.execution_engine - Starting execution: 2 model(s), 4 question(s), 1 iteration(s)
2026-03-15 23:14:41 - INFO - src.core.execution_engine - Executing model variant: var-ae7cf538
2026-03-15 23:14:41 - DEBUG - src.core.execution_engine -   Iteration 1/1
2026-03-15 23:14:41 - INFO - src.core.iteration_executor - IterationExecutor initialized for run=run-20260315231413-e4dae222, model=google/gemini-2.5-flash-lite, iteration=1, experiment_id=exp-a7189910, reasoning_config=None
2026-03-15 23:14:42 - INFO - src.core.iteration_executor - Starting iteration 1 for model google/gemini-2.5-flash-lite with 4 pending questions (0 already answered)
2026-03-15 23:14:42 - INFO - src.utils.progress - ProgressTracker initialized: total=4, run=run-20260315231413-e4dae222, model=google/gemini-2.5-flash-lite, iteration=1
2026-03-15 23:14:42 - DEBUG - src.utils.progress - Progress tracking started for run-20260315231413-e4dae222
2026-03-15 23:14:42 - DEBUG - asyncio - Using proactor: IocpProactor
2026-03-15 23:14:42 - INFO - src.core.iteration_executor - Registered model variant: var-3f3edeb8 | model=google/gemini-2.5-flash-lite | signature=google/gemini-2.5-flash-lite::reasoning=unspecified::vision=true::structured=false
2026-03-15 23:14:42 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-3f3edeb8, model=google/gemini-2.5-flash-lite, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:42 - DEBUG - src.core.question_executor - Executing question Q001
2026-03-15 23:14:42 - DEBUG - src.core.question_executor - Using provided snapshot_id 101 for question Q001
2026-03-15 23:14:42 - DEBUG - src.core.randomizer - Randomized question Q001: original correct=A, new correct=D
2026-03-15 23:14:42 - DEBUG - src.core.question_executor - Randomized question Q001: correct answer changed from A to D
2026-03-15 23:14:42 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:42 - INFO - src.api.client - Sending API request: model=google/gemini-2.5-flash-lite, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:42 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:42 - DEBUG - src.api.client - Model: google/gemini-2.5-flash-lite, Messages: 1
2026-03-15 23:14:42 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:42 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C157BB60>
2026-03-15 23:14:42 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:42 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C1595810>
2026-03-15 23:14:42 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:42 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:42 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:42 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:42 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:43 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:16 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd03fbd0aa7a48c-GRU')])
2026-03-15 23:14:43 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:43 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:14:43 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:14:43 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:14:43 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:14:43 - DEBUG - httpcore.connection - close.started
2026-03-15 23:14:43 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:14:43 - INFO - src.api.client - API response: model=google/gemini-2.5-flash-lite, tokens=293, finish_reason=stop, status=200
2026-03-15 23:14:43 - DEBUG - src.api.client - Received response: id=gen-1773627315-lWW0DjfPzWeimv8Kzf3a
2026-03-15 23:14:43 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'D', 'refusal': None, 'reasoning': None}}]
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Message content: D...
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:43 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:43 - DEBUG - src.core.answer_parser - All letter matches: ['D'], filtered: ['D']
2026-03-15 23:14:43 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Answer parsing for question Q001: answer=D, confidence=low_confidence, raw_matches=['D']
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:43 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=101, model_id=google/gemini-2.5-flash-lite
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:14:43 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=101, question_id=Q001, variant_id=var-3f3edeb8
2026-03-15 23:14:43 - INFO - src.db.repository - Response saved with ID 101
2026-03-15 23:14:43 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:14:43 - INFO - src.core.question_executor - Question Q001 completed: selected=D, correct=D, is_correct=True, latency=1948ms, structured_outputs=False
2026-03-15 23:14:43 - INFO - src.utils.progress - Progress: 1/4 (25.0%)
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-3f3edeb8, model=google/gemini-2.5-flash-lite, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Executing question Q002
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Using provided snapshot_id 102 for question Q002
2026-03-15 23:14:43 - DEBUG - src.core.randomizer - Randomized question Q002: original correct=B, new correct=A
2026-03-15 23:14:43 - DEBUG - src.core.question_executor - Randomized question Q002: correct answer changed from B to A
2026-03-15 23:14:43 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:43 - INFO - src.api.client - Sending API request: model=google/gemini-2.5-flash-lite, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:43 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:43 - DEBUG - src.api.client - Model: google/gemini-2.5-flash-lite, Messages: 1
2026-03-15 23:14:43 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:44 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C1597250>
2026-03-15 23:14:44 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:44 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C159CC30>
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:17 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd03fc93f53b284-GRU')])
2026-03-15 23:14:44 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:44 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:14:48 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:14:48 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:14:48 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:14:48 - DEBUG - httpcore.connection - close.started
2026-03-15 23:14:48 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:14:48 - INFO - src.api.client - API response: model=google/gemini-2.5-flash-lite, tokens=980, finish_reason=stop, status=200
2026-03-15 23:14:48 - DEBUG - src.api.client - Received response: id=gen-1773627316-40Ou7c6wM45xdVaGEeqr
2026-03-15 23:14:48 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'A principal hipótese diagnóstica em um lactente com vômitos crônicos, poliúria, fraqueza, febre, desidratação grave, déficit de crescimento, osteopenia e raquitismo resistente à vitamina D é a **acidose tubular renal (ATR)**.\n\nDentre os tipos de ATR, a **acidose tubular renal tipo 1 (ATR distal)** e a **acidose tubular renal tipo 2 (ATR proximal)** são as mais comuns em lactentes.\n\n**Acidose tubular renal tipo 1 (ATR distal):** Caracteriza-se pela incapacidade dos túbulos distais de excretar H+, levando a uma acidose metabólica hiperclorêmica, com pH urinário persistentemente elevado (>5.5), hipocalemia (devido à perda de potássio nos túbulos distais) e nefrocalcinose. O raquitismo resistente à vitamina D também é uma manifestação significativa desta condição, pois a acidose crônica pode levar à desmineralização óssea e interferir no metabolismo da vitamina D.\n\n**Acidose tubular renal tipo 2 (ATR proximal):** Caracteriza-se pela incapacidade dos túbulos proximais de reabsorver bicarbonato, levando a perdas de bicarbonato pela urina e, subsequentemente, a uma acidose metabólica. Nestes casos, geralmente observamos bicarbonato sérico e urinário baixo, cloreto sérico normal ou elevado, e hipocalemia. O raquitismo também é comum devido à perda de fosfato pela urina e à acidose crônica.\n\nConsiderando as opções:\n\n*   **A) acidose metabólica hiperclorêmica:** É uma forte candidata, especialmente em ATR tipo 1, onde a retenção de cloreto ocorre para compensar a perda de bicarbonato. A apresentação clínica com vômitos (que levam à perda de ácido), poliúria, fraqueza e raquitismo é altamente sugestiva de uma acidose tubular renal. A principal consequência dos vômitos crônicos é a perda de fluidos e eletrólitos, e a desidratação e déficits de crescimento são comuns. A acidose tubular renal, particularmente a tipo 1, cursa com acidose metabólica hiperclorêmica e hipocalemia.\n\n*   **B) acidose metabólica hipercalêmica:** A hipercalemia não é típica da ATR. Em crianças com vômitos crônicos e perda de potássio, a hipocalemia é mais provável.\n\n*   **C) alcalose respiratória hipoclorêmica:** A alcalose respiratória é geralmente associada à hiperventilação, o que não é a principal manifestação aqui. Além disso, a clínica de raquitismo e poliúria não se encaixa bem.\n\n*   **D) alcalose respiratória hipocalêmica:** Similar à C, a alcalose respiratória não é a alteração primária esperada.\n\nA história clínica de vômitos (levando à perda de base/bicarbonato indiretamente, e mais diretamente a desidratação e perda de fluidos), poliúria (que pode ser induzida por mecanismos que afetam o túbulo renal), fraqueza (associada a distúrbios eletrolíticos e acidose), febre, desidratação grave, déficit de crescimento e raquitismo resistente à vitamina D são sinais clássicos de **acidose tubular renal**. A acidose metabólica hiperclorêmica é a descrição mais apropriada do distúrbio ácido-básico associado à ATR, especialmente a tipo 1, que cursa com perda de bicarbonato associada a um cloreto elevado para manter a eletroneutralidade.\n\nA resposta correta é a:\nA', 'refusal': None, 'reasoning': None}}]
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Message content: A principal hipótese diagnóstica em um lactente com vômitos crônicos, poliúria, fraqueza, febre, desidratação grave, déficit de crescimento, osteopenia e raquitismo resistente à vitamina D é a **acidose tubular renal (ATR)**.

Dentre os tipos de ATR, a **acidose tubular renal tipo 1 (ATR distal)** e a **acidose tubular renal tipo 2 (ATR proximal)** são as mais comuns em lactentes.

**Acidose tubular renal tipo 1 (ATR distal):** Caracteriza-se pela incapacidade dos túbulos distais de excretar H+,...
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:48 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:48 - DEBUG - src.core.answer_parser - Filtering out article 'A' at position 3054
2026-03-15 23:14:48 - DEBUG - src.core.answer_parser - All letter matches: ['A', 'D', 'A', 'A', 'A', 'A', 'D', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'B', 'A', 'A', 'C', 'A', 'A', 'A', 'D', 'C', 'A', 'A', 'A', 'A', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A'], filtered: ['A', 'D', 'A', 'A', 'A', 'A', 'D', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'B', 'A', 'A', 'C', 'A', 'A', 'A', 'D', 'C', 'A', 'A', 'A', 'A', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A']
2026-03-15 23:14:48 - DEBUG - src.core.answer_parser - Ambiguous response: multiple letters {'C', 'A', 'D', 'B'}
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Answer parsing for question Q002: answer=None, confidence=ambiguous, raw_matches=['A', 'D', 'A', 'A', 'A', 'A', 'D', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'B', 'A', 'A', 'C', 'A', 'A', 'A', 'D', 'C', 'A', 'A', 'A', 'A', 'A', 'D', 'A', 'A', 'A', 'A', 'A', 'A', 'A']
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:48 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=102, model_id=google/gemini-2.5-flash-lite
2026-03-15 23:14:48 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:14:48 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=102, question_id=Q002, variant_id=var-3f3edeb8
2026-03-15 23:14:48 - INFO - src.db.repository - Response saved with ID 102
2026-03-15 23:14:48 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:14:48 - INFO - src.core.question_executor - Question Q002 completed: selected=None, correct=A, is_correct=False, latency=4979ms, structured_outputs=False
2026-03-15 23:14:48 - INFO - src.utils.progress - Progress: 2/4 (50.0%)
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-3f3edeb8, model=google/gemini-2.5-flash-lite, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Executing question Q003
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Using provided snapshot_id 103 for question Q003
2026-03-15 23:14:49 - DEBUG - src.core.randomizer - Randomized question Q003: original correct=A, new correct=B
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Randomized question Q003: correct answer changed from A to B
2026-03-15 23:14:49 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:49 - INFO - src.api.client - Sending API request: model=google/gemini-2.5-flash-lite, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:49 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:49 - DEBUG - src.api.client - Model: google/gemini-2.5-flash-lite, Messages: 1
2026-03-15 23:14:49 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:49 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C159E190>
2026-03-15 23:14:49 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:49 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C15CC950>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:22 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd03fe88cafe024-GRU')])
2026-03-15 23:14:49 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:14:49 - DEBUG - httpcore.connection - close.started
2026-03-15 23:14:49 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:14:49 - INFO - src.api.client - API response: model=google/gemini-2.5-flash-lite, tokens=338, finish_reason=stop, status=200
2026-03-15 23:14:49 - DEBUG - src.api.client - Received response: id=gen-1773627321-MH3wn5rAZXtXxJcf7rQZ
2026-03-15 23:14:49 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'A', 'refusal': None, 'reasoning': None}}]
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Message content: A...
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:49 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:49 - DEBUG - src.core.answer_parser - All letter matches: ['A'], filtered: ['A']
2026-03-15 23:14:49 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Answer parsing for question Q003: answer=A, confidence=low_confidence, raw_matches=['A']
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:49 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=103, model_id=google/gemini-2.5-flash-lite
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:14:49 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=103, question_id=Q003, variant_id=var-3f3edeb8
2026-03-15 23:14:49 - INFO - src.db.repository - Response saved with ID 103
2026-03-15 23:14:49 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:14:49 - INFO - src.core.question_executor - Question Q003 completed: selected=A, correct=B, is_correct=False, latency=755ms, structured_outputs=False
2026-03-15 23:14:49 - INFO - src.utils.progress - Progress: 3/4 (75.0%)
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-3f3edeb8, model=google/gemini-2.5-flash-lite, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Executing question Q004
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Using provided snapshot_id 104 for question Q004
2026-03-15 23:14:49 - DEBUG - src.core.randomizer - Randomized question Q004: original correct=D, new correct=A
2026-03-15 23:14:49 - DEBUG - src.core.question_executor - Randomized question Q004: correct answer changed from D to A
2026-03-15 23:14:49 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:49 - INFO - src.api.client - Sending API request: model=google/gemini-2.5-flash-lite, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:49 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:49 - DEBUG - src.api.client - Model: google/gemini-2.5-flash-lite, Messages: 1
2026-03-15 23:14:49 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:49 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C155BBD0>
2026-03-15 23:14:49 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:49 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C155BDF0>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:49 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:23 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd03fed69501595-GRU')])
2026-03-15 23:14:51 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:14:51 - DEBUG - httpcore.connection - close.started
2026-03-15 23:14:51 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:14:51 - INFO - src.api.client - API response: model=google/gemini-2.5-flash-lite, tokens=129, finish_reason=stop, status=200
2026-03-15 23:14:51 - DEBUG - src.api.client - Received response: id=gen-1773627322-vyVlR9O3tPrQepPxUhoK
2026-03-15 23:14:51 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'A', 'refusal': None, 'reasoning': None}}]
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Message content: A...
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:51 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:51 - DEBUG - src.core.answer_parser - All letter matches: ['A'], filtered: ['A']
2026-03-15 23:14:51 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Answer parsing for question Q004: answer=A, confidence=low_confidence, raw_matches=['A']
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 23:14:51 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=104, model_id=google/gemini-2.5-flash-lite
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:14:51 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=104, question_id=Q004, variant_id=var-3f3edeb8
2026-03-15 23:14:51 - INFO - src.db.repository - Response saved with ID 104
2026-03-15 23:14:51 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:14:51 - INFO - src.core.question_executor - Question Q004 completed: selected=A, correct=A, is_correct=True, latency=1294ms, structured_outputs=False
2026-03-15 23:14:51 - INFO - src.utils.progress - Progress: 4/4 (100.0%)
2026-03-15 23:14:51 - INFO - src.core.iteration_executor - Iteration 1 completed: 4/4 pending questions, 0 skipped (already answered), 0 errors, 9105ms
2026-03-15 23:14:51 - DEBUG - src.core.execution_engine -     Completed: 4/4, Errors: 0, Duration: 9106ms
2026-03-15 23:14:51 - INFO - src.core.execution_engine - Executing model variant: var-9a56c041
2026-03-15 23:14:51 - DEBUG - src.core.execution_engine -   Iteration 1/1
2026-03-15 23:14:51 - INFO - src.core.iteration_executor - IterationExecutor initialized for run=run-20260315231413-e4dae222, model=openai/gpt-5-mini, iteration=1, experiment_id=exp-a7189910, reasoning_config=None
2026-03-15 23:14:51 - INFO - src.core.iteration_executor - Starting iteration 1 for model openai/gpt-5-mini with 4 pending questions (0 already answered)
2026-03-15 23:14:51 - INFO - src.utils.progress - ProgressTracker initialized: total=4, run=run-20260315231413-e4dae222, model=openai/gpt-5-mini, iteration=1
2026-03-15 23:14:51 - DEBUG - src.utils.progress - Progress tracking started for run-20260315231413-e4dae222
2026-03-15 23:14:51 - DEBUG - asyncio - Using proactor: IocpProactor
2026-03-15 23:14:51 - INFO - src.core.iteration_executor - Registered model variant: var-03f2219a | model=openai/gpt-5-mini | signature=openai/gpt-5-mini::reasoning=unspecified::vision=true::structured=false
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-03f2219a, model=openai/gpt-5-mini, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Executing question Q001
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Using provided snapshot_id 101 for question Q001
2026-03-15 23:14:51 - DEBUG - src.core.randomizer - Randomized question Q001: original correct=A, new correct=A
2026-03-15 23:14:51 - DEBUG - src.core.question_executor - Randomized question Q001: correct answer changed from A to A
2026-03-15 23:14:51 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:51 - INFO - src.api.client - Sending API request: model=openai/gpt-5-mini, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:51 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:51 - DEBUG - src.api.client - Model: openai/gpt-5-mini, Messages: 1
2026-03-15 23:14:51 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:51 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C15A3150>
2026-03-15 23:14:51 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:51 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C15A3450>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:24 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd03ff5f8d329e4-GRU')])
2026-03-15 23:14:51 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:51 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:14:58 - DEBUG - httpcore.connection - close.started
2026-03-15 23:14:58 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:14:58 - INFO - src.api.client - API response: model=openai/gpt-5-mini, tokens=706, finish_reason=stop, status=200
2026-03-15 23:14:58 - DEBUG - src.api.client - Received response: id=gen-1773627324-e6aBmQu2WMXyuvs9pRZt
2026-03-15 23:14:58 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'completed', 'message': {'role': 'assistant', 'content': 'A', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'gAAAAABpt2fCJ-k1vkoTHL0sNo_cJqPNBLB9x42H9B0zUue8lVS1-XWEsx3Ij8cQUxNDtjhCzMyjSLk_L69SczjFT4Iq3De27tP6bFmEVGouTYwwR-fFXe7k8hgIJ_QTgapi_d98zHu8r6LFkKGxqIy_oGm1Jatp_S92oAqFHpoYiOI6wYSCOyD2k7w2bwdihaCd2OwEwpjkT6U3PFr4HoHgPHQoYMqeAizN1j28OjXOmTSlzPkPTMv82oLmVQ__iPJPqU0ssMGLhUrByKo4vTSwSazR5KTx-HRm7zb8-c9Io9wwlD-NIbwDwFi1-h_oOtjtENs3s85PKaDvNDB4_1Z--kh96qgeWZvhIwB1eLR4rRUxHbIY1ls8Uvof1bZbKcc3uWdiBsyQIzQ0_dWrMckfSs9kzpHycSAqJKGU9lwj8WOQVZEtKtkAixcT7ijcj4hDQc5o04umNHqQh0otyH_rcbN0yTUKptxG9Qrko8xa4VJUZVbeNEn5r8SryIdoPNRW-f9KvlOJsoA0edPy5rWJh1dXMn8HgHisD_rGIKMIYye7db_XeD9Mt10wEGuwDEfHBZRlcHRAzTSQ_s8jEI2TlXMT6tTCkqG7IJzFHJiVLZPsX_bGo79C2M1xpA9drPnSv9yDVKi46SWqfuOdpHEwbiF6Uj0_s4QwXY0jkV-yZMTWV7kd1l3e6uD9kc7MRoIKRaQV3JFZ1W1ur8tNEMtXfqhNjUGkyY65pFMBqH1lFc0iawT9hZVDzUuvz87NS9DFQf8GhZQEtsJQy1No1O6H608cdCYdeIdhQxTKZaCaXpKooRvxWfJP9kdfmifyXvWs0bKtKbZIyvLdyqLePbcR_6aoMJMLteME92AAt0LGU7FACuQUm-i3V5rdNy1J0LUNbsVOSYKNpw1VXZYRc2bVfljvgtXu7DWV_yvZT9V020T7u-nNmFxrUzBFlYyKtwx_DfZP8_Leqzy1vPG0gLBDXIqn2GvjMWcrYJlaXYqyoP9imrgnTTRN_5NpZoUHE3kGoc1dxSi38AsNf82oA2U3cIosVbPrSuLiIiAPgrZphzg6VVNOhnB84TsEUC8TIKi0rzwV_USyhhZJvQd96EeQdYizczwxXtoV1o38QOVisy9OS_LHAFovtlGmaG149CGBv8nJaeURX2kKaQDC-dtJ8QJVlH57xl1kpILYX4_R5Wzu4JAFRW3jWoNZ542rs6GE6w2EKh2N-c9yX_tCs3B8-6QPP52gzeE8YsdzAzFzTB_V1296Nz9124Bqi0HbSBrsRVb-yfPXFIlPs62ABa6jCqmhwRJGRGW63_ycTjZpke3szl9VGB4g-5OeXc7kBmaF4DQhKlHa6SsCmgSTULmdbgDIRpF116ftSZQOhEZ4Y2KBP-jXj4bJ0Z8re_pGrFNZwKOniAOqsgZfW_7T5crXmAlGHlFEemjWBZA5KAc0VVoC6Z2B13KEBv4TW7ilHdmcSaaX7g6BqXiJy2-uVddoWO-drG6EofykR_rywOPE-aAkz1a7_gVKmaUux24Ayw5og8-M1thxd2aagFo1bXrNWFDD1seK_GlVQtrxRfWzoXfvz4mGUxWDhB_xSbXEfLpXjDjYPwFF4yWtjGj2kpv2EGTewJIudEdNRrZZejqsJx-zZLFZBsXvzxmoOISrgg3FcIGt0YJn_uUfIdnJx1y1AjqmcgJCJ6YVMGZe_vFvB53joQLFozNxk3j-KIheoriBLLYqHuZAW0OZzna9ugExc7Y74Zw36qDlTpMGnPIVOu2rqhWWn98O7-2rktG8_-I7WvPmWkdXW9VrcO7BhrvUtpDC9pzB3V_tPhiCD3zCe19nQQTV8CixPymRAeI9hwkKrdcJ4XoK_Ejh_A45QnUFvuGYoBB7HBS5IFKmg6oJgpPHHVFwiVW3QLMis3Oddu7isa2p0AOUHfqrlwdtiWWO36jWCVu3JMHNznL9YmfFXy-O_kTcbV2ow_wqWWKo0k6cHvP11YKJwZSUBP1CukofbBf25_gTQGPUGyB0qvkh_u2OlzRDw0oyk3epHdWewNG8OHpS0cJJidhzFYqiACtQiIcfyYiBnjV3GUyDi5M5FL7sB8z7svEhXk7iDi_blZBV3N_OpNr0c1rAstPOO62KA5a88TfthE_xj2yBT7oaUFrjxzIoyRjEGwh79tiuXuXWBc-wrs344qIjTII2OvyBpINFUuJ2qAlG1UCKneSCKP3vQC7GSXltFC3l0yGMA7x4qUnGuFWbE1lFeC04OKSB4NrgLHTcG-UDpr7HAxVgRRzk0p8O59QHKDLpHvClWmcUx45vuyD9rz6XyFHaJKavZaDw1S_7JVoKIesSjakizXi5RPAqPZlyPDi63bXBRyYHhJ5FJnDbbmTkeGnYFUkxgcHUQGX_lXGLI8bvlWovuPcKTiTw0mh0WvScseTUQl8Q82eyuLoJcZoSUGYh1oCkFqbBBwXEcSIyKSEAjP4ZbfhyUJs3S1W77uLlWBGJGuh27Nvp3AK1Wif4p8r0c9UiewIa-YaC2JxqcONVm4Ok48EyseaU7nosV4sVTuAKhf0CwMyX1dgdnaWtewVl_r8v8LYsG9rvOtQvI0zX404fVneuT2TotDuXIlZNtA-Cvi6h4-9s_zy5W5_lfDf-BUf7nS26ctp2pT8s0s6bB1wU5ewEpXyKY_5pjAy48i4ArTZRCliB7teiK37IcU4A0NylI9_57h36WwMlKkCnfPZ6xiwEtkBJSYBy-o8cxqdTYEW4hrFWeYiasx2gkhr7Z9k8Vpx2sCz4IMSRrhuFEdLH8rB3Rl7LKGFF97M7IlYfphV7wk5Ku3oE5YRpG45lgsycPNrw8pQOLMhQZhCkO2JJOpa3ul8aPFHES3GqP6gjdZy1TBTa95PNAVijZgs3TBg2rji4f0s06Fje1gydwl1Befej4ie_bSYuTsXnSVZ4V_xTltxRlKi4L4wi_b27FDf8xcMiLlJ8fUDCTX7uYOueTkn1GDbzF4DnMUrDVJFdE_RoMwbdykD1c-C1qIqeY8Jh5j23aX3vDo8tJHwYrhRnK0iVd38Zc9a5XVjVxtCe9PQLRwLDNVL32Ap9xTFO2JQeYmiIJWlXkuJV2fIpE-XIZRHkWyh2xuN9_XNe1im6VuBWZJ9vPbI0ObnlA-ajm7uPPZxxrGhzkc4qVILTfark9iYfCEa43e0=', 'format': 'openai-responses-v1', 'id': 'rs_075e56f8e67deaa40169b767bc8dd48193b49cfe8e58509476', 'index': 0}]}}]
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Message content: A...
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 384
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 384
2026-03-15 23:14:58 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:58 - INFO - src.core.question_executor - API response indicates different model: requested=openai/gpt-5-mini, actual=openai/gpt-5-mini-2025-08-07
2026-03-15 23:14:58 - DEBUG - src.core.answer_parser - All letter matches: ['A'], filtered: ['A']
2026-03-15 23:14:58 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Answer parsing for question Q001: answer=A, confidence=low_confidence, raw_matches=['A']
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 384
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 384
2026-03-15 23:14:58 - INFO - src.core.question_executor - Token usage
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=101, model_id=openai/gpt-5-mini
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:14:58 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=101, question_id=Q001, variant_id=var-03f2219a
2026-03-15 23:14:58 - INFO - src.db.repository - Response saved with ID 105
2026-03-15 23:14:58 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:14:58 - INFO - src.core.question_executor - Question Q001 completed: selected=A, correct=A, is_correct=True, latency=7300ms, structured_outputs=False
2026-03-15 23:14:58 - INFO - src.utils.progress - Progress: 1/4 (25.0%)
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-03f2219a, model=openai/gpt-5-mini, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Executing question Q002
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Using provided snapshot_id 102 for question Q002
2026-03-15 23:14:58 - DEBUG - src.core.randomizer - Randomized question Q002: original correct=B, new correct=A
2026-03-15 23:14:58 - DEBUG - src.core.question_executor - Randomized question Q002: correct answer changed from B to A
2026-03-15 23:14:58 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:14:58 - INFO - src.api.client - Sending API request: model=openai/gpt-5-mini, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:14:58 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:14:58 - DEBUG - src.api.client - Model: openai/gpt-5-mini, Messages: 1
2026-03-15 23:14:58 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:14:58 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C16345F0>
2026-03-15 23:14:58 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:14:58 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C1634050>
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:31 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd04023a8f8464c-GRU')])
2026-03-15 23:14:58 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:14:58 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:15:04 - DEBUG - httpcore.connection - close.started
2026-03-15 23:15:04 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:15:04 - INFO - src.api.client - API response: model=openai/gpt-5-mini, tokens=440, finish_reason=stop, status=200
2026-03-15 23:15:04 - DEBUG - src.api.client - Received response: id=gen-1773627331-pdDxWuYwU0ucveed5shL
2026-03-15 23:15:04 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'completed', 'message': {'role': 'assistant', 'content': 'A', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'gAAAAABpt2fIGAws2KWY4d8fZu4DctLbIaVg86nDa8xvLuvw5qM6zvagy2zNYB5rzkrqUOLPXm4-mFf96ZtmBfJlHVI6TOmDZlYpR5xrWsClVzaHGQl8B0ePAyW0ik6NdsXnMyVC8-vZ8QJeWrNSbS8_xQHtQA6PRgBghob8Nur7EY-q5nmoxVH0NuA_t3mFtkUVqqDm-lmxu9LOtWNhvORUP0EsfKOieH60O_Ue-5qehiU9xbHIGLqPciUKHbIw-yQTiXGCc5nrPxqJFW-HUmoDl8AH2oS31mXLpijxk74U480wnRFhk5pS3EsDZbl82P_rAXTZJHf5UB2jpsrV5J0NxT3OSdda5MZztge4pGfqqc8K5ZqI2EI8QJJV3vUOKettoPY437LAP00kpWwJa0GJmS0AVP9FdbpuxEIQEwyTbDfXrlHfK8L1tsvkyHdDsIGHfClfdchshGsfYMajiJDB-I88VqK2JJYBdsaM3Sk_bbl35wDzM2MrZnQrysPEE6LVU6z5h6CSrtERnP_p5gV7HgbgHNGcFC7XWZDK2nWGJQcG-ALkN8-ioMOI6drTKgEgolqhuPvCQnAfD9KFj-zfi3sZtoYnyNWJMhhi5xRYaRmpFpcw1u_um7xQsb5XVcXTv3hH6nj9ADbdE0__vzzxkfdOBTN_JvnwI3XKxoN1f6qxBK-ngZetEd1bB2-HL8zZPNOOCZUUDa_evYZszqOk5MtSqyOBynZvv1xOtmd-y9H0f0B0B3IqMcslnsb66zq08Tl1zDf0oESnirfyZjuz24dX-ActIkZdY6c2c5h3SxjQ2lLVyzkwPIaVMi8x4q8dKIIT2cw27gydbXyBX2MvrEAQt5y_pXVW6iOFO2kT9MS60mr3xL2XaIxnKn3gKV1XJkNJG8ceGNoFNQF2lHTilv0zCYkJrom2IkM9Rl1uvRwSYZRV8Zjc6BKf4yr0bzithz-8pupqM9X-OwfaKIb3S6kWMiTUqp35n1UoQAsDoVlCND3dVXohmat3XAv16iu6GwfQrTT-Gr3QRQkFwNQF3UDMBKZUHUPFuS4rbq2utPQGtUQNV1435ZwoD8sw5n-sXz6GTZOPkmWA3_0w006zaflPksVOx6dos74QydleUo6b8cgcfGXxtuORqHAq5uqNkDtf-90mIeSUDX8FJx3-gqhfO99rrUVeNMWlS4Vd6T2JQ5KhbiqrwuxTYHnBExy8NpwUKty2_Cf3jpJRafHpQ3l2vFl1o99eQeqGzygGHp2ONK3FKq33jPayyZXInT3qGx0w2dNXHNco_d5LPeMx8P6e1iEbc4OJBsSwELjQZH1iBGaF-j-n0k2n4gIhKhi2945UOyJzrjgSfQNYuOvYx7ecQMurCjR1wGNr5MkY3lLKHQa4O2dR3tP6madylk05B5119wfZZDO8p3HDlSvZ_0dVU0oESG87tRBacCY9_6fgapDFXljmZTkJSTL1GqIstCsCq6hllAjVV4XxQz8V-60AwddaKOELIKSZA2JC3caGCkEDzDUzLx_r60y-OXg94V5pmPtYGDlFGUA9OpnLDZxnMjxjLePYwfPGZEgLWaWXkzSyK43AMaKTWDqPvv9wmTsF1K6nMeOAsZYeg0mo-UxNUhmlvwh9b8xi-SgUfNlco7rODAATPpaajojRcV0xlzCJodjnWzi_En8TVnnFki8CMnokWGAUnEdY36eZdHwb5nue3CttfJ40Pl7q6Cf3x8XCcJ_NY3IhkhseWPw7Mm8NHE54tF8puE9AfH3DcFgL5aCN6DkNnwiVD9Jhuu6iWSeWZShYAUWjYAfCi3ufQeuVMzi6QheZJ-e_ulL_EKa7ktbhK5V_IXz6YesI-zQmoBEEcsmZRoCyeTuYY4NfyQDJRcdkN1Dmj5o4HOK0fe7YC-4rZdma34-WINh59gKhBzdO0al3NYEfDFgYiSUGuta20trYgQI2KZEuk1bX7mXlejsKPbXeQAmQDotCt6bOrTvmTmnVr0DL2xR_Hco3F-vj45Z3_U6bUcHog2DaPOZh1NrMgmW5-PNqiks7fYf4sje3kwK8gy-DIV-ivAChnwrchrVB77074B1ogVHmVWqrj5UIi_zxhqHEvZ_80Z27lV9ngM1-jLCm7yD_ZI5NoEb3m0nTHfMt0Iak_K5ADod_OUBsgZ2FMcjbGL1ExevB5xxp72QIEhsnbtOfEk9FT9Syi7vzR14j7DnMn0Vc-USpyPafKGQBcTM9FbcROcoSnhLUh7_q9cdSXBoWD2yv5dZlJ06tcoaRxvSv745DHLuFeyIh5PmUUfwdtYSQAAV4n5b8wA8QowxfsjkEXz7HOA9kJ_jgyOYid5BxYT0sLQ37rBMfijGbs-jIXAdkhH9WYGPWZT5Nx6-GKCbAYmxrfYNTF-Lc0iKT1sjHpwdPQPZ988pOcW7rWs0pGS3CTDi_El2ozUjF1UmEYP-lVwSJPJaAjOdVPH2IzEBEYR1Kv3yCt03x9rqIENkPrHtxNq-fy91Qkwon', 'format': 'openai-responses-v1', 'id': 'rs_0df981aa35e3c1460169b767c3d86481948cac3e8828b5b2f8', 'index': 0}]}}]
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Message content: A...
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 256
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 256
2026-03-15 23:15:04 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:04 - INFO - src.core.question_executor - API response indicates different model: requested=openai/gpt-5-mini, actual=openai/gpt-5-mini-2025-08-07
2026-03-15 23:15:04 - DEBUG - src.core.answer_parser - All letter matches: ['A'], filtered: ['A']
2026-03-15 23:15:04 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Answer parsing for question Q002: answer=A, confidence=low_confidence, raw_matches=['A']
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 256
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 256
2026-03-15 23:15:04 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=102, model_id=openai/gpt-5-mini
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:15:04 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=102, question_id=Q002, variant_id=var-03f2219a
2026-03-15 23:15:04 - INFO - src.db.repository - Response saved with ID 106
2026-03-15 23:15:04 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:15:04 - INFO - src.core.question_executor - Question Q002 completed: selected=A, correct=A, is_correct=True, latency=5684ms, structured_outputs=False
2026-03-15 23:15:04 - INFO - src.utils.progress - Progress: 2/4 (50.0%)
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-03f2219a, model=openai/gpt-5-mini, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Executing question Q003
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Using provided snapshot_id 103 for question Q003
2026-03-15 23:15:04 - DEBUG - src.core.randomizer - Randomized question Q003: original correct=A, new correct=C
2026-03-15 23:15:04 - DEBUG - src.core.question_executor - Randomized question Q003: correct answer changed from A to C
2026-03-15 23:15:04 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:15:04 - INFO - src.api.client - Sending API request: model=openai/gpt-5-mini, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:15:04 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:15:04 - DEBUG - src.api.client - Model: openai/gpt-5-mini, Messages: 1
2026-03-15 23:15:04 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:15:04 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C15F60B0>
2026-03-15 23:15:04 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:15:04 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C15F6270>
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:37 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd040476dec2395-GRU')])
2026-03-15 23:15:04 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:15:04 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:15:13 - DEBUG - httpcore.connection - close.started
2026-03-15 23:15:13 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:15:13 - INFO - src.api.client - API response: model=openai/gpt-5-mini, tokens=867, finish_reason=stop, status=200
2026-03-15 23:15:13 - DEBUG - src.api.client - Received response: id=gen-1773627337-MAeSNw5i3oBcqiHcNYDM
2026-03-15 23:15:13 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'completed', 'message': {'role': 'assistant', 'content': 'C', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'gAAAAABpt2fSEeEVycobA8BvLfuEO35or8uP_7Vh27WeI0q4lJKdN7vhYXT3nCm74GyKIcUEgfIxirrlN5VQD8UTRjJKrgL-OyWczg9UMdPpYMSLNRPVwCYYQeSD9shtH6Z6vfvmXrpPEpR8H0AsenacRTT4LfR7kq2omCVu1dPiupX2CLeGLzDwi139B75pXjdIbM5I2fPYMOwK7eXhcy7D4LSpU4BpbgGaXZjlQttw6fJnI6iKeDGwMoDmLqpku6TzrAPFBWuKBa15n_B9RYxnnuJXNB65fJ81zvisuL1K81a4mPcIQVxPPm96mCxEMyMnpE_WnZcLhxbXycYH2ccp3viuP1_8cCJgaAjLr1rcOAM64gFRlETQ4OpjbQQxu6UU4Ajie4OXGUPLdL_icK4QT_saQWktXsPH3d9MQsyhoqLZ5auvRtw9cKHkGv2FoA_qtmIBpifdTx0ZAfUDhh2v7iLLaFaVB9iCztfZPoWzGU-0t9zhvdc5VSgYft-4h5mm-VsZ2LT7wnKBoTmQ4x0sPjv1g4K1TUCax_tC3uR5KCHYfaPrEwM-Vtj5szBwcJJ_Rbb7Dg0L0pbQc353QgwlwlBiiO-o7e_dBxqcHjX6mvYyPq_GmjCL8uP6Ez1mU177Rwb2qjNbbFIRdzfroj7IhFeEkD_sbVPxd3L0C7pwMnWKiT_qPD0Gl3RB7HbqT4W4Q-giu1yWSetukmkgw1_xpSvC-m_wJlGbpfIeVTZM8byeJccDIifXqW8a_9eUovc4IUMStv4_GcQZLi8Pi6gVE9z3dG5qXZlB8W2TRfbTz7wt6roanydDy5jAXehhO4xlrvZIhFimICJJp5MQjbqXIivfADi0xeN4A7n1FNT4dRUuzNqxggsbXKnugNzUgJrRxJ1iU8XZoyUzdCQL1vCUZR7txwQSRn8gg2PSlqxbw1uM9tJmg1aChNij8_n5ih_AlQ1xdkcrNvBKMNMaUYrtcBinoL9dop_c3OdxdVN240CWGnx6DRfHiaAGLO_3jfJUt5oPM-f70P0MctrcfOLpeJV7AuQMoK55mPfQIEl-CEro1V5fK368dR1kZThB8J-TkSFUbaOmkK-zlDPehz4aFmV1khuLpqnPQc1ygcZSuLocA_H4e60F22DEH-HZODkXMB27OkXp3LpdLZz_0vpAqZH0EwNl_3avtMlKCkSfsJtyeO2X2bYDQuN0ca_t8woV2qQBbZYCU2yWsogpC4NyUwtxIZxjsDaiEggNTKxT_8H5hj1lOkNhDjH9m86sIr6NUKcG2IhTLVhfXKYxFcUIr8orGV4Oj3nFdS0ZBtoXzGI7ZjtZ8VTMsbFixU0Zpk0PKmwW3wRbNWjBqLkJws4TGttcsPxsgv_fcTelrqhQmTbcXB4r5lQGiTuzcOsMMG_bKaYIjpXpuUORtK6TtzooN3V1E_4x9Yk4KUsytWxcC9ryJCoAunSh9tt9d_XyaBuYYyqmNICsLgwJcdqYtyrH7QhNs1HFE3iT6NHnJAw0_4mDJka4-6iVkl4h9_xSqEckVDF9i_uBdGV2pD6zDPV_4mxCKL2NJjbX5J8F_jEBZxWtmf31bPMhi9o8DsFTCSRRLYbEeHbfqWhZtFTo8VzAMdkIg3n5YkFlhi7lMO-YLjEAi8CiRH-BcHXEvqcvPJVS3MrOqKQhRaW_pUAdN8Bc1uOa5GzWRcXCxRCZKMWpJbGHKQHsXDkyD2_2IWtmrArJ4PVOzEYvXSpNE9WV3JKTNvuMHwCqqTXC012Vzs_lpkhA3YQPxqRurg7kzMgoA0ENCSNwsYUudppJbMK1DjfcAIZ8nBhit3s6PFABTei_V_ZH2KmTBh4_Kle-kf7KgWPDmbr8uPsQlU3rXBEaykLxDubiPi2u5ftsO7NdW295YGE--BY-faux-kUt_JP5PtPk3jzEYomunHie3aj6Qhd4JUKod0L6g59KLBWN-yOgkIAJsELxwD6vq5j6Pountkipy7lYx_OlInRB-H5fF_WbnQMq62xHZqGceuViG16qK0SQi7-TuqM8leS0bYs-r9FyQgIi9PDynSZcZyKYjMkLOj0hKirUxq3C-zEqlxijJIdR2UX-Ke1a-dpEze7_iUrQQTjSA25S-aEUn8JGrdUyfSfR9wQyXkgppb5GhTWpyt_MFVhchhojJBCjm_Neq6rkibPij8z2fIHa4ZEjLozpgCN4b6LS29fgtKt0qsyYiZoc-fSAE8zbaNCS9NFYusDkDVVynygh4WhQD1HNeu2f3IT8ITbPLPSuWvtt6vGDMUUSQA3h-t_aF2tD4-nZx1x1TwA9hDow8eSqvqFqL8M2K4pO6CgnEDKcjNixd1UHH_Kd8UH0JrWCeIcVT6Svn19Xs7Xk2JIjimN5NFooHIGSir-54v3qxnkNuKtMAHadyScmRPl0ZrKRRjbn5KuiI5MjRgCI3oyaSTcOSRCHD02T9srNmgPAxL1yJsaQMYJWuZyelJMSOXWbsZm8vn7zE2h5ZHv3S-cbUHoQf4ya-iekJ9z1tsFz-LxWLkN4sLwlkfsTJECAPeRdEaZlJo-EKBguMGGoZ0gCiM6NCionPF0vV3okzbtDfMNBwQfZklhaUplp5yFt5KaNEBfPmGWHEd2VUbVLtuf8IkgPgLRc_SSWWUOy4h8mOTEVsOK23ZZ21jFD6UHcqWyWej_7NEI6fp2WenIqJ04WLUTezbeJKCAPm6r3IfH1bNqojqmVZLMAtaz7K5qHO5xF2uRoAQh2pb-O0UIM0eXXQsABv2WmRGV7pYQfcJoivTOy_iDEhqxOCgEH7m_tH6uSMdfaWu3PEG9MtPVj2Upv1EsyBxfcljSvSO9Uk3FKVDfrFsh5R1kPRr_nOHY75mCQG7c7OJpRh7bVufoJHa-xw8y_YBPDndF6z7wt-hE8CVp2f7Nyv_xYWRSirMlu6xf10aZQvW_d_2CfFTKJ8q6y2TzbBNghBBpXBsFVvH25QSS8AtJ42rVLg6NxGWyvXLwCUkwvf0rRCr-N2TpWtqxnKsV3Icpx5-W_ac21spXRpkfBuoKQwDT2ASad6URbF7QVFLlVqT4REkEgq1b4eCg__LWNeZebxIl_FNFnfZO_vIyWbU2VNJqZo34W1zFBkJ5yM1OZB_1scXRm8IjcSWRo9xkOcwvi1eeBx6Skxm-VlgfiPPp90RlFyt_ToMxCj0-rvDUAQTSVpH6es58VFvPeBA0fgEMpxQ9EDQYSE4kbDLwW5hKcvcEJrFWHB1-GgV1WhIcAt--Nl45hnEHAjZijAP6yA4ur3Q7Cel_sL1cS8Ty8s3l-EvrKWsluUkRt3_t14v2innT5dK467QJp99jxzz1f2OtmOKQLYrC-8UNqICZviOS5LvD9XL0MAfzRiJ2iLxRe4TokU6BhtVibXXlKhhwoaGpGEcAIp7LLI1Q24wzjeiORpSdpJSCsmspvP6YpJHyfyutK25vohfM_NDSnbiRK3ezCKLuI0HOsRjg8jZ90DFTuSrCoKB8-Gspp0BDa_hS9Gc0T6y7oJO-QpgbMJt7JSBmD62ROL3YHMrBse3ZlHUnTUN2YOgouQ55yNgM-ClysgNJAHv3XyKlr_wrA5K3BvFFBMICwnSXEhjBghOF0nsDNyJESGbzvtfNOuOrVNADuWlx6GgIqtonXZFtvYdHp-njGUB9kGLFLBw9P5TBe0ASDkPorCd1_RpS32dlvrO0Bo3Z2AgBf29CElshBNB8GrBnOXmuPGW5P2PJ2BWHprGaGcUDLphtz_5vYLRuUKqMcs_-5c9l4igBuRJhfKwqpMvJW15kC2uCvotqOhsUKyb-Jvq6LuukZ820mjCK1hxthv42Sm2zxdXqLL6kNSWzCIOpDcdPfikXSJsgELIHijJhbOWyDS4oK9HIRaE7G5C_gHLzWEbqrgdHUrIrwookJtNbp2__fb4bXKj94AwGC_yqWfWk9DKmM1qy8Lz7ct4pvFHzVz0mMkvy-MLFbf1z3XPGrG2Iwi1ujoZNWvfy-5JoKmPkGc0Rv_Ly_cDBA_dBLvPzwx-PjDiewk2FdRXo4rh9a6qgep_sj7wB36vuafCgIuQBHq73QBYGKT9ybNlOcSKcz9QAZ3UDCvCKCMNdjS8GIOpHYvqpkQy6m_XIML9K9MFdz9yXxJolNaHZd3corbSs83u0quDznA3onLDHYaPTiV_G1kILYUpolB7O71sjFM3fZRNKYo6xMN8zrPieOmSnaKIs4bsZ2Xpevw2_P3WZMWAvid5F_0suq8Bm5VADxA3N7pJYnbe34huY=', 'format': 'openai-responses-v1', 'id': 'rs_089fc12103e13ad20169b767c9a3088196932a5403e184300b', 'index': 0}]}}]
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Message content: C...
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 512
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 512
2026-03-15 23:15:13 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:13 - INFO - src.core.question_executor - API response indicates different model: requested=openai/gpt-5-mini, actual=openai/gpt-5-mini-2025-08-07
2026-03-15 23:15:13 - DEBUG - src.core.answer_parser - All letter matches: ['C'], filtered: ['C']
2026-03-15 23:15:13 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Answer parsing for question Q003: answer=C, confidence=low_confidence, raw_matches=['C']
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 512
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 512
2026-03-15 23:15:13 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=103, model_id=openai/gpt-5-mini
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:15:13 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=103, question_id=Q003, variant_id=var-03f2219a
2026-03-15 23:15:13 - INFO - src.db.repository - Response saved with ID 107
2026-03-15 23:15:13 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:15:13 - INFO - src.core.question_executor - Question Q003 completed: selected=C, correct=C, is_correct=True, latency=9478ms, structured_outputs=False
2026-03-15 23:15:13 - INFO - src.utils.progress - Progress: 3/4 (75.0%)
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315231413-e4dae222, variant=var-03f2219a, model=openai/gpt-5-mini, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 101, 'Q002': 102, 'Q003': 103, 'Q004': 104}}, reasoning_config=None
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Executing question Q004
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Using provided snapshot_id 104 for question Q004
2026-03-15 23:15:13 - DEBUG - src.core.randomizer - Randomized question Q004: original correct=D, new correct=B
2026-03-15 23:15:13 - DEBUG - src.core.question_executor - Randomized question Q004: correct answer changed from D to B
2026-03-15 23:15:13 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 23:15:13 - INFO - src.api.client - Sending API request: model=openai/gpt-5-mini, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 23:15:13 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 23:15:13 - DEBUG - src.api.client - Model: openai/gpt-5-mini, Messages: 1
2026-03-15 23:15:13 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 23:15:13 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C156DCC0>
2026-03-15 23:15:13 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x00000206C1465D00> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 23:15:13 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x00000206C0E4DA90>
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 23:15:13 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 23:15:14 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 02:15:46 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd04082e8ec4585-GRU')])
2026-03-15 23:15:14 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 23:15:14 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 23:15:18 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 23:15:18 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 23:15:18 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 23:15:18 - DEBUG - httpcore.connection - close.started
2026-03-15 23:15:18 - DEBUG - httpcore.connection - close.complete
2026-03-15 23:15:18 - INFO - src.api.client - API response: model=openai/gpt-5-mini, tokens=338, finish_reason=stop, status=200
2026-03-15 23:15:18 - DEBUG - src.api.client - Received response: id=gen-1773627346-ZV0Q8SCY1n3hHZ5t4l15
2026-03-15 23:15:18 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'completed', 'message': {'role': 'assistant', 'content': 'B', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'gAAAAABpt2fW_JLcBuZGHDVinhf-XDJxTm5dinhOpXYLcM7cSV2trl1nOV-vLgweXEzLef0SI-JJLBTE5IYgSLMaAt2CeGg9rZCpMZk4l5KaQjsp52MH0tiZ6wPV8VSRO2GqZTxBrBIViTjEcmM4YaNaM_qLjRP-pAoqhDQi0nbK2hzEhWMBGI69Gk5lYAH2BCtt8fDK-SL4DPKA1RP4Br4IHtVwZEWZSOMeZ3uajmcE2VXkO2pGlqbnk_dU2YVYf9E43aEa9x1CWO6sXW1P-e1R8CIo8chrmRDs2po6vhC5rpDxkyxHCMOnMdf8RUot2h61NniRzUPJ0NnoqYb-uBN7lVtJ1olY_QvzofXC4rydSWVKwpraQjBUwS6qiMeoAZKE24vWjnvMvsGGAR1YpZao-XKcmZmt1GkQvfk_MXiCOhuTLNDt5AHSqcm9xqQLQEUZGNAGd8-Nm3RlZ9wH89DTTO6s5_SbMk46sNwBRsP-liLX5Atc2UqP42c1T7xfkIcJ19Xqn0xGwUJP8f_FHGu808A_MOSdR6NX5D4C4_yrfokC8AGMtP1-0hpqZwwoqXUjcAdgS9jczo_bSOzb7sGJeY5zcnEfX0mM3UCZ36_8NZI0qgPuDsL6STp3xe9eH1h6VKZm88lWOixouLn7P5ExTM7MJydE4b525QKWv94xAYUhPXpMONwgOxPDGOHQAhxxNTRMj4B85QbeWoujRhzZgOsPMXp_SqzeHt-k0uXF9Ja1ESDQws6rce8jkfHm2lH0AKTyN_x7z_mGCM6wfjB7M-cS3VPtv0LGASUxXCGFAjOU1_NfIlrWTZYKC33qheCvwghkjJJ5HK6dZGGBr31x93MpSQaVNcK5x5qXk5ra6vfzbPXnldkWeP9YJn57TTFfK6EbA-JOqFtopvU4vNxPYoLWoeyx4dKtNT32NqKwt5uKaEvMKXwI2vewjKLXZemFW0FW_VQhFph2zmjxu_PDujJxXS7-eL2TWv528qexUYUiwPGZvUqvtWvX0wJ9nHMGgLsTyUvC0Oe8vqFC0tS4b72237JKpHOmUcoa2bZQLjaRmwhT2RkE3JZpfrXMi0x6i6n3er7YVL-_TNncT5gsA7TDjcISUuAwyY02r0unfXzS2JQCgoiTwJP_bvQ8RJGT8ofP3ceNxCBNDDgTZOFkcqkcdzU89PBhc9ik0UJHi2zzZRqq1XjpQ38CrvhW6z3mIHpgPg2pZFW2DNDYvft608jxw8ees8tsPLHs3TRg0CFr_b6lgRxiTlHH-fJjnaryZD-V5ySQ1TXCJzHJYKQ1jr6kd9jx3bT1BfRkBx6sS2Nb2tuFsrqfiOlxDG4E7quh4F_KUytQNYJ_IMf7dPSe-Q53cGvoptKyiibuceJEL_orxxndbDLdHCIwyGfAG1ejVWvNcXg_i_DfM7IJyrJP-revW4aCvK2dG8NJ-_uAszuDzvNVCeb2V2RgQQBGz9Rvk_t8BD8Gnc6R7YZWDj8I2U-yQQRraNHjTXjqIRMffzK2muEZdKM1VJVoYSdbpwxYqsyDy929JhhyV5DABSn6roTnizW8Zaok_2Jw5aA3Y6T-GSUPH7zL75_Ejm-fnbrpmER603pZZz5hRde76e888mzqp9J1iMQdTv79AxfJHVT0Q7Npg2Mc22GWAOknZpbVWQcfkC-nGp-tx7LaskbvU2I0mz7LID0LMvU7NjLDoFrWij9Zz3qrMyW-keFWVHdKLF4zhmMYkAxwU0La8f90fnCsUEPr_dIDf7BOXN2CNQ73hI0kSEJiC5t4hMBQWyh-FuPesYYYUnl_I_VwRozbP0-hCiZeGEyTp60CE8LoCDXzI5NgagR25oECp7Jql2AfUTmpBaLdRzSYB0i5lZ-nvsiPo7YiHE16mem2Q2gucEN2K1mqaO8uo3Z3sOunkrSVCuxjB87HvtTiQBSvE8FDAzoUl7rSLTCVY0MpTDM_rgeDzGOnXy_YLmTUKOHmOFTR-Zqrufrv6hKuJN576d_P_ymTn4k4ouPuVHh9oXCcz_M4601FTCjK-7E0ZZh85gIa6hk_xiHZ', 'format': 'openai-responses-v1', 'id': 'rs_0eb3a19eb973628d0169b767d3a9448190b813e18837c1fd10', 'index': 0}]}}]
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Message content: B...
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 192
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 192
2026-03-15 23:15:18 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:18 - INFO - src.core.question_executor - API response indicates different model: requested=openai/gpt-5-mini, actual=openai/gpt-5-mini-2025-08-07
2026-03-15 23:15:18 - DEBUG - src.core.answer_parser - All letter matches: ['B'], filtered: ['B']
2026-03-15 23:15:18 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Answer parsing for question Q004: answer=B, confidence=low_confidence, raw_matches=['B']
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 192
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 192
2026-03-15 23:15:18 - INFO - src.core.question_executor - Token usage
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315231413-e4dae222, snapshot_id=104, model_id=openai/gpt-5-mini
2026-03-15 23:15:18 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 23:15:18 - INFO - src.db.repository - Saving response: run_id=run-20260315231413-e4dae222, snapshot_id=104, question_id=Q004, variant_id=var-03f2219a
2026-03-15 23:15:18 - INFO - src.db.repository - Response saved with ID 108
2026-03-15 23:15:18 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 23:15:18 - INFO - src.core.question_executor - Question Q004 completed: selected=B, correct=B, is_correct=True, latency=4544ms, structured_outputs=False
2026-03-15 23:15:18 - INFO - src.utils.progress - Progress: 4/4 (100.0%)
2026-03-15 23:15:18 - INFO - src.core.iteration_executor - Iteration 1 completed: 4/4 pending questions, 0 skipped (already answered), 0 errors, 27163ms
2026-03-15 23:15:18 - DEBUG - src.core.execution_engine -     Completed: 4/4, Errors: 0, Duration: 27164ms
2026-03-15 23:15:18 - INFO - src.core.execution_engine - Execution completed: 2 iteration(s)
2026-03-15 23:15:18 - INFO - src.cli.experiment_commands - Run run-20260315231413-e4dae222 completed successfully