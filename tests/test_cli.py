"""Tests for CLI module of benchmark_llm project.

This module contains unit tests for CLI argument parsing,
statistics calculations, and output formatting.
"""

import csv
import json
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.cli.cli import CLIParser, parse_arguments
from src.cli.statistics import BenchmarkStatistics, StatisticsCalculator
from src.cli.output_formatter import OutputFormatter, ConsoleFormatter


class TestCLIParser:
    """Test cases for CLIParser class."""

    def test_init_creates_parser(self) -> None:
        """Test that CLIParser initializes correctly."""
        parser = CLIParser()
        assert parser is not None
        assert parser.parser is not None

    def test_parse_models_single(self) -> None:
        """Test parsing a single model argument."""
        parser = CLIParser()
        args = parser.parse(["--models", "gpt-4"])
        assert args.models == ["gpt-4"]

    def test_parse_models_multiple(self) -> None:
        """Test parsing multiple model arguments."""
        parser = CLIParser()
        args = parser.parse(["--models", "gpt-4", "claude-3", "gemini-pro"])
        assert args.models == ["gpt-4", "claude-3", "gemini-pro"]

    def test_parse_iterations_default(self) -> None:
        """Test that iterations defaults to 1."""
        parser = CLIParser()
        args = parser.parse([])
        assert args.iterations == 1

    def test_parse_iterations_custom(self) -> None:
        """Test parsing custom iterations value."""
        parser = CLIParser()
        args = parser.parse(["--iterations", "5"])
        assert args.iterations == 5

    def test_parse_iterations_invalid(self) -> None:
        """Test that invalid iterations raises error."""
        parser = CLIParser()
        with pytest.raises(SystemExit):
            parser.parse(["--iterations", "0"])

    def test_parse_questions_single(self) -> None:
        """Test parsing a single question filter."""
        parser = CLIParser()
        args = parser.parse(["--questions", "Q001"])
        assert args.questions == ["Q001"]

    def test_parse_questions_multiple(self) -> None:
        """Test parsing multiple question filters."""
        parser = CLIParser()
        args = parser.parse(["--questions", "Q001", "Q002", "Q003"])
        assert args.questions == ["Q001", "Q002", "Q003"]

    def test_parse_questions_range(self) -> None:
        """Test parsing question range."""
        parser = CLIParser()
        args = parser.parse(["--questions", "Q001-Q010"])
        assert args.questions is not None
        assert "Q001" in args.questions
        assert "Q010" in args.questions

    def test_parse_config_file(self) -> None:
        """Test parsing config file argument."""
        parser = CLIParser()
        args = parser.parse(["--config", "config.yaml"])
        assert args.config == Path("config.yaml")

    def test_parse_output_format_default(self) -> None:
        """Test that output format defaults to console."""
        parser = CLIParser()
        args = parser.parse([])
        assert args.output == "console"

    def test_parse_output_format_json(self) -> None:
        """Test parsing JSON output format."""
        parser = CLIParser()
        args = parser.parse(["--output", "json"])
        assert args.output == "json"

    def test_parse_output_format_csv(self) -> None:
        """Test parsing CSV output format."""
        parser = CLIParser()
        args = parser.parse(["--output", "csv"])
        assert args.output == "csv"

    def test_parse_output_format_markdown(self) -> None:
        """Test parsing Markdown output format."""
        parser = CLIParser()
        args = parser.parse(["--output", "markdown"])
        assert args.output == "markdown"

    def test_parse_output_file(self) -> None:
        """Test parsing output file argument."""
        parser = CLIParser()
        args = parser.parse(["--output-file", "results.json"])
        assert args.output_file == Path("results.json")

    def test_parse_seed(self) -> None:
        """Test parsing random seed argument."""
        parser = CLIParser()
        args = parser.parse(["--seed", "42"])
        assert args.seed == 42

    def test_parse_verbose(self) -> None:
        """Test parsing verbose flag."""
        parser = CLIParser()
        args = parser.parse(["--verbose"])
        assert args.verbose is True

    def test_parse_dry_run(self) -> None:
        """Test parsing dry-run flag."""
        parser = CLIParser()
        args = parser.parse(["--dry-run"])
        assert args.dry_run is True

    def test_parse_all_arguments(self) -> None:
        """Test parsing all arguments together."""
        parser = CLIParser()
        args = parser.parse([
            "--models", "gpt-4", "claude-3",
            "--iterations", "3",
            "--questions", "Q001-Q010",
            "--config", "config.yaml",
            "--output", "json",
            "--output-file", "results.json",
            "--seed", "42",
            "--verbose",
            "--dry-run",
        ])
        assert args.models == ["gpt-4", "claude-3"]
        assert args.iterations == 3
        assert args.questions is not None
        assert args.config == Path("config.yaml")
        assert args.output == "json"
        assert args.output_file == Path("results.json")
        assert args.seed == 42
        assert args.verbose is True
        assert args.dry_run is True


class TestParseArguments:
    """Test cases for parse_arguments convenience function."""

    def test_parse_arguments_returns_args(self) -> None:
        """Test that parse_arguments returns parsed args."""
        with patch.object(sys, 'argv', ['benchmark_llm', '--models', 'gpt-4']):
            args = parse_arguments()
            assert args.models == ["gpt-4"]


class TestBenchmarkStatistics:
    """Test cases for BenchmarkStatistics dataclass."""

    def test_create_statistics(self) -> None:
        """Test creating BenchmarkStatistics instance."""
        stats = BenchmarkStatistics(
            model_id="gpt-4",
            total_questions=100,
            correct_answers=85,
            accuracy=0.85,
            avg_latency_ms=1500.0,
            min_latency_ms=800,
            max_latency_ms=3000,
            total_input_tokens=50000,
            total_output_tokens=10000,
            error_count=5,
            error_rate=0.05,
        )
        assert stats.model_id == "gpt-4"
        assert stats.accuracy == 0.85
        assert stats.avg_latency_ms == 1500.0

    def test_statistics_default_values(self) -> None:
        """Test BenchmarkStatistics default values."""
        stats = BenchmarkStatistics(model_id="test-model")
        assert stats.total_questions == 0
        assert stats.correct_answers == 0
        assert stats.accuracy == 0.0
        assert stats.avg_latency_ms == 0.0
        assert stats.error_count == 0


class TestStatisticsCalculator:
    """Test cases for StatisticsCalculator class."""

    @pytest.fixture
    def sample_responses(self) -> list[dict[str, Any]]:
        """Provide sample response data for testing."""
        return [
            {
                "response_id": 1,
                "iteration_id": 1,
                "question_id": "Q001",
                "model_id": "gpt-4",
                "run_id": "run-001",
                "selected_answer": "A",
                "correct_answer": "A",
                "is_correct": True,
                "input_tokens": 500,
                "output_tokens": 100,
                "latency_ms": 1200,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            },
            {
                "response_id": 2,
                "iteration_id": 1,
                "question_id": "Q002",
                "model_id": "gpt-4",
                "run_id": "run-001",
                "selected_answer": "B",
                "correct_answer": "A",
                "is_correct": False,
                "input_tokens": 450,
                "output_tokens": 80,
                "latency_ms": 1800,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            },
            {
                "response_id": 3,
                "iteration_id": 1,
                "question_id": "Q003",
                "model_id": "gpt-4",
                "run_id": "run-001",
                "selected_answer": None,
                "correct_answer": "C",
                "is_correct": False,
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "status": "error",
                "timestamp": datetime.now().isoformat(),
            },
        ]

    @pytest.fixture
    def sample_errors(self) -> list[dict[str, Any]]:
        """Provide sample error data for testing."""
        return [
            {
                "error_id": 1,
                "response_id": 3,
                "error_type": "APIError",
                "error_message": "Rate limit exceeded",
                "timestamp": datetime.now().isoformat(),
            },
        ]

    def test_calculate_accuracy(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test accuracy calculation."""
        calculator = StatisticsCalculator(sample_responses, [])
        accuracy = calculator.calculate_accuracy("gpt-4")
        assert accuracy == 0.5  # 1 correct out of 2 answered

    def test_calculate_avg_latency(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test average latency calculation."""
        calculator = StatisticsCalculator(sample_responses, [])
        avg_latency = calculator.calculate_avg_latency("gpt-4")
        assert avg_latency == 1500.0  # (1200 + 1800) / 2

    def test_calculate_latency_min_max(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test min/max latency calculation."""
        calculator = StatisticsCalculator(sample_responses, [])
        min_lat, max_lat = calculator.calculate_latency_min_max("gpt-4")
        assert min_lat == 1200
        assert max_lat == 1800

    def test_calculate_token_usage(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test token usage calculation."""
        calculator = StatisticsCalculator(sample_responses, [])
        input_tokens, output_tokens = calculator.calculate_token_usage("gpt-4")
        assert input_tokens == 950  # 500 + 450
        assert output_tokens == 180  # 100 + 80

    def test_calculate_error_rate(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test error rate calculation."""
        calculator = StatisticsCalculator(sample_responses, [])
        error_count, error_rate = calculator.calculate_error_summary("gpt-4")
        assert error_count == 1
        assert error_rate == 1.0 / 3.0  # 1 error out of 3 total

    def test_calculate_consistency(self) -> None:
        """Test consistency calculation across iterations."""
        responses = [
            {
                "response_id": 1,
                "iteration_id": 1,
                "question_id": "Q001",
                "model_id": "gpt-4",
                "selected_answer": "A",
                "is_correct": True,
                "status": "success",
            },
            {
                "response_id": 2,
                "iteration_id": 2,
                "question_id": "Q001",
                "model_id": "gpt-4",
                "selected_answer": "A",
                "is_correct": True,
                "status": "success",
            },
            {
                "response_id": 3,
                "iteration_id": 3,
                "question_id": "Q001",
                "model_id": "gpt-4",
                "selected_answer": "B",
                "is_correct": False,
                "status": "success",
            },
        ]
        calculator = StatisticsCalculator(responses, [])
        consistency = calculator.calculate_consistency("gpt-4", "Q001")
        assert consistency == pytest.approx(0.666, rel=0.01)  # 2 out of 3 same answers

    def test_get_model_statistics(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test getting complete statistics for a model."""
        calculator = StatisticsCalculator(sample_responses, [])
        stats = calculator.get_model_statistics("gpt-4")
        assert stats.model_id == "gpt-4"
        assert stats.total_questions == 3
        assert stats.correct_answers == 1
        assert stats.error_count == 1

    def test_get_all_model_ids(self, sample_responses: list[dict[str, Any]]) -> None:
        """Test getting all unique model IDs."""
        responses = sample_responses + [
            {
                "response_id": 4,
                "iteration_id": 1,
                "question_id": "Q001",
                "model_id": "claude-3",
                "selected_answer": "A",
                "is_correct": True,
                "status": "success",
            },
        ]
        calculator = StatisticsCalculator(responses, [])
        model_ids = calculator.get_all_model_ids()
        assert "gpt-4" in model_ids
        assert "claude-3" in model_ids

    def test_empty_responses(self) -> None:
        """Test statistics calculation with empty responses."""
        calculator = StatisticsCalculator([], [])
        stats = calculator.get_model_statistics("gpt-4")
        assert stats.total_questions == 0
        assert stats.accuracy == 0.0


class TestOutputFormatter:
    """Test cases for OutputFormatter base class."""

    def test_formatter_init(self) -> None:
        """Test OutputFormatter initialization."""
        formatter = OutputFormatter()
        assert formatter is not None


class TestConsoleFormatter:
    """Test cases for ConsoleFormatter class."""

    @pytest.fixture
    def sample_statistics(self) -> list[BenchmarkStatistics]:
        """Provide sample statistics for testing."""
        return [
            BenchmarkStatistics(
                model_id="gpt-4",
                total_questions=100,
                correct_answers=85,
                accuracy=0.85,
                avg_latency_ms=1500.0,
                min_latency_ms=800,
                max_latency_ms=3000,
                total_input_tokens=50000,
                total_output_tokens=10000,
                error_count=5,
                error_rate=0.05,
            ),
            BenchmarkStatistics(
                model_id="claude-3",
                total_questions=100,
                correct_answers=90,
                accuracy=0.90,
                avg_latency_ms=1200.0,
                min_latency_ms=600,
                max_latency_ms=2500,
                total_input_tokens=45000,
                total_output_tokens=9000,
                error_count=3,
                error_rate=0.03,
            ),
        ]

    def test_console_formatter_format_table(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test console table formatting."""
        formatter = ConsoleFormatter()
        output = formatter.format_table(sample_statistics)
        assert output is not None
        assert "gpt-4" in output or "claude-3" in output

    def test_console_formatter_format_summary(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test console summary formatting."""
        formatter = ConsoleFormatter()
        output = formatter.format_summary(sample_statistics)
        assert output is not None
        assert "models" in output.lower() or "benchmark" in output.lower()


class TestJSONFormatter:
    """Test cases for JSON output formatting."""

    @pytest.fixture
    def sample_statistics(self) -> list[BenchmarkStatistics]:
        """Provide sample statistics for testing."""
        return [
            BenchmarkStatistics(
                model_id="gpt-4",
                total_questions=100,
                correct_answers=85,
                accuracy=0.85,
                avg_latency_ms=1500.0,
                min_latency_ms=800,
                max_latency_ms=3000,
                total_input_tokens=50000,
                total_output_tokens=10000,
                error_count=5,
                error_rate=0.05,
            ),
        ]

    def test_json_formatter_export(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test JSON export formatting."""
        formatter = OutputFormatter()
        json_output = formatter.to_json(sample_statistics)
        parsed = json.loads(json_output)
        assert len(parsed) == 1
        assert parsed[0]["model_id"] == "gpt-4"
        assert parsed[0]["accuracy"] == 0.85

    def test_json_formatter_valid_json(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test that JSON output is valid JSON."""
        formatter = OutputFormatter()
        json_output = formatter.to_json(sample_statistics)
        # Should not raise
        parsed = json.loads(json_output)
        assert isinstance(parsed, list)


class TestCSVFormatter:
    """Test cases for CSV output formatting."""

    @pytest.fixture
    def sample_statistics(self) -> list[BenchmarkStatistics]:
        """Provide sample statistics for testing."""
        return [
            BenchmarkStatistics(
                model_id="gpt-4",
                total_questions=100,
                correct_answers=85,
                accuracy=0.85,
                avg_latency_ms=1500.0,
                min_latency_ms=800,
                max_latency_ms=3000,
                total_input_tokens=50000,
                total_output_tokens=10000,
                error_count=5,
                error_rate=0.05,
            ),
            BenchmarkStatistics(
                model_id="claude-3",
                total_questions=100,
                correct_answers=90,
                accuracy=0.90,
                avg_latency_ms=1200.0,
                min_latency_ms=600,
                max_latency_ms=2500,
                total_input_tokens=45000,
                total_output_tokens=9000,
                error_count=3,
                error_rate=0.03,
            ),
        ]

    def test_csv_formatter_export(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test CSV export formatting."""
        formatter = OutputFormatter()
        csv_output = formatter.to_csv(sample_statistics)
        assert "model_id" in csv_output
        assert "gpt-4" in csv_output
        assert "claude-3" in csv_output

    def test_csv_formatter_valid_csv(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test that CSV output is valid CSV."""
        formatter = OutputFormatter()
        csv_output = formatter.to_csv(sample_statistics)
        # Parse CSV to verify it's valid
        reader = csv.DictReader(StringIO(csv_output))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["model_id"] == "gpt-4"
        assert rows[1]["model_id"] == "claude-3"


class TestMarkdownFormatter:
    """Test cases for Markdown output formatting."""

    @pytest.fixture
    def sample_statistics(self) -> list[BenchmarkStatistics]:
        """Provide sample statistics for testing."""
        return [
            BenchmarkStatistics(
                model_id="gpt-4",
                total_questions=100,
                correct_answers=85,
                accuracy=0.85,
                avg_latency_ms=1500.0,
                min_latency_ms=800,
                max_latency_ms=3000,
                total_input_tokens=50000,
                total_output_tokens=10000,
                error_count=5,
                error_rate=0.05,
            ),
        ]

    def test_markdown_formatter_export(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test Markdown export formatting."""
        formatter = OutputFormatter()
        md_output = formatter.to_markdown(sample_statistics)
        assert "| model_id |" in md_output or "| Model" in md_output
        assert "gpt-4" in md_output

    def test_markdown_formatter_table_structure(self, sample_statistics: list[BenchmarkStatistics]) -> None:
        """Test Markdown table structure."""
        formatter = OutputFormatter()
        md_output = formatter.to_markdown(sample_statistics)
        # Check for markdown table elements
        assert "|" in md_output
        # Check for header separator
        assert "|---" in md_output or "| ---" in md_output


class TestOutputFormatterExportToFile:
    """Test cases for exporting formatted output to files."""

    @pytest.fixture
    def sample_statistics(self) -> list[BenchmarkStatistics]:
        """Provide sample statistics for testing."""
        return [
            BenchmarkStatistics(
                model_id="gpt-4",
                total_questions=100,
                correct_answers=85,
                accuracy=0.85,
                avg_latency_ms=1500.0,
                min_latency_ms=800,
                max_latency_ms=3000,
                total_input_tokens=50000,
                total_output_tokens=10000,
                error_count=5,
                error_rate=0.05,
            ),
        ]

    def test_export_json_to_file(self, sample_statistics: list[BenchmarkStatistics], tmp_path: Path) -> None:
        """Test exporting JSON to file."""
        formatter = OutputFormatter()
        output_file = tmp_path / "results.json"
        formatter.export_to_file(sample_statistics, str(output_file), "json")
        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
        assert len(data) == 1

    def test_export_csv_to_file(self, sample_statistics: list[BenchmarkStatistics], tmp_path: Path) -> None:
        """Test exporting CSV to file."""
        formatter = OutputFormatter()
        output_file = tmp_path / "results.csv"
        formatter.export_to_file(sample_statistics, str(output_file), "csv")
        assert output_file.exists()
        with open(output_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1

    def test_export_markdown_to_file(self, sample_statistics: list[BenchmarkStatistics], tmp_path: Path) -> None:
        """Test exporting Markdown to file."""
        formatter = OutputFormatter()
        output_file = tmp_path / "results.md"
        formatter.export_to_file(sample_statistics, str(output_file), "markdown")
        assert output_file.exists()
        with open(output_file) as f:
            content = f.read()
        assert "|" in content

    def test_export_console_to_file(self, sample_statistics: list[BenchmarkStatistics], tmp_path: Path) -> None:
        """Test exporting console output to file."""
        formatter = OutputFormatter()
        output_file = tmp_path / "results.txt"
        formatter.export_to_file(sample_statistics, str(output_file), "console")
        assert output_file.exists()
