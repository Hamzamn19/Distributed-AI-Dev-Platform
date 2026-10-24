import json
import os
import requests

MASTER_URL = os.getenv("MASTER_URL", "http://localhost:5000")
REGISTRY_FILE = "docs/agents.json"

def seed_agents():
    if not os.path.exists(REGISTRY_FILE):
        print(f"[ERROR] {REGISTRY_FILE} not found!")
        exit(1)

    with open(REGISTRY_FILE, "r") as f:
        agents = json.load(f)

    endpoint = f"{MASTER_URL}/api/v1/agents/register"
    print(f"[INFO] Seeding {len(agents)} agents to live server at {endpoint}...")

    for agent in agents:
        try:
            response = requests.post(endpoint, json=agent, timeout=5)
            if response.status_code in [200, 201]:
                print(f"[SUCCESS] Registered: {agent['agent_id']}")
            else:
                print(f"[ERROR] Failed to register {agent['agent_id']}: Status {response.status_code}")
                exit(1)
        except requests.exceptions.ConnectionError:
            print(f"[ERROR] Could not connect to master server at {MASTER_URL}. Is it running?")
            exit(1)

if __name__ == "__main__":
    seed_agents()
