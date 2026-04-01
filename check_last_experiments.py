import sqlite3
import json

conn = sqlite3.connect('data/benchmark.db')
cursor = conn.cursor()

cursor.execute("SELECT experiment_id, name, config_json FROM experiments ORDER BY created_at DESC LIMIT 5")
results = cursor.fetchall()

for row in results:
    print(f"\n{'='*60}")
    print(f"Experiment: {row[1]} (ID: {row[0]})")
    print(f"config_json: {row[2]}")
    if row[2]:
        config = json.loads(row[2])
        print(f"Parsed keys: {list(config.keys())}")
        print(f"Total keys: {len(config)}")
        
        # Check for unwanted keys
        unwanted = ['QUESTIONS_STATUS_ADD', 'QUESTIONS_STATUS_EXCLUDE', 'MODELS_DEFAULT_FOR_EXPERIMENTS']
        found_unwanted = [k for k in unwanted if k in config]
        if found_unwanted:
            print(f"WARNING: Found unwanted keys: {found_unwanted}")
        else:
            print("✓ No unwanted keys found")

conn.close()
