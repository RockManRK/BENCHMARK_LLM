2026-03-15 23:06:27 - INFO - src.main - BenchmarkRunner initialized
2026-03-15 23:06:27 - DEBUG - src.main - Arguments: Namespace(create_experiment=None, add_models=['openai/gpt-5-mini'], remove_model=None, add_questions=None, create_run=False, execute_run=False, models=None, run_id=None, iterations=1, questions=None, where=[], exclude=[], config=None, output='console', output_file=None, seed=None, verbose=False, dry_run=False, mode=None, experiment='nonteste', test_mode=False, vary_seed=False, temperature=None, max_tokens=None, top_p=None, top_k=None, repeat_penalty=None, reasoning_effort='low', enable_vision=True, enable_structured=None, add_to_run=None, complete_run=None, review_run=None, review_experiment=None, review_all=False, execution_mode='experiment', experiment_name='nonteste')
2026-03-15 23:06:27 - INFO - src.main - Set reasoning_effort from CLI: low
2026-03-15 23:06:27 - INFO - src.main - Set enable_vision from CLI: True
2026-03-15 23:06:27 - DEBUG - src.db.schema - Database initialized at data\benchmark.db
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - ExperimentManager initialized
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - Adding 1 models to experiment nonteste
2026-03-15 23:06:27 - DEBUG - src.cli.experiment_commands - Registered base model: openai/gpt-5-mini
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - Created variant: var-9a56c041
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - Associating variant var-9a56c041 with experiment exp-a7189910
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - Association successful
2026-03-15 23:06:27 - INFO - src.cli.experiment_commands - Registered variant: var-9a56c041 for model openai/gpt-5-mini
2026-03-15 23:06:27 - INFO - src.main - Models added successfully to experiment nonteste