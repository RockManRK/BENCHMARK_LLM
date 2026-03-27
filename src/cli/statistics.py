"""Statistics module for benchmark_llm project.

This module provides statistical calculations and analysis
for benchmark results, including accuracy, latency, tokens,
consistency, and error summaries.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BenchmarkStatistics:
    """Statistics summary for a single model's benchmark performance.

    This dataclass aggregates all key metrics for a model across
    all questions and iterations.

    Attributes:
        model_id: Unique identifier for the model.
        total_questions: Total number of questions attempted.
        correct_answers: Number of correctly answered questions.
        accuracy: Accuracy rate (correct_answers / total_questions).
        avg_latency_ms: Average response latency in milliseconds.
        min_latency_ms: Minimum response latency in milliseconds.
        max_latency_ms: Maximum response latency in milliseconds.
        total_input_tokens: Total input tokens consumed.
        total_response_tokens: Total response tokens generated.
        error_count: Number of errors encountered.
        error_rate: Error rate (error_count / total_questions).

    Example:
        >>> stats = BenchmarkStatistics(
        ...     model_id="gpt-4",
        ...     total_questions=100,
        ...     correct_answers=85,
        ...     accuracy=0.85,
        ...     avg_latency_ms=1500.0,
        ...     min_latency_ms=800,
        ...     max_latency_ms=3000,
        ...     total_input_tokens=50000,
        ...     total_response_tokens=10000,
        ...     error_count=5,
        ...     error_rate=0.05,
        ... )
        >>> print(f"{stats.model_id}: {stats.accuracy:.2%} accuracy")
        gpt-4: 85.00% accuracy
    """

    model_id: str
    total_questions: int = 0
    correct_answers: int = 0
    accuracy: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: int = 0
    max_latency_ms: int = 0
    total_input_tokens: int = 0
    total_response_tokens: int = 0
    error_count: int = 0
    error_rate: float = 0.0


class StatisticsCalculator:
    """Calculator for benchmark statistics from response data.

    This class processes raw response and error data to compute
    comprehensive statistics for each model.

    Attributes:
        responses: List of response dictionaries from the database.
        errors: List of error dictionaries from the database.

    Example:
        >>> calculator = StatisticsCalculator(responses, errors)
        >>> stats = calculator.get_model_statistics("gpt-4")
        >>> print(f"Accuracy: {stats.accuracy:.2%}")
    """

    def __init__(
        self,
        responses: list[dict[str, Any]],
        errors: list[dict[str, Any]],
    ) -> None:
        """Initialize the statistics calculator.

        Args:
            responses: List of response dictionaries containing
                      question responses with metrics.
            errors: List of error dictionaries containing
                   error information.

        Example:
            >>> responses = [{"model_id": "gpt-4", "is_correct": True, ...}]
            >>> errors = [{"response_id": 1, "error_type": "APIError"}]
            >>> calculator = StatisticsCalculator(responses, errors)
        """
        self.responses = responses
        self.errors = errors

    def calculate_accuracy(self, model_id: str) -> float:
        """Calculate accuracy rate for a model.

        Accuracy is computed as the ratio of correct answers to
        total answered questions (excluding errors/unsupported).

        Args:
            model_id: The model identifier to calculate accuracy for.

        Returns:
            Accuracy rate as a float between 0.0 and 1.0.
            Returns 0.0 if no questions were answered.

        Example:
            >>> calculator = StatisticsCalculator(responses, errors)
            >>> accuracy = calculator.calculate_accuracy("gpt-4")
            >>> print(f"Accuracy: {accuracy:.2%}")
        """
        model_responses = [r for r in self.responses if r.get("model_id") == model_id]

        if not model_responses:
            return 0.0

        # Count only successfully answered questions
        answered = [r for r in model_responses if r.get("status") == "success"]
        if not answered:
            return 0.0

        correct = sum(1 for r in answered if r.get("is_correct", False))
        return correct / len(answered)

    def calculate_avg_latency(self, model_id: str) -> float:
        """Calculate average response latency for a model.

        Args:
            model_id: The model identifier to calculate latency for.

        Returns:
            Average latency in milliseconds. Returns 0.0 if no
            latency data available.

        Example:
            >>> avg_latency = calculator.calculate_avg_latency("gpt-4")
            >>> print(f"Average latency: {avg_latency:.0f}ms")
        """
        model_responses = [
            r for r in self.responses
            if r.get("model_id") == model_id and r.get("latency_ms", 0) > 0
        ]

        if not model_responses:
            return 0.0

        total_latency = sum(r.get("latency_ms", 0) for r in model_responses)
        return total_latency / len(model_responses)

    def calculate_latency_min_max(self, model_id: str) -> tuple[int, int]:
        """Calculate minimum and maximum latency for a model.

        Args:
            model_id: The model identifier to calculate latency range for.

        Returns:
            Tuple of (min_latency_ms, max_latency_ms).
            Returns (0, 0) if no latency data available.

        Example:
            >>> min_lat, max_lat = calculator.calculate_latency_min_max("gpt-4")
            >>> print(f"Latency range: {min_lat}ms - {max_lat}ms")
        """
        model_responses = [
            r for r in self.responses
            if r.get("model_id") == model_id and r.get("latency_ms", 0) > 0
        ]

        if not model_responses:
            return (0, 0)

        latencies = [r.get("latency_ms", 0) for r in model_responses]
        return (min(latencies), max(latencies))

    def calculate_token_usage(self, model_id: str) -> tuple[int, int]:
        """Calculate total token usage for a model.

        Args:
            model_id: The model identifier to calculate token usage for.

        Returns:
            Tuple of (total_input_tokens, total_response_tokens).

        Example:
            >>> input_tok, output_tok = calculator.calculate_token_usage("gpt-4")
            >>> print(f"Tokens: {input_tok} input, {output_tok} response")
        """
        model_responses = [r for r in self.responses if r.get("model_id") == model_id]

        total_input = sum(r.get("input_tokens", 0) for r in model_responses)
        total_response = sum(r.get("response_tokens", 0) for r in model_responses)

        return (total_input, total_response)

    def calculate_error_summary(self, model_id: str) -> tuple[int, float]:
        """Calculate error count and error rate for a model.

        Args:
            model_id: The model identifier to calculate errors for.

        Returns:
            Tuple of (error_count, error_rate).
            Error rate is error_count / total_questions.

        Example:
            >>> error_count, error_rate = calculator.calculate_error_summary("gpt-4")
            >>> print(f"Errors: {error_count} ({error_rate:.2%})")
        """
        model_responses = [r for r in self.responses if r.get("model_id") == model_id]
        total_questions = len(model_responses)

        if total_questions == 0:
            return (0, 0.0)

        # Count responses with error status
        error_count = sum(1 for r in model_responses if r.get("status") == "error")

        return (error_count, error_count / total_questions)

    def calculate_consistency(self, model_id: str, question_id: str) -> float:
        """Calculate answer consistency across iterations for a question.

        Consistency measures how often the model gives the same answer
        to the same question across different iterations.

        Args:
            model_id: The model identifier.
            question_id: The question identifier to check consistency for.

        Returns:
            Consistency score between 0.0 and 1.0.
            1.0 means the model always gave the same answer.
            Returns 0.0 if insufficient data.

        Example:
            >>> consistency = calculator.calculate_consistency("gpt-4", "Q001")
            >>> print(f"Consistency on Q001: {consistency:.2%}")
        """
        question_responses = [
            r for r in self.responses
            if r.get("model_id") == model_id
            and r.get("question_id") == question_id
            and r.get("selected_answer") is not None
        ]

        if len(question_responses) < 2:
            return 0.0

        # Count answer occurrences
        answer_counts: dict[str, int] = defaultdict(int)
        for response in question_responses:
            answer = response.get("selected_answer", "")
            answer_counts[answer] += 1

        # Consistency = most common answer count / total responses
        most_common_count = max(answer_counts.values())
        return most_common_count / len(question_responses)

    def get_model_statistics(self, model_id: str) -> BenchmarkStatistics:
        """Get comprehensive statistics for a model.

        Aggregates all metrics for a single model into a
        BenchmarkStatistics object.

        Args:
            model_id: The model identifier to get statistics for.

        Returns:
            BenchmarkStatistics object with all computed metrics.

        Example:
            >>> stats = calculator.get_model_statistics("gpt-4")
            >>> print(f"Model: {stats.model_id}")
            >>> print(f"Accuracy: {stats.accuracy:.2%}")
            >>> print(f"Avg Latency: {stats.avg_latency_ms:.0f}ms")
        """
        model_responses = [r for r in self.responses if r.get("model_id") == model_id]
        total_questions = len(model_responses)

        # Calculate correct answers (only from successful responses)
        successful = [r for r in model_responses if r.get("status") == "success"]
        correct_answers = sum(1 for r in successful if r.get("is_correct", False))

        # Calculate accuracy
        accuracy = self.calculate_accuracy(model_id)

        # Calculate latency
        avg_latency = self.calculate_avg_latency(model_id)
        min_latency, max_latency = self.calculate_latency_min_max(model_id)

        # Calculate token usage
        input_tokens, response_tokens = self.calculate_token_usage(model_id)

        # Calculate errors
        error_count, error_rate = self.calculate_error_summary(model_id)

        return BenchmarkStatistics(
            model_id=model_id,
            total_questions=total_questions,
            correct_answers=correct_answers,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            total_input_tokens=input_tokens,
            total_response_tokens=response_tokens,
            error_count=error_count,
            error_rate=error_rate,
        )

    def get_all_model_ids(self) -> list[str]:
        """Get all unique model IDs from the responses.

        Returns:
            List of unique model identifiers.

        Example:
            >>> model_ids = calculator.get_all_model_ids()
            >>> print(f"Models: {', '.join(model_ids)}")
        """
        model_ids = set(r.get("model_id", "") for r in self.responses)
        return sorted([m for m in model_ids if m])

    def get_all_statistics(self) -> list[BenchmarkStatistics]:
        """Get statistics for all models.

        Returns:
            List of BenchmarkStatistics objects, one per model.

        Example:
            >>> all_stats = calculator.get_all_statistics()
            >>> for stats in all_stats:
            ...     print(f"{stats.model_id}: {stats.accuracy:.2%}")
        """
        model_ids = self.get_all_model_ids()
        return [self.get_model_statistics(model_id) for model_id in model_ids]

    def get_error_details(self, model_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get detailed error information.

        Args:
            model_id: Optional model ID to filter errors.
                     If None, returns all errors.

        Returns:
            List of error dictionaries.

        Example:
            >>> errors = calculator.get_error_details("gpt-4")
            >>> for error in errors:
            ...     print(f"{error['error_type']}: {error['error_message']}")
        """
        if model_id is None:
            return self.errors

        # Get response IDs for the model
        model_response_ids = {
            r.get("response_id")
            for r in self.responses
            if r.get("model_id") == model_id
        }

        return [e for e in self.errors if e.get("response_id") in model_response_ids]

    def get_summary_report(self) -> dict[str, Any]:
        """Generate a summary report of all benchmark results.

        Returns:
            Dictionary containing summary statistics and insights.

        Example:
            >>> report = calculator.get_summary_report()
            >>> print(f"Total models: {report['total_models']}")
            >>> print(f"Best accuracy: {report['best_accuracy']:.2%}")
        """
        all_stats = self.get_all_statistics()

        if not all_stats:
            return {
                "total_models": 0,
                "total_questions": 0,
                "total_errors": 0,
                "best_accuracy": 0.0,
                "best_model": None,
                "avg_latency_overall": 0.0,
            }

        # Find best model by accuracy
        best_model = max(all_stats, key=lambda s: s.accuracy)

        # Calculate overall average latency
        total_latency = sum(s.avg_latency_ms for s in all_stats)
        avg_latency_overall = total_latency / len(all_stats) if all_stats else 0.0

        return {
            "total_models": len(all_stats),
            "total_questions": sum(s.total_questions for s in all_stats),
            "total_errors": sum(s.error_count for s in all_stats),
            "best_accuracy": best_model.accuracy,
            "best_model": best_model.model_id,
            "avg_latency_overall": avg_latency_overall,
        }
