2026-03-15 22:19:11 - INFO - src.main - BenchmarkRunner initialized
2026-03-15 22:19:11 - DEBUG - src.main - Arguments: Namespace(create_experiment='oitteste', add_models=None, remove_model=None, add_questions=None, create_run=False, execute_run=False, models=None, run_id=None, iterations=1, questions=None, where=[], exclude=[], config=None, output='console', output_file=None, seed=None, verbose=False, dry_run=False, mode=None, experiment=None, test_mode=False, vary_seed=False, temperature=None, max_tokens=None, top_p=None, top_k=None, repeat_penalty=None, reasoning_effort=None, enable_vision=None, enable_structured=None, add_to_run=None, complete_run=None, review_run=None, review_experiment=None, review_all=False, execution_mode='dev', experiment_name=None)
2026-03-15 22:19:11 - DEBUG - src.db.schema - Database initialized at data\benchmark.db
2026-03-15 22:19:11 - INFO - src.cli.experiment_commands - ExperimentManager initialized
2026-03-15 22:19:11 - INFO - src.cli.experiment_commands - Created experiment: oitteste (hash=375c4741b341e3e7)
2026-03-15 22:19:11 - INFO - src.core.loader - Loaded 100 questions from data\enamed_questions.json
2026-03-15 22:19:12 - INFO - src.cli.experiment_commands - No questions specified, using all 100 available questions from data\enamed_questions.json
2026-03-15 22:19:12 - INFO - src.db.repository - Created snapshot 1 for experiment=exp-a68530c1, question=Q001
2026-03-15 22:19:12 - INFO - src.db.repository - Created snapshot 2 for experiment=exp-a68530c1, question=Q002
2026-03-15 22:19:12 - INFO - src.db.repository - Created snapshot 3 for experiment=exp-a68530c1, question=Q003
[...] (Criando snapshots das perguntas de 001 até 100)
2026-03-15 22:19:13 - INFO - src.db.repository - Created snapshot 98 for experiment=exp-a68530c1, question=Q098
2026-03-15 22:19:13 - INFO - src.db.repository - Created snapshot 99 for experiment=exp-a68530c1, question=Q099
2026-03-15 22:19:13 - INFO - src.db.repository - Created snapshot 100 for experiment=exp-a68530c1, question=Q100
2026-03-15 22:19:13 - INFO - src.cli.experiment_commands - Created 100 question snapshots for experiment oitteste