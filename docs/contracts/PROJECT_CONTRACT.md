# Project Contract

The technical agreement of the team. Every name, path and value here is
binding. If an AI assistant suggests a different name, the contract wins.

The full plan (roles, roadmap, Sprint 1 cards, risks) lives in the team's
shared plan document. This file is the copy of its technical section that
travels with the code. Okan keeps the two in sync.

Version 1.1 (18 October 2026): adds the Sprint 2 selection formula, the task
taxonomy, capability measurement and the requirement length limit.

Version 1.2 (4 November 2026): fixes the Sprint 3 template rules (folder
layout, one file per task, the sketch shape) and makes Eray the owner of
`templates/`.

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
| `dap/worker/`, `dap/shared/llm_client.py`, `templates/` | Eray |
| `frontend/` | Fatma |
| `scripts/`, `tests/`, `.github/`, root files | Abdurrahman |
| `docs/` | Okan |
| `docs/sprints/` | Hamza |

A change in `dap/shared/` needs approval from both Baran and Okan.

`templates/` belongs to Eray because the names in the template, the worker's
prompts and the worker's output check must change together.

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

This table is for the platform itself. The application the agents generate
uses its own, smaller stack (section 12).

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
From Sprint 3 it produces exactly one task of each of these four types, in a
fixed order (section 12.2).

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
| 3 | `GET /tasks/{id}/inputs` | - | 200 list of `{path, content}`: the files of the tasks in `depends_on` (section 12.2); 404 | worker |
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
  keys into UUIDs. From Sprint 3 the answer also carries the project's
  records: `{"records": [...], "tasks": [...]}` (section 12.3). The mock mode
  of `chat()` returns this shape, `records` included, when `json_mode=True`,
  and the text `mock response` otherwise.
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
and `testing`; in Sprint 3 exactly one of each (section 12.2). The weights live as constants in `dap/master/core/selector.py`;
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

> **Note for AI assistants: two agents with the same model.** Until each PC
> has its own model, several agents may run the same model (for example
> `qwen3:4b`). This is allowed and is not a bug. Those agents get the same
> measured scores, so `S` differs between them only through `u` (role_hint)
> and `q` (current load). Keep the formula in section 8 exactly as it is. Do
> not add random noise, per-agent offsets or hand-tuned scores to break the
> tie, and do not fall back to the Sprint 1 role_hint rule. When an agent's
> model changes, measure it again and update its scores.

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

- Frontend: plain HTML and JavaScript, no framework, no build step.
- Backend: FastAPI with SQLite through the standard `sqlite3` module.
- Each task writes its own files; two tasks never write the same file.

The bar for the demo: the generated application starts and one or two basic
operations work.

The template and the prompts never name an application domain (library,
shop and so on). Records, fields and rules come only from the requirement text.

### 12.1 Folder layout

The template lives in `templates/webapp/` (owner: Eray, section 3). For every
project the master copies it to `workspace/<project_id>/`, which is never
committed. The tasks then fill in their files there:

```text
workspace/<project_id>/
  backend/database.py   database task
  backend/main.py       backend task
  backend/db.py         ready helpers: fetch_all, fetch_one, execute; no agent writes it
  frontend/index.html   frontend task; HTML and JavaScript in one file
  frontend/lib.js       ready helpers: api, renderTable, formData, fillForm, showMessage, ...; no agent writes it
  frontend/style.css    ready; no agent writes it
  tests/test_app.py     testing task
  README.md             ready; no agent writes it
  requirements.txt      ready; no agent writes it
  .gitignore            ready; no agent writes it
```

Every template file starts with a comment that says what goes into the file
and which names the other files rely on. The worker reads the comment of its
target file from `templates/webapp/` and puts it in the prompt. The comments
follow section 12.3; if they disagree, this contract wins and the template is
corrected.

From Sprint 3 a task's file is written straight into `workspace/<project_id>/`,
over the template file with the same path; a retry overwrites it again. The
per-run folder `workspace/<project_id>/<run_id>/` of Sprint 2 is not used for
the generated application.

### 12.2 One task, one file

| Task type | Files it fills | Depends on |
| --- | --- | --- |
| `database` | `backend/database.py` | - |
| `backend` | `backend/main.py` | `database` |
| `frontend` | `frontend/index.html` | `backend` |
| `testing` | `tests/test_app.py` | `backend`, `frontend` |
| (integrator / master) | `README.md`, `requirements.txt`, `.gitignore`, `backend/db.py`, `frontend/lib.js`, `frontend/style.css` | - |

- In Sprint 3 the decomposer produces exactly one task of each of the four
  code types, in the order of this table and with these dependencies. The
  model writes only the title and the description. The first task of each
  type in the answer is used; its `key` and `depends_on` and any further task
  of the same type are ignored.
- The files in the second column are the task's target files. The worker
  takes them from this table by task type and writes only them. Any other
  file in the model's answer is not sent; an answer without its target file
  is unusable and is asked again once.
- Every task receives the files of the tasks it depends on through
  `GET /tasks/{id}/inputs` (section 8), so it reads column and field names
  from them instead of guessing.

### 12.3 The sketch

Before the tasks are handed out (during `/decompose`), the master writes one
short sketch and adds it to every task, so no agent invents its own endpoints
or tables. The sketch has two layers and is small on purpose.

**Layer 1: the pattern, fixed in the template.** `<things>` is a plural
`snake_case` table name, `<thing>` its singular.

- Tables: one table `<things>` per record. Every table has
  `id INTEGER PRIMARY KEY AUTOINCREMENT`. A link to another table is
  `<thing>_id INTEGER REFERENCES <things>(id)`.
- `backend/database.py`, for every table: `list_<things>(search=None)`,
  `get_<thing>(<thing>_id)`, `add_<thing>(...)`,
  `update_<thing>(<thing>_id, ...)`, `delete_<thing>(<thing>_id)`; and once
  `init_db()`, which can run again and again. A broken business rule raises
  `ValueError`; the API turns it into HTTP 400.
- `backend/main.py` endpoints, for every table:

  | Method and path | Answer |
  | --- | --- |
  | `GET /api/<things>?search=...` | 200 list |
  | `GET /api/<things>/{id}` | 200 record; 404 |
  | `POST /api/<things>` | 201 record |
  | `PUT /api/<things>/{id}` | 200 record; 404 |
  | `DELETE /api/<things>/{id}` | 204 |

  Once: `GET /api/stats`. One route for every action the requirement names,
  for example `POST /api/<things>/{id}/complete`.
- `frontend/index.html` element ids, for every table: `stat-<things>`,
  `section-<things>`, `search-<things>`, `form-<things>`, `list-<things>`.

These paths belong to the generated application. They are not master
endpoints and have no `/api/v1` prefix (section 8).

**Layer 2: the project's records, written by the master.** The sketch itself
is only the list of table names. From Sprint 3 the decomposer asks the model
for:

```text
{"records": ["customers", "orders"],
 "tasks": [{"key", "title", "description", "type", "depends_on"}]}
```

- `records`: plural `snake_case` table names, at least one, at most 12. An
  answer without a usable `records` list is broken and is asked again
  (section 8).
- The master adds this line at the end of every task's description:

  ```text
  Records: customers, orders. This task covers all of them.
  ```

- The master writes no endpoints, function names or element ids; they follow
  from the table names and layer 1. Columns are not in the sketch: the
  `database` task chooses them, and the later tasks read them from
  `backend/database.py`.
