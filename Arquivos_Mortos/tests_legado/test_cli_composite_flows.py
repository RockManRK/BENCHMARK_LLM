"""Integration tests for composite CLI flows (CREATE + ADD_*).

These tests validate that:
- Composite commands work end-to-end
- Experiment is created BEFORE action execution
- Data is persisted correctly
- Argument order does not affect behavior
"""

import subprocess
import sys
import uuid
import json

from src.cli.database import get_database_connection
from src.db.repository import ExperimentRepository, VariantRepository, SnapshotRepository, RunRepository


def run_command(cmd: str) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def cleanup_experiment(name: str) -> None:
    """Clean up test experiment from database."""
    conn = get_database_connection()
    try:
        exp_repo = ExperimentRepository(conn)
        exp = exp_repo.get_by_name(name)
        if exp:
            # Soft delete
            exp.status = "deleted"
            exp_repo.save(exp)
    finally:
        conn.close()


class TestCompositeFlows:
    """Integration tests for composite CLI flows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_prefix = f"composite_test_{uuid.uuid4().hex[:8]}"
    
    def teardown_method(self):
        """Clean up after each test."""
        cleanup_experiment(self.test_prefix)
    
    def test_create_experiment_with_add_model(self):
        """Test: --create-experiment EXP --add-model M"""
        cmd = (
            f'python bcllm.py --create-experiment {self.test_prefix} '
            f'--add-model openai/gpt-4o-mini'
        )
        
        code, out, err = run_command(cmd)
        
        # Should succeed
        assert code == 0, f"Command failed: {err}"
        assert "✓" in out or "created" in out.lower()
        
        # Verify experiment was created
        conn = get_database_connection()
        try:
            exp_repo = ExperimentRepository(conn)
            exp = exp_repo.get_by_name(self.test_prefix)
            assert exp is not None, "Experiment was not created"
            
            # Verify model was added
            var_repo = VariantRepository(conn)
            variants = var_repo.list_by_experiment(exp.experiment_id)
            assert len(variants) > 0, "Model was not added"
        finally:
            conn.close()
    
    def test_create_experiment_with_add_questions(self):
        """Test: --create-experiment EXP --add-questions Q"""
        cmd = (
            f'python bcllm.py --create-experiment {self.test_prefix} '
            f'--add-questions 1-5'
        )
        
        code, out, err = run_command(cmd)
        
        # Should succeed
        assert code == 0, f"Command failed: {err}"
        
        # Verify experiment was created
        conn = get_database_connection()
        try:
            exp_repo = ExperimentRepository(conn)
            exp = exp_repo.get_by_name(self.test_prefix)
            assert exp is not None, "Experiment was not created"
            
            # Verify questions were added
            snap_repo = SnapshotRepository(conn)
            snapshots = snap_repo.list_by_experiment(exp.experiment_id)
            assert len(snapshots) > 0, "Questions were not added"
        finally:
            conn.close()
    
    def test_create_experiment_with_add_run(self):
        """Test: --create-experiment EXP --add-run"""
        cmd = (
            f'python bcllm.py --create-experiment {self.test_prefix} '
            f'--add-run --seed 42'
        )
        
        code, out, err = run_command(cmd)
        
        # Should succeed
        assert code == 0, f"Command failed: {err}"
        
        # Verify experiment was created
        conn = get_database_connection()
        try:
            exp_repo = ExperimentRepository(conn)
            exp = exp_repo.get_by_name(self.test_prefix)
            assert exp is not None, "Experiment was not created"
            
            # Verify run was added
            run_repo = RunRepository(conn)
            runs = run_repo.list_by_experiment(exp.experiment_id)
            assert len(runs) > 0, "Run was not added"
        finally:
            conn.close()
    
    def test_argument_order_does_not_matter(self):
        """Test that argument order does not affect behavior."""
        # Order 1: --create-experiment first
        cmd1 = (
            f'python bcllm.py --create-experiment {self.test_prefix}_1 '
            f'--add-model openai/gpt-4o-mini'
        )

        # Order 2: --add-model first
        cmd2 = (
            f'python bcllm.py --add-model openai/gpt-4o-mini '
            f'--create-experiment {self.test_prefix}_2'
        )

        code1, out1, err1 = run_command(cmd1)
        code2, out2, err2 = run_command(cmd2)

        # Both should succeed
        assert code1 == 0, f"Command 1 failed: {err1}"
        assert code2 == 0, f"Command 2 failed: {err2}"

        # Both should create experiment and add model
        conn = get_database_connection()
        try:
            exp_repo = ExperimentRepository(conn)
            var_repo = VariantRepository(conn)

            # Check experiment 1
            exp1 = exp_repo.get_by_name(f"{self.test_prefix}_1")
            assert exp1 is not None
            variants1 = var_repo.list_by_experiment(exp1.experiment_id)
            assert len(variants1) > 0

            # Check experiment 2
            exp2 = exp_repo.get_by_name(f"{self.test_prefix}_2")
            assert exp2 is not None
            variants2 = var_repo.list_by_experiment(exp2.experiment_id)
            assert len(variants2) > 0
        finally:
            conn.close()

        # Clean up extra experiments
        cleanup_experiment(f"{self.test_prefix}_1")
        cleanup_experiment(f"{self.test_prefix}_2")

    def test_composite_flow_creates_identical_config_to_standalone(self):
        """Verify composite flow applies .env defaults identically to standalone flow.
        
        This test ensures that:
        - Creating experiment via --create-experiment EXP --add-model M
        - Creating experiment via --create-experiment EXP then --add-model M
        
        Both produce experiments with identical configuration (all 17 config keys match).
        """
        # Generate unique names for both experiments
        uuid_suffix = uuid.uuid4().hex[:8]
        standalone_name = f"test_standalone_{uuid_suffix}"
        composite_name = f"test_composite_{uuid_suffix}"
        
        try:
            # Create via standalone flow (two separate commands)
            cmd_standalone_create = f'python bcllm.py --create-experiment {standalone_name}'
            cmd_standalone_add_model = f'python bcllm.py --experiment {standalone_name} --add-model openai/gpt-4o-mini'
            
            code_create, out_create, err_create = run_command(cmd_standalone_create)
            assert code_create == 0, f"Standalone create failed: {err_create}"
            
            code_add, out_add, err_add = run_command(cmd_standalone_add_model)
            assert code_add == 0, f"Standalone add-model failed: {err_add}"
            
            # Create via composite flow (single command)
            cmd_composite = f'python bcllm.py --create-experiment {composite_name} --add-model openai/gpt-4o-mini'
            code_composite, out_composite, err_composite = run_command(cmd_composite)
            assert code_composite == 0, f"Composite flow failed: {err_composite}"
            
            # Fetch both experiments from DB
            conn = get_database_connection()
            try:
                exp_repo = ExperimentRepository(conn)
                
                standalone_exp = exp_repo.get_by_name(standalone_name)
                composite_exp = exp_repo.get_by_name(composite_name)
                
                # Verify both experiments exist
                assert standalone_exp is not None, "Standalone experiment was not created"
                assert composite_exp is not None, "Composite experiment was not created"
                
                # Parse configs
                standalone_config = json.loads(standalone_exp.config_json)
                composite_config = json.loads(composite_exp.config_json)
                
                # Verify both have the same set of keys (17 config keys)
                standalone_keys = set(standalone_config.keys())
                composite_keys = set(composite_config.keys())
                assert standalone_keys == composite_keys, (
                    f"Config key mismatch. "
                    f"Standalone has {len(standalone_keys)} keys, composite has {len(composite_keys)} keys. "
                    f"Missing in composite: {standalone_keys - composite_keys}. "
                    f"Extra in composite: {composite_keys - standalone_keys}"
                )
                
                # Verify all 17 keys match with identical values
                mismatched_keys = []
                for key in standalone_config:
                    if standalone_config[key] != composite_config[key]:
                        mismatched_keys.append(
                            f"{key}: standalone={standalone_config[key]!r}, composite={composite_config[key]!r}"
                        )
                
                assert len(mismatched_keys) == 0, (
                    f"Found {len(mismatched_keys)} mismatched config keys:\n" +
                    "\n".join(mismatched_keys)
                )
                
                # Verify .env defaults are applied (critical fields)
                # USER_PROMPT from .env: "Select the correct answer by providing only the letter (A, B, C, or D)."
                assert standalone_config.get("USER_PROMPT") is not None, (
                    "USER_PROMPT should be loaded from .env"
                )
                assert standalone_config.get("USER_PROMPT") == (
                    "Select the correct answer by providing only the letter (A, B, C, or D)."
                ), "USER_PROMPT should match .env value"
                
                # BASE_URL from .env: "https://openrouter.ai/api"
                assert standalone_config.get("BASE_URL") is not None, (
                    "BASE_URL should be loaded from .env"
                )
                assert standalone_config.get("BASE_URL") == "https://openrouter.ai/api", (
                    "BASE_URL should match .env value"
                )
                
                # MODEL_VISION from .env: true
                assert standalone_config.get("MODEL_VISION") is not None, (
                    "MODEL_VISION should be loaded from .env"
                )
                
                # STRUCTURED_OUTPUTS from .env: false
                assert standalone_config.get("STRUCTURED_OUTPUTS") is not None, (
                    "STRUCTURED_OUTPUTS should be loaded from .env"
                )
                
                # RUN_RESPONSES_SEED from .env (may be empty string or None)
                # Just verify the key exists
                assert "RUN_RESPONSES_SEED" in standalone_config, (
                    "RUN_RESPONSES_SEED key should exist in config"
                )
                
                # Verify config hash would be identical (same JSON = same hash)
                # Note: JSON may have different key ordering, so we compare sorted JSON
                standalone_sorted = json.dumps(standalone_config, sort_keys=True)
                composite_sorted = json.dumps(composite_config, sort_keys=True)
                assert standalone_sorted == composite_sorted, (
                    "Sorted JSON configs should be identical (ensures hash equivalence)"
                )
                
            finally:
                conn.close()
                
        finally:
            # Cleanup both experiments
            cleanup_experiment(standalone_name)
            cleanup_experiment(composite_name)


if __name__ == "__main__":
    # Run tests manually if executed as script
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
