# Project Contract

The technical agreement of the team. Every name, path and value here is
binding. If an AI assistant suggests a different name, the contract wins.

The full plan (roles, roadmap, Sprint 1 cards, risks) lives in the team's
shared plan document. This file is the copy of its technical section that
travels with the code. Okan keeps the two in sync.

Version 1.1 (18 October 2026): adds the Sprint 2 selection formula, the task
taxonomy, capability measurement and the requirement length limit.

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

- The **master** runs on one PC: a FastAPI server with a SQLite database.
- Six **workers** run on six other PCs. All run the same program; only `.env` differs.
- Workers call the master. The master never calls a worker, so only the
  master's address has to be reachable.
- The PCs reach each other over Tailscale: `MASTER_URL=http://<master Tailscale IP>:8000`.
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
| Master API | `http://localhost:8000`, prefix `/api/v1` |
| API docs | `http://localhost:8000/docs` |
| Frontend (dev) | `http://localhost:5173` |
| Ollama | `http://localhost:11434/v1` (reached only from its own PC) |
| Worker | no port; it only sends requests |

All environment variables are listed in `.env.example`. Settings are read from
`.env`; no model name, address or port is written in code.

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
AgentRegister  agent_id, name, owner, role_hint, model, provider, capabilities
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
LLMResponse    text, prompt_tokens, completion_tokens, duration_ms
```

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
| 3 | `GET /agents/{agent_id}/tasks/next` | - | 200 Task or 204 | worker |
| 3 | `POST /tasks/{id}/result` | TaskResult | 200 Task | worker |
| 4 | `POST /tasks/{id}/reassign` | - | 200 Task | frontend |
| 5 | `GET /metrics/agents` | - | time, success rate, tokens per agent | frontend |

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
| `agents` | 1 | agent_id (PK), name, owner, role_hint, model, provider, cap_coding, cap_reasoning, cap_context, status, current_task_id, registered_at, last_heartbeat_at |
| `projects` | 1 | id (PK), name, requirement_text, status, created_at, updated_at |
| `tasks` | 1 | id (PK), project_id (FK), title, description, type, status, depends_on (JSON), assigned_agent_id (FK, nullable), assignment_reason, attempt, created_at, updated_at |
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

Before the tasks are handed out, the master writes one short sketch of the
generated app's endpoints and tables and adds it to every task as context,
so no agent invents its own endpoints or tables. Its exact shape is fixed in
Sprint 3. The files of a project go to `workspace/<project_id>/`, which is
never committed.
