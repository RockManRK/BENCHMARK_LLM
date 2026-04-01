"""Unit tests for null normalization in argv_utils.

Tests the normalize_nulls() function for case-insensitive 'null' → EXPLICIT_NULL conversion
while preserving 'none' as a literal string.

The normalization rules are:
1. 'null' (case-insensitive) → EXPLICIT_NULL for nullable arguments
2. 'none' (any case) → preserved as literal string
3. Only arguments with default=None and required=False are normalized
4. Non-string values (int, bool, None) are not normalized

Note: The normalization layer converts 'null' to EXPLICIT_NULL sentinel.
Downstream code (e.g., config_resolver) then handles EXPLICIT_NULL by
converting to Python None for actual usage. This two-step process ensures
explicit null semantics are preserved through the configuration chain.
"""

import argparse
import pytest
from src.core.argv_utils import normalize_nulls, _is_nullable_arg, parse_args_normalized
from src.core.null_semantics import EXPLICIT_NULL


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def nullable_parser() -> argparse.ArgumentParser:
    """Create parser with nullable arguments (default=None, required=False).

    Returns:
        ArgumentParser with nullable string arguments for testing.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=str, default=None, required=False)
    parser.add_argument("--vision", type=str, default=None, required=False)
    parser.add_argument("--structured", type=str, default=None, required=False)
    parser.add_argument("--url", type=str, default=None, required=False)
    return parser


@pytest.fixture
def non_nullable_parser() -> argparse.ArgumentParser:
    """Create parser with non-nullable arguments.

    Returns:
        ArgumentParser with arguments that should NOT be normalized.
    """
    parser = argparse.ArgumentParser()
    # Has default value (not None)
    parser.add_argument("--output", type=str, default="console", required=False)
    # Required argument
    parser.add_argument("--name", type=str, required=True)
    # Integer argument
    parser.add_argument("--count", type=int, default=0)
    return parser


@pytest.fixture
def mixed_parser() -> argparse.ArgumentParser:
    """Create parser with both nullable and non-nullable arguments.

    Returns:
        ArgumentParser with mixed argument types.
    """
    parser = argparse.ArgumentParser()
    # Nullable
    parser.add_argument("--seed", type=str, default=None, required=False)
    parser.add_argument("--vision", type=str, default=None, required=False)
    # Non-nullable (has default)
    parser.add_argument("--output", type=str, default="console", required=False)
    # Non-nullable (required)
    parser.add_argument("--experiment", type=str, required=True)
    return parser


# =============================================================================
# Part 1: 'null' → None (case-insensitive)
# =============================================================================

class TestNullNormalizationCaseInsensitive:
    """Test that 'null' is normalized to None regardless of case."""

    def test_lowercase_null_becomes_none(self, nullable_parser):
        """When value is 'null' (lowercase), it is normalized to None."""
        # Arrange
        args = argparse.Namespace(seed='null', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL

    def test_uppercase_null_becomes_explicit_null(self, nullable_parser):
        """When value is 'NULL' (uppercase), it is normalized to EXPLICIT_NULL."""
        # Arrange
        args = argparse.Namespace(seed='NULL', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL

    def test_titlecase_null_becomes_explicit_null(self, nullable_parser):
        """When value is 'Null' (title case), it is normalized to EXPLICIT_NULL."""
        # Arrange
        args = argparse.Namespace(seed='Null', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL

    def test_mixed_case_null_becomes_explicit_null(self, nullable_parser):
        """When value is 'nUlL' (mixed case), it is normalized to EXPLICIT_NULL."""
        # Arrange
        args = argparse.Namespace(seed='nUlL', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL

    def test_multiple_nullable_args_with_null(self, nullable_parser):
        """When multiple nullable args have 'null' values, all are normalized."""
        # Arrange
        args = argparse.Namespace(
            seed='null',
            vision='NULL',
            structured='Null',
            url='nUlL'
        )

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL
        assert result.vision is EXPLICIT_NULL
        assert result.structured is EXPLICIT_NULL
        assert result.url is EXPLICIT_NULL


# =============================================================================
# Part 2: 'none' preserved as literal
# =============================================================================

class TestNonePreservedAsLiteral:
    """Test that 'none' (any case) is preserved as a literal string."""

    def test_lowercase_none_preserved(self, nullable_parser):
        """When value is 'none' (lowercase), it is preserved as literal."""
        # Arrange
        args = argparse.Namespace(seed='none', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'none'

    def test_uppercase_none_preserved(self, nullable_parser):
        """When value is 'NONE' (uppercase), it is preserved as literal."""
        # Arrange
        args = argparse.Namespace(seed='NONE', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'NONE'

    def test_titlecase_none_preserved(self, nullable_parser):
        """When value is 'None' (title case), it is preserved as literal."""
        # Arrange
        args = argparse.Namespace(seed='None', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'None'

    def test_mixed_case_none_preserved(self, nullable_parser):
        """When value is 'NoNe' (mixed case), it is preserved as literal."""
        # Arrange
        args = argparse.Namespace(seed='NoNe', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'NoNe'


# =============================================================================
# Part 3: Only nullable arguments are normalized
# =============================================================================

class TestOnlyNullableArgumentsNormalized:
    """Test that only nullable arguments (default=None, required=False) are normalized."""

    def test_argument_with_default_value_not_normalized(self, non_nullable_parser):
        """When argument has default value (not None), 'null' is NOT normalized."""
        # Arrange
        args = argparse.Namespace(output='null', name='test', count=0)

        # Act
        result = normalize_nulls(args, non_nullable_parser)

        # Assert
        assert result.output == 'null'  # Preserved as literal

    def test_required_argument_not_normalized(self, non_nullable_parser):
        """When argument is required, 'null' is NOT normalized."""
        # Arrange
        args = argparse.Namespace(output='console', name='null', count=0)

        # Act
        result = normalize_nulls(args, non_nullable_parser)

        # Assert
        assert result.name == 'null'  # Preserved as literal

    def test_nullable_arg_in_mixed_parser_normalized(self, mixed_parser):
        """In mixed parser, only nullable args are normalized."""
        # Arrange
        args = argparse.Namespace(
            seed='null',           # Nullable → should normalize
            vision='null',         # Nullable → should normalize
            output='null',         # Has default → should NOT normalize
            experiment='test'      # Required → unchanged
        )

        # Act
        result = normalize_nulls(args, mixed_parser)

        # Assert
        assert result.seed is EXPLICIT_NULL      # Normalized
        assert result.vision is EXPLICIT_NULL    # Normalized
        assert result.output == 'null'  # NOT normalized (has default)
        assert result.experiment == 'test'

    def test_is_nullable_arg_with_default_none(self, nullable_parser):
        """_is_nullable_arg returns True for arguments with default=None."""
        # Arrange
        action = nullable_parser._actions[1]  # --seed

        # Act
        result = _is_nullable_arg(action)

        # Assert
        assert result is True

    def test_is_nullable_arg_with_default_value(self, non_nullable_parser):
        """_is_nullable_arg returns False for arguments with default value."""
        # Arrange
        action = non_nullable_parser._actions[1]  # --output

        # Act
        result = _is_nullable_arg(action)

        # Assert
        assert result is False

    def test_is_nullable_arg_required(self, non_nullable_parser):
        """_is_nullable_arg returns False for required arguments."""
        # Arrange
        action = non_nullable_parser._actions[2]  # --name

        # Act
        result = _is_nullable_arg(action)

        # Assert
        assert result is False


# =============================================================================
# Part 4: Non-string values are NOT normalized
# =============================================================================

class TestNonStringValuesNotNormalized:
    """Test that non-string values (int, bool, None) are not normalized."""

    def test_integer_value_unchanged(self, nullable_parser):
        """When value is integer, it is unchanged (not normalized)."""
        # Arrange
        args = argparse.Namespace(seed=42, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 42

    def test_zero_value_unchanged(self, nullable_parser):
        """When value is 0 (integer), it is unchanged."""
        # Arrange
        args = argparse.Namespace(seed=0, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 0

    def test_boolean_true_unchanged(self, nullable_parser):
        """When value is True (boolean), it is unchanged."""
        # Arrange
        args = argparse.Namespace(seed=True, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is True

    def test_boolean_false_unchanged(self, nullable_parser):
        """When value is False (boolean), it is unchanged."""
        # Arrange
        args = argparse.Namespace(seed=False, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is False

    def test_none_value_unchanged(self, nullable_parser):
        """When value is already None, it remains None."""
        # Arrange
        args = argparse.Namespace(seed=None, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is None

    def test_float_value_unchanged(self, nullable_parser):
        """When value is float, it is unchanged."""
        # Arrange
        args = argparse.Namespace(seed=3.14, vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 3.14


# =============================================================================
# Part 5: parse_args_normalized() integration
# =============================================================================

class TestParseArgsNormalized:
    """Test parse_args_normalized() wrapper function."""

    def test_parse_args_normalized_with_null(self, nullable_parser):
        """parse_args_normalized normalizes 'null' from command line."""
        # Arrange
        argv = ['--seed', 'null', '--vision', 'NULL']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is EXPLICIT_NULL
        assert result.vision is EXPLICIT_NULL

    def test_parse_args_normalized_with_none(self, nullable_parser):
        """parse_args_normalized preserves 'none' from command line."""
        # Arrange
        argv = ['--seed', 'none', '--vision', 'None']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed == 'none'
        assert result.vision == 'None'

    def test_parse_args_normalized_with_literal_value(self, nullable_parser):
        """parse_args_normalized preserves literal string values."""
        # Arrange
        argv = ['--seed', '42', '--vision', 'true']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed == '42'
        assert result.vision == 'true'

    def test_parse_args_normalized_mixed_values(self, nullable_parser):
        """parse_args_normalized handles mixed null/none/literal values."""
        # Arrange
        argv = ['--seed', 'null', '--vision', 'none', '--structured', 'custom']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is EXPLICIT_NULL  # 'null' → EXPLICIT_NULL
        assert result.vision == 'none'   # 'none' preserved
        assert result.structured == 'custom'  # literal preserved

    def test_parse_args_normalized_equals_sign(self, nullable_parser):
        """parse_args_normalized handles --flag=value syntax."""
        # Arrange
        argv = ['--seed=null', '--vision=NULL']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is EXPLICIT_NULL
        assert result.vision is EXPLICIT_NULL


# =============================================================================
# Part 6: Edge cases and boundary conditions
# =============================================================================

class TestNullNormalizationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_not_normalized(self, nullable_parser):
        """Empty string is not normalized (not equal to 'null')."""
        # Arrange
        args = argparse.Namespace(seed='', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ''

    def test_whitespace_string_not_normalized(self, nullable_parser):
        """String with whitespace is not normalized."""
        # Arrange
        args = argparse.Namespace(seed=' null ', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ' null '  # Not stripped, so not equal to 'null'

    def test_null_with_extra_characters_not_normalized(self, nullable_parser):
        """String 'null' with extra characters is not normalized."""
        # Arrange
        args = argparse.Namespace(seed='nullify', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'nullify'

    def test_unicode_null_not_normalized(self, nullable_parser):
        """Unicode lookalike of 'null' is not normalized."""
        # Arrange
        args = argparse.Namespace(seed='пυll', vision=None, structured=None, url=None)  # Unicode lookalike

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'пυll'

    def test_null_in_list_not_applicable(self, nullable_parser):
        """List values are not affected by normalization (not strings)."""
        # Arrange
        args = argparse.Namespace(seed=['null', 'null'], vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ['null', 'null']  # List is not a string

    def test_multiple_calls_are_idempotent(self, nullable_parser):
        """Calling normalize_nulls multiple times is idempotent."""
        # Arrange
        args = argparse.Namespace(seed='null', vision=None, structured=None, url=None)

        # Act
        result1 = normalize_nulls(args, nullable_parser)
        result2 = normalize_nulls(result1, nullable_parser)

        # Assert
        assert result1.seed is EXPLICIT_NULL
        assert result2.seed is EXPLICIT_NULL
        assert result1 is result2  # Same object returned

    def test_parser_with_no_actions(self):
        """normalize_nulls handles parser with no actions gracefully."""
        # Arrange
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(seed='null', vision='null')

        # Act
        result = normalize_nulls(args, parser)

        # Assert
        assert result.seed == 'null'  # Not normalized (no actions to inspect)
        assert result.vision == 'null'

    def test_dest_different_from_flag_name(self, nullable_parser):
        """Normalization works when dest differs from flag name."""
        # Arrange
        parser = argparse.ArgumentParser()
        parser.add_argument("--seed-value", dest="seed", type=str, default=None, required=False)
        args = argparse.Namespace(seed='null')

        # Act
        result = normalize_nulls(args, parser)

        # Assert
        assert result.seed is EXPLICIT_NULL
