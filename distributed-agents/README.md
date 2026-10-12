# Distributed Agents Platform

CM6453 Software Processes term project. A platform that turns a requirement
document into a web application by splitting the work across LLM agents
running on seven PCs: one **master** plans, assigns and integrates; six
**workers** do the tasks with their own local models.

## Quick start

```bash
git clone https://github.com/<owner>/distributed-agents.git
cd distributed-agents
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
pytest
uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open http://localhost:8000/api/v1/health. Full steps, Tailscale and
Ollama: [docs/SETUP.md](docs/SETUP.md).

## Read this before writing code

[docs/PROJECT_CONTRACT.md](docs/PROJECT_CONTRACT.md) fixes every shared name:
endpoints, JSON fields, enum values, ports, environment variables and function
signatures. Paste it into your AI assistant at the start of every session.

## Working with an AI assistant

Open the repository folder in your AI tool, run `git pull origin main`, then say:

```text
Read AGENTS.md and follow it. I am <NAME>. Do my next task for the current sprint.
```

[AGENTS.md](AGENTS.md) holds the rules every assistant follows. What each
member does in a sprint is in `docs/sprints/sprint-N/member-guide.md`
(now: [Sprint 1](docs/sprints/sprint-1/member-guide.md)). Before you commit,
run `git status` and make sure only files in your own folder changed.

## Structure

```text
dap/
  shared/     enums, data models, LLM client (used by master and worker)
  master/     FastAPI server: api/, core/ (decompose, assign), db/
  worker/     the program that runs on the six worker PCs
frontend/     React web interface
tests/        pytest
scripts/      helper scripts (seed agents, smoke test)
docs/         contract, setup guide, requirements, sprint documents
```

## Team

| Member | Role | Folder |
| --- | --- | --- |
| Okan | Product Owner | `docs/` |
| Hamza | Scrum Master | `docs/sprints/` |
| Baran | Master Agent | `dap/master/api/`, `dap/master/core/` |
| Can | Database | `dap/master/db/` |
| Fatma | Frontend | `frontend/` |
| Eray | Worker Agent and LLM | `dap/worker/`, `dap/shared/llm_client.py` |
| Abdurrahman | DevOps, network and tests | `scripts/`, `tests/`, `.github/` |

## How we work

1. `git pull origin main`
2. `git checkout -b feature/S1-07-worker-register` (card id + short name)
3. Commit with the card id first: `S1-07: add heartbeat loop`
4. `git push -u origin feature/S1-07-worker-register`, then open a pull request
5. Ask a teammate to look at it. If nobody has reviewed it within a day, merge
   it yourself. Nobody pushes to `main` directly.

## Status

Sprint 1 skeleton. The shared contract (`dap/shared/enums.py`,
`dap/shared/schemas.py`), the settings files and `GET /api/v1/health` work.
Every other file states in its docstring what belongs there, who owns it and
which Trello card covers it.
