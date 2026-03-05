"""Answer randomizer module for benchmark_llm project.

This module provides functionality to randomize answer options using
the Fisher-Yates shuffle algorithm, with reproducible results via seeding.
"""

import logging
import random
from copy import deepcopy
from typing import Optional

from src.db.models import Question

logger = logging.getLogger(__name__)

# Standard answer option letters
OPTION_LETTERS = ["A", "B", "C", "D"]


class AnswerRandomizer:
    """Randomizer for answer options using Fisher-Yates shuffle.

    This class implements reproducible randomization of question answer
    options. The same run_id seed will always produce the same randomization,
    enabling reproducible benchmark results.

    Attributes:
        run_id: Seed value for reproducible randomization.

    Example:
        >>> randomizer = AnswerRandomizer(run_id=42)
        >>> randomized_question = randomizer.randomize(question)
        >>> print(randomized_question.options)
        {'A': 'Option C', 'B': 'Option A', 'C': 'Option D', 'D': 'Option B'}
    """

    def __init__(self, run_id: int) -> None:
        """Initialize the AnswerRandomizer.

        Sets the global random seed for reproducibility based on run_id.

        Args:
            run_id: Unique identifier used as random seed for reproducibility.

        Example:
            >>> randomizer = AnswerRandomizer(run_id=12345)
            >>> # Same run_id will always produce same randomization
        """
        self.run_id = run_id
        random.seed(run_id)
        logger.info(f"AnswerRandomizer initialized with seed {run_id}")

    def randomize(self, question: Question) -> Question:
        """Randomize the answer options for a question.

        Uses Fisher-Yates shuffle to randomize option order while
        tracking the original mapping. The correct answer is remapped
        to point to the new letter containing the original correct text.

        Args:
            question: The Question object to randomize.

        Returns:
            A new Question object with randomized options and remapped
            correct answer. The original question is not modified.

        Example:
            >>> randomizer = AnswerRandomizer(run_id=42)
            >>> randomized = randomizer.randomize(question)
            >>> # Original correct answer "A" might now be at position "C"
        """
        # Create a deep copy to avoid modifying the original
        randomized_question = deepcopy(question)

        # Store original options for tracking
        original_options = dict(question.options)
        original_correct_answer = question.correct_answer

        # Get the text of the correct answer
        correct_answer_text = original_options.get(original_correct_answer, "")

        # Fisher-Yates shuffle on the option values
        option_values = list(original_options.values())
        shuffled_values = self._fisher_yates_shuffle(option_values)

        # Create new options dictionary with standard letters
        new_options = {}
        for i, letter in enumerate(OPTION_LETTERS[: len(shuffled_values)]):
            new_options[letter] = shuffled_values[i]

        # Find the new letter that contains the correct answer
        new_correct_answer = self._find_correct_letter(new_options, correct_answer_text)

        # Update the randomized question
        randomized_question.options = new_options
        randomized_question.correct_answer = new_correct_answer

        # Store mapping information in metadata for traceability
        original_mapping = self._create_mapping(original_options, new_options)
        randomized_question.metadata["original_options"] = original_options
        randomized_question.metadata["original_correct_answer"] = original_correct_answer
        randomized_question.metadata["original_mapping"] = original_mapping
        randomized_question.metadata["options_randomized"] = True

        logger.debug(
            f"Randomized question {question.question_id}: "
            f"original correct={original_correct_answer}, new correct={new_correct_answer}"
        )

        return randomized_question

    def _fisher_yates_shuffle(self, items: list) -> list:
        """Perform Fisher-Yates shuffle on a list.

        The Fisher-Yates algorithm produces an unbiased permutation
        where every permutation is equally likely.

        Args:
            items: List of items to shuffle.

        Returns:
            A new list with items in shuffled order.

        Example:
            >>> randomizer = AnswerRandomizer(run_id=42)
            >>> shuffled = randomizer._fisher_yates_shuffle([1, 2, 3, 4])
        """
        result = list(items)  # Create a copy to avoid modifying original
        n = len(result)

        # Fisher-Yates shuffle: iterate from end to beginning
        for i in range(n - 1, 0, -1):
            # Pick a random index from 0 to i
            j = random.randint(0, i)
            # Swap elements at i and j
            result[i], result[j] = result[j], result[i]

        return result

    def _find_correct_letter(
        self, options: dict[str, str], correct_text: str
    ) -> str:
        """Find the letter corresponding to the correct answer text.

        Args:
            options: Dictionary of option letter -> text.
            correct_text: The text of the correct answer.

        Returns:
            The letter (A, B, C, D) that contains the correct answer.

        Raises:
            ValueError: If the correct answer text is not found in options.
        """
        for letter, text in options.items():
            if text == correct_text:
                return letter

        # This should never happen if the algorithm is correct
        logger.error(f"Correct answer text '{correct_text}' not found in options")
        raise ValueError("Correct answer not found in randomized options")

    def _create_mapping(
        self, original: dict[str, str], randomized: dict[str, str]
    ) -> dict[str, str]:
        """Create a mapping from original letters to randomized letters.

        Args:
            original: Original options dictionary.
            randomized: Randomized options dictionary.

        Returns:
            Dictionary mapping original letters to new letters.

        Example:
            >>> original = {"A": "Paris", "B": "London"}
            >>> randomized = {"A": "London", "B": "Paris"}
            >>> mapping = {"A": "B", "B": "A"}  # A moved to B, B moved to A
        """
        mapping = {}

        for orig_letter, orig_text in original.items():
            for new_letter, new_text in randomized.items():
                if orig_text == new_text:
                    mapping[orig_letter] = new_letter
                    break

        return mapping

    def reset_seed(self, run_id: Optional[int] = None) -> None:
        """Reset the random seed.

        Args:
            run_id: New run_id to use as seed. If None, uses the original run_id.
        """
        seed = run_id if run_id is not None else self.run_id
        random.seed(seed)
        self.run_id = seed
        logger.debug(f"Random seed reset to {seed}")

    @staticmethod
    def is_randomized(question: Question) -> bool:
        """Check if a question has been randomized.

        Args:
            question: Question to check.

        Returns:
            True if the question has been randomized, False otherwise.
        """
        return question.metadata.get("options_randomized", False)

    @staticmethod
    def get_original_options(question: Question) -> Optional[dict[str, str]]:
        """Get the original options before randomization.

        Args:
            question: Question to get original options from.

        Returns:
            Dictionary of original options, or None if not randomized.
        """
        return question.metadata.get("original_options")

    @staticmethod
    def get_original_correct_answer(question: Question) -> Optional[str]:
        """Get the original correct answer before randomization.

        Args:
            question: Question to get original correct answer from.

        Returns:
            Original correct answer letter, or None if not randomized.
        """
        return question.metadata.get("original_correct_answer")
