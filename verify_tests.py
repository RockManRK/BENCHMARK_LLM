import subprocess
import sqlite3
import os

def run_cmd(cmd):
    print(f"\n>>> [CMD]: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout + "\n" + result.stderr

def check_db(query):
    conn = sqlite3.connect("data/benchmark.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

if os.path.exists("data/benchmark.db"):
    os.remove("data/benchmark.db")
    print("Database wiped to clear state.")

print("\n" + "="*40 + "\n 2. DEV MODE \n" + "="*40)
out1 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --models Qwen --questions Q001")
print("- Execution mode : DEV MODE ->", "Execution mode      : DEV MODE" in out1)
print("- Persist data : YES ->", "Persist data        : YES" in out1)
runs1 = check_db("SELECT * FROM runs")
print(f"- Runs count: {len(runs1)}")
if runs1:
    print(f"- Run is_dev: {runs1[0]['is_dev']}, exp_id: {runs1[0]['experiment_id']}")

out2 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --models Qwen --questions Q001 --temperature 0.7")
runs2 = check_db("SELECT * FROM runs")
print(f"- Total Runs after temp change: {len(runs2)}")

out3 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --models Qwen --questions Q001 --iterations 3")
runs3 = check_db("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1")
run_id3 = runs3[0]['run_id']
responses3 = check_db(f"SELECT * FROM responses WHERE run_id='{run_id3}'")
print(f"- Responses for iterations run: {len(responses3)}")
print(f"- Iterations saved: {[r['iteration'] for r in responses3]}")

print("\n" + "="*40 + "\n 3. EXPERIMENT MODE \n" + "="*40)
out4 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --experiment estudo_teste --models Qwen --questions Q002 --temperature 0.0")
print("- Execution mode : EXPERIMENT MODE ->", "Execution mode      : EXPERIMENT MODE" in out4)
exps = check_db("SELECT * FROM experiments")
print(f"- Experiments count: {len(exps)}, hash: {exps[0]['config_hash']}")
runs4 = check_db("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1")
print(f"- Run is_dev: {runs4[0]['is_dev']}, exp_id: {runs4[0]['experiment_id']}")

out5 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --experiment estudo_teste --models Qwen --questions Q002 --temperature 0.9")
print("- Ignored Warning triggered on temp diff ->", "Frozen experiment configuration detected" in out5)

out6 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --experiment estudo_teste --models Qwen --max-tokens 2048 --questions Q002")
print("- Ignored Warning triggered on tokens diff ->", "Frozen experiment configuration detected" in out6)

print("\n" + "="*40 + "\n 4. FLAGS PRECEDENCE \n" + "="*40)
out7 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --mode dev --experiment estudo_teste --models Qwen --questions Q002")
print("- Warning that force EXPERIMENT MODE ->", "forces EXPERIMENT MODE" in out7)

out8 = run_cmd(r".\.venv\Scripts\python.exe bcllm.py --test-mode --experiment estudo_teste --models Qwen --questions Q002")
print("- Warning that test-mode overrides experiment ->", "Warning: --test-mode has precedence" in out8)
print("- Actually executed as TEST MODE ->", "Execution mode      : TEST MODE" in out8)

print("\n" + "="*40 + "\n 5. TOKENS E METRICS \n" + "="*40)
responses9 = check_db(f"SELECT * FROM responses ORDER BY response_id DESC LIMIT 1")
if responses9:
    r = responses9[0]
    print(f"- Input tokens: {r['input_tokens']}, Output tokens: {r['output_tokens']}, Reasoning: {r['reasoning_tokens']}")

print("\n" + "="*40 + "\n 7. SANITY CHECKS \n" + "="*40)
dev_runs = check_db("SELECT COUNT(*) as c FROM runs WHERE is_dev = 1")
exp_runs = check_db("SELECT COUNT(*) as c FROM runs WHERE is_dev = 0")
print(f"- Dev runs (is_dev=true): {dev_runs[0]['c']}")
print(f"- Exp runs (is_dev=false): {exp_runs[0]['c']}")

print("\nTests completed successfully.")
