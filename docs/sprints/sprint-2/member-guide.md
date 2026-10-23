# Sprint 2 Member Guide

What each member writes in Sprint 2 (15–29 October 2026), card by card.
AI agents: read "Shared agreements", then the section with your member's name.
Card source of truth: GitHub Issues #21–#30 (this guide mirrors them; if they
disagree, the Issues win — report it to Hamza).

## The prompt

```text
Read AGENTS.md and follow it. I am <NAME>. Do my next task for the current sprint.
```

For one specific job, change the last sentence, for example `Do card S2-03, step 2.`
Show the plan first; commit only after `pytest` and `git status` cleanliness.

## Backlog

| Owner | Cards | Issues |
| --- | --- | --- |
| Baran | S2-01, S2-02 | #21, #22 |
| Can | S2-05 | #25 |
| Eray | S2-04, S2-03 | #24, #23 |
| Fatma | S2-06 | #26 |
| Abdurrahman | S2-09, S2-07 | #29, #27 |
| Okan | S2-08 | #28 |
| Hamza | S2-10 | #30 |

## Shared agreements

1. **One master after S2-01.** The working prototype `master/` is a read-only reference
   until Baran's port passes the Thursday script; then it is deleted. No new code may
   connect to it (Issues #6, #21; Okan's PR-#32 review: bridge only, not permanent).
2. **Field names are frozen.** `types.ts` and `schemas.py` are the contract shapes.
   Sprint 1 lesson: aliases and field renames (online→idle style) are temporary bridges,
   never the solution. Nobody edits shared names (AGENTS.md rule 2).
3. **Tokens.** Only worker endpoints (`/agents/register`, `/agents/{id}/heartbeat`, and
   the new task endpoints in S2-01) carry `X-Agent-Token`. GET endpoints stay tokenless.
   `CORS_ORIGINS` must come from `.env` (AGENTS.md rule 4), never hardcoded `*`.
4. **LLM mock mode unchanged.** `LLM_MOCK=1` returns agreement-2 shape JSON with
   `json_mode=True`; the voice demo flow must run on mock in the Thursday checkpoints.
5. **Task types.** Until Okan's taxonomy lands (S2-08), aim only at the four Sprint 1
   types: frontend, backend, database, testing. The taxonomy may expand to eight types
   when the contract amendment merges; selector weights (S2-02) must then match it —
   do not freeze S2-02 weights before S2-08.
6. **Orders of the day.** Can first two days → Baran (port) → Eray (loop) → Fatma
   (wiring); Abdurrahman/Okan/Hamza parallel. Thursday: 30-minute integration checkpoint
   on the master PC (register + decompose + assign on `LLM_MOCK=1`, one look at the UI).
7. **Tests.** `tests/conftest.py` keeps pointing `DATABASE_URL` at `data/test.db`;
   never touch `data/dap.db`.

Ready files (do not change without Okan): `dap/shared/enums.py`, `dap/shared/schemas.py`,
`dap/master/config.py`, `dap/worker/config.py`, `dap/master/main.py`. `frontend/src/api/types.ts`.

## Baran — S2-01 then S2-02

1. S2-01: port the verified prototype into contract paths, behaviour unchanged:
   - `master/decomposer.py` → `dap/master/core/decomposer.py` (subtasks→tasks,
     task_type→type; only frontend/backend/database/testing for now)
   - `master/router.py` scoring → `dap/master/core/selector.py`
   - `master/main.py` endpoints → `dap/master/api/agents.py` + `projects.py`
     (X-Agent-Token on worker endpoints, `/api/v1`, schemas.py models)
   - `master/cli.py` → `dap/master/cli.py`; `master/ollama_client.py` →
     `dap/shared/llm_client.py chat()`
   - Delete `master/` + Streamlit only when the dap/ flow passes the Thursday script
   - `pytest` green (contract suite + 1 end-to-end decompose test)
   Done when: the Thursday demo runs identically from `dap/` paths.
2. S2-02: weights per task type (`w_c/w_r/w_x` in `selector.py`);
   `S = wc*C + wr*R + wx*X + 10u − 15q`, `role_hint` is the equalities tie-break;
   tests: 3-agent assignment example (expected winner), tie → role_hint, loaded agent
   loses, context overflow ineligible.

## Can — S2-05

- All 13 functions (upsert/get/list/touch/stale + create/get/list/set-status projects +
  create/list/get/assign tasks).
- `events` table (project/task/agent/type/message) + `task_results` table
  (files JSON, tokens, duration).
- Task files persisted under `workspace/<run-id>/` on result (path resolution with Baran).
- `tests/test_repositories.py` grows: CRUD, double-register updates, stale→offline,
  restart persistence.
  Done when: suite green incl. persistence across master restart. First two days are
  the window Baran builds on.

## Eray — S2-04 while waiting, then S2-03

1. S2-04 (no dependency): `scripts/measure_model.py` — the same 5 questions for every
   model (2 coding micro-tasks with unit tests, 2 reasoning Q&A checked, 1
   needle-in-haystack); 0–100 per dimension → `docs/agents.json` capabilities replaces
   estimates; model change ⇒ re-run; method documented in `docs/models.md`.
   Done when: six rows measured, method reproducible by a teammate.
2. S2-03 (needs S2-01): poll `GET /agents/{id}/tasks/next` every `POLL_INTERVAL_SEC`;
   run the task with the local LLM (`chat`, json_mode per type prompt); POST TaskResult
   (files/summary/tokens/duration), retry once on failure; 404 on heartbeat ⇒ re-register;
   Ctrl+C clean shutdown; `busy/idle` transitions. Done when: one worker on a second PC
   completes a task end-to-end and its files land in `workspace/`.
   Team note (23 October, agreed by the team): S2-03 is a task for everyone.
   Eray leads the code in `dap/worker/`; every other member runs a worker on
   their own PC against the master over Tailscale and reports failures as
   issues. Thursday checkpoint: at least two live workers completing tasks.

## Fatma — S2-06

- Task board: title, type badge, status, assigned agent + reason, `depends_on`;
  auto-refresh 3 s. Agents page: name, owner, model, role_hint, 3 scores, status colour+text.
- New-project form (Hamza's snippet): <20 characters blocked; loading + error states.
- 100% via `client.ts` (no direct `fetch`); desktop + mobile widths; English text only.
- No schema renames (see agreements 2 and 3); mock until S2-01 lands.
  Done when: decompose→assign flow visible live end-to-end.


## Abdurrahman — S2-09 first, then S2-07

1. S2-09 (no dependency): Tailscale runbook in `docs/SETUP.md` (shared account, `tailscale ip -4`,
   per-machine `MASTER_URL`, fallback note) + `docs/network-test.md` table
   (member | Tailscale IP | reachable from master) + proof: ≥1 worker registers and
   heartbeats from a second PC (screenshot/log).
2. S2-07: `scripts/seed_agents.py` reads `docs/agents.json` → registers all six
   (env: `MASTER_URL`, `AGENT_TOKEN`); `scripts/smoke_test.py` single command —
   health/register/project/decompose/assign/tasks on `LLM_MOCK=1`, prints
   `SMOKE TEST PASSED` or the failing step, exit 0/1; `.github/workflows/ci.yml`: pytest
   on every PR + green badge in README.
   Done when: CI green on a test PR + smoke passes on the master PC.

## Okan — S2-08

- Review AMENDMENT-v1.1 (PR #20, items A1–A7) against the assignment expectations
  (including the A4 12 000-character question raised in the Sprint 1 audit).
- Merge accepted items into `PROJECT_CONTRACT.md` the same day the review is done;
   delete the proposal file.
- Publish the task taxonomy: 8 types, when each is used, required capabilities per type —
   Baran's S2-02 references it.
- Sprint 1 audit leftovers you track: model-sharing rule vs `agents.json` (update the
  models or the contract line), `sprint-01.md` vs `sprint-1/` dedup, `library.md`.
  Done when: one contract, no proposal file, taxonomy referenced by S2-02.

## Hamza — S2-10

- Planning + owners confirmed (filed 18 October), Trello reset done 18 October (mirror
  #21–#30, S1 leftovers labelled Sprint-2), weekly burndown sheet, written dailies
  2–3x/week, report + retro with one change for Sprint 3.
Done when: report filed; retro produced one change for Sprint 3.

## Open questions (owner: Okan, via S2-08)

1. Contract line "no two PCs share a model" vs `agents.json` repeating `qwen3:4b` six times.
2. Sequencing of S2-08 taxonomy vs S2-02 score weights (agreement 5).
3. A4 (12 000-character requirement limit): keep in the amendment or drop.
4. Fatma's `App.jsx`/`main.jsx` → `.tsx` conversion: keep in Sprint 2 or move.
