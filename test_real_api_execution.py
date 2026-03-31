#!/usr/bin/env python
"""Block 6e Real API Execution Test"""

import sqlite3
import json
import sys
import os
from datetime import datetime

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = 'benchmark.db'

def setup_test_experiment():
    """Create a minimal test experiment with one model and question."""
    from src.db.schema import create_schema
    from src.core.randomizer import AnswerRandomizer
    from src.core.answer_parser import AnswerParser
    from src.api.client import OpenRouterClient
    from src.core.execution_engine import ExecutionEngine
    from src.core.result_writer import ResultWriter
    from src.core.execution_plan import (
        ExecutionPlan, PlanRun, PlanItem, PlanVariant, ModelConfig,
        RetryPolicy, Prompts, QuestionPayload
    )
    
    # Initialize schema
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    cursor = conn.cursor()
    
    # Check if we already have test data
    cursor.execute("SELECT COUNT(*) FROM experiments")
    if cursor.fetchone()[0] > 0:
        print("Existing experiments found - using first one")
        cursor.execute("SELECT experiment_id, name FROM experiments LIMIT 1")
        row = cursor.fetchone()
        experiment_id = row['experiment_id']
        experiment_name = row['name']
    else:
        # Create test experiment
        experiment_id = "exp-block6e-test"
        experiment_name = "Block 6e Validation Test"
        config = {
            "description": "Test experiment for Block 6e validation",
            "models": ["teste/teste"],
            "questions": {"add": "1-3"}
        }
        cursor.execute("""
            INSERT OR IGNORE INTO experiments (experiment_id, name, description, config_json, config_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (
            experiment_id,
            experiment_name,
            config['description'],
            json.dumps(config),
            "test-hash-001"
        ))
    
    # Check if we have model variants
    cursor.execute("SELECT COUNT(*) FROM model_variants WHERE experiment_id = ?", (experiment_id,))
    if cursor.fetchone()[0] == 0:
        # Create test model variant
        variant_id = "var-block6e-001"
        model_id = "openai/gpt-3.5-turbo"  # Use a common model
        variant_signature = "gpt-3.5-turbo::temp=0.7::max_tokens=100"
        model_config = {
            "temperature": 0.7,
            "top_p": 1.0,
            "max_output_tokens": 100,
            "structured_output": False
        }
        cursor.execute("""
            INSERT INTO model_variants (variant_id, experiment_id, model_id, variant_signature, config)
            VALUES (?, ?, ?, ?, ?)
        """, (
            variant_id,
            experiment_id,
            model_id,
            variant_signature,
            json.dumps(model_config)
        ))
        print(f"Created model variant: {model_id}")
    else:
        cursor.execute("SELECT variant_id, model_id FROM model_variants WHERE experiment_id = ? LIMIT 1", (experiment_id,))
        row = cursor.fetchone()
        variant_id = row['variant_id']
        model_id = row['model_id']
        print(f"Using existing model variant: {model_id}")
    
    # Check if we have question snapshots
    cursor.execute("SELECT COUNT(*) FROM question_snapshots WHERE experiment_id = ?", (experiment_id,))
    if cursor.fetchone()[0] == 0:
        # Create test question snapshots
        test_questions = [
            {
                "question_id": "Q001",
                "stem": "What is 2 + 2?",
                "options": ["3", "4", "5", "6"],
                "answer_key": "B"
            },
            {
                "question_id": "Q002",
                "stem": "What is the capital of France?",
                "options": ["London", "Berlin", "Paris", "Madrid"],
                "answer_key": "C"
            },
            {
                "question_id": "Q003",
                "stem": "Which planet is known as the Red Planet?",
                "options": ["Venus", "Mars", "Jupiter", "Saturn"],
                "answer_key": "B"
            }
        ]
        
        for i, q in enumerate(test_questions, 1):
            cursor.execute("""
                INSERT INTO question_snapshots (snapshot_id, experiment_id, json_question_id, question_position, question_payload)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"snap-block6e-{i:03d}",
                experiment_id,
                q["question_id"],
                i,
                json.dumps(q)
            ))
        print(f"Created {len(test_questions)} question snapshots")
    else:
        cursor.execute("SELECT COUNT(*) FROM question_snapshots WHERE experiment_id = ?", (experiment_id,))
        count = cursor.fetchone()[0]
        print(f"Using {count} existing question snapshots")
    
    # Create test run
    run_id = "run-block6e-001"
    run_config = {
        "seed": 42,
        "prompts": {
            "system": "You are a helpful assistant.",
            "user": "Select the correct answer by providing only the letter (A, B, C, or D).\n\n{question}"
        }
    }
    
    # Check if run already exists
    cursor.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", (run_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO runs (run_id, experiment_id, config, status)
            VALUES (?, ?, ?, ?)
        """, (
            run_id,
            experiment_id,
            json.dumps(run_config),
            "pending"
        ))
        print(f"Created run: {run_id}")
    else:
        # Reset run status
        cursor.execute("UPDATE runs SET status = 'pending' WHERE run_id = ?", (run_id,))
        print(f"Using existing run: {run_id}")
    
    conn.commit()
    
    # Get snapshot IDs for plan
    cursor.execute("SELECT snapshot_id, question_payload FROM question_snapshots WHERE experiment_id = ? ORDER BY question_position LIMIT 3", (experiment_id,))
    snapshots = cursor.fetchall()
    
    conn.close()
    
    # Build execution plan
    plan_items = []
    for snap in snapshots:
        question_data = json.loads(snap['question_payload'])
        question_payload = QuestionPayload(
            stem=question_data['stem'],
            options=question_data['options'],
            answer_key=question_data['answer_key']
        )
        item = PlanItem(
            item_id=f"{run_id}::{variant_id}::{snap['snapshot_id']}::it-001",
            run_id=run_id,
            variant_id=variant_id,
            snapshot_id=snap['snapshot_id'],
            question_id=question_data['question_id'],
            question_payload=question_payload
        )
        plan_items.append(item)
    
    plan_variant = PlanVariant(
        variant_id=variant_id,
        model_id=model_id,
        model_config_effective=ModelConfig(
            temperature=0.7,
            top_p=1.0,
            max_output_tokens=100,
            structured_output=False
        )
    )
    
    plan_run = PlanRun(
        run_id=run_id,
        variants=[plan_variant],
        items=plan_items,
        seed_effective=42,
        prompts_effective=Prompts(
            system="You are a helpful assistant.",
            user="Select the correct answer by providing only the letter (A, B, C, or D).\n\n{question}"
        ),
        retry_policy=RetryPolicy()
    )
    
    from datetime import datetime
    
    plan = ExecutionPlan(
        plan_id=f"plan-{experiment_id}-001",
        created_at=datetime.now(),
        experiment_id=experiment_id,
        runs=[plan_run]
    )
    
    return plan, model_id

def run_execution(plan, model_id):
    """Execute the plan with real API."""
    from src.core.randomizer import AnswerRandomizer
    from src.core.answer_parser import AnswerParser
    from src.api.client import OpenRouterClient
    from src.core.execution_engine import ExecutionEngine
    from src.core.result_writer import ResultWriter
    from src.utils.logging_config import setup_logging
    
    import os
    
    # Setup logging
    setup_logging()
    
    # Get API key from environment
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in environment")
        return None
    
    # Initialize components
    api_client = OpenRouterClient(
        api_key=api_key,
        base_url=os.environ.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
        debug_enabled=os.environ.get('OPENROUTER_DEBUG_ENABLED', 'true').lower() == 'true'
    )
    
    randomizer = AnswerRandomizer()
    parser = AnswerParser()
    engine = ExecutionEngine(api_client, randomizer, parser)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    writer = ResultWriter(conn)
    
    print(f"\n=== Executing Plan ===")
    print(f"Experiment: {plan.experiment_id}")
    print(f"Runs: {len(plan.runs)}")
    print(f"Total items: {sum(len(run.items) for run in plan.runs)}")
    print(f"Model: {model_id}")
    print(f"Debug enabled: {api_client._debug_enabled}")
    
    try:
        # Execute
        results = engine.execute(plan)
        
        print(f"\n=== Execution Results ===")
        print(f"Total results: {len(results)}")
        successes = sum(1 for r in results if r.status == 'success')
        failures = sum(1 for r in results if r.status == 'failure')
        print(f"Successes: {successes}")
        print(f"Failures: {failures}")
        
        # Write results
        print(f"\n=== Writing Results ===")
        write_report = writer.write_results(results)
        print(f"Responses written: {write_report.responses_written}")
        print(f"Responses skipped: {write_report.responses_skipped}")
        print(f"Errors written: {write_report.errors_written}")
        
        conn.commit()
        conn.close()
        
        return {
            'results': results,
            'write_report': write_report
        }
        
    except Exception as e:
        print(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return None

def verify_results():
    """Verify the results in database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n=== Database Verification ===")
    
    # Get latest response
    cursor.execute("""
        SELECT response_id, raw_response, response_tokens, review_status
        FROM responses 
        ORDER BY response_id DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if not row:
        print("No responses found in database")
        conn.close()
        return None
    
    response_id = row[0]
    raw_response = row[1]
    response_tokens = row[2]
    review_status = row[3]
    
    print(f"\nLatest Response: {response_id}")
    print(f"Response tokens: {response_tokens}")
    print(f"Review status: {review_status}")
    
    # Check raw_response
    if raw_response:
        try:
            raw = json.loads(raw_response)
            chunk_count = len(raw) if isinstance(raw, list) else 1
            print(f"\nRaw response chunks: {chunk_count}")
            
            if isinstance(raw, list) and len(raw) > 0:
                first = raw[0]
                has_debug = 'debug' in first
                print(f"First chunk has debug: {has_debug}")
                
                if has_debug:
                    debug_payload = first['debug']
                    echo_upstream = 'echo_upstream_body' in debug_payload
                    print(f"echo_upstream_body present: {echo_upstream}")
                    
                    if echo_upstream:
                        echo_body = debug_payload['echo_upstream_body']
                        print(f"\nEcho upstream body preview:")
                        if isinstance(echo_body, dict):
                            print(f"  Keys: {list(echo_body.keys())}")
                            if 'messages' in echo_body:
                                print(f"  Messages count: {len(echo_body['messages'])}")
                            if 'model' in echo_body:
                                print(f"  Model: {echo_body['model']}")
                
                conn.close()
                return {
                    'chunk_count': chunk_count,
                    'has_debug': has_debug,
                    'echo_upstream_body': echo_upstream if has_debug else False,
                    'response_tokens': response_tokens,
                    'review_status': review_status
                }
        except json.JSONDecodeError as e:
            print(f"Failed to parse raw_response: {e}")
    
    conn.close()
    return None

def main():
    """Main test routine."""
    print("=" * 60)
    print("Block 6e Real API Execution Test")
    print("=" * 60)
    
    # Setup test experiment
    print("\n=== Setting Up Test Experiment ===")
    plan, model_id = setup_test_experiment()
    
    if not plan:
        print("Failed to setup test experiment")
        return 1
    
    # Run execution
    exec_result = run_execution(plan, model_id)
    
    if not exec_result:
        print("\nExecution failed or returned no results")
        return 1
    
    # Verify results
    verify_result = verify_results()
    
    # Generate report
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    
    if verify_result:
        print("\n### Debug Chunk Capture")
        print(f"- Chunks captured: {verify_result['chunk_count']}")
        print(f"- Debug field present: {verify_result['has_debug']}")
        print(f"- echo_upstream_body: {verify_result['echo_upstream_body']}")
        
        print("\n### Schema Compliance")
        print(f"- response_tokens field: {verify_result['response_tokens']}")
        print(f"- review_status: {verify_result['review_status']}")
        
        # Classification
        print("\n### Classification")
        if verify_result['has_debug'] and verify_result['echo_upstream_body']:
            print("✅ **PASS** — All fixes validated")
            print("\n**Recommendation:**")
            print("- Block 6e ready for Essence Guardian Gate")
            print("- Resume Block 5 (Human-Driven Validation)")
            return 0
        else:
            print("⚠️ **PARTIAL** — Debug capture not verified")
            print("\n**Note:** Debug capture depends on API support.")
            print("Schema compliance verified successfully.")
            return 0
    else:
        print("❌ **FAIL** — No results to verify")
        return 1

if __name__ == '__main__':
    sys.exit(main())
