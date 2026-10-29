# Machines and models

Fill one row each. Card S1-10. Commands: `nvidia-smi --query-gpu=name,memory.total --format=csv`, `python --version`, `node --version`, `git --version`, `docker --version`, `ollama --version`.

The model each agent runs is recorded in `docs/agents.json` (source of truth) and `docs/models.md`.

| Member | OS + version | CPU | RAM (GB) | GPU + VRAM (or unified memory) | Free disk (GB) | Laptop / desktop | Installed: Python / Node / Git / Docker / Ollama | Models installed | Speed (tokens/s) |
|---|---|---|---|---|---|---|---|---|---|
| Abdurrahman | Windows | Ryzen 7 | 40 | NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB | 245 | Laptop | Python 3.14.6 / Git 2.56.0 / Ollama 0.40.3 | qwen3:4b | - |
| Baran (master PC) | macOS | | | | | Laptop | | gemma4:26b (Gemma 4 26B A4B, same model as Hamza) | |
| Can | | | | | | | | | |
| Eray | | | | | | | | | |
| Fatma | | | | | | | | | |
| Hamza | Linux | | | | | | llama.cpp (llama-server) | gemma-4-26b-a4b-iq2_xxs (Gemma 4 26B A4B, same model as Baran) | |
| Okan | Windows 11 Pro | | 15.4 | NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB | | Laptop | Ollama 0.20.5 | qwen2.5:7b, qwen3:4b, qwen3:8b, llama3.1:8b | |
