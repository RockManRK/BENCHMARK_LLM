"""Test script to validate options normalization.

This script validates that _normalize_options() correctly converts
dict options to list format.
"""

import sys
sys.path.insert(0, 'D:\\OneDrive\\Pessoais\\Projetos\\benchmark_llm')

from src.cli.bcllm_experiment import _normalize_options


def test_normalize_options_from_dict():
    """Test that dict options are converted to list."""
    print("=" * 70)
    print("TEST: Normalize Options from Dict")
    print("=" * 70)
    
    # Test data (as it comes from dataset)
    options_dict = {
        "A": "espironolactona.",
        "B": "clortalidona.",
        "C": "hidralazina.",
        "D": "clonidina."
    }
    
    # Normalize
    result = _normalize_options(options_dict)
    
    # Validate
    print("\nInput (dict):")
    for key, value in options_dict.items():
        print(f"  {key}: {value}")
    print()
    
    print("Output (list):")
    for i, opt in enumerate(result):
        print(f"  {chr(65+i)}) {opt}")
    print()
    
    assert isinstance(result, list), f"Result should be list, got {type(result)}"
    assert len(result) == 4, f"Should have 4 options, got {len(result)}"
    assert result[0] == "espironolactona.", f"First option wrong: {result[0]}"
    assert result[1] == "clortalidona.", f"Second option wrong: {result[1]}"
    assert result[2] == "hidralazina.", f"Third option wrong: {result[2]}"
    assert result[3] == "clonidina.", f"Fourth option wrong: {result[3]}"
    
    print("✅ Dict converted to list correctly")
    print("✅ All option texts preserved")
    print("✅ Order maintained (A, B, C, D)")
    print()


def test_normalize_options_already_list():
    """Test that list options pass through unchanged."""
    print("=" * 70)
    print("TEST: Normalize Options Already List")
    print("=" * 70)
    
    # Test data (already normalized)
    options_list = [
        "espironolactona.",
        "clortalidona.",
        "hidralazina.",
        "clonidina."
    ]
    
    # Normalize (should pass through)
    result = _normalize_options(options_list)
    
    # Validate
    print("\nInput (list):")
    for i, opt in enumerate(options_list):
        print(f"  {chr(65+i)}) {opt}")
    print()
    
    print("Output (list):")
    for i, opt in enumerate(result):
        print(f"  {chr(65+i)}) {opt}")
    print()
    
    assert isinstance(result, list), f"Result should be list, got {type(result)}"
    assert result == options_list, "List should pass through unchanged"
    
    print("✅ List passed through unchanged")
    print()


def test_normalize_options_empty():
    """Test that empty options are handled."""
    print("=" * 70)
    print("TEST: Normalize Empty Options")
    print("=" * 70)
    
    # Test empty dict
    result_dict = _normalize_options({})
    assert result_dict == [], f"Empty dict should return empty list, got {result_dict}"
    
    # Test empty list
    result_list = _normalize_options([])
    assert result_list == [], f"Empty list should return empty list, got {result_list}"
    
    print("✅ Empty dict returns empty list")
    print("✅ Empty list returns empty list")
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "VALIDATION: Options Normalization" + " " * 20 + "║")
    print("╚" + "=" * 68 + "╝")
    print()
    
    try:
        test_normalize_options_from_dict()
        test_normalize_options_already_list()
        test_normalize_options_empty()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  - Dict to list conversion: ✅ Working")
        print("  - List pass-through: ✅ Working")
        print("  - Empty options: ✅ Handled")
        print()
        print("Expected behavior in execution:")
        print("  1. Dataset loads: {'A': 'opt1', 'B': 'opt2', ...}")
        print("  2. Snapshot creation: _normalize_options() → ['opt1', 'opt2', ...]")
        print("  3. Execution engine: list(options) → ['opt1', 'opt2', ...] ✅")
        print("  4. Prompt builds: 'A) opt1\\nB) opt2\\n...' ✅")
        print()
        
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
