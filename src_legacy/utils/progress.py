"""Progress tracking module for benchmark_llm project.

This module provides functionality to display and track execution progress
using rich progress bars, with time estimation and status reporting.
"""

import logging
import time
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks and displays execution progress.

    This class provides a rich progress bar display for benchmark
    execution, showing current question, model, iteration, and
    estimated time remaining.

    Attributes:
        total: Total number of items to process.
        run_id: ID of the current benchmark run.
        model_id: ID of the model being tested.
        iteration_number: Current iteration number.
        current: Current progress count.
        start_time: Time when tracking started.

    Example:
        >>> tracker = ProgressTracker(
        ...     total=100,
        ...     run_id="run-123",
        ...     model_id="gpt-4",
        ...     iteration_number=1
        ... )
        >>> tracker.update(10)
        >>> print(f"Progress: {tracker.percentage}%")
    """

    def __init__(
        self,
        total: int,
        run_id: str,
        model_id: str,
        iteration_number: int,
        description: str = "Processing",
    ) -> None:
        """Initialize the ProgressTracker.

        Args:
            total: Total number of items to process.
            run_id: ID of the current benchmark run.
            model_id: ID of the model being tested.
            iteration_number: Current iteration number.
            description: Description text for the progress bar.

        Example:
            >>> tracker = ProgressTracker(
            ...     total=100,
            ...     run_id="run-123",
            ...     model_id="gpt-4",
            ...     iteration_number=1
            ... )
        """
        self.total = total
        self.run_id = run_id
        self.model_id = model_id
        self.iteration_number = iteration_number
        self.description = description
        self.current = 0
        self.start_time: Optional[float] = None
        self._last_update_time: Optional[float] = None
        self._items_per_second: float = 0.0
        self._console = Console()
        self._progress: Optional[Progress] = None
        self._task_id: Optional[int] = None

        logger.info(
            f"ProgressTracker initialized: total={total}, "
            f"run={run_id}, model={model_id}, iteration={iteration_number}"
        )

    def start(self) -> None:
        """Start the progress tracking.

        Initializes the progress bar and starts the timer.

        Example:
            >>> tracker.start()
            >>> for i in range(100):
            ...     process_item(i)
            ...     tracker.update(1)
        """
        self.start_time = time.time()
        self._last_update_time = self.start_time
        self.current = 0
        self._items_per_second = 0.0

        logger.debug(f"Progress tracking started for {self.run_id}")

    def update(self, advance: int = 1) -> None:
        """Update the progress by advancing the counter.

        Args:
            advance: Number of items to advance (default 1).

        Example:
            >>> tracker.update(1)  # Advance by 1
            >>> tracker.update(5)  # Advance by 5
        """
        if self.start_time is None:
            self.start()

        self.current += advance
        current_time = time.time()

        # Calculate items per second
        if self._last_update_time and current_time > self._last_update_time:
            time_delta = current_time - self._last_update_time
            self._items_per_second = advance / time_delta

        self._last_update_time = current_time

        # Log progress at certain milestones
        if self.total > 0:
            percentage = (self.current / self.total) * 100
            if percentage % 25 < (advance / self.total * 100):
                logger.info(f"Progress: {self.current}/{self.total} ({percentage:.1f}%)")

    def reset(self) -> None:
        """Reset the progress tracker to initial state.

        Example:
            >>> tracker.update(50)
            >>> tracker.reset()
            >>> print(tracker.current)  # 0
        """
        self.current = 0
        self.start_time = None
        self._last_update_time = None
        self._items_per_second = 0.0
        logger.debug(f"Progress tracker reset for {self.run_id}")

    @property
    def percentage(self) -> float:
        """Get the current progress percentage.

        Returns:
            Progress percentage (0.0 to 100.0), or 0.0 if total is 0.

        Example:
            >>> tracker.update(25)
            >>> print(f"{tracker.percentage}% complete")
            25.0% complete
        """
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100

    def estimate_time_remaining(self) -> Optional[float]:
        """Estimate the time remaining in seconds.

        Returns:
            Estimated seconds remaining, or None if not enough data.

        Example:
            >>> tracker.update(10)
            >>> time.sleep(1)
            >>> tracker.update(10)
            >>> eta = tracker.estimate_time_remaining()
            >>> print(f"ETA: {eta:.0f} seconds")
        """
        if self._items_per_second <= 0 or self.total == 0:
            return None

        remaining_items = self.total - self.current
        estimated_seconds = remaining_items / self._items_per_second

        logger.debug(
            f"Time remaining estimate: {estimated_seconds:.1f}s "
            f"({remaining_items} items at {self._items_per_second:.2f}/s)"
        )

        return estimated_seconds

    def get_status(self) -> str:
        """Get a status message describing current progress.

        Returns:
            Status string with progress information.

        Example:
            >>> tracker.update(50)
            >>> print(tracker.get_status())
            "Run run-123 | Model gpt-4 | Iteration 1 | 50/100 (50.0%)"
        """
        percentage = self.percentage
        status = (
            f"Run {self.run_id} | "
            f"Model {self.model_id} | "
            f"Iteration {self.iteration_number} | "
            f"{self.current}/{self.total} ({percentage:.1f}%)"
        )

        time_remaining = self.estimate_time_remaining()
        if time_remaining is not None:
            status += f" | ETA: {time_remaining:.0f}s"

        return status

    def is_complete(self) -> bool:
        """Check if progress is complete.

        Returns:
            True if current >= total, False otherwise.

        Example:
            >>> tracker.update(100)
            >>> print(tracker.is_complete())
            True
        """
        return self.current >= self.total

    def display(self) -> None:
        """Display the progress bar using rich.

        Creates and displays a rich progress bar with all configured
        columns and information.

        Example:
            >>> tracker.display()
            [Progress bar will be shown in terminal]
        """
        # Create progress bar with rich columns
        self._progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TextColumn("[green]{task.fields[status]}"),
            console=self._console,
        )

        status_text = f"{self.model_id} (Iter {self.iteration_number})"

        with self._progress:
            self._task_id = self._progress.add_task(
                self.description,
                total=self.total,
                status=status_text,
            )

            # Simulate progress for display
            # In real usage, this would be updated by the executor
            if self.current > 0:
                self._progress.update(self._task_id, completed=self.current)

    def log_progress(self) -> None:
        """Log current progress to the operational log.

        Example:
            >>> tracker.update(25)
            >>> tracker.log_progress()
            # Logs: "Progress: 25/100 (25.0%) for run run-123"
        """
        status = self.get_status()
        logger.info(f"Progress update: {status}")

    def finish(self) -> None:
        """Mark the progress as complete.

        Sets current to total and logs completion.

        Example:
            >>> tracker.finish()
            >>> print(tracker.is_complete())  # True
        """
        self.current = self.total
        elapsed_time = None
        if self.start_time:
            elapsed_time = time.time() - self.start_time

        logger.info(
            f"Progress complete for {self.run_id}: "
            f"{self.total} items processed"
            + (f" in {elapsed_time:.1f}s" if elapsed_time else "")
        )


class ExecutionProgress:
    """Manages progress tracking for entire execution.

    This class coordinates progress tracking across multiple
    iterations and models, providing a high-level progress view.

    Attributes:
        run_id: ID of the current benchmark run.
        total_questions: Total number of questions to process.
        total_iterations: Total number of iterations.
        models: List of model IDs being tested.

    Example:
        >>> progress = ExecutionProgress(
        ...     run_id="run-123",
        ...     total_questions=100,
        ...     total_iterations=3,
        ...     models=["gpt-4", "claude-3"]
        ... )
        >>> progress.start()
        >>> # ... execute ...
        >>> progress.finish()
    """

    def __init__(
        self,
        run_id: str,
        total_questions: int,
        total_iterations: int,
        models: list[str],
    ) -> None:
        """Initialize the ExecutionProgress.

        Args:
            run_id: ID of the current benchmark run.
            total_questions: Total number of questions to process.
            total_iterations: Total number of iterations.
            models: List of model IDs being tested.

        Example:
            >>> progress = ExecutionProgress(
            ...     run_id="run-123",
            ...     total_questions=100,
            ...     total_iterations=3,
            ...     models=["gpt-4", "claude-3"]
            ... )
        """
        self.run_id = run_id
        self.total_questions = total_questions
        self.total_iterations = total_iterations
        self.models = models
        self.current_model_index = 0
        self.current_iteration = 0
        self.questions_completed = 0
        self._console = Console()
        self._progress: Optional[Progress] = None
        self._task_id: Optional[int] = None

        total_items = total_questions * total_iterations * len(models)
        self._tracker = ProgressTracker(
            total=total_items,
            run_id=run_id,
            model_id=models[0] if models else "unknown",
            iteration_number=1,
            description="Benchmark Execution",
        )

        logger.info(
            f"ExecutionProgress initialized: {total_items} total items, "
            f"models={models}"
        )

    def start(self) -> None:
        """Start the execution progress tracking."""
        self._tracker.start()
        logger.info(f"Execution started for run {self.run_id}")

    def update(self, advance: int = 1) -> None:
        """Update progress by advancing the counter.

        Args:
            advance: Number of items to advance.
        """
        self.questions_completed += advance
        self._tracker.update(advance)

    def set_current_model(self, model_index: int, model_id: str) -> None:
        """Set the current model being processed.

        Args:
            model_index: Index of the current model.
            model_id: ID of the current model.
        """
        self.current_model_index = model_index
        self._tracker.model_id = model_id
        logger.info(f"Switched to model {model_id} ({model_index + 1}/{len(self.models)})")

    def set_current_iteration(self, iteration: int) -> None:
        """Set the current iteration number.

        Args:
            iteration: Current iteration number (1-based).
        """
        self.current_iteration = iteration
        self._tracker.iteration_number = iteration
        logger.info(f"Starting iteration {iteration}/{self.total_iterations}")

    def get_status(self) -> str:
        """Get the current execution status.

        Returns:
            Status string with execution progress.
        """
        return self._tracker.get_status()

    def display(self) -> None:
        """Display the progress bar."""
        self._tracker.display()

    def finish(self) -> None:
        """Mark the execution as complete."""
        self._tracker.finish()
        logger.info(f"Execution completed for run {self.run_id}")
