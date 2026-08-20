"""Tests for add-models-to-run functionality.

This module tests the ability to add models to existing runs
and the detection of pending questions.
"""

import pytest
from src.core.variant_config import VariantConfig
from src.db.models import Run, RunModel
from src.db.repository import RunModelRepository


class TestRunModelRepository:
    """Test RunModelRepository CRUD operations."""

    def test_create_run_model(self, db_manager) -> None:
        """Test creating a run-model association."""
        from src.db.repository import RunModelRepository, ModelVariantRepository, ModelRepository, RunRepository
        from src.db.models import ModelVariant, Model, Run

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-001", status="pending", is_dev=True))

        # Create base model first (FK constraint) - use unique provider/name
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-001", provider="test", model_name="Test Model 001"))

        # Create variant
        variant_repo = ModelVariantRepository(db_manager)
        variant = ModelVariant(
            variant_id="var-abc123",
            model_id="test-model-001",
            variant_signature="test-model-001::reasoning=unspecified::vision=false::structured=false",
        )
        variant_repo.create(variant)

        repo = RunModelRepository(db_manager)
        run_model = RunModel(
            run_id="run-test-001",
            variant_id="var-abc123",
            status="pending",
        )

        created = repo.create(run_model)

        assert created.run_id == "run-test-001"
        assert created.variant_id == "var-abc123"
        assert created.status == "pending"
    
    def test_get_by_run(self, db_manager) -> None:
        """Test retrieving all models for a run."""
        from src.db.repository import RunModelRepository, ModelVariantRepository, ModelRepository, RunRepository
        from src.db.models import ModelVariant, Model, Run

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-002", status="pending", is_dev=True))

        # Create base models first (need unique provider/name for each)
        model_repo = ModelRepository(db_manager)
        for i in range(1, 4):
            model_repo.create(Model(model_id=f"test-model-{i:03d}", provider=f"test{i}", model_name=f"Test Model {i}"))

        # Create variants first
        variant_repo = ModelVariantRepository(db_manager)
        for i, vid in enumerate(["var-1", "var-2", "var-3"], start=1):
            variant_repo.create(ModelVariant(
                variant_id=vid,
                model_id=f"test-model-{i:03d}",
                variant_signature=f"test-model-{i:03d}::reasoning=unspecified::vision=false::structured=false",
            ))

        repo = RunModelRepository(db_manager)

        # Create multiple run-model associations
        repo.create(RunModel(run_id="run-test-002", variant_id="var-1", status="pending"))
        repo.create(RunModel(run_id="run-test-002", variant_id="var-2", status="pending"))
        repo.create(RunModel(run_id="run-test-002", variant_id="var-3", status="completed"))

        models = repo.get_by_run("run-test-002")

        assert len(models) == 3
        assert {m.variant_id for m in models} == {"var-1", "var-2", "var-3"}
    
    def test_get_by_run_and_variant(self, db_manager) -> None:
        """Test retrieving a specific run-model association."""
        from src.db.repository import RunModelRepository, ModelVariantRepository, ModelRepository, RunRepository
        from src.db.models import ModelVariant, Model, Run

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-003", status="pending", is_dev=True))

        # Create base model first
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-xyz", provider="testxyz", model_name="Test Model XYZ"))

        # Create variant first
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-xyz",
            model_id="test-model-xyz",
            variant_signature="test-model-xyz::reasoning=unspecified::vision=false::structured=false",
        ))

        repo = RunModelRepository(db_manager)
        repo.create(RunModel(run_id="run-test-003", variant_id="var-xyz", status="pending"))

        model = repo.get_by_run_and_variant("run-test-003", "var-xyz")

        assert model is not None
        assert model.run_id == "run-test-003"
        assert model.variant_id == "var-xyz"
        assert model.status == "pending"
    
    def test_get_by_run_and_variant_not_found(self, db_manager) -> None:
        """Test retrieving a non-existent run-model association."""
        from src.db.repository import RunModelRepository
        
        repo = RunModelRepository(db_manager)
        model = repo.get_by_run_and_variant("run-nonexistent", "var-nonexistent")
        
        assert model is None
    
    def test_update_status(self, db_manager) -> None:
        """Test updating run-model status."""
        from src.db.repository import RunModelRepository, ModelVariantRepository, ModelRepository, RunRepository
        from src.db.models import ModelVariant, Model, Run

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-004", status="pending", is_dev=True))

        # Create base model first
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-abc", provider="testabc", model_name="Test Model ABC"))

        # Create variant first
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-abc",
            model_id="test-model-abc",
            variant_signature="test-model-abc::reasoning=unspecified::vision=false::structured=false",
        ))

        repo = RunModelRepository(db_manager)
        repo.create(RunModel(run_id="run-test-004", variant_id="var-abc", status="pending"))

        # Update to pending
        success = repo.update_status("run-test-004", "var-abc", "pending")
        assert success is True

        model = repo.get_by_run_and_variant("run-test-004", "var-abc")
        assert model.status == "pending"

        # Update to completed (should set completed_at)
        success = repo.update_status("run-test-004", "var-abc", "completed")
        assert success is True

        model = repo.get_by_run_and_variant("run-test-004", "var-abc")
        assert model.status == "completed"
        assert model.completed_at is not None
    
    def test_delete_run_model(self, db_manager) -> None:
        """Test deleting a run-model association."""
        from src.db.repository import RunModelRepository, ModelVariantRepository, ModelRepository, RunRepository
        from src.db.models import ModelVariant, Model, Run

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-005", status="pending", is_dev=True))

        # Create base model first
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-del", provider="testdel", model_name="Test Model Del"))

        # Create variant first
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-del",
            model_id="test-model-del",
            variant_signature="test-model-del::reasoning=unspecified::vision=false::structured=false",
        ))

        repo = RunModelRepository(db_manager)
        repo.create(RunModel(run_id="run-test-005", variant_id="var-del", status="pending"))

        success = repo.delete("run-test-005", "var-del")
        assert success is True

        model = repo.get_by_run_and_variant("run-test-005", "var-del")
        assert model is None


class TestAddModelsToRun:
    """Test RunManager.add_models_to_run functionality."""

    def test_add_models_to_pending_run(self, db_manager, settings) -> None:
        """Test adding models to a run in 'pending' status."""
        from src.core.run_manager import RunManager
        from src.db.repository import RunRepository
        
        # Create a run
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-add", status="pending", is_dev=True)
        run_repo.create(run)
        
        # Add models
        run_manager = RunManager(db_manager, settings)
        run_manager.add_models_to_run("run-test-add", ["openai/gpt-4", "anthropic/claude-3"])
        
        # Verify models were added
        run_model_repo = RunModelRepository(db_manager)
        models = run_model_repo.get_by_run("run-test-add")
        
        assert len(models) == 2
        model_ids = {m.variant_id for m in models}
        assert len(model_ids) == 2  # Two different variants created
    
    def test_cannot_add_models_to_completed_run(self, db_manager, settings) -> None:
        """Test that adding models to a completed run raises error."""
        from src.core.run_manager import RunManager
        from src.db.repository import RunRepository
        
        # Create a completed run
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-completed", status="completed", is_dev=True)
        run_repo.create(run)
        
        # Try to add models
        run_manager = RunManager(db_manager, settings)
        
        with pytest.raises(ValueError, match="status is 'completed'"):
            run_manager.add_models_to_run("run-test-completed", ["openai/gpt-4"])
    
    def test_cannot_add_models_to_nonexistent_run(self, db_manager, settings) -> None:
        """Test that adding models to a non-existent run raises error."""
        from src.core.run_manager import RunManager
        
        run_manager = RunManager(db_manager, settings)
        
        with pytest.raises(ValueError, match="does not exist"):
            run_manager.add_models_to_run("run-nonexistent", ["openai/gpt-4"])
    
    def test_add_same_model_twice(self, db_manager, settings) -> None:
        """Test that adding the same model twice doesn't create duplicates."""
        from src.core.run_manager import RunManager
        from src.db.repository import RunRepository
        
        # Create a run
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-dup", status="pending", is_dev=True)
        run_repo.create(run)
        
        # Add same model twice
        run_manager = RunManager(db_manager, settings)
        run_manager.add_models_to_run("run-test-dup", ["openai/gpt-4"])
        run_manager.add_models_to_run("run-test-dup", ["openai/gpt-4"])
        
        # Verify only one association exists
        run_model_repo = RunModelRepository(db_manager)
        models = run_model_repo.get_by_run("run-test-dup")
        
        assert len(models) == 1


class TestGetPendingQuestions:
    """Test IterationExecutor.get_pending_questions functionality."""

    def test_get_pending_questions_all_new(self, db_manager) -> None:
        """Test getting pending questions when none are answered."""
        from src.core.iteration_executor import IterationExecutor
        from src.db.models import Question
        
        # Create test questions
        questions = [
            Question(question_id=f"Q{i:03d}", stem=f"Question {i}", options_json='{}')
            for i in range(1, 6)
        ]
        
        # Create executor
        executor = IterationExecutor(
            db_manager=db_manager,
            api_client=None,  # Not needed for this test
            randomizer=None,
            run_id="run-test-pending",
            model_id="test-model",
            iteration_number=1,
            experiment_id="exp-test",
        )
        
        # Generate variant_id
        config = VariantConfig()
        variant_id = config.build_variant_id("test-model")
        
        # Get pending (all should be pending)
        pending = executor.get_pending_questions(variant_id, questions, 1)
        
        assert len(pending) == 5
        assert {q.question_id for q in pending} == {"Q001", "Q002", "Q003", "Q004", "Q005"}
    
    def test_get_pending_questions_some_answered(self, db_manager) -> None:
        """Test getting pending questions when some are already answered."""
        from src.core.iteration_executor import IterationExecutor
        from src.db.models import Question, Response, Run, Model, ModelVariant, QuestionSnapshot, Experiment
        from src.db.repository import ResponseRepository, RunRepository, QuestionRepository
        from src.db.repository import ModelVariantRepository, ModelRepository, QuestionSnapshotRepository, ExperimentRepository

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-partial", status="pending", is_dev=True))

        # Create experiment (FK constraint for snapshots)
        exp_repo = ExperimentRepository(db_manager)
        exp_repo.create(Experiment(experiment_id="exp-test", name="Test Experiment", config_hash="test-hash", config_json='{}'))

        # Create test questions
        questions = [
            Question(question_id=f"Q{i:03d}", stem=f"Question {i}", options_json='{}')
            for i in range(1, 6)
        ]
        question_repo = QuestionRepository(db_manager)
        for q in questions:
            question_repo.create(q)

        # Create model and variant (FK constraint)
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model", provider="test", model_name="Test Model"))
        
        config = VariantConfig()
        variant_id = config.build_variant_id("test-model")
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id=variant_id,
            model_id="test-model",
            variant_signature="test-model::reasoning=unspecified::vision=false::structured=false",
        ))

        # Create question snapshots (FK constraint for responses)
        snapshot_repo = QuestionSnapshotRepository(db_manager)
        for i in range(1, 6):
            snapshot_repo.create_if_not_exists(
                experiment_id="exp-test",
                question_id=f"Q{i:03d}",
                question_json='{}',
            )

        # Create some responses
        response_repo = ResponseRepository(db_manager)
        for i in range(1, 4):  # Answer Q001, Q002, Q003
            response = Response(
                run_id="run-test-partial",
                snapshot_id=i,
                question_id=f"Q{i:03d}",
                variant_id=variant_id,
                iteration=1,
                selected_answer="A",
                is_correct=True,
                status="success",
            )
            response_repo.create(response)
        
        # Create executor
        executor = IterationExecutor(
            db_manager=db_manager,
            api_client=None,
            randomizer=None,
            run_id="run-test-partial",
            model_id="test-model",
            iteration_number=1,
            experiment_id="exp-test",
        )
        
        # Get pending (Q004, Q005 should be pending)
        pending = executor.get_pending_questions(variant_id, questions, 1)
        
        assert len(pending) == 2
        assert {q.question_id for q in pending} == {"Q004", "Q005"}
    
    def test_get_pending_questions_different_iteration(self, db_manager) -> None:
        """Test that questions answered in iteration 1 are still pending in iteration 2."""
        from src.core.iteration_executor import IterationExecutor
        from src.db.models import Question, Response, Run, Model, ModelVariant, QuestionSnapshot, Experiment
        from src.db.repository import ResponseRepository, RunRepository, QuestionRepository
        from src.db.repository import ModelVariantRepository, ModelRepository, QuestionSnapshotRepository, ExperimentRepository

        # Create run first (FK constraint)
        run_repo = RunRepository(db_manager)
        run_repo.create(Run(run_id="run-test-iter", status="pending", is_dev=True))

        # Create experiment (FK constraint for snapshots)
        exp_repo = ExperimentRepository(db_manager)
        exp_repo.create(Experiment(experiment_id="exp-test", name="Test Experiment", config_hash="test-hash", config_json='{}'))

        # Create test question
        questions = [Question(question_id="Q001", stem="Question 1", options_json='{}')]
        question_repo = QuestionRepository(db_manager)
        question_repo.create(questions[0])

        # Create model and variant (FK constraint)
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model", provider="test", model_name="Test Model"))
        
        config = VariantConfig()
        variant_id = config.build_variant_id("test-model")
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id=variant_id,
            model_id="test-model",
            variant_signature="test-model::reasoning=unspecified::vision=false::structured=false",
        ))

        # Create question snapshot (FK constraint for responses)
        snapshot_repo = QuestionSnapshotRepository(db_manager)
        snapshot_repo.create_if_not_exists(
            experiment_id="exp-test",
            question_id="Q001",
            question_json='{}',
        )

        # Create response for iteration 1
        response_repo = ResponseRepository(db_manager)
        response = Response(
            run_id="run-test-iter",
            snapshot_id=1,
            question_id="Q001",
            variant_id=variant_id,
            iteration=1,  # Answered in iteration 1
            selected_answer="A",
            is_correct=True,
            status="success",
        )
        response_repo.create(response)
        
        # Create executor for iteration 2
        executor = IterationExecutor(
            db_manager=db_manager,
            api_client=None,
            randomizer=None,
            run_id="run-test-iter",
            model_id="test-model",
            iteration_number=2,  # Iteration 2
            experiment_id="exp-test",
        )
        
        # Q001 should still be pending for iteration 2
        pending = executor.get_pending_questions(variant_id, questions, 2)

        assert len(pending) == 1
        assert pending[0].question_id == "Q001"


class TestReexecutionFilter:
    """Test re-execution filter for models based on status."""

    def test_reexecution_skips_completed_models(self, db_manager, settings, mocker) -> None:
        """Garantir que modelos completados NÃO são reexecutados."""
        from src.core.run_manager import RunManager
        from src.db.repository import RunRepository, RunModelRepository, ModelVariantRepository, ModelRepository
        from src.db.models import Run, ModelVariant, Model
        from src.main import BenchmarkRunner
        from argparse import Namespace

        # 1. Criar run com 2 modelos
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-reexec", status="pending", is_dev=True)
        run_repo.create(run)

        # Create base models first (need unique provider/name for each)
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-1", provider="test1", model_name="Test Model 1"))
        model_repo.create(Model(model_id="test-model-2", provider="test2", model_name="Test Model 2"))
        model_repo.create(Model(model_id="test-model-3", provider="test3", model_name="Test Model 3"))

        # Create variants
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-1",
            model_id="test-model-1",
            variant_signature="test-model-1::reasoning=unspecified::vision=false::structured=false",
        ))
        variant_repo.create(ModelVariant(
            variant_id="var-2",
            model_id="test-model-2",
            variant_signature="test-model-2::reasoning=unspecified::vision=false::structured=false",
        ))

        # Add models to run
        run_model_repo = RunModelRepository(db_manager)
        run_model_repo.create(RunModel(run_id="run-test-reexec", variant_id="var-1", status="pending"))
        run_model_repo.create(RunModel(run_id="run-test-reexec", variant_id="var-2", status="pending"))

        # 2. Simular que ambos foram completados (atualizar status)
        run_model_repo.update_status("run-test-reexec", "var-1", "completed")
        run_model_repo.update_status("run-test-reexec", "var-2", "completed")

        # 3. Adicionar 1 modelo novo
        variant_repo.create(ModelVariant(
            variant_id="var-3",
            model_id="test-model-3",
            variant_signature="test-model-3::reasoning=unspecified::vision=false::structured=false",
        ))
        
        run_model_repo.create(RunModel(run_id="run-test-reexec", variant_id="var-3", status="pending"))

        # 4. Criar BenchmarkRunner com --run-id
        args = Namespace(
            run_id="run-test-reexec",
            models=None,  # --models não deve ser usado
            iterations=1,
            questions=None,
            seed=None,
            vary_seed=False,
            test_mode=False,
            dry_run=False,
            reasoning_effort=None,
            reasoning_tokens=None,
            reasoning_exclude=None,
            reasoning_mode=None,
            enable_vision=False,
            enable_structured=False,
            temperature=None,
            max_tokens=None,
            top_p=None,
            top_k=None,
            repeat_penalty=None,
            execution_mode="dev",
            experiment_name=None,
            where=[],
            exclude=[],
        )

        runner = BenchmarkRunner(args)
        runner.db_manager = db_manager
        runner.settings = settings

        # 5. Verificar que apenas modelo novo foi executado (log de skip)
        # Mock logger to capture skip messages
        import logging
        logger = logging.getLogger("src.main")
        
        # Load models from run_models
        run_models = run_model_repo.get_by_run("run-test-reexec")
        models_to_execute = [rm for rm in run_models if rm.status in ('pending',)]
        skipped_models = [rm for rm in run_models if rm.status in ('completed', 'removed')]

        # 6. Verificações
        assert len(models_to_execute) == 1, "Apenas 1 modelo pendente deve ser executado"
        assert models_to_execute[0].variant_id == "var-3", "Apenas o modelo novo deve ser executado"
        assert len(skipped_models) == 2, "2 modelos completados devem ser skipados"
        assert {rm.variant_id for rm in skipped_models} == {"var-1", "var-2"}

    def test_run_id_ignores_cli_models(self, db_manager, settings) -> None:
        """Garantir que --run-id ignora --models da CLI."""
        from src.core.run_manager import RunManager
        from src.db.repository import RunRepository, RunModelRepository, ModelVariantRepository, ModelRepository
        from src.db.models import Run, ModelVariant, Model
        from src.main import BenchmarkRunner
        from argparse import Namespace

        # 1. Criar run com modelos [A, B]
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-ignore", status="pending", is_dev=True)
        run_repo.create(run)

        # Create base models (need unique provider/name for each)
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-a", provider="testa", model_name="Test Model A"))
        model_repo.create(Model(model_id="test-model-b", provider="testb", model_name="Test Model B"))
        model_repo.create(Model(model_id="test-model-c", provider="testc", model_name="Test Model C"))

        # Create variants for A, B
        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-a",
            model_id="test-model-a",
            variant_signature="test-model-a::reasoning=unspecified::vision=false::structured=false",
        ))
        variant_repo.create(ModelVariant(
            variant_id="var-b",
            model_id="test-model-b",
            variant_signature="test-model-b::reasoning=unspecified::vision=false::structured=false",
        ))

        run_model_repo = RunModelRepository(db_manager)
        run_model_repo.create(RunModel(run_id="run-test-ignore", variant_id="var-a", status="pending"))
        run_model_repo.create(RunModel(run_id="run-test-ignore", variant_id="var-b", status="pending"))

        # 2. Adicionar modelo [C]
        variant_repo.create(ModelVariant(
            variant_id="var-c",
            model_id="test-model-c",
            variant_signature="test-model-c::reasoning=unspecified::vision=false::structured=false",
        ))
        run_model_repo.create(RunModel(run_id="run-test-ignore", variant_id="var-c", status="pending"))

        # 3. Executar com --run-id X --models D (D não existe no run)
        args = Namespace(
            run_id="run-test-ignore",
            models=["model-d"],  # Este deve ser IGNORADO
            iterations=1,
            questions=None,
            seed=None,
            vary_seed=False,
            test_mode=False,
            dry_run=False,
            reasoning_effort=None,
            reasoning_tokens=None,
            reasoning_exclude=None,
            reasoning_mode=None,
            enable_vision=False,
            enable_structured=False,
            temperature=None,
            max_tokens=None,
            top_p=None,
            top_k=None,
            repeat_penalty=None,
            execution_mode="dev",
            experiment_name=None,
            where=[],
            exclude=[],
        )

        runner = BenchmarkRunner(args)
        runner.db_manager = db_manager
        runner.settings = settings

        # 4. Verificar que apenas [A, B, C] foram executados (D ignorado)
        run_models = run_model_repo.get_by_run("run-test-ignore")
        models_to_execute = [rm for rm in run_models if rm.status in ('pending',)]

        assert len(models_to_execute) == 3, "3 modelos do run devem ser executados"
        assert {rm.variant_id for rm in models_to_execute} == {"var-a", "var-b", "var-c"}
        # Verificar que 'model-d' da CLI foi ignorado
        assert not any(rm.variant_id == "model-d" for rm in models_to_execute)

    def test_run_id_loads_from_database(self, db_manager, settings) -> None:
        """Garantir que modelos são carregados da tabela run_models."""
        from src.db.repository import RunRepository, RunModelRepository, ModelVariantRepository, ModelRepository
        from src.db.models import Run, ModelVariant, Model
        from src.main import BenchmarkRunner
        from argparse import Namespace

        # Criar run
        run_repo = RunRepository(db_manager)
        run = Run(run_id="run-test-db", status="pending", is_dev=True)
        run_repo.create(run)

        # Create base model and variant
        model_repo = ModelRepository(db_manager)
        model_repo.create(Model(model_id="test-model-db", provider="testdb", model_name="Test Model DB"))

        variant_repo = ModelVariantRepository(db_manager)
        variant_repo.create(ModelVariant(
            variant_id="var-db",
            model_id="test-model-db",
            variant_signature="test-model-db::reasoning=unspecified::vision=false::structured=false",
        ))

        # Adicionar modelo ao run
        run_model_repo = RunModelRepository(db_manager)
        run_model_repo.create(RunModel(run_id="run-test-db", variant_id="var-db", status="pending"))

        # Criar runner com --run-id
        args = Namespace(
            run_id="run-test-db",
            models=None,
            iterations=1,
            questions=None,
            seed=None,
            vary_seed=False,
            test_mode=False,
            dry_run=False,
            reasoning_effort=None,
            reasoning_tokens=None,
            reasoning_exclude=None,
            reasoning_mode=None,
            enable_vision=False,
            enable_structured=False,
            temperature=None,
            max_tokens=None,
            top_p=None,
            top_k=None,
            repeat_penalty=None,
            execution_mode="dev",
            experiment_name=None,
            where=[],
            exclude=[],
        )

        runner = BenchmarkRunner(args)
        runner.db_manager = db_manager
        runner.settings = settings

        # Verificar que modelo foi carregado do banco
        run_models = run_model_repo.get_by_run("run-test-db")
        assert len(run_models) == 1
        assert run_models[0].variant_id == "var-db"
        assert run_models[0].status == "pending"
