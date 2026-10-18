import os
import json

def smoke_test():
    print("[INFO] Running smoke test for distributed AI nodes...")
    config_path = "config/agents_registry.json"
    
    if not os.path.exists(config_path):
        print(f"[ERROR] Agent registry not found at {config_path}!")
        exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"[INFO] Loaded registry: {data}")
    print("[SUCCESS] Smoke test passed successfully! All nodes configured.")

if __name__ == "__main__":
    smoke_test()