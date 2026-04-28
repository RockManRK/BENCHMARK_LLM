"""Unit tests for bcllm_provider CLI module.

Tests the --resolve-providers command that resolves PROVIDER for all
model variants in an experiment that have PROVIDER=null.

The command is idempotent - running multiple times is safe and will skip
already-resolved variants.
"""

import json
import pytest
import os
from unittest.mock import MagicMock, patch, call
from io import StringIO

from src.cli.bcllm_provider import handle_resolve_providers


class TestResolveProviders:
    """Tests for handle_resolve_providers."""

    def _create_mock_variant(self, variant_id: str, model_id: str, config: dict) -> MagicMock:
        """Create a mock ModelVariant with the given config.

        Args:
            variant_id: Unique variant ID
            model_id: Model identifier
            config: Configuration dict (will be serialized as JSON)

        Returns:
            Mock ModelVariant object
        """
        variant = MagicMock()
        variant.variant_id = variant_id
        variant.model_id = model_id
        variant.config = json.dumps(config) if config else "{}"
        return variant

    def test_resolves_unresolved_variants(self, in_memory_db):
        """Unresolved variants get their PROVIDER set."""
        # Arrange: mock variant with null provider
        mock_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})

        # Mock the repository methods
        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({"PROVIDER_SELECTION_STRATEGY": "first"})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [mock_variant]

            # Mock resolver to return a resolution
            mock_resolution = MagicMock()
            mock_resolution.provider_slug = "deepinfra/turbo"
            mock_resolution.strategy_applied = "first"
            mock_resolution.was_fallback = False
            mock_resolution.warning = None
            MockResolver.return_value.resolve.return_value = mock_resolution

            # Create args object
            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 0
            # Verify variant was saved with updated config
            MockVarRepo.return_value.save.assert_called_once()
            saved_variant = MockVarRepo.return_value.save.call_args[0][0]
            assert saved_variant.config is not None
            saved_config = json.loads(saved_variant.config)
            assert saved_config.get("PROVIDER") == "deepinfra/turbo"

    def test_skips_already_resolved_variants(self, in_memory_db):
        """Variants with PROVIDER already set are skipped."""
        # Arrange: variant with provider already set
        mock_variant = self._create_mock_variant(
            "var-001", "openai/gpt-4", {"PROVIDER": "deepinfra/turbo"}
        )

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [mock_variant]

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 0
            # Resolver should NOT have been called
            MockResolver.return_value.resolve.assert_not_called()
            # Save should NOT have been called (skipped)
            MockVarRepo.return_value.save.assert_not_called()

    def test_reports_resolved_count(self, in_memory_db):
        """Report shows correct resolved/skipped/failed counts."""
        # Arrange: two variants - one resolved, one already has provider
        resolved_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})
        skipped_variant = self._create_mock_variant(
            "var-002", "anthropic/claude-3", {"PROVIDER": "deepinfra/turbo"}
        )

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [
                resolved_variant, skipped_variant
            ]

            mock_resolution = MagicMock()
            mock_resolution.provider_slug = "togethercomputer/llama"
            mock_resolution.strategy_applied = "first"
            mock_resolution.was_fallback = False
            mock_resolution.warning = None
            MockResolver.return_value.resolve.return_value = mock_resolution

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 0
            output = mock_stdout.getvalue()
            assert "Resolved: 1" in output
            assert "Skipped:  1" in output  # Note: two spaces to match actual output
            assert "Failed:   0" in output  # Note: three spaces to match actual output

    def test_returns_error_when_experiment_not_found(self, in_memory_db):
        """Returns 1 when experiment doesn't exist."""
        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            # Setup mocks
            MockExpRepo.return_value.get_by_name.return_value = None

            args = MagicMock()
            args.experiment = "non-existent-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 1
            assert "Experiment not found" in mock_stderr.getvalue()

    def test_returns_error_when_api_key_missing(self, in_memory_db):
        """Returns 1 when OPENROUTER_API_KEY not set."""
        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch.dict(os.environ, {}, clear=True), \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            # Mock VariantRepository to return some variants
            with patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo:
                MockVarRepo.return_value.list_by_experiment.return_value = [
                    self._create_mock_variant("var-001", "openai/gpt-4", {})
                ]

                args = MagicMock()
                args.experiment = "test-experiment"
                args.resolve_providers = True

                # Act
                result = handle_resolve_providers(args, in_memory_db)

                # Assert
                assert result == 1
                assert "OPENROUTER_API_KEY not set" in mock_stderr.getvalue()

    def test_strategy_from_experiment_config(self, in_memory_db):
        """Uses PROVIDER_SELECTION_STRATEGY from experiment config."""
        # Arrange
        mock_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO):

            # Setup experiment with specific strategy
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({"PROVIDER_SELECTION_STRATEGY": "cheapest"})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [mock_variant]

            mock_resolution = MagicMock()
            mock_resolution.provider_slug = "togethercomputer/llama"
            mock_resolution.strategy_applied = "cheapest"
            mock_resolution.was_fallback = False
            mock_resolution.warning = None
            MockResolver.return_value.resolve.return_value = mock_resolution

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            handle_resolve_providers(args, in_memory_db)

            # Assert: resolver was called with correct strategy
            MockResolver.return_value.resolve.assert_called_once()
            call_args = MockResolver.return_value.resolve.call_args
            assert call_args[0][1] == "cheapest"  # Second positional arg is strategy

    def test_provider_lock_warning_when_not_enabled(self, in_memory_db):
        """Prints warning when PROVIDER_LOCK is not enabled."""
        mock_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            # Setup experiment WITHOUT PROVIDER_LOCK
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({
                "PROVIDER_SELECTION_STRATEGY": "first"
                # No PROVIDER_LOCK
            })
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [mock_variant]

            mock_resolution = MagicMock()
            mock_resolution.provider_slug = "deepinfra/turbo"
            mock_resolution.strategy_applied = "first"
            mock_resolution.was_fallback = False
            mock_resolution.warning = None
            MockResolver.return_value.resolve.return_value = mock_resolution

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 0  # Still succeeds
            stderr_output = mock_stderr.getvalue()
            assert "PROVIDER_LOCK is not enabled" in stderr_output

    def test_fallback_warning_printed_when_applicable(self, in_memory_db):
        """Warning is printed when resolution used fallback."""
        mock_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
             patch('sys.stderr', new_callable=StringIO) as mock_stderr:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [mock_variant]

            # Return a resolution with fallback
            mock_resolution = MagicMock()
            mock_resolution.provider_slug = "deepinfra/turbo"
            mock_resolution.strategy_applied = "first"
            mock_resolution.was_fallback = True
            mock_resolution.warning = "Falling back to first provider"
            MockResolver.return_value.resolve.return_value = mock_resolution

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            handle_resolve_providers(args, in_memory_db)

            # Assert
            stderr_output = mock_stderr.getvalue()
            assert "Falling back to first provider" in stderr_output

    def test_handles_resolution_failure(self, in_memory_db):
        """Failed resolutions are reported but don't stop processing."""
        # Arrange: one variant that will fail
        failing_variant = self._create_mock_variant("var-001", "openai/gpt-4", {})

        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('src.cli.bcllm_provider.ProviderResolver') as MockResolver, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = [failing_variant]

            # Make resolver raise an error
            MockResolver.return_value.resolve.side_effect = Exception("API error")

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert: command should report failure but not crash
            assert result == 1
            output = mock_stdout.getvalue()
            assert "Failed:   1" in output  # Note: three spaces to match actual output

    def test_no_variants_found_returns_zero(self, in_memory_db):
        """Returns 0 when experiment has no variants."""
        with patch('src.cli.bcllm_provider.ExperimentRepository') as MockExpRepo, \
             patch('src.cli.bcllm_provider.VariantRepository') as MockVarRepo, \
             patch('sys.stdout', new_callable=StringIO) as mock_stdout:

            # Setup mocks
            mock_exp = MagicMock()
            mock_exp.config_json = json.dumps({})
            MockExpRepo.return_value.get_by_name.return_value = mock_exp
            MockVarRepo.return_value.list_by_experiment.return_value = []  # No variants

            args = MagicMock()
            args.experiment = "test-experiment"
            args.resolve_providers = True

            # Act
            result = handle_resolve_providers(args, in_memory_db)

            # Assert
            assert result == 0
            output = mock_stdout.getvalue()
            assert "No model variants found" in output
