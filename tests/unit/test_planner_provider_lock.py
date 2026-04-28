"""Unit tests for provider lock validation in Planner.

Tests the _validate_provider_lock method that ensures all model variants
have PROVIDER resolved when PROVIDER_LOCK is enabled in experiment config.

When PROVIDER_LOCK=True, the planner validates that every variant in the
experiment has a non-null PROVIDER in its config. This prevents execution
without locked providers.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.core.planner import Planner, PlannerValidationError


class TestProviderLockValidation:
    """Tests for _validate_provider_lock method."""

    def _create_variant_row(self, variant_id: str, model_id: str, config: dict) -> MagicMock:
        """Create a mock variant row with the given config.

        Args:
            variant_id: Unique variant ID
            model_id: Model identifier
            config: Variant configuration dict

        Returns:
            Mock sqlite3.Row with config serialized as JSON string
        """
        row = MagicMock()
        row.__getitem__ = lambda self, key: {
            "variant_id": variant_id,
            "model_id": model_id,
            "config": json.dumps(config),
        }.get(key)
        row.keys = lambda: ["variant_id", "model_id", "config"]
        return row

    def test_no_validation_when_lock_disabled(self, in_memory_db):
        """When PROVIDER_LOCK is False, no validation needed."""
        # Arrange: experiment with PROVIDER_LOCK=false
        exp_config = {"PROVIDER_LOCK": False}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        # Add a variant with null provider
        variant_config = {"MODEL_ID": "openai/gpt-4"}
        variant_row = self._create_variant_row(
            "var-001", "openai/gpt-4", variant_config
        )

        # Act & Assert: no exception raised
        planner = Planner(in_memory_db)
        # Should not raise
        planner._validate_provider_lock("exp-001", [variant_row])

    def test_no_validation_when_no_variants(self, in_memory_db):
        """When experiment has no variants, no validation needed."""
        # Arrange: PROVIDER_LOCK=true but no variants
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        # Act & Assert: no exception raised
        planner = Planner(in_memory_db)
        # Should not raise
        planner._validate_provider_lock("exp-001", [])

    def test_validation_passes_when_all_providers_resolved(self, in_memory_db):
        """When all variants have PROVIDER set, validation passes."""
        # Arrange: PROVIDER_LOCK=true, variants with providers
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {"PROVIDER": "deepinfra/turbo"}),
            self._create_variant_row("var-002", "anthropic/claude-3", {"PROVIDER": "togethercomputer/llama"}),
        ]

        # Act & Assert: no exception raised
        planner = Planner(in_memory_db)
        # Should not raise
        planner._validate_provider_lock("exp-001", variants)

    def test_validation_fails_when_unresolved_variants(self, in_memory_db):
        """When PROVIDER_LOCK=true and any variant has PROVIDER=null, fails."""
        # Arrange: PROVIDER_LOCK=true, one variant with null provider
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {"PROVIDER": "deepinfra/turbo"}),
            self._create_variant_row("var-002", "anthropic/claude-3", {}),  # PROVIDER is null
        ]

        # Act & Assert: raises PlannerValidationError
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError) as exc_info:
            planner._validate_provider_lock("exp-001", variants)

        assert "Provider lock is enabled" in str(exc_info.value)

    def test_validation_error_lists_unresolved_variants(self, in_memory_db):
        """Error message includes model_id and variant_id of unresolved variants."""
        # Arrange: PROVIDER_LOCK=true, multiple variants, one unresolved
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {"PROVIDER": "deepinfra/turbo"}),
            self._create_variant_row("var-002", "anthropic/claude-3", {}),  # PROVIDER is null
            self._create_variant_row("var-003", "meta-llama/llama-3", {"PROVIDER": "anyscale/llama"}),
        ]

        # Act & Assert: error message contains variant model_id
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError) as exc_info:
            planner._validate_provider_lock("exp-001", variants)

        error_msg = str(exc_info.value)
        assert "anthropic/claude-3" in error_msg

    def test_validation_error_mentions_resolve_command(self, in_memory_db):
        """Error message directs user to --resolve-providers command."""
        # Arrange: PROVIDER_LOCK=true, one variant with null provider
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {}),  # PROVIDER is null
        ]

        # Act & Assert: error message contains --resolve-providers
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError) as exc_info:
            planner._validate_provider_lock("exp-001", variants)

        error_msg = str(exc_info.value)
        assert "--resolve-providers" in error_msg or "resolve-providers" in error_msg

    def test_validation_skips_experiment_without_provider_lock_key(self, in_memory_db):
        """When PROVIDER_LOCK is not in config, behaves as if lock is disabled."""
        # Arrange: experiment config has no PROVIDER_LOCK key
        exp_config = {}  # No PROVIDER_LOCK key
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {}),  # PROVIDER is null
        ]

        # Act & Assert: no exception raised (defaults to False)
        planner = Planner(in_memory_db)
        # Should not raise
        planner._validate_provider_lock("exp-001", variants)

    def test_validation_fails_when_provider_explicitly_null(self, in_memory_db):
        """When PROVIDER is explicitly set to null in config, fails validation."""
        # Arrange: PROVIDER_LOCK=true, PROVIDER explicitly null
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {"PROVIDER": None}),  # Explicitly null
        ]

        # Act & Assert: raises PlannerValidationError
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError) as exc_info:
            planner._validate_provider_lock("exp-001", variants)

        assert "Provider lock is enabled" in str(exc_info.value)

    def test_validation_passes_with_empty_config(self, in_memory_db):
        """When variant has empty config, provider is considered unresolved."""
        # Arrange: PROVIDER_LOCK=true, variant with empty config
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {}),
        ]

        # Act & Assert: raises PlannerValidationError (empty config means PROVIDER is null)
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError):
            planner._validate_provider_lock("exp-001", variants)

    def test_validation_counts_multiple_unresolved_variants(self, in_memory_db):
        """Error message correctly counts multiple unresolved variants."""
        # Arrange: PROVIDER_LOCK=true, multiple variants with null providers
        exp_config = {"PROVIDER_LOCK": True}
        in_memory_db.execute(
            "INSERT INTO experiments (experiment_id, name, config_json, config_hash) VALUES (?, ?, ?, ?)",
            ("exp-001", "test-experiment", json.dumps(exp_config), "abc123"),
        )

        variants = [
            self._create_variant_row("var-001", "openai/gpt-4", {}),
            self._create_variant_row("var-002", "anthropic/claude-3", {}),
        ]

        # Act & Assert: raises with correct count
        planner = Planner(in_memory_db)
        with pytest.raises(PlannerValidationError) as exc_info:
            planner._validate_provider_lock("exp-001", variants)

        error_msg = str(exc_info.value)
        assert "2 model variant(s)" in error_msg or "2 variant" in error_msg.lower()
