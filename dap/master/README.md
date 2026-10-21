# Master (`dap/master/`)

Owner: Baran. Settings come from `.env` through `config.py`.

## Status

- `main.py` serves the `/api/v1` routes (health, agents, projects) with CORS
  from `.env`.
- `api/agents.py`: `POST /agents/register` and `POST /agents/{id}/heartbeat`
  behind the `X-Agent-Token` header; `GET /agents` lists agents.
- `api/projects.py`: create/list/get projects and tasks, `POST /decompose`
  (LLM failure → project `failed` + 502) and `POST /assign` with the scoring
  of contract section 8.
- `core/decomposer.py`: builds tasks per contract section 9; `core/selector.py`:
  scores agents per contract section 8 (reads `q` through the repository).
- `cli.py`: `python -m dap.master.cli agents` / `project <file or text>`;
  needs `MASTER_URL` in `.env`.
- Tests: `tests/test_agents.py`, `test_projects.py`, `test_decomposer.py`,
  `test_selector.py`, `test_cli.py`.
