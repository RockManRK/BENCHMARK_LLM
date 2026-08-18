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

        ACCEPTED ARCHITECTURAL RISK (ADR: adr-execution-pipeline.md, Decision 2):
        The Planner takes a raw sqlite3.Connection and executes SQL directly. This
        couples domain logic to SQLite. This is an intentional trade-off documented
        in the ADR: cost protection (excluding already-executed items) belongs at
        plan-build time, requiring DB access. Mitigation would require a read-only
        query abstraction layer (e.g., ReadOnlyQueryGateway), which is deferred
        until database portability becomes a real requirement.

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

        # Validate provider lock if enabled
        self._validate_provider_lock(experiment_row["experiment_id"], variants)

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

    def _validate_provider_lock(self, experiment_id: str, variants: list[sqlite3.Row]) -> None:
        """Validate that all variants have PROVIDER resolved if lock is enabled.

        When PROVIDER_LOCK is True in experiment config, all model variants must have
        their PROVIDER field set. This ensures provider locking can be enforced during
        execution without requiring fallback resolution.

        Args:
            experiment_id: Experiment identifier
            variants: List of model variant rows

        Raises:
            PlannerValidationError: If PROVIDER_LOCK is True and any variant has PROVIDER=null
        """
        import json

        # Get experiment config
        cursor = self.conn.execute(
            "SELECT config_json FROM experiments WHERE experiment_id = ?",
            (experiment_id,)
        )
        row = cursor.fetchone()
        if not row:
            return  # Experiment doesn't exist — caught by other validation

        exp_config = json.loads(row["config_json"]) if row["config_json"] else {}
        provider_lock = exp_config.get("PROVIDER_LOCK", False)

        if not provider_lock:
            return  # Lock not enabled — no validation needed

        # Check each variant
        unresolved = []
        for variant in variants:
            config = json.loads(variant["config"]) if variant["config"] else {}
            if config.get("PROVIDER") is None:
                unresolved.append({
                    "variant_id": variant["variant_id"],
                    "model_id": variant["model_id"],
                })

        if unresolved:
            variant_info = ", ".join(f"{u['model_id']} ({u['variant_id']})" for u in unresolved)
            error_msg = (
                f"ERROR: Provider lock is enabled for this experiment, "
                f"but {len(unresolved)} model variant(s) have PROVIDER=null:\n"
                f"  {variant_info}\n"
                f"\nRun: bcllm --experiment <name> --resolve-providers\n"
                f"Aborting execution."
            )
            self._logger.error(f"PLAN_VALIDATION_ERROR | experiment={experiment_id} | error={error_msg}")
            raise PlannerValidationError(error_msg)

    def _get_variant_provider(self, variant_row: sqlite3.Row) -> str | None:
        """Get provider from variant config.

        Args:
            variant_row: Model variant database row

        Returns:
            Provider slug string or None if not set
        """
        import json
        config_str = variant_row["config"] if "config" in variant_row.keys() else "{}"
        config = json.loads(config_str) if config_str else {}
        return config.get("PROVIDER")

    def _get_runs(
        self,
        experiment_id: str,
        run_ids: list[str] | None = None,
    ) -> list[sqlite3.Row]:
        """Get runs for experiment.

        This is the execution path only (called from create_plan()) — never
        used by --run <id>'s show/display handler (that goes through
        RunRepository.get_by_id() directly) — so a 'removed' run must never
        be returned here, in either branch. Bug fixed 2026-08-17: the
        run_ids branch (bcllm --execute --run <id>) previously had NO
        status filter at all, so explicitly targeting a removed run's ID
        would include it in the plan, execute it, and let RunFinalizer
        silently overwrite status='removed' with a computed execution
        outcome — reactivating a run the user had just removed. Caught by
        an essence-guardian review; the original --remove-run fix had only
        verified the *default* (run_ids=None) path excluded 'removed', not
        this explicit-target path. See docs/status/known-issues.md.

        Args:
            experiment_id: Experiment identifier
            run_ids: Optional list of specific run IDs to include

        Returns:
            List of run rows matching the criteria (never includes a
            'removed' run, in either branch).
        """
        if run_ids is not None:
            # Filter to specific runs, still excluding 'removed'
            placeholders = ",".join("?" for _ in run_ids)
            cursor = self.conn.execute(
                f"""
                SELECT * FROM runs
                WHERE experiment_id = ? AND run_id IN ({placeholders})
                  AND status != 'removed'
                """,
                [experiment_id] + list(run_ids),
            )
        else:
            # Get all runs that can be executed (pending or recoverable failed states)
            # Data integrity is ensured by UNIQUE constraint on responses table
            cursor = self.conn.execute(
                """
                SELECT * FROM runs
                WHERE experiment_id = ? AND status IN ('pending', 'failed', 'partial_failed')
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
                resolved_provider=self._get_variant_provider(variant),
            )
            for variant in variants
        ]

        # Get already-executed items to exclude (idempotency filter)
        executed_items = self._get_executed_items(run_row["run_id"])

        # Build items (deduplicated per run by construction, excluding already-executed)
        items = self._build_items(run_row, variants, snapshots, executed_items)

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

    def _get_executed_items(self, run_id: str) -> set[tuple[str, str]]:
        """Query DB for already-executed items in a run.

        Returns a set of (variant_id, snapshot_id) tuples where raw_response IS NOT NULL,
        meaning the item has actual response data and should NOT be re-executed.

        Items that only have errors (transient failures) are NOT excluded,
        so they can be retried.

        Args:
            run_id: Run identifier to query for

        Returns:
            Set of (variant_id, snapshot_id) tuples to exclude from the plan
        """
        cursor = self.conn.execute(
            """
            SELECT variant_id, snapshot_id FROM responses
            WHERE run_id = ? AND raw_response IS NOT NULL
            """,
            (run_id,),
        )
        return {(row["variant_id"], row["snapshot_id"]) for row in cursor.fetchall()}

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

        CONTRATO ARQUITETURAL DE SEED:

        Este método é a ÚNICA fonte de verdade para normalização de seed.
        Após este método, seed_effective é GARANTIDAMENTE int | None.

        Por que a normalização acontece aqui:
        - O planner é o ponto onde configs do banco são lidos e resolvidos
        - Configs podem conter strings ("OFF", "NULL", etc.) ou ints
        - Após resolução, todas as camadas downstream assumem contrato limpo
        - Outras camadas NÃO devem repetir normalização

        Regras de conversão:
        - "OFF", "NULL", "NONE", "" → None (randomização DESLIGADA)
        - strings numéricas ("42") → int (randomização LIGADA)
        - int → int (mantido)
        - qualquer valor inválido → None

        Este é um contrato arquitetural, não uma convenção informal.

        Args:
            experiment_row: Experiment database row
            run_row: Run database row (has config column with RUN_RESPONSES_SEED)

        Returns:
            Effective seed (int | None only — never string or other type)
        """
        import json

        # Parse run config
        run_config_str = run_row["config"] if "config" in run_row.keys() else "{}"
        run_config = json.loads(run_config_str) if run_config_str else {}

        # Run seed takes precedence
        run_seed = run_config.get("RUN_RESPONSES_SEED")
        if run_seed is not None:
            return self._normalize_seed_value(run_seed)

        # Fallback to experiment config
        exp_config_str = experiment_row["config_json"] if "config_json" in experiment_row.keys() else "{}"
        exp_config = json.loads(exp_config_str) if exp_config_str else {}
        return self._normalize_seed_value(exp_config.get("RUN_RESPONSES_SEED"))

    def _normalize_seed_value(self, seed_value) -> int | None:
        """Normalize seed value to int | None.

        This is the ONLY method that handles string seeds.
        All other code assumes seed is already int | None.

        Args:
            seed_value: Raw seed value from config (may be str, int, or None)

        Returns:
            int if valid seed, None if disabled or invalid.
        """
        if seed_value is None:
            return None

        if isinstance(seed_value, int):
            return seed_value

        if isinstance(seed_value, str):
            normalized = seed_value.strip().upper()
            if normalized in ("OFF", "NULL", "NONE", ""):
                return None
            try:
                return int(seed_value)
            except ValueError:
                return None

        # Any other type → disable randomization
        return None

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
            - base_url: str (variant's resolved API endpoint)
        """
        import json
        
        # Parse config column
        config_str = variant_row["config"] if "config" in variant_row.keys() else "{}"
        config = json.loads(config_str) if config_str else {}

        # Extract values from config (all optional, None = model default)
        # Keys must match those generated by ConfigResolver.build_config_dict()
        reasoning_effort = config.get("MODEL_REASONING_EFFORT")
        has_reasoning = reasoning_effort is not None and reasoning_effort != "none"

        return ModelConfig(
            temperature=config.get("MODEL_TEMPERATURE"),
            top_p=config.get("MODEL_TOP_P"),
            top_k=config.get("MODEL_TOP_K"),
            repeat_penalty=config.get("MODEL_REPEAT_PENALTY"),
            max_output_tokens=config.get("MODEL_MAX_TOKENS_TOTAL"),
            max_reasoning_tokens=config.get("MODEL_MAX_TOKENS_REASONING"),
            reasoning_effort=reasoning_effort if has_reasoning else None,
            enable_vision=config.get("MODEL_VISION", False),
            structured_output=config.get("STRUCTURED_OUTPUTS", False),
            reasoning_mode="effort" if has_reasoning else "off",
            base_url=config.get("BASE_URL"),
        )

    def _build_items(
        self,
        run_row: sqlite3.Row,
        variants: list[sqlite3.Row],
        snapshots: list[sqlite3.Row],
        executed_items: set[tuple[str, str]] | None = None,
    ) -> list[PlanItem]:
        """Build execution items for run.

        Creates one item per (variant, snapshot) combination.
        Items are naturally deduplicated by construction.
        Already-executed items are excluded for idempotent re-execution.

        Args:
            run_row: Run database row
            variants: List of variant rows
            snapshots: List of snapshot rows
            executed_items: Set of (variant_id, snapshot_id) tuples to exclude
                           (items that already have raw_response in DB)

        Returns:
            List of PlanItem (one per variant × snapshot, excluding executed)
        """
        items = []

        # Ensure executed_items is a set (empty if not provided)
        exclude = executed_items if executed_items is not None else set()

        for variant in variants:
            for snapshot in snapshots:
                # Skip already-executed items (idempotency filter)
                variant_id = variant["variant_id"]
                snapshot_id = snapshot["snapshot_id"]
                if (variant_id, snapshot_id) in exclude:
                    self._logger.debug(
                        f"PLAN_SKIP_EXECUTED | run={run_row['run_id']} | "
                        f"variant={variant_id} | snapshot={snapshot_id}"
                    )
                    continue

                # Parse question payload
                payload_data = json.loads(snapshot["question_payload"])

                # Extract image fields from existing snapshot data
                # has_image comes from meta.has_image
                has_image = payload_data.get("meta", {}).get("has_image", False)

                # image_path comes from assets array (first asset if has_image is true)
                image_path = None
                if has_image and payload_data.get("assets"):
                    image_path = payload_data["assets"][0]

                question_payload = QuestionPayload(
                    stem=payload_data["stem"],
                    options=payload_data["options"],
                    answer_key=payload_data["answer_key"],
                    has_image=has_image,
                    image_path=image_path,
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
