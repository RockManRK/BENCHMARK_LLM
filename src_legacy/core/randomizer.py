"""Answer randomizer module for benchmark_llm project.

This module provides functionality to randomize answer options using
the Fisher-Yates shuffle algorithm, with reproducible results via seeding.
"""

import json
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
        >>> print(randomized_question.options_json)
        '{"A": "Option C", "B": "Option A", "C": "Option D", "D": "Option B"}'
    """

    def __init__(self, run_id: Optional[int] = None) -> None:
        """Initialize the AnswerRandomizer.

        Sets the global random seed for reproducibility based on run_id.
        The run_id should come from run.seed (single source of truth).

        If run_id is None, randomization is DISABLED (natural order preserved).

        Args:
            run_id: Unique identifier used as random seed for reproducibility.
                   Should be the value from run.seed database field.
                   If None, randomization is disabled.

        Example:
            >>> randomizer = AnswerRandomizer(run_id=12345)
            >>> # Same run_id will always produce same randomization
            >>> randomizer_disabled = AnswerRandomizer(run_id=None)
            >>> # No randomization applied
        """
        self.run_id = run_id
        self._randomization_enabled = run_id is not None
        if self._randomization_enabled:
            random.seed(run_id)
            logger.debug(f"AnswerRandomizer initialized with seed {run_id}")
        else:
            logger.debug("AnswerRandomizer initialized with randomization DISABLED (run_id=None)")

    def randomize(self, question: Question) -> Question:
        """Randomize the answer options for a question.

        Uses Fisher-Yates shuffle to randomize option order while
        tracking the original mapping. The correct answer is remapped
        to point to the new letter containing the original correct text.

        If randomization is disabled (run_id=None), returns the original
        question unchanged (deep copy).

        Args:
            question: The Question object to randomize.

        Returns:
            A new Question object with randomized options (or unchanged if
            randomization is disabled). The original question is not modified.

        Example:
            >>> randomizer = AnswerRandomizer(run_id=42)
            >>> randomized = randomizer.randomize(question)
            >>> # Original correct answer "A" might now be at position "C"
        """
        # If randomization is disabled, return unchanged copy
        if not self._randomization_enabled:
            logger.debug(f"Randomization disabled, returning question {question.question_id} unchanged")
            return deepcopy(question)

        # Parse options from JSON
        original_options = json.loads(question.options_json)
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

        # Create a deep copy to avoid modifying the original
        randomized_question = deepcopy(question)

        # Update the randomized question with new options JSON
        randomized_question.options_json = json.dumps(new_options)
        randomized_question.correct_answer = new_correct_answer

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

    def randomize_options(
        self, options: dict[str, str], correct_answer: str
    ) -> dict[str, dict[str, str] | str]:
        """Randomize answer options and return mapping.

        This method shuffles the option values using Fisher-Yates algorithm
        and returns the new options dictionary with the remapped correct answer.

        If randomization is disabled (run_id=None), returns options unchanged.

        Args:
            options: Dictionary of option letter -> text (e.g., {"A": "Paris", "B": "London"}).
            correct_answer: The letter of the correct answer (e.g., "A").

        Returns:
            Dictionary with:
            - "options": New options dictionary with shuffled values
            - "correct_answer": New letter that contains the correct answer text

        Example:
            >>> randomizer = AnswerRandomizer(run_id=42)
            >>> result = randomizer.randomize_options(
            ...     {"A": "Paris", "B": "London", "C": "Berlin", "D": "Madrid"},
            ...     "A"
            ... )
            >>> # result["options"] might be {"A": "London", "B": "Paris", ...}
            >>> # result["correct_answer"] would be "B" (where "Paris" moved to)
        """
        # If randomization is disabled, return unchanged
        if not self._randomization_enabled:
            return {
                "options": options,
                "correct_answer": correct_answer,
            }

        # Get the text of the correct answer
        correct_answer_text = options.get(correct_answer, "")

        # Fisher-Yates shuffle on the option values
        option_values = list(options.values())
        shuffled_values = self._fisher_yates_shuffle(option_values)

        # Create new options dictionary with standard letters
        new_options = {}
        for i, letter in enumerate(OPTION_LETTERS[: len(shuffled_values)]):
            new_options[letter] = shuffled_values[i]

        # Find the new letter that contains the correct answer
        new_correct_answer = self._find_correct_letter(new_options, correct_answer_text)

        logger.debug(
            f"Randomized options: original correct={correct_answer}, new correct={new_correct_answer}"
        )

        return {
            "options": new_options,
            "correct_answer": new_correct_answer,
        }

    def reset_seed(self, run_id: Optional[int] = None) -> None:
        """Reset the random seed.

        Args:
            run_id: New run_id to use as seed. If None, uses the original run_id.
        """
        seed = run_id if run_id is not None else self.run_id
        random.seed(seed)
        self.run_id = seed
        logger.debug(f"Random seed reset to {seed}")
