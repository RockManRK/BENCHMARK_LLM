"""TO-BE database layer.

Exports:
- schema: create_schema(), get_schema_sql()
- models: Experiment, ModelVariant, QuestionSnapshot, Run, Response
- repository: ExperimentRepository, VariantRepository, SnapshotRepository,
              RunRepository, ResponseRepository

Note:
    ErrorRepository and Error dataclass have been removed. ResultWriter is the
    sole writer for the errors table. Tests must use ResultWriter.write_result()
    to create error rows.
"""

from src.db.schema import create_schema, get_schema_sql
from src.db.models import (
    Experiment,
    ModelVariant,
    QuestionSnapshot,
    Run,
    Response,
)
from src.db.repository import (
    ExperimentRepository,
    VariantRepository,
    SnapshotRepository,
    RunRepository,
    ResponseRepository,
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
    # Repositories
    "ExperimentRepository",
    "VariantRepository",
    "SnapshotRepository",
    "RunRepository",
    "ResponseRepository",
]
