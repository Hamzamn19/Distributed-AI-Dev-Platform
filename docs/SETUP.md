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
| Node.js LTS | Fatma (frontend) | `node --version` |

On Windows, tick "Add Python to PATH" in the Python installer.

## 2. Get the code

```bash
git clone https://github.com/<owner>/distributed-agents.git
cd distributed-agents
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

## 5. Check that it works

```bash
pytest
uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/api/v1/health. You should see
`{"status":"ok","version":"0.1.0"}`.

## 6. Connect the PCs with Tailscale

1. Install Tailscale and sign in with the **shared team account**. (The free
   plan allows 6 users but unlimited devices, so all seven PCs join through
   one account.)
2. On the master PC run `tailscale ip -4`. The `100.x.y.z` address it prints
   does not change.
3. On every worker PC set `MASTER_URL=http://100.x.y.z:8000` in `.env`.
4. The first time the master starts, Windows Firewall asks for permission:
   allow it.
5. From another PC open `http://100.x.y.z:8000/api/v1/health` in a browser.

Backup when Tailscale does not work: on the master PC run
`cloudflared tunnel --url http://localhost:8000` and use the printed
`https://....trycloudflare.com` address as `MASTER_URL`. The address changes
every time the tunnel restarts.

## 7. Ollama (master PC)

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
