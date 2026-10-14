# Contract Amendment v1.1 — PROPOSAL (not binding until Okan merges it)

Supplements `docs/contracts/PROJECT_CONTRACT.md`. Additive only: no banned
technology is unbanned, no endpoint/field/enum is renamed. Written Oct 14
after a gap audit against the assignment expectations.

## A1. Task classifier (Sprint 2)

Pure function, rules first, LLM fallback:

```python
# dap/master/core/classifier.py (new file, Baran+Eray)
classify_task(title: str, description: str) -> TaskType
required_capabilities(task_type: TaskType) -> dict  # {"coding":0-100,...}
```

Rules: keyword match on title/description (e.g. "table/schema" -> database,
"page/screen" -> frontend, "test" -> testing, "API/endpoint" -> backend).
Tie or no match -> ask the master model (same `chat()` + `think=False` rule
as the decomposer), validate against `TaskType`, fall back to `backend`.

## A2. Capability measurement (Sprint 2)

Same 5 questions for every model, scored 0-100 per dimension:
coding (unit-test pass rate on 2 micro-tasks), reasoning (2 checked Q&A),
context (1 needle-in-haystack). Method: `scripts/measure_model.py`
(Eray writes, Hamza reviews). Scores replace the Sprint 1 estimates in
`docs/agents.json`; re-measure whenever a model changes.

## A3. Score-based selection (Sprint 2)

Replaces the Sprint 1 `role_hint` rule without changing the path or answer
shape. Adapted from the proven `master/router.py` formula:

```python
# dap/master/core/selector.py
S = (w_c * C) + (w_r * R) + (w_x * X) + (10 * u) - (15 * q)
```

`C/R/X` = agent capability scores; `u` = 1 when `role_hint` equals the task
type (role_hint becomes the tiebreak); `q` = agent's active tasks.
Weights per task type (`w_c/w_r/w_x`) live in `selector.py` as constants;
tuning is a Sprint 5 activity. Highest S wins; ties -> first agent.

## A4. Long requirement documents

Sprint 1: `requirement_text` hard limit is 12000 characters; longer input is
rejected with 422 ("split the document and submit in parts").
Sprint 2: chunk + map-reduce summary on the master before `decompose()`.

## A5. Architect step (Sprint 3)

Before fan-out, the master emits one JSON sketch
`{"api": [...endpoints...], "schema": [...tables...]}` and attaches it to
every task's context. Agents fill a fixed template; no agent invents
endpoints or tables.

## A6. Live updates stay polling

No Socket.io/WebSocket/SSE, permanently: the frontend re-fetches every 3 s.
Rationale: 6 workers, demo scale; sockets add a failure mode with no grading
benefit.

## A7. Generated-app workspace

Per-run output goes to `workspace/<run-id>/` (already git-ignored).
`workspace/` layout is per-template and defined with the Sprint 3 template.

## Reaffirmed bans (scale justification, 6 workers / 1 master)

Celery/Redis (direct HTTPS calls suffice), PostgreSQL (single master writer;
SQLite suffices), LangChain/LangGraph (plain functions; YAGNI),
cloud LLM APIs (course rule: local models only).

## Okan's review checklist

- [ ] A1-A7 match the assignment expectations (Section 2 of the Trello plan)
- [ ] No endpoint/field/enum renamed; `dap/shared/` untouched
- [ ] Merge into `PROJECT_CONTRACT.md` the same day; then this file is deleted
