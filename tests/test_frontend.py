"""The master serves the built web interface and the API on one address."""

import pytest
from fastapi.testclient import TestClient

from dap.master import main
from dap.master.main import app

client = TestClient(app)


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>DAP UI</html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('dap')", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    return tmp_path


def test_root_serves_the_built_ui(dist):
    response = client.get("/")
    assert response.status_code == 200
    assert "DAP UI" in response.text


def test_asset_files_are_served(dist):
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_unknown_react_route_returns_index_html(dist):
    response = client.get("/projects/some-id")
    assert response.status_code == 200
    assert "DAP UI" in response.text


def test_api_and_docs_are_not_caught_by_the_fallback(dist):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    unknown = client.get("/api/v1/no-such-endpoint")
    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Not Found"}


def test_files_outside_dist_are_not_served(dist):
    (dist.parent / "secret.txt").write_text("secret", encoding="utf-8")
    response = client.get("/%2E%2E/secret.txt")
    assert "secret" not in response.text


def test_not_built_page_when_dist_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "missing")
    response = client.get("/")
    assert response.status_code == 200
    assert "Frontend not built" in response.text
    assert client.get("/api/v1/health").status_code == 200
