# Sprint 2 Planning

Owner: Hamza (card S2-10). Distribution was written in the team WhatsApp group on
15 October 2026 (10:43 message, "Sprint 1'i kapatıyoruz — Sprint 2 yarın başlıyor"),
followed by a short Google Meet the same day.
Backlog source of truth: GitHub Issues #21–#30. Trello is the mirror for the course:
`trello.com/b/iyaH8vmC/distributed-agents` (reset done 18 October — see Open items).

| Field | Value |
| --- | --- |
| Dates | 15–29 October 2026 (Thu→Thu, two weeks — opened the same day Sprint 1 closed) |
| Goal | One worker completes a real task end-to-end from a second PC, assignment becomes score-based, and all bookkeeping (events, results, CI) runs on one contract |
| Out of scope | Workers choosing methods and writing code autonomously (Sprint 3); cloud LLM APIs; extra messaging layers (no WebSocket/SSE/Celery) |
| Card list | Issues #21–#30 (`S2-01 … S2-10`), opened 14 October 2026 |

## Sprint backlog

| Code | Card | Owner | Issue |
| --- | --- | --- | --- |
| S2-01 | Port Thursday prototype into dap/ contract paths | Baran | #21 |
| S2-02 | Score-based agent selection (contract A3) | Baran | #22 |
| S2-03 | Worker execution loop | Eray | #23 |
| S2-04 | Capability measurement + real scores | Eray | #24 |
| S2-05 | Full repositories + events + task_results | Can | #25 |
| S2-06 | Task board + live agents UI | Fatma | #26 |
| S2-07 | Seed + smoke + CI | Abdurrahman | #27 |
| S2-08 | Contract v1.1 merge + task taxonomy | Okan | #28 |
| S2-09 | Network runbook + 2-machine proof | Abdurrahman | #29 |
| S2-10 | Sprint 2 planning + report | Hamza | #30 |

## Order (who waits for whom)

Written in the group on 15 October:

```
Can (agent+project repository functions, first 2 days) → Baran (dap/ port)
Baran (S2-01 lands) → Eray (worker loop) → Fatma (real-API wiring)
Abdurrahman, Okan, Hamza: parallel, no dependencies
```

Dependencies inside Sprint 2: S2-03 and S2-02 need S2-01 (`/agents/{id}/tasks/next`,
result endpoints, selector formula); S2-08 needs PR #20 reviewed first; S2-07's full
smoke run needs S2-01 (contract endpoints).

## Success criteria

1. The Thursday demo flow runs identically from `dap/` paths only (`master/` deleted). — #21
2. Selection by score is proven by tests and used by `/assign`. — #22
3. A worker on a second PC completes a task end-to-end; files land under `workspace/`. — #23
4. All six worker models are measured with the same 5-question script; method reproducible. — #24
5. Test suite green including persistence across a master restart. — #25
6. `decompose → assign` flow is visible live in the UI. — #26
7. CI green on a test PR + smoke test passes on the master PC. — #27
8. One contract (v1.1 merged), no leftover proposal file, taxonomy referenced by #22. — #28
9. Network table complete; every member reachable from the master over Tailscale. — #29
10. Sprint 2 report filed; retrospective produces one change for Sprint 3. — #30

## Week 2 checklist (written 23 October)

Week 1 closed with every open card merged green (PRs #44–#51). Below is what
is left to finish Sprint 2, in dependency order. Read your own part exactly;
the contract values quoted here are the ones to code against.

### 1. Baran — unblock the worker loop (first, everyone waits on this)

- `GET /agents/{agent_id}/tasks/next` (contract endpoint table): worker
  caller, `X-Agent-Token` header (shared agreement 3), returns **200 Task or
  204** when the agent has nothing. Agree the pick rule with Eray before
  writing tests: only `pending` tasks whose `depends_on` entries are
  `completed` (FR-13), then the task is marked assigned to the asking agent.
- `POST /tasks/{id}/result` (contract endpoint table): worker caller,
  body **`TaskResult`** = `task_id, agent_id, success, summary,
  files[{path, content}], error, duration_ms, tokens_used`, returns **200
  Task**. Persist through Can's functions in `dap/master/db/results.py` /
  `workspace.py` (`store_task_result`, `save_generated_files`,
  `record_event`) — read `dap/master/db/RESULTS.md` and `WORKSPACE.md`
  first; they define `run_id` and the retry behaviour.
- Decide the retry policy with Can before wiring (review finding on #47):
  a repeated attempt currently cannot rewrite files under the same `run_id`.
  Cheapest rule: a new attempt gets a new `run_id`.
- `workspace_root` needs a value: `dap/master/config.py` is a ready file
  ("do not change without Okan"), so confirm with Okan — either a
  `WORKSPACE_ROOT` setting through `config.py`/`.env`, or the plain
  `workspace/` directory relative to the repository root. No path or address
  hardcoded beyond that.
- Endpoint tables in the contract label these two rows "Sprint 3"; the team
  needs them in Sprint 2 (S2-03). Flagged to Okan with the other contract
  items — code against the contract shapes now.

### 2. Eray — lead the worker loop (S2-03), then your measurements

- Loop behaviour is exactly the member-guide S2-03 list: poll `tasks/next`
  every `POLL_INTERVAL_SEC`, run the local LLM (`chat`, `json_mode` per type
  prompt), POST `TaskResult`, retry once on failure, **404 on heartbeat ⇒
  re-register**, Ctrl+C clean shutdown, `busy/idle` transitions. The team
  note under S2-03 makes this a team task: you lead `dap/worker/` code;
  everyone else runs a worker and files issues.
- Until Baran's two endpoints land, write against the contract shapes above
  and integration-test after they merge (dependency in the Sprint backlog
  section).
- S2-04 remainder: fix the comment above the haystack in
  `scripts/measure_model.py` (≈2 000 tokens; Ollama's default window is
  2 048) and lead the measurement wave below.

### 3. Everyone — run a worker and measure the models you have

Worker on your PC (after the loop lands):

1. Copy `.env.example` to `.env`: `AGENT_TOKEN` (same on all PCs), your
   `AGENT_ID` / `AGENT_NAME` / `AGENT_OWNER` / `AGENT_ROLE_HINT`, and
   `MASTER_URL=http://<Hamza's Tailscale IP>:8000`.
2. `python -m dap.worker.main` from the repository root; leave it running;
   report any failure as a GitHub issue (that is your part of S2-03).

Measurements (S2-04, everyone — each member measures **every model they have
locally**):

1. Ollama running, `LLM_MOCK` unset or `0`, from the repository root:
   `python scripts/measure_model.py --model <name>`
2. If `<name>` is one of the models in `docs/agents.json`, store the scores
   on that row: `python scripts/measure_model.py --model <name> --write <agent-id>`.
3. Paste the printed per-question lines into `docs/models.md` (Results) —
   that is what makes the numbers auditable.
4. A model that is not in `docs/agents.json`: record the run in
   `docs/models.md` only; do not invent rows (Okan owns the contract row set).
5. Two members measuring the same model is a feature: compare the numbers
   and note both runs (reproducibility check).

### 4. Fatma — switch the interface to the real API

- `frontend/src/api/client.ts`: set `USING_MOCK` to `false` once Baran's
  endpoints are live; agents page, new-project form and task board then run
  against the master. Keep `types.ts` frozen, all calls through `client.ts`,
  English text, desktop + mobile widths.
- Done when: success criterion 6 — `decompose → assign` visible live.

### 5. Abdurrahman — finish S2-07 and S2-09

- `SETUP.md` is currently **empty (0 bytes)**: write the Tailscale runbook —
  shared account, `tailscale ip -4`, per-machine `MASTER_URL`, fallback note.
- `scripts/seed_agents.py` must read `docs/agents.json` and register all six
  via `POST /api/v1/agents/register` with `X-Agent-Token`; env: `MASTER_URL`,
  `AGENT_TOKEN`. (It currently only writes `config/agents_registry.json`
  instead of registering anything — `scripts/smoke_test.py` then reads that
  file.)
- `scripts/smoke_test.py`: one command covering health/register/project/
  decompose/assign/tasks on `LLM_MOCK=1`, prints `SMOKE TEST PASSED` or the
  failing step, exit 0/1.
- CI green badge in `README.md`; confirm every member has a row in
  `docs/network-test.md` (7 machines listed today).

### 6. Can — support (no S2-05 code left)

- Pair with Baran on the results wiring (`RESULTS.md` / `WORKSPACE.md`),
  settle the `run_id` retry rule with him, and measure any models you have.

### 7. Okan — contract items (Hamza's message)

- The five new repository signatures, `task_results` → sprint 2, accept the
  hybrid `workspace/<project_id>/<run_id>/`, stale `docs/database.md` line,
  the two endpoint rows' sprint label, open questions 1–4 of the member
  guide, and the `context_window` question for S2-02's overflow rule (add to
  the frozen schemas now or move the rule to Sprint 3).

### 8. Hamza — S2-10

- Burndown sheet, dailies 2–3×/week, report + retrospective with one change
  for Sprint 3.

### Closing checkpoint — Thursday 29 October (30 minutes)

- Flow register → decompose → assign from `dap/` paths on `LLM_MOCK=1`,
  one look at the UI, **at least two live workers** completing a task
  (team agreement of 22 October), smoke test green on the master PC.

## Meeting notes

- Date: 15 October 2026, ~11:10 (Google Meet), Sprint 2 planning and distribution.
- Attendees: Hamza, Baran, Okan (joiners); Abdurrahman joined later from the road ("toplantıya
  katıldım da alır mısın"); Can and Fatma followed in writing (Fatma was in a live class and
  kept being dropped from the call); Eray received the written plan in the group.
- Decisions:
  - Sprint 2 starts Friday 16 October (announced "yarın" the morning of the 15th);
    final window recorded 18 Oct: sprints run Thu→Thu in two-week blocks, so Sprint 2
    counts from Thursday 15 October (15–29). Issues #21–#30 are the authoritative backlog.
  - Order: Can (first two days) → Baran (port) → Eray (loop) → Fatma (wiring); others parallel.
  - `master/` stays only as a read-only reference until S2-01 lands; nothing new connects to it.
    (Recorded rationale: Issues #6 + #21, Okan's PR-#32 review — bridge only, never permanent.)
  - Fatma edits no schema names; she keeps client.ts on the contract shapes (`types.ts`)
    and mock data until the `dap/` endpoints arrive (#26).
  - PR #20 (contract amendment v1.1) stays open until Okan's review, then merges the same
    day and the proposal file is deleted (S2-08).
  - Hamza + Okan follow up the plan/document reconciliation over the weekend.

## Open items (carried/for owner)

- Trello reset: DONE 18 Oct — "Sprint 2 Backlog" list holds #21–#30 as S2-01…S2-10
  (owner/issue/branch per card) plus the four S1 leftovers (S1-03, S1-06, S1-08, S1-10)
  labelled Sprint-2 with comments pointing at their S2 issues; S1-02/S1-04/S1-11 moved to
  Done; "In Progress" list typo fixed. Remaining for Hamza: burndown sheet + dailies.
- `docs/sprints/sprint-01.md` conflicts with `sprint-1/`; keep one only. (Okan audit item 13)
- Contract says no two machines share a model; `agents.json` currently repeats `qwen3:4b`
  six times. Decide: change models or amend the rule during the v1.1 merge. (Okan, S2-08)
- FATMA: `App.jsx`/`main.jsx` are plain JS inside a TS template; conversion to `.tsx` is
  scheduled informally for Sprint 2 — confirm or drop it. (Open; see member guide)
