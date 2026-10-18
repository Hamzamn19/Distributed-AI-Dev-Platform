# Sprint 1 Report — Distributed AI Dev Platform

Dates: 1–15 October 2026 (Thu→Thu, two weeks) · Owner: Hamza (Scrum Master) · Card S1-11 (Issue #12)
Repo: https://github.com/Hamzamn19/Distributed-AI-Dev-Platform · `main` at report time: 4d2e1f4

> Sources: merged PRs in GitHub, repo files, `pytest` run on a clean venv, chat statuses
> (group + 1:1) 6–15 Oct. Phone numbers and invite links are intentionally not repeated here.

## 1. Sprint goal and result

**Goal.** A working master that takes a requirement, splits it into tasks, assigns each
task to an agent and stores it all in the database; the result is visible in the web
interface. Workers do not write code yet. (Success criteria in `sprint-1/planning.md`.)

**Result: partially reached, by an explicit scope cut.** On 12 October the team reduced
the target to the Thursday 15 October emergency demo P0 ("the models are reachable and
the master answers"; details in `sprint-1/task-distribution.md`). The foundations landed
— database, master API, LLM client, web UI, 39 green tests — but the central pipeline
(decompose + assign, card S1-06) was never merged to `main`, so the full goal is
reached today only through Baran's out-of-contract `master/` prototype. Porting that
prototype into the contract `dap/` paths is Sprint 2 card S2-01, agreed as such.

## 2. Completed cards (with pull request links)

15 PRs merged during the sprint, one branch per card:

| Card | Owner | State | Evidence (PRs) |
| --- | --- | --- | --- |
| S1-01 Trello board + planning | Hamza | done | #13, #14, #15, #33; 11 Issues became the authoritative card list (team decision 12 Oct); Trello: `trello.com/b/iyaH8vmC/distributed-agents` |
| S1-04 Web interface | Fatma | done (within scope) | #1 (first interface), #16 (client.ts + agents from real API), #37 (online badge) |
| S1-05 Master core + API | Baran | done (minimal) | #17 (core + API), #34, #36 (GET /agents); #32 (frontend /api/v1 compat, by Hamza) |
| S1-09 Database schema + repository | Can | done | #35; 13 functions + tests |
| S1-07 LLM client + worker stub | Eray | partial | #31 (`chat()` + mock mode); worker loop not started |
| S1-01…S1-02 repo skeleton + setup | Abdurrahman | mostly done | #18 (hardware inventory); `SETUP.md`, `.env.example`, `pytest.ini`, `requirements.txt` in place; contract amendment PR #20 open on purpose (review = S2-08) |
| S1-03/S1-08 Requirements + inventory (Okan) | Okan | partial | #19 (three sample requirements + expected decompositions); `agents.json` written; `requirements.md`, `models.md`, `architecture.md`, `library.md` not yet written |

Card statuses follow the 12 October team decision: the items planned for the sprint's
closing stretch (16–18 October) were moved to Sprint 2 (#21–#30) and the sprint closed
on schedule on Thursday the 15th.

## 3. Unfinished cards and reasons

| Card | What is missing | Reason | Where it continues |
| --- | --- | --- | --- |
| S1-06 Breakdown + assignment | `dap/master/core/` (decomposer, selector), `cli.py` | Depends on Can + Eray; both only merged on 15 Oct; remaining time went into demo compatibility (PR #32) | S2-01, S2-02 |
| S1-07 (part 2) Worker loop | `dap/worker/main.py`, `master_client.py` | Needs Baran's contract endpoints to test against | S2-03 |
| S1-10 Seed + smoke + final checks | `scripts/` is empty; no CI yet | Same dependency on S1-05 endpoints; deprioritized by the 12 Oct cut | S2-07, S2-09 |
| S1-03/S1-08 documents | `requirements.md`, `models.md`, `architecture.md`, `library.md` | Documentation behind code; deliberately moved (P2 of the 12 Oct cut) | Sprint 2 |
| S1-11 Review + report | (this report) | Filed 18 October, three days after sprint end | — |

Note: `master/`, `repo_starter/`, `agents/`, `backend/` are leftovers of the old plan /
Baran's prototype and are scheduled for deletion or cleanup in Sprint 2 (S2-01, and the
contract v1.1 merge S2-08 determines what stays).

## 4. Demo summary

The live demo planned for Thursday 15 October **did not take place**. Instead, that day:

- the last compatibility PRs (#32–#37) were reviewed and merged;
- Fatma's three contract-vs-code questions (paths, token, CORS) were answered and merged;
- agent registration + heartbeat was exercised against the demo master from a second PC
  (Okan wrote a register loop on 15 Oct — the P0 registration check happened in practice);
- per-person written status was collected in the group (Hamza's 10:38 recap "Bu hafta ne
  yaptık — kişi kişi"), and Sprint 2 was planned and distributed the same morning.

What was actually reached (P0 checklist, honest state):

| P0 item | State |
| --- | --- |
| Master boots, `GET /api/v1/health` ok | yes (contract path) |
| Register + heartbeat accepted from another PC | yes (tested 15 Oct) |
| Every PC has a model (`ollama pull qwen3:4b`) | yes for Can / Abdurrahman / Eray / Fatma / Okan confirmed in chats; Baran runs gemma4:26b + qwen3.8:27b + llama3.1 on the M5 (master candidate) |
| One real model call through the master path | no — decompose/assign only exists in the `master/` prototype (S1-06 slipped) |
| `pytest` green | yes (19 tests on 15 Oct; 39 at sprint close) |
| Sprint report filed honestly | yes (written 16–18 Oct, this file) |

Screenshots: Trello at sprint end — `trello.com/b/iyaH8vmC/distributed-agents`
(backlog untouched: 101 reference cards; Done 9; Sprint Backlog 1; Sprint 2 Backlog 14
with the four S1 leftovers labelled Sprint-2; In Progress empty). Board export image
skipped by decision 18 Oct — add one here if the course asks for it.

## 5. Blockers and decisions

1. **Two masters.** The repository had both the contract `dap/` skeleton and Baran's
   working `master/` prototype (Streamlit). For the planned demo day a temporary bridge
   (PR #32 alias routes) was a recorded, deliberate decision (Issues #6, #21). Okan's
   15 October audit `PR #32 review` confirms: acceptable as a bridge, not as the permanent
   solution. Permanent fix = S2-01 port + delete prototype.
2. **Contract vs code field mismatch** (`online` vs `idle`, `task_type` vs `type`, …).
   Decision: `types.ts` and `schemas.py` win; Fatma keeps mock data until `dap/` endpoints
   land; nobody edits schema names further (contract rule 2).
3. **AI attribution.** A test commit made "Claude" appear in GitHub Contributors. Cleaned
   up on 15 Oct (author-info fix commit merged, empty test PR rejected). Going forward:
   every member sets `git config user.name / user.email` to their own identity before
   their first commit.
4. **Attendance / connectivity.** Fatma was repeatedly dropped from meetings (live class,
   room network); the Sprint 2 plan was therefore mirrored in writing in the group.
   Meeting decisions are, from now on, written the same day.
5. **Which plan is authoritative.** Two planning PDFs (old "Baslangic Rehberi" and
   "Ekip Plani ve Ortak Sozlesme") had left remnants. Decision of record: Issues #2–#12
   were the single task source in Sprint 1 (team decision 12 Oct); the two-document
   double is reconciled in Sprint 2 under Okan (S2-08), starting from
   `docs/sprints/sprint-01.md` vs `sprint-1/` (Okan audit item 13).

## 6. Test results

- `pytest`: **39 passed in 1.43 s** on a fresh virtualenv at `main` @ 4d2e1f4
  (repositories, agents API, health, contract schema, LLM client mock, worker config).
- At the time of the 15 Oct distribution: 19 tests — the suite roughly doubled in the
  closing days of the sprint.
- Failure path: the Ollama-off behaviour is covered through mock mode (S1-07 agreement 3);
  the `/decompose` failure path could not be exercised because S1-06 never merged.

## 7. Retrospective summary and proposal for Sprint 2

**Went well**

1. The git/Issue workflow held: one branch per card, one PR per card, Issues as the
   single card list — 15 merged PRs across 11 cards, reviewable history.
2. The 12 October emergency scope cut kept the sprint honest and produced real
   foundations instead of a pile of half-features.
3. Every member shipped something representative: DB + tests (Can), master API (Baran),
   LLM client (Eray), UI + live agents (Fatma), setup/network (Abdurrahman), samples +
   contract (Okan), board + planning + reviews (Hamza).

**To improve**

1. The central pipeline (S1-06) started too late — at demo time the agreed storyline
   could not be shown from contract paths at all.
2. There was no mid-sprint integration checkpoint; path/field incompatibilities were all
   discovered in one rush on 15 October (Fatma had to ask three questions, Okan produced
   a long delta audit).
3. Twin documents (two planning PDFs, plus `sprint-01.md` vs `sprint-1/`) caused
   measurable role confusion; also several merged tickets were never closed on GitHub.

**One change for Sprint 2 (proposed retro action):** a 30-minute integration checkpoint
every Thursday on the master PC — minimum script: register + decompose + assign under
`LLM_MOCK=1`, one live look at the UI. Three of the four sprint problems above would
have surfaced there a week earlier.

**Sprint 2 proposal.** Already distributed on 15 October in the group and opened as
Issues #21–#30 (S2-01…S2-10): port to contract paths + score-based selection (Baran),
worker execution loop + capability measurement (Eray), full repositories + events +
task_results (Can), task board + live UI (Fatma), seed/smoke/CI + network proof
(Abdurrahman), contract v1.1 merge + task taxonomy (Okan), planning + Trello reset +
report (Hamza). Order: Can (first two days) → Baran (port) → Eray (loop) → Fatma
(wiring); Abdurrahman, Okan and Hamza in parallel. Sprint 2 runs 15–29 October 2026
(Thu→Thu; it opened the same day Sprint 1 closed).
