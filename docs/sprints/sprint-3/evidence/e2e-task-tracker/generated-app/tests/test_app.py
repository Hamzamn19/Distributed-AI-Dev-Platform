import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_task_lifecycle():
    # Create
    res = client.post("/api/tasks", json={"title": "Task 1", "description": "Desc 1"})
    assert res.status_code == 201
    task_id = res.json()["id"]

    # List
    res = client.get("/api/tasks")
    assert res.status_code == 200
    assert any(t["id"] == task_id for t in res.json())

    # Get
    res = client.get(f"/api/tasks/{task_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Task 1"

    # Update
    res = client.put(f"/api/tasks/{task_id}", json={"title": "Updated Task"})
    assert res.status_code == 200
    assert res.json()["title"] == "Updated Task"

    # Complete (Action)
    res = client.patch(f"/api/tasks/{task_id}/complete")
    assert res.status_code == 200
    res = client.get(f"/api/tasks/{task_id}")
    # The backend uses 'is_completed' or similar, checking for truthiness in the field
    assert res.json()["is_completed"] is True

    # Delete
    res = client.delete(f"/api/tasks/{task_id}")
    assert res.status_code == 204

def test_business_rules():
    # Rule: Title cannot be empty (backend returns 400 for validation errors)
    res = client.post("/api/tasks", json={"title": "", "description": "No title"})
    assert res.status_code == 400

    # Rule: Title max length (assuming 50)
    res = client.post("/api/tasks", json={"title": "a" * 51, "description": "Too long"})
    assert res.status_code == 400

def test_stats_endpoint():
    # Verify stats works - backend returns {'tasks': count}
    res = client.get("/api/stats")
    assert res.status_code == 200
    assert "tasks" in res.json()

def test_not_found():
    res = client.get("/api/tasks/99999")
    assert res.status_code == 404
