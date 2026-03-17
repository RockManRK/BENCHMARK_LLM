📊 Database: data\benchmark.db
📋 Total tables: 10

===========

📁 TABLE: errors
----------
   Columns (9): error_id, run_id, question_id, model_id, variant_id, error_type, error_message, stack_trace, timestamp

   Detailed schema:
     • error_id: INTEGER [PRIMARY KEY]
     • run_id: TEXT
     • question_id: TEXT
     • model_id: TEXT
     • variant_id: TEXT
     • error_type: TEXT [NOT NULL]
     • error_message: TEXT [NOT NULL]
     • stack_trace: TEXT
     • timestamp: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: experiment_models
----------
   Columns (3): experiment_id, variant_id, added_at

   Detailed schema:
     • experiment_id: TEXT [PRIMARY KEY, NOT NULL]
     • variant_id: TEXT [PRIMARY KEY, NOT NULL]
     • added_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: experiments
----------
   Columns (8): experiment_id, name, description, config_json, config_hash, system_prompt_template, user_prompt_template, created_at

   Detailed schema:
     • experiment_id: TEXT [PRIMARY KEY]
     • name: TEXT [NOT NULL]
     • description: TEXT
     • config_json: TEXT [NOT NULL]
     • config_hash: TEXT [NOT NULL]
     • system_prompt_template: TEXT
     • user_prompt_template: TEXT
     • created_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: model_variants
----------
   Columns (9): variant_id, model_id, reasoning_mode, reasoning_effort, reasoning_max_tokens, vision_enabled, structured_enabled, variant_signature, created_at

   Detailed schema:
     • variant_id: TEXT [PRIMARY KEY]
     • model_id: TEXT [NOT NULL]
     • reasoning_mode: TEXT [NOT NULL, DEFAULT 'unspecified']
     • reasoning_effort: TEXT
     • reasoning_max_tokens: INTEGER
     • vision_enabled: BOOLEAN [NOT NULL, DEFAULT 0]
     • structured_enabled: BOOLEAN [NOT NULL, DEFAULT 0]
     • variant_signature: TEXT [NOT NULL]
     • created_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: models
----------
   Columns (6): model_id, provider, model_name, supports_multimodal, metadata_json, created_at

   Detailed schema:
     • model_id: TEXT [PRIMARY KEY]
     • provider: TEXT [NOT NULL]
     • model_name: TEXT [NOT NULL]
     • supports_multimodal: BOOLEAN [NOT NULL, DEFAULT 0]
     • metadata_json: TEXT
     • created_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: question_snapshots
----------
   Columns (5): snapshot_id, experiment_id, question_id, question_json, created_at

   Detailed schema:
     • snapshot_id: INTEGER [PRIMARY KEY]
     • experiment_id: TEXT [NOT NULL]
     • question_id: TEXT [NOT NULL]
     • question_json: TEXT [NOT NULL]
     • created_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]


📁 TABLE: questions
----------
   Columns (7): question_id, stem, options_json, correct_answer, has_image, image_path, status

   Detailed schema:
     • question_id: TEXT [PRIMARY KEY]
     • stem: TEXT [NOT NULL]
     • options_json: TEXT [NOT NULL]
     • correct_answer: TEXT
     • has_image: BOOLEAN [NOT NULL, DEFAULT 0]
     • image_path: TEXT
     • status: TEXT [NOT NULL, DEFAULT 'active']


📁 TABLE: responses
----------
   Columns (26): response_id, run_id, snapshot_id, question_id, model_id, variant_id, iteration, selected_answer, response_text, is_correct, status, finish_reason, error_details, latency_ms, input_tokens, response_tokens, total_tokens, reasoning_tokens, effective_tokens, cost, raw_response_json, timestamp, parse_confidence, review_status, reviewed_at, manual_answer

   Detailed schema:
     • response_id: INTEGER [PRIMARY KEY]
     • run_id: TEXT [NOT NULL]
     • snapshot_id: INTEGER [NOT NULL]
     • question_id: TEXT [NOT NULL]
     • model_id: TEXT [NOT NULL]
     • variant_id: TEXT
     • iteration: INTEGER [NOT NULL, DEFAULT 1]
     • selected_answer: TEXT
     • response_text: TEXT
     • is_correct: BOOLEAN
     • status: TEXT [NOT NULL, DEFAULT 'pending']
     • finish_reason: TEXT
     • error_details: TEXT
     • latency_ms: INTEGER
     • input_tokens: INTEGER
     • response_tokens: INTEGER
     • total_tokens: INTEGER
     • reasoning_tokens: INTEGER
     • effective_tokens: INTEGER
     • cost: REAL
     • raw_response_json: TEXT
     • timestamp: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]
     • parse_confidence: TEXT [NOT NULL, DEFAULT 'unknown']
     • review_status: TEXT [NOT NULL, DEFAULT 'auto']
     • reviewed_at: TIMESTAMP
     • manual_answer: TEXT


📁 TABLE: run_models
----------
   Columns (5): run_id, variant_id, status, added_at, completed_at

   Detailed schema:
     • run_id: TEXT [PRIMARY KEY, NOT NULL]
     • variant_id: TEXT [PRIMARY KEY, NOT NULL]
     • status: TEXT [NOT NULL, DEFAULT 'pending']
     • added_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]
     • completed_at: TIMESTAMP


📁 TABLE: runs
----------
   Columns (7): run_id, experiment_id, seed, is_dev, started_at, finished_at, status

   Detailed schema:
     • run_id: TEXT [PRIMARY KEY]
     • experiment_id: TEXT
     • seed: INTEGER
     • is_dev: BOOLEAN [NOT NULL, DEFAULT 0]
     • started_at: TIMESTAMP [DEFAULT CURRENT_TIMESTAMP]
     • finished_at: TIMESTAMP
     • status: TEXT [NOT NULL, DEFAULT 'pending']

===========
✅ Done!