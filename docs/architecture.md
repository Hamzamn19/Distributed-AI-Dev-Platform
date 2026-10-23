# Architecture

How the Distributed AI Software Development Platform is built (Sprint 3). The
binding names, fields and endpoints are in
[`contracts/PROJECT_CONTRACT.md`](contracts/PROJECT_CONTRACT.md); this page explains
how the parts work together.

```text
                    Browser (any PC on Tailscale)
                               |
                http://<master-ip>:8000   (UI and API on ONE address)
                               |
+--------------------------- MASTER PC -----------------------------+
| FastAPI :8000                                                      |
|   /            -> built React UI (frontend/dist), SPA fallback     |
|   /api/v1/...  -> REST API                                         |
| core: decomposer -> selector -> orchestrator -> integrator         |
| SQLite data/dap.db      workspace/<project_id>/ (git repo)         |
+----------------------------------+--------------------------------+
     ^ register + heartbeat        |  A2A over HTTP+JSON (master is the client)
     | (worker -> master)          v  POST /message:send, GET /tasks/{id}
+------------------------- WORKER PC (x6) ---------------------------+
| FastAPI :9000  A2A server                                          |
|   GET  /.well-known/agent-card.json                                |
|   POST /message:send   (returns a Task immediately)                |
|   GET  /tasks/{id}     (status + artifacts with generated files)   |
| executor thread -> llm_client.chat() -> local Ollama model         |
+--------------------------------------------------------------------+
```

## The parts

| Part | Code | What it does |
| --- | --- | --- |
| Web interface | `frontend/` | Project form, task board, results and files, agents with status and reachability. Built once (`npm run build`); the master serves it. Polls every 3 s. |
| Master API | `dap/master/main.py`, `api/` | REST API under `/api/v1`, plus the UI at `/` |
| Decomposer | `dap/master/core/decomposer.py` | Asks the master's model for four tasks (database, backend, frontend, testing) with titles and descriptions for the requirement; order and dependencies are fixed |
| Selector | `dap/master/core/selector.py` | Scores every online agent for a task: `S = w_c*C + w_r*R + w_x*X + 10*u - 15*q`; the reason is stored and shown |
| Orchestrator | `dap/master/core/orchestrator.py` | Sends ready tasks to their workers over A2A, follows them, collects the results; replaces an offline agent; timeouts |
| Integrator | `dap/master/core/integrator.py` | Copies `templates/webapp/` into `workspace/<project_id>/`, writes each task's files, one git commit per task |
| Database | `dap/master/db/` | SQLite: agents, projects, tasks, events, task results |
| Worker | `dap/worker/` | A2A server, a queue that runs one task at a time with the local model, registration and heartbeats |
| LLM client | `dap/shared/llm_client.py` | Local models only (Ollama, OpenAI-compatible API); `LLM_MOCK=1` for tests |

## One project, step by step

1. **Requirement.** The user enters a requirement document (20 to 12 000
   characters) on the web interface: `POST /projects`.
2. **Decompose.** The master's model splits it into four tasks; each depends on
   the ones before it: database -> backend -> frontend -> testing.
3. **Assign.** For each task the selector scores the online agents with their
   measured capabilities (coding, reasoning, context), the role bonus and the
   current load. The best agent and the reason are stored: the answer to "why
   did this task go to this agent?"
4. **Run.** The orchestrator sends every task whose dependencies are completed
   to its agent's A2A server (`POST /message:send`) with the requirement, the
   files it must fill and the files of the tasks it depends on. Independent
   tasks run in parallel on different PCs; one PC runs its tasks one after another.
5. **Execute.** The worker builds a prompt from the template file and asks its
   local model; the answer must contain exactly the task's files. The worker
   then loads every new Python file next to the files of the earlier tasks; on
   an error (for example a missing import) the model gets the error message and
   corrects its files, at most twice, before the task counts as failed.
6. **Collect.** The master polls `GET /tasks/{id}`. A completed task's files are
   committed to `workspace/<project_id>/`; every result (or error) is stored and
   shown on the web interface.
7. **Result.** When all four tasks are completed, `workspace/<project_id>/` is a
   runnable application (`uvicorn backend.main:app`) whose git log shows which
   agent wrote which part.

## Network

All PCs are in one Tailscale network. Connections go both ways: workers call
the master on port 8000 (register, heartbeat), the master calls the workers on
port 9000 (tasks). Every call between them carries the team's `X-Agent-Token`.
The setup and a first-run checklist are in [`SETUP.md`](SETUP.md);
`scripts/check_connection.py` tests a worker PC.

## What is deliberately simple

- No queue system, no WebSocket or SSE: the database holds the state, the UI polls.
- The A2A subset is written by hand (three operations); the deviations from the
  specification are listed in contract section 13.
- The generated application always has the same shape (FastAPI + SQLite + plain
  HTML/JavaScript), so small local models only fill in files.
- Retrying failed tasks on another agent, automated tests of the generated app
  and a code review agent are Sprint 4.
