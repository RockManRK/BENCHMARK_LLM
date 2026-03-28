"""Package initialization for src.core.

This module contains the core domain logic of the TO-BE architecture,
including immutable data structures and execution orchestration.
"""

from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)

from src.core.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
)

from src.core.randomizer import (
    AnswerRandomizer,
)

from src.core.answer_parser import (
    AnswerParser,
    ParsedAnswer,
)

from src.core.result_writer import (
    ResultWriter,
    WriteReport,
)

from src.core.planner import (
    Planner,
    PlannerValidationError,
)

from src.core.config_resolver import (
    ConfigResolver,
)

from src.core.question_loader import (
    QuestionLoader,
)

from src.core.argv_utils import (
    parse_args_normalized,
    normalize_nulls,
)

__all__ = [
    # Execution Plan
    'ExecutionPlan',
    'PlanRun',
    'PlanItem',
    'PlanVariant',
    'Prompts',
    'RetryPolicy',
    'ModelConfig',
    'QuestionPayload',
    # Execution Engine
    'ExecutionEngine',
    'ExecutionResult',
    # Randomizer
    'AnswerRandomizer',
    # Parser
    'AnswerParser',
    'ParsedAnswer',
    # Result Writer
    'ResultWriter',
    'WriteReport',
    # Planner
    'Planner',
    'PlannerValidationError',
    # Config Resolver
    'ConfigResolver',
    # Question Loader
    'QuestionLoader',
    # Argv Utils
    'parse_args_normalized',
    'normalize_nulls',
]
