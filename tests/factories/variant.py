"""Factory for creating ModelVariant instances in tests.

Builds the real `src.db.models.ModelVariant` entity — no duplicate/parallel
dataclass. `ModelVariant` only has `variant_id`, `experiment_id`,
`model_id`, `variant_signature`, `config`, `created_at`; there is no
top-level `reasoning_mode`/`vision_enabled`/`is_active`/etc. Convenience
kwargs are folded into `config` under the real config-hierarchy keys (see
`src/core/config_resolver.py::build_model_config_dict` and
`src/utils/variant_signature.py::SIGNATURE_FIELD_ORDER`).

`reasoning_mode` and `web_access_enabled` from the old duplicate dataclass
were dropped: neither maps to any key the system actually resolves or
persists today (no `MODEL_REASONING_MODE`/`WEB_ACCESS` key exists in
`config_resolver.py`) — they were never real, just unused factory
parameters. Web/internet-enabled runs are an unimplemented roadmap item
(docs/status/roadmap.md item 9), not current config surface.
"""

import json
import uuid
from typing import Any, Optional

from src.db.models import ModelVariant
from src.utils.variant_signature import generate_variant_signature


class VariantFactory:
    """Factory for creating ModelVariant instances in tests.

    Example:
        # Basic usage
        variant = VariantFactory.create(experiment_id="exp-123")

        # With overrides
        variant = VariantFactory.create(
            experiment_id="exp-123",
            model_id="openai/gpt-4",
            reasoning_effort="high",
        )

        # In a test
        def test_variant_creation(in_memory_db):
            variant = VariantFactory.create(experiment_id="exp-123")
            repo = VariantRepository(in_memory_db)
            repo.save(variant)
    """

    @staticmethod
    def create(
        experiment_id: str,
        model_id: str = "openai/gpt-4",
        variant_id: Optional[str] = None,
        variant_signature: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        reasoning_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        vision_enabled: Optional[bool] = None,
        structured_output: Optional[bool] = None,
        base_url: Optional[str] = None,
        provider: Optional[str] = None,
        config: Optional[str] = None,
    ) -> ModelVariant:
        """Create a ModelVariant with sensible defaults.

        Args:
            experiment_id: Parent experiment ID (required)
            model_id: Base model identifier (e.g., "openai/gpt-4")
            variant_id: Unique ID (auto-generated if None)
            variant_signature: Human-readable identity (auto-generated from
                model_id + config via the real signature generator if None)
            reasoning_effort: Folded into config["MODEL_REASONING_EFFORT"]
            max_output_tokens: Folded into config["MODEL_MAX_TOKENS_TOTAL"]
            reasoning_tokens: Folded into config["MODEL_MAX_TOKENS_REASONING"]
            temperature: Folded into config["MODEL_TEMPERATURE"]
            top_p: Folded into config["MODEL_TOP_P"]
            top_k: Folded into config["MODEL_TOP_K"]
            repeat_penalty: Folded into config["MODEL_REPEAT_PENALTY"]
            vision_enabled: Folded into config["MODEL_VISION"]
            structured_output: Folded into config["STRUCTURED_OUTPUTS"]
            base_url: Folded into config["BASE_URL"]
            provider: Folded into config["PROVIDER"]
            config: Full config JSON string — overrides all the individual
                config kwargs above when provided

        Returns:
            ModelVariant instance (src.db.models.ModelVariant)
        """
        if variant_id is None:
            variant_id = f"var-{uuid.uuid4().hex[:8]}"

        if config is None:
            config_dict: dict[str, Any] = {
                "MODEL_REASONING_EFFORT": reasoning_effort,
                "MODEL_MAX_TOKENS_TOTAL": max_output_tokens,
                "MODEL_MAX_TOKENS_REASONING": reasoning_tokens,
                "MODEL_TEMPERATURE": temperature,
                "MODEL_TOP_P": top_p,
                "MODEL_TOP_K": top_k,
                "MODEL_REPEAT_PENALTY": repeat_penalty,
                "MODEL_VISION": vision_enabled,
                "STRUCTURED_OUTPUTS": structured_output,
                "BASE_URL": base_url,
                "PROVIDER": provider,
            }
            config = json.dumps(config_dict)

        if variant_signature is None:
            variant_signature = generate_variant_signature(model_id, config)

        return ModelVariant(
            variant_id=variant_id,
            experiment_id=experiment_id,
            model_id=model_id,
            variant_signature=variant_signature,
            config=config,
        )
