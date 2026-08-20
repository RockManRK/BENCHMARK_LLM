"""Factory for creating Run instances in tests.

Builds the real `src.db.models.Run` entity — no duplicate/parallel
dataclass. `Run` only has `run_id`, `experiment_id`, `config`, `status`,
`duration`, `created_at`; there is no top-level `randomization_seed`/
`started_at`/`finished_at` (those either live inside `config` —
Randomization Seed, prompts — or don't exist at Run level at all in the
current schema; `started_at`/`finished_at` are Response-level fields, not
Run-level). Convenience kwargs (`randomization_seed`, `system_prompt`,
`user_prompt`) are folded into `config` under the real config-hierarchy
keys (`RANDOMIZATION_SEED`, `SYSTEM_PROMPT`, `USER_PROMPT` — see
`src/core/config_resolver.py::build_run_config_dict`). This is the
Randomization Seed only (controls AnswerRandomizer) — unrelated to Model
Seed (sent to the API for inference, a model_variant-level concern, not
implemented on this factory).
"""

import json
import uuid
from typing import Any, Literal, Optional

from src.db.models import Run


class RunFactory:
    """Factory for creating Run instances in tests.

    Example:
        # Basic usage - pending run
        run = RunFactory.create(experiment_id="exp-123")

        # Completed run with a Randomization Seed
        run = RunFactory.create(
            experiment_id="exp-123",
            randomization_seed=42,
            status="completed",
        )

        # In a test
        def test_run_creation(in_memory_db):
            run = RunFactory.create(experiment_id="exp-123")
            repo = RunRepository(in_memory_db)
            repo.save(run)
    """

    @staticmethod
    def create(
        experiment_id: str,
        randomization_seed: Optional[int] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        status: Literal['pending', 'completed', 'failed', 'partial_failed', 'removed'] = 'pending',
        duration: int = 0,
        run_id: Optional[str] = None,
        created_at: Optional[str] = None,
        config: Optional[str] = None,
    ) -> Run:
        """
        Create a Run with defaults.

        Args:
            experiment_id: Parent experiment ID (required)
            randomization_seed: Folded into config["RANDOMIZATION_SEED"]
                (None = no randomization; always explicitly present as a
                key, per the frozen-at-creation contract — never
                "missing")
            system_prompt: Folded into config["SYSTEM_PROMPT"]
            user_prompt: Folded into config["USER_PROMPT"]
            status: Run status (default: 'pending')
            duration: Accumulated execution time in milliseconds
            run_id: Unique ID (auto-generated if not provided)
            created_at: Creation timestamp
            config: Full config JSON string — overrides
                randomization_seed/system_prompt/user_prompt entirely
                when provided

        Returns:
            Run instance (src.db.models.Run)
        """
        if run_id is None:
            run_id = f"run-{uuid.uuid4().hex[:8]}"

        if config is None:
            config_dict: dict[str, Any] = {
                "RANDOMIZATION_SEED": randomization_seed,
                "SYSTEM_PROMPT": system_prompt,
                "USER_PROMPT": user_prompt,
            }
            config = json.dumps(config_dict)

        return Run(
            run_id=run_id,
            experiment_id=experiment_id,
            config=config,
            status=status,
            duration=duration,
            created_at=created_at,
        )
