# Sprint 3 Report — Distributed AI Dev Platform

Dates: 4–18 November 2026, closing week extended to 25 November · Owner: Hamza · Sources: [planning.md](planning.md), [task-distribution.md](task-distribution.md), Issue [#61](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/61), PRs [#63](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/63), [#64](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/64), [#65](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/65)

**Updated 25 November 2026, after the team-approved merge into `main`.** Records below come from git history,
pull requests and the test-day checklist; states that still need a person's
confirmation are marked pending.

## Goal and result

The goal was to generate a small web application from a real requirement with the
fixed template: requirement → decompose → assign → worker generation → running
application, with a live multi-PC test. **Result: the architecture decision was
made by team vote, the A2A implementation was adopted and is now the team's `main`
line (merge commit 7b2af8d, 25 November, CI green on 280 passing tests), with a
real-model end-to-end run as evidence; the per-owner adoption commits of the
remaining owners are the open item, tracked on the board.**

## How the sprint ran

1. **Contract v1.2 (4 November, PR #63, merged).** Fixed the Sprint 3 template
   rules: folder layout of the generated application, one task per code type,
   the two-layer sketch (fixed pattern + the project's records), and Eray as
   owner of `templates/`.
2. **Two implementation lines formed on the same base.**
   - In the main repository: PR #64 (Baran + Can: template backend, template copy
     on project create, task inputs, records contract; last commit 5 November) and
     PR #65 (Eray, based on the #64 branch: worker fills the task's one template
     file, rejects broken Python, waits for missing inputs; last commit 17 November,
     including issue #68).
   - In a separate architecture test repository (an exploratory spike, kept out of
     `main` on purpose): Okan implemented the A2A design — the master serves the
     web interface and the API on one address and **sends** tasks to the workers
     (A2A protocol, section 13), with a worker self-correction loop, a master
     acceptance check, an orchestrator/integrator, a new web interface and the
     test-day scripts. 26 commits, all labelled `S3-ARCH`.
3. **17 November test day** (checklist merged as `docs/test-day.md`): Baran's PC as master (gemma4:26b, Ollama), six workers
   (qwen2.5-coder and qwen3 models; Hamza's gemma-4-26b on llama.cpp), connected
   over Tailscale. The run surfaced concrete failures; fixes were committed the
   same evening (master acceptance check, narrower testing task, worker checks,
   setup prompts for every member's AI assistant, skill scores follow the model
   instead of the saturated five-question measurement).
4. **18 November team decision.** The team compared both architectures and voted
   to adopt the A2A design (the "team decision + per-owner adoption" option):
   - Contract **v1.3** amendment: master serves UI + API on one address, tasks go
     to workers over A2A, the worker pull endpoints are removed (section 8 updated).
   - The spike was merged into `main` on branch
     `feature/S3-arch-a2a-adoption` (merge commit "S3: adopt the A2A architecture").
     The retired pull-endpoint code (`dap/master/api/tasks.py`,
     `dap/worker/master_client.py`, their tests) stays available in git history.
   - Reusable results of #64/#65 (one task per type with target files, dependency
     waiting, output restriction) are carried by the merged implementation; the two
     pull requests are re-pointed to contract v1.3 in Sprint 4.
5. **Per-owner adoption review (19 November, in progress).** Every owner reviews the
   merged code of their own folders and commits an adoption confirmation, so the
   A2A implementation becomes the team's reviewed code, not one person's spike.
   Done: Baran (commit 2999e0e, master core + api reviewed, review notes added to
   `orchestrator.py`). Pending: Can, Eray, Fatma, Abdurrahman, Okan (contract v1.3).
6. **Closing week (19–25 November).**
   - 19 November: live demonstration for the instructor (master on Baran's PC,
     `agent-hamza` connected over Tailscale with the real model gemma4-26b) —
     **the instructor accepted the demo.**
   - Okan continued the architecture in the test repository (commits 6db4823,
     0432694, 9545e15): an "Open the app" button that runs the generated
     application on the master host (port 8100), author lines in every generated
     file naming the agent, PC, model and task, a **"Cancel run"** button with
     its endpoint, a fix for Qwen3's thinking stall on Ollama (`/no_think`), and
     the master-side model context raised to 12288.
   - 23 November team session: the team tested Okan's latest features live with
     the real model through `agent-hamza`; a generated application was cancelled
     and re-run from the interface. The team then agreed to bring the tested
     repository into the main repository.
   - Hamza added **`RUN_MODE=parallel`** (commit bb0e705): with `RUN_MODE=parallel`
     the frontend and testing tasks start together after the backend (the
     generated tests hit the API, not the UI); the default `sequential` mode is
     unchanged. Proposed to Okan as contract v1.4 material.
   - 25 November, with the team's agreement: Okan's repository (tested) was
     merged into the integration branch (commit dec5056, conflicts resolved
     keeping both the parallel mode and the cancel feature), and the branch was
     merged into `main` (commit 7b2af8d). **CI on `main` is green: 280 passing
     tests plus the frontend build.** Pull requests #64/#65 are superseded by
     this line; their still-valid parts are carried by the merged code.

## Work distribution

| Member | Sprint 3 work |
| --- | --- |
| Okan | Contract v1.2 (#63) and the v1.3 A2A amendment; architecture spike in the test repository (A2A, self-correction, acceptance check, orchestrator, web interface); test-day `.env` files and coordination (his owned area: `docs/`) |
| Baran + Can | PR #64: master decomposition, template copy, task inputs, records contract; review of the merged master-side code (`dap/master/core/`, `api/`, `db/`) |
| Eray | PR #65: worker template generation, output validation, #68 fix; review of the merged worker-side code (`dap/worker/`, `templates/`) |
| Fatma | Review and adoption of the new web interface (`frontend/`): pages, polling, theming; Sprint 2 board work carried over |
| Abdurrahman | Measurement script improvements (both implementation lines merged); review of the test-day tooling (`scripts/`, `tests/`, CI plan) |
| Hamza | Sprint planning and recovery plan, Sprint 2 report, this report, evidence collection and demo coordination (`docs/sprints/`) |
| Everyone | Ran a worker on their own PC on test day and reported connection status |

## Tests and evidence

- Full suite on the integration branch, 18 November: **264 passed, 0 failed**
  (`pytest`, includes A2A server, orchestrator, acceptance, self-correction,
  generated-app and test-day script tests).
- Full suite after merging Okan's latest features, 25 November: **280 passed,
  0 failed** (adds the preview, author-line, cancel-run and `no_think` tests),
  and **CI green on `main`** after the team merge (7b2af8d).
- **Real-model end-to-end run on one PC, 19 November 01:05**
  ([evidence](evidence/README.md)): master + two workers over A2A, one local
  model (gemma4-26b, thinking disabled); requirement `kisa.md` → decompose 8 s
  → four tasks done by the workers in 131 s → generated app running → master
  acceptance check **9 of 9 passed**. Full log ends with `E2E PASSED`.
- Test-day records: connection checks of six workers, the models each member runs,
  and per-question measurement results in `docs/models.md` (gemma-4-26b measured on
  two PCs; six-agent table with the new scoring rationale).
- Pending evidence: adoption commits of the remaining owners (Can, Eray, Fatma,
  Abdurrahman, Okan) and a generated application run on at least two PCs
  (planned for the Monday session with the prepared requirements).

## Closing week (19–25 November)

- Live demonstration for the instructor on 19 November (master on Baran's PC +
  `agent-hamza` over Tailscale, real model) — **accepted**.
- CI on the branch green on 18 November (264 tests) after two CI-environment
  fixes (`python -m pytest`, and a test accepting both Python 3.11/3.12+ error
  wordings); CI on `main` green on 25 November (280 tests + frontend build).
- 23 November team session: Okan's newest features tested live (Open the app,
  agent signatures, Cancel run, `no_think` fix, context 12288); the team agreed
  to adopt the tested repository into `main`.
- Final merge into `main` on 25 November with the team's agreement: the A2A
  implementation, contract v1.3, parallel run mode, sprint reports and the
  real-model E2E evidence are now the team's main line.

## Retrospective input

The Sprint 2 proposal (one repeatable integrated checkpoint before a card is
declared complete) was effectively applied this sprint through the test day and
the adoption review. Formal retrospective decision: **pending team confirmation.**

The team's decisions and working rules of this sprint are now recorded in one
place: [the decisions log](../../decisions-log.md) (distilled from the team
group on 26 November) — including the 2026-11-18 architecture vote with its
exact context, and the 2026-11-18 adoption procedure.
