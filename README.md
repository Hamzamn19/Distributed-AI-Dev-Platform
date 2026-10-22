# Distributed AI Software Development Platform

CM6453 Software Processes term project. A user enters a software requirement in a
web interface. A **master** agent splits it into tasks, scores the available agents
by their measured capabilities and assigns each task to the best one. **Worker**
agents on other PCs run local LLMs (Ollama). Scrum, five two-week sprints.

## Where things are

| Path | Purpose | Owner |
| --- | --- | --- |
| `dap/master/` | Master: FastAPI API, decomposer, agent selection, database | Baran, Can (`db/`) |
| `dap/worker/` | Worker program every agent PC runs | Eray |
| `dap/shared/` | Shared enums, data models, LLM client | Baran, Eray |
| `frontend/` | Web interface (React + TypeScript + Vite + Tailwind) | Fatma |
| `tests/`, `scripts/`, `.github/` | Tests, helper scripts, CI | Abdurrahman |
| `docs/` | Contract, requirements, setup guide, sample requirements | Okan |
| `docs/sprints/` | Sprint planning, guides and reports | Hamza |

Start with [`AGENTS.md`](AGENTS.md) and the contract
[`docs/contracts/PROJECT_CONTRACT.md`](docs/contracts/PROJECT_CONTRACT.md).

## Getting started

Full guide, including Tailscale: [`docs/SETUP.md`](docs/SETUP.md). Short version,
from the repository root (Windows PowerShell; on macOS/Linux use `cp` and
`source .venv/bin/activate`):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env          # set LLM_MOCK=1 to try it without Ollama

cd frontend
npm install
npm run build                   # once, and after every frontend change
cd ..

python -m dap.master            # then open http://localhost:8000
```

The master serves the web interface and the API on one address:
`http://localhost:8000` (UI), `/docs` (API docs), `/api/v1/...` (API). From another PC
open `http://<master Tailscale IP>:8000`.

A worker (on an agent PC, or a second terminal on the same PC):

```powershell
python -m dap.worker.main                          # reads .env
python -m dap.worker.main --env-file .env.worker1  # see .env.worker.example
```

Checks: `pytest` (no Ollama needed) and, with the master running on `LLM_MOCK=1`,
`python scripts/smoke_test.py`.

## Team workflow

Branches `feature/<card-id>-<short-name>`, pull requests into `main`, CI runs `pytest`
and the frontend build on every pull request. Details: [`CONTRIBUTING.md`](CONTRIBUTING.md).
