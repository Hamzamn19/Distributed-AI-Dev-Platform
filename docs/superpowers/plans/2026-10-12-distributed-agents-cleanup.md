# distributed-agents Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep only the useful, contract-conformant content from `distributed-agents/` and delete the rest.

**Architecture:** Audit `distributed-agents/` file-by-file against the team contract (`docs/PROJECT_CONTRACT.md`, Section 5) and the main repo layout (`backend/`, `agents/`, `frontend/`, `tests/`, `docs/`); copy KEEP items to their canonical main-repo homes; delete stubs, caches, and empty placeholders; remove the proposal folder once extraction is verified.

**Tech Stack:** Python 3.11+, FastAPI + Uvicorn, Pydantic v2, SQLAlchemy 2.x, httpx, openai package (Ollama `/v1/chat/completions`), React + Vite + TypeScript + Tailwind, pytest + TestClient.

**Spec:** Team contract in `distributed-agents/docs/PROJECT_CONTRACT.md` (binding Sections 5.1-5.8) + full team plan pasted in user message (26 pages, CM6453) + Sprint 1 member guide `distributed-agents/docs/sprints/sprint-1/member-guide.md`. Main-repo context: `README.md`, `docs/PROJECT_PLAN.md`, `docs/contracts/README.md`.

## Global Constraints

- Master API prefix is `/api/v1`; Master at `http://localhost:8000`, docs at `http://localhost:8000/docs`.
- Frontend dev at `http://localhost:5173`; Ollama at `http://localhost:11434/v1` (own PC only); worker has no port.
- Env names from `.env.example`: `AGENT_TOKEN, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MOCK, MASTER_HOST, MASTER_PORT, DATABASE_URL, CORS_ORIGINS, HEARTBEAT_TIMEOUT_SEC, MASTER_URL, AGENT_ID, AGENT_NAME, AGENT_OWNER, AGENT_ROLE_HINT, AGENT_CAP_CODING, AGENT_CAP_REASONING, AGENT_CAP_CONTEXT, HEARTBEAT_INTERVAL_SEC, POLL_INTERVAL_SEC, VITE_API_BASE_URL`.
- Enums are lowercase underscore strings; source of truth `dap/shared/enums.py`; frontend `types.ts` mirrors them.
- Field names `snake_case` everywhere; ids are UUID4 strings; time fields end `_at`, UTC ISO 8601; missing value = `null`; unknown field = 422; error shape `{"detail": "message"}`; `requirement_text` min 20 chars.
- Task flow `pending -> assigned -> in_progress -> completed|failed`; failed returns to `pending` with `attempt+1`, max 3 attempts.
- `api/` and `core/` never use SQL/session; only call `repositories.py`; repositories return `schemas.py` models, never ORM objects.
- Settings only from `.env` via `get_settings()`; never hard-code model name, URL, port, token.
- Never commit `.env`, `data/`, `workspace/`; code/comments/commits/UI text in English.
- Not used: Celery, Redis, RabbitMQ, Socket.io, WebSocket, SSE, LangChain, LangGraph.
- Sprint 1 `/assign` rule: task goes to agent whose `role_hint` equals task type; online status not checked.
- Tests never touch `data/dap.db`: `conftest.py` points `DATABASE_URL` at `data/test.db` and sets `LLM_MOCK=1`.

## Review Focus

- `dap/` vs `backend/`+`agents/` layout conflict: main repo splits backend/agents, contract mandates single `dap` package — copying `dap/shared` to `backend/` breaks imports; expect import-path breakage if layout changes without updating all imports.
- `docs/contracts/` vs `docs/PROJECT_CONTRACT.md` duplication: two sources of truth will drift; expect stale contract if both kept.
- `frontend/.env` vs root `.env`: frontend example was found at `distributed-agents/frontend/.env.example` but `ls -R frontend` shows only `README.md` + `src/api/types.ts`; expect missing-file confusion if plan assumes it exists.
- Empty `scripts/` + missing `seed_agents.py`/`smoke_test.py`: assign/decompose cannot be demoed without them; expect demo failure if stubs deleted before scripts exist.
- `test_contract.py` validates `docs/agents.json` (6 unique ids): moving/editing `agents.json` without re-running contract tests will silently break seed data.

---

### Task 1: Preserve binding contract docs

**Files:**
- Create: `docs/contracts/PROJECT_CONTRACT.md` (copy from `distributed-agents/docs/PROJECT_CONTRACT.md`)
- Create: `docs/SETUP.md` (copy from `distributed-agents/docs/SETUP.md`, verify Tailscale + `OLLAMA_CONTEXT_LENGTH` notes)
- Create: `docs/agents.json` (copy from `distributed-agents/docs/agents.json`, 6 agents)
- Create: `docs/sprints/sprint-1/member-guide.md` + `planning.md` (copy from `distributed-agents/docs/sprints/sprint-1/`)
- Test: `tests/test_contract.py` (validates `agents.json` shape)

**Interfaces:**
- Consumes: nothing (source files already verified to exist)
- Produces: canonical doc paths that Tasks 2-4 reference for validation

- [ ] **Step 1: Write the failing check**

```python
def test_contract_docs_present():
    import pathlib
    for p in ["docs/contracts/PROJECT_CONTRACT.md", "docs/SETUP.md",
              "docs/agents.json", "docs/sprints/sprint-1/member-guide.md"]:
        assert pathlib.Path(p).exists(), p
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python -m pytest tests/test_contract_docs_present.py -v`
Expected: FAIL (files not yet copied; `docs/contracts/` holds only placeholder README)

- [ ] **Step 3: Copy the 4 doc items verbatim, no edits**

Run: `cp distributed-agents/docs/PROJECT_CONTRACT.md docs/contracts/PROJECT_CONTRACT.md` (same for SETUP.md, agents.json, sprint-1/*.md)

- [ ] **Step 4: Run check to verify it passes**

Run: `python -m pytest tests/test_contract_docs_present.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/contracts/PROJECT_CONTRACT.md docs/SETUP.md docs/agents.json docs/sprints/sprint-1/
git commit -m "S1-03: preserve binding contract docs from proposal"
```

### Task 2: Preserve implemented shared + config + health code

**Files:**
- Create: `dap/shared/enums.py`, `dap/shared/schemas.py` (verbatim from `distributed-agents/dap/shared/`)
- Create: `dap/master/main.py`, `dap/master/config.py`, `dap/master/api/health.py`
- Create: `dap/worker/config.py`
- Create: `frontend/src/api/types.ts`
- Create: `.env.example`, `requirements.txt`, `pytest.ini` (merge, do not overwrite local-stack secrets)
- Test: `tests/test_contract.py`, `tests/test_health.py`, `tests/test_worker_config.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: Task 1 doc paths (contract values must match code)
- Produces: importable `dap.shared` + `GET /api/v1/health -> {status:ok,version}` + `get_settings()` env mapping

- [ ] **Step 1: Write the failing test (import + health)**

```python
def test_shared_importable_and_health():
    from dap.shared.enums import AgentStatus, TaskType
    from dap.shared.schemas import Agent, Project, Task
    assert AgentStatus.IDLE == "idle"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shared_importable.py -v`
Expected: FAIL with "No module named 'dap'"

- [ ] **Step 3: Copy implemented files verbatim in `dap/` layout (`dap/` single package per contract, not `backend/` split)**

Copy: `enums.py`, `schemas.py`, `master/main.py`, `master/config.py`, `master/api/health.py`, `worker/config.py`, `frontend/src/api/types.ts`, `tests/conftest.py`, `tests/test_contract.py`, `tests/test_health.py`, `tests/test_worker_config.py`. Merge (not overwrite) root `.env.example`, `requirements.txt`, `pytest.ini` after diffing against existing.

- [ ] **Step 4: Run tests to verify they pass (venv with deps)**

Run: `python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pytest tests/test_contract.py tests/test_worker_config.py -v`
Expected: PASS (health test needs fastapi; contract/worker-config tests are pure)

- [ ] **Step 5: Commit**

```bash
git add dap/shared/enums.py dap/shared/schemas.py dap/master/main.py dap/master/config.py dap/master/api/health.py dap/worker/config.py frontend/src/api/types.ts tests/
git commit -m "S1-05: preserve implemented shared contract code"
```

### Task 3: Delete stubs, caches, and empty placeholders

**Files:**
- Delete: all `__pycache__/`, `distributed-agents/.pytest_cache/`
- Delete: `distributed-agents/CLAUDE.md`, `GEMINI.md` (90-byte redirects to AGENTS.md)
- Delete: `distributed-agents/scripts/.gitkeep`, `distributed-agents/data/` (empty), `distributed-agents/docs/sample_requirements/` (empty)
- Delete or keep-as-stub (decide in review): 13x `NotImplementedError` in `repositories.py`, `decomposer.py`, `selector.py`, `cli.py`, `llm_client.py` (2x), `worker/main.py`, `worker/master_client.py` (2x); bare routers `agents.py`, `projects.py`; docstring-only `database.py`, `models.py`; missing `frontend/src/api/client.ts`, `pages/`, `scripts/seed_agents.py`, `smoke_test.py`
- Test: `grep -rn NotImplementedError` returns expected set; `pytest` still green

**Interfaces:**
- Consumes: Task 2 preserved files (must still import after deletions)
- Produces: clean tree with no dead placeholders

- [ ] **Step 1: Write the failing check (no caches, no empty dirs)**

```bash
test ! -d distributed-agents/.pytest_cache && test -z "$(find distributed-agents -name __pycache__)" && echo CLEAN
```

- [ ] **Step 2: Run check to verify it fails**

Run: above one-liner
Expected: FAIL (caches exist — verified Oct 12: `.pytest_cache/` + 6x `__pycache__/` present)

- [ ] **Step 3: Delete caches + redirect dupes + empty placeholders (`rm -rf` only listed paths, never `data/dap.db` outside proposal)**

```bash
find distributed-agents -name __pycache__ -type d -exec rm -rf {} +; rm -rf distributed-agents/.pytest_cache; rm distributed-agents/CLAUDE.md distributed-agents/GEMINI.md distributed-agents/scripts/.gitkeep; rmdir distributed-agents/data distributed-agents/docs/sample_requirements 2>/dev/null || true
```

- [ ] **Step 4: Run tests + import check to verify nothing broke**

Run: `python -c "import dap.shared.enums, dap.shared.schemas; print('imports ok')" && pytest tests/test_contract.py -q`
Expected: PASS / imports ok

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "S1-02: remove caches and empty placeholders from proposal"
```

### Task 4: Remove the proposal folder after extraction is verified

**Files:**
- Delete: `distributed-agents/` (entire folder, only after Tasks 1-3 PASS + reviewer approval)
- Test: root `pytest` green; `git status` shows only intended `dap/`, `docs/`, `frontend/src/api/types.ts`, `tests/` additions

**Interfaces:**
- Consumes: Tasks 1-3 outputs (docs + code + clean tree)
- Produces: single canonical repo layout, no duplicate `dap` vs `backend` confusion

- [ ] **Step 1: Write the failing check (no duplicate package)**

```python
def test_no_duplicate_proposal():
    import pathlib
    assert not pathlib.Path("distributed-agents").exists()
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python -m pytest tests/test_no_duplicate_proposal.py -v`
Expected: FAIL (folder still exists pre-approval)

- [ ] **Step 3: Delete folder only after human confirms Tasks 1-3 diff (`git rm -r distributed-agents`)**

- [ ] **Step 4: Run full verification**

Run: `pytest -q && git status --short`
Expected: PASS, status shows only Task 1-2 additions

- [ ] **Step 5: Commit**

```bash
git rm -r distributed-agents
git commit -m "S1-02: remove proposal folder after extracting contract code"
```
