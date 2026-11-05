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


def _seed_project_with(tasks: list[tuple[str, list[str]]], types=None):
    """Create one project; `tasks` is a list of (task_id, depends_on)."""
    project = repositories.create_project(ProjectCreate(
        name="Worker flow", requirement_text="requirement for the worker endpoint tests",
    ))
    created = repositories.create_tasks(project.id, [
        TaskCreate(id=task_id, title=task_id, description="do it",
                   type=(types or {}).get(task_id, TaskType.BACKEND), depends_on=deps)
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
        "summary": "done", "files": [{"path": "backend/main.py", "content": "print(1)\n"}],
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


def test_next_waits_for_dependencies_of_an_already_assigned_task(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    _seed_agent("worker-b")
    _seed_project_with([("t-one", []), ("t-two", ["t-one"])])
    repositories.assign_task("t-one", "worker-b", "picked")
    repositories.assign_task("t-two", "worker-a", "picked")
    assert _next("worker-a").status_code == 204
    assert _result("t-one", _payload("t-one", "worker-b")).status_code == 200
    assert _next("worker-a").json()["id"] == "t-two"


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
    saved = tmp_path / r.json()["project_id"] / "backend/main.py"   # no run folder (contract 12.1)
    assert saved.read_text(encoding="utf-8") == "print(1)\n"


def test_result_files_overwrite_the_template_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    project, _ = _seed_project_with([("t-one", [])])
    (tmp_path / project.id / "backend").mkdir(parents=True)
    (tmp_path / project.id / "backend/main.py").write_text("# template\n", encoding="utf-8")
    repositories.assign_task("t-one", "worker-a", "picked")
    assert _result("t-one", _payload("t-one", "worker-a")).status_code == 200
    assert (tmp_path / project.id / "backend/main.py").read_text(encoding="utf-8") == "print(1)\n"


# -------------------------------------------------------------- inputs


def _inputs(task_id: str, headers: dict | None = None):
    return client.get(f"/api/v1/tasks/{task_id}/inputs",
                      headers=headers if headers is not None else _auth())


def _complete(task_id: str, files: list[dict], tmp_path, monkeypatch, success=True):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    repositories.assign_task(task_id, "worker-a", "picked")
    r = _result(task_id, _payload(task_id, "worker-a", files=files, success=success,
                                  error=None if success else "boom"))
    assert r.status_code == 200


def test_inputs_needs_the_token_and_a_known_task():
    _seed_agent()
    _seed_project_with([("t-one", [])])
    assert _inputs("t-one", headers={}).status_code == 401
    assert _inputs("missing").status_code == 404


def test_inputs_of_a_task_without_dependencies_is_empty():
    _seed_agent()
    _seed_project_with([("t-one", [])])
    assert _inputs("t-one").json() == []


def test_inputs_give_the_files_of_the_dependencies(tmp_path, monkeypatch):
    _seed_agent()
    _seed_project_with([("t-db", []), ("t-api", ["t-db"]), ("t-ui", ["t-db", "t-api"]),
                        ("t-other", [])], {"t-db": TaskType.DATABASE, "t-other": TaskType.FRONTEND})
    _complete("t-db", [{"path": "backend/database.py", "content": "db\n"}], tmp_path, monkeypatch)
    _complete("t-api", [{"path": "backend/main.py", "content": "api\n"}], tmp_path, monkeypatch)
    _complete("t-other", [{"path": "frontend/index.html", "content": "x\n"}], tmp_path, monkeypatch)
    assert _inputs("t-api").json() == [{"path": "backend/database.py", "content": "db\n"}]
    assert _inputs("t-ui").json() == [
        {"path": "backend/database.py", "content": "db\n"},
        {"path": "backend/main.py", "content": "api\n"},
    ]


def test_inputs_skip_a_dependency_without_a_successful_result(tmp_path, monkeypatch):
    _seed_agent()
    _seed_project_with([("t-db", []), ("t-api", ["t-db"])], {"t-db": TaskType.DATABASE})
    _complete("t-db", [], tmp_path, monkeypatch, success=False)
    assert _inputs("t-api").json() == []


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


@pytest.mark.parametrize("paths", [["backend/main.py"], ["backend/database.py", "backend/main.py"], []])
def test_database_result_cannot_overwrite_backend(tmp_path, monkeypatch, paths):
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path)
    _seed_agent()
    project, _ = _seed_project_with([("db-task", [])], {"db-task": TaskType.DATABASE})
    backend = tmp_path / project.id / "backend"
    backend.mkdir(parents=True)
    original = backend / "main.py"
    original.write_text("# original", encoding="utf-8")
    repositories.assign_task("db-task", "worker-a", "picked")
    response = _result("db-task", _payload("db-task", "worker-a", files=[
        {"path": path, "content": "# overwritten"} for path in paths
    ]))
    assert response.status_code == 422
    assert original.read_text(encoding="utf-8") == "# original"
    assert not (backend / "database.py").exists()
    assert repositories.get_task("db-task").status == TaskStatus.ASSIGNED
    accepted = _result("db-task", _payload("db-task", "worker-a", files=[
        {"path": "backend/database.py", "content": "# valid"}
    ]))
    assert accepted.status_code == 200
    assert (backend / "database.py").read_text(encoding="utf-8") == "# valid"
