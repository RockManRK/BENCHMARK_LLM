"""Manual review UI module for benchmark_llm project.

This module provides a CLI-based interface for manually reviewing
LLM responses that were classified as needing review during
automatic parsing.

The review interface:
- Shows pending responses grouped by question
- Displays question stem, options, and LLM response
- Allows quick classification via keyboard (A/B/C/D/N/E)
- Tracks progress and statistics
- Saves changes to the database incrementally

Example:
    >>> from src_v2.review.review_ui import ReviewUI
    >>> ui = ReviewUI(conn)
    >>> ui.start_review_by_experiment("exp_001")
"""

import json
import sys
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src_v2.db.models import Response
from src_v2.db.repository import ResponseRepository


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
        by_classification: Count by classification (A, B, C, D, N, E).
        by_question: Count of pending items grouped by question ID.
        by_model: Count of pending items grouped by model ID.

    Example:
        >>> stats = ReviewStatistics(
        ...     total_pending=23,
        ...     total_processed=10,
        ...     by_classification={"A": 5, "B": 3, "C": 2},
        ...     by_question={"Q001": 3, "Q002": 5},
        ...     by_model={"gpt-4": 10, "claude-3": 13}
        ... )
    """

    total_pending: int = 0
    total_processed: int = 0
    by_classification: dict[str, int] = field(default_factory=dict)
    by_question: dict[str, int] = field(default_factory=dict)
    by_model: dict[str, int] = field(default_factory=dict)


class ReviewUI:
    """CLI-based interface for manual review of LLM responses.

    This class provides an interactive terminal interface for reviewing
    and classifying LLM responses that couldn't be automatically parsed.

    Features:
        - Grouped display by question (all iterations together)
        - Quick keyboard navigation (A/B/C/D/N/E/S/Q/Z)
        - Real-time progress tracking
        - Automatic saving to database
        - Cross-platform support (Windows + Linux) via rich library

    Keyboard shortcuts:
        A/B/C/D  - Select answer alternative
        N        - No clear answer
        E        - Error not detected (technical issue)
        S        - Skip (save for later)
        Q        - Quit and save progress
        Z        - Undo last classification

    Example:
        >>> ui = ReviewUI(conn)
        >>> ui.start_review_by_experiment("exp-001")
    """

    CLASSIFICATION_LABELS = {
        "A": "Correct",
        "B": "Partial",
        "C": "Wrong",
        "D": "Empty",
        "N": "None",
        "E": "Error",
    }

    def __init__(self, conn) -> None:
        """Initialize the ReviewUI.

        Args:
            conn: SQLite database connection.

        Example:
            >>> ui = ReviewUI(conn)
        """
        self.conn = conn
        self._response_repository = ResponseRepository(conn)
        self._console = Console()
        self._pending_items: list[ReviewItem] = []
        self._current_index = 0
        self._statistics = ReviewStatistics()
        self._history: list[tuple[int, str]] = []
        self._experiment_id: str = ""
        self._experiment_name: str = ""

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
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.response_id, r.run_id, r.variant_id, r.snapshot_id,
                   r.model_id, r.question_id, r.selected_answer,
                   r.response_text, r.is_correct,
                   r.parse_confidence, r.needs_review, r.manual_answer,
                   r.latency_ms, r.input_tokens, r.output_tokens, r.created_at,
                   json_extract(q.question_payload, '$.stem') as stem,
                   json_extract(q.question_payload, '$.options') as options_json,
                   json_extract(q.question_payload, '$.answer_key') as answer_key
            FROM responses r
            JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
            JOIN runs run ON r.run_id = run.run_id
            WHERE run.experiment_id = ?
              AND r.needs_review = 1
            ORDER BY r.question_id, r.model_id, r.created_at
        """, (experiment_id,))

        items = []
        for row in cursor.fetchall():
            options = json.loads(row["options_json"]) if row["options_json"] else {}

            response = Response(
                response_id=row["response_id"],
                run_id=row["run_id"],
                variant_id=row["variant_id"],
                snapshot_id=row["snapshot_id"],
                model_id=row["model_id"],
                question_id=row["question_id"],
                response_text=row["response_text"],
                selected_answer=row["selected_answer"],
                is_correct=row["is_correct"],
                parse_confidence=row["parse_confidence"] or "unknown",
                needs_review=bool(row["needs_review"]),
                manual_answer=row["manual_answer"],
                latency_ms=row["latency_ms"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                created_at=row["created_at"],
            )

            items.append(ReviewItem(
                response=response,
                question_stem=row["stem"] or "",
                question_options=options,
                correct_answer=row["answer_key"] or "",
            ))

        return items

    def _calculate_statistics(self, items: list[ReviewItem]) -> ReviewStatistics:
        """Calculate review statistics from pending items.

        Args:
            items: List of pending review items.

        Returns:
            ReviewStatistics object with calculated metrics.
        """
        stats = ReviewStatistics(total_pending=len(items))

        for item in items:
            question_count = stats.by_question.get(item.response.question_id, 0)
            stats.by_question[item.response.question_id] = question_count + 1

            model_count = stats.by_model.get(item.response.model_id, 0)
            stats.by_model[item.response.model_id] = model_count + 1

        return stats

    def _display_header(self, item_number: int, total: int) -> None:
        """Display review header with progress and statistics.

        Args:
            item_number: Current item number (1-based).
            total: Total number of items.
        """
        header_text = Text()
        header_text.append("REVIEW MANUAL DE RESPOSTAS", style="bold blue")
        header_text.append(f"  |  Item {item_number}/{total}", style="dim")

        stats_text = Text()
        stats_text.append(f"Pendentes: {self._statistics.total_pending - self._statistics.total_processed}", style="yellow")
        stats_text.append("  |  ", style="dim")
        stats_text.append(f"Processadas: {self._statistics.total_processed}", style="green")

        if self._statistics.by_classification:
            stats_text.append("  |  ", style="dim")
            class_parts = []
            for cls, count in sorted(self._statistics.by_classification.items()):
                if count > 0:
                    class_parts.append(f"{cls}: {count}")
            if class_parts:
                stats_text.append(", ".join(class_parts), style="cyan")

        self._console.print(Panel(
            Text("\n").join([header_text, stats_text]),
            title=f"Experiment: {self._experiment_name}",
            border_style="blue",
        ))

    def _display_item(self, item: ReviewItem, item_number: int, total: int) -> None:
        """Display a single review item.

        Args:
            item: The ReviewItem to display.
            item_number: Current item number (1-based).
            total: Total number of items.
        """
        self._console.print()
        self._display_header(item_number, total)

        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("Label", style="bold cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Pergunta:", item.response.question_id)
        info_table.add_row("Modelo:", item.response.model_id)
        info_table.add_row("Resposta Correta:", item.correct_answer)
        info_table.add_row("Status:", item.response.parse_confidence.upper())

        self._console.print(info_table)
        self._console.print()

        question_panel = Panel(
            Text(item.question_stem, style="white"),
            title="[bold]ENUNCIADO[/bold]",
            border_style="cyan",
        )
        self._console.print(question_panel)
        self._console.print()

        options_table = Table(show_header=False, box=None, padding=(0, 1))
        options_table.add_column("Key", style="bold yellow", width=3)
        options_table.add_column("Value", style="white")

        for key, value in sorted(item.question_options.items()):
            options_table.add_row(f"{key})", value)

        options_panel = Panel(
            options_table,
            title="[bold]ALTERNATIVAS[/bold]",
            border_style="yellow",
        )
        self._console.print(options_panel)
        self._console.print()

        response_text = item.response.response_text or "(no response)"
        if len(response_text) > 800:
            response_text = response_text[:800] + "\n\n... (truncado)"

        response_panel = Panel(
            Text(response_text, style="dim white"),
            title="[bold]RESPOSTA DA LLM[/bold]",
            border_style="dim",
        )
        self._console.print(response_panel)
        self._console.print()

        classification_table = Table(show_header=False, box=None, padding=(0, 2))
        classification_table.add_column("Key", style="bold green", width=10)
        classification_table.add_column("Action", style="white")

        classification_table.add_row("[A]", "Correta")
        classification_table.add_row("[B]", "Parcial")
        classification_table.add_row("[C]", "Errada")
        classification_table.add_row("[D]", "Vazia")
        classification_table.add_row("[N]", "Nenhuma")
        classification_table.add_row("[E]", "Erro não detectado")

        navigation_table = Table(show_header=False, box=None, padding=(0, 2))
        navigation_table.add_column("Key", style="bold cyan")
        navigation_table.add_column("Action", style="dim")

        navigation_table.add_row("[S]", "Pular")
        navigation_table.add_row("[Q]", "Sair e salvar")
        navigation_table.add_row("[Z]", "Desfazer última")

        controls_panel = Panel(
            Text("\n").join([
                Text("CLASSIFICAÇÃO:", style="bold"),
                classification_table,
                Text("\nNAVIGAÇÃO:", style="bold"),
                navigation_table,
            ]),
            border_style="green",
        )
        self._console.print(controls_panel)

    def _save_classification(self, item: ReviewItem, classification: str) -> None:
        """Save a manual classification to the database.

        Args:
            item: The ReviewItem being classified.
            classification: The classification (A, B, C, D, N, E, or S for skip).
        """
        if classification == "S":
            return

        cursor = self.conn.cursor()

        if classification in ("A", "B", "C", "D"):
            item.response.manual_answer = classification
            item.response.needs_review = False
            item.response.selected_answer = classification
            item.response.is_correct = (classification.upper() == item.correct_answer.upper())
        elif classification == "N":
            item.response.manual_answer = None
            item.response.needs_review = False
            item.response.selected_answer = None
            item.response.is_correct = False
        elif classification == "E":
            item.response.manual_answer = None
            item.response.needs_review = False
            item.response.selected_answer = None
            item.response.is_correct = False

        cursor.execute("""
            UPDATE responses
            SET manual_answer = ?, needs_review = ?,
                selected_answer = ?, is_correct = ?
            WHERE response_id = ?
        """, (
            item.response.manual_answer,
            0,
            item.response.selected_answer,
            item.response.is_correct,
            item.response.response_id,
        ))
        self.conn.commit()

        classification_label = self.CLASSIFICATION_LABELS.get(classification, classification)
        self._console.print(f"[green]✓[/green] Classificado como [bold]{classification}[/bold] ({classification_label})")

    def _get_user_input(self) -> str:
        """Get user input from keyboard.

        Returns:
            Single character input (uppercase).
        """
        try:
            if sys.platform == "win32":
                import msvcrt
                char = msvcrt.getwch().upper()
            else:
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
            self._console.print(f"[red]Error getting user input: {e}[/red]")
            return ""

    def _confirm_quit(self) -> bool:
        """Ask user to confirm quit.

        Returns:
            True if user confirms quit, False otherwise.
        """
        self._console.print()
        self._console.print("[yellow]Tem certeza que deseja sair? (y/n): [/yellow]", end="")
        try:
            if sys.platform == "win32":
                import msvcrt
                char = msvcrt.getwch().upper()
            else:
                import termios
                import tty

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    char = sys.stdin.read(1).upper()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

            self._console.print(char)
            return char == "Y"
        except Exception:
            return False

    def start_review_by_experiment(self, experiment_name: str) -> None:
        """Start the manual review interface for an experiment.

        Args:
            experiment_name: Name of the experiment to review.

        Example:
            >>> ui.start_review_by_experiment("exp-001")
        """
        from src_v2.db.repository import ExperimentRepository

        exp_repo = ExperimentRepository(self.conn)
        experiment = exp_repo.get_by_name(experiment_name)

        if not experiment:
            self._console.print(f"[red]Erro: Experimento não encontrado: {experiment_name}[/red]")
            return

        self._experiment_id = experiment.experiment_id
        self._experiment_name = experiment.name

        self._pending_items = self.get_pending_by_experiment(self._experiment_id)

        if not self._pending_items:
            self._console.print()
            self._console.print("[green]✓[/green] Nenhuma resposta pendente de revisão para este experimento.")
            return

        self._statistics = self._calculate_statistics(self._pending_items)

        self._console.print()
        self._console.print(Panel(
            f"[bold]Iniciando revisão para o experimento {self._experiment_name}[/bold]\n\n"
            f"Total de itens pendentes: [yellow]{self._statistics.total_pending}[/yellow]\n\n"
            f"Use as teclas [bold]A/B/C/D/N/E[/bold] para classificar\n"
            f"Pressione [bold]Enter[/bold] para começar...",
            title="Review UI",
            border_style="green",
        ))

        input()

        self._current_index = 0

        while self._current_index < len(self._pending_items):
            item = self._pending_items[self._current_index]
            item_number = self._current_index + 1

            self._console.clear()
            self._display_item(item, item_number, len(self._pending_items))

            self._console.print()
            self._console.print("[bold cyan]Sua escolha: [/bold cyan]", end="")

            user_input = self._get_user_input()
            self._console.print(user_input)

            if user_input in ("A", "B", "C", "D", "N", "E"):
                previous_answer = item.response.manual_answer or item.response.selected_answer or "None"
                self._history.append((self._current_index, previous_answer))

                self._save_classification(item, user_input)

                class_count = self._statistics.by_classification.get(user_input, 0)
                self._statistics.by_classification[user_input] = class_count + 1
                self._statistics.total_processed += 1
                self._current_index += 1

            elif user_input == "S":
                self._current_index += 1

            elif user_input == "Q":
                if self._confirm_quit():
                    self._console.print("\n[yellow]Salvando progresso e saindo...[/yellow]")
                    break

            elif user_input == "Z":
                if self._current_index > 0:
                    self._current_index -= 1
                    self._statistics.total_processed -= 1

                    if self._history:
                        prev_index, prev_answer = self._history.pop()
                        if prev_index == self._current_index:
                            self._console.print(f"[yellow]Desfeito: classificação anterior era {prev_answer}[/yellow]")
                else:
                    self._console.print("\n[yellow]Nada para desfazer.[/yellow]")
                    input("Pressione Enter para continuar...")

        self._console.print()
        self._console.print(Panel(
            f"[bold green]Revisão concluída![/bold green]\n\n"
            f"[bold]{self._statistics.total_processed}[/bold] itens processados.\n\n"
            f"Classificações:\n" +
            "\n".join([f"  {k}: {v}" for k, v in sorted(self._statistics.by_classification.items()) if v > 0]),
            title="Resumo",
            border_style="green",
        ))

    def start_review_all(self) -> None:
        """Start the manual review interface for all pending items.

        This method reviews ALL pending responses across all experiments and runs.

        Example:
            >>> ui.start_review_all()
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT r.response_id, r.run_id, r.variant_id, r.snapshot_id,
                   r.model_id, r.question_id, r.selected_answer,
                   r.response_text, r.is_correct,
                   r.parse_confidence, r.needs_review, r.manual_answer,
                   r.latency_ms, r.input_tokens, r.output_tokens, r.created_at,
                   json_extract(q.question_payload, '$.stem') as stem,
                   json_extract(q.question_payload, '$.options') as options_json,
                   json_extract(q.question_payload, '$.answer_key') as answer_key,
                   run.experiment_id
            FROM responses r
            JOIN question_snapshots q ON r.snapshot_id = q.snapshot_id
            JOIN runs run ON r.run_id = run.run_id
            WHERE r.needs_review = 1
            ORDER BY run.experiment_id, r.question_id, r.model_id, r.created_at
        """)

        items = []
        for row in cursor.fetchall():
            options = json.loads(row["options_json"]) if row["options_json"] else {}

            response = Response(
                response_id=row["response_id"],
                run_id=row["run_id"],
                variant_id=row["variant_id"],
                snapshot_id=row["snapshot_id"],
                model_id=row["model_id"],
                question_id=row["question_id"],
                response_text=row["response_text"],
                selected_answer=row["selected_answer"],
                is_correct=row["is_correct"],
                parse_confidence=row["parse_confidence"] or "unknown",
                needs_review=bool(row["needs_review"]),
                manual_answer=row["manual_answer"],
                latency_ms=row["latency_ms"],
                input_tokens=row["input_tokens"],
                output_tokens=row["output_tokens"],
                created_at=row["created_at"],
            )

            items.append(ReviewItem(
                response=response,
                question_stem=row["stem"] or "",
                question_options=options,
                correct_answer=row["answer_key"] or "",
            ))

        if not items:
            self._console.print()
            self._console.print("[green]✓[/green] Nenhuma resposta pendente de revisão.")
            return

        self._pending_items = items
        self._statistics = self._calculate_statistics(items)
        self._experiment_name = "Todos Experimentos"

        self._console.print()
        self._console.print(Panel(
            f"[bold]Iniciando revisão de TODAS as respostas pendentes[/bold]\n\n"
            f"Total de itens pendentes: [yellow]{self._statistics.total_pending}[/yellow]\n\n"
            f"Por modelo:\n" +
            "\n".join([f"  {m}: {c}" for m, c in sorted(self._statistics.by_model.items())]),
            title="Review UI - All Experiments",
            border_style="green",
        ))

        input("\nPressione Enter para começar...")

        self._current_index = 0

        while self._current_index < len(self._pending_items):
            item = self._pending_items[self._current_index]
            item_number = self._current_index + 1

            self._console.clear()
            self._display_item(item, item_number, len(self._pending_items))

            self._console.print()
            self._console.print("[bold cyan]Sua escolha: [/bold cyan]", end="")

            user_input = self._get_user_input()
            self._console.print(user_input)

            if user_input in ("A", "B", "C", "D", "N", "E"):
                previous_answer = item.response.manual_answer or item.response.selected_answer or "None"
                self._history.append((self._current_index, previous_answer))

                self._save_classification(item, user_input)

                class_count = self._statistics.by_classification.get(user_input, 0)
                self._statistics.by_classification[user_input] = class_count + 1
                self._statistics.total_processed += 1
                self._current_index += 1

            elif user_input == "S":
                self._current_index += 1

            elif user_input == "Q":
                if self._confirm_quit():
                    self._console.print("\n[yellow]Salvando progresso e saindo...[/yellow]")
                    break

            elif user_input == "Z":
                if self._current_index > 0:
                    self._current_index -= 1
                    self._statistics.total_processed -= 1

                    if self._history:
                        prev_index, prev_answer = self._history.pop()
                        if prev_index == self._current_index:
                            self._console.print(f"[yellow]Desfeito: classificação anterior era {prev_answer}[/yellow]")
                else:
                    self._console.print("\n[yellow]Nada para desfazer.[/yellow]")
                    input("Pressione Enter para continuar...")

        self._console.print()
        self._console.print(Panel(
            f"[bold green]Revisão concluída![/bold green]\n\n"
            f"[bold]{self._statistics.total_processed}[/bold] itens processados.\n\n"
            f"Classificações:\n" +
            "\n".join([f"  {k}: {v}" for k, v in sorted(self._statistics.by_classification.items()) if v > 0]),
            title="Resumo",
            border_style="green",
        ))
