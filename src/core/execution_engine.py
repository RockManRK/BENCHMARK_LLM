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
from typing import Any, Literal

from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    ModelConfig,
)
from src.core.randomizer import AnswerRandomizer
from src.core.answer_parser import AnswerParser, ParsedAnswer


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
        output_tokens: Number of output tokens (None on failure)
        error_type: Type of error if failed (None on success)
        error_message: Error message if failed (None on success)
        attempt_count: Number of API call attempts made

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
        ...     output_tokens=10,
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
    output_tokens: int | None
    error_type: str | None
    error_message: str | None
    attempt_count: int


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
    ) -> None:
        """Initialize engine with dependencies.

        Args:
            api_client: OpenRouter API client
            randomizer: Answer option randomizer (seeded)
            parser: Response parser with confidence levels

        Example:
            >>> engine = ExecutionEngine(api_client, randomizer, parser)
        """
        self.api_client = api_client
        self.randomizer = randomizer
        self.parser = parser

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

        for run in plan.runs:
            run_results = self._execute_run(run)
            all_results.extend(run_results)

        return all_results

    def _execute_run(self, run: PlanRun) -> list[ExecutionResult]:
        """Execute all items in a single run.

        Args:
            run: Plan run to execute

        Returns:
            List of ExecutionResult for this run
        """
        results: list[ExecutionResult] = []

        # Apply randomization seed if set
        if run.seed_effective is not None:
            self.randomizer.set_seed(run.seed_effective)

        for item in run.items:
            result = self._execute_item(item, run)
            results.append(result)

        return results

    def _execute_item(
        self,
        item: PlanItem,
        run: PlanRun,
    ) -> ExecutionResult:
        """Execute a single item.

        Args:
            item: Plan item to execute
            run: Parent run containing retry policy

        Returns:
            ExecutionResult for this item
        """
        attempt_count = 0
        last_error_type: str | None = None
        last_error_message: str | None = None

        # Get the variant for this item
        variant = self._get_variant_for_item(run, item.variant_id)
        if variant is None:
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
                output_tokens=None,
                error_type="config_error",
                error_message=f"Variant {item.variant_id} not found in run",
                attempt_count=0,
            )

        # Retry loop
        max_attempts = run.retry_policy.max_attempts

        for attempt in range(1, max_attempts + 1):
            attempt_count = attempt

            try:
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

                # Build messages - filter out null content (null means "do not send")
                messages = []
                if run.prompts_effective.system is not None:
                    messages.append({"role": "system", "content": run.prompts_effective.system})
                if user_prompt is not None:
                    messages.append({"role": "user", "content": user_prompt})

                # Get model config
                model_config = variant.model_config_effective

                # Call API
                # CRITICAL: Use variant.model_id for API calls (external identifier)
                # variant.variant_id is for internal identity tracking only
                response = self._call_api_sync(
                    variant.model_id,  # External API identifier
                    messages,
                    model_config,
                )

                # Extract response data
                response_text = self._extract_response_content(response)
                latency_ms = self._extract_latency(response)
                input_tokens = self._extract_input_tokens(response)
                output_tokens = self._extract_output_tokens(response)

                # Parse the answer
                parsed = self.parser.parse(response_text)

                # Success!
                return ExecutionResult(
                    item_id=item.item_id,
                    run_id=item.run_id,
                    variant_id=item.variant_id,  # Internal identity
                    snapshot_id=item.snapshot_id,
                    question_id=item.question_id,
                    status="success",
                    response_text=response_text,
                    selected_answer=parsed.answer,
                    parse_confidence=parsed.confidence,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error_type=None,
                    error_message=None,
                    attempt_count=attempt_count,
                )

            except Exception as e:
                # Record error
                last_error_type = self._classify_error(e)
                last_error_message = str(e)

                # Continue to next attempt
                if attempt < max_attempts:
                    continue

        # All attempts failed
        return ExecutionResult(
            item_id=item.item_id,
            run_id=item.run_id,
            variant_id=item.variant_id,  # Internal identity
            snapshot_id=item.snapshot_id,
            question_id=item.question_id,
            status="failure",
            response_text=None,
            selected_answer=None,
            parse_confidence=None,
            latency_ms=None,
            input_tokens=None,
            output_tokens=None,
            error_type=last_error_type,
            error_message=last_error_message,
            attempt_count=attempt_count,
        )

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
            response: API response (dict or object)

        Returns:
            Response content as string
        """
        if isinstance(response, dict):
            # Handle dict response
            if "choices" in response:
                return response["choices"][0].get("message", {}).get("content", "")
            if "content" in response:
                return str(response["content"])
            return str(response)

        # Handle object response
        if hasattr(response, "content"):
            return str(response.content)

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
