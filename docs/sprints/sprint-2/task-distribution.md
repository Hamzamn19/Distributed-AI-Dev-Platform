# Sprint 2 Task Distribution (git-based)

Owner: Hamza (Scrum Master). Same rules as Sprint 1: Trello mirrors status; git tracks
the work — one branch per card, one owner per branch, one PR per card, no direct pushes
to `main`. GitHub Issues #21–#30 are the authoritative card list.

Branch convention: `feature/<S2-XX>-<short-name>` (suggestions in the table).
Commit convention: `S2-XX: <what changed>`.
Before every commit: run `pytest`, then `git status` — only your own folders may change.

## Order (who waits for whom)

1. Can first (all 13 repository functions back; Baran's endpoints wait on the agent+project side).
2. Baran ports the working prototype into `dap/` (S2-01) — everyone downstream waits for this.
3. Eray: measure models while waiting (S2-04 has no dependency), then the worker loop (S2-03).
4. Fatma: task board screens on mock, switch to real API after S2-01.
5. Abdurrahman: network runbook + 2-machine proof first (S2-09), then seed/smoke/CI (S2-07).
6. Okan: review PR #20, merge contract v1.1, publish taxonomy (S2-08). Hamza: planning/Trello/report (S2-10).

## Cards

| Card | Owner | Branch | Folders | Key files | Blocked by | Done when |
| --- | --- | --- | --- | --- | --- | --- |
| S2-01 | Baran | `feature/S2-01-dap-port` | `dap/master/core/`, `dap/master/cli.py`, `dap/shared/` | `decomposer.py`, `selector.py`, `cli.py`, `llm_client.py` | Can repos + Eray `chat()` | Thursday demo flow runs identically from `dap/` paths; `master/` deleted; `pytest` green incl. 1 end-to-end decompose test |
| S2-02 | Baran | `feature/S2-02-score-selection` | `dap/master/core/` | `selector.py` | S2-01 | Selection by score proven by tests; `/assign` uses it |
| S2-03 | Eray | `feature/S2-03-worker-loop` | `dap/worker/` | `main.py`, `master_client.py` | S2-01 (`/agents/{id}/tasks/next` + result endpoints) | One worker on a second PC completes a task end-to-end; files land in `workspace/` |
| S2-04 | Eray | `feature/S2-04-measure-models` | `scripts/` (w/ Abdurrahman), `docs/` | `measure_model.py`, `agents.json` scores, `models.md` | none | Six rows measured with the same 5 questions; method reproducible |
| S2-05 | Can | `feature/S2-05-repos-events` | `dap/master/db/`, `tests/` | `repositories.py` (+13 funcs), `events`+`task_results` tables | none | Suite green including persistence across master restart; task files under `workspace/<run-id>/` |
| S2-06 | Fatma | `feature/S2-06-taskboard` | `frontend/src/` | pages + `client.ts` | none (mock) | `decompose → assign` flow visible live end-to-end; all calls via `client.ts`; desktop+mobile widths; English UI |
| S2-07 | Abdurrahman | `feature/S2-07-seed-smoke-ci` | `scripts/`, `.github/`, root | `seed_agents.py`, `smoke_test.py`, `ci.yml` | S2-01 for the full flow | CI green on a test PR; smoke passes on the master PC (`LLM_MOCK=1`) |
| S2-08 | Okan | `feature/S2-08-contract-v11` | `docs/contracts/`, `docs/` | `PROJECT_CONTRACT.md`, taxonomy doc | PR #20 review first | One contract, no proposal file, taxonomy referenced by S2-02 |
| S2-09 | Abdurrahman | `feature/S2-09-network-runbook` | `docs/` | `SETUP.md` Tailscale section, `network-test.md` | none | Table complete (member | Tailscale IP | reachable); 1 worker registers + heartbeats from a second PC |
| S2-10 | Hamza | `feature/S2-10-planning-report` | `docs/sprints/` | `sprint-2/planning.md`, this file, `report.md` | none | Report filed; retro produced one change for Sprint 3 |

## Leftovers from Sprint 1 folded into Sprint 2

| Sprint 1 item | Goes to |
| --- | --- |
| Baran's prototype logic in `master/` | S2-01 (then delete `master/`) |
| Score-based assignment (contract A3) | S2-02 |
| Worker register/heartbeat beyond the stub | S2-03 |
| `docs/models.md` + real capability measurements | S2-04 |
| Can's project/task branch of the repository (slipped from the Thursday cut) | S2-05 |
| UI polish + form + agents detail | S2-06 |
| `scripts/seed_agents.py`, `smoke_test.py`, CI | S2-07 |
| Requirements/models/architecture/library docs | S2-04/S2-08/Okan's regular docs work |
| Tailscale runbook + 2-machine proof | S2-09 |

## Daily routine (Hamza, group channel, 2–3x per week)

1. What did you finish (branch + PR link)? 2. What is next (card + step)? 3. What blocks you?
Weekly: update the burndown sheet (S2-10) and, every Thursday, run the 30-minute
integration checkpoint on the master PC (retro action from Sprint 1: register +
decompose + assign under `LLM_MOCK=1` + one look at the UI).

## Master and models (unchanged from Sprint 1 decision)

Master PC: Baran's (Mac M5, 24 GB unified memory). Workers run
`qwen3:4b` (`docs/agents.json`) until S2-04 replaces estimated scores with measured ones.
Conflict to resolve in S2-08: the contract's "no two PCs share a model" vs six identical
models — decide then, record in the contract, in this file and in `docs/agents.json`.
