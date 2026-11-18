# Sprint 3 Report — Distributed AI Dev Platform

Dates: 4–18 November 2026 · Owner: Hamza · Sources: [planning.md](planning.md), [task-distribution.md](task-distribution.md), Issue [#61](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/issues/61), PRs [#63](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/63), [#64](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/64), [#65](https://github.com/Hamzamn19/Distributed-AI-Dev-Platform/pull/65)

**Updated 18 November 2026, the closing day.** Records below come from git history,
pull requests and the test-day checklist; states that still need a person's
confirmation are marked pending.

## Goal and result

The goal was to generate a small web application from a real requirement with the
fixed template: requirement → decompose → assign → worker generation → running
application, with a live multi-PC test. **Result: the architecture decision is made
and its implementation is merged and green (264 passing tests); the closing demo
evidence per PC is the remaining item, scheduled with the per-owner adoption review
on 19 November.**

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
5. **Per-owner adoption review (19 November, pending).** Every owner reviews the
   merged code of their own folders and commits an adoption confirmation, so the
   A2A implementation becomes the team's reviewed code, not one person's spike.

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
- Test-day records: connection checks of six workers, the models each member runs,
  and per-question measurement results in `docs/models.md` (gemma-4-26b measured on
  two PCs; six-agent table with the new scoring rationale).
- Pending evidence: per-owner adoption commits (19 November), a generated
  application run on at least two PCs, and the CI workflow running the full suite.

## Retrospective input

The Sprint 2 proposal (one repeatable integrated checkpoint before a card is
declared complete) was effectively applied this sprint through the test day and
the adoption review. Formal retrospective decision: **pending team confirmation.**
