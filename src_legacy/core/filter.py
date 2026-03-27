"""Question filter module for benchmark_llm project.

This module provides functionality to filter questions by various criteria
including ID, status, and metadata attributes.
"""

import logging
import re
from typing import Any, Optional

from src.db.models import Question

logger = logging.getLogger(__name__)


class QuestionFilter:
    """Filter for Question objects based on various criteria.

    This class provides a fluent interface for filtering questions
    by ID, status, and metadata attributes. Filters can be chained
    to create complex filtering criteria.

    Attributes:
        questions: The list of questions to filter.
        _filtered: The current filtered result set.

    Example:
        >>> filter_obj = QuestionFilter(questions)
        >>> filtered = filter_obj.by_status("valid").by_metadata(has_image=False)
        >>> print(len(filtered))
        85
    """

    def __init__(self, questions: list[Question]) -> None:
        """Initialize the QuestionFilter.

        Args:
            questions: List of Question objects to filter.
        """
        self.questions = questions
        self._filtered: list[Question] = list(questions)
        logger.debug(f"QuestionFilter initialized with {len(questions)} questions")

    def by_ids(self, question_ids: list[str]) -> "QuestionFilter":
        """Filter questions by their IDs.

        Supports individual IDs (e.g., ["Q001", "Q003"]) and ranges
        (e.g., ["Q001-Q010"] for questions Q001 through Q010).

        Args:
            question_ids: List of question IDs or ID ranges to include.

        Returns:
            Self for method chaining.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> filtered = filter_obj.by_ids(["Q001", "Q003", "Q005-Q010"])
            >>> print(len(filtered))
            8
        """
        if not self._filtered:
            return self

        id_set = self._expand_id_ranges(question_ids)
        self._filtered = [q for q in self._filtered if q.question_id in id_set]
        logger.debug(f"Filtered by IDs: {len(self._filtered)} questions remaining")
        return self

    def _expand_id_ranges(self, question_ids: list[str]) -> set[str]:
        """Expand ID ranges into individual IDs.

        Converts range specifications like "Q001-Q010" into individual
        IDs like "Q001", "Q002", ..., "Q010".

        Args:
            question_ids: List of IDs and/or ID ranges.

        Returns:
            Set of expanded individual question IDs.
        """
        expanded: set[str] = set()
        range_pattern = re.compile(r"^(Q\d+)-Q(\d+)$")

        for item in question_ids:
            match = range_pattern.match(item)
            if match:
                start_id = match.group(1)
                end_num = int(match.group(2))

                start_num = int(start_id[1:])
                for num in range(start_num, end_num + 1):
                    expanded.add(f"Q{num:03d}")
            else:
                expanded.add(item)

        return expanded

    def by_status(self, status: str) -> "QuestionFilter":
        """Filter questions by their status.

        Args:
            status: Status to filter by ("valid" or "annulled").

        Returns:
            Self for method chaining.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> valid_questions = filter_obj.by_status("valid")
            >>> print(len(valid_questions))
            85
        """
        if not self._filtered:
            return self

        self._filtered = [
            q for q in self._filtered
            if q.metadata.get("status") == status
        ]
        logger.debug(f"Filtered by status '{status}': {len(self._filtered)} questions remaining")
        return self

    def by_metadata(self, **kwargs: Any) -> "QuestionFilter":
        """Filter questions by metadata attributes.

        Filters questions where metadata matches all specified key-value pairs.

        Args:
            **kwargs: Metadata key-value pairs to match.

        Returns:
            Self for method chaining.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> image_questions = filter_obj.by_metadata(has_image=True)
            >>> table_questions = filter_obj.by_metadata(has_table=True)
        """
        if not self._filtered:
            return self

        def matches_metadata(question: Question) -> bool:
            """Check if question metadata matches all criteria."""
            for key, value in kwargs.items():
                if question.metadata.get(key) != value:
                    return False
            return True

        self._filtered = [q for q in self._filtered if matches_metadata(q)]
        logger.debug(
            f"Filtered by metadata {kwargs}: {len(self._filtered)} questions remaining"
        )
        return self

    def by_has_image(self, has_image: bool = True) -> "QuestionFilter":
        """Filter questions by whether they have an image.

        Convenience method for filtering by has_image attribute.

        Args:
            has_image: True to get questions with images, False otherwise.

        Returns:
            Self for method chaining.
        """
        return self.by_metadata(has_image=has_image)

    def by_has_table(self, has_table: bool = True) -> "QuestionFilter":
        """Filter questions by whether they have a table.

        Convenience method for filtering by has_table attribute.

        Args:
            has_table: True to get questions with tables, False otherwise.

        Returns:
            Self for method chaining.
        """
        return self.by_metadata(has_table=has_table)

    def exclude_by_metadata(self, **kwargs: Any) -> "QuestionFilter":
        """Exclude questions by metadata attributes.

        Excludes questions where metadata matches any of the specified key-value pairs.
        Uses OR logic - if any criterion matches, the question is excluded.

        Args:
            **kwargs: Metadata key-value pairs to exclude.

        Returns:
            Self for method chaining.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> filtered = filter_obj.exclude_by_metadata(status="annulled", has_image=True)
            >>> # Excludes questions that are annulled OR have images
        """
        if not self._filtered:
            return self

        def matches_any_criterion(question: Question) -> bool:
            """Check if question metadata matches any exclusion criterion."""
            for key, value in kwargs.items():
                if question.metadata.get(key) == value:
                    return True
            return False

        self._filtered = [q for q in self._filtered if not matches_any_criterion(q)]
        logger.debug(
            f"Excluded by metadata {kwargs}: {len(self._filtered)} questions remaining"
        )
        return self

    def get_filtered(self) -> list[Question]:
        """Get the current filtered list of questions.

        Returns:
            List of filtered Question objects.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> filtered = filter_obj.by_status("valid").get_filtered()
        """
        return self._filtered

    def reset(self) -> "QuestionFilter":
        """Reset the filter to include all original questions.

        Returns:
            Self for method chaining.

        Example:
            >>> filter_obj = QuestionFilter(questions)
            >>> filtered = filter_obj.by_status("valid")
            >>> all_questions = filter_obj.reset().get_filtered()
        """
        self._filtered = list(self.questions)
        logger.debug("Filter reset to all questions")
        return self

    def count(self) -> int:
        """Get the count of currently filtered questions.

        Returns:
            Number of questions in the current filter result.
        """
        return len(self._filtered)

    def __len__(self) -> int:
        """Return the count of currently filtered questions."""
        return self.count()

    def __iter__(self):
        """Iterate over the filtered questions."""
        return iter(self._filtered)

    def __getitem__(self, index: int) -> Question:
        """Get a question by index from the filtered list."""
        return self._filtered[index]

    def get_results(self) -> list[Question]:
        """Get the final filtered results.

        Alias for get_filtered() for clearer intent.

        Returns:
            List of filtered Question objects.
        """
        return self.get_filtered()
