"""Unit tests for null normalization in argv_utils.

Tests the normalize_nulls() function for case-insensitive 'system-default' → FORCE_SYSTEM_DEFAULT conversion
while preserving 'none' as a literal string and rejecting deprecated 'null'.

The normalization rules are:
1. 'system-default' (case-insensitive) → FORCE_SYSTEM_DEFAULT for nullable arguments
2. 'null' (case-insensitive) → raises ArgumentError with migration hint
3. 'none' (any case) → preserved as literal string
4. Only arguments with default=None and required=False are normalized
5. Non-string values (int, bool, None) are not normalized

Note: The normalization layer converts 'system-default' to FORCE_SYSTEM_DEFAULT sentinel.
Downstream code (e.g., config_resolver) then handles FORCE_SYSTEM_DEFAULT by
converting to Python None for actual usage. This two-step process ensures
explicit null semantics are preserved through the configuration chain.
"""

import argparse
import pytest
from src.core.argv_utils import normalize_nulls, _is_nullable_arg, parse_args_normalized
from src.core.null_semantics import FORCE_SYSTEM_DEFAULT


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
# Part 1: 'system-default' → FORCE_SYSTEM_DEFAULT (case-insensitive)
# =============================================================================

class TestSystemDefaultNormalizationCaseInsensitive:
    """Test that 'system-default' is normalized to FORCE_SYSTEM_DEFAULT regardless of case."""

    def test_lowercase_system_default_becomes_force_system_default(self, nullable_parser):
        """When value is 'system-default' (lowercase), it is normalized to FORCE_SYSTEM_DEFAULT."""
        # Arrange
        args = argparse.Namespace(seed='system-default', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT

    def test_uppercase_system_default_becomes_force_system_default(self, nullable_parser):
        """When value is 'SYSTEM-DEFAULT' (uppercase), it is normalized to FORCE_SYSTEM_DEFAULT."""
        # Arrange
        args = argparse.Namespace(seed='SYSTEM-DEFAULT', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT

    def test_titlecase_system_default_becomes_force_system_default(self, nullable_parser):
        """When value is 'System-Default' (title case), it is normalized to FORCE_SYSTEM_DEFAULT."""
        # Arrange
        args = argparse.Namespace(seed='System-Default', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT

    def test_mixed_case_system_default_becomes_force_system_default(self, nullable_parser):
        """When value is 'SyStEm-DeFaUlT' (mixed case), it is normalized to FORCE_SYSTEM_DEFAULT."""
        # Arrange
        args = argparse.Namespace(seed='SyStEm-DeFaUlT', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT

    def test_multiple_nullable_args_with_system_default(self, nullable_parser):
        """When multiple nullable args have 'system-default' values, all are normalized."""
        # Arrange
        args = argparse.Namespace(
            seed='system-default',
            vision='SYSTEM-DEFAULT',
            structured='System-Default',
            url='SyStEm-DeFaUlT'
        )

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT
        assert result.vision is FORCE_SYSTEM_DEFAULT
        assert result.structured is FORCE_SYSTEM_DEFAULT
        assert result.url is FORCE_SYSTEM_DEFAULT


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
        """When argument has default value (not None), 'system-default' is NOT normalized."""
        # Arrange
        args = argparse.Namespace(output='system-default', name='test', count=0)

        # Act
        result = normalize_nulls(args, non_nullable_parser)

        # Assert
        assert result.output == 'system-default'  # Preserved as literal (has default)

    def test_required_argument_not_normalized(self, non_nullable_parser):
        """When argument is required, 'system-default' is NOT normalized."""
        # Arrange
        args = argparse.Namespace(output='console', name='system-default', count=0)

        # Act
        result = normalize_nulls(args, non_nullable_parser)

        # Assert
        assert result.name == 'system-default'  # Preserved as literal (required)

    def test_nullable_arg_in_mixed_parser_normalized(self, mixed_parser):
        """In mixed parser, only nullable args are normalized."""
        # Arrange
        args = argparse.Namespace(
            seed='system-default',   # Nullable → should normalize
            vision='system-default', # Nullable → should normalize
            output='system-default', # Has default → should NOT normalize
            experiment='test'        # Required → unchanged
        )

        # Act
        result = normalize_nulls(args, mixed_parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT    # Normalized
        assert result.vision is FORCE_SYSTEM_DEFAULT  # Normalized
        assert result.output == 'system-default'      # NOT normalized (has default)
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

    def test_parse_args_normalized_with_system_default(self, nullable_parser):
        """parse_args_normalized normalizes 'system-default' from command line."""
        # Arrange
        argv = ['--seed', 'system-default', '--vision', 'SYSTEM-DEFAULT']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT
        assert result.vision is FORCE_SYSTEM_DEFAULT

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
        """parse_args_normalized handles mixed system-default/none/literal values."""
        # Arrange
        argv = ['--seed', 'system-default', '--vision', 'none', '--structured', 'custom']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT  # 'system-default' → FORCE_SYSTEM_DEFAULT
        assert result.vision == 'none'              # 'none' preserved
        assert result.structured == 'custom'        # literal preserved

    def test_parse_args_normalized_equals_sign(self, nullable_parser):
        """parse_args_normalized handles --flag=value syntax."""
        # Arrange
        argv = ['--seed=system-default', '--vision=SYSTEM-DEFAULT']

        # Act
        result = parse_args_normalized(nullable_parser, argv)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT
        assert result.vision is FORCE_SYSTEM_DEFAULT


# =============================================================================
# Part 6: Edge cases and boundary conditions
# =============================================================================

class TestNullNormalizationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_not_normalized(self, nullable_parser):
        """Empty string is not normalized (not equal to 'system-default')."""
        # Arrange
        args = argparse.Namespace(seed='', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ''

    def test_whitespace_string_not_normalized(self, nullable_parser):
        """String with whitespace is not normalized."""
        # Arrange
        args = argparse.Namespace(seed=' system-default ', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ' system-default '  # Not stripped, so not equal to 'system-default'

    def test_system_default_with_extra_characters_not_normalized(self, nullable_parser):
        """String 'system-default' with extra characters is not normalized."""
        # Arrange
        args = argparse.Namespace(seed='system-defaults', vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'system-defaults'

    def test_unicode_system_default_not_normalized(self, nullable_parser):
        """Unicode lookalike of 'system-default' is not normalized."""
        # Arrange
        args = argparse.Namespace(seed='ѕуѕтєм-δεƒαυℓт', vision=None, structured=None, url=None)  # Unicode lookalike

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == 'ѕуѕтєм-δεƒαυℓт'

    def test_system_default_in_list_not_applicable(self, nullable_parser):
        """List values are not affected by normalization (not strings)."""
        # Arrange
        args = argparse.Namespace(seed=['system-default', 'system-default'], vision=None, structured=None, url=None)

        # Act
        result = normalize_nulls(args, nullable_parser)

        # Assert
        assert result.seed == ['system-default', 'system-default']  # List is not a string

    def test_multiple_calls_are_idempotent(self, nullable_parser):
        """Calling normalize_nulls multiple times is idempotent."""
        # Arrange
        args = argparse.Namespace(seed='system-default', vision=None, structured=None, url=None)

        # Act
        result1 = normalize_nulls(args, nullable_parser)
        result2 = normalize_nulls(result1, nullable_parser)

        # Assert
        assert result1.seed is FORCE_SYSTEM_DEFAULT
        assert result2.seed is FORCE_SYSTEM_DEFAULT
        assert result1 is result2  # Same object returned

    def test_parser_with_no_actions(self):
        """normalize_nulls handles parser with no actions gracefully."""
        # Arrange
        parser = argparse.ArgumentParser()
        args = argparse.Namespace(seed='system-default', vision='system-default')

        # Act
        result = normalize_nulls(args, parser)

        # Assert
        assert result.seed == 'system-default'  # Not normalized (no actions to inspect)
        assert result.vision == 'system-default'

    def test_dest_different_from_flag_name(self, nullable_parser):
        """Normalization works when dest differs from flag name."""
        # Arrange
        parser = argparse.ArgumentParser()
        parser.add_argument("--seed-value", dest="seed", type=str, default=None, required=False)
        args = argparse.Namespace(seed='system-default')

        # Act
        result = normalize_nulls(args, parser)

        # Assert
        assert result.seed is FORCE_SYSTEM_DEFAULT


# =============================================================================
# Part 7: Deprecated 'null' rejection
# =============================================================================

class TestNullRejection:
    """Test that deprecated 'null' literal is rejected with migration hint."""

    def test_lowercase_null_raises_error(self, nullable_parser):
        """When value is 'null' (lowercase), ArgumentError is raised."""
        # Arrange
        args = argparse.Namespace(seed='null', vision=None, structured=None, url=None)

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_nulls(args, nullable_parser)

    def test_uppercase_null_raises_error(self, nullable_parser):
        """When value is 'NULL' (uppercase), ArgumentError is raised."""
        # Arrange
        args = argparse.Namespace(seed='NULL', vision=None, structured=None, url=None)

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_nulls(args, nullable_parser)

    def test_titlecase_null_raises_error(self, nullable_parser):
        """When value is 'Null' (title case), ArgumentError is raised."""
        # Arrange
        args = argparse.Namespace(seed='Null', vision=None, structured=None, url=None)

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_nulls(args, nullable_parser)

    def test_mixed_case_null_raises_error(self, nullable_parser):
        """When value is 'nUlL' (mixed case), ArgumentError is raised."""
        # Arrange
        args = argparse.Namespace(seed='nUlL', vision=None, structured=None, url=None)

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_nulls(args, nullable_parser)

    def test_multiple_null_values_all_rejected(self, nullable_parser):
        """When multiple nullable args have 'null' values, error is raised on first."""
        # Arrange
        args = argparse.Namespace(
            seed='null',
            vision='NULL',
            structured='Null',
            url='nUlL'
        )

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            normalize_nulls(args, nullable_parser)

    def test_null_in_parse_args_normalized(self, nullable_parser):
        """parse_args_normalized rejects 'null' from command line."""
        # Arrange
        argv = ['--seed', 'null']

        # Act & Assert
        with pytest.raises(argparse.ArgumentError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            parse_args_normalized(nullable_parser, argv)

    def test_nullable_int_rejects_null(self):
        """nullable_int() rejects 'null' with migration hint."""
        from src.core.null_semantics import nullable_int

        # Act & Assert
        with pytest.raises(argparse.ArgumentTypeError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            nullable_int('null')

    def test_nullable_float_rejects_null(self):
        """nullable_float() rejects 'null' with migration hint."""
        from src.core.null_semantics import nullable_float

        # Act & Assert
        with pytest.raises(argparse.ArgumentTypeError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            nullable_float('null')

    def test_nullable_str_rejects_null(self):
        """nullable_str() rejects 'null' with migration hint."""
        from src.core.null_semantics import nullable_str

        # Act & Assert
        with pytest.raises(argparse.ArgumentTypeError, match="The 'null' literal is deprecated. Use 'system-default' instead."):
            nullable_str('null')
