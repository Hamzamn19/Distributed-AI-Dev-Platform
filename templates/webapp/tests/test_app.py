"""TESTING TASK FILE - the testing task replaces this example.

Run from the project folder:  pytest
Each test uses its own database file through the APP_DB variable and calls
the API only through TestClient.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB", str(tmp_path / "test.db"))
    from backend import database
    from backend.main import app

    database.init_db()
    return TestClient(app)


def test_list_is_empty_at_start(client):
    response = client.get("/api/items")
    assert response.status_code == 200
    assert response.json() == []


def test_create_then_list(client):
    created = client.post("/api/items", json={"name": "first"})
    assert created.status_code == 201
    assert created.json()["name"] == "first"
    assert [i["name"] for i in client.get("/api/items").json()] == ["first"]


def test_search_filters_the_list(client):
    client.post("/api/items", json={"name": "apple"})
    client.post("/api/items", json={"name": "pear"})
    found = client.get("/api/items", params={"search": "app"}).json()
    assert [i["name"] for i in found] == ["apple"]


def test_empty_name_is_rejected(client):
    assert client.post("/api/items", json={"name": "  "}).status_code == 400
