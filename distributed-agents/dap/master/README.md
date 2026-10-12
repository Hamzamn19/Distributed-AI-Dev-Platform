# Master Agent

Owners: Baran (`api/`, `core/`, `cli.py`), Can (`db/`).

## What it does

Receives a requirement document, splits it into tasks with the local LLM,
decides which agent gets each task and stores everything in the database.
It is the only service the other PCs connect to.

## How to run

From the repository root, with the virtual environment active:

```bash
uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload
```

- Health check: http://localhost:8000/api/v1/health
- Interactive API docs: http://localhost:8000/docs

## Input and output

- Input: HTTP requests under `/api/v1` (see `docs/PROJECT_CONTRACT.md`).
- Output: JSON shaped like the models in `dap/shared/schemas.py`.
- Data: SQLite file `data/dap.db` (created on first start, not in git).

## Connections

| Talks to | How |
| --- | --- |
| Frontend | The frontend calls the API; the master never calls the frontend |
| Workers | Workers call the API (register, heartbeat); the master never calls a worker |
| LLM | `dap.shared.llm_client.chat()` |
| Database | Only through `dap/master/db/repositories.py` |

## Status

Sprint 1 skeleton: only `/health` works. See the docstring at the top of each
file for what belongs there and which Trello card covers it.
