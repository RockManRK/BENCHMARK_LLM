"""TO-BE database layer.

Exports:
- schema: create_schema(), get_schema_sql()
- models: Experiment, ModelVariant, QuestionSnapshot, Run, Response, Error
- repository: ExperimentRepository, VariantRepository, SnapshotRepository,
              RunRepository, ResponseRepository, ErrorRepository
"""

from src_v2.db.schema import create_schema, get_schema_sql
from src_v2.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
    Error,
)
from src_v2.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
    ErrorRepository,
)

__all__ = [
    # Schema
    "create_schema",
    "get_schema_sql",
    # Models
    "Experiment",
    "ModelVariant",
    "QuestionSnapshot",
    "Run",
    "Response",
    "Error",
    # Repositories
    "ExperimentRepository",
    "VariantRepository",
    "SnapshotRepository",
    "RunRepository",
    "ResponseRepository",
    "ErrorRepository",
]
