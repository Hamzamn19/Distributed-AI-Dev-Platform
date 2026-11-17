"""The template filled with the mock outputs (LLM_MOCK=1) is an application that starts."""

import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx
import pytest

from dap.master.core import integrator
from dap.shared.enums import TaskStatus, TaskType
from dap.shared.schemas import GeneratedFile, Task
from dap.worker.executor import MOCK_FILES

TEMPLATE_FILES = [
    ".gitignore", "README.md", "backend/database.py", "backend/db.py", "backend/main.py",
    "frontend/index.html", "frontend/lib.js", "frontend/style.css",
    "requirements.txt", "tests/test_app.py",
]


def _task(kind: TaskType) -> Task:
    now = datetime.now(timezone.utc)
    return Task(id=kind.value, project_id="p", title=f"{kind.value} task", description="",
                type=kind, status=TaskStatus.IN_PROGRESS, created_at=now, updated_at=now)


@pytest.fixture
def app_folder(tmp_path, monkeypatch):
    """A project folder built like a run: template, then one commit per task."""
    monkeypatch.setattr(integrator, "WORKSPACE_ROOT", tmp_path / "workspace")
    for kind, paths in integrator.TEMPLATE_FILES.items():
        files = [GeneratedFile(path=p, content=MOCK_FILES[p]) for p in paths]
        integrator.commit_task("generated", _task(kind), f"agent-{kind.value}", files)
    return integrator.project_dir("generated")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_every_template_file_is_in_the_project_with_one_commit_per_task(app_folder):
    assert integrator.list_files("generated") == TEMPLATE_FILES
    log = subprocess.run(["git", "log", "--format=%s"], cwd=app_folder,
                         capture_output=True, text=True).stdout.splitlines()
    assert len(log) == 4
    assert log[-1] == "database: database task (by agent-database)"


def test_template_tells_each_agent_what_to_write():
    for path in TEMPLATE_FILES:
        text = (integrator.TEMPLATE_DIR / path).read_text(encoding="utf-8")
        assert text.strip(), path
    assert "Filled by: the DATABASE task" in (integrator.TEMPLATE_DIR / "backend/database.py").read_text("utf-8")
    assert "LAST line" in (integrator.TEMPLATE_DIR / "backend/main.py").read_text("utf-8")


def test_the_generated_app_starts_and_answers(app_folder):
    port = _free_port()
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port)],
        cwd=app_folder, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                if httpx.get(f"{base}/api/items", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if server.poll() is not None:
                pytest.fail(f"the app stopped: {server.stderr.read().decode(errors='replace')}")
            time.sleep(0.1)
        created = httpx.post(f"{base}/api/items", json={"name": "Dune"})
        assert created.status_code == 201
        assert {"id": created.json()["id"], "name": "Dune"} in httpx.get(f"{base}/api/items").json()
        page = httpx.get(f"{base}/")
        assert page.status_code == 200 and "<h1>Items</h1>" in page.text
    finally:
        server.terminate()
        server.wait(10)


def test_the_generated_tests_pass(app_folder):
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                            cwd=app_folder, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
