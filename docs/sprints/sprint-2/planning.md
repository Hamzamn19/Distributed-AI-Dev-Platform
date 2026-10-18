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
