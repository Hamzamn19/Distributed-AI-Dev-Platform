# Setup Guide

Owner: Abdurrahman (card S1-02). This is the starting version: please follow
it on a clean PC, fix what does not match and add screenshots where a step is
unclear.

## 1. Install

| Tool | Who | Check |
| --- | --- | --- |
| Git | everyone | `git --version` |
| Python 3.11 or newer | everyone | `python --version` |
| Tailscale | everyone | `tailscale status` |
| Ollama + one model | the master PC in Sprint 1; the six worker PCs in Sprint 2 | `ollama list` |
| Node.js LTS | the master PC (builds the web interface) and Fatma | `node --version` |

On Windows, tick "Add Python to PATH" in the Python installer.

## 2. Get the code

```bash
git clone https://github.com/Hamzamn19/Distributed-AI-Dev-Platform.git
cd Distributed-AI-Dev-Platform
```

## 3. Python environment

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

If PowerShell refuses to run `activate`, run this once and try again:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 4. Fill in `.env`

- `AGENT_TOKEN`: the team secret. The same value on all seven PCs.
- Worker PCs: `AGENT_ID`, `AGENT_NAME`, `AGENT_OWNER`, `AGENT_ROLE_HINT`
  (your entry in `docs/agents.json`), and `MASTER_URL`.
- `LLM_MODEL`: the model installed on this PC.
- `LLM_MOCK=1` runs everything without Ollama (fixed answers), for a first try.
- `LLM_TIMEOUT_SEC`: keep 120 on the master; use 600 on worker PCs.

## 5. Check that it works

```bash
pytest
```

Master PC: build the web interface once (again after every frontend change),
then start the master. It serves the interface and the API on one address.

```bash
cd frontend
npm install
npm run build
cd ..
python -m dap.master
```

- http://localhost:8000 shows the web interface.
- http://localhost:8000/api/v1/health answers `{"status":"ok","version":"0.1.0"}`.
- http://localhost:8000/docs lists the API.

`uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload` still works too.
During frontend development, `cd frontend && npm run dev` serves the interface
with hot reload on http://localhost:5173 and forwards `/api` to the master.

With the master running on `LLM_MOCK=1`, `python scripts/smoke_test.py` checks
the whole decompose/assign flow and prints `SMOKE TEST PASSED`.

## 6. Start a worker

On a worker PC (or in a second terminal on the master PC):

```bash
python -m dap.worker.main
```

The worker starts its A2A server on `WORKER_PORT` (default 9000); the master sends
tasks to it there. It registers with `MASTER_URL` together with its own address,
`WORKER_PUBLIC_URL` (on the tailnet: `http://<this PC's Tailscale IP>:9000`; when
it is empty the worker asks Tailscale itself), and sends a heartbeat every
`HEARTBEAT_INTERVAL_SEC`. The Agents page shows it as `idle`, as `busy` while it
works, and whether the master reaches its A2A server. Stop it with Ctrl+C: after
`HEARTBEAT_TIMEOUT_SEC` (30 s) it shows as `offline`.

The first time a worker starts, Windows Firewall asks whether Python may accept
connections: allow it on private networks. Without that the master cannot send
tasks to this PC. To add the rule by hand (PowerShell as administrator):

```powershell
New-NetFirewallRule -DisplayName "DAP worker 9000" -Direction Inbound -Protocol TCP -LocalPort 9000 -Action Allow
```

On a worker PC set `LLM_TIMEOUT_SEC=600`: writing code with a local model takes
minutes.

Two workers on one PC, for local tests:

```bash
copy .env.worker.example .env.worker1
copy .env.worker.example .env.worker2
# in .env.worker2 change AGENT_ID, AGENT_ROLE_HINT, WORKER_PORT and WORKER_PUBLIC_URL
python -m dap.worker.main --env-file .env.worker1
python -m dap.worker.main --env-file .env.worker2
```

`python scripts/seed_agents.py` registers the six team agents of
`docs/agents.json` at once (they turn offline after 30 s without a worker).

The whole flow on one PC, with two workers and mock answers, in one command:

```bash
python scripts/e2e_local.py      # prints E2E PASSED or the step that failed
```

## 7. Connect the PCs with Tailscale

1. Install Tailscale and sign in with the **shared team account**. (The free
   plan allows 6 users but unlimited devices, so all seven PCs join through
   one account.)
2. On the master PC run `tailscale ip -4`. The `100.x.y.z` address it prints
   does not change.
3. On every worker PC set `MASTER_URL=http://100.x.y.z:8000` and
   `WORKER_PUBLIC_URL=http://<that worker's own Tailscale IP>:9000` in `.env`.
4. The first time the master and each worker start, Windows Firewall asks for
   permission: allow it (master: port 8000, worker: port 9000).
5. From another PC open `http://100.x.y.z:8000` in a browser: the web interface.

Connections go both ways: workers call the master (register, heartbeat) and the
master calls the workers (tasks over A2A). A Cloudflare quick tunnel to the master
alone is therefore not enough any more; use Tailscale.

### First tailnet run (checklist)

Do it in this order; go on only when a step works.

1. **Master PC.** Tailscale on. `cd frontend && npm run build`, then
   `python -m dap.master`. From the master PC open `http://localhost:8000`; from
   any other PC open `http://<master Tailscale IP>:8000`. Both show the web interface.
2. **One worker PC.** Tailscale on. `.env` with `MASTER_URL`, `WORKER_PUBLIC_URL`,
   `AGENT_TOKEN` (the master's value), `AGENT_ID` and the model. Start
   `python -m dap.worker.main`, allow the firewall prompt, then in a second
   terminal run `python scripts/check_connection.py`. All six lines must say OK;
   each FAIL line says the likely fix.
3. **On the master's web interface:** the Agents page shows the worker `idle`
   with "✓ reachable". Create a small project, Decompose, Assign agents, Run on
   agents: its tasks finish on that PC.
4. **All six workers.** Repeat step 2 on each PC (each with its own `AGENT_ID`).
   The Agents page shows six reachable agents; run the sample requirement
   `docs/sample_requirements/orta.md`.

## 8. Ollama

```bash
ollama pull <model>
ollama run <model> "Say hello"
```

Ollama reads only a few thousand tokens of a prompt by default and silently
drops the rest. For long requirement documents set the environment variable
`OLLAMA_CONTEXT_LENGTH` (for example `8192`) before starting Ollama, as far as
the PC's memory allows.

## Problems and fixes

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'dap'` | Run commands from the repository root, with the virtual environment active |
| `/health` works on the master PC but not from another PC | Check `tailscale status` on both PCs; check the firewall prompt; the master must run with `--host 0.0.0.0` |
| Worker gets 401 | `AGENT_TOKEN` differs between the two `.env` files |
| Agents page: worker `idle` but "✗ not reachable" | The master cannot reach the worker's port 9000: firewall on the worker PC, or a wrong `WORKER_PUBLIC_URL`. Run `python scripts/check_connection.py` on the worker |
| Worker says "A2A server could not start" | Another program (or a second worker) uses `WORKER_PORT`; choose another port and update `WORKER_PUBLIC_URL` |
| A task fails with "timeout" | The model needs longer: raise `TASK_TIMEOUT_SEC` on the master and `LLM_TIMEOUT_SEC` on the worker |
| http://localhost:8000 says "Frontend not built" | Run `cd frontend && npm install && npm run build`, then reload |
| Worker gets `Env file not found` | The `--env-file` path is wrong; run from the repository root |
