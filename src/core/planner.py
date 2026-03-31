"""Planner — Builds immutable ExecutionPlan from database state.

The Planner is a read-only component that constructs ExecutionPlan
instances from the database. It validates preconditions and resolves
effective values, but never modifies database state.

Key responsibilities:
- Validate experiment exists and has models/snapshots
- Read experiment, runs, variants, snapshots from DB
- Resolve effective prompts (run.config overrides experiment.config)
- Resolve effective seed (run.config overrides experiment.config)
- Build ExecutionPlan with deduplicated items per run
- Apply run ID filters when specified
- Apply question ID filters when specified
- Apply model variant ID filters when specified
- Apply retry policy when specified

Database schema (TO-BE):
- experiments: config_json (contains SYSTEM_PROMPT, USER_PROMPT, etc.)
- model_variants: config (JSON with MODEL_* keys)
- question_snapshots: question_payload (JSON)
- runs: config (JSON with RUN_RESPONSES_SEED, SYSTEM_PROMPT, USER_PROMPT)
- responses: execution results
- errors: error records

The Planner is READ-ONLY:
- No database writes
- No state inference or repair
- Explicit validation only
- All execution decisions explicit in ExecutionPlan

Prompt resolution chain:
1. Run config (RUN_RESPONSES_SEED, SYSTEM_PROMPT, USER_PROMPT)
2. Experiment config (fallback)

Seed resolution chain:
1. Run config.RUN_RESPONSES_SEED
2. Experiment config.RUN_RESPONSES_SEED (fallback)
"""

import sqlite3
import json
import uuid
from datetime import datetime
from logging import Logger
from typing import Any, Optional

from src.core.execution_plan import (
    ExecutionPlan,
    PlanRun,
    PlanItem,
    PlanVariant,
    Prompts,
    RetryPolicy,
    ModelConfig,
    QuestionPayload,
)
from src.utils.logging_config import get_logger


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

    Configuration resolution:
    - Prompts: run.config.SYSTEM_PROMPT/USER_PROMPT > experiment.config
    - Seed: run.config.RUN_RESPONSES_SEED > experiment.config
    - Model config: variant.config (MODEL_* keys)

    Attributes:
        conn: Database connection (read-only usage)

    Example:
        conn = sqlite3.connect("benchmark.db")
        planner = Planner(conn)
        plan = planner.build_plan("my-experiment")
        # plan is an immutable ExecutionPlan
    """

    def __init__(self, db_connection: sqlite3.Connection, logger: Optional[Logger] = None) -> None:
        """Initialize with database connection.

        Args:
            db_connection: SQLite database connection (used read-only)
            logger: Optional logger instance. If not provided, uses get_logger('core.planner').
        """
        self.conn = db_connection
        self._logger = logger or get_logger('core.planner')

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

        Notes:
            - Prompts resolved from: run.config > experiment.config
            - Seed resolved from: run.config > experiment.config
            - Model config from: variant.config (MODEL_* keys)
        """
        # Log plan build start
        self._logger.info(f"PLAN_BUILD_START | experiment={experiment_name}")

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

        # Calculate total items
        total_items = sum(len(plan_run.items) for plan_run in plan_runs)

        # Log loaded plan summary
        self._logger.info(
            f"PLAN_LOADED | experiment={experiment_name} | models={len(variants)} | questions={len(snapshots)} | runs={len(plan_runs)}"
        )

        # Create execution plan
        plan = ExecutionPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(),
            experiment_id=experiment_row["experiment_id"],
            runs=plan_runs,
        )

        # Log plan build complete
        self._logger.info(f"PLAN_BUILD_COMPLETE | experiment={experiment_name} | total_items={total_items}")

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
            WHERE name = ?
            """,
            (name,),
        )
        row = cursor.fetchone()

        if row is None:
            error_msg = f"Experiment not found: {name}. Create the experiment first with --create-experiment."
            self._logger.error(f"PLAN_VALIDATION_ERROR | experiment={name} | error={error_msg}")
            raise PlannerValidationError(error_msg)

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
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        )
        variants = cursor.fetchall()

        if not variants:
            error_msg = f"Experiment has no models. Add models before creating runs. Use: --experiment {experiment_id} --add-model <model_id>"
            self._logger.error(f"PLAN_VALIDATION_ERROR | experiment={experiment_id} | error={error_msg}")
            raise PlannerValidationError(error_msg)

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
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        )
        snapshots = cursor.fetchall()

        if not snapshots:
            error_msg = f"Experiment has no questions. Add questions before creating runs. Use: --experiment {experiment_id} --add-questions <spec>"
            self._logger.error(f"PLAN_VALIDATION_ERROR | experiment={experiment_id} | error={error_msg}")
            raise PlannerValidationError(error_msg)

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
        
        Resolution chain:
        1. Run config (RUN_RESPONSES_SEED, SYSTEM_PROMPT, USER_PROMPT)
        2. Experiment config_json (fallback)
        
        Prompts are stored in JSON columns as:
        - SYSTEM_PROMPT: str | None
        - USER_PROMPT: str

        Args:
            experiment_row: Experiment database row (has config_json)
            run_row: Run database row (has config column with prompts)

        Returns:
            Resolved Prompts
        """
        import json
        
        # Parse run config
        run_config_str = run_row["config"] if "config" in run_row.keys() else "{}"
        run_config = json.loads(run_config_str) if run_config_str else {}
        
        # Parse experiment config_json
        exp_config_str = experiment_row["config_json"] if "config_json" in experiment_row.keys() else "{}"
        exp_config = json.loads(exp_config_str) if exp_config_str else {}
        
        # Run-level prompts override experiment-level
        system_prompt = run_config.get("SYSTEM_PROMPT") or exp_config.get("SYSTEM_PROMPT")
        user_prompt = run_config.get("USER_PROMPT") or exp_config.get("USER_PROMPT")
        
        return Prompts(
            system=system_prompt,
            user=user_prompt,
        )

    def _resolve_seed_effective(
        self,
        experiment_row: sqlite3.Row,
        run_row: sqlite3.Row,
    ) -> int | None:
        """Resolve effective seed for run.

        Run-level seed overrides experiment-level seed.
        
        Resolution chain:
        1. Run config.RUN_RESPONSES_SEED
        2. Experiment config.RUN_RESPONSES_SEED (fallback)
        
        Seed is stored in run.config JSON column as RUN_RESPONSES_SEED.

        Args:
            experiment_row: Experiment database row
            run_row: Run database row (has config column with RUN_RESPONSES_SEED)

        Returns:
            Effective seed (None = no randomization)
        """
        import json
        
        # Parse run config
        run_config_str = run_row["config"] if "config" in run_row.keys() else "{}"
        run_config = json.loads(run_config_str) if run_config_str else {}
        
        # Run seed takes precedence
        run_seed = run_config.get("RUN_RESPONSES_SEED")
        if run_seed is not None:
            return run_seed
        
        # Fallback to experiment config
        exp_config_str = experiment_row["config_json"] if "config_json" in experiment_row.keys() else "{}"
        exp_config = json.loads(exp_config_str) if exp_config_str else {}
        return exp_config.get("RUN_RESPONSES_SEED")

    def _build_model_config(self, variant_row: sqlite3.Row) -> ModelConfig:
        """Build ModelConfig from variant row.

        Parses config column (JSON string) to extract execution configuration.
        Config is the source of truth — deprecated columns are ignored.

        Args:
            variant_row: Model variant database row (must include 'config' column)

        Returns:
            ModelConfig with resolved values from config column

        Config keys (all optional):
            - reasoning_effort: 'none', 'minimal', 'low', 'medium', 'high', 'xhigh'
            - vision: true/false
            - structured: true/false
            - temperature: float
            - top_p: float
            - top_k: int
            - max_output_tokens: int
            - reasoning_tokens: int
        """
        import json
        
        # Parse config column
        config_str = variant_row["config"] if "config" in variant_row.keys() else "{}"
        config = json.loads(config_str) if config_str else {}
        
        # Extract values from config (all optional, None = model default)
        return ModelConfig(
            temperature=config.get("temperature"),
            top_p=config.get("top_p"),
            max_output_tokens=config.get("max_output_tokens"),
            enable_vision=config.get("vision", False),
            structured_output=config.get("structured", False),
            reasoning_mode="effort" if config.get("reasoning_effort") and config["reasoning_effort"] != "none" else "off",
            reasoning_effort=config.get("reasoning_effort") if config.get("reasoning_effort") and config["reasoning_effort"] != "none" else None,
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
                    question_id=snapshot["json_question_id"],
                    question_payload=question_payload,
                )

                items.append(item)

        return items
