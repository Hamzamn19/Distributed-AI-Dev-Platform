# Database Agent prototype

Flow: Master/API client -> FastAPI -> local Ollama -> Qwen2.5-Coder 7B -> SQL text.

This is a small, independent worker for CanKolcu's database role. It generates
schemas; it does not execute SQL or store projects/tasks. The shared contracts
are still pending in `docs/contracts/`, so this API is a provisional prototype.

## Run on Windows

Open PowerShell in the repository root, on `feat/database-agent`.

First-time setup (Python 3.12 or newer):

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r agents\database_agent\requirements.txt
```

Start Ollama in one terminal (or launch the installed Ollama application):

```powershell
ollama serve
```

In another terminal, download the model once and start the agent:

```powershell
ollama pull qwen2.5-coder:7b
.\.venv\Scripts\python.exe -m uvicorn agents.database_agent.main:app --host 127.0.0.1 --port 8001
```

This workspace also includes `Start-Ollama.ps1` in the parent `outputs` folder.
Run it in a normal PowerShell terminal with
`powershell -ExecutionPolicy Bypass -File .\Start-Ollama.ps1` from that folder.
Ollama 0.40.0 and the verified model are already downloaded under `work/`.
The launcher keeps Ollama's profile and models there and changes only its child
process environment. Normal PowerShell is required because the development
sandbox blocks Ollama's path-resolution checks when loading model manifests.
The already-created `.venv` uses bundled Python 3.12 because Python 3.13 was
inaccessible from the development session. No activation command is needed.

## Demo

Open http://127.0.0.1:8001/docs for FastAPI's interactive API page.

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
$body = @{
  task_type = 'database_design'
  description = 'Create a PostgreSQL schema for a library management system with books, members, and loans. Include primary keys, foreign keys, and a due date.'
} | ConvertTo-Json
$result = Invoke-RestMethod http://127.0.0.1:8001/task -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 200
$result.result
```

Successful `/health` response:

```json
{"agent":"database-agent","status":"available","model":"qwen2.5-coder:7b"}
```

`POST /task` returns `agent`, `status`, `model`, `task_type`, and `result`.
The result contains generated SQL and a short explanation. Model output varies;
review it before using it. A completed task means generation completed, not that
PostgreSQL validated the SQL. Health checks that Ollama is reachable and the
model is installed; it does not perform inference or prove GPU readiness.

## Tests and troubleshooting

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_database_agent.py -v
ollama ps
nvidia-smi
```

- 422: invalid input (only `database_design`; description 1-4000 characters).
- 429: another generation is running; retry afterward.
- 503: Ollama is unreachable or the model is missing.
- 504: generation took more than 180 seconds.
- 502: failed, malformed, empty, or truncated model output.

The context is 4096 tokens and output is capped at 1800 tokens. Keep tasks small.
Ollama keeps the model loaded for 10 minutes after generation. `ollama stop
qwen2.5-coder:7b` releases it. Ctrl+C stops the API/foreground Ollama server.

Optional process environment variables: `OLLAMA_BASE_URL` (default
`http://127.0.0.1:11434`) and `OLLAMA_MODEL` (default `qwen2.5-coder:7b`).
Set them before starting the API. `.env` files are not loaded automatically.
The demo binds to localhost; multi-machine networking is a later step.

## Verified local result (2026-10-07)

Five offline tests passed. A direct Qwen request generated a `books` table.
The live API returned an available health response and generated a library
schema (`members`, `books`, `loans`) in 19.27 seconds. Ollama reported 18% CPU /
82% GPU allocation. Sampled peak GPU memory was 4123 MiB of 6144 MiB, with 40%
peak GPU utilization. Available physical RAM after the test was 4.58 GiB.
These are measurements from one small request, not a general benchmark.
The generated SQL was inspected as text and was not executed in PostgreSQL.

## Files and next steps

- `main.py`: routes, input validation, one generation at a time.
- `ollama_client.py`: HTTP calls, model readiness, timeouts and error handling.
- `prompts.py`: database instructions.
- `requirements.txt`: runtime dependencies.
- `requirements-lock.txt`: exact versions installed for this demo.
- `tests/test_database_agent.py`: offline tests; no GPU/model required.

Later: agree team contracts, connect the Master Agent, add task/project/execution
persistence, and have a teammate review/test before any merge. No Git write to
the remote is required to run this prototype.
