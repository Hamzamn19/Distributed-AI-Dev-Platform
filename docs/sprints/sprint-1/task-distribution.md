# Sprint 1 Task Distribution (git-based)

Owner: Hamza (Scrum Master). Trello tracks status
(Sprint Backlog -> In Progress -> In Review -> Done); git tracks the work:
one branch per card, one owner per branch, PR per card. No direct push to `main`.

Team decision (Oct 12): GitHub Issues (#2-#12) are the single authoritative task
reference for Sprint 1; Trello is a secondary formal mirror for the course only.
Any other card list (CSV imports, starter guides) is reference material, never
a task source. Card IDs S1-01..S1-11 mean what the Issues say.

Branch convention: `feature/<CARD>-<short-name>`, e.g. `feature/S1-07-worker-register`.
Commit convention: `<CARD>: <what changed>`, e.g. `S1-07: add heartbeat loop`.
Before every commit: run `pytest`, then `git status` (only your own folders may change).

## Order (who waits for whom)

1. Can (agent repo functions) + Eray (`chat()` + mock) first — Baran waits for both.
2. Baran (endpoints, decompose, assign) — everyone else waits for him.
3. Fatma (real API), Eray (worker), Abdurrahman (seed + smoke scripts) after Baran.
4. Okan + Hamza run in parallel, no dependencies.

## Cards

| Card | Owner | Branch | Folders | Key files | Blocked by | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| S1-01 | Hamza | `feature/S1-01-trello-planning` | `docs/sprints/` | `sprint-1/planning.md`, this file | — | 11 Trello cards with checklists; planning minutes filed |
| S1-02 | Abdurrahman | `feature/S1-02-setup-guide` | root, `docs/SETUP.md` | `.env.example`, `requirements.txt`, `pytest.ini` | — | teammate finishes setup following only the guide |
| S1-03 | Okan | `feature/S1-03-requirements` | `docs/` | `requirements.md`, `sample_requirements/library.md`, `architecture.md` | — | all Sprint 1 instructor items map to a requirement |
| S1-04 | Fatma | `feature/S1-04-web-ui` | `frontend/` | `src/api/client.ts`, `src/pages/` (3 pages) | Baran endpoints | 3 pages on real API, no mock data, 3s refresh |
| S1-05 | Baran | `feature/S1-05-master-api` | `dap/master/api/` | `agents.py`, `projects.py` (endpoints) | Can agent funcs | register/heartbeat/list + create/list/get work via curl |
| S1-06 | Baran | `feature/S1-06-decompose-assign` | `dap/master/core/`, `cli.py` | `decomposer.py`, `selector.py` | Eray `chat()`, Can project funcs | sample doc -> 4 task types with agents + reasons |
| S1-07 | Eray | `feature/S1-07-worker-register` | `dap/worker/`, `dap/shared/llm_client.py` | `llm_client.py`, `master_client.py`, `main.py` | Baran agent endpoints (to test) | worker shows idle in `GET /agents`; re-registers alone |
| S1-08 | Okan | `feature/S1-08-agent-inventory` | `docs/` | `models.md`, `agents.json` | — | 6 workers in `agents.json`, no two share a model |
| S1-09 | Can | `feature/S1-09-database` | `dap/master/db/` | `database.py`, `models.py`, `repositories.py` | — | 13 functions written, `pytest` green |
| S1-10 | Abdurrahman | `feature/S1-10-smoke-final` | `scripts/`, `tests/` | `seed_agents.py`, `smoke_test.py` | Baran endpoints | `smoke_test.py` passes with `LLM_MOCK=1`; final checks filed |
| S1-11 | Hamza | `feature/S1-11-review-report` | `docs/sprints/` | `sprint-1/report.md` | all above | demo held, report filed with test results |

## Model setup per machine (Sprint 1 decision: `qwen3:4b` for all workers, upgrade later)

Qwen machines (Okan, Abdurrahman, Fatma, Can, Eray) — Ollama:
```bash
ollama pull qwen3:4b
```
`docs/agents.json` already pins all six workers to `qwen3:4b`.

Master PC (team decision): Baran's PC, model via Ollama; Baran proceeds with a small
local model until S1-08 is final. Workers reach it at
`http://<Baran Tailscale IP>:8000` (Hamza's own Tailscale IP is `100.116.89.127` —
that is a worker address, not the master). Okan records any change in the contract.

## Daily routine (Hamza asks in the group channel, 2-3x per week)

1. What did you finish (branch + PR link)?
2. What is next (card + step)?
3. Blockers — critical dates first: shared contract in `main` (done),
   `chat()` mock + agent repo funcs (Oct 13), master endpoints + `agents.json`
   (Oct 14), decompose + assign + real API frontend (Oct 15), remote worker +
   smoke (Oct 16), final checks (Oct 17), review + report (Oct 18).

## Thursday emergency demo scope (cut Oct 12: team on full university days)

Goal for Thursday is reduced to one sentence: the models are reachable and the
master answers through an interface. Everything else moves to Sprint 2.

P0 — must work Thursday (demo fails without it):
- Master boots on Baran's PC: `GET /api/v1/health` returns ok (S1-05 minimal).
- `POST /agents/register` + heartbeat accept one worker from another PC (S1-05 minimal).
- Every PC: `ollama pull qwen3:4b` done; `ollama run qwen3:4b "Hello"` answers (S1-08 minimal).
- One real model call through the master path (CLI or `/docs`), rest may run on `LLM_MOCK=1`.
- `pytest` green; `docs/sprints/sprint-1/report.md` filed honestly (reached / partly).

P1 — include only if P0 is green by Wednesday night:
- `decompose` + `assign` on the library sample (S1-06); task list visible in UI (S1-04).
- `scripts/seed_agents.py` + `smoke_test.py` (S1-10).

P2 — explicitly moved to Sprint 2: full UI polish, `docs/models.md`/`requirements.md`/
`architecture.md`/`database.md` finishes, capability measurement, score-based assignment.

Per-person micro-task (30-60 min each, Tue-Wed):
Baran: boot + register endpoints (needs only Can's `upsert_agent`/`list_agents`).
Can: `database.py` + `models.py` + agent functions only; project/task functions slip to Sprint 2.
Eray: `chat()` + mock only; worker loop slips unless time remains.
Fatma: pages render (mock allowed); real-API wiring only in P1.
Okan: `library.md` sample only (demo input); other docs slip.
Abdurrahman: Tailscale addresses collected + manual health checks; scripts only in P1.
Hamza: mirror Trello, collect outputs, write report.
