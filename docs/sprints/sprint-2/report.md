# Sprint 2 Report — Distributed AI Dev Platform

Dates: 15–29 October 2026 · Owner: Hamza · S2-10 ([#30](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/30))

**Draft, updated 16 November 2026.** This is a retrospective snapshot prepared after the
sprint, not evidence that the closing demo happened. GitHub issue and PR states were
checked on 16 November; changes merged after 29 October are identified below. Team
confirmation, demo evidence, and the retrospective decision are still needed.

## Goal and result

The goal was a worker completing a real task from a second PC, score-based assignment,
and events, results and CI operating under one contract. **Result: partially evidenced.**
Code for the master, worker, persistence and UI was merged, some after the sprint. The
available records do not establish the closing two-worker demo, a real API smoke test,
or a full current test run. They do not establish that every acceptance criterion was met.

## Card status

States below distinguish GitHub issue state from acceptance. A merged PR alone does not
prove the card's demo or operational criteria.

| Card / owner | Issue | Evidence and remaining acceptance |
| --- | --- | --- |
| S2-01 Baran | [#21](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/21) closed | Port and worker endpoints: [#45](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/45), [#53](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/53); old prototype removed in [#58](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/58), merged 1 November. Demo evidence pending. |
| S2-02 Baran | [#22](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/22) open | Score selection exists; confirm all acceptance tests and resolve context-overflow scope with Okan. |
| S2-03 Eray / team | [#23](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/23) open | Worker loop [#57](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/57), merged 1 November. Second-PC task completion and file evidence still needed. |
| S2-04 Eray / team | [#24](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/24) open | Measurement script [#46](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/46); six-agent results proposed in [#66](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/66), open; question-level evidence requested in review. |
| S2-05 Can | [#25](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/25) closed | Repository and persistence work [#43](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/43), [#47](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/47). |
| S2-06 Fatma | [#26](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/26) open | Board [#48](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/48), real API [#60](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/60) merged 1 November; live flow evidence pending. |
| S2-07 Abdurrahman | [#27](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/27) open | Initial [#42](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/42); [review](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/27#issuecomment-6910937588) records missing real HTTP smoke and pytest CI. |
| S2-08 Okan | [#28](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/28) open | Contract v1.1 and taxonomy [#40](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/40); confirm remaining audit items before closure. |
| S2-09 Abdurrahman | [#29](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/29) open | Runbook exists; complete reachability and second-PC registration/heartbeat proof pending. |
| S2-10 Hamza | [#30](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/30) open | Planning [#39](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/39), week-2 checklist [#52](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/52); this draft, burndown and retrospective require completion. |

## Demo, blockers and decisions

The 29 October checkpoint was planned for mock register → decompose → assign, a UI
check, two live workers and smoke test. **Its actual results and screenshots have not
been verified.** Collect the date, participants, command output and evidence from the
team; do not infer a successful demo from merged code.

As of 16 November, Sprint 3 [#64](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/64)
and [#65](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/65) remain
open with recorded integration and worker-validation blockers. The dependency gate
fix is pushed in #64; integrated validation remains outstanding. Contract v1.2 was
merged in [#63](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/63)
on 15 November, after Sprint 2.

## Tests and progress data

The 15 November review ran 99 focused tests on each of #63 and #66, and 110 focused
tests on each of #64 and #65 in isolated copies. Full local `pytest` hung in FastAPI
TestClient; these partial results do not constitute a full-suite pass. The reviewed
CI workflow did not run pytest and its smoke test checked a registry file, not the
API. Master-PC smoke and live demo outcomes remain unverified.

Current GitHub snapshot: 2 of 10 Sprint 2 issues closed (#21 and #25), 8 open. This
is an issue-status snapshot, **not a historical burndown** or a measure of accepted
work. Recover dated board snapshots and written dailies before reconstructing progress;
do not invent past data.

## Developments after 16 November (recorded 18 November)

- 17 November: a live multi-PC test day was held from the team's architecture test
  repository (one master, six workers over Tailscale, real local models). The S2-03
  worker loop card is affected by the follow-up decision below.
- 18 November: the team adopted the A2A architecture (contract v1.3): the master
  sends tasks to workers and the S2 pull endpoints (`tasks/next`, `tasks/{id}/result`)
  are retired; their code remains in git history. The worker-loop implementation and
  evidence for a second PC carry into the A2A worker in Sprint 4.
- Full-suite `pytest` on the integration branch: 264 passed, 0 failed (18 November).

## Retrospective

Team retrospective and its final decision are **pending**. Proposed single change for
Sprint 3: require one repeatable integrated checkpoint with actual test and smoke output
before declaring a card complete. The team must discuss and accept or replace this
proposal; it is not recorded as an agreed decision.
