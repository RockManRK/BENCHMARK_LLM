"""Answer randomizer module for TO-BE architecture.

This module provides functionality to randomize answer options using
the Fisher-Yates shuffle algorithm, with reproducible results via seeding.

The randomizer is used by the ExecutionEngine to shuffle answer options
before sending them to the API, ensuring reproducible benchmarking.

IMPORTANT CONTRACT:
- seed=None means randomization is DISABLED (no shuffling)
- seed=int means randomization is ENABLED with deterministic results
- This class does NOT decide whether to randomize - it only executes
- The decision is made by ExecutionEngine based on run.randomization_seed_effective
"""

import random
from typing import Any


class AnswerRandomizer:
    """Randomizer for answer options using Fisher-Yates shuffle.

    This class implements reproducible randomization of question answer
    options. The same seed will always produce the same randomization,
    enabling reproducible benchmark results.

    Example:
        >>> randomizer = AnswerRandomizer(seed=42)
        >>> result = randomizer.randomize_options(["A", "B", "C", "D"], "B")
        >>> print(result["options"])  # Shuffled options
        >>> print(result["correct_answer"])  # New position of correct answer
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the AnswerRandomizer.

        Contract: seed is guaranteed to be int | None by the caller (ExecutionEngine).
        This class does NOT validate, normalize, or decide — it only executes.

        Args:
            seed: Seed value for reproducible randomization.
                  If None, randomization is disabled.

        Example:
            >>> randomizer = AnswerRandomizer(seed=42)
            >>> randomizer_disabled = AnswerRandomizer(seed=None)
        """
        self.seed = seed
        if seed is None:
            self._randomization_enabled = False
        else:
            self._randomization_enabled = True
            random.seed(seed)

    def set_seed(self, seed: int | None) -> None:
        """Set the random seed.

        Contract: seed is guaranteed to be int | None by the caller.
        This method does NOT validate or normalize — it only executes.

        Args:
            seed: New seed value. If None, disables randomization.
        """
        self.seed = seed
        if seed is None:
            self._randomization_enabled = False
        else:
            self._randomization_enabled = True
            random.seed(seed)

    def randomize_options(
        self,
        options: list[str],
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Randomize answer options and return mapping.

        This method shuffles the option values using Fisher-Yates algorithm
        and returns the new options dictionary.

        If randomization is disabled (seed=None), returns options unchanged.

        Args:
            options: List of option texts (e.g., ["Paris", "London", "Berlin"]).
            seed: Optional seed for this specific randomization.
                  If None, uses the instance seed.

        Returns:
            Dictionary with:
            - "options": List with shuffled values
            - "correct_answer": The correct answer (unchanged, for reference)

        Example:
            >>> randomizer = AnswerRandomizer(seed=42)
            >>> result = randomizer.randomize_options(
            ...     ["Paris", "London", "Berlin", "Madrid"],
            ...     seed=42,
            ... )
            >>> # result["options"] will be shuffled deterministically
        """
        # Use provided seed or instance seed
        effective_seed = seed if seed is not None else self.seed

        # If randomization is disabled, return unchanged
        if effective_seed is None:
            return {
                "options": options,
            }

        # Set seed for this randomization
        random.seed(effective_seed)

        # Fisher-Yates shuffle on the option values
        shuffled_values = self._fisher_yates_shuffle(options)

        return {
            "options": shuffled_values,
        }

    def _fisher_yates_shuffle(self, items: list[str]) -> list[str]:
        """Perform Fisher-Yates shuffle on a list.

        The Fisher-Yates algorithm produces an unbiased permutation
        where every permutation is equally likely.

        Args:
            items: List of items to shuffle.

        Returns:
            A new list with items in shuffled order.

        Example:
            >>> randomizer = AnswerRandomizer(seed=42)
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
