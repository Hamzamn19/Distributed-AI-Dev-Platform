import uuid

import pytest
from fastapi.testclient import TestClient

from dap.master.api import projects
from dap.master.core import decomposer
from dap.master.main import app
from dap.shared.enums import SPRINT1_TASK_TYPES
from dap.shared.schemas import Project, Task

client = TestClient(app)

BODY = {"name": "Library", "requirement_text": "A library app where members borrow and return books."}


def _create() -> dict:
    response = client.post("/api/v1/projects", json=BODY)
    assert response.status_code == 201
    return response.json()


def test_create_project_returns_contract_project():
    project = Project.model_validate(_create())
    assert project.status == "created"
    uuid.UUID(project.id, version=4)


@pytest.mark.parametrize("body", [
    {"name": "x", "requirement_text": "short"},
    {"name": "x"},
])
def test_create_project_rejects_bad_body(body):
    assert client.post("/api/v1/projects", json=body).status_code == 422


def test_list_and_get_project():
    created = _create()
    listed = client.get("/api/v1/projects").json()
    assert created["id"] in [p["id"] for p in listed]
    assert client.get(f"/api/v1/projects/{created['id']}").json()["id"] == created["id"]


def test_unknown_project_gives_404():
    missing = str(uuid.uuid4())
    for method, path in [("get", ""), ("get", "/tasks"), ("post", "/decompose")]:
        response = getattr(client, method)(f"/api/v1/projects/{missing}{path}")
        assert response.status_code == 404
        assert "detail" in response.json()


def test_new_project_has_no_tasks():
    project = _create()
    assert client.get(f"/api/v1/projects/{project['id']}/tasks").json() == []


def test_decompose_stores_four_tasks_with_dependencies():
    project = _create()
    response = client.post(f"/api/v1/projects/{project['id']}/decompose")
    assert response.status_code == 200
    tasks = [Task.model_validate(t) for t in response.json()]
    assert len(tasks) == 4
    assert {t.type for t in tasks} == set(SPRINT1_TASK_TYPES)
    ids = {t.id for t in tasks}
    assert all(set(t.depends_on) <= ids for t in tasks)
    assert any(t.depends_on for t in tasks)
    assert all(t.project_id == project["id"] and t.status == "pending" for t in tasks)

    stored = client.get(f"/api/v1/projects/{project['id']}/tasks").json()
    assert {t["id"] for t in stored} == ids
    assert client.get(f"/api/v1/projects/{project['id']}").json()["status"] == "in_progress"


def test_decompose_twice_returns_existing_tasks():
    project = _create()
    first = client.post(f"/api/v1/projects/{project['id']}/decompose").json()
    second = client.post(f"/api/v1/projects/{project['id']}/decompose").json()
    assert {t["id"] for t in second} == {t["id"] for t in first}
    assert len(client.get(f"/api/v1/projects/{project['id']}/tasks").json()) == 4


def test_unreachable_model_fails_project_with_502(monkeypatch):
    def down(requirement_text):
        raise RuntimeError("LLM did not answer")

    monkeypatch.setattr(projects.decomposer, "decompose", down)
    project = _create()
    response = client.post(f"/api/v1/projects/{project['id']}/decompose")
    assert response.status_code == 502
    assert "LLM did not answer" in response.json()["detail"]
    assert client.get(f"/api/v1/projects/{project['id']}").json()["status"] == "failed"
    assert client.get(f"/api/v1/projects/{project['id']}/tasks").json() == []


def test_decompose_end_to_end_uses_mock_llm():
    assert decomposer.chat.__module__ == "dap.shared.llm_client"
    project = _create()
    tasks = client.post(f"/api/v1/projects/{project['id']}/decompose").json()
    assert [t["title"] for t in tasks]
