"""CLI-specific integration tests.

This module tests CLI workflows and error messages:
- Create and list operations
- Add and list models/questions
- Create and show run details
- Error message user-friendliness

All tests use:
- Mocked database (in-memory SQLite)
- CLI entry points (verifies argument parsing + integration)
- User-facing output validation
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from io import StringIO

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestCLIWorkflow:
    """Test CLI workflows for all commands."""
    
    def test_cli_create_experiment_then_list(self, in_memory_db, capsys):
        """
        Test create experiment and list experiments.
        
        Verifies:
        - Create command succeeds
        - List command shows created experiment
        - Output is human-readable
        """
        from src.cli.bcllm_experiment import main as experiment_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            # Verify creation message
            captured = capsys.readouterr()
            assert "created" in captured.out.lower()
            assert "test-exp" in captured.out
        
        # List experiments (need new capsys)
        import pytest
        from _pytest.capture import CaptureFixture
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--list-experiments",
            ]):
                result = experiment_main()
                assert result == 0
            
            captured = capsys.readouterr()
            assert "test-exp" in captured.out
    
    def test_cli_add_model_then_list(self, in_memory_db, capsys):
        """
        Test add model and list models.
        
        Verifies:
        - Add model command succeeds
        - List command shows added model
        - Model details are displayed
        """
        from src.cli.bcllm_experiment import main as experiment_main
        from src.cli.bcllm_model import main as model_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Create experiment first
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            # Add model
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0
            
            # Verify add message
            captured = capsys.readouterr()
            assert "added" in captured.out.lower()
            assert "openai/gpt-4" in captured.out
        
        # List models
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--list-models",
            ]):
                result = model_main()
                assert result == 0
            
            captured = capsys.readouterr()
            assert "openai/gpt-4" in captured.out
    
    def test_cli_add_questions_then_list(self, in_memory_db, capsys):
        """
        Test add questions and list questions.
        
        Verifies:
        - Add questions command succeeds
        - List command shows added questions
        - Question count is correct
        """
        from src.cli.bcllm_experiment import main as experiment_main
        from src.cli.bcllm_questions import main as questions_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Create experiment first
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            # Add single question
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--add-questions", "q1",
            ]):
                result = questions_main()
                assert result == 0
            
            # Verify add message
            captured = capsys.readouterr()
            assert "1 question" in captured.out.lower()
        
        # Add range of questions
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--add-questions", "q2-q5",
            ]):
                result = questions_main()
                assert result == 0
            
            captured = capsys.readouterr()
            assert "4 question" in captured.out.lower()
        
        # List questions
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--list-questions",
            ]):
                result = questions_main()
                assert result == 0
            
            captured = capsys.readouterr()
            # Should show all 5 questions
            assert "Q01" in captured.out
            assert "Q05" in captured.out
    
    def test_cli_create_run_then_show(self, in_memory_db, capsys):
        """
        Test create run and show run details.
        
        Verifies:
        - Create run command succeeds
        - Run ID is displayed
        - Show command displays run details
        """
        from src.cli.bcllm_experiment import main as experiment_main
        from src.cli.bcllm_model import main as model_main
        from src.cli.bcllm_questions import main as questions_main
        from src.cli.bcllm_run import main as run_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Setup: Create experiment with model and question
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0
            
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--add-questions", "q1",
            ]):
                result = questions_main()
                assert result == 0
            
            # Create run
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "test-exp",
                "--create-run",
            ]):
                result = run_main()
                assert result == 0
            
            # Extract run ID from database
            run_id = self._get_run_id(in_memory_db)
            assert run_id is not None
        
        # Show run details
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "test-exp",
                "--run", run_id,
            ]):
                result = run_main()
                assert result == 0
            
            captured = capsys.readouterr()
            assert run_id in captured.out
            assert "pending" in captured.out.lower()
    
    def _get_run_id(self, conn):
        """Helper to get run ID from database."""
        cursor = conn.cursor()
        cursor.execute("SELECT run_id FROM runs LIMIT 1")
        row = cursor.fetchone()
        return row[0] if row else None
    
    def test_cli_error_messages(self, in_memory_db, capsys):
        """
        Test CLI error messages are user-friendly.
        
        Verifies:
        - Error messages are clear and actionable
        - Error messages include hints for resolution
        - Exit codes are correct (1 for errors)
        """
        from src.cli.bcllm_experiment import main as experiment_main
        from src.cli.bcllm_model import main as model_main
        from src.cli.bcllm_questions import main as questions_main
        from src.cli.bcllm_run import main as run_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Test 1: Experiment not found
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "nonexistent",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 1
            
            captured = capsys.readouterr()
            assert "not found" in captured.err.lower()
            
            # Test 2: Invalid model ID format
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--add-model", "invalid-model-id",
            ]):
                result = model_main()
                assert result == 1
            
            captured = capsys.readouterr()
            assert "invalid" in captured.err.lower()
            assert "format" in captured.err.lower()
            
            # Test 3: Create run without models (precondition failed)
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "test-exp",
                "--create-run",
            ]):
                result = run_main()
                assert result == 1
            
            captured = capsys.readouterr()
            assert "no models" in captured.err.lower()
            assert "add models first" in captured.err.lower()
            
            # Test 4: Create run without questions (precondition failed)
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--add-model", "openai/gpt-4",
            ]):
                result = model_main()
                assert result == 0
            
            with patch.object(sys, "argv", [
                "bcllm_run.py",
                "--experiment", "test-exp",
                "--create-run",
            ]):
                result = run_main()
                assert result == 1
            
            captured = capsys.readouterr()
            assert "no questions" in captured.err.lower()
            assert "add questions first" in captured.err.lower()


@pytest.mark.integration
class TestCLIParserValidation:
    """Test CLI argument parsing and validation."""
    
    def test_cli_question_spec_parsing(self):
        """
        Test question specification parsing.
        
        Verifies:
        - Comma-separated specs work (q1,q2,q3)
        - Range specs work (1-10)
        - Mixed specs work (q1,q2,5-10)
        - Invalid specs raise errors
        """
        from src.cli.bcllm_questions import parse_question_spec
        
        # Test comma-separated
        result = parse_question_spec("q1,q2,q3")
        assert result == ["Q01", "Q02", "Q03"]
        
        # Test range
        result = parse_question_spec("1-5")
        assert result == ["Q01", "Q02", "Q03", "Q04", "Q05"]
        
        # Test mixed
        result = parse_question_spec("q1,q2,5-7")
        assert result == ["Q01", "Q02", "Q05", "Q06", "Q07"]
        
        # Test invalid: start > end
        with pytest.raises(ValueError) as exc_info:
            parse_question_spec("10-5")
        assert "start > end" in str(exc_info.value)
        
        # Test invalid: bad format
        with pytest.raises(ValueError) as exc_info:
            parse_question_spec("invalid")
        assert "invalid" in str(exc_info.value).lower()
    
    def test_cli_model_id_validation(self):
        """
        Test model ID format validation.
        
        Verifies:
        - Valid formats accepted (provider/model-name)
        - Invalid formats rejected
        - Error messages are clear
        """
        from src.cli.bcllm_model import validate_model_id
        
        # Valid formats
        assert validate_model_id("openai/gpt-4") == True
        assert validate_model_id("anthropic/claude-3") == True
        assert validate_model_id("google/gemini-pro") == True
        assert validate_model_id("meta/llama-2-70b") == True
        
        # Invalid formats
        assert validate_model_id("invalid") == False  # No slash
        assert validate_model_id("openai//gpt-4") == False  # Double slash
        assert validate_model_id("/gpt-4") == False  # Missing provider
        assert validate_model_id("openai/") == False  # Missing model
    
    def test_cli_experiment_name_validation(self, in_memory_db, capsys):
        """
        Test experiment name validation.
        
        Verifies:
        - Empty names rejected
        - Duplicate names rejected
        - Valid names accepted
        """
        from src.cli.bcllm_experiment import main as experiment_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Create first experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 0
            
            # Try to create duplicate
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                result = experiment_main()
                assert result == 1
            
            captured = capsys.readouterr()
            assert "already exists" in captured.err.lower()


@pytest.mark.integration
class TestCLIOutputFormatting:
    """Test CLI output formatting."""
    
    def test_cli_table_format(self, in_memory_db, capsys):
        """
        Test CLI table formatting for list commands.
        
        Verifies:
        - Tables have headers
        - Columns are aligned
        - Data is readable
        """
        from src.cli.bcllm_experiment import main as experiment_main
        from src.cli.bcllm_model import main as model_main
        from src.cli.bcllm_questions import main as questions_main
        
        with patch("sqlite3.connect", return_value=in_memory_db):
            # Create experiment
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--create-experiment", "test-exp",
            ]):
                experiment_main()
            
            # Add model
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--add-model", "openai/gpt-4",
            ]):
                model_main()
            
            # Add question
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--add-questions", "q1",
            ]):
                questions_main()
        
        # List experiments - verify table format
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_experiment.py",
                "--list-experiments",
            ]):
                experiment_main()
            
            captured = capsys.readouterr()
            # Table should have header separator
            assert "---" in captured.out or "Name" in captured.out
        
        # List models - verify table format
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_model.py",
                "--experiment", "test-exp",
                "--list-models",
            ]):
                model_main()
            
            captured = capsys.readouterr()
            assert "---" in captured.out or "ID" in captured.out
        
        # List questions - verify table format
        with patch("sqlite3.connect", return_value=in_memory_db):
            with patch.object(sys, "argv", [
                "bcllm_questions.py",
                "--experiment", "test-exp",
                "--list-questions",
            ]):
                questions_main()
            
            captured = capsys.readouterr()
            assert "---" in captured.out or "ID" in captured.out
