# Team Decisions Log — Distributed AI Dev Platform

Owner: Hamza (Scrum Master) · Source: the team's WhatsApp group ("Software
Engineering Process and DevOps"), read in full on 26 November 2026 and
distilled here. Phone numbers, meeting links and personal messages are
sanitized out; every entry names its date, the decision, and where it lives in
the repository today.

The log exists because Scrum records decisions where they can be re-read, not
only where they were typed. When a decision changed the repository, the
commit/PR is linked.

---

## Sprint 1 (1–15 October)

**2026-10-15 · API paths and browser access.** The frontend reported three
mismatches between the contract and the running master: endpoint paths, GET
authentication and CORS. Decision (Hamza, same morning, implemented and tested
in PR #32, contract appendix PR #20): the frontend uses the `/api/v1/...`
paths of the contract; GET requests stay tokenless (browser sends no token),
write and heartbeat paths keep the token; CORS is opened for the dev origin.
*Why it matters: first recorded case of a contract–code disagreement resolved
by a written decision instead of a private fix.*

**2026-10-15 · The board moves to Trello.** The shared board becomes the
mirror of the sprint backlog; issues stay in GitHub.

## Sprint 2 (15–29 October)

**2026-10-18 · Working rules of the team (standing agreements).** Posted with
the Sprint 2 plan and applied from then on:
- one branch + one pull request per card; no direct pushes to `main`;
- `pytest` green before every commit;
- small pull requests, fast reviews;
- the balance rule: nobody sits waiting — while blocked, you move to your
  next card;
- written stand-up by the Scrum Master 2–3 times a week.

**2026-10-24 · Sprint 2 closes only live.** Closing rule for the sprint:
`LLM_MOCK=0` on every machine for the closing live test — no mocked outputs
count, and nothing is carried to the next day. The eight closing criteria were
posted and agreed; the 23:00 live test followed.

## Sprint 3 (4–25 November)

**2026-11-04 · Cross-PC testing becomes the standard.** Hamza named the gap:
members were testing only on their own machines while the system is
distributed. Decision: connected parts are tested together, on different PCs,
and the result is written into the issue/PR (who tested, which machines,
result, commit, remaining impediment). Never share tokens or `.env` files in
the group.

**2026-11-04 · The measurement wave.** The missing per-model measurements
(S2-04) were unblocked with a written step-by-step guide every member could
run; results go into `docs/models.md` as pull requests, nobody writes
`agents.json` directly.

**2026-11-16 · The cross-testing matrix.** Hamza published the per-person
testing matrix (who tests what with whom, linked issues and PRs) — the basis
of the 17 November joint session.

**2026-11-17 · Joint test evening (21:30, Google Meet).** The team cloned the
architecture-test repository and ran it together; per-PC environment files
were distributed through the session (not through the group chat). Records:
connection checks, master URL per machine.

**2026-11-18 · The architecture decision (A2A adoption).** Two diverging
codebases existed: Okan's architecture-test repository (master sends tasks to
workers over A2A; 259 tests; live-tested on 17 November) and the main line
(workers pull tasks; Baran/Can/Eray's Sprint 3 work). Hamza put three options
to a vote with honest pros and cons (A: adopt Okan's copy outright; B: keep
the team line and port Okan's extras; C: formal decision + adoption with
per-owner review commits). Outcome: **C** — recorded as the team decision in
[Sprint 3 report](sprint-3/report.md) and executed as merge `7b2af8d` on
25 November. For the record: one member (Okan) objected to deciding that
night and proposed the weekend; one member (Can) supported C with the
modification of deferring integration to the next sprint; the decision was
taken on the same night because Sprint 3 closed the next day, and the
integration was executed the same night as C planned.

**2026-11-18 · The adoption procedure.** Every owner reviews their own area of
the merged code on the adoption branch, runs the tests, and signs with one
adoption commit (`S3: adopt my area …`). Assignments: Baran → `dap/master/`
core+api, Can → `dap/master/db/`, Eray → `dap/worker/` + `templates/`, Fatma →
`frontend/src/`, Abdurrahman → `scripts/` + `tests/`, Okan → contract v1.3.
Status: Baran done (`2999e0e`); the rest tracked as an open item since.

**2026-11-22 · Test-day scheduling by vote.** A poll fixed the joint test day
(Monday 20:30); the warning that non-attendance carries its consequences was
pinned at the owner's request.

**2026-11-23 · Joint test session.** Held as scheduled (Google Meet); the
tested repository and the live master address were shared in the session; the
results fed the Sprint 3 report and the 25 November merge.

## Sprint 4 (25–26 November)

**2026-11-25 · Sprint 4 opens as a pull-based sprint.** After the merge, the
Scrum Master pulled one card at a time from the live-testing findings and
closed each to Done before the next ([planning](sprints/sprint-4/planning.md)).
No separate WhatsApp decision was needed — the cards came straight from the
sprint goal and the Definition of Done rules of 2026-10-18.

**2026-11-26 · Personal files stay local.** The personal experiment folders
(`local-stack/`, `docs/local-stack/`, `docs/superpowers/`, `docs/adr/`) are
ignored wholesale (commit `d35b7c9`) so no `git add -A` can sweep them into
the shared repository again.
