import os
import json

def seed_agents():
    print("[INFO] Seeding distributed AI agents across tailnet nodes...")
    
    # Düğüm ve rol konfigürasyonu
    agent_config = {
        "orchestrator": "Partner-PC (Windows)",
        "worker": "WSL-Node (Linux)",
        "network": "Tailscale Mesh",
        "status": "seeded"
    }
    
    # config klasörünü oluştur ve JSON olarak kaydet
    os.makedirs("config", exist_ok=True)
    config_path = "config/agents_registry.json"
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(agent_config, f, indent=4)
        
    print(f"[SUCCESS] Agent registry created successfully at {config_path}!")

if __name__ == "__main__":
    seed_agents()