#!/usr/bin/env python3
"""Check experiment config for top-k null test."""

from src.cli.database import get_database_connection
from src.db.repository import ExperimentRepository
import json

conn = get_database_connection()
repo = ExperimentRepository(conn)
exp = repo.get_by_name('test_topk_null')

config = json.loads(exp.config_json) if exp.config_json else {}
print(f'Experiment: {exp.name}')
print(f'MODEL_TOP_K: {config.get("MODEL_TOP_K")} (should be None/.env fallback)')
print(f'MODEL_TEMPERATURE: {config.get("MODEL_TEMPERATURE")}')
print(f'MODEL_TOP_P: {config.get("MODEL_TOP_P")}')

conn.close()
