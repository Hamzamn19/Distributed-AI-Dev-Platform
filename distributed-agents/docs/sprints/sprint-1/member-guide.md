# Sprint 1 Member Guide

What each member writes in Sprint 1 (5-18 October 2026), file by file.
AI agents: read "Shared agreements" and the section with your member's name.

Sprint goal: a working master that takes a requirement, splits it into tasks,
assigns each task to an agent and stores it all in the database; the result is
visible in the web interface. Workers do not write code yet.

## The prompt

Open the repository folder in your AI tool, run `git pull origin main`, and
write this, changing only the name:

```text
Read AGENTS.md and follow it. I am <NAME>. Do my next task for the current sprint.
```

The tool shows a plan first; approve it, then it writes the code. For one
specific job, change the last sentence, for example `Do card S1-07, step 2.`
Before you commit, run `git status` and check that only your own files changed.

## Ready files (do not change)

`dap/shared/enums.py`, `dap/shared/schemas.py`, `dap/master/config.py`,
`dap/worker/config.py`, `dap/master/main.py`, `dap/master/api/health.py`,
`frontend/src/api/types.ts`, `tests/conftest.py`. If one of them needs a
change, ask Okan first.

## Order

```text
First (wait for nobody)         Then (master endpoints)         Last (use the endpoints)
Can: agent repository      -->  Baran: agent endpoints     -->  Eray: worker
Can: project/task repository -> Baran: decompose + assign  -->  Fatma: real API
Eray: llm_client.chat()    -->  Baran: decompose + assign  -->  Abdurrahman: scripts
```

While waiting: Fatma builds the pages with mock data, Eray writes the worker,
Abdurrahman finishes the setup guide and Tailscale. Okan's model inventory
decides which PC runs the master, so it comes first among Okan's steps.

## Shared agreements

These bind more than one member's code.

1. **Tables.** Importing `dap.master.db.repositories` creates the tables
   (it calls `init_db()` from `database.py` once). Callers do nothing extra.
2. **Model answer format for decomposition.** Baran's prompt asks the model
   for this JSON. Eray's mock mode returns the same shape when
   `json_mode=True`, so decomposition also works on a PC without Ollama.

   ```json
   {
     "tasks": [
       {"key": "T1", "title": "Design database schema", "description": "...", "type": "database", "depends_on": []},
       {"key": "T2", "title": "Build REST API", "description": "...", "type": "backend", "depends_on": ["T1"]},
       {"key": "T3", "title": "Build web pages", "description": "...", "type": "frontend", "depends_on": ["T2"]},
       {"key": "T4", "title": "Write tests", "description": "...", "type": "testing", "depends_on": ["T2", "T3"]}
     ]
   }
   ```

   `key` is a temporary name inside the model's answer. The decomposer gives
   every task a UUID and translates the keys in `depends_on` into those UUIDs.
   With `json_mode=False` the mock returns the plain text `mock response`.
3. **LLM failure.** `chat()` raises `RuntimeError` with a clear message.
   `/decompose` then sets the project status to `failed` and answers 502 with
   `{"detail": "..."}`.
4. **Decompose twice.** `/decompose` on a project that already has tasks
   returns the existing tasks and creates nothing.
5. **Test database.** Tests never touch `data/dap.db`. `tests/conftest.py`
   points `DATABASE_URL` at `data/test.db` and sets `LLM_MOCK=1`.

## Baran

Cards: S1-05 Master Agent core + API, S1-06 Task breakdown + simple assignment.
Folders: `dap/master/api/`, `dap/master/core/`, `dap/master/cli.py`.
Waits for: Can's repository functions (steps 1-2), Eray's `chat()` (step 3).
Endpoints can be written before those exist; they raise `NotImplementedError`
when called until then.

1. `dap/master/api/agents.py`
   - `require_agent_token`: compares the `X-Agent-Token` header with
     `get_settings().agent_token`; 401 when different.
   - `POST /register` (token): `upsert_agent(data)`, returns `Agent`.
   - `POST /{agent_id}/heartbeat` (token): `touch_heartbeat(...)`; 404 when it
     returns `False`, otherwise `{"ok": true}`.
   - `GET` list: `mark_stale_agents_offline(settings.heartbeat_timeout_sec)`,
     then `list_agents()`.
2. `dap/master/api/projects.py`
   - `POST` (201): `create_project(data)`.
   - `GET` list, `GET /{id}` (404 when missing), `GET /{id}/tasks`.
   - `POST /{id}/decompose`: status `decomposing`, `decompose(text)`,
     `create_tasks(...)`, status `in_progress`. See agreements 3 and 4.
   - `POST /{id}/assign`: for every `pending` task call
     `select_agent(task, agents)`; when it returns a result call
     `assign_task(task.id, agent.agent_id, reason)`. Returns the task list.
3. `dap/master/core/decomposer.py`
   - `decompose(requirement_text)`: system message with the rules and the JSON
     format of agreement 2, user message with the requirement text;
     `chat(messages, json_mode=True)`.
   - Parse with `json.loads` and validate: every type is one of
     `SPRINT1_TASK_TYPES`, and each of the four types has at least one task.
   - Give each task `str(uuid.uuid4())`, translate `depends_on`, return
     `list[TaskCreate]`.
   - Broken answer: retry once, then return a fixed template with one task per type.
4. `dap/master/core/selector.py`
   - `select_agent(task, agents)`: the first agent whose `role_hint` equals
     `task.type`, with a reason such as
     `role_hint 'backend' matches task type 'backend'`. `None` when nobody matches.
5. `dap/master/cli.py`
   - Reads the given file, creates a project, decomposes, assigns, and prints
     the tasks with type, agent and reason.
6. `dap/master/README.md`: update "Status" as endpoints are added.

How to check: with `LLM_MOCK=1`, start the master and use
`http://localhost:8000/docs` to register an agent, create a project, then
decompose, assign and list tasks. Then try the sample library document with
`LLM_MOCK=0` and the real model.

Done when: the sample document gives at least one task for each of the four
types, every task has an agent and a reason, and with Ollama stopped the
master answers with an error instead of crashing.

Notes: the master's model is decided by card S1-08; use a small model until
then. For long documents set the `OLLAMA_CONTEXT_LENGTH` environment variable
(for example 8192) before starting Ollama, or the end of the text is silently cut.

## Can

Card: S1-09 Database schema + repository.
Folder: `dap/master/db/`. Waits for nobody. Write the agent functions first:
Baran's endpoints wait for them.

1. `dap/master/db/database.py`
   - Reads the address from `get_settings().database_url`.
   - Defines `engine`, `SessionLocal`, `Base`; creates the SQLite file's folder
     (`data/`) when missing.
   - `init_db()`: creates the tables.
2. `dap/master/db/models.py`
   - Tables `agents`, `projects`, `tasks` with the columns in the file's docstring.
   - `type` and `status` columns accept only the values in `dap/shared/enums.py`.
   - `depends_on` is a JSON column; time columns are `DateTime`.
3. `dap/master/db/repositories.py`
   - Calls `init_db()` once when imported (agreement 1).
   - First: `upsert_agent`, `get_agent`, `list_agents`, `touch_heartbeat`,
     `mark_stale_agents_offline`.
   - Then: `create_project`, `get_project`, `list_projects`,
     `set_project_status`, `create_tasks`, `list_tasks`, `get_task`, `assign_task`.
   - Each function opens and closes its own session and returns models from
     `dap/shared/schemas.py`. Signatures do not change.
   - SQLite drops the timezone. Fix every datetime read from the database with
     `value.replace(tzinfo=timezone.utc)`; the schemas reject naive datetimes.
   - `Capabilities` maps to the columns `cap_coding`, `cap_reasoning`, `cap_context`.
4. `tests/test_repositories.py`
   - An agent is stored and read back; the same `agent_id` again updates it;
     heartbeat for an unknown agent returns `False`; a stale agent becomes
     `offline`; a project and its tasks are stored and read back;
     `assign_task` sets the status to `assigned`.
5. `docs/database.md`
   - ER diagram of the three tables (a Mermaid `erDiagram` block is enough)
     and a few sample queries.

How to check: `pytest` passes. After the master has started once,
`data/dap.db` exists; records are still there after a restart.

Done when: all 13 functions are written, tests pass, and an invalid `status`
value is rejected.

## Eray

Card: S1-07 LLM client + worker registration stub.
Folders: `dap/worker/`, `dap/shared/llm_client.py`.
Write `llm_client.py` first: Baran's decomposer waits for it. Testing the
worker needs Baran's agent endpoints. To try `chat()` with a real model,
install Ollama and a small model on your own PC.

1. `dap/shared/llm_client.py`
   - Reads `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MOCK` from the environment.
   - `chat()`: uses the `openai` package (`OpenAI(base_url=..., api_key=...)`).
     With `json_mode=True` adds `response_format={"type": "json_object"}`.
   - Measures the duration, takes token counts from the answer's `usage`,
     removes a `<think>...</think>` block, returns `LLMResponse`.
   - 120 second timeout and one retry. See agreement 3 for failures.
   - Mock mode (`LLM_MOCK=1`): no model call; see agreement 2 for what it
     returns; token counts are 0.
   - `health_check()`: `True` in mock mode; otherwise tries to list the
     server's models and returns `True` or `False`.
2. `dap/worker/master_client.py`
   - `register(payload)`: `httpx` `POST {api_url}/agents/register`, body
     `payload.model_dump(mode="json")`, header `X-Agent-Token`; reads the
     answer with `Agent.model_validate(...)`.
   - `send_heartbeat(agent_id, heartbeat)`:
     `POST {api_url}/agents/{agent_id}/heartbeat`; returns `False` on 404.
   - Address and token come from `get_settings()` in `dap/worker/config.py`.
3. `dap/worker/main.py`
   - Reads the settings and registers with `settings.to_register_payload()`.
     When the master is unreachable it waits a few seconds and tries again.
   - Sends a heartbeat with status `idle` every `HEARTBEAT_INTERVAL_SEC`.
     Registers again when `send_heartbeat` returns `False`.
   - Stops cleanly on Ctrl+C. No LLM call in this sprint.
4. `dap/worker/README.md`: update "Status".

How to check:

```bash
python -c "from dap.shared.llm_client import chat; print(chat([{'role': 'user', 'content': 'Say hello'}]))"
uvicorn dap.master.main:app --host 0.0.0.0 --port 8000     # terminal 1
python -m dap.worker.main                                   # terminal 2
```

Open `http://localhost:8000/api/v1/agents`: the worker is `idle`; after
stopping it, it becomes `offline` within 30 seconds; after restarting the
master, the worker registers again by itself.

Done when: those three checks work, and together with Abdurrahman at least one
worker registers from a different PC over Tailscale.

## Fatma

Card: S1-04 Web interface skeleton.
Folder: `frontend/`. Build the pages with mock data first; connect to the real
API when Baran's endpoints are in `main`.

1. Setup (from the repository root)
   - `npm create vite@latest frontend -- --template react-ts`; when asked about
     the non-empty folder choose "Ignore files and continue".
   - Add Tailwind CSS following its current Vite guide; install `react-router-dom`.
   - Copy `frontend/.env.example` to `frontend/.env`.
2. `frontend/src/api/client.ts`
   - Base address: `import.meta.env.VITE_API_BASE_URL + "/api/v1"`.
   - The seven functions below. On a failed answer throw an error with the
     body's `detail` text. Pages never call `fetch` directly.

   | Function | Request | Returns |
   | --- | --- | --- |
   | `getAgents()` | `GET /agents` | `Agent[]` |
   | `createProject(data)` | `POST /projects` | `Project` |
   | `getProjects()` | `GET /projects` | `Project[]` |
   | `getProject(id)` | `GET /projects/{id}` | `Project` |
   | `decomposeProject(id)` | `POST /projects/{id}/decompose` | `Task[]` |
   | `assignProject(id)` | `POST /projects/{id}/assign` | `Task[]` |
   | `getTasks(id)` | `GET /projects/{id}/tasks` | `Task[]` |

3. `frontend/src/api/mock.ts`
   - Sample agents, a project and tasks typed with `types.ts`. The client
     functions return this data until the endpoints exist; then they are
     replaced with real calls and this file is deleted.
4. `frontend/src/pages/`
   - `NewProjectPage.tsx` (`/`): project name and requirement text. Submit is
     disabled while the text is shorter than 20 characters; shows loading and
     error states; goes to the project page on success. Lists existing
     projects below the form.
   - `ProjectPage.tsx` (`/projects/:id`): project name and status; the flow
     Requirement, Master, Tasks; "Decompose" and "Assign agents" buttons; task
     table (title, type, status, assigned agent, reason, depends on).
     Refreshes every 3 seconds.
   - `AgentsPage.tsx` (`/agents`): name, owner, model, `role_hint`, the three
     scores and status (shown with both colour and text). Refreshes every 3 seconds.
5. `frontend/README.md`: update the run steps.

How to check: master in one terminal, `cd frontend` and `npm run dev` in
another, open `http://localhost:5173`. Create a project, press Decompose and
Assign agents, and the task table fills.

Done when: mock data is removed, the three pages work with the real API, the
layout works at desktop and phone widths, all interface text is in English.

## Abdurrahman

Cards: S1-02 Repo skeleton + setup guide, S1-10 Test infrastructure + final checks.
Folders: `scripts/`, `tests/`, `docs/SETUP.md`. Steps 3-5 need Baran's endpoints.

1. `docs/SETUP.md`
   - Follow it from start to end on a clean PC; fix every step that does not
     match; add a screenshot where a step is unclear.
2. Tailscale
   - Create the shared team account and share the sign-in with the team; all
     seven PCs join with it.
   - Post the master PC's `tailscale ip -4` address to the group; everyone
     sets `MASTER_URL` in `.env`.
3. `scripts/seed_agents.py`
   - Reads `docs/agents.json` and sends each entry to
     `POST {MASTER_URL}/api/v1/agents/register`. `MASTER_URL` and
     `AGENT_TOKEN` come from the environment.
4. `scripts/smoke_test.py`
   - Calls in order: health, register one agent, create project, decompose,
     assign, tasks. Checks the status code and the fields at each step.
   - Prints `SMOKE TEST PASSED` and exits 0, or names the failed step and exits 1.
   - Must also pass while the master runs with `LLM_MOCK=1`.
5. Final checks (last two days of the sprint)
   - Data created: in the sample project every task has an agent and a reason.
   - Data stored: after a master restart the project and tasks are still
     there; task count and type-to-agent mapping are consistent.
   - Failure: with Ollama stopped, decompose answers with an error and the
     project status becomes `failed`.
   - Give the results to Hamza for the sprint report.

How to check: with the master running, `python scripts/seed_agents.py` and
`python scripts/smoke_test.py`. With Eray, open
`http://<master Tailscale address>:8000/api/v1/health` from another PC and
start a worker there.

## Okan

Cards: S1-03 Requirements + sample requirement document, S1-08 Agent listing.
Folder: `docs/`. No code.

1. `docs/models.md` (first)
   - One table with every member's OS, RAM, GPU and VRAM, free disk.
   - Decide the master's PC and model first: the PC with the strongest GPU
     runs the master.
   - Then one local model per worker PC, fitting its role and hardware; no two
     PCs share a model. Write "to be decided" where no decision exists yet.
2. `docs/agents.json`
   - Replace the `to-be-decided` model values with the chosen models. Scores
     stay estimates until Sprint 2. Do not rename fields; `pytest` checks the format.
3. `docs/sample_requirements/library.md`
   - A 1-2 page requirement for an online library management system, in
     English: roles (member, librarian), screens, stored data (book, member,
     loan), rules (loan period, maximum books at once).
4. `docs/requirements.md`
   - The platform's own requirements: purpose, users, numbered functional
     requirements (FR-1, FR-2, ...), non-functional requirements, and which
     sprint covers each. Every Sprint 1 item of the instructor maps to at
     least one requirement.
5. `docs/architecture.md`
   - A summary of the architecture and the architecture diagram as an image.
6. Outside the repo
   - Replace `<owner>` in `README.md` and `docs/SETUP.md` with the GitHub user name.
   - Fill the Product Backlog in Trello with the epics of the five sprints.
   - Collect contract change requests; a change goes into
     `docs/PROJECT_CONTRACT.md` first.
   - At sprint end, run the six success steps in `planning.md` one by one.

## Hamza

Cards: S1-01 Trello board + sprint planning, S1-11 Sprint review, retrospective, report.
Folder: `docs/sprints/sprint-1/`.

1. Trello
   - Five lists, seven labels, the 11 cards with their checklists.
   - Ask for a short written status two or three times a week: what I did,
     what I will do, what blocks me.
2. `docs/sprints/sprint-1/planning.md`
   - Fill in "Meeting notes": date, attendees, decisions.
3. `docs/sprints/sprint-1/report.md` (last day of the sprint)
   - Sections: sprint goal and result; completed cards with pull request
     links; unfinished cards and reasons; demo summary and screenshots;
     blockers and decisions; test results; retrospective summary and proposal
     for Sprint 2.
   - Test results come from Abdurrahman, demo screenshots from Fatma. Add a
     screenshot of the Trello board at sprint end to the same folder.
4. Review and retrospective
   - In the review, Okan's six success steps are shown live.
   - In the retrospective, agree on one thing to change in Sprint 2 and write
     it in the report.
