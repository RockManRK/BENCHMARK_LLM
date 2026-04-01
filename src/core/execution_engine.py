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

Example:
    >>> engine = ExecutionEngine(api_client, randomizer, parser)
    >>> results = engine.execute(plan)
    >>> for result in results:
    ...     print(f"Item {result.item_id}: {result.status}")
"""

from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Any, Literal, Optional

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
        error_type: Type of error if failed (None on success)
        error_message: Error message if failed (None on success)
        attempt_count: Number of API call attempts made
        raw_response: Raw API response (dict for non-streaming, list for streaming) (None on failure)
        started_at: Execution start timestamp (None on failure)
        finished_at: Execution end timestamp (None on failure)
        finish_reason: API finish reason (None on failure)
        error_details: Model-level error details (None on success or execution failure)

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
        ...     error_type=None,
        ...     error_message=None,
        ...     attempt_count=1,
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
    raw_response: list[dict] | dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    finish_reason: str | None = None
    error_details: str | None = None


class OpenRouterClient:
    """Type hint for OpenRouterClient.

    This is a placeholder for type hints. The actual implementation
    is in src.api.client (to be implemented).
    """

    async def chat_completion(
        self,
        model_id: str,
        messages: list[dict],
        **kwargs: Any,
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

    def execute(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        """Execute all items in the plan.

        This method executes all items in all runs in the execution plan.
        For each item:

        1. Apply randomization (if seed is set)
        2. Build the prompt
        3. Call the API
        4. Parse the response
        5. Create ExecutionResult

        Args:
            plan: Immutable execution plan from Planner

        Returns:
            List of ExecutionResult (one per item)

        Constraints:
            - NO database access
            - NO configuration resolution
            - NO scope decisions
            - Returns pure data only

        Example:
            >>> results = engine.execute(plan)
            >>> for result in results:
            ...     print(f"Item {result.item_id}: {result.status}")
        """
        all_results: list[ExecutionResult] = []

        # Extract context from plan for logging
        experiment_id = plan.experiment_id
        run_count = len(plan.runs)
        total_items = sum(len(run.items) for run in plan.runs)

        self._logger.info(
            f"EXECUTION_START | experiment={experiment_id} | runs={run_count} | total_items={total_items}"
        )

        for run in plan.runs:
            run_results = self._execute_run(run)
            all_results.extend(run_results)

        # Calculate summary statistics
        succeeded = sum(1 for r in all_results if r.status == 'success')
        failed = sum(1 for r in all_results if r.status == 'failure')

        self._logger.info(
            f"EXECUTION_COMPLETE | experiment={experiment_id} | total={total_items} | succeeded={succeeded} | failed={failed}"
        )

        return all_results

    def _execute_run(self, run: PlanRun) -> list[ExecutionResult]:
        """Execute all items in a single run.

        Args:
            run: Plan run to execute

        Returns:
            List of ExecutionResult for this run
        """
        results: list[ExecutionResult] = []
        total_items = len(run.items)
        completed = 0

        # Create retry handler for this run using its retry policy
        run_retry_handler = RetryHandler(
            policy=run.retry_policy,
            logger=self._logger
        )

        # Apply randomization seed if set
        if run.seed_effective is not None:
            self.randomizer.set_seed(run.seed_effective)

        # Calculate milestone interval (25%, 50%, 75%, 100%)
        milestone_interval = max(1, total_items // 4)

        for i, item in enumerate(run.items):
            result = self._execute_item(item, run, run_retry_handler)
            results.append(result)
            completed = i + 1

            # Log progress milestones
            if completed % milestone_interval == 0 or completed == total_items:
                percent = int((completed / total_items) * 100)
                self._logger.info(
                    f"PROGRESS_MILESTONE | run={run.run_id} | completed={completed}/{total_items} | percent={percent}%"
                )

        return results

    async def _execute_item_async(
        self,
        item: PlanItem,
        run: PlanRun,
        retry_handler: Optional[RetryHandler] = None,
    ) -> ExecutionResult:
        """Execute a single item asynchronously with retry policy.

        Args:
            item: Plan item to execute
            run: Parent run containing retry policy
            retry_handler: Optional retry handler. If not provided, uses self._retry_handler.

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

        # Log item start
        self._logger.info(
            f"ITEM_START | run={item.run_id} | variant={item.variant_id} | snapshot={item.snapshot_id}"
        )

        # Get the variant for this item
        variant = self._get_variant_for_item(run, item.variant_id)
        if variant is None:
            error_msg = f"Variant {item.variant_id} not found in run"
            # Capture finish timestamp for config error
            finished_at = datetime.now()
            self._logger.error(
                f"ITEM_FAILED | run={item.run_id} | variant={item.variant_id} | snapshot={item.snapshot_id} | error_type=config_error | error={error_msg}"
            )
            return ExecutionResult(
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

        # Retry wrapper for API call
        async def api_call_with_retry() -> dict:
            """Inner function for RetryHandler to execute."""
            nonlocal attempt_count

            # Apply randomization if seed is set
            options = list(item.question_payload.options)
            if run.seed_effective is not None:
                randomized = self.randomizer.randomize_options(
                    options,
                    seed=run.seed_effective,
                )
                options = randomized["options"]

            # Build the prompt
            user_prompt = self._build_user_prompt(
                item.question_payload.stem,
                options,
                run.prompts_effective.user,
            )

            # Build messages - filter out None content (system-default means "do not send")
            messages = []
            if run.prompts_effective.system is not None:
                messages.append({"role": "system", "content": run.prompts_effective.system})
            if user_prompt is not None:
                messages.append({"role": "user", "content": user_prompt})

            # Get model config
            model_config = variant.model_config_effective

            # Build response_format if structured_output is enabled
            response_format: dict[str, Any] | None = None
            if model_config.structured_output:
                response_format = {"type": "json_object"}

            # Call API (this is what RetryHandler will retry)
            # CRITICAL: Use variant.model_id for API calls (external identifier)
            # variant.variant_id is for internal identity tracking only
            response = await self.api_client.chat_completion(
                model_id=variant.model_id,  # External API identifier
                messages=messages,
                temperature=model_config.temperature,
                top_p=model_config.top_p,
                max_tokens=model_config.max_output_tokens,
                response_format=response_format,
            )

            # Extract response data
            response_text = self._extract_response_content(response)
            latency_ms = self._extract_latency(response)
            input_tokens = self._extract_input_tokens(response)
            response_tokens = self._extract_output_tokens(response)
            finish_reason = self._extract_finish_reason(response)
            raw_response = response.raw_response if hasattr(response, 'raw_response') else None

            # Check for model-level error (HTTP 200 with finish_reason: 'error')
            error_details: str | None = None
            if finish_reason == 'error':
                # Model encountered an error during generation
                # This is a successful execution with model error, not an execution failure
                error_details = self._extract_error_details(response)

                self._logger.warning(
                    f"MODEL_ERROR | run={item.run_id} | variant={item.variant_id} | "
                    f"snapshot={item.snapshot_id} | error={error_details}"
                )

            # Check for no-content scenario (OpenRouter warm-up/scaling)
            if not response_text or response_text.strip() == '':
                self._logger.warning(
                    f"NO_CONTENT | run={item.run_id} | variant={item.variant_id} | "
                    f"snapshot={item.snapshot_id} | Model returned empty content "
                    f"(possible warm-up or scaling scenario)"
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
                "finish_reason": finish_reason,
                "raw_response": raw_response,
                "error_details": error_details,
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
            finish_reason = result_data["finish_reason"]
            raw_response = result_data["raw_response"]
            error_details = result_data.get("error_details")

            # Capture finish timestamp
            finished_at = datetime.now()

            # Calculate total tokens
            total_tokens = (input_tokens or 0) + (response_tokens or 0)

            # Log success
            self._logger.info(
                f"ITEM_COMPLETE | run={item.run_id} | variant={item.variant_id} | snapshot={item.snapshot_id} | latency={latency_ms}ms | tokens={total_tokens}"
            )

            return ExecutionResult(
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
                error_type=None,
                error_message=None,
                attempt_count=attempt_count,
                raw_response=raw_response,
                started_at=started_at,
                finished_at=finished_at,
                finish_reason=finish_reason,
                error_details=error_details,
            )

        except Exception as e:
            # Retry exhausted or non-retryable error
            last_error_type = self._classify_error(e)
            last_error_message = str(e)
            attempt_count = getattr(e, '_retry_attempts', 1)

            # Capture finish timestamp
            finished_at = datetime.now()

            # Log failure
            self._logger.error(
                f"ITEM_FAILED | run={item.run_id} | variant={item.variant_id} | snapshot={item.snapshot_id} | error_type={last_error_type} | error={last_error_message}"
            )

            return ExecutionResult(
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
                started_at=started_at,
                finished_at=finished_at,
                finish_reason=None,
            )

    def _execute_item(
        self,
        item: PlanItem,
        run: PlanRun,
        retry_handler: Optional[RetryHandler] = None,
    ) -> ExecutionResult:
        """Execute a single item (synchronous wrapper for async execution).

        Args:
            item: Plan item to execute
            run: Parent run containing retry policy
            retry_handler: Optional retry handler. If not provided, uses self._retry_handler.

        Returns:
            ExecutionResult for this item
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - run in a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._execute_item_async(item, run, retry_handler),
                    )
                    return future.result()
            else:
                # No running loop - use asyncio.run directly
                return asyncio.run(self._execute_item_async(item, run, retry_handler))
        except RuntimeError:
            # No event loop exists - create new one
            return asyncio.run(self._execute_item_async(item, run, retry_handler))

    def _call_api_sync(
        self,
        model_id: str,
        messages: list[dict],
        model_config: ModelConfig,
    ) -> Any:
        """Call the API synchronously.

        Args:
            model_id: Model identifier for API call
            messages: Chat messages
            model_config: Model configuration

        Returns:
            API response
        """
        import asyncio

        # Build response_format if structured_output is enabled
        response_format: dict[str, Any] | None = None
        if model_config.structured_output:
            response_format = {"type": "json_object"}

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context - run in a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.api_client.chat_completion(
                            model_id=model_id,
                            messages=messages,
                            temperature=model_config.temperature,
                            top_p=model_config.top_p,
                            max_tokens=model_config.max_output_tokens,
                            response_format=response_format,
                        )
                    )
                    return future.result()
            else:
                # No running loop - use asyncio.run directly
                return asyncio.run(
                    self.api_client.chat_completion(
                        model_id=model_id,
                        messages=messages,
                        temperature=model_config.temperature,
                        top_p=model_config.top_p,
                        max_tokens=model_config.max_output_tokens,
                        response_format=response_format,
                    )
                )
        except RuntimeError:
            # No event loop exists - create new one
            return asyncio.run(
                self.api_client.chat_completion(
                    model_id=model_id,
                    messages=messages,
                    temperature=model_config.temperature,
                    top_p=model_config.top_p,
                    max_tokens=model_config.max_output_tokens,
                    response_format=response_format,
                )
            )

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
        """Build the user prompt from template.

        Args:
            stem: Question stem
            options: Answer options (may be randomized)
            user_prompt_template: User prompt template

        Returns:
            Formatted user prompt
        """
        # Build options text
        option_letters = ["A", "B", "C", "D"]
        options_text = "\n".join(
            f"{letter}) {option}"
            for letter, option in zip(option_letters, options[:len(option_letters)])
        )

        # Build question text
        question_text = f"{stem}\n\n{options_text}"

        # Format template
        user_prompt = user_prompt_template.replace("{question}", question_text)

        return user_prompt

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

    def _extract_input_tokens(self, response: Any) -> int | None:
        """Extract input tokens from API response.

        Args:
            response: API response

        Returns:
            Input token count or None
        """
        if isinstance(response, dict):
            usage = response.get("usage", {})
            return usage.get("prompt_tokens") or usage.get("input_tokens")
        if hasattr(response, "input_tokens"):
            return response.input_tokens
        return None

    def _extract_output_tokens(self, response: Any) -> int | None:
        """Extract output tokens from API response.

        Args:
            response: API response

        Returns:
            Output token count or None
        """
        if isinstance(response, dict):
            usage = response.get("usage", {})
            return usage.get("completion_tokens") or usage.get("output_tokens")
        if hasattr(response, "output_tokens"):
            return response.output_tokens
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
