"""Question loader module for benchmark_llm project.

This module provides functionality to load and validate JSON questionnaire
files using pydantic for schema validation.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.db.models import Question

logger = logging.getLogger(__name__)


class MetaData(BaseModel):
    """Pydantic model for question metadata validation.

    Attributes:
        has_table: Whether the question contains a table.
        has_image: Whether the question has an associated image.
        status: Question status (valid or annulled).
        notes: Additional notes about the question.
    """

    has_table: bool = Field(..., description="Whether the question contains a table")
    has_image: bool = Field(..., description="Whether the question has an associated image")
    status: str = Field(..., description="Question status (valid or annulled)")
    notes: str = Field(default="", description="Additional notes about the question")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate that status is either 'valid' or 'annulled'."""
        if v not in ("valid", "annulled"):
            raise ValueError(f"Status must be 'valid' or 'annulled', got '{v}'")
        return v


class QuestionSchema(BaseModel):
    """Pydantic model for question schema validation.

    This model validates the structure of individual questions
    from the JSON questionnaire file.

    Attributes:
        id: Unique question identifier (e.g., "Q001").
        stem: The question text/stem.
        options: Dictionary of answer options (letter -> text).
        answer_key: The correct answer letter.
        assets: List of asset file paths (images, etc.).
        meta: Question metadata.
    """

    id: str = Field(..., description="Unique question identifier")
    stem: str = Field(..., description="The question text/stem")
    options: dict[str, str] = Field(..., description="Dictionary of answer options")
    answer_key: str = Field(..., description="The correct answer letter")
    assets: list[str] = Field(default_factory=list, description="List of asset file paths")
    meta: MetaData = Field(..., description="Question metadata")

    @classmethod
    def validate_options(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate that options is a non-empty dictionary."""
        if not v:
            raise ValueError("Options dictionary cannot be empty")
        return v


class DatasetInfo(BaseModel):
    """Pydantic model for dataset information.

    Attributes:
        name: Dataset name.
        version: Dataset version.
        language: Dataset language code.
        source: Data source type.
    """

    name: str = Field(..., description="Dataset name")
    version: str = Field(..., description="Dataset version")
    language: str = Field(..., description="Dataset language code")
    source: str = Field(..., description="Data source type")


class QuestionnaireSchema(BaseModel):
    """Pydantic model for complete questionnaire validation.

    Attributes:
        dataset: Dataset information.
        questions: List of questions.
    """

    dataset: DatasetInfo = Field(..., description="Dataset information")
    questions: list[QuestionSchema] = Field(..., description="List of questions")


@dataclass
class QuestionData:
    """Data class for parsed question data.

    This is an intermediate data structure used during loading
    before converting to the Question model.

    Attributes:
        question_id: Unique question identifier.
        stem: The question text.
        options: Dictionary of answer options.
        answer_key: Correct answer letter.
        assets: List of asset paths.
        has_image: Whether question has an image.
        has_table: Whether question has a table.
        status: Question status.
        notes: Additional notes.
    """

    question_id: str
    stem: str
    options: dict[str, str]
    answer_key: str
    assets: list[str]
    has_image: bool = False
    has_table: bool = False
    status: str = "valid"
    notes: str = ""


class QuestionLoader:
    """Loader for JSON questionnaire files.

    This class handles loading, validating, and parsing JSON questionnaire
    files into Question objects ready for use in the benchmark system.

    Attributes:
        json_path: Path to the JSON questionnaire file.

    Example:
        >>> loader = QuestionLoader("data/enamed_questions.json")
        >>> questions = loader.load()
        >>> print(len(questions))
        100
    """

    def __init__(self, json_path: str) -> None:
        """Initialize the QuestionLoader.

        Args:
            json_path: Path to the JSON questionnaire file.
        """
        self.json_path = json_path
        self._validated_data: Optional[QuestionnaireSchema] = None

    def load(self) -> list[Question]:
        """Load and validate the questionnaire from JSON file.

        Reads the JSON file, validates its structure using pydantic,
        and converts it to a list of Question objects.

        Returns:
            List of Question objects parsed from the JSON file.

        Raises:
            FileNotFoundError: If the JSON file does not exist.
            ValueError: If the JSON structure is invalid.

        Example:
            >>> loader = QuestionLoader("data/questions.json")
            >>> questions = loader.load()
            >>> len(questions)
            100
        """
        path = Path(self.json_path)

        if not path.exists():
            logger.error(f"Questionnaire file not found: {self.json_path}")
            raise FileNotFoundError(f"Questionnaire file not found: {self.json_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error reading file {self.json_path}: {e}")
            raise ValueError(f"Error reading file: {e}") from e

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.json_path}: {e}")
            raise ValueError(f"Invalid JSON format: {e}") from e

        try:
            self._validated_data = QuestionnaireSchema(**data)
        except ValidationError as e:
            logger.error(f"Schema validation error: {e}")
            raise ValueError(f"Invalid questionnaire structure: {e}") from e

        questions = self._parse_questions(self._validated_data.questions)
        logger.info(f"Loaded {len(questions)} questions from {self.json_path}")

        return questions

    def _parse_questions(self, schemas: list[QuestionSchema]) -> list[Question]:
        """Parse validated question schemas into Question objects.

        Args:
            schemas: List of validated QuestionSchema objects.

        Returns:
            List of Question objects ready for use.
        """
        questions = []

        for schema in schemas:
            image_path: Optional[str] = None
            if schema.meta.has_image and schema.assets:
                image_path = schema.assets[0]

            metadata = {
                "has_image": schema.meta.has_image,
                "has_table": schema.meta.has_table,
                "status": schema.meta.status,
                "notes": schema.meta.notes,
                "original_options": dict(schema.options),
                "original_correct_answer": schema.answer_key,
            }

            question = Question(
                question_id=schema.id,
                question_text=schema.stem,
                options=dict(schema.options),
                correct_answer=schema.answer_key,
                has_image=schema.meta.has_image,
                image_path=image_path,
                has_table=schema.meta.has_table,
                metadata=metadata,
            )
            questions.append(question)

        return questions

    def get_dataset_info(self) -> Optional[dict[str, str]]:
        """Get information about the loaded dataset.

        Returns:
            Dictionary with dataset information, or None if not loaded.

        Example:
            >>> loader = QuestionLoader("data/questions.json")
            >>> loader.load()
            >>> info = loader.get_dataset_info()
            >>> print(info["name"])
            ENAMED 2025-26
        """
        if self._validated_data is None:
            return None

        return {
            "name": self._validated_data.dataset.name,
            "version": self._validated_data.dataset.version,
            "language": self._validated_data.dataset.language,
            "source": self._validated_data.dataset.source,
        }

    def get_question_count(self) -> int:
        """Get the total number of questions in the loaded file.

        Returns:
            Number of questions, or 0 if not loaded.
        """
        if self._validated_data is None:
            return 0
        return len(self._validated_data.questions)
