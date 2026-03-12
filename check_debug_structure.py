import sqlite3
import json

conn = sqlite3.connect('data/benchmark.db')
cur = conn.cursor()

# Check responses 56 (debug ON) and 57 (debug OFF)
cur.execute('''
    SELECT response_id, model_id, reasoning_tokens, raw_response_json
    FROM responses 
    WHERE response_id IN (55, 56, 57, 58)
    ORDER BY response_id
''')

rows = cur.fetchall()

for r in rows:
    print(f"\n{'='*80}")
    print(f"Response ID: {r[0]}, Model: {r[1]}, Reasoning Tokens: {r[2]}")
    print(f"{'='*80}")
    
    if r[3]:
        try:
            raw = json.loads(r[3])
            
            # Check structure
            has_debug = "_debug" in raw
            has_response = "response" in raw
            
            print(f"Has '_debug': {has_debug}")
            print(f"Has 'response': {has_response}")
            
            # Get the actual response data
            if has_response:
                response_data = raw["response"]
                print(f"\nResponse wrapper detected - extracting from raw['response']")
            else:
                response_data = raw
                print(f"\nDirect response - using raw directly")
            
            # Check usage location
            usage = response_data.get("usage", {})
            print(f"\nUsage in response_data: {bool(usage)}")
            
            if usage:
                print(f"Usage keys: {list(usage.keys())}")
                if "completion_tokens_details" in usage:
                    print(f"completion_tokens_details: {usage['completion_tokens_details']}")
                    if "reasoning_tokens" in usage["completion_tokens_details"]:
                        print(f"✓ reasoning_tokens FOUND: {usage['completion_tokens_details']['reasoning_tokens']}")
                    else:
                        print(f"✗ reasoning_tokens NOT in completion_tokens_details")
                elif "reasoning_tokens" in usage:
                    print(f"✓ reasoning_tokens FOUND (flat): {usage['reasoning_tokens']}")
                else:
                    print(f"✗ reasoning_tokens NOT found in usage")
            else:
                print("Usage is EMPTY!")
                
                # Check if usage exists in debug wrapper
                if has_debug and "_debug" in raw:
                    debug = raw["_debug"]
                    if "upstream_body" in debug and debug["upstream_body"]:
                        upstream = debug["upstream_body"]
                        upstream_usage = upstream.get("usage", {})
                        print(f"\nChecking upstream_body for usage...")
                        if upstream_usage:
                            print(f"Usage in upstream_body: {bool(upstream_usage)}")
                            if "completion_tokens_details" in upstream_usage:
                                print(f"completion_tokens_details in upstream: {upstream_usage['completion_tokens_details']}")
                                if "reasoning_tokens" in upstream_usage["completion_tokens_details"]:
                                    print(f"✓ reasoning_tokens FOUND in upstream: {upstream_usage['completion_tokens_details']['reasoning_tokens']}")
            
        except Exception as e:
            print(f"Error parsing JSON: {e}")

conn.close()
