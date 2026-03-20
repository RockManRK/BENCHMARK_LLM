"""Package initialization for src_v2.core.

This module contains the core domain logic of the TO-BE architecture,
including immutable data structures and execution orchestration.
"""

from src_v2.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)

from src_v2.core.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
)

from src_v2.core.randomizer import (
    AnswerRandomizer,
)

from src_v2.core.answer_parser import (
    AnswerParser,
    ParsedAnswer,
)

from src_v2.core.result_writer import (
    ResultWriter,
    WriteReport,
)

from src_v2.core.planner import (
    Planner,
    PlannerValidationError,
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
]
