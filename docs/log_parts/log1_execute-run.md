2026-03-15 22:27:37 - INFO - src.main - BenchmarkRunner initialized
2026-03-15 22:27:37 - DEBUG - src.main - Arguments: Namespace(create_experiment=None, add_models=None, remove_model=None, add_questions=None, create_run=False, execute_run=True, models=None, run_id=None, iterations=1, questions=None, where=[], exclude=[], config=None, output='console', output_file=None, seed=None, verbose=False, dry_run=False, mode=None, experiment='oitteste', test_mode=False, vary_seed=False, temperature=None, max_tokens=None, top_p=None, top_k=None, repeat_penalty=None, reasoning_effort=None, enable_vision=None, enable_structured=None, add_to_run=None, complete_run=None, review_run=None, review_experiment=None, review_all=False, execution_mode='experiment', experiment_name='oitteste')
2026-03-15 22:27:37 - DEBUG - src.db.schema - Database initialized at data\benchmark.db
2026-03-15 22:27:37 - INFO - src.cli.experiment_commands - RunManager initialized
2026-03-15 22:27:37 - INFO - src.cli.experiment_commands - Executing run run-20260315222541-f47e3c31 for experiment oitteste
2026-03-15 22:27:38 - INFO - src.api.client - OpenRouterClient initialized with base_url=https://openrouter.ai/api/v1
2026-03-15 22:27:38 - DEBUG - src.core.randomizer - AnswerRandomizer initialized with seed AUTO
2026-03-15 22:27:38 - DEBUG - src.core.execution_engine - ExecutionEngine initialized
2026-03-15 22:27:38 - INFO - src.core.execution_engine - Starting execution: 2 model(s), 100 question(s), 1 iteration(s)
2026-03-15 22:27:38 - INFO - src.core.execution_engine - Executing model variant: var-5eb0bdca
2026-03-15 22:27:38 - DEBUG - src.core.execution_engine -   Iteration 1/1
2026-03-15 22:27:38 - INFO - src.core.iteration_executor - IterationExecutor initialized for run=run-20260315222541-f47e3c31, model=google/gemini-3.1-flash-lite-preview, iteration=1, experiment_id=exp-a68530c1, reasoning_config=None
2026-03-15 22:27:38 - INFO - src.core.iteration_executor - Starting iteration 1 for model google/gemini-3.1-flash-lite-preview with 100 pending questions (0 already answered)
2026-03-15 22:27:38 - INFO - src.utils.progress - ProgressTracker initialized: total=100, run=run-20260315222541-f47e3c31, model=google/gemini-3.1-flash-lite-preview, iteration=1
2026-03-15 22:27:38 - DEBUG - src.utils.progress - Progress tracking started for run-20260315222541-f47e3c31
2026-03-15 22:27:38 - DEBUG - asyncio - Using proactor: IocpProactor
2026-03-15 22:27:38 - INFO - src.core.iteration_executor - Registered model variant: var-4fadde11 | model=google/gemini-3.1-flash-lite-preview | signature=google/gemini-3.1-flash-lite-preview::reasoning=unspecified::vision=true::structured=false
2026-03-15 22:27:38 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315222541-f47e3c31, variant=var-4fadde11, model=google/gemini-3.1-flash-lite-preview, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 1, 'Q002': 2, 'Q003': 3,
[...] (Listando snapshots de 1 até 100)
 'Q097': 97, 'Q098': 98, 'Q099': 99, 'Q100': 100}}, reasoning_config=None
2026-03-15 22:27:38 - DEBUG - src.core.question_executor - Executing question Q001
2026-03-15 22:27:38 - DEBUG - src.core.question_executor - Using provided snapshot_id 1 for question Q001
2026-03-15 22:27:38 - DEBUG - src.core.randomizer - Randomized question Q001: original correct=A, new correct=D
2026-03-15 22:27:38 - DEBUG - src.core.question_executor - Randomized question Q001: correct answer changed from A to D
2026-03-15 22:27:38 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 22:27:38 - INFO - src.api.client - Sending API request: model=google/gemini-3.1-flash-lite-preview, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 22:27:38 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 22:27:38 - DEBUG - src.api.client - Model: google/gemini-3.1-flash-lite-preview, Messages: 1
2026-03-15 22:27:38 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 22:27:38 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6A8ABB60>
2026-03-15 22:27:38 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x000001DC6A742060> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 22:27:38 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6A8ADD10>
2026-03-15 22:27:38 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 22:27:38 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 22:27:38 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 22:27:38 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 22:27:38 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 01:28:13 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dcffacb8b945573-GRU')])
2026-03-15 22:27:40 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 22:27:40 - DEBUG - httpcore.connection - close.started
2026-03-15 22:27:40 - DEBUG - httpcore.connection - close.complete
2026-03-15 22:27:40 - INFO - src.api.client - API response: model=google/gemini-3.1-flash-lite-preview, tokens=293, finish_reason=stop, status=200
2026-03-15 22:27:40 - DEBUG - src.api.client - Received response: id=gen-1773624491-D7P5zcekbCfM93abTjyo
2026-03-15 22:27:40 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'D', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'AY89a1/pZA2ZGf9YlCZzZ5EOSQEikXLjr3/KJb7qFHIrb47yqs5wZkK9BEOQAEZzQMs=', 'format': 'google-gemini-v1', 'index': 0}]}}]
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Message content: D...
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:27:40 - INFO - src.core.question_executor - Token usage
2026-03-15 22:27:40 - INFO - src.core.question_executor - API response indicates different model: requested=google/gemini-3.1-flash-lite-preview, actual=google/gemini-3.1-flash-lite-preview-20260303
2026-03-15 22:27:40 - DEBUG - src.core.answer_parser - All letter matches: ['D'], filtered: ['D']
2026-03-15 22:27:40 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Answer parsing for question Q001: answer=D, confidence=low_confidence, raw_matches=['D']
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:27:40 - INFO - src.core.question_executor - Token usage
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315222541-f47e3c31, snapshot_id=1, model_id=google/gemini-3.1-flash-lite-preview
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 22:27:40 - INFO - src.db.repository - Saving response: run_id=run-20260315222541-f47e3c31, snapshot_id=1, question_id=Q001, variant_id=var-4fadde11
2026-03-15 22:27:40 - INFO - src.db.repository - Response saved with ID 1
2026-03-15 22:27:40 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 22:27:40 - INFO - src.core.question_executor - Question Q001 completed: selected=D, correct=D, is_correct=True, latency=2665ms, structured_outputs=False
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315222541-f47e3c31, variant=var-4fadde11, model=google/gemini-3.1-flash-lite-preview, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 1, 'Q002': 2, 'Q003': 3, 'Q004': 4, 'Q005': 5, 'Q006': 6,
[...] (Listando snapshots de 1 até 100)
'Q098': 98, 'Q099': 99, 'Q100': 100}}, reasoning_config=None
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Executing question Q002
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Using provided snapshot_id 2 for question Q002
2026-03-15 22:27:40 - DEBUG - src.core.randomizer - Randomized question Q002: original correct=B, new correct=A
2026-03-15 22:27:40 - DEBUG - src.core.question_executor - Randomized question Q002: correct answer changed from B to A
2026-03-15 22:27:40 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 22:27:40 - INFO - src.api.client - Sending API request: model=google/gemini-3.1-flash-lite-preview, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 22:27:40 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 22:27:40 - DEBUG - src.api.client - Model: google/gemini-3.1-flash-lite-preview, Messages: 1
2026-03-15 22:27:40 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 22:27:40 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6A8AF890>
2026-03-15 22:27:40 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x000001DC6A742060> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 22:27:40 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6A8B1940>
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 22:27:40 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 22:27:43 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 01:28:16 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dcffadc4836f450-GRU')])
2026-03-15 22:27:43 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 22:27:43 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 22:27:43 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 22:27:43 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 22:27:43 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 22:27:43 - DEBUG - httpcore.connection - close.started
2026-03-15 22:27:43 - DEBUG - httpcore.connection - close.complete
2026-03-15 22:27:43 - INFO - src.api.client - API response: model=google/gemini-3.1-flash-lite-preview, tokens=172, finish_reason=stop, status=200
2026-03-15 22:27:43 - DEBUG - src.api.client - Received response: id=gen-1773624493-tVHrJ7dSP3HdumJYl6LY
2026-03-15 22:27:43 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'A', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'AY89a19+O/+FbUosbKwpe0nZr57LdcnY7OOOePHXZ6MP9ZyiB5OnWIrvHvrFiRTzHFI=', 'format': 'google-gemini-v1', 'index': 0}]}}]
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Message content: A...
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:27:43 - INFO - src.core.question_executor - Token usage
2026-03-15 22:27:43 - INFO - src.core.question_executor - API response indicates different model: requested=google/gemini-3.1-flash-lite-preview, actual=google/gemini-3.1-flash-lite-preview-20260303
2026-03-15 22:27:43 - DEBUG - src.core.answer_parser - All letter matches: ['A'], filtered: ['A']
2026-03-15 22:27:43 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Answer parsing for question Q002: answer=A, confidence=low_confidence, raw_matches=['A']
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:27:43 - INFO - src.core.question_executor - Token usage
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315222541-f47e3c31, snapshot_id=2, model_id=google/gemini-3.1-flash-lite-preview
2026-03-15 22:27:43 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 22:27:43 - INFO - src.db.repository - Saving response: run_id=run-20260315222541-f47e3c31, snapshot_id=2, question_id=Q002, variant_id=var-4fadde11
2026-03-15 22:27:43 - INFO - src.db.repository - Response saved with ID 2
2026-03-15 22:27:43 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 22:27:43 - INFO - src.core.question_executor - Question Q002 completed: selected=A, correct=A, is_correct=True, latency=2854ms, structured_outputs=False

[...] (Requisições das perguntas 3 até 54 deletadas do log para economia de memória)

2026-03-15 22:29:39 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315222541-f47e3c31, variant=var-4fadde11, model=google/gemini-3.1-flash-lite-preview, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 1, 'Q002': 2, 'Q003': 3, 'Q004': 4,
[...] (Listando snapshots de 1 até 100)
'Q098': 98, 'Q099': 99, 'Q100': 100}}, reasoning_config=None
2026-03-15 22:29:39 - DEBUG - src.core.question_executor - Executing question Q055
2026-03-15 22:29:39 - DEBUG - src.core.question_executor - Using provided snapshot_id 55 for question Q055
2026-03-15 22:29:39 - ERROR - src.core.randomizer - Correct answer text '' not found in options
2026-03-15 22:29:39 - ERROR - src.core.question_executor - Unexpected error for question Q055: Correct answer not found in randomized options
Traceback (most recent call last):
  File "D:\OneDrive\Pessoais\Projetos\benchmark_llm\src\core\question_executor.py", line 221, in execute_question
    randomized_question = self._randomizer.randomize(question)
  File "D:\OneDrive\Pessoais\Projetos\benchmark_llm\src\core\randomizer.py", line 92, in randomize
    new_correct_answer = self._find_correct_letter(new_options, correct_answer_text)
  File "D:\OneDrive\Pessoais\Projetos\benchmark_llm\src\core\randomizer.py", line 157, in _find_correct_letter
    raise ValueError("Correct answer not found in randomized options")
ValueError: Correct answer not found in randomized options
2026-03-15 22:29:39 - INFO - src.db.repository - Saving response: run_id=run-20260315222541-f47e3c31, snapshot_id=55, question_id=Q055, variant_id=var-4fadde11
2026-03-15 22:29:39 - INFO - src.db.repository - Response saved with ID 55
2026-03-15 22:29:39 - WARNING - src.core.iteration_executor - Question Q055 failed: Correct answer not found in randomized options

[...] (Requisições das perguntas 56 até 98 deletadas do log para economia de memória)

2026-03-15 22:31:11 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315222541-f47e3c31, variant=var-4fadde11, model=google/gemini-3.1-flash-lite-preview, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 1, 'Q002': 2, 'Q003': 3, 'Q004': 4, 'Q005': 5, 'Q006': 6,
[...] (Listando snapshots de 1 até 100)
'Q098': 98, 'Q099': 99, 'Q100': 100}}, reasoning_config=None
2026-03-15 22:31:11 - DEBUG - src.core.question_executor - Executing question Q099
2026-03-15 22:31:11 - DEBUG - src.core.question_executor - Using provided snapshot_id 99 for question Q099
2026-03-15 22:31:11 - DEBUG - src.core.randomizer - Randomized question Q099: original correct=A, new correct=B
2026-03-15 22:31:11 - DEBUG - src.core.question_executor - Randomized question Q099: correct answer changed from A to B
2026-03-15 22:31:11 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 22:31:11 - INFO - src.api.client - Sending API request: model=google/gemini-3.1-flash-lite-preview, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 22:31:11 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 22:31:11 - DEBUG - src.api.client - Model: google/gemini-3.1-flash-lite-preview, Messages: 1
2026-03-15 22:31:11 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 22:31:11 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6BA7EDF0>
2026-03-15 22:31:11 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x000001DC6A742060> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 22:31:11 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6BA7EDA0>
2026-03-15 22:31:11 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 22:31:11 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 22:31:11 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 22:31:11 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 22:31:11 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 500, b'Internal Server Error', [(b'Date', b'Mon, 16 Mar 2026 01:31:49 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd00002af0d01a1-GRU')])
2026-03-15 22:31:16 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 500 Internal Server Error"
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 22:31:16 - DEBUG - httpcore.connection - close.started
2026-03-15 22:31:16 - DEBUG - httpcore.connection - close.complete
2026-03-15 22:31:16 - ERROR - src.api.client - API error 500: model=google/gemini-3.1-flash-lite-preview, message=Internal Server Error
2026-03-15 22:31:16 - ERROR - src.api.client - Error response body: {"error":{"message":"Internal Server Error","code":500}}
2026-03-15 22:31:16 - ERROR - src.core.question_executor - HTTP error for question Q099: 500 - API error: Internal Server Error
2026-03-15 22:31:16 - DEBUG - src.api.error_handler - Normalized error: type=server_error, status=500, message=Internal Server Error
2026-03-15 22:31:16 - INFO - src.db.repository - Saving response: run_id=run-20260315222541-f47e3c31, snapshot_id=99, question_id=Q099, variant_id=var-4fadde11
2026-03-15 22:31:16 - INFO - src.db.repository - Response saved with ID 99
2026-03-15 22:31:16 - WARNING - src.core.iteration_executor - Question Q099 failed: API error: Internal Server Error
2026-03-15 22:31:16 - DEBUG - src.core.question_executor - QuestionExecutor initialized for run=run-20260315222541-f47e3c31, variant=var-4fadde11, model=google/gemini-3.1-flash-lite-preview, iteration=1, use_structured_outputs=False, enable_vision=True, model_kwargs={'_snapshot_ids': {'Q001': 1, 'Q002': 2, 'Q003': 3, 'Q004': 4, 'Q005': 5,
[...] (Listando snapshots de 1 até 100)
'Q098': 98, 'Q099': 99, 'Q100': 100}}, reasoning_config=None
2026-03-15 22:31:16 - DEBUG - src.core.question_executor - Executing question Q100
2026-03-15 22:31:16 - DEBUG - src.core.question_executor - Using provided snapshot_id 100 for question Q100
2026-03-15 22:31:16 - DEBUG - src.core.randomizer - Randomized question Q100: original correct=A, new correct=D
2026-03-15 22:31:16 - DEBUG - src.core.question_executor - Randomized question Q100: correct answer changed from A to D
2026-03-15 22:31:16 - INFO - src.api.client - Debug mode enabled: capturing request payload and upstream body
2026-03-15 22:31:16 - INFO - src.api.client - Sending API request: model=google/gemini-3.1-flash-lite-preview, max_tokens=None, temperature=None, structured_output=False, debug=True
2026-03-15 22:31:16 - DEBUG - src.api.client - Sending chat completion request to https://openrouter.ai/api/v1/chat/completions
2026-03-15 22:31:16 - DEBUG - src.api.client - Model: google/gemini-3.1-flash-lite-preview, Messages: 1
2026-03-15 22:31:16 - DEBUG - httpcore.connection - connect_tcp.started host='openrouter.ai' port=443 local_address=None timeout=180.0 socket_options=None
2026-03-15 22:31:16 - DEBUG - httpcore.connection - connect_tcp.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6BA990E0>
2026-03-15 22:31:16 - DEBUG - httpcore.connection - start_tls.started ssl_context=<ssl.SSLContext object at 0x000001DC6A742060> server_hostname='openrouter.ai' timeout=180.0
2026-03-15 22:31:16 - DEBUG - httpcore.connection - start_tls.complete return_value=<httpcore._backends.anyio.AnyIOStream object at 0x000001DC6BA991D0>
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - send_request_headers.started request=<Request [b'POST']>
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - send_request_headers.complete
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - send_request_body.started request=<Request [b'POST']>
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - send_request_body.complete
2026-03-15 22:31:16 - DEBUG - httpcore.http11 - receive_response_headers.started request=<Request [b'POST']>
2026-03-15 22:31:19 - DEBUG - httpcore.http11 - receive_response_headers.complete return_value=(b'HTTP/1.1', 200, b'OK', [(b'Date', b'Mon, 16 Mar 2026 01:31:52 GMT'), (b'Content-Type', b'application/json'), (b'Transfer-Encoding', b'chunked'), (b'Connection', b'keep-alive'), (b'Access-Control-Allow-Origin', b'*'), (b'Permissions-Policy', b'payment=(self "https://checkout.stripe.com" "https://connect-js.stripe.com" "https://js.stripe.com" "https://*.js.stripe.com" "https://hooks.stripe.com")'), (b'Referrer-Policy', b'no-referrer, strict-origin-when-cross-origin'), (b'X-Content-Type-Options', b'nosniff'), (b'Content-Encoding', b'gzip'), (b'Server', b'cloudflare'), (b'CF-RAY', b'9dd00022aa551af2-GRU')])
2026-03-15 22:31:19 - INFO - httpx - HTTP Request: POST https://openrouter.ai/api/v1/chat/completions "HTTP/1.1 200 OK"
2026-03-15 22:31:19 - DEBUG - httpcore.http11 - receive_response_body.started request=<Request [b'POST']>
2026-03-15 22:31:19 - DEBUG - httpcore.http11 - receive_response_body.complete
2026-03-15 22:31:19 - DEBUG - httpcore.http11 - response_closed.started
2026-03-15 22:31:19 - DEBUG - httpcore.http11 - response_closed.complete
2026-03-15 22:31:19 - DEBUG - httpcore.connection - close.started
2026-03-15 22:31:19 - DEBUG - httpcore.connection - close.complete
2026-03-15 22:31:19 - INFO - src.api.client - API response: model=google/gemini-3.1-flash-lite-preview, tokens=127, finish_reason=stop, status=200
2026-03-15 22:31:19 - DEBUG - src.api.client - Received response: id=gen-1773624709-0YUL1mYRPjSHpQokPGSt
2026-03-15 22:31:19 - DEBUG - src.api.client - Debug mode: captured request payload and upstream_body
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Debug mode detected: extracting response from wrapper
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - FULL API RESPONSE: choices=[{'index': 0, 'logprobs': None, 'finish_reason': 'stop', 'native_finish_reason': 'STOP', 'message': {'role': 'assistant', 'content': 'D', 'refusal': None, 'reasoning': None, 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': 'AY89a1+AJWYJ2UEW9wgyTGEN8NPc2V/478L6BTiMDguCsWgEYgw5GvwYCGQTMu7UjbI=', 'format': 'google-gemini-v1', 'index': 0}]}}]
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Message content: D...
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:31:19 - INFO - src.core.question_executor - Token usage
2026-03-15 22:31:19 - INFO - src.core.question_executor - API response indicates different model: requested=google/gemini-3.1-flash-lite-preview, actual=google/gemini-3.1-flash-lite-preview-20260303
2026-03-15 22:31:19 - DEBUG - src.core.answer_parser - All letter matches: ['D'], filtered: ['D']
2026-03-15 22:31:19 - DEBUG - src.core.answer_parser - Matched fallback pattern with filtered matches
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Answer parsing for question Q100: answer=D, confidence=low_confidence, raw_matches=['D']
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Debug mode detected in _extract_token_usage: extracting response from wrapper
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Extracted reasoning_tokens from completion_tokens_details: 0
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - reasoning_tokens extracted: 0
2026-03-15 22:31:19 - INFO - src.core.question_executor - Token usage
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Debug mode detected in _extract_reasoning_details: extracting response from wrapper
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Extracted reasoning_details: 1 items
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Creating response: run_id=run-20260315222541-f47e3c31, snapshot_id=100, model_id=google/gemini-3.1-flash-lite-preview
2026-03-15 22:31:19 - DEBUG - src.core.question_executor - Response object created, saving to DB
2026-03-15 22:31:19 - INFO - src.db.repository - Saving response: run_id=run-20260315222541-f47e3c31, snapshot_id=100, question_id=Q100, variant_id=var-4fadde11
2026-03-15 22:31:19 - INFO - src.db.repository - Response saved with ID 100
2026-03-15 22:31:19 - INFO - src.core.question_executor - Response saved successfully
2026-03-15 22:31:19 - INFO - src.core.question_executor - Question Q100 completed: selected=D, correct=D, is_correct=True, latency=3051ms, structured_outputs=False
2026-03-15 22:31:19 - INFO - src.utils.progress - Progress: 100/100 (100.0%)
2026-03-15 22:31:19 - INFO - src.core.iteration_executor - Iteration 1 completed: 98/100 pending questions, 0 skipped (already answered), 2 errors, 221854ms
2026-03-15 22:31:19 - DEBUG - src.core.execution_engine -     Completed: 98/100, Errors: 2, Duration: 221855ms
2026-03-15 22:31:19 - INFO - src.core.execution_engine - Executing model variant: var-93517b5b
2026-03-15 22:31:19 - DEBUG - src.core.execution_engine -   Iteration 1/1
2026-03-15 22:31:19 - INFO - src.core.iteration_executor - IterationExecutor initialized for run=run-20260315222541-f47e3c31, model=google/gemini-3.1-flash-lite-preview, iteration=1, experiment_id=exp-a68530c1, reasoning_config=None
2026-03-15 22:31:19 - INFO - src.core.iteration_executor - Variant var-4fadde11: 100/100 questions already answered in iteration 1, executing 0 pending
2026-03-15 22:31:19 - INFO - src.core.iteration_executor - Iteration 1 for model google/gemini-3.1-flash-lite-preview: All questions already answered, skipping execution
2026-03-15 22:31:19 - DEBUG - src.core.execution_engine -     Completed: 0/100, Errors: 0, Duration: 7ms
2026-03-15 22:31:19 - INFO - src.core.execution_engine - Execution completed: 2 iteration(s)
2026-03-15 22:31:19 - WARNING - src.cli.experiment_commands - Run run-20260315222541-f47e3c31 completed with 2 errors