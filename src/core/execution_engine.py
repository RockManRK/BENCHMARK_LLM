"""Purified ExecutionEngine for benchmark_llm.

This module provides a unified, context-agnostic execution engine for running
benchmarks. It executes ONLY an ExecutionPlan and returns ExecutionResults.

Design Principles:
    - ExecutionEngine does NOT know about database
    - ExecutionEngine does NOT persist results
    - ExecutionEngine ONLY executes API calls and returns raw results
    - Persistence is the responsibility of the caller (ResultWriter)

Example:
    >>> engine = ExecutionEngine(api_client, randomizer, settings)
    >>> results = engine.execute(plan)
    >>> # Results are pure data - caller persists them
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from src.api.client import MessageBuilder, OpenRouterClient
from src.core.execution_plan import (
    ExecutionPlan,
    ExecutionResult,
    PlanItem,
    PlanRun,
    PlanVariant,
)
from src.core.randomizer import AnswerRandomizer
from src.utils.config import Settings

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Pure execution engine. NO DB ACCESS.

    This engine executes an ExecutionPlan by making API calls and returning
    ExecutionResults. It does NOT:
    - Access the database
    - Create or modify model variants
    - Create or modify question snapshots
    - Persist results
    - Decide scope or deduplicate

    Attributes:
        api_client: OpenRouter API client for model inference
        randomizer: Answer randomizer for shuffling options
        settings: Application settings

    Example:
        >>> engine = ExecutionEngine(api_client, randomizer, settings)
        >>> results = engine.execute(plan)
    """

    def __init__(
        self,
        api_client: OpenRouterClient,
        randomizer: AnswerRandomizer,
        settings: Settings,
    ) -> None:
        """Initialize the execution engine.

        Args:
            api_client: OpenRouter API client for model inference
            randomizer: Answer randomizer for shuffling options
            settings: Application settings

        Example:
            >>> engine = ExecutionEngine(api_client, randomizer, settings)
        """
        self.api_client = api_client
        self.randomizer = randomizer
        self.settings = settings

        logger.debug("ExecutionEngine initialized (NO DB ACCESS)")

    def execute(self, plan: ExecutionPlan) -> list[ExecutionResult]:
        """Execute all items in plan.

        This method executes all items in the ExecutionPlan by:
        1. For each run in plan
        2. For each variant in run
        3. For each item in run.items
           - Build API request (prompts + question_payload)
           - Apply answer randomization
           - Call API
           - Parse response
           - Return ExecutionResult

        Args:
            plan: ExecutionPlan to execute

        Returns:
            List of ExecutionResult objects (pure data, no persistence)

        Example:
            >>> results = engine.execute(plan)
            >>> for result in results:
            ...     print(f"{result.question_id}: {result.status}")
        """
        all_results = []

        logger.info(f"Starting execution of plan {plan.plan_id}")
        logger.info(f"Plan: {len(plan.runs)} run(s), experiment={plan.experiment_name}")

        for plan_run in plan.runs:
            logger.info(f"Executing run {plan_run.run_id}")

            # Execute all items in this run
            run_results = self._execute_run(plan_run)
            all_results.extend(run_results)

            logger.info(
                f"Completed run {plan_run.run_id}: {len(run_results)} items executed"
            )

        logger.info(
            f"Execution completed: {len(all_results)} total results for plan {plan.plan_id}"
        )
        return all_results

    def _execute_run(self, plan_run: PlanRun) -> list[ExecutionResult]:
        """Execute all items in a single run.

        Args:
            plan_run: PlanRun to execute

        Returns:
            List of ExecutionResult objects for this run
        """
        results = []

        # Initialize randomizer with run seed (only if seed is not None)
        # seed=None means "no randomization, preserve natural order"
        if self.randomizer and plan_run.seed_effective is not None:
            self.randomizer.reset_seed(plan_run.seed_effective)
            logger.debug(f"Randomizer initialized with seed={plan_run.seed_effective}")
        elif self.randomizer:
            logger.debug("seed_effective is None, skipping randomization (natural order)")

        # Execute all items
        for item in plan_run.items:
            logger.debug(f"Executing item {item.item_id}")

            # Execute item
            result = self._execute_item(
                item=item,
                plan_run=plan_run,
            )
            results.append(result)

        return results

    def _execute_item(
        self,
        item: PlanItem,
        plan_run: PlanRun,
    ) -> ExecutionResult:
        """Execute a single item.

        Args:
            item: PlanItem to execute
            plan_run: PlanRun containing the item

        Returns:
            ExecutionResult for this item
        """
        start_time = time.time()

        try:
            # Build question payload with options
            question_payload = item.question_payload
            stem = question_payload.get("stem", "")
            options = question_payload.get("options", {})
            correct_answer = question_payload.get("answer_key", None)

            # Build options text
            options_text = "\n".join([f"{k}) {v}" for k, v in options.items()])

            # Build prompt
            prompt = f"""{stem}

{options_text}

{plan_run.user_prompt}"""

            # Apply answer randomization ONLY if:
            # 1. Randomizer is available
            # 2. seed_effective is NOT None (None = no randomization)
            # 3. correct_answer exists
            should_randomize = (
                self.randomizer is not None
                and plan_run.seed_effective is not None
                and correct_answer is not None
            )

            if should_randomize:
                # Randomize options and get new correct answer
                randomized = self.randomizer._randomize_options(options, correct_answer)
                randomized_options = randomized["options"]
                randomized_correct = randomized["correct_answer"]

                # Rebuild options text with randomized order
                options_text = "\n".join([f"{k}) {v}" for k, v in randomized_options.items()])

                # Rebuild prompt with randomized options
                prompt = f"""{stem}

{options_text}

{plan_run.user_prompt}"""

                logger.debug(
                    f"Randomized question {item.question_id}: correct answer {correct_answer} -> {randomized_correct}"
                )
            else:
                # No randomization: use original order
                randomized_correct = correct_answer
                if plan_run.seed_effective is None:
                    logger.debug(f"Question {item.question_id}: no randomization (seed=None)")

            # Build user message
            if item.question_payload.get("has_image") and item.question_payload.get("image_path"):
                # Multimodal message
                from pathlib import Path

                image_path = Path(item.question_payload["image_path"])
                if image_path.exists():
                    user_message = MessageBuilder.build_multimodal_message(prompt, image_path)
                else:
                    logger.warning(f"Image not found for question {item.question_id}: {image_path}")
                    user_message = MessageBuilder.build_user_message(prompt)
            else:
                # Text-only message
                user_message = MessageBuilder.build_user_message(prompt)

            # Build messages array with system prompt
            messages = [
                {"role": "system", "content": plan_run.system_prompt},
                user_message,
            ]

            # Build model config from variant
            model_config = self._get_variant_model_config(item)

            # Execute API call (handle both sync and async contexts)
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # We're in an async context - use create_task
                api_response = asyncio.run_coroutine_threadsafe(
                    self.api_client.chat_completion(
                        model=item.model_id,
                        messages=messages,
                        **model_config,
                    ),
                    loop
                ).result()
            except RuntimeError:
                # No running loop - use asyncio.run
                api_response = asyncio.run(
                    self.api_client.chat_completion(
                        model=item.model_id,
                        messages=messages,
                        **model_config,
                    )
                )

            # Parse response
            parsed = self._parse_api_response(api_response, randomized_correct)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract token usage
            tokens = self._extract_token_usage(api_response)

            # Build execution result
            result = ExecutionResult(
                item_id=item.item_id,
                run_id=item.run_id,
                variant_id=item.variant_id,
                model_id=item.model_id,
                snapshot_id=item.snapshot_id,
                question_id=item.question_id,
                iteration_number=item.iteration_number,
                status="success",
                response_text=parsed.get("response_text", ""),
                selected_answer=parsed.get("selected_answer"),
                is_correct=parsed.get("is_correct"),
                latency_ms=latency_ms,
                input_tokens=tokens.get("input_tokens", 0),
                output_tokens=tokens.get("output_tokens", 0),
            )

            logger.info(
                f"Item {item.item_id} completed: "
                f"answer={parsed.get('selected_answer')}, "
                f"correct={parsed.get('is_correct')}, "
                f"latency={latency_ms}ms"
            )

            return result

        except Exception as e:
            logger.exception(f"Failed to execute item {item.item_id}: {e}")

            # Build error result
            result = ExecutionResult(
                item_id=item.item_id,
                run_id=item.run_id,
                variant_id=item.variant_id,
                model_id=item.model_id,
                snapshot_id=item.snapshot_id,
                question_id=item.question_id,
                iteration_number=item.iteration_number,
                status="failure",
                response_text="",
                selected_answer=None,
                is_correct=None,
                latency_ms=int((time.time() - start_time) * 1000),
                input_tokens=0,
                output_tokens=0,
                error_type=type(e).__name__,
                error_message=str(e),
            )

            return result

    def _get_variant_model_config(self, item: PlanItem) -> dict[str, Any]:
        """Build model config from variant settings.

        Args:
            item: PlanItem with variant information

        Returns:
            Dictionary of model kwargs for API call
        """
        config = {}

        # Add generation parameters from settings
        if hasattr(self.settings, 'model_max_tokens') and self.settings.model_max_tokens is not None:
            config["max_tokens"] = self.settings.model_max_tokens

        if hasattr(self.settings, 'model_temperature') and self.settings.model_temperature is not None:
            config["temperature"] = self.settings.model_temperature

        if hasattr(self.settings, 'model_top_p') and self.settings.model_top_p is not None:
            config["top_p"] = self.settings.model_top_p

        # Build reasoning config from settings
        reasoning = self._build_reasoning_config()
        if reasoning is not None:
            config["reasoning"] = reasoning

        # Add structured output if enabled
        if hasattr(self.settings, 'use_structured_outputs') and self.settings.use_structured_outputs:
            from src.utils.answer_schema import ANSWER_SCHEMA
            config["response_format"] = ANSWER_SCHEMA

        return config

    def _build_reasoning_config(self) -> Optional[dict[str, Any]]:
        """Build reasoning configuration from settings.

        Returns:
            Reasoning config dict or None if not configured
        """
        if not self.settings:
            return None

        reasoning_config = {}

        if hasattr(self.settings, 'reasoning_effort') and self.settings.reasoning_effort is not None:
            if self.settings.reasoning_effort == 'none':
                reasoning_config["enabled"] = False
            else:
                reasoning_config["effort"] = self.settings.reasoning_effort

        if hasattr(self.settings, 'reasoning_max_tokens') and self.settings.reasoning_max_tokens is not None:
            reasoning_config["max_tokens"] = self.settings.reasoning_max_tokens

        if hasattr(self.settings, 'reasoning_enabled') and self.settings.reasoning_enabled is not None:
            reasoning_config["enabled"] = self.settings.reasoning_enabled

        return reasoning_config if reasoning_config else None

    def _parse_api_response(
        self,
        api_response: dict[str, Any],
        correct_answer: Optional[str],
    ) -> dict[str, Any]:
        """Parse API response and extract answer.

        Args:
            api_response: Raw API response dictionary
            correct_answer: Correct answer for comparison

        Returns:
            Dictionary with parsed response data
        """
        # Extract content from response
        choices = api_response.get("choices", [])
        content = ""
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")

        # Parse answer from content
        selected_answer = self._parse_answer(content)

        # Determine if correct
        is_correct = selected_answer == correct_answer if selected_answer and correct_answer else None

        return {
            "response_text": content,
            "selected_answer": selected_answer,
            "is_correct": is_correct,
        }

    def _parse_answer(self, content: str) -> Optional[str]:
        """Parse answer letter from response content.

        Args:
            content: Response content from model

        Returns:
            Answer letter (A, B, C, D) or None
        """
        if not content:
            return None

        # Try to extract answer letter using AnswerParser
        try:
            from src.core.answer_parser import AnswerParser

            parser = AnswerParser()
            parsed = parser.parse(content)
            return parsed.answer if parsed.answer else None
        except Exception:
            # Fallback: simple regex extraction
            import re

            match = re.search(r'\b([A-D])\b', content.upper())
            if match:
                return match.group(1)

            # Try to find "answer is X" pattern
            match = re.search(r'answer\s+is\s+([A-D])', content.upper())
            if match:
                return match.group(1)

            return None

    def _extract_token_usage(self, api_response: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from API response.

        Args:
            api_response: Raw API response dictionary

        Returns:
            Dictionary with input_tokens, output_tokens, total_tokens
        """
        usage = api_response.get("usage", {})

        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
