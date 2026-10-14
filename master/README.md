# Master Agent (Sprint 1 demo)

Master Agent splits a requirement into tasks with a local Ollama model and assigns each
task to the best online agent using the S score. Sprint 1 scope: no agent executes tasks yet.

## Setup (once)

```bash
cd master
python3 -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set DAP_TOKEN
ollama pull llama3.1
```

## Quick start (one command)

From the project root (the folder that contains `run.py`):

```bash
.venv/bin/python run.py
```

It starts the backend (:8000) and the dashboard (:8501), waits until the backend answers,
opens the browser and stops both on Ctrl+C. Alternatives: double-click `start.command` in
Finder, or in VS Code press F5 ("Start DAP Platform" launch configuration) or run the "Start All" task.
Then click "Örnek Ajanları Kaydet" in the dashboard sidebar and submit a sample.

## Run the demo (manual, separate terminals)

1. Terminal 1, backend: `python main.py` (http://localhost:8000)
2. Terminal 2, one-command demo: `python cli.py demo` (or `demo todo`, `demo shop`)
   It registers the sample agents, submits `demo/library.md`, prints the task table
   (agent, S score, status) and the agent list. Registered this way the agents go offline
   after 30 s because nothing sends heartbeats; `python cli.py register` keeps them alive.
3. Terminal 3, dashboard: `streamlit run app.py` (http://localhost:8501)
   - Sidebar: "Örnek Ajanları Kaydet" registers backend/frontend/devops and keeps them
     alive while the dashboard runs.
   - Pick a sample in "Örnek gereksinim" (or upload a PDF), then "Projeyi Analiz Et".

## Quick API checks

- `GET /health` needs no token and returns `{"status": "ok", "version": "0.1.0", "ollama": true}`
  (`"ollama": false` when Ollama is not reachable).
- `POST /decompose` with `{"requirement": "..."}` splits the text into subtasks with Ollama
  and returns them without saving or assigning anything (`POST /projects` does both).
  Like every other endpoint it needs the `X-DAP-Token` header.

Other helpers: `python cli.py status`, `python cli.py project <file>`, `python cli.py register`.
Samples live in `demo/` (`library.md`, `todo.md`, `shop.md`).
