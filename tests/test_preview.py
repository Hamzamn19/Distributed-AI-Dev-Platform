"""Open the app: the master runs a generated application (dap/master/core/preview.py)."""

import shutil
import socket

import httpx
import pytest
from fastapi.testclient import TestClient

from dap.master.core import integrator, preview
from dap.master.main import app
from dap.worker.executor import MOCK_FILES


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(integrator, "WORKSPACE_ROOT", tmp_path / "workspace")

    def make(project_id: str, **files) -> None:
        folder = integrator.project_dir(project_id)
        shutil.copytree(integrator.TEMPLATE_DIR, folder)
        for path, content in {**MOCK_FILES, **files}.items():
            (folder / path).write_text(content, encoding="utf-8")

    yield make
    preview.stop()


def test_the_app_runs_and_a_second_one_takes_its_place(workspace):
    workspace("first")
    workspace("second")
    port = free_port()
    assert preview.start("first", port) == port
    assert preview.running() == "first"
    assert httpx.get(f"http://127.0.0.1:{port}/").status_code == 200
    assert httpx.get(f"http://127.0.0.1:{port}/api/items").status_code == 200
    assert preview.start("second", port) == port
    assert preview.running() == "second"
    assert httpx.get(f"http://127.0.0.1:{port}/api/stats").status_code == 200
    preview.stop()
    assert preview.running() is None


def test_an_app_that_does_not_start_says_why(workspace):
    workspace("broken", **{"backend/main.py": "from backend import nothing_here\n"})
    with pytest.raises(preview.PreviewError, match="ImportError"):
        preview.start("broken", free_port())
    assert preview.running() is None


def test_a_project_without_backend_has_nothing_to_open(workspace):
    integrator.project_dir("empty").mkdir(parents=True)
    with pytest.raises(FileNotFoundError):
        preview.start("empty", free_port())


def test_the_endpoint_answers_with_the_port(monkeypatch):
    client = TestClient(app)
    pid = client.post("/api/v1/projects", json={
        "name": "Preview", "requirement_text": "A small app with items to list and add."}).json()["id"]
    monkeypatch.setattr(preview, "start", lambda project_id: 8100)
    assert client.post(f"/api/v1/projects/{pid}/preview").json() == {"project_id": pid, "port": 8100}

    def missing(project_id):
        raise FileNotFoundError("the project has no backend/main.py yet")

    monkeypatch.setattr(preview, "start", missing)
    answer = client.post(f"/api/v1/projects/{pid}/preview")
    assert answer.status_code == 409
    assert "backend/main.py" in answer.json()["detail"]
    assert client.post("/api/v1/projects/no-such-project/preview").status_code == 404
