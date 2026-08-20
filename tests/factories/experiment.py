"""Factory for creating Experiment instances in tests.

Builds the real `src.db.models.Experiment` entity — no duplicate/parallel
dataclass. `Experiment` only has `experiment_id`, `name`, `description`,
`config_json`, `config_hash`, `created_at`; there is no top-level
`system_prompt`/`user_prompt`/`is_active`. Convenience kwargs
(`system_prompt`, `user_prompt`, `randomization_seed`) are folded into
`config_json` under the real config-hierarchy keys (`SYSTEM_PROMPT`,
`USER_PROMPT`, `RANDOMIZATION_SEED` — see
`src/core/config_resolver.py`) instead of being passed as fields the
entity does not have. This is the Randomization Seed only (controls
AnswerRandomizer) — unrelated to Model Seed (sent to the API for
inference, a model_variant-level concern, not implemented on this
factory).
"""

import json
import uuid
from typing import Any, Optional

from src.db.models import Experiment


class ExperimentFactory:
    """Factory for creating Experiment instances in tests.

    Example:
        # Basic usage
        experiment = ExperimentFactory.create(name="test-exp")

        # With overrides
        experiment = ExperimentFactory.create(
            name="custom-experiment",
            system_prompt="Custom system prompt",
        )

        # In a test
        def test_experiment_creation(in_memory_db):
            experiment = ExperimentFactory.create(name="test-exp")
            repo = ExperimentRepository(in_memory_db)
            repo.save(experiment)
    """

    @staticmethod
    def create(
        name: Optional[str] = None,
        system_prompt: Optional[str] = "You are a helpful assistant.",
        user_prompt: Optional[str] = "Answer the following question.",
        randomization_seed: Optional[int] = None,
        experiment_id: Optional[str] = None,
        description: Optional[str] = None,
        config_json: Optional[str] = None,
        config_hash: str = "",
        extra_config: Optional[dict[str, Any]] = None,
    ) -> Experiment:
        """Create an Experiment with sensible defaults.

        Args:
            name: Experiment name (auto-generated if not provided)
            system_prompt: Folded into config_json["SYSTEM_PROMPT"]
            user_prompt: Folded into config_json["USER_PROMPT"]
            randomization_seed: Folded into config_json["RANDOMIZATION_SEED"]
            experiment_id: Unique ID (auto-generated if not provided)
            description: Optional description
            config_json: Full config JSON string — overrides system_prompt/
                user_prompt/randomization_seed/extra_config entirely when provided
            config_hash: SHA-256 hash of protocol config
            extra_config: Additional config-hierarchy keys to merge in
                (e.g. {"PROVIDER_LOCK": True})

        Returns:
            Experiment instance (src.db.models.Experiment)
        """
        if name is None:
            name = f"test-experiment-{uuid.uuid4().hex[:8]}"

        if experiment_id is None:
            experiment_id = f"exp-{uuid.uuid4().hex[:8]}"

        if config_json is None:
            config: dict[str, Any] = {
                "SYSTEM_PROMPT": system_prompt,
                "USER_PROMPT": user_prompt,
                "RANDOMIZATION_SEED": randomization_seed,
            }
            if extra_config:
                config.update(extra_config)
            config_json = json.dumps(config)

        return Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            config_json=config_json,
            config_hash=config_hash,
        )
