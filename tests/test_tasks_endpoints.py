"""Worker endpoints: GET /agents/{id}/tasks/next and POST /tasks/{id}/result.

Owner: Baran - card S2-01 (worker endpoints, team authorization 23 October).
"""

import os
import sqlite3
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from dap.master.api import tasks as tasks_api
from dap.master.config import get_settings
from dap.master.db import repositories
from dap.master.main import app
from dap.shared.enums import TaskStatus, TaskType
from dap.shared.schemas import (
    AgentRegister,
    Capabilities,
    ProjectCreate,
    TaskCreate,
)

client = TestClient(app)
NOW = datetime.now(timezone.utc)

# Children before parents on delete, parents before children on restore.
_TABLES = ("task_results", "events", "tasks", "projects", "agents")


def _connect() -> sqlite3.Connection:
    url = os.environ["DATABASE_URL"]
    assert url.startswith("sqlite:///"), url
    return sqlite3.connect(url.removeprefix("sqlite:///"))


@pytest.fixture(autouse=True)
def _isolated_tables():
    """Empty every table per test so earlier test files cannot leak rows."""
    conn = _connect()
    saved = []
    for table in _TABLES:
        cursor = conn.execute(f"SELECT * FROM {table}")
        saved.append((table, [d[0] for d in cursor.description], cursor.fetchall()))
    for table, _, _ in reversed(saved):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    try:
        yield
    finally:
        conn = _connect()
        for table, _, _ in reversed(saved):
            conn.execute(f"DELETE FROM {table}")
        for table, columns, rows in saved:
            if rows:
                marks = ",".join("?" * len(columns))
                conn.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})", rows
                )
        conn.commit()
        conn.close()


def _auth() -> dict:
    return {"X-Agent-Token": get_settings().agent_token}


def _seed_agent(agent_id: str = "worker-a"):
    repositories.upsert_agent(AgentRegister(
        agent_id=agent_id, name=agent_id, owner="Tester", model="qwen3:4b",
        role_hint=TaskType.BACKEND,
        capabilities=Capabilities(coding=60, reasoning=50, context=40),
    ))


def _seed_project_with(tasks: list[tuple[str, list[str]]]):
    """Create one project; `tasks` is a list of (task_id, depends_on)."""
    project = repositories.create_project(ProjectCreate(
        name="Worker flow", requirement_text="requirement for the worker endpoint tests",
    ))
    created = repositories.create_tasks(project.id, [
        TaskCreate(id=task_id, title=task_id, description="do it",
                   type=TaskType.BACKEND, depends_on=deps)
        for task_id, deps in tasks
    ])
    return project, {task.id: task for task in created}


def _next(agent_id: str, headers: dict | None = None):
    return client.get(f"/api/v1/agents/{agent_id}/tasks/next",
                      headers=headers if headers is not None else _auth())


def _result(task_id: str, body: dict, headers: dict | None = None):
    return client.post(f"/api/v1/tasks/{task_id}/result", json=body,
                       headers=headers if headers is not None else _auth())


def _payload(task_id: str, agent_id: str, **over) -> dict:
    body = {
        "task_id": task_id, "agent_id": agent_id, "success": True,
        "summary": "done", "files": [{"path": "main.py", "content": "print(1)\n"}],
        "error": None, "duration_ms": 1000, "tokens_used": 50,
    }
    body.update(over)
    return body


# ---------------------------------------------------------------- next


def test_next_needs_the_token():
    _seed_agent()
    for headers in ({}, {"X-Agent-Token": "wrong"}):
        assert _next("worker-a", headers=headers).status_code == 401


def test_next_unknown_agent_is_404():
    response = _next("no-such-agent")
    assert response.status_code == 404


def test_next_is_204_when_nothing_is_ready():
    _seed_agent()
    assert _next("worker-a").status_code == 204


def test_next_hands_a_pending_task_with_completed_dependencies():
    _seed_agent()
    project, tasks = _seed_project_with([("t-one", []), ("t-two", ["t-one"])])
    response = _next("worker-a")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "t-one"
    assert body["status"] == "assigned"
    assert body["assigned_agent_id"] == "worker-a"
    assert body["assignment_reason"]
    # Asking again returns the same task (the agent's own), never t-two,
    # whose dependency t-one is not completed yet.
    second = _next("worker-a")
    assert second.status_code == 200
    assert second.json()["id"] == "t-one"


def test_next_skips_a_task_whose_dependency_is_not_completed():
    _seed_agent()
    _seed_agent("worker-b")
    _seed_project_with([("t-one", []), ("t-two", ["t-one"])])
    # t-one is assigned (not completed), so t-two must not be handed out.
    repositories.assign_task("t-one", "worker-a", "picked")
    assert _next("worker-b").status_code == 204


def test_next_returns_the_agents_own_assigned_task_first():
    _seed_agent()
    _seed_agent("worker-b")
    _, tasks = _seed_project_with([("t-one", []), ("t-two", [])])
    repositories.assign_task("t-two", "worker-a", "given earlier")
    response = _next("worker-a")
    assert response.status_code == 200
    assert response.json()["id"] == "t-two"
    # worker-b does not inherit it.
    response = _next("worker-b")
    assert response.status_code == 200
    assert response.json()["id"] == "t-one"


# ---------------------------------------------------------------- result


def test_result_needs_the_token():
    _seed_agent()
    _, tasks = _seed_project_with([("t-one", [])])
    repositories.assign_task("t-one", "worker-a", "picked")
    for headers in ({}, {"X-Agent-Token": "wrong"}):
        r = _result("t-one", _payload("t-one", "worker-a"), headers=headers)
        assert r.status_code == 401


def test_result_unknown_task_is_404():
    _seed_agent()
    assert _result("t-missing", _payload("t-missing", "worker-a")).status_code == 404


def test_result_from_another_agent_is_403():
    _seed_agent()
    _seed_agent("worker-b")
    _, tasks = _seed_project_with([("t-one", [])])
    repositories.assign_task("t-one", "worker-a", "picked")
    r = _result("t-one", _payload("t-one", "worker-b"))
    assert r.status_code == 403


def test_result_body_id_must_match_the_path():
    _seed_agent()
    _, tasks = _seed_project_with([("t-one", [])])
    repositories.assign_task("t-one", "worker-a", "picked")
    r = _result("t-one", _payload("t-other", "worker-a"))
    assert r.status_code == 422


def test_success_result_completes_the_task_and_saves_files(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    _, tasks = _seed_project_with([("t-one", [])])
    repositories.assign_task("t-one", "worker-a", "picked")
    r = _result("t-one", _payload("t-one", "worker-a"))
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    run_dirs = list((tmp_path / r.json()["project_id"]).iterdir())
    assert len(run_dirs) == 1
    saved = run_dirs[0] / "main.py"
    assert saved.read_text(encoding="utf-8") == "print(1)\n"


def test_identical_delivery_twice_stores_one_result(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    _, tasks = _seed_project_with([("t-one", [])])
    repositories.assign_task("t-one", "worker-a", "picked")
    body = _payload("t-one", "worker-a")
    assert _result("t-one", body).status_code == 200
    again = _result("t-one", body)
    assert again.status_code == 200
    assert again.json()["status"] == "completed"
    from dap.master.db import results
    assert len(results.list_task_results("t-one")) == 1


def test_failed_result_requeues_until_three_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    _, tasks = _seed_project_with([("t-one", [])])
    # Attempt 1 fails -> pending with attempt 1.
    repositories.assign_task("t-one", "worker-a", "picked")
    r = _result("t-one", _payload("t-one", "worker-a", success=False, summary="broke",
                                  files=[], error="boom"))
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    assert r.json()["attempt"] == 1
    # Attempt 2 fails -> pending with attempt 2.
    assert _next("worker-a").json()["attempt"] == 1
    r = _result("t-one", _payload("t-one", "worker-a", success=False, summary="broke",
                                  files=[], error="boom"))
    assert r.json()["status"] == "pending"
    assert r.json()["attempt"] == 2
    # Attempt 3 fails -> stays failed; the counter only grows when the task
    # returns to pending (contract section 6), so it stops at 2.
    assert _next("worker-a").status_code == 200
    r = _result("t-one", _payload("t-one", "worker-a", success=False, summary="broke",
                                  files=[], error="boom"))
    assert r.json()["status"] == "failed"
    assert r.json()["attempt"] == 2
    assert _next("worker-a").status_code == 204
