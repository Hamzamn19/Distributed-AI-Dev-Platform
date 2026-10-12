# Worker Agent

Owner: Eray.

## What it does

Runs on each of the six worker PCs. It tells the master "I am here"
(register), then "I am still here" every 10 seconds (heartbeat). From Sprint 3
it also asks for tasks, runs them with the local LLM and sends the result back.

## How to run

From the repository root, with the virtual environment active and `.env` filled in:

```bash
python -m dap.worker.main
```

The worker opens no port. It only needs to reach `MASTER_URL`.

## Input and output

- Input: the worker block of `.env` (`MASTER_URL`, `AGENT_ID`, `AGENT_ROLE_HINT`, ...).
- Output: HTTP requests to the master, shaped like `AgentRegister` and
  `Heartbeat` in `dap/shared/schemas.py`.

## Connections

| Talks to | How |
| --- | --- |
| Master | `dap/worker/master_client.py`, with the `X-Agent-Token` header |
| LLM | `dap.shared.llm_client.chat()` (from Sprint 3) |

## Status

Sprint 1 skeleton: `config.py` is ready; `main.py` and `master_client.py` are
described in their docstrings and still to be written (card S1-07).
