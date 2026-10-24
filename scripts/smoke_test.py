import os
import requests

MASTER_URL = os.getenv("MASTER_URL", "http://localhost:5000")

def run_smoke_test():
    steps = [
        ("Health Check", "GET", "/health", None),
        ("Agent Register", "POST", "/api/v1/agents/register", {"agent_id": "smoke-tester", "role": "verifier"}),
        ("Create Project", "POST", "/api/v1/projects", {"name": "Test Project"}),
        ("Decompose Task", "POST", "/api/v1/projects/decompose", {"project_id": "test-proj"}),
        ("Assign Task", "POST", "/api/v1/tasks/assign", {"task_id": "t1", "agent_id": "smoke-tester"}),
        ("Get Next Task", "GET", "/api/v1/tasks/next?agent_id=smoke-tester", None),
        ("Submit Result", "POST", "/api/v1/tasks/result", {"task_id": "t1", "status": "completed"})
    ]

    print(f"[INFO] Running live smoke test against {MASTER_URL}...")

    for name, method, path, payload in steps:
        url = f"{MASTER_URL}{path}"
        try:
            if method == "GET":
                response = requests.get(url, timeout=5)
            else:
                response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code in [200, 201]: 
                print(f"[PASS] {name} ({path}) -> Status: {response.status_code}")
            else:
                print(f"[FAIL] {name} ({path}) -> Status: {response.status_code}")
                print(f"[ERROR] SMOKE TEST FAILED at step: {name}")
                exit(1)
        except Exception as e:
            print(f"[FAIL] {name} ({path}) -> Connection Error: {e}")
            print(f"[ERROR] SMOKE TEST FAILED at step: {name}")
            exit(1)

    print("SMOKE TEST PASSED")
    exit(0)

if __name__ == "__main__":
    run_smoke_test()
