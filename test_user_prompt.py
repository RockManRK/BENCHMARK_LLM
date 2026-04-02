"""Test script to validate user prompt construction.

This script validates that _build_user_prompt() correctly concatenates:
stem + options + user_prompt
"""

import sys
sys.path.insert(0, 'D:\\OneDrive\\Pessoais\\Projetos\\benchmark_llm')

from unittest.mock import Mock
from src.core.execution_engine import ExecutionEngine


def test_build_user_prompt_complete():
    """Test that user prompt includes stem, options, and user_prompt."""
    print("=" * 70)
    print("TEST: Build User Prompt - Complete Format")
    print("=" * 70)
    
    # Create mock dependencies
    mock_client = Mock()
    mock_randomizer = Mock()
    mock_parser = Mock()
    
    engine = ExecutionEngine(mock_client, mock_randomizer, mock_parser)
    
    # Test data
    stem = "Mulher de 58 anos, com diagnóstico de hipertensão arterial. O fármaco introduzido foi:"
    options = ["espironolactona.", "clortalidona.", "hidralazina.", "clonidina."]
    user_prompt = "Select the correct answer by providing only the letter (A, B, C, or D)."
    
    # Build prompt
    result = engine._build_user_prompt(stem, options, user_prompt)
    
    # Validate
    print("\nGenerated prompt:")
    print("-" * 70)
    print(result)
    print("-" * 70)
    print()
    
    assert stem in result, "Stem must be in the prompt"
    assert "A) espironolactona." in result, "Option A must be in the prompt"
    assert "B) clortalidona." in result, "Option B must be in the prompt"
    assert "C) hidralazina." in result, "Option C must be in the prompt"
    assert "D) clonidina." in result, "Option D must be in the prompt"
    assert user_prompt in result, "User prompt must be in the prompt"
    
    # Validate format: stem\n\noptions\n\nuser_prompt
    expected = f"{stem}\n\nA) espironolactona.\nB) clortalidona.\nC) hidralazina.\nD) clonidina.\n\n{user_prompt}"
    assert result == expected, f"Format mismatch:\nExpected:\n{expected}\n\nGot:\n{result}"
    
    print("✅ Stem included correctly")
    print("✅ Options formatted with letters (A, B, C, D)")
    print("✅ Options separated by newlines")
    print("✅ User prompt appended at the end")
    print("✅ All parts separated by double newlines (\\n\\n)")
    print()


def test_build_user_prompt_without_user_prompt():
    """Test that user prompt works without user_prompt_template."""
    print("=" * 70)
    print("TEST: Build User Prompt - Without User Prompt Template")
    print("=" * 70)
    
    # Create mock dependencies
    mock_client = Mock()
    mock_randomizer = Mock()
    mock_parser = Mock()
    
    engine = ExecutionEngine(mock_client, mock_randomizer, mock_parser)
    
    # Test data
    stem = "What is 2+2?"
    options = ["3", "4", "5", "6"]
    user_prompt = ""  # Empty user prompt
    
    # Build prompt
    result = engine._build_user_prompt(stem, options, user_prompt)
    
    # Validate
    print("\nGenerated prompt:")
    print("-" * 70)
    print(result)
    print("-" * 70)
    print()
    
    assert stem in result, "Stem must be in the prompt"
    assert "A) 3" in result, "Option A must be in the prompt"
    assert "B) 4" in result, "Option B must be in the prompt"
    assert user_prompt not in result or result.endswith(user_prompt), "Empty user prompt should not add extra content"
    
    # Should be just stem + options
    expected = f"{stem}\n\nA) 3\nB) 4\nC) 5\nD) 6"
    assert result == expected, f"Format mismatch:\nExpected:\n{expected}\n\nGot:\n{result}"
    
    print("✅ Works correctly without user prompt template")
    print("✅ Only stem and options are included")
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "VALIDATION: User Prompt Construction" + " " * 17 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        test_build_user_prompt_complete()
        test_build_user_prompt_without_user_prompt()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  - User prompt format: ✅ stem + options + user_prompt")
        print("  - Options formatting: ✅ A) opt1\\nB) opt2\\nC) opt3\\nD) opt4")
        print("  - Separator: ✅ Double newlines (\\n\\n) between parts")
        print("  - Without user_prompt: ✅ Works correctly")
        print()
        print("Expected API request format:")
        print('  "messages": [')
        print('    {')
        print('      "role": "user",')
        print('      "content": "Stem...\\n\\nA) opt1\\nB) opt2\\nC) opt3\\nD) opt4\\n\\nUser prompt..."')
        print('    }')
        print('  ]')
        print()
        
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
