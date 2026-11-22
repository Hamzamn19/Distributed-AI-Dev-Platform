# Project Contract

The technical agreement of the team. Every name, path and value here is
binding. If an AI assistant suggests a different name, the contract wins.

The full plan (roles, roadmap, Sprint 1 cards, risks) lives in the team's
shared plan document. This file is the copy of its technical section that
travels with the code. Okan keeps the two in sync.

Version 1.1 (18 October 2026): adds the Sprint 2 selection formula, the task
taxonomy, capability measurement and the requirement length limit.

Version 1.2 (Sprint 3): the master serves the web interface and the API on one
address, and sends tasks to the workers over A2A (section 13). The endpoints
planned earlier for workers to pull tasks and post results are removed.

## 1. How to use this file with an AI assistant

An AI tool that opens the repository (Antigravity, Claude Code, Cursor and
similar) reads `AGENTS.md` and this file by itself. This prompt is enough:

```text
Read AGENTS.md and follow it. I am <NAME>. Do my next task for the current sprint.
```

A chat assistant that cannot see the repository needs the files pasted in:
`AGENTS.md`, this whole file, your section of the current
`docs/sprints/sprint-N/member-guide.md` and the file you are filling in,
with this header:

```text
Below is my team's project contract. It is binding.

I am: <NAME>
My module and folder: <e.g. Worker Agent, dap/worker/>
Today's task: <card id and title, e.g. S1-07 LLM client + worker registration stub>

Rules:
1. Create or change files only in my folder.
2. Use endpoint paths, JSON field names, enum values, ports and environment
   variable names exactly as in the contract. Do not invent new ones.
3. Import data models from dap/shared. Do not redefine them.
4. If the contract is missing something or contradicts itself, tell me before
   writing code.
5. Code, comments and interface text are in English.
6. Show the implementation plan first; write code after I approve. At the end,
   tell me step by step how to run and test it.

<THIS WHOLE FILE>
```

Three rules prevent most integration problems:

1. Nobody changes the contract alone. Write to Okan first; the contract is
   updated, then the code.
2. Everybody writes code only in their own folder (section 3).
3. Use the current version of this file in every session.

## 2. Architecture in five sentences

- The **master** runs on one PC: a FastAPI server with a SQLite database. It
  serves the web interface and the API on one address, `http://<master>:8000`.
- Six **workers** run on six other PCs. All run the same program; only `.env` differs.
- Each worker registers with the master and sends heartbeats (worker -> master).
  The master sends each task to its worker over A2A and asks for its status
  (master -> worker, port 9000; section 13).
- The PCs reach each other over Tailscale: `MASTER_URL=http://<master Tailscale IP>:8000`
  on every worker, `WORKER_PUBLIC_URL=http://<worker Tailscale IP>:9000` for its A2A server.
- The frontend asks the master again every 3 seconds. No WebSocket, no SSE.

## 3. Folder ownership

| Folder | Owner |
| --- | --- |
| `dap/master/api/`, `dap/master/core/`, `dap/master/cli.py`, `dap/shared/enums.py`, `dap/shared/schemas.py` | Baran |
| `dap/master/db/` | Can |
| `dap/worker/`, `dap/shared/llm_client.py` | Eray |
| `frontend/` | Fatma |
| `scripts/`, `tests/`, `.github/`, root files | Abdurrahman |
| `docs/` | Okan |
| `docs/sprints/` | Hamza |

A change in `dap/shared/` needs approval from both Baran and Okan.

## 4. Technology

| Layer | Decision |
| --- | --- |
| Language | Python 3.11+ (master, worker), TypeScript (frontend) |
| Master API | FastAPI + Uvicorn, Pydantic v2 |
| Database | SQLite + SQLAlchemy 2.x; address from `DATABASE_URL` |
| HTTP client | httpx |
| LLM | Local models only (Ollama), through the OpenAI-compatible `/v1/chat/completions` API and the `openai` package |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Tests | pytest, FastAPI TestClient |
| Not used | Celery, Redis, RabbitMQ, Socket.io, WebSocket, SSE, LangChain, LangGraph, PostgreSQL, cloud LLM APIs |

## 5. Ports, addresses, environment variables

| Service | Address |
| --- | --- |
| Master | `http://localhost:8000`: web interface at `/`, API prefix `/api/v1` |
| API docs | `http://localhost:8000/docs` |
| Frontend (development only) | `http://localhost:5173`; forwards `/api` to the master on :8000 |
| Ollama | `http://localhost:11434/v1` (reached only from its own PC) |
| Worker | A2A server on `0.0.0.0:9000`; the master calls it (section 13) |

All environment variables are listed in `.env.example`; two workers on one PC
use `.env.worker.example`. Settings are read from `.env` (a worker started with
`--env-file <file>` reads that file instead); no model name, address or port is
written in code. Added in Sprint 3:

| Name | Where | Default | Meaning |
| --- | --- | --- | --- |
| `WORKER_HOST` | worker | `0.0.0.0` | A2A server bind address |
| `WORKER_PORT` | worker | `9000` | A2A server port |
| `WORKER_PUBLIC_URL` | worker | empty | Address the master uses, e.g. `http://100.x.y.z:9000`. Empty: `tailscale ip -4`, else `http://127.0.0.1:<WORKER_PORT>` with a warning |
| `TASK_TIMEOUT_SEC` | master | `900` | A task not finished after this is marked `failed` |
| `A2A_POLL_INTERVAL_SEC` | master | `3` | How often the master asks a worker for task status |
| `PREVIEW_PORT` | master | `8100` | Port where "Open the app" runs a generated application on the master PC (from Sprint 3) |
| `LLM_TIMEOUT_SEC` | both | `120` | Seconds to wait for one model answer; use 600 on worker PCs |
| `LLM_THINK` | both | `0` | `0`: requests ask reasoning models not to think first (`chat_template_kwargs.enable_thinking=false`, read by llama.cpp's llama-server); `1`: thinking allowed |
| `LLM_MAX_TOKENS` | both | `8192` | Most tokens of one model answer when the caller gives no limit |
| `MOCK_DELAY_SEC` | worker | `0` | With `LLM_MOCK=1`: seconds a mock task takes (demos show the agent busy) |
| `VITE_API_BASE_URL` | frontend | empty | Empty means the relative `/api/v1`; set only for unusual setups |

`POLL_INTERVAL_SEC` is no longer used.

## 6. Enums

Lowercase strings with underscores. Source of truth: `dap/shared/enums.py`.

```text
AgentStatus:   idle | busy | offline
TaskType:      requirements_analysis | frontend | backend | database |
               testing | code_review | integration | documentation
TaskStatus:    pending | assigned | in_progress | completed | failed
ProjectStatus: created | decomposing | in_progress | integrating | completed | failed
```

Task flow: `pending` -> `assigned` (master chose an agent) -> `in_progress`
(worker took it) -> `completed` or `failed`. A failed task returns to `pending`
with `attempt` + 1, at most 3 attempts.

The Sprint 1 decomposer produces only `frontend`, `backend`, `database`, `testing`.

## 7. Data models

Source of truth: `dap/shared/schemas.py`. General rules:

- Field names are `snake_case` everywhere; the frontend does not convert them.
- Project and task ids are UUID4 strings made by the master. The agent id comes from `.env`.
- Time fields end with `_at`, are UTC and ISO 8601 (`2026-10-05T18:00:00Z`).
- A field without a value is sent as `null`, never left out.
- Unknown fields are rejected (HTTP 422).
- Every error answer is `{"detail": "message"}` with the right HTTP status.
- `requirement_text` must be 20 to 12 000 characters long (HTTP 422 otherwise).
  A longer document is split by the user and submitted in parts.

```text
AgentRegister  agent_id, name, owner, role_hint, model, provider, capabilities,
               a2a_url                                            (a2a_url: Sprint 3)
Agent          AgentRegister + status, current_task_id, registered_at, last_heartbeat_at
Capabilities   coding, reasoning, context          (each 0-100)
Heartbeat      status, current_task_id
ProjectCreate  name, requirement_text
Project        id, name, requirement_text, status, created_at, updated_at
TaskCreate     id, title, description, type, depends_on
Task           id, project_id, title, description, type, status, depends_on,
               assigned_agent_id, assignment_reason, attempt, created_at, updated_at
TaskResult     task_id, agent_id, success, summary, files[{path, content}],
               error, duration_ms, tokens_used                    (Sprint 3)
DapTaskPayload task_id, project_id, type, title, description, requirement_text,
               target_files[path], dependency_files[{path, content}]   (Sprint 3)
DapTaskOutput  summary, files[{path, content}], prompt_tokens, completion_tokens,
               duration_ms                                        (Sprint 3)
LLMResponse    text, prompt_tokens, completion_tokens, duration_ms
```

`a2a_url` is the address of the worker's A2A server (null for an agent without
one). `DapTaskPayload` and `DapTaskOutput` travel inside A2A messages (section
13); the master stores each output as a `TaskResult`.

`depends_on` is a list of task ids. `assignment_reason` is a short text saying
why the master chose that agent; the interface shows it.

## 8. API, database and module interfaces

All paths start with `/api/v1`. Endpoints called by workers need the
`X-Agent-Token` header (401 when wrong).

| Sprint | Method and path | Body | Answer | Caller |
| --- | --- | --- | --- | --- |
| 1 | `GET /health` | - | `{"status": "ok", "version": "0.1.0"}` | anyone |
| 1 | `POST /agents/register` | AgentRegister | 200 Agent; same `agent_id` again updates the record | worker |
| 1 | `POST /agents/{agent_id}/heartbeat` | Heartbeat | 200 `{"ok": true}`; 404 when not registered | worker |
| 1 | `GET /agents` | - | list of Agent | frontend |
| 1 | `POST /projects` | ProjectCreate | 201 Project | frontend |
| 1 | `GET /projects` | - | list of Project | frontend |
| 1 | `GET /projects/{id}` | - | Project; 404 | frontend |
| 1 | `POST /projects/{id}/decompose` | - | 200 list of Task | frontend |
| 1 | `GET /projects/{id}/tasks` | - | list of Task | frontend |
| 1 | `POST /projects/{id}/assign` | - | list of Task with `assigned_agent_id` and `assignment_reason` | frontend |
| 3 | `GET /agents/{agent_id}/card` | - | the worker's A2A agent card, fetched by the master; 404 unknown agent or no A2A address; 502 the master cannot reach the worker | frontend |
| 3 | `POST /projects/{id}/run` | - | 202 Project; starts sending the assigned tasks to the workers; 409 while a run is going | frontend |
| 3 | `GET /projects/{id}/results` | - | list of TaskResult | frontend |
| 3 | `GET /projects/{id}/files` | - | list of file paths in `workspace/<project_id>/` | frontend |
| 3 | `GET /projects/{id}/files/{path}` | - | the file as text; 404; a path outside the project folder is refused | frontend |
| 3 | `POST /projects/{id}/preview` | - | 200 `{"project_id", "port"}`: the generated application runs on `PREVIEW_PORT` of the master (one at a time); 409 without a written backend, 502 when it does not start | frontend |
| 4 | `POST /tasks/{id}/reassign` | - | 200 Task | frontend |
| 5 | `GET /metrics/agents` | - | time, success rate, tokens per agent | frontend |

Workers do not pull tasks: the master sends them over A2A and collects the
results (section 13).

Sprint 1 `/assign` rule: a task goes to the agent whose `role_hint` equals the
task type; whether the agent is online is not checked. Sprint 2 switches to
capability scores without changing the path or the answer.

Sprint 2 `/assign` rule: the candidates are the agents whose status is not
`offline`. For each candidate the master computes

```text
S = w_c * C + w_r * R + w_x * X + 10 * u - 15 * q
```

- `C`, `R`, `X`: the agent's `capabilities` (coding, reasoning, context, 0-100).
- `w_c`, `w_r`, `w_x`: the weights of the task type (section 9).
- `u`: 1 when the agent's `role_hint` equals the task type, otherwise 0.
- `q`: the number of the agent's tasks with status `assigned` or `in_progress`.

The highest `S` wins. On a tie, the agent with `u = 1` wins, then the smaller
`agent_id`. With no candidate the task stays `pending`. `assignment_reason`
states `S` and its parts, so the interface can show why this agent was chosen.

Database tables:

| Table | Sprint | Columns |
| --- | --- | --- |
| `agents` | 1 | agent_id (PK), name, owner, role_hint, model, provider, cap_coding, cap_reasoning, cap_context, status, current_task_id, registered_at, last_heartbeat_at; a2a_url (Sprint 3) |
| `projects` | 1 | id (PK), name, requirement_text, status, created_at, updated_at |
| `tasks` | 1 | id (PK), project_id (FK), title, description, type, status, depends_on (JSON), assigned_agent_id (FK, nullable), assignment_reason, attempt, created_at, updated_at; remote_task_id (Sprint 3: the worker's A2A task id) |
| `events` | 2 | id, project_id, task_id, agent_id, type, message, created_at |
| `task_results` | 3 | id, task_id (FK), agent_id (FK), success, summary, files (JSON), error, duration_ms, tokens_used, created_at |

Module interfaces (signatures are fixed; see the files for details):

```python
# dap/master/db/repositories.py   (Can writes, Baran calls)
upsert_agent(data: AgentRegister) -> Agent
get_agent(agent_id: str) -> Agent | None
list_agents() -> list[Agent]
touch_heartbeat(agent_id: str, status: AgentStatus, current_task_id: str | None) -> bool
mark_stale_agents_offline(timeout_sec: int) -> int
create_project(data: ProjectCreate) -> Project
get_project(project_id: str) -> Project | None
list_projects() -> list[Project]
set_project_status(project_id: str, status: ProjectStatus) -> None
create_tasks(project_id: str, tasks: list[TaskCreate]) -> list[Task]
list_tasks(project_id: str) -> list[Task]
get_task(task_id: str) -> Task | None
assign_task(task_id: str, agent_id: str, reason: str) -> Task
set_task_status(task_id: str, status: TaskStatus, remote_task_id: str | None = None) -> Task
increment_attempt(task_id: str) -> Task                             # Sprint 3

# dap/master/db/results.py        (Can writes, Baran calls)          Sprint 3
store_task_result(data: TaskResult, *, run_id: str) -> TaskResult   # one per task and run
list_project_results(project_id: str) -> list[TaskResult]
record_event(event_type: str, message: str, *, project_id=None, task_id=None,
             agent_id=None) -> str

# dap/shared/llm_client.py        (Eray writes; master and worker call)
chat(messages: list[dict], *, temperature: float = 0.2,
     max_tokens: int | None = None, json_mode: bool = False) -> LLMResponse
health_check() -> bool

# dap/master/core                 (Baran)
decompose(requirement_text: str) -> list[TaskCreate]
select_agent(task: Task, agents: list[Agent]) -> tuple[Agent, str] | None
```

`api/` and `core/` never use SQL or a database session; they call the
repository functions. Repository functions return the models in
`dap/shared/schemas.py`, never ORM objects.

Agreed behaviour between modules:

- Importing `dap.master.db.repositories` creates the tables. Callers do nothing extra.
  A column added in a later sprint is added to an older `data/dap.db` at start
  (`ALTER TABLE`); deleting `data/dap.db` also works.
- For decomposition the model is asked for
  `{"tasks": [{"key", "title", "description", "type", "depends_on"}]}`, where
  `key` is a temporary name and `depends_on` lists keys. The decomposer turns
  keys into UUIDs. The mock mode of `chat()` returns this shape when
  `json_mode=True`, and the text `mock response` otherwise.
- When the model cannot be reached `chat()` raises `RuntimeError`.
  `/decompose` then sets the project to `failed` and answers 502.
- `/decompose` on a project that already has tasks returns the existing tasks.
- Tests never touch `data/dap.db`: `tests/conftest.py` points `DATABASE_URL`
  at `data/test.db` and sets `LLM_MOCK=1`.

Frontend: every request goes through `frontend/src/api/client.ts`
(`getAgents`, `createProject`, `getProjects`, `getProject`, `decomposeProject`,
`assignProject`, `getTasks`). `types.ts` matches section 7 field by field.

## 9. Task taxonomy

The eight `TaskType` values, when each is used and the weights `/assign` uses
for it (section 8). No other type exists; a new one needs a contract change.

| Type | When it is used | Created by | From sprint | w_c | w_r | w_x |
| --- | --- | --- | --- | --- | --- | --- |
| `frontend` | Pages, forms, client-side logic of the generated app | decomposer | 1 | 0.6 | 0.2 | 0.2 |
| `backend` | API endpoints and business rules | decomposer | 1 | 0.5 | 0.3 | 0.2 |
| `database` | Tables, relations, seed data | decomposer | 1 | 0.4 | 0.4 | 0.2 |
| `testing` | Tests for the generated code | decomposer | 1 | 0.4 | 0.4 | 0.2 |
| `code_review` | A short review of another task's files | master, one per code task | 4 | 0.2 | 0.5 | 0.3 |
| `integration` | Joining the parts into one runnable app | master, one per project | 4 | 0.3 | 0.3 | 0.4 |
| `requirements_analysis` | Reading the requirement and planning the tasks | master itself; never assigned to a worker | 1 | 0.1 | 0.6 | 0.3 |
| `documentation` | README and usage notes of the generated app | master, optional | 5 | 0.1 | 0.4 | 0.5 |

Until Sprint 4 the decomposer produces only `frontend`, `backend`, `database`
and `testing`. The weights live as constants in `dap/master/core/selector.py`;
tuning them is a Sprint 5 activity.

## 10. Capability measurement (from Sprint 2)

The Sprint 1 capability scores are estimates. In Sprint 2 every worker model
answers the same five questions: two coding tasks (scored by unit tests), two
reasoning questions with a checked answer, one context question (find a fact
in a long text). Each dimension gets a score from 0 to 100. The scores replace
the estimates in `docs/agents.json` and in each worker's `.env`
(`AGENT_CAP_*`). A model change means measuring again.

Goal: every worker PC runs a different model, so the measured scores differ
and the score-based selection in section 8 has something to compare.

From 17 November 2026: the five questions turned out too easy (every model
scored 100 in coding and context, a 4B model tied with a 26B one), so they no
longer rank the models. The scores are now set from the model itself: its size,
whether it is trained for code, its quantization and its measured speed, keeping
the measured results where they separate the models. `docs/models.md` gives the
reason for every score; a model change means setting its score again there.

> **Note for AI assistants: two agents with the same model.** Until each PC
> has its own model, several agents may run the same model (for example
> `qwen3:4b`). This is allowed and is not a bug. Those agents get the same
> measured scores, so `S` differs between them only through `u` (role_hint)
> and `q` (current load). Keep the formula in section 8 exactly as it is. Do
> not add random noise or per-agent offsets to break the tie, and do not fall
> back to the Sprint 1 role_hint rule. Scores follow the model (see above and
> `docs/models.md`), never the person; when an agent's model changes, set its
> scores again there.

## 11. Working rules

- Nobody pushes to `main` directly. Work on `feature/<card-id>-short-name`,
  for example `feature/S1-07-worker-register`, and open a pull request.
- Ask a teammate to look at the pull request. If nobody has reviewed it within
  a day, merge it yourself.
- A commit message starts with the card id: `S1-05: add health endpoint`.
- Start every session with `git pull origin main`. A branch lives two days at most.
- `.env`, `data/` and `workspace/` are never committed.

Definition of Done:

1. The code is in `main` through a pull request.
2. It follows this contract; settings come from `.env`; no secret is in the repo.
3. `pytest` passes, and `scripts/smoke_test.py` passes once it exists.

## 12. The generated application (from Sprint 3)

The agents do not write an application from scratch. They fill in a fixed
template, so small local models can succeed and a broken part is easy to find:

- Frontend: plain HTML and JavaScript, no build step.
- Backend: FastAPI with SQLite.
- Each task writes its own files; two tasks never write the same file.

The bar for the demo: the generated application starts and one or two basic
operations work. The template gets its own folder in Sprint 3.

The template is in `templates/webapp/`; the integrator copies it into every
project. It is the shared sketch: every template file starts with a comment
saying what goes there and which names the other files rely on, so no agent
invents its own endpoints or tables. In Sprint 3 the decomposer produces exactly
one task per code type, in a fixed order with fixed dependencies (the model
writes the titles and descriptions); each task fills fixed files:

| Task type | Files it fills | Depends on |
| --- | --- | --- |
| `database` | `backend/database.py` | - |
| `backend` | `backend/main.py` | database |
| `frontend` | `frontend/index.html` (the HTML and its JavaScript in one file) | backend |
| `testing` | `tests/test_app.py` | backend, frontend |
| (integrator) | `README.md`, `requirements.txt`, `.gitignore`, and the ready helpers `backend/db.py`, `frontend/lib.js`, `frontend/style.css`, `tests/conftest.py` (test database and the `client` fixture; no agent writes them) | - |

The template and the prompts name no domain: the records, fields and rules come
from the requirement and the task descriptions, so the instructor can choose any
application. Before a worker returns its files it checks what the next agents rely
on (`dap/worker/executor.py`, `verify()`): `init_db()` runs twice, every table has
its `list_/get_/add_/update_/delete_` functions, `main.py` calls only defined
database functions and its GET routes answer, the page calls only existing routes
and element ids, and the generated tests run. A problem goes back to the model
(at most two corrections), with the likely cause of known mistakes (for example
WHERE after ORDER BY); a repeated identical answer is named as such. Some failing
or erroring generated tests are accepted after the last correction, with the
count in the task summary.

When every task is completed, the master runs its acceptance check
(`dap/master/core/acceptance.py`, no model): it loads a copy of the application
and tries `GET /`, `GET /api/stats` and, for every `/api/<things>` route (and every
record of the decomposer's list), list, search, create (a body made from
`/openapi.json`), get, update, delete and get again (404). A 400 answer is a rule
saying no, not a failure. The result is `acceptance.json` in the project folder,
with its own commit (`master: acceptance check (...)`); an application that does not
start fails the project. So the testing task tests only what the requirement says:
one create-and-list test per record type, then its business rules and actions.

A worker may only write the files of its task (`target_files`). The files of a
project go to `workspace/<project_id>/`, a git repository with one commit per
completed task (`"<task type>: <title> (by <agent_id>)"`). `workspace/` is
never committed to the team repository. The master starts every file an agent
wrote with one comment naming that agent, in the comment syntax of the file
(`#`, `//`, `/* */`, `<!-- -->`; in HTML after the doctype), for example
`# Written by agent-eray (Eray-PC, model qwen2.5-coder:7b) - database task "...", 2026-11-22 21:40 UTC`.
The ready template files get none.

## 13. A2A between master and workers (from Sprint 3)

Workers run a small A2A server (A2A protocol v1.0, HTTP+JSON binding,
https://a2a-protocol.org/latest/specification/); the master is the client. We
implement three operations, by hand with FastAPI, Pydantic and httpx:

| Operation | Worker endpoint | Notes |
| --- | --- | --- |
| Agent Card | `GET /.well-known/agent-card.json` | no token |
| SendMessage | `POST /message:send` | the master always sends `configuration.returnImmediately: true`; answer `{"task": Task}` |
| GetTask | `GET /tasks/{id}` | the master polls it every `A2A_POLL_INTERVAL_SEC`; answer: the Task |

Every master -> worker request carries `X-Agent-Token` (401 when wrong) and
`A2A-Version: 1.0`. Not implemented: streaming, push notifications, ListTasks,
CancelTask, SubscribeToTask, the extended agent card (the card says
`"streaming": false, "pushNotifications": false`).

Wire rules: camelCase field names, enum names such as `TASK_STATE_COMPLETED`
and `ROLE_USER`, parts without a `kind` field (`{"text": ...}` or
`{"data": ..., "mediaType": "application/json"}`). The models are in
`dap/shared/schemas.py` (`AgentCard`, `SendMessageRequest`, `A2ATask`, ...).

- The message has a text part (the task title) and a data part with a
  `DapTaskPayload`; `contextId` is the project id.
- A finished task has one artifact named `result` whose data part is a
  `DapTaskOutput`. A failed task has `status.message` with a text part that
  explains the error.
- States: `TASK_STATE_SUBMITTED`, `TASK_STATE_WORKING`, `TASK_STATE_COMPLETED`,
  `TASK_STATE_FAILED`, stored as `in_progress`, `in_progress`, `completed`, `failed`.
- A worker runs one task at a time, in the order received; a message sent
  while it is busy is accepted and queued.
- Before it answers, the worker checks the files: exactly the task's
  `target_files`, none empty, and every Python file loads next to the template
  and the files of all earlier tasks (`dependency_files` holds the whole chain).
  On a problem the model gets the error text and answers again, at most twice;
  still wrong, the task fails with that error.
- At `/run`, a task whose agent is offline is assigned again among the online
  agents with the section 8 rule; with no online agent it fails with
  "no online agent". A task whose dependency failed fails with
  "dependency failed". A new `/run` (the UI's "Run again") sends the failed tasks
  again, with `attempt` + 1. Choosing another agent within one run is Sprint 4.

Deviations from the specification, chosen for simplicity:

- Error answers use this contract's `{"detail": "message"}` (unknown task 404,
  bad body 422, wrong token 401), not the specification's `google.rpc.Status`.
- Workers accept `application/json` and `application/a2a+json` request bodies
  and answer with `application/json`.
