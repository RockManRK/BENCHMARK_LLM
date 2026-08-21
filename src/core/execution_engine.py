"""ExecutionEngine module for TO-BE architecture.

This module provides the pure execution engine that executes ExecutionPlans.
The engine has NO database access - it is pure execution only.

Key Principles:
- No database access (pure execution)
- No configuration resolution (uses effective config as-is)
- No scope decisions (executes what's in the plan)
- Returns pure data only (ExecutionResult list)

The ExecutionEngine is initialized with:
- OpenRouterClient: For API calls
- AnswerRandomizer: For answer option randomization
- AnswerParser: For parsing LLM responses

IMPORTANT - Randomization Contract:
    Randomização de alternativas é uma decisão experimental explícita.

    - randomization_seed_effective = None significa randomização DESLIGADA (NÃO embaralhar)
    - randomization_seed_effective = int significa randomização LIGADA (embaralhar deterministicamente)
    - randomization_seed_effective NÃO é uma flag - é apenas parâmetro do RNG
    - A decisão de randomizar é feita EXCLUSIVAMENTE com:
        randomization_enabled = (randomization_seed_effective is not None)
    - NUNCA usar checagens truthy (if randomization_seed_effective)
    - randomization_seed_effective = 0 NÃO deve desligar randomização

    O que foi apresentado à LLM é a verdade experimental:
    - Opções são salvas EXATAMENTE como apresentadas
    - NUNCA "desrandomizar" respostas após a execução
    - NUNCA reescrever texto da LLM
    - Cada response carrega seu próprio contexto experimental
    - is_correct é calculado usando correct_option_presented (espaço apresentado)

    Estes dados são persistidos por resposta para garantir:
    - reprodutibilidade
    - auditoria
    - integridade científica

Example:
    >>> engine = ExecutionEngine(api_client, randomizer, parser)
    >>> results = engine.execute(plan)
    >>> for result in results:
    ...     print(f"Item {result.item_id}: {result.status}")
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Any, Literal, Optional

from src.api.message_builder import MessageBuilder
from src.api.request_payload import build_chat_completion_payload
from src.core.json_serializer import serialize_json
from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    ModelConfig,
    RetryPolicy,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser, ParsedAnswer
from src.core.retry import RetryHandler
from src.utils.logging_config import get_logger
from src.utils.log_emitter import emit_event
from src.utils.log_events import Event
import logging
from src.api.errors import APIError


@dataclass
class ExecutionResult:
    """Result of executing a single PlanItem.

    This dataclass contains the complete result of executing one item
    in an execution plan. It includes both success and failure cases.

    Attributes:
        item_id: Unique identifier for the executed item
        run_id: Parent run identifier
        variant_id: Model variant identifier (internal identity)
        snapshot_id: Question snapshot identifier
        question_id: Original question identifier
        status: Execution status ('success' or 'failure')
        response_text: Full LLM response text (None on failure)
        selected_answer: Parsed answer letter (None on failure)
        parse_confidence: Confidence level of parsed answer (None on failure)
        latency_ms: API call latency in milliseconds (None on failure)
        input_tokens: Number of input tokens (None on failure)
        response_tokens: Number of output tokens (None on failure)
        reasoning_tokens: Number of tokens used for reasoning (None on failure)
        cost: Cost of the API call in USD (None on failure)
        effective_tokens: Total tokens (input + response + reasoning) (None on failure)
        error_type: Type of error if failed (None on success)
        error_message: Error message if failed (None on success)
        attempt_count: Number of API call attempts made
        raw_response: Raw API response (dict for non-streaming, list for streaming) (None on failure)
        started_at: Execution start timestamp (None on failure)
        finished_at: Execution end timestamp (None on failure)
        finish_reason: API finish reason (None on failure)
        error_details: Model-level error details (None on success or execution failure)

        # Experimental context (randomization tracking)
        randomization_enabled: Whether answer options were randomized
        randomization_seed: Seed used for randomization (None if disabled)
        options_presented: Options exactly as presented to LLM (JSON)
        correct_option_presented: Correct answer letter in presented space
        option_letter_map: Mapping from presented letter to original letter

    Example:
        >>> result = ExecutionResult(
        ...     item_id="run-001::var-abc::snap-xyz::it-1",
        ...     run_id="run-001",
        ...     variant_id="var-abc",
        ...     snapshot_id="snap-xyz",
        ...     question_id="q1",
        ...     status="success",
        ...     response_text="The answer is (B).",
        ...     selected_answer="B",
        ...     parse_confidence="clear",
        ...     latency_ms=500,
        ...     input_tokens=50,
        ...     response_tokens=10,
        ...     reasoning_tokens=5,
        ...     cost=0.0001,
        ...     effective_tokens=65,
        ...     error_type=None,
        ...     error_message=None,
        ...     attempt_count=1,
        ...     randomization_enabled=False,
        ...     randomization_seed=None,
        ...     options_presented=["opt A", "opt B", "opt C", "opt D"],
        ...     correct_option_presented="A",
        ...     option_letter_map={"A": "A", "B": "B", "C": "C", "D": "D"},
        ... )
    """

    item_id: str
    run_id: str
    variant_id: str
    snapshot_id: str
    question_id: str
    status: Literal['success', 'failure']
    response_text: str | None
    selected_answer: str | None
    parse_confidence: str | None
    latency_ms: int | None
    input_tokens: int | None
    response_tokens: int | None
    error_type: str | None
    error_message: str | None
    attempt_count: int
    reasoning_tokens: int | None = None
    cost: float | None = None
    effective_tokens: int | None = None
    raw_response: list[dict] | dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    finish_reason: str | None = None
    error_details: str | None = None
    request_json: str | None = None
    raw_response_consolidated: str | None = None

    # Experimental context (randomization tracking)
    randomization_enabled: bool = False
    randomization_seed: int | None = None
    options_presented: list[str] | None = None
    correct_option_presented: str | None = None
    option_letter_map: dict[str, str] | None = None


class OpenRouterClient:
    """Type hint for OpenRouterClient.

    This is a placeholder for type hints. The actual implementation
    is in src.api.client.
    """

    debug_enabled: bool = False

    async def chat_completion(
        self,
        payload: dict[str, Any],
        base_url: str | None = None,
        operation_id: str | None = None,
    ) -> Any:
        """Call OpenRouter chat completion API."""
        ...


class ExecutionEngine:
    """Pure execution engine with no database access.

    The ExecutionEngine is responsible for executing all items in an
    ExecutionPlan. It:

    - Applies randomization (if seed is set)
    - Calls the API for each item
    - Parses the response
    - Returns ExecutionResult list

    The engine has NO database access. It receives a fully-resolved
    ExecutionPlan from the Planner and executes it as-is.

    Attributes:
        api_client: OpenRouter API client
        randomizer: Answer option randomizer
        parser: Response parser

    Example:
        >>> engine = ExecutionEngine(api_client, randomizer, parser)
        >>> results = engine.execute(plan)
    """

    def __init__(
        self,
        api_client: OpenRouterClient,
        randomizer: AnswerRandomizer,
        parser: AnswerParser,
        logger: Optional[Logger] = None,
        retry_handler: Optional[RetryHandler] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        """Initialize engine with dependencies.

        Args:
            api_client: OpenRouter API client
            randomizer: Answer option randomizer (seeded)
            parser: Response parser with confidence levels
            logger: Optional logger instance. If not provided, uses get_logger('core.execution_engine').
            retry_handler: Optional retry handler. If not provided, creates default with RetryPolicy().
            retry_policy: Optional default retry policy. Used only if retry_handler is not provided.
                         If neither is provided, uses RetryPolicy() with default values.

        Example:
            >>> engine = ExecutionEngine(api_client, randomizer, parser)
        """
        self.api_client = api_client
        self.randomizer = randomizer
        self.parser = parser
        self._logger = logger or get_logger('core.execution_engine')
        self._retry_handler = retry_handler or RetryHandler(
            policy=retry_policy if retry_policy is not None else RetryPolicy(),
            logger=self._logger
        )

    async def execute_async(
        self,
        plan: ExecutionPlan,
        result_queue: asyncio.Queue,
    ) -> list[ExecutionResult]:
        """Async execution entry point. Pushes each result to queue after completion.

        Args:
            plan: Immutable execution plan from Planner
            result_queue: Shared queue to push results to

        Returns:
            List of ExecutionResult (one per item)
        """
        all_results: list[ExecutionResult] = []

        # Extract context from plan for logging
        experiment_id = plan.experiment_id
        run_count = len(plan.runs)
        total_items = sum(len(run.items) for run in plan.runs)
        operation_id = plan.operation_id

        emit_event(
            self._logger, Event.EXECUTION_START, operation_id=operation_id,
            experiment_id=experiment_id, runs=run_count, total_items=total_items,
        )

        for run in plan.runs:
            run_results = await self._execute_run_async(run, result_queue, operation_id=operation_id)
            all_results.extend(run_results)

        # Calculate summary statistics
        succeeded = sum(1 for r in all_results if r.status == 'success')
        failed = sum(1 for r in all_results if r.status == 'failure')

        emit_event(
            self._logger, Event.EXECUTION_COMPLETE, operation_id=operation_id,
            experiment_id=experiment_id, total=total_items, succeeded=succeeded, failed=failed,
        )

        return all_results

    async def _execute_run_async(
        self,
        run: PlanRun,
        result_queue: asyncio.Queue,
        operation_id: str | None = None,
    ) -> list[ExecutionResult]:
        """Execute all items in a single run asynchronously.

        Args:
            run: Plan run to execute
            result_queue: Shared queue to push results to
            operation_id: Correlation ID for the CLI invocation, threaded
                down from the parent ExecutionPlan (logging only).

        Returns:
            List of ExecutionResult for this run
        """
        results: list[ExecutionResult] = []
        total_items = len(run.items)
        completed = 0

        # Create retry handler for this run using its retry policy
        run_retry_handler = RetryHandler(
            policy=run.retry_policy,
            logger=self._logger,
            operation_id=operation_id,
        )

        # Apply Randomization Seed if set
        # Contract: Generate option_letter_map ONCE per run for determinism.
        # All items in the same run share the exact same mapping.
        seed = run.randomization_seed_effective
        run_option_map: Optional[dict[str, str]] = None
        if seed is not None:
            assert isinstance(seed, int), (
                f"randomization_seed_effective must be int, got {type(seed).__name__}. "
                f"Seed normalization must happen in Planner._resolve_randomization_seed_effective()."
            )
            # Generate the option map once using the run seed
            # Use the first item's options as the reference for shuffling
            # (the shuffle order is the same regardless of content)
            self.randomizer.set_seed(seed)
            if run.items:
                ref_options = list(run.items[0].question_payload.options)
                randomized = self.randomizer.randomize_options(ref_options, seed=seed)
                shuffled = randomized["options"]
                # Build the map from the shuffle result
                run_option_map = {}
                for presented_idx, shuffled_option in enumerate(shuffled):
                    presented_letter = chr(65 + presented_idx)
                    original_idx = ref_options.index(shuffled_option)
                    original_letter = chr(65 + original_idx)
                    run_option_map[presented_letter] = original_letter

        # Calculate milestone interval (25%, 50%, 75%, 100%)
        milestone_interval = max(1, total_items // 4)

        for i, item in enumerate(run.items):
            result = await self._execute_item_async(
                item, run, run_retry_handler, result_queue,
                item_index=i, run_option_map=run_option_map,
                operation_id=operation_id,
            )
            results.append(result)
            completed = i + 1

            # Log progress milestones
            if completed % milestone_interval == 0 or completed == total_items:
                percent = int((completed / total_items) * 100)
                emit_event(
                    self._logger, Event.PROGRESS_MILESTONE, operation_id=operation_id,
                    run_id=run.run_id, completed=completed, total=total_items, percent=percent,
                )

        return results

    async def _execute_item_async(
        self,
        item: PlanItem,
        run: PlanRun,
        retry_handler: Optional[RetryHandler] = None,
        result_queue: Optional[asyncio.Queue] = None,
        item_index: Optional[int] = None,
        run_option_map: Optional[dict[str, str]] = None,
        operation_id: str | None = None,
    ) -> ExecutionResult:
        """Execute a single item asynchronously with retry policy.

        Args:
            item: Plan item to execute
            run: Parent run containing retry policy
            retry_handler: Optional retry handler. If not provided, uses self._retry_handler.
            result_queue: Optional shared queue to push result to after completion.
            item_index: Optional zero-based index of item within the run.
            run_option_map: Pre-computed option_letter_map for the entire run.
                           When provided, used for all items (ensures determinism).
                           When None, falls back to per-item generation (legacy).

        Returns:
            ExecutionResult for this item
        """
        attempt_count = 0
        last_error_type: str | None = None
        last_error_message: str | None = None

        # Use provided retry handler or fall back to instance default
        effective_retry_handler = retry_handler if retry_handler is not None else self._retry_handler

        # Capture start timestamp
        started_at = datetime.now()

        emit_event(
            self._logger, Event.ITEM_START, operation_id=operation_id,
            run_id=item.run_id, variant_id=item.variant_id, snapshot_id=item.snapshot_id,
        )

        # Get the variant for this item
        variant = self._get_variant_for_item(run, item.variant_id)
        if variant is None:
            error_msg = f"Variant {item.variant_id} not found in run"
            # Capture finish timestamp for config error
            finished_at = datetime.now()
            emit_event(
                self._logger, Event.ITEM_FAILED, level=logging.ERROR, operation_id=operation_id,
                run_id=item.run_id, variant_id=item.variant_id, snapshot_id=item.snapshot_id,
                error_type="config_error", error=error_msg,
            )
            result = ExecutionResult(
                item_id=item.item_id,
                run_id=item.run_id,
                variant_id=item.variant_id,
                snapshot_id=item.snapshot_id,
                question_id=item.question_id,
                status="failure",
                response_text=None,
                selected_answer=None,
                parse_confidence=None,
                latency_ms=None,
                input_tokens=None,
                response_tokens=None,
                error_type="config_error",
                error_message=error_msg,
                attempt_count=0,
                raw_response=None,
                started_at=started_at,
                finished_at=finished_at,
                finish_reason=None,
            )

            # Push result to shared queue (non-blocking: queue has unlimited size)
            if result_queue is not None:
                await result_queue.put(result)

            return result

        # Retry wrapper for API call
        # Mutable container to capture request_json even on exception
        execution_context: dict[str, Any] = {"request_json": None}
        
        async def api_call_with_retry() -> dict:
            """Inner function for RetryHandler to execute."""
            nonlocal attempt_count

            """
            Randomização de alternativas é uma decisão experimental explícita.

            Seed = None significa randomização DESLIGADA.
            Seed não é flag, apenas parâmetro do RNG.

            O que foi apresentado à LLM é a verdade experimental e deve ser
            preservado exatamente como ocorreu, sem desrandomização posterior.
            """

            # Determine if randomization is enabled (explicit check, not truthy)
            randomization_enabled = run.randomization_seed_effective is not None

            # Start with original options
            original_options = list(item.question_payload.options)
            options = original_options
            option_letter_map = {chr(65 + i): chr(65 + i) for i in range(len(original_options))}

            # Apply randomization ONLY if seed is explicitly set (not None)
            if randomization_enabled:
                # Use the pre-computed run-level option map if provided.
                # This ensures all items in the same run share the SAME mapping,
                # regardless of execution order or concurrency.
                if run_option_map is not None:
                    option_letter_map = run_option_map
                    # Apply the same shuffle to this item's options
                    # We need to reorder original_options to match the run's shuffled order
                    run_shuffled_order = [None] * len(original_options)
                    for presented_letter, original_letter in run_option_map.items():
                        presented_idx = ord(presented_letter) - 65
                        original_idx = ord(original_letter) - 65
                        if 0 <= original_idx < len(original_options):
                            run_shuffled_order[presented_idx] = original_options[original_idx]
                    options = [o for o in run_shuffled_order if o is not None]
                else:
                    # Fallback: per-item randomization (legacy path, should not be reached
                    # in normal operation after Issue 1 fix)
                    randomized = self.randomizer.randomize_options(
                        original_options,
                        seed=run.randomization_seed_effective,
                    )
                    options = randomized["options"]
                    option_letter_map = {}
                    for presented_idx, shuffled_option in enumerate(options):
                        presented_letter = chr(65 + presented_idx)
                        original_idx = original_options.index(shuffled_option)
                        original_letter = chr(65 + original_idx)
                        option_letter_map[presented_letter] = original_letter

            # Determine correct answer in the presented space
            # If options were shuffled, the correct answer letter changes
            """
            Contrato Experimental - Avaliação por Letras:

            Este sistema trabalha EXCLUSIVAMENTE com letras (A/B/C/D), nunca com texto.

            - answer_key é uma LETRA original: "A", "B", "C", ou "D"
            - selected_answer é uma LETRA respondida pela LLM: "A", "B", "C", ou "D"
            - correct_option_presented é uma LETRA no espaço apresentado
            - is_correct é calculado APENAS por: selected_answer == correct_option_presented

            O TEXTO das opções é apenas para apresentação visual.
            NUNCA usar options.index(text) para lógica de correção.

            Isso é um contrato experimental, não uma heurística.
            """

            answer_key_letter = item.question_payload.answer_key  # "A", "B", "C", or "D"

            if randomization_enabled:
                # Convert answer_key letter to original index
                # e.g., "A" -> 0, "B" -> 1, "C" -> 2, "D" -> 3
                original_letter = answer_key_letter.upper()
                original_idx = ord(original_letter) - ord("A")

                # The option at this original position moved to a new position after shuffling
                # Find where the original option ended up
                original_option_text = original_options[original_idx]
                presented_idx = options.index(original_option_text)
                correct_option_presented = chr(ord("A") + presented_idx)
            else:
                # No randomization: correct answer letter stays the same
                correct_option_presented = answer_key_letter.upper()

            # Build user message (text-only or multimodal based on vision config)
            user_message = self._build_user_message_for_item(
                item=item,
                options=options,
                user_prompt_template=run.prompts_effective.user,
                model_config=variant.model_config_effective,
                operation_id=operation_id,
            )

            # Build messages - filter out None content (system-default means "do not send")
            messages = []
            if run.prompts_effective.system is not None:
                messages.append({"role": "system", "content": run.prompts_effective.system})
            if user_message is not None:
                messages.append(user_message)

            # Get model config
            model_config = variant.model_config_effective

            # Build response_format if structured_output is enabled
            response_format: dict[str, Any] | None = None
            if model_config.structured_output:
                response_format = {"type": "json_object"}

            # --- Provider Locking ---
            # When resolved_provider is set, include provider.only and allow_fallbacks=false
            # This ensures the same provider is used for every request in this variant.
            provider_slug = variant.resolved_provider  # From PlanVariant
            provider_config: dict[str, Any] | None = None
            if provider_slug is not None:
                provider_config = {
                    "only": [provider_slug],
                    "allow_fallbacks": False
                }
                emit_event(
                    self._logger, Event.PROVIDER_LOCKED, operation_id=operation_id,
                    run_id=item.run_id, variant_id=item.variant_id, provider=provider_slug,
                )

            # Requested provider (NORMAL-tier: "provider solicitado" — the
            # effective/actually-used provider, when the response reports
            # one, is logged separately as PROVIDER_EFFECTIVE below, after
            # the API call completes).
            emit_event(
                self._logger, Event.PROVIDER_REQUESTED, operation_id=operation_id,
                run_id=item.run_id, variant_id=item.variant_id, provider=provider_slug,
            )

            if model_config.reasoning_effort is not None and model_config.max_reasoning_tokens is not None:
                emit_event(
                    self._logger, Event.REASONING_CONFLICT, level=logging.WARNING,
                    operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                    snapshot_id=item.snapshot_id, reasoning_effort=model_config.reasoning_effort,
                    max_reasoning_tokens=model_config.max_reasoning_tokens,
                )

            # Build the ONE canonical request payload. This same object is
            # used, unmodified, both to derive request_json (audit) below
            # and as the literal body handed to the API client — there is
            # no second construction to drift from this one. See
            # docs/status/model-seed-checkpoint-b-design.md, Part 1.
            #
            # debug_enabled is read from the client's own constructed
            # setting (single source of truth — never duplicated here).
            # `is True` (not a plain truthy check) so an unconfigured test
            # double (e.g. a MagicMock without debug_enabled explicitly
            # set) never accidentally enables debug.
            debug_enabled = getattr(self.api_client, "debug_enabled", False) is True

            payload = build_chat_completion_payload(
                model_id=variant.model_id,
                messages=messages,
                temperature=model_config.temperature,
                top_p=model_config.top_p,
                top_k=model_config.top_k,
                repeat_penalty=model_config.repeat_penalty,
                max_tokens=model_config.max_output_tokens,
                reasoning_effort=model_config.reasoning_effort,
                max_reasoning_tokens=model_config.max_reasoning_tokens,
                response_format=response_format,
                provider=provider_config,
                model_seed=model_config.model_seed,
                debug_enabled=debug_enabled,
            )

            # Capture request_json from the SAME payload object that will
            # be sent — fields serialized in insertion order for readability.
            request_json = serialize_json(payload, pretty=True)

            # Store in context for exception handling
            execution_context["request_json"] = request_json

            # TRACE-only: the canonical payload itself, redacted (emit_event
            # applies redaction unconditionally — never the raw object).
            # Same object request_json was derived from — never a second
            # construction (docs/status/model-seed-checkpoint-b-design.md, Part 1).
            emit_event(
                self._logger, Event.REQUEST_PAYLOAD_TRACE, level=logging.DEBUG,
                operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                payload=payload,
            )

            # Call API (this is what RetryHandler will retry). The payload
            # is passed through unmodified — OpenRouterClient never
            # reconstructs it.
            response = await self.api_client.chat_completion(
                payload=payload,
                base_url=model_config.base_url,
                operation_id=operation_id,
            )

            # Extract response data
            response_text = self._extract_response_content(response)
            latency_ms = self._extract_latency(response)
            input_tokens = response.input_tokens if hasattr(response, 'input_tokens') else None
            response_tokens = response.response_tokens if hasattr(response, 'response_tokens') else None
            reasoning_tokens = response.reasoning_tokens if hasattr(response, 'reasoning_tokens') else None
            cost = response.cost if hasattr(response, 'cost') else None
            finish_reason = self._extract_finish_reason(response)
            raw_response = response.raw_response if hasattr(response, 'raw_response') else None

            # Effective provider — as reported back by OpenRouter in the
            # response itself, distinct from the requested one logged as
            # PROVIDER_REQUESTED above (they can differ when no provider
            # was pinned, or in principle even when one was). Only emitted
            # when the response actually carries it ("quando disponível").
            effective_provider = self._extract_effective_provider(raw_response)
            if effective_provider is not None:
                emit_event(
                    self._logger, Event.PROVIDER_EFFECTIVE, operation_id=operation_id,
                    run_id=item.run_id, variant_id=item.variant_id, provider=effective_provider,
                )

            # TRACE-only: response-side evidence, kept structurally distinct
            # from REQUEST_PAYLOAD_TRACE above (never merged into it — see
            # docs/status/checkpoint-c-logging-observability-design.md, §7
            # and docs/contracts/data-auditability.md §4b). The upstream
            # echo (when debug was on) and every raw SSE chunk, redacted.
            if isinstance(raw_response, list):
                upstream_echo = None
                for chunk in raw_response:
                    if isinstance(chunk, dict) and "debug" in chunk:
                        upstream_echo = chunk["debug"]
                        break
                if upstream_echo is not None:
                    emit_event(
                        self._logger, Event.UPSTREAM_ECHO_TRACE, level=logging.DEBUG,
                        operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                        echo=upstream_echo,
                    )
                for chunk_index, chunk in enumerate(raw_response):
                    emit_event(
                        self._logger, Event.STREAM_CHUNK_TRACE, level=logging.DEBUG,
                        operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                        chunk_index=chunk_index, chunk=chunk,
                    )

            # Consolidated version for human-readable debug (separate from raw)
            raw_response_consolidated: str | None = None
            if raw_response and isinstance(raw_response, list):
                try:
                    from src.api.stream_aggregator import (
                        AggregatedResponse,
                        consolidate_streaming_response,
                    )
                    agg = AggregatedResponse(
                        content="",
                        finish_reason=None,
                        usage={},
                        debug_info=None,
                        raw_response=raw_response,
                    )
                    consolidated_dict = consolidate_streaming_response(agg)
                    raw_response_consolidated = serialize_json(consolidated_dict, pretty=True)
                except Exception:
                    # Consolidation is debug-only — never break execution
                    pass

            # Calculate effective tokens (input + response + reasoning)
            effective_tokens = None
            if input_tokens is not None and response_tokens is not None:
                effective_tokens = input_tokens + response_tokens + (reasoning_tokens or 0)

            # Check for model-level error (HTTP 200 with finish_reason: 'error')
            error_details: str | None = None
            if finish_reason == 'error':
                # Model encountered an error during generation
                # This is a successful execution with model error, not an execution failure
                error_details = self._extract_error_details(response)

                emit_event(
                    self._logger, Event.MODEL_ERROR, level=logging.WARNING,
                    operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                    snapshot_id=item.snapshot_id, error=error_details,
                )

            # Check for no-content scenario (OpenRouter warm-up/scaling)
            if not response_text or response_text.strip() == '':
                emit_event(
                    self._logger, Event.NO_CONTENT, level=logging.WARNING,
                    operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                    snapshot_id=item.snapshot_id,
                )
                # Still return success with empty content - not an error

            # Parse the answer
            parsed = self.parser.parse(response_text)

            # Update attempt count (RetryHandler tracks this, but we set it here for success case)
            attempt_count = 1

            return {
                "response": response,
                "response_text": response_text,
                "parsed": parsed,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "response_tokens": response_tokens,
                "reasoning_tokens": reasoning_tokens,
                "cost": cost,
                "effective_tokens": effective_tokens,
                "finish_reason": finish_reason,
                "raw_response": raw_response,
                "raw_response_consolidated": raw_response_consolidated,
                "error_details": error_details,
                "request_json": request_json,
                # Experimental context
                "randomization_enabled": randomization_enabled,
                "randomization_seed": run.randomization_seed_effective,
                "options_presented": options,
                "correct_option_presented": correct_option_presented,
                "option_letter_map": option_letter_map,
            }

        try:
            # Execute with retry policy
            result_data = await effective_retry_handler.execute_with_retry(
                api_call_with_retry,
                context=f"run={item.run_id}|variant={item.variant_id}|snapshot={item.snapshot_id}",
            )

            # Extract data
            response = result_data["response"]
            response_text = result_data["response_text"]
            parsed = result_data["parsed"]
            latency_ms = result_data["latency_ms"]
            input_tokens = result_data["input_tokens"]
            response_tokens = result_data["response_tokens"]
            reasoning_tokens = result_data.get("reasoning_tokens")
            cost = result_data.get("cost")
            effective_tokens = result_data.get("effective_tokens")
            finish_reason = result_data["finish_reason"]
            raw_response = result_data["raw_response"]
            raw_response_consolidated = result_data.get("raw_response_consolidated")
            error_details = result_data.get("error_details")
            request_json = result_data.get("request_json")

            # Extract experimental context
            randomization_enabled = result_data.get("randomization_enabled", False)
            randomization_seed = result_data.get("randomization_seed")
            options_presented = result_data.get("options_presented")
            correct_option_presented = result_data.get("correct_option_presented")
            option_letter_map = result_data.get("option_letter_map")

            # Capture finish timestamp
            finished_at = datetime.now()

            # Calculate total tokens for logging
            total_tokens = (input_tokens or 0) + (response_tokens or 0) + (reasoning_tokens or 0)

            emit_event(
                self._logger, Event.PARSE_DECISION, level=logging.DEBUG,
                operation_id=operation_id, run_id=item.run_id, variant_id=item.variant_id,
                snapshot_id=item.snapshot_id, selected_answer=parsed.answer,
                parse_confidence=parsed.confidence,
            )

            emit_event(
                self._logger, Event.RANDOMIZATION_APPLIED, level=logging.DEBUG,
                operation_id=operation_id, run_id=item.run_id, snapshot_id=item.snapshot_id,
                randomization_enabled=randomization_enabled, randomization_seed=randomization_seed,
            )

            emit_event(
                self._logger, Event.ITEM_COMPLETE, operation_id=operation_id,
                run_id=item.run_id, variant_id=item.variant_id, snapshot_id=item.snapshot_id,
                duration_ms=latency_ms, tokens=total_tokens, cost=cost, outcome="success",
            )

            result = ExecutionResult(
                item_id=item.item_id,
                run_id=item.run_id,
                variant_id=item.variant_id,
                snapshot_id=item.snapshot_id,
                question_id=item.question_id,
                status="success",
                response_text=response_text,
                selected_answer=parsed.answer,
                parse_confidence=parsed.confidence,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                response_tokens=response_tokens,
                reasoning_tokens=reasoning_tokens,
                cost=cost,
                effective_tokens=effective_tokens,
                error_type=None,
                error_message=None,
                attempt_count=attempt_count,
                raw_response=raw_response,
                raw_response_consolidated=raw_response_consolidated,
                started_at=started_at,
                finished_at=finished_at,
                finish_reason=finish_reason,
                error_details=error_details,
                request_json=request_json,
                # Experimental context
                randomization_enabled=randomization_enabled,
                randomization_seed=randomization_seed,
                options_presented=options_presented,
                correct_option_presented=correct_option_presented,
                option_letter_map=option_letter_map,
            )

            # Push result to shared queue (non-blocking: queue has unlimited size)
            if result_queue is not None:
                await result_queue.put(result)

            return result

        except Exception as e:
            # Retry exhausted or non-retryable error
            last_error_type = self._classify_error(e)
            last_error_message = str(e)
            attempt_count = getattr(e, '_retry_attempts', 1)

            # Capture finish timestamp
            finished_at = datetime.now()

            emit_event(
                self._logger, Event.ITEM_FAILED, level=logging.ERROR, operation_id=operation_id,
                run_id=item.run_id, variant_id=item.variant_id, snapshot_id=item.snapshot_id,
                error_type=last_error_type, error=last_error_message,
            )

            result = ExecutionResult(
                item_id=item.item_id,
                run_id=item.run_id,
                variant_id=item.variant_id,
                snapshot_id=item.snapshot_id,
                question_id=item.question_id,
                status="failure",
                response_text=None,
                selected_answer=None,
                parse_confidence=None,
                latency_ms=None,
                input_tokens=None,
                response_tokens=None,
                error_type=last_error_type,
                error_message=last_error_message,
                attempt_count=attempt_count,
                raw_response=None,
                raw_response_consolidated=None,
                started_at=started_at,
                finished_at=finished_at,
                finish_reason=None,
                request_json=execution_context.get("request_json"),
            )

            # Push result to shared queue (non-blocking: queue has unlimited size)
            if result_queue is not None:
                await result_queue.put(result)

            return result

    def _get_variant_for_item(
        self,
        run: PlanRun,
        variant_id: str,
    ) -> PlanVariant | None:
        """Get the variant for an item.

        Args:
            run: Plan run containing variants
            variant_id: Variant ID to find

        Returns:
            PlanVariant or None if not found
        """
        for variant in run.variants:
            if variant.variant_id == variant_id:
                return variant
        return None

    def _build_user_prompt(
        self,
        stem: str,
        options: list[str],
        user_prompt_template: str,
    ) -> str:
        """Build the user prompt from stem, options, and user prompt template.

        The user prompt is built by concatenating stem, options, and user_prompt_template
        with double newlines between them.

        Format:
            {stem}

            {options}

            {user_prompt_template}

        Args:
            stem: Question stem
            options: Answer options (may be randomized)
            user_prompt_template: User prompt template (may be empty)

        Returns:
            Complete user prompt with stem, options, and user prompt

        Example:
            >>> stem = "What is 2+2?"
            >>> options = ["3", "4", "5", "6"]
            >>> user_prompt = "Select the correct answer."
            >>> result = _build_user_prompt(stem, options, user_prompt)
            >>> result
            "What is 2+2?\\n\\nA) 3\\nB) 4\\nC) 5\\nD) 6\\n\\nSelect the correct answer."
        """
        # Build options text
        option_letters = ["A", "B", "C", "D"]
        options_text = "\n".join(
            f"{letter}) {option}"
            for letter, option in zip(option_letters, options[:len(option_letters)])
        )

        # Build complete user prompt: stem + options + user_prompt
        parts = [stem, options_text]
        if user_prompt_template:
            parts.append(user_prompt_template)

        return "\n\n".join(parts)

    def _build_user_message_for_item(
        self,
        item: PlanItem,
        options: list[str],
        user_prompt_template: str,
        model_config: ModelConfig,
        operation_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Build user message for an item (text-only or multimodal).

        This method decides whether to build a text-only or multimodal message
        based on:
        1. Whether the question has images (`has_image` and `image_path`)
        2. Whether the model variant has vision enabled (`enable_vision`)

        Vision Gating Logic:
        - If question has images AND variant has enable_vision=True:
            -> Build multimodal message with image
            -> If image file is missing: raise FileNotFoundError (item will fail)
        - If question has images BUT variant has enable_vision=False:
            -> Log warning
            -> Build text-only message (image omitted)
        - If question has no images:
            -> Build text-only message

        Args:
            item: Plan item containing question payload
            options: Answer options (may be randomized)
            user_prompt_template: User prompt template from run configuration
            model_config: Model configuration including vision flag

        Returns:
            User message dictionary (text-only or multimodal), or None if
            user_prompt_template is None (system-default behavior)

        Raises:
            FileNotFoundError: If question has image, vision is enabled, but
                              image file does not exist.
        """
        has_image = item.question_payload.has_image
        image_path_str = item.question_payload.image_path

        # Check if we should send images
        should_send_image = (
            has_image
            and image_path_str is not None
            and model_config.enable_vision
        )

        # Build text prompt
        text_prompt = self._build_user_prompt(
            stem=item.question_payload.stem,
            options=options,
            user_prompt_template=user_prompt_template,
        )

        # If text prompt is None (system-default), return None
        if text_prompt is None:
            return None

        # Handle image logic
        if should_send_image:
            image_path = Path(image_path_str)

            if not image_path.exists():
                # V2 FIX: Explicit failure instead of silent fallback
                error_msg = (
                    f"Image file not found for question {item.question_id}: {image_path}. "
                    f"Vision is enabled for this model variant, but the image file is missing. "
                    f"This item will fail to ensure data integrity."
                )
                self._logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            # Build multimodal message
            emit_event(
                self._logger, Event.VISION_ENABLED, operation_id=operation_id,
                question_id=item.question_id, image=str(image_path),
            )
            return MessageBuilder.build_multimodal_message(
                text=text_prompt,
                image_path=image_path,
            )

        # Question has images but vision is NOT enabled for this variant
        if has_image and image_path_str is not None:
            emit_event(
                self._logger, Event.VISION_DISABLED, level=logging.WARNING,
                operation_id=operation_id, question_id=item.question_id,
                image_path=image_path_str,
            )

        # Build text-only message
        return MessageBuilder.build_user_message(content=text_prompt)

    def _extract_response_content(self, response: Any) -> str:
        """Extract content from API response.

        Args:
            response: API response (CompletionResponse object)

        Returns:
            Response content as string
        """
        # If response is a CompletionResponse object, use its content directly
        if hasattr(response, "content"):
            return response.content or ""

        # Fallback for dict response (non-streaming legacy)
        if isinstance(response, dict):
            if "choices" in response:
                return response["choices"][0].get("message", {}).get("content", "")
            if "content" in response:
                return str(response["content"])
            return str(response)

        return str(response)

    def _extract_latency(self, response: Any) -> int | None:
        """Extract latency from API response.

        Args:
            response: API response

        Returns:
            Latency in milliseconds or None
        """
        if isinstance(response, dict):
            return response.get("latency_ms")
        if hasattr(response, "latency_ms"):
            return response.latency_ms
        return None

    def _extract_finish_reason(self, response: Any) -> str | None:
        """Extract finish reason from API response.

        Args:
            response: API response (CompletionResponse or dict)

        Returns:
            Finish reason string or None
        """
        # If response is a CompletionResponse object, extract from raw_response
        if hasattr(response, 'raw_response'):
            raw = response.raw_response
            
            # Handle list-based raw_response (streaming mode)
            if isinstance(raw, list):
                # Get from final non-debug chunk
                for chunk in reversed(raw):
                    if chunk.get("choices") and len(chunk["choices"]) > 0:
                        return chunk["choices"][0].get("finish_reason")
                return None
            
            # Handle dict-based raw_response (non-streaming legacy)
            if isinstance(raw, dict):
                if "choices" in raw:
                    choices = raw["choices"]
                    if choices and len(choices) > 0:
                        return choices[0].get("finish_reason")
                return raw.get("finish_reason")

        # If response is a dict, extract directly
        if isinstance(response, dict):
            if "choices" in response:
                choices = response["choices"]
                if choices and len(choices) > 0:
                    return choices[0].get("finish_reason")
            return response.get("finish_reason")

        # If response object has finish_reason attribute
        if hasattr(response, "finish_reason"):
            return response.finish_reason

        return None

    def _extract_effective_provider(self, raw_response: Any) -> str | None:
        """Extract the provider OpenRouter actually reports having used,
        from the raw response chunks — distinct from the requested
        provider (PlanVariant.resolved_provider, logged as
        PROVIDER_REQUESTED). Logging-only; never persisted separately
        from raw_response/raw_response_consolidated, which already carry
        it.

        Args:
            raw_response: The raw response chunks (list, for streaming)
                or dict (non-streaming), or None.

        Returns:
            The provider string if any chunk/response carries one, else None.
        """
        if isinstance(raw_response, list):
            for chunk in raw_response:
                if isinstance(chunk, dict) and chunk.get("provider"):
                    return chunk["provider"]
            return None
        if isinstance(raw_response, dict):
            return raw_response.get("provider")
        return None

    def _extract_error_details(self, response: Any) -> str:
        """Extract error details from model-level error response.

        Args:
            response: API response (CompletionResponse or dict)

        Returns:
            Error details string
        """
        raw = response.raw_response if hasattr(response, 'raw_response') else response
        if not raw:
            return "Unknown model error"

        # Handle list-based raw_response (streaming mode)
        if isinstance(raw, list):
            # Look for error in any chunk
            for chunk in raw:
                error = chunk.get('error', {})
                if error:
                    code = error.get('code', 'unknown')
                    message = error.get('message', 'No message')
                    return f"[{code}] {message}"
                
                # Check choices for error
                choices = chunk.get('choices', [])
                if choices and len(choices) > 0:
                    choice = choices[0]
                    if choice.get('finish_reason') == 'error':
                        return "Model error during generation"
            return "Unknown model error"

        # Handle dict-based raw_response (non-streaming legacy)
        if isinstance(raw, dict):
            # Per OpenRouter docs, error can be at top level or in choices
            error = raw.get('error', {})
            if error:
                code = error.get('code', 'unknown')
                message = error.get('message', 'No message')
                return f"[{code}] {message}"

            # Check choices for error
            choices = raw.get('choices', [])
            if choices and len(choices) > 0:
                choice = choices[0]
                if choice.get('finish_reason') == 'error':
                    return "Model error during generation"

        return "Unknown model error"

    def _classify_error(self, error: Exception) -> str:
        """Classify an error type.

        Args:
            error: Exception to classify

        Returns:
            Error type string
        """
        error_str = str(error).lower()

        if "timeout" in error_str:
            return "timeout"
        if "429" in error_str or "rate limit" in error_str:
            return "http_429"
        if "500" in error_str or "502" in error_str or "503" in error_str:
            return "http_5xx"
        if "connection" in error_str or "network" in error_str:
            return "network_error"
        if "authentication" in error_str or "401" in error_str:
            return "authentication_error"
        if "parse" in error_str:
            return "parse_error"

        return "api_error"
