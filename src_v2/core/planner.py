"""Planner — Builds immutable ExecutionPlan from database state.

The Planner is a read-only component that constructs ExecutionPlan
instances from the database. It validates preconditions and resolves
effective values, but never modifies database state.

Key responsibilities:
- Validate experiment exists and has models/snapshots
- Read experiment, runs, variants, snapshots from DB
- Resolve effective prompts (run overrides experiment)
- Resolve effective seed (run overrides experiment)
- Build ExecutionPlan with deduplicated items per run
- Apply run ID filters when specified
- Apply question ID filters when specified
- Apply model variant ID filters when specified
- Apply retry policy when specified

The Planner is READ-ONLY:
- No database writes
- No state inference or repair
- Explicit validation only
- All execution decisions explicit in ExecutionPlan
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Any

from src_v2.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)


class PlannerValidationError(Exception):
    """Raised when Planner cannot build a valid execution plan.

    This exception is raised when validation rules are violated:
    - Experiment does not exist
    - Experiment has no models
    - Experiment has no snapshots

    Example:
        planner = Planner(conn)
        try:
            plan = planner.build_plan("non-existent")
        except PlannerValidationError as e:
            print(f"Validation failed: {e}")
    """

    pass


class Planner:
    """Builds immutable ExecutionPlan from database state. READ-ONLY.

    The Planner is responsible for constructing ExecutionPlan instances
    from the database. It performs explicit validation and resolves
    effective values, but never modifies database state.

    Attributes:
        conn: Database connection (read-only usage)

    Example:
        conn = sqlite3.connect("benchmark.db")
        planner = Planner(conn)
        plan = planner.build_plan("my-experiment")
        # plan is an immutable ExecutionPlan
    """

    def __init__(self, db_connection: sqlite3.Connection) -> None:
        """Initialize with database connection.

        Args:
            db_connection: SQLite database connection (used read-only)
        """
        self.conn = db_connection

    def build_plan(
        self,
        experiment_name: str,
        run_ids: list[str] | None = None,
        question_ids: list[str] | None = None,
        model_variant_ids: list[str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> ExecutionPlan:
        """Build execution plan for experiment.

        Args:
            experiment_name: Human-readable experiment name
            run_ids: Optional list of specific runs (default: all pending)
            question_ids: Optional list of specific question IDs to filter
            model_variant_ids: Optional list of specific variant IDs to filter
            retry_policy: Optional retry policy override (default: RetryPolicy())

        Returns:
            Immutable ExecutionPlan

        Raises:
            PlannerValidationError: If experiment has no models/snapshots or doesn't exist
        """
        # Validate experiment exists and get its data
        experiment_row = self._validate_experiment_exists(experiment_name)

        # Validate experiment has models
        variants = self._validate_has_models(experiment_row["experiment_id"])

        # Validate experiment has snapshots
        snapshots = self._validate_has_snapshots(experiment_row["experiment_id"])

        # Apply filters
        if model_variant_ids:
            variants = [v for v in variants if v["variant_id"] in model_variant_ids]

        if question_ids:
            snapshots = [s for s in snapshots if s["question_id"] in question_ids]

        # Get runs to execute
        runs = self._get_runs(experiment_row["experiment_id"], run_ids)

        # Build plan runs
        plan_runs = []
        for run_row in runs:
            plan_run = self._build_plan_run(
                run_row=run_row,
                experiment_row=experiment_row,
                variants=variants,
                snapshots=snapshots,
                retry_policy=retry_policy or RetryPolicy(),
            )
            plan_runs.append(plan_run)

        # Create execution plan
        plan = ExecutionPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(),
            experiment_id=experiment_row["experiment_id"],
            runs=plan_runs,
        )

        return plan

    def _validate_experiment_exists(self, name: str) -> sqlite3.Row:
        """Validate experiment exists and return its data.

        Args:
            name: Human-readable experiment name

        Returns:
            Experiment row from database

        Raises:
            PlannerValidationError: If experiment not found
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM experiments
            WHERE name = ? AND is_active = TRUE
            """,
            (name,),
        )
        row = cursor.fetchone()

        if row is None:
            raise PlannerValidationError(
                f"Experiment not found: {name}. "
                "Create the experiment first with --create-experiment."
            )

        return row

    def _validate_has_models(self, experiment_id: str) -> list[sqlite3.Row]:
        """Validate experiment has models and return them.

        Args:
            experiment_id: Experiment identifier

        Returns:
            List of active model variant rows

        Raises:
            PlannerValidationError: If experiment has no models
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM model_variants
            WHERE experiment_id = ? AND is_active = TRUE
            """,
            (experiment_id,),
        )
        variants = cursor.fetchall()

        if not variants:
            raise PlannerValidationError(
                f"Experiment has no models. Add models before creating runs. "
                f"Use: --experiment {experiment_id} --add-model <model_id>"
            )

        return variants

    def _validate_has_snapshots(self, experiment_id: str) -> list[sqlite3.Row]:
        """Validate experiment has snapshots and return them.

        Args:
            experiment_id: Experiment identifier

        Returns:
            List of active snapshot rows

        Raises:
            PlannerValidationError: If experiment has no snapshots
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM question_snapshots
            WHERE experiment_id = ? AND is_active = TRUE
            """,
            (experiment_id,),
        )
        snapshots = cursor.fetchall()

        if not snapshots:
            raise PlannerValidationError(
                f"Experiment has no questions. Add questions before creating runs. "
                f"Use: --experiment {experiment_id} --add-questions <spec>"
            )

        return snapshots

    def _get_runs(
        self,
        experiment_id: str,
        run_ids: list[str] | None = None,
    ) -> list[sqlite3.Row]:
        """Get runs for experiment.

        Args:
            experiment_id: Experiment identifier
            run_ids: Optional list of specific run IDs to include

        Returns:
            List of run rows matching the criteria
        """
        if run_ids is not None:
            # Filter to specific runs
            placeholders = ",".join("?" for _ in run_ids)
            cursor = self.conn.execute(
                f"""
                SELECT * FROM runs
                WHERE experiment_id = ? AND run_id IN ({placeholders})
                """,
                [experiment_id] + list(run_ids),
            )
        else:
            # Get all pending runs
            cursor = self.conn.execute(
                """
                SELECT * FROM runs
                WHERE experiment_id = ? AND status = 'pending'
                """,
                (experiment_id,),
            )

        return cursor.fetchall()

    def _build_plan_run(
        self,
        run_row: sqlite3.Row,
        experiment_row: sqlite3.Row,
        variants: list[sqlite3.Row],
        snapshots: list[sqlite3.Row],
        retry_policy: RetryPolicy,
    ) -> PlanRun:
        """Build a single PlanRun with all items.

        Args:
            run_row: Run database row
            experiment_row: Experiment database row
            variants: List of variant rows
            snapshots: List of snapshot rows
            retry_policy: Retry policy for this run

        Returns:
            Immutable PlanRun with all items
        """
        # Resolve effective prompts (run overrides experiment)
        prompts_effective = self._resolve_prompts_effective(experiment_row, run_row)

        # Resolve effective seed (run overrides experiment)
        seed_effective = self._resolve_seed_effective(experiment_row, run_row)

        # Build plan variants
        plan_variants = [
            PlanVariant(
                variant_id=variant["variant_id"],
                model_id=variant["model_id"],
                model_config_effective=self._build_model_config(variant),
            )
            for variant in variants
        ]

        # Build items (deduplicated per run by construction)
        items = self._build_items(run_row, variants, snapshots)

        # Create plan run with specified retry policy
        plan_run = PlanRun(
            run_id=run_row["run_id"],
            seed_effective=seed_effective,
            prompts_effective=prompts_effective,
            retry_policy=retry_policy,
            variants=plan_variants,
            items=items,
        )

        return plan_run

    def _resolve_prompts_effective(
        self,
        experiment_row: sqlite3.Row,
        run_row: sqlite3.Row,
    ) -> Prompts:
        """Resolve effective prompts for run.

        Run-level prompts override experiment-level prompts.
        In the minimal schema, runs don't have prompts, so we use
        experiment prompts.

        Args:
            experiment_row: Experiment database row
            run_row: Run database row

        Returns:
            Resolved Prompts
        """
        # For minimal schema: use experiment prompts
        # Future: check if run has custom prompts, else use experiment
        return Prompts(
            system=experiment_row["system_prompt"],
            user=experiment_row["user_prompt"],
        )

    def _resolve_seed_effective(
        self,
        experiment_row: sqlite3.Row,
        run_row: sqlite3.Row,
    ) -> int | None:
        """Resolve effective seed for run.

        Run-level seed overrides experiment-level seed.

        Args:
            experiment_row: Experiment database row
            run_row: Run database row

        Returns:
            Effective seed (None = no randomization)
        """
        # Run seed takes precedence
        return run_row["seed"]

    def _build_model_config(self, variant_row: sqlite3.Row) -> ModelConfig:
        """Build ModelConfig from variant row.

        Args:
            variant_row: Model variant database row

        Returns:
            ModelConfig with resolved values
        """
        # For minimal schema: use defaults
        # Access columns directly (sqlite3.Row supports dict-style access)
        return ModelConfig(
            temperature=None,
            top_p=None,
            max_output_tokens=None,
            enable_vision=bool(variant_row["vision_enabled"]) if "vision_enabled" in variant_row.keys() else False,
            structured_output=bool(variant_row["structured_output"]) if "structured_output" in variant_row.keys() else False,
            reasoning_mode=variant_row["reasoning_mode"] if "reasoning_mode" in variant_row.keys() else "off",
            reasoning_effort=variant_row["reasoning_effort"] if "reasoning_effort" in variant_row.keys() else None,
        )

    def _build_items(
        self,
        run_row: sqlite3.Row,
        variants: list[sqlite3.Row],
        snapshots: list[sqlite3.Row],
    ) -> list[PlanItem]:
        """Build execution items for run.

        Creates one item per (variant, snapshot) combination.
        Items are naturally deduplicated by construction.

        Args:
            run_row: Run database row
            variants: List of variant rows
            snapshots: List of snapshot rows

        Returns:
            List of PlanItem (one per variant × snapshot)
        """
        items = []

        for variant in variants:
            for snapshot in snapshots:
                # Parse question payload
                payload_data = json.loads(snapshot["question_payload"])

                question_payload = QuestionPayload(
                    stem=payload_data["stem"],
                    options=payload_data["options"],
                    answer_key=payload_data["answer_key"],
                )

                # Generate unique item ID
                item_id = (
                    f"{run_row['run_id']}::{variant['variant_id']}::"
                    f"{snapshot['snapshot_id']}::it-{len(items) + 1}"
                )

                item = PlanItem(
                    item_id=item_id,
                    run_id=run_row["run_id"],
                    variant_id=variant["variant_id"],
                    snapshot_id=snapshot["snapshot_id"],
                    question_id=snapshot["question_id"],
                    question_payload=question_payload,
                )

                items.append(item)

        return items
