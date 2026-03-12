"""Manual review UI module for benchmark_llm project.

This module provides a CLI-based interface for manually reviewing
LLM responses that were classified as ambiguous, no_answer, or
low_confidence during automatic parsing.

The review interface:
- Shows pending responses grouped by question
- Displays question stem, options, and LLM response
- Allows quick classification via keyboard (A/B/C/D/N/E)
- Tracks progress and statistics
- Saves changes to the database

Example:
    >>> from src.cli.review_ui import ReviewUI
    >>> ui = ReviewUI(db_manager)
    >>> ui.start_review_by_experiment("exp-001")
"""

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.db.models import Response
from src.db.repository import ResponseRepository
from src.db.schema import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """A single item pending manual review.

    Attributes:
        response: The Response object to review.
        question_stem: The question text/stem.
        question_options: The answer options as a dictionary.
        correct_answer: The correct answer key (for reference).

    Example:
        >>> item = ReviewItem(
        ...     response=response,
        ...     question_stem="What is the capital of France?",
        ...     question_options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Madrid"},
        ...     correct_answer="B"
        ... )
    """

    response: Response
    question_stem: str
    question_options: dict[str, str]
    correct_answer: str


@dataclass
class ReviewStatistics:
    """Statistics for a review session.

    Attributes:
        total_pending: Total number of items pending review.
        total_processed: Total number of items processed in this session.
        by_question: Count of pending items grouped by question ID.
        by_model: Count of pending items grouped by model ID.
        by_confidence: Count of pending items grouped by parse confidence.

    Example:
        >>> stats = ReviewStatistics(
        ...     total_pending=23,
        ...     total_processed=10,
        ...     by_question={"Q001": 3, "Q002": 5},
        ...     by_model={"gpt-4": 10, "claude-3": 13},
        ...     by_confidence={"ambiguous": 15, "no_answer": 8}
        ... )
    """

    total_pending: int = 0
    total_processed: int = 0
    by_question: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)
    by_confidence: dict[str, int] = field(default_factory=dict)


class ReviewUI:
    """CLI-based interface for manual review of LLM responses.

    This class provides an interactive terminal interface for reviewing
    and classifying LLM responses that couldn't be automatically parsed.

    Features:
        - Grouped display by question (all iterations together)
        - Quick keyboard navigation (A/B/C/D/N/E/S/Q/Z)
        - Real-time progress tracking
        - Automatic saving to database

    Keyboard shortcuts:
        A/B/C/D  - Select answer alternative
        N        - No clear answer
        E        - Error not detected (technical issue)
        S        - Skip (save for later)
        Q        - Quit and save progress
        Z        - Undo last classification

    Example:
        >>> ui = ReviewUI(db_manager)
        >>> ui.start_review_by_experiment("exp-001")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the ReviewUI.

        Args:
            db_manager: DatabaseManager instance for database operations.

        Example:
            >>> ui = ReviewUI(db_manager)
        """
        self.db_manager = db_manager
        self._response_repository = ResponseRepository(db_manager)
        self._pending_items: list[ReviewItem] = []
        self._current_index = 0
        self._statistics = ReviewStatistics()
        self._history: list[tuple[int, str]] = []  # (index, previous_status)

    def get_pending_by_experiment(self, experiment_id: str) -> list[ReviewItem]:
        """Get pending review items for an experiment.

        Args:
            experiment_id: ID of the experiment to review.

        Returns:
            List of ReviewItem objects pending review, grouped by question.

        Example:
            >>> items = ui.get_pending_by_experiment("exp-001")
            >>> print(f"Found {len(items)} items to review")
        """
        # Query responses with low confidence that haven't been manually reviewed
        # Join with question_snapshots to get question details
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.response_id, r.run_id, r.snapshot_id, r.question_id, r.model_id,
                       r.iteration, r.selected_answer, r.response_text, r.is_correct,
                       r.status, r.finish_reason, r.error_details, r.latency_ms,
                       r.input_tokens, r.response_tokens, r.total_tokens, r.reasoning_tokens, r.effective_tokens,
                       r.cost, r.raw_response_json, r.timestamp,
                       r.parse_confidence, r.review_status, r.reviewed_at, r.manual_answer,
                       json_extract(q.question_json, '$.stem') as stem,
                       json_extract(q.question_json, '$.options') as options_json,
                       json_extract(q.question_json, '$.answer_key') as answer_key
                FROM responses r
                JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
                WHERE q.experiment_id = ?
                  AND r.parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
                  AND r.review_status = 'auto'
                ORDER BY r.question_id, r.iteration
                """,
                (experiment_id,),
            )

            items = []
            for row in cursor.fetchall():
                import json

                # Parse options from JSON
                options = json.loads(row["options_json"])

                # Create Response object from row
                response = Response(
                    response_id=row["response_id"],
                    run_id=row["run_id"],
                    snapshot_id=row["snapshot_id"],
                    question_id=row["question_id"],
                    model_id=row["model_id"],
                    iteration=row["iteration"],
                    selected_answer=row["selected_answer"],
                    response_text=row["response_text"],
                    is_correct=row["is_correct"],
                    status=row["status"],
                    finish_reason=row["finish_reason"],
                    error_details=row["error_details"],
                    latency_ms=row["latency_ms"],
                    input_tokens=row["input_tokens"],
                    response_tokens=row["response_tokens"],
                    total_tokens=row["total_tokens"],
                    reasoning_tokens=row["reasoning_tokens"],
                    effective_tokens=row["effective_tokens"],
                    cost=row["cost"],
                    raw_response_json=row["raw_response_json"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    parse_confidence=row["parse_confidence"],
                    review_status=row["review_status"],
                    reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
                    manual_answer=row["manual_answer"],
                )

                items.append(ReviewItem(
                    response=response,
                    question_stem=row["stem"],
                    question_options=options,
                    correct_answer=row["answer_key"],
                ))

            return items
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_pending_by_run(self, run_id: str) -> list[ReviewItem]:
        """Get pending review items for a run.

        Args:
            run_id: ID of the run to review.

        Returns:
            List of ReviewItem objects pending review, grouped by question.

        Example:
            >>> items = ui.get_pending_by_run("run-001")
            >>> print(f"Found {len(items)} items to review")
        """
        # Query responses with low confidence that haven't been manually reviewed
        # Join with question_snapshots to get question details
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.response_id, r.run_id, r.snapshot_id, r.question_id, r.model_id,
                       r.iteration, r.selected_answer, r.response_text, r.is_correct,
                       r.status, r.finish_reason, r.error_details, r.latency_ms,
                       r.input_tokens, r.response_tokens, r.total_tokens, r.reasoning_tokens, r.effective_tokens,
                       r.cost, r.raw_response_json, r.timestamp,
                       r.parse_confidence, r.review_status, r.reviewed_at, r.manual_answer,
                       json_extract(q.question_json, '$.stem') as stem,
                       json_extract(q.question_json, '$.options') as options_json,
                       json_extract(q.question_json, '$.answer_key') as answer_key
                FROM responses r
                JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
                WHERE r.run_id = ?
                  AND r.parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
                  AND r.review_status = 'auto'
                ORDER BY r.question_id, r.iteration
                """,
                (run_id,),
            )

            items = []
            for row in cursor.fetchall():
                import json

                # Parse options from JSON
                options = json.loads(row["options_json"])

                # Create Response object from row
                response = Response(
                    response_id=row["response_id"],
                    run_id=row["run_id"],
                    snapshot_id=row["snapshot_id"],
                    question_id=row["question_id"],
                    model_id=row["model_id"],
                    iteration=row["iteration"],
                    selected_answer=row["selected_answer"],
                    response_text=row["response_text"],
                    is_correct=row["is_correct"],
                    status=row["status"],
                    finish_reason=row["finish_reason"],
                    error_details=row["error_details"],
                    latency_ms=row["latency_ms"],
                    input_tokens=row["input_tokens"],
                    response_tokens=row["response_tokens"],
                    total_tokens=row["total_tokens"],
                    reasoning_tokens=row["reasoning_tokens"],
                    effective_tokens=row["effective_tokens"],
                    cost=row["cost"],
                    raw_response_json=row["raw_response_json"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    parse_confidence=row["parse_confidence"],
                    review_status=row["review_status"],
                    reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
                    manual_answer=row["manual_answer"],
                )

                items.append(ReviewItem(
                    response=response,
                    question_stem=row["stem"],
                    question_options=options,
                    correct_answer=row["answer_key"],
                ))

            return items
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def get_pending_all(self) -> list[ReviewItem]:
        """Get all pending review items across all experiments and runs.

        Returns:
            List of ReviewItem objects pending review, grouped by question.

        Example:
            >>> items = ui.get_pending_all()
            >>> print(f"Found {len(items)} items to review across all experiments")
        """
        # Query all responses with low confidence that haven't been manually reviewed
        # Join with question_snapshots to get question details
        # Extract stem and answer_key from question_json JSON field
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT r.response_id, r.run_id, r.snapshot_id, r.question_id, r.model_id,
                       r.iteration, r.selected_answer, r.response_text, r.is_correct,
                       r.status, r.finish_reason, r.error_details, r.latency_ms,
                       r.input_tokens, r.response_tokens, r.total_tokens, r.reasoning_tokens, r.effective_tokens,
                       r.cost, r.raw_response_json, r.timestamp,
                       r.parse_confidence, r.review_status, r.reviewed_at, r.manual_answer,
                       json_extract(q.question_json, '$.stem') as stem,
                       json_extract(q.question_json, '$.options') as options_json,
                       json_extract(q.question_json, '$.answer_key') as answer_key
                FROM responses r
                JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
                WHERE r.parse_confidence IN ('ambiguous', 'no_answer', 'low_confidence')
                  AND r.review_status = 'auto'
                ORDER BY r.question_id, r.iteration
                """,
            )

            items = []
            for row in cursor.fetchall():
                import json

                # Parse options from JSON
                options = json.loads(row["options_json"])

                # Create Response object from row
                response = Response(
                    response_id=row["response_id"],
                    run_id=row["run_id"],
                    snapshot_id=row["snapshot_id"],
                    question_id=row["question_id"],
                    model_id=row["model_id"],
                    iteration=row["iteration"],
                    selected_answer=row["selected_answer"],
                    response_text=row["response_text"],
                    is_correct=row["is_correct"],
                    status=row["status"],
                    finish_reason=row["finish_reason"],
                    error_details=row["error_details"],
                    latency_ms=row["latency_ms"],
                    input_tokens=row["input_tokens"],
                    response_tokens=row["response_tokens"],
                    total_tokens=row["total_tokens"],
                    reasoning_tokens=row["reasoning_tokens"],
                    effective_tokens=row["effective_tokens"],
                    cost=row["cost"],
                    raw_response_json=row["raw_response_json"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    parse_confidence=row["parse_confidence"],
                    review_status=row["review_status"],
                    reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
                    manual_answer=row["manual_answer"],
                )

                items.append(ReviewItem(
                    response=response,
                    question_stem=row["stem"],
                    question_options=options,
                    correct_answer=row["answer_key"],
                ))

            return items
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def _calculate_statistics(self, items: list[ReviewItem]) -> ReviewStatistics:
        """Calculate review statistics from pending items.

        Args:
            items: List of pending review items.

        Returns:
            ReviewStatistics object with calculated metrics.
        """
        stats = ReviewStatistics(total_pending=len(items))

        # Group by question
        for item in items:
            question_count = stats.by_question.get(item.response.question_id, 0)
            stats.by_question[item.response.question_id] = question_count + 1

            # Group by model
            model_count = stats.by_model.get(item.response.model_id, 0)
            stats.by_model[item.response.model_id] = model_count + 1

            # Group by confidence
            conf_count = stats.by_confidence.get(item.response.parse_confidence, 0)
            stats.by_confidence[item.response.parse_confidence] = conf_count + 1

        return stats

    def _display_item(self, item: ReviewItem, item_number: int, total: int) -> None:
        """Display a single review item.

        Args:
            item: The ReviewItem to display.
            item_number: Current item number (1-based).
            total: Total number of items.
        """
        # Clear screen (works on both Windows and Unix)
        print("\n" * 2)

        # Header
        print("=" * 80)
        print(f"REVIEW MANUAL DE RESPOSTAS  |  Item {item_number}/{total}")
        print("=" * 80)

        # Progress and statistics
        print(f"Pendentes: {self._statistics.total_pending - self._statistics.total_processed}  |  "
              f"Processadas: {self._statistics.total_processed}")
        print(f"Pergunta: {item.response.question_id} (Iteração {item.response.iteration}, Modelo: {item.response.model_id})")
        print(f"Resposta: {item.correct_answer}")
        print(f"Status: {item.response.parse_confidence.upper()}")
        print("=" * 80)

        # Question stem
        print("\nENUNCIADO:")
        print("-" * 80)
        print(item.question_stem)
        print()

        # Options
        print("ALTERNATIVAS:")
        print("-" * 80)
        for key, value in item.question_options.items():
            print(f"  {key}) {value}")
        print()

        # LLM response
        print("RESPOSTA DA LLM:")
        print("-" * 80)
        # Truncate long responses for display
        response_text = item.response.response_text
        if len(response_text) > 800:
            response_text = response_text[:800] + "... (truncado)"
        print(response_text)
        print()

        # Classification options
        print("=" * 80)
        print("CLASSIFICAÇÃO:")
        print("-" * 80)
        print("  [A]  [B]  [C]  [D]  [N]enhuma  [E]rro não detectado")
        print()
        print("  [S] Pular  |  [Q] Sair e salvar  |  [Z] Desfazer última")
        print("=" * 80)

    def _save_classification(
        self, item: ReviewItem, classification: str
    ) -> None:
        """Save a manual classification to the database.

        Args:
            item: The ReviewItem being classified.
            classification: The classification (A, B, C, D, N, E, or S for skip).
        """
        if classification == "S":
            # Skip - don't save
            return

        # Update response
        if classification in ("A", "B", "C", "D"):
            item.response.manual_answer = classification
            item.response.review_status = "manual"
            item.response.reviewed_at = datetime.now()
            # Update selected answer with manual classification
            item.response.selected_answer = classification
            # Recalculate is_correct
            item.response.is_correct = (classification == item.correct_answer)
        elif classification == "N":
            item.response.manual_answer = None
            item.response.review_status = "manual"
            item.response.reviewed_at = datetime.now()
            item.response.selected_answer = None
            item.response.is_correct = False
        elif classification == "E":
            item.response.manual_answer = None
            item.response.review_status = "skipped"
            item.response.reviewed_at = datetime.now()
            item.response.status = "error"

        # Save to database
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE responses
                SET manual_answer = ?, review_status = ?, reviewed_at = ?,
                    selected_answer = ?, is_correct = ?, status = ?
                WHERE response_id = ?
                """,
                (
                    item.response.manual_answer,
                    item.response.review_status,
                    item.response.reviewed_at.isoformat() if item.response.reviewed_at else None,
                    item.response.selected_answer,
                    item.response.is_correct,
                    item.response.status,
                    item.response.response_id,
                ),
            )
            conn.commit()
            logger.info(
                f"Saved manual classification for response {item.response.response_id}: {classification}"
            )
        finally:
            if self.db_manager.should_close_connection():
                conn.close()

    def _get_user_input(self) -> str:
        """Get user input from keyboard.

        Returns:
            Single character input (uppercase).
        """
        try:
            # Use msvcrt for Windows
            if sys.platform == "win32":
                import msvcrt
                char = msvcrt.getwch().upper()
            else:
                # Use termios for Unix
                import termios
                import tty

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    char = sys.stdin.read(1).upper()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            return char
        except Exception as e:
            logger.error(f"Error getting user input: {e}")
            return ""

    def start_review_by_experiment(self, experiment_id: str) -> None:
        """Start the manual review interface for an experiment.

        Args:
            experiment_id: ID of the experiment to review.

        Example:
            >>> ui.start_review_by_experiment("exp-001")
        """
        # Load pending items
        self._pending_items = self.get_pending_by_experiment(experiment_id)

        if not self._pending_items:
            print("\nNenhuma resposta pendente de revisão para este experimento.")
            return

        # Calculate statistics
        self._statistics = self._calculate_statistics(self._pending_items)

        print(f"\nIniciando revisão para o experimento {experiment_id}")
        print(f"Total de itens pendentes: {self._statistics.total_pending}")
        input("\nPressione Enter para começar...")

        # Main review loop
        self._current_index = 0
        while self._current_index < len(self._pending_items):
            item = self._pending_items[self._current_index]
            item_number = self._current_index + 1

            # Display item
            self._display_item(item, item_number, len(self._pending_items))

            # Get user input
            user_input = self._get_user_input()

            # Process input
            if user_input in ("A", "B", "C", "D", "N", "E"):
                # Save classification
                self._save_classification(item, user_input)
                self._statistics.total_processed += 1
                self._current_index += 1
            elif user_input == "S":
                # Skip
                self._current_index += 1
            elif user_input == "Q":
                # Quit
                print("\n\nSalvando progresso e saindo...")
                break
            elif user_input == "Z":
                # Undo
                if self._current_index > 0:
                    self._current_index -= 1
                    self._statistics.total_processed -= 1
                else:
                    print("\nNada para desfazer.")
                    input("Pressione Enter para continuar...")

        print(f"\nRevisão concluída! {self._statistics.total_processed} itens processados.")

    def start_review_all(self) -> None:
        """Start the manual review interface for all pending items.

        This method reviews ALL pending responses across all experiments and runs.

        Example:
            >>> ui.start_review_all()
        """
        # Load pending items
        self._pending_items = self.get_pending_all()

        if not self._pending_items:
            print("\nNenhuma resposta pendente de revisão.")
            return

        # Calculate statistics
        self._statistics = self._calculate_statistics(self._pending_items)

        print(f"\nIniciando revisão de TODAS as respostas pendentes")
        print(f"Total de itens pendentes: {self._statistics.total_pending}")
        
        # Show summary by experiment/run
        if self._statistics.by_model:
            print(f"\nPor modelo:")
            for model_id, count in sorted(self._statistics.by_model.items()):
                print(f"  {model_id}: {count}")
        
        if self._statistics.by_confidence:
            print(f"\nPor confiança:")
            for conf, count in sorted(self._statistics.by_confidence.items()):
                print(f"  {conf}: {count}")
        
        input("\nPressione Enter para começar...")

        # Main review loop
        self._current_index = 0
        while self._current_index < len(self._pending_items):
            item = self._pending_items[self._current_index]
            item_number = self._current_index + 1

            # Display item
            self._display_item(item, item_number, len(self._pending_items))

            # Get user input
            user_input = self._get_user_input()

            # Process input
            if user_input in ("A", "B", "C", "D", "N", "E"):
                # Save classification
                self._save_classification(item, user_input)
                self._statistics.total_processed += 1
                self._current_index += 1
            elif user_input == "S":
                # Skip
                self._current_index += 1
            elif user_input == "Q":
                # Quit
                print("\n\nSalvando progresso e saindo...")
                break
            elif user_input == "Z":
                # Undo
                if self._current_index > 0:
                    self._current_index -= 1
                    self._statistics.total_processed -= 1
                else:
                    print("\nNada para desfazer.")
                    input("Pressione Enter para continuar...")

        print(f"\nRevisão concluída! {self._statistics.total_processed} itens processados.")

    def start_review_by_run(self, run_id: str) -> None:
        """Start the manual review interface for a run.

        Args:
            run_id: ID of the run to review.

        Example:
            >>> ui.start_review_by_run("run-001")
        """
        # Load pending items
        self._pending_items = self.get_pending_by_run(run_id)

        if not self._pending_items:
            print("\nNenhuma resposta pendente de revisão para esta run.")
            return

        # Calculate statistics
        self._statistics = self._calculate_statistics(self._pending_items)

        print(f"\nIniciando revisão para a run {run_id}")
        print(f"Total de itens pendentes: {self._statistics.total_pending}")
        input("\nPressione Enter para começar...")

        # Main review loop
        self._current_index = 0
        while self._current_index < len(self._pending_items):
            item = self._pending_items[self._current_index]
            item_number = self._current_index + 1

            # Display item
            self._display_item(item, item_number, len(self._pending_items))

            # Get user input
            user_input = self._get_user_input()

            # Process input
            if user_input in ("A", "B", "C", "D", "N", "E"):
                # Save classification
                self._save_classification(item, user_input)
                self._statistics.total_processed += 1
                self._current_index += 1
            elif user_input == "S":
                # Skip
                self._current_index += 1
            elif user_input == "Q":
                # Quit
                print("\n\nSalvando progresso e saindo...")
                break
            elif user_input == "Z":
                # Undo
                if self._current_index > 0:
                    self._current_index -= 1
                    self._statistics.total_processed -= 1
                else:
                    print("\nNada para desfazer.")
                    input("Pressione Enter para continuar...")

        print(f"\nRevisão concluída! {self._statistics.total_processed} itens processados.")
