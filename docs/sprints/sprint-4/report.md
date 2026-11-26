# Sprint 4 Report — Distributed AI Dev Platform

Dates: 25–26 November 2026, **ending today with this Sprint Review** · Owner: Hamza (Scrum Master) · Sources: [planning.md](planning.md), the git history of `main` (all commits below are pushed), [contract v1.3/v1.4 sections](../../contracts/PROJECT_CONTRACT.md)

> Cadence note: Sprints 1–2 ran two weeks each (1–15 Oct, 15–29 Oct); Sprint 3
> stretched with a closing week to 25 November. By the team's week accounting we
> are now at the **end of Sprint 4**: it ran as one compressed sprint (25–26
> November) right after the Sprint 3 merge, closed today by this review.

## Sprint Goal and result

**Goal:** make the platform usable and observable in real use — the user
controls a running project, watches the model work live, and every project gets
its own visual identity — while `main` stays green.

**Result: achieved.** Nine feature batches merged to `main` (25–26 November,
commits `53b17b6` → `da604e2`), test suite grown from 280 to **303 passing
tests** with the frontend build, and two real-model end-to-end runs as
evidence — the largest one (5 tables, 2 business-action routes) passed the
master acceptance with **57 of 57 checks** and completed in ~7.5 minutes on one
worker.

## How the sprint ran

1. **Live testing exposed the backlog.** Right after the Sprint 3 merge, the
   platform was driven with the real model. Every gap found became a pulled
   card the same hour (see [planning.md](planning.md) for the mapping).
2. **Follow-up requests (`53b17b6`).** A finished application can now be asked
   for a change: `POST /projects/{id}/followup` creates one `revision` task over
   the finished tasks and runs it. A real discount feature was added to a
   generated parking application in one attempt.
3. **Search honesty (`e741a02`).** Live testing showed "search" that returned
   HTTP 200 without filtering. The acceptance check and the generated
   applications' `wireSearch()` helper now verify the filter really works.
4. **Run control batch (`3097706`, 5 features).** A2A **CancelTask**
   (real cancellation at the worker), **contextId = project id** per the A2A
   "Life of a Task" spec, **export zip** of the generated application,
   **automatic retry on a different agent** when a worker-level failure happens
   (max 3 attempts, with an idempotency fix so a retried task does not
   double-store results), and a **run queue** (a run request while all agents
   are busy starts when one is free).
5. **Live-test fixes (`8aefc6b`).** Three real bugs found and fixed the same
   session: revisions now write only the files they change (the model lost
   files when forced to repeat all four), the worker's LLM timeout matches its
   documented 600 s, and the frontend build no longer bakes a wrong API base
   URL.
6. **Watching the model write live (`aa32a77` → `da604e2`).** The worker now
   streams the model's answer (OpenAI `stream: true`), keeps the running token
   count, the file being written and the last ~600 characters; the master
   exposes `GET /projects/{id}/live`, and the interface shows a writing panel
   under the task that is running — openable, with a live token counter. Four
   hardening commits followed from live use (stale gap skipped, the master's
   task id survives the worker's answer, the panel lives under each task).
7. **Five visual styles (`0230442`, `ed085ea`) + a modern layout (`48046b1`).**
   The template was rebuilt around current dashboard UX (researched: persistent
   sidebar, F-pattern hierarchy, bento metric cards, reserved loading/empty
   states, actions next to what they act on). A project now picks one of five
   themes (modern, midnight, warm, forest, mono) at creation; the choice rides
   on the frontend task's description (`data-theme`), so style.css does the
   colors and the model keeps the structure. Status badges color themselves by
   their text, number columns align with tabular numerals, `#message` became a
   toast, `showSkeleton()` shimmers during first loads.
8. **Section switching (`f2b96df`, `da604e2`).** The sidebar now behaves like
   page navigation — one panel on screen at a time, the URL hash follows, the
   active link is marked — while the application stays one file (no framework,
   no build step): the trade-off that keeps a 27 B local model reliable.
9. **Engineering the machine, not just the code.** The recurring VRAM→RAM
   freezes were root-caused (an oversized model context filled VRAM, buffers
   spilled into RAM, swap filled, the desktop froze). The model server now runs
   with a bounded 32 768-token context (7.5/12.3 GB VRAM, ~4.7 GB margin), the
   indexer that leaked 3 GB was disabled, and a llama-server restart discipline
   (found with 6.5 GB of weights spilled into swap) recovered the machine
   before the big run. The discipline is written down: one model process, RAM
   and VRAM checked before heavy steps, bracket-trick kill patterns.

## Increment and demo (what can be shown today)

1. Create a project with a chosen visual style → decompose → assign → run;
   **watch the model write live** under the running task (token counter,
   current file, scrolling tail).
2. The generated warehouse application (5 tables, stock actions, dashboard) in
   the **midnight** theme: sidebar navigation between panels, colored status
   badges, toasts.
3. **Cancel run** → tasks fail with "cancelled by the user" → **Run again**
   resumes; **Download app (.zip)**; a **follow-up request** ("add a footer")
   completed by one revision task.
4. Reproduce the numbers: `pytest` → 303 passed; the runs are in the master
   database / git history (`workspace/`).

**Verification (26 November, before this review):** all 18 commit hashes cited
in this report were re-checked against `main` (subjects and timestamps match);
`main == origin/main`; the full suite re-run → **303 passed**; the warehouse
run re-confirmed from its acceptance file (57/57, `data-theme="midnight"`, 5
tables); CI green on the report commit itself (GitHub Actions run 45755691586).

## Metrics

| Measure | Sprint 3 end | Sprint 4 end |
| --- | --- | --- |
| Tests (pytest) | 280 | **303** (+23) |
| CI on `main` | green | green |
| Generation speed (worker model) | ~54 tok/s (gemma4-26b) | **62–64 tok/s** (bonsai-2.5-27b with MTP, 89–97 % draft acceptance) |
| Largest accepted run | 4 tables, 9/9 checks | **5 tables + 2 action routes, 57/57 checks** |
| Model context discipline | unbounded (163 840; caused freezes) | bounded 32 768 (7.5/12.3 GB VRAM) |

## Review notes (open items, honestly)

- **Per-owner adoption commits** of the merged Sprint 4 code are pending:
  Baran (master core/api), Eray (worker + templates), Fatma (frontend pages),
  Okan (contract sections 8/13, marked v1.4 material), Abdurrahman
  (measurement/tests). Sprint 3's review of Okan's architecture was completed
  by Baran only; the same pattern continues this sprint.
- **Trello board sync** is behind the code (the board ends at Sprint 3); the
  import file `~/Documents/dap-trello-import.json` needs a Sprint 4 pass.
- A generated application has not yet been run on **two PCs** in this sprint —
  planned for the Monday session with the prepared requirements
  (`~/Documents/dap-test-prep/requirements/`).
- Cache note for review (Eray): a revision that changes `frontend/lib.js` can
  serve a stale browser copy; fix is a versioned script tag in revision
  templates.

## Retrospective input

- **Went well:** pull-based planning from live findings — every card came from
  real use and was finished to Done the same session; the self-correction loop
  fixed a backend bug unattended during the big run ("corrected 1x").
- **To improve (actions):** (1) adopt a formal Definition-of-Done checklist for
  cards including the adoption commit of the owning member; (2) keep the
  machine-health discipline written next to the run scripts so any member can
  operate the master PC safely.

## Next sprint (proposal for the team)

- A real **login page**: UI-only gate works today; protecting the API requires
  allowing new files in revisions and token-aware acceptance checks — scoped
  and ready to build.
- **SSE streaming** end-to-end (character-level instead of ~2 s polling).
- **Multi-PC run** with the whole team Monday; adoption commits; Trello sync.

The team's dated decisions, standing rules and the exact context of the
2026-11-18 architecture vote are recorded in [the decisions log](../../decisions-log.md);
the sprint's meetings and stand-ups in [meetings.md](meetings.md).
