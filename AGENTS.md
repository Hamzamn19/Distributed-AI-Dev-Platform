# AGENTS.md

Instructions for AI coding agents working in this repository. Follow them in
every session. They exist so that seven people, each working with their own
AI assistant, produce code that fits together.

## The project

A course project (CM6453 Software Processes): a platform that turns a
requirement document into a small web application. One **master** PC plans and
assigns tasks; six **worker** PCs carry them out with local LLMs. Keep
everything as simple as a course project allows.

## Before you write anything

1. Find out who you are working for. If the user has not said their name, ask.

   | Member | Owns |
   | --- | --- |
   | Baran | `dap/master/api/`, `dap/master/core/`, `dap/master/cli.py`, `dap/master/main.py` |
   | Can | `dap/master/db/` |
   | Eray | `dap/worker/`, `dap/shared/llm_client.py` |
   | Fatma | `frontend/` |
   | Abdurrahman | `scripts/`, `tests/`, `.github/`, `docs/SETUP.md`, root files |
   | Okan | `docs/` (except `docs/sprints/`), `AGENTS.md` |
   | Hamza | `docs/sprints/` |

2. Read `docs/contracts/PROJECT_CONTRACT.md` completely. It fixes every shared name.
3. Find the current sprint: the highest-numbered folder in `docs/sprints/`
   that contains `member-guide.md`. Read its "Shared agreements" section and
   the section with the member's name.
4. Read the docstring at the top of every file you are going to fill in.

## Choosing what to do

- If the user names a card or a step, do that one.
- Otherwise take the member's first unfinished step in the member guide.
  A function that still raises `NotImplementedError`, or a file the guide
  lists that does not exist yet, is unfinished.
- If a step depends on someone else's code that is not in `main` yet, say so
  and take the member's next step that does not depend on it.
- Work on one step at a time. First show a short plan (files, functions, how
  it will be tested) and wait for the member to approve it. Then write code.

## Rules

1. Write only in the member's own folders. The one exception: a member may
   add a test file for their own code in `tests/` (`test_<module>.py`).
   If another folder needs a change, stop and say what is needed and who owns it.
2. Never change a name the contract fixes: endpoint paths, JSON field names,
   enum values, ports, environment variable names, function names and
   signatures. `dap/shared/enums.py` and `dap/shared/schemas.py` are read-only.
3. If the contract or the member guide is missing something, or the two
   disagree, stop and tell the member to ask Okan. Do not invent an answer.
4. Settings come from `.env` through `dap/master/config.py` and
   `dap/worker/config.py`. Never write a model name, address, port or token in
   code. Never print or commit `.env`.
5. Add a package only when the step cannot be done without it. Then add it to
   `requirements.txt` and tell the member to mention it in the pull request.
6. Code, comments, commit messages and interface text are in English. Talk to
   the member in the language they use.
7. Keep it simple. No extra layers, no features the guide does not ask for.
   Not used in this project: Celery, Redis, RabbitMQ, Socket.io, WebSocket,
   SSE, LangChain, LangGraph, cloud LLM APIs.
8. Do not reformat, rename or "improve" code you were not asked to change.

## Git

- Start: `git pull origin main`, then
  `git checkout -b feature/<card-id>-<short-name>` (example:
  `feature/S1-07-worker-register`).
- Before committing: run `pytest`, then `git status`. Only the member's own
  files may appear. Undo any other change.
- Commit messages start with the card id: `S1-07: add heartbeat loop`.
- Never push to `main`. Ask before pushing the branch; then tell the member to
  open a pull request on GitHub.

## When you finish a step

Tell the member, briefly:

1. The `pytest` result.
2. How to try the change by hand (exact commands or the page to open).
3. Which files changed.
4. What comes next in the member guide, and who was waiting for this step.

If the behaviour of a folder changed, update the "Status" part of its `README.md`.

## Commands

Run everything from the repository root, with the virtual environment active.

```bash
pytest                                                             # tests
uvicorn dap.master.main:app --host 0.0.0.0 --port 8000 --reload    # master
python -m dap.worker.main                                          # worker
cd frontend && npm run dev                                         # web interface
```

Set `LLM_MOCK=1` in `.env` to run the master without Ollama.
