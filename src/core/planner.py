"""Planner component for building immutable ExecutionPlans.

This module provides the Planner class, which is responsible for building
immutable ExecutionPlans from database state. The Planner is the ONLY
component (besides ResultWriter) with database write access during execution.

Design Principles:
    - Planner is read-only in this cycle (no plan persistence)
    - Planner resolves all configuration (no fallback to global settings)
    - Planner deduplicates items (excludes already-answered combinations)
    - Planner builds complete, self-contained plans

Example:
    >>> planner = Planner(db_manager)
    >>> plan = planner.build_plan(
    ...     experiment_name="test_exp",
    ...     run_name="run-001",
    ...     model_filter=["openai/gpt-4"],
    ...     question_filter=["Q001", "Q002"]
    ... )
"""

import logging
from datetime import datetime
from typing import Optional

from src.core.execution_plan import (
    ExecutionPlan,
    PlanItem,
    PlanRun,
    PlanVariant,
    generate_plan_id,
    generate_item_id,
)
from src.db.repository import (
    ExperimentRepository,
    RunRepository,
    ModelVariantRepository,
    RunModelRepository,
    QuestionSnapshotRepository,
    ResponseRepository,
)
from src.db.schema import DatabaseManager

logger = logging.getLogger(__name__)


class Planner:
    """Builds immutable ExecutionPlan from database state.

    The Planner is responsible for:
    1. Resolving experiment, runs, variants, and snapshots from DB
    2. Applying filters (model_filter, question_filter)
    3. Deduplicating items (excluding already-answered combinations)
    4. Resolving seeds and prompts (run overrides experiment)
    5. Building an immutable, self-contained ExecutionPlan

    Attributes:
        db_manager: DatabaseManager instance for database connections

    Example:
        >>> planner = Planner(db_manager)
        >>> plan = planner.build_plan("my_experiment")
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize the Planner with database access.

        Args:
            db_manager: DatabaseManager instance for database connections

        Example:
            >>> planner = Planner(db_manager)
        """
        self.db_manager = db_manager
        self._experiment_repo = ExperimentRepository(db_manager)
        self._run_repo = RunRepository(db_manager)
        self._variant_repo = ModelVariantRepository(db_manager)
        self._run_model_repo = RunModelRepository(db_manager)
        self._snapshot_repo = QuestionSnapshotRepository(db_manager)
        self._response_repo = ResponseRepository(db_manager)

        logger.info("Planner initialized")

    def build_plan(
        self,
        experiment_name: str,
        run_name: Optional[str] = None,
        model_filter: Optional[list[str]] = None,
        question_filter: Optional[list[str]] = None,
    ) -> ExecutionPlan:
        """Build complete ExecutionPlan from database state.

        This method builds an immutable, self-contained execution plan by:
        1. Resolving the experiment by name
        2. Resolving runs (filter by status != completed, optionally by run_name)
        3. Resolving variants (intersect with model_filter if provided)
        4. Resolving snapshots (intersect with question_filter if provided)
        5. Deduplicating items (exclude already-answered combinations)
        6. Resolving seeds and prompts (run overrides experiment)
        7. Building the immutable ExecutionPlan

        Args:
            experiment_name: Name of the experiment to execute
            run_name: Optional specific run name to execute (None = all pending runs)
            model_filter: Optional list of model IDs to filter variants
            question_filter: Optional list of question IDs to filter snapshots

        Returns:
            Immutable ExecutionPlan ready for execution

        Raises:
            ValueError: If experiment not found or no items to execute

        Example:
            >>> planner = Planner(db_manager)
            >>> plan = planner.build_plan(
            ...     experiment_name="test_exp",
            ...     run_name="run-001",
            ...     model_filter=["openai/gpt-4"],
            ...     question_filter=["Q001", "Q002"]
            ... )
        """
        logger.info(f"Building execution plan for experiment '{experiment_name}'")

        # Step 1: Resolve experiment
        experiment = self._resolve_experiment(experiment_name)
        logger.info(f"Resolved experiment: {experiment.name} (id={experiment.experiment_id})")

        # Step 2: Resolve runs
        runs = self._resolve_runs(experiment.experiment_id, run_name)
        if not runs:
            raise ValueError(f"No runs found for experiment '{experiment_name}' with status pending/running")
        logger.info(f"Resolved {len(runs)} run(s)")

        # Step 3: Resolve variants (for all runs)
        all_variants = self._resolve_variants(experiment.experiment_id, model_filter)
        if not all_variants:
            raise ValueError(f"No model variants found for experiment '{experiment_name}'")
        logger.info(f"Resolved {len(all_variants)} variant(s)")

        # Step 4: Resolve snapshots
        all_snapshots = self._resolve_snapshots(experiment.experiment_id, question_filter)
        if not all_snapshots:
            raise ValueError(f"No question snapshots found for experiment '{experiment_name}'")
        logger.info(f"Resolved {len(all_snapshots)} snapshot(s)")

        # Step 5 & 6: Build plan runs with deduplication
        plan_runs = []
        total_items = 0

        for run in runs:
            plan_run = self._build_plan_run(
                run=run,
                experiment=experiment,
                all_variants=all_variants,
                all_snapshots=all_snapshots,
            )
            plan_runs.append(plan_run)
            total_items += len(plan_run.items)

        if total_items == 0:
            raise ValueError("No items to execute (all combinations already answered)")

        # Step 7: Build immutable ExecutionPlan
        plan = ExecutionPlan(
            plan_id=generate_plan_id(experiment.experiment_id),
            created_at=datetime.now(),
            experiment_id=experiment.experiment_id,
            experiment_name=experiment.name,
            runs=plan_runs,
        )

        logger.info(f"Built execution plan: {plan.plan_id} with {len(plan_runs)} run(s), {total_items} item(s)")
        return plan

    def _resolve_experiment(self, name: str) -> "Experiment":
        """Resolve experiment by name.

        Args:
            name: Experiment name

        Returns:
            Experiment object

        Raises:
            ValueError: If experiment not found
        """
        from src.db.models import Experiment

        experiment = self._experiment_repo.get_by_name(name)
        if not experiment:
            raise ValueError(f"Experiment '{name}' not found. Use --create-experiment to create one.")
        return experiment

    def _resolve_runs(self, experiment_id: str, run_name: Optional[str]) -> list["Run"]:
        """Resolve runs for an experiment.

        Args:
            experiment_id: Experiment identifier
            run_name: Optional specific run name

        Returns:
            List of runs to execute (status != completed)

        Raises:
            ValueError: If specific run_name not found
        """
        from src.db.models import Run

        if run_name:
            # Find specific run by name pattern
            all_runs = self._run_repo.get_by_experiment(experiment_id)
            runs = [r for r in all_runs if r.run_id == run_name or r.run_id.endswith(run_name)]
            if not runs:
                raise ValueError(f"Run '{run_name}' not found in experiment")
        else:
            # Get all pending/running runs
            all_runs = self._run_repo.get_by_experiment(experiment_id)
            runs = [r for r in all_runs if r.status in ("pending", "running")]

        return runs

    def _resolve_variants(
        self, experiment_id: str, model_filter: Optional[list[str]]
    ) -> list["ModelVariant"]:
        """Resolve model variants for an experiment.

        Args:
            experiment_id: Experiment identifier
            model_filter: Optional list of model IDs to filter

        Returns:
            List of model variants
        """
        from src.db.models import ModelVariant

        # Get all variants for the experiment
        # Note: In TO-BE architecture, variants belong to experiments via experiment_models
        # For now, get all variants and filter by model_id if needed
        all_variants = self._variant_repo.get_all()

        if model_filter:
            # Filter variants by model_id
            filtered_variants = [v for v in all_variants if v.model_id in model_filter]
            logger.info(f"Filtered variants: {len(all_variants)} -> {len(filtered_variants)} (model_filter)")
            return filtered_variants

        return all_variants

    def _resolve_snapshots(
        self, experiment_id: str, question_filter: Optional[list[str]]
    ) -> list["QuestionSnapshot"]:
        """Resolve question snapshots for an experiment.

        Args:
            experiment_id: Experiment identifier
            question_filter: Optional list of question IDs to filter

        Returns:
            List of question snapshots
        """
        from src.db.models import QuestionSnapshot

        all_snapshots = self._snapshot_repo.get_by_experiment(experiment_id)

        if question_filter:
            # Filter snapshots by question_id
            filtered_snapshots = [s for s in all_snapshots if s.question_id in question_filter]
            logger.info(f"Filtered snapshots: {len(all_snapshots)} -> {len(filtered_snapshots)} (question_filter)")
            return filtered_snapshots

        return all_snapshots

    def _build_plan_run(
        self,
        run: "Run",
        experiment: "Experiment",
        all_variants: list["ModelVariant"],
        all_snapshots: list["QuestionSnapshot"],
    ) -> PlanRun:
        """Build a single PlanRun with deduplicated items.

        Args:
            run: Run object
            experiment: Experiment object
            all_variants: All model variants for the experiment
            all_snapshots: All question snapshots for the experiment

        Returns:
            PlanRun with resolved configuration and deduplicated items
        """
        import json

        # Resolve seed (run seed, fallback to experiment default)
        seed_effective = self._resolve_seed(run, experiment)

        # Resolve prompts (run prompts, fallback to experiment templates)
        system_prompt, user_prompt = self._resolve_prompts(run, experiment)

        # In TO-BE architecture, variants are GLOBAL (not associated with runs)
        # ALL variants from all_variants are used (already filtered by model_filter in _resolve_variants)
        variants_for_run = all_variants

        if not variants_for_run:
            logger.warning(f"No variants associated with run {run.run_id}, skipping")
            return None

        # Build PlanVariant list
        plan_variants = [
            PlanVariant(
                variant_id=v.variant_id,
                model_id=v.model_id,
                model_config=self._build_model_config(v),
            )
            for v in variants_for_run
        ]

        # Build items with deduplication
        items = self._build_deduplicated_items(
            run_id=run.run_id,
            variants=variants_for_run,
            snapshots=all_snapshots,
        )

        if not items:
            logger.warning(f"No items to execute for run {run.run_id}")

        return PlanRun(
            run_id=run.run_id,
            seed_effective=seed_effective,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            variants=plan_variants,
            items=items,
        )

    def _resolve_seed(self, run: "Run", experiment: "Experiment") -> Optional[int]:
        """Resolve effective seed value.

        Priority:
        1. Run seed (if set)
        2. Experiment default seed (if set)
        3. None (no randomization, preserve natural order)

        Args:
            run: Run object
            experiment: Experiment object

        Returns:
            Effective seed value or None (None = no randomization)

        Note:
            Returning None is VALID and means:
            - No answer randomization is applied
            - Questions execute in natural snapshot order
            - Execution is deterministic by construction
        """
        # Run seed takes precedence
        if run.seed is not None:
            return run.seed

        # Try to get seed from experiment config
        import json

        try:
            config = json.loads(experiment.config_json)
            if "random_seed" in config and config["random_seed"] is not None:
                return config["random_seed"]
        except (json.JSONDecodeError, KeyError):
            pass

        # Default: None (no randomization)
        return None

    def _resolve_prompts(self, run: "Run", experiment: "Experiment") -> tuple[str, str]:
        """Resolve effective prompts.

        Priority:
        1. Run prompts (if set)
        2. Experiment templates
        3. Defaults

        Args:
            run: Run object
            experiment: Experiment object

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Run-level prompts (if run table has prompt columns)
        # For now, use experiment templates
        system_prompt = experiment.system_prompt_template or "You are a helpful assistant."
        user_prompt = experiment.user_prompt_template or "Select the correct answer by providing only the letter (A, B, C, or D)."

        return system_prompt, user_prompt

    def _build_model_config(self, variant: "ModelVariant") -> dict:
        """Build model configuration from variant.

        Args:
            variant: ModelVariant object

        Returns:
            Model configuration dictionary for API calls
        """
        return {
            "reasoning_mode": variant.reasoning_mode,
            "reasoning_effort": variant.reasoning_effort,
            "max_output_tokens": variant.max_output_tokens,  # Note: ModelVariant uses max_output_tokens
            "vision_enabled": variant.vision_enabled,
            "structured_output": variant.structured_output,  # Note: ModelVariant uses structured_output
        }

    def _build_deduplicated_items(
        self,
        run_id: str,
        variants: list["ModelVariant"],
        snapshots: list["QuestionSnapshot"],
    ) -> list[PlanItem]:
        """Build deduplicated list of PlanItems.

        Deduplication key: (run_id, variant_id, snapshot_id)
        Excludes items that already have responses in the database.

        Args:
            run_id: Run identifier
            variants: List of model variants
            snapshots: List of question snapshots

        Returns:
            List of PlanItems to execute
        """
        import json

        items = []

        # Get existing response keys for deduplication
        existing_keys = self._get_existing_response_keys(run_id, variants)

        for variant in variants:
            for snapshot in snapshots:
                # Check if this combination already has a response
                key = (run_id, variant.variant_id, snapshot.snapshot_id)
                if key in existing_keys:
                    logger.debug(f"Skipping already answered: {key}")
                    continue

                # Parse question payload from snapshot
                try:
                    question_payload = json.loads(snapshot.question_payload)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse snapshot {snapshot.snapshot_id}: {e}")
                    continue

                # Build item
                item = PlanItem(
                    item_id=generate_item_id(run_id, variant.variant_id, snapshot.snapshot_id),
                    run_id=run_id,
                    variant_id=variant.variant_id,
                    model_id=variant.model_id,
                    snapshot_id=snapshot.snapshot_id,
                    question_id=snapshot.question_id,
                    iteration_number=1,  # Fixed at 1 - no iteration concept in TO-BE
                    question_payload=question_payload,
                )
                items.append(item)

        logger.info(f"Built {len(items)} items for run {run_id} ({len(existing_keys)} already answered)")
        return items

    def _get_existing_response_keys(
        self, run_id: str, variants: list["ModelVariant"]
    ) -> set:
        """Get set of existing response keys for deduplication.

        Key: (run_id, variant_id, snapshot_id)

        Args:
            run_id: Run identifier
            variants: List of model variants

        Returns:
            Set of existing response keys
        """
        existing_keys = set()

        for variant in variants:
            # Get all responses for this run and variant
            responses = self._response_repo.get_by_run_and_model(run_id, variant.model_id)
            for response in responses:
                key = (run_id, variant.variant_id, response.snapshot_id)
                existing_keys.add(key)

        return existing_keys
