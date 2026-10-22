# Master (`dap/master/`)

Owner: Baran. Settings come from `.env` through `config.py`.

## Status

- `python -m dap.master` starts the master on `MASTER_HOST:MASTER_PORT` from `.env`
  (default `0.0.0.0:8000`); the uvicorn command still works.
- `main.py` serves the `/api/v1` routes (health, agents, projects) with CORS
  from `.env`, and the built web interface (`frontend/dist`) at `/`, with
  `index.html` for React routes. Without a build, `/` explains how to build.
- `api/agents.py`: `POST /agents/register` and `POST /agents/{id}/heartbeat`
  behind the `X-Agent-Token` header; `GET /agents` lists agents.
- `api/projects.py`: create/list/get projects and tasks, `POST /decompose`
  (LLM failure → project `failed` + 502) and `POST /assign` with the scoring
  of contract section 8; agents without a recent heartbeat are marked offline first.
- `core/decomposer.py`: builds tasks per contract section 9; `core/selector.py`:
  scores agents per contract section 8 (reads `q` through the repository).
- Sprint 3: `POST /projects/{id}/run` starts `core/orchestrator.py` in a thread. It sends
  the tasks to the workers over A2A (`a2a_client.py`) in dependency order, follows them,
  stores the results and commits each task's files into `workspace/<project_id>/`
  (`core/integrator.py`). `GET /results`, `GET /files`, `GET /files/{path}` show them.
- `cli.py`: `python -m dap.master.cli agents` / `project <file or text>`;
  needs `MASTER_URL` in `.env`.
- Tests: `tests/test_agents.py`, `test_projects.py`, `test_decomposer.py`,
  `test_selector.py`, `test_cli.py`, `test_frontend.py`, `test_orchestrator.py`.
