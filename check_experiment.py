#!/usr/bin/env python3
"""Check saved experiment config."""

from src.cli.database import get_database_connection
from src.db.repository import ExperimentRepository
import json

conn = get_database_connection()
repo = ExperimentRepository(conn)
exp = repo.get_by_name('test_seed_null')

config = json.loads(exp.config_json) if exp.config_json else {}
print(f'Experiment: {exp.name}')
print(f'RUN_RESPONSES_SEED: {config.get("RUN_RESPONSES_SEED")}')
print(f'SYSTEM_PROMPT: {repr(config.get("SYSTEM_PROMPT"))}')
print(f'MODEL_TOP_K: {config.get("MODEL_TOP_K")}')
print(f'MODEL_TEMPERATURE: {config.get("MODEL_TEMPERATURE")}')

conn.close()
