"""Worker loop (S2-03) against the real master app, with a fake local model.

Owner: Eray. The master runs in-process through FastAPI's TestClient, so the
worker talks to the same endpoints and database a live master would use.
"""

import json
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from dap.master.api import tasks as tasks_api
from dap.master.config import get_settings as master_settings
from dap.master.db import repositories
from dap.master.main import app
from dap.shared.enums import AgentStatus, TaskStatus, TaskType
from dap.shared.schemas import LLMResponse, ProjectCreate, TaskCreate
from dap.worker import executor
from dap.worker.config import WorkerSettings
from dap.worker.main import Worker
from dap.worker.master_client import MasterClient

_TABLES = ("task_results", "events", "tasks", "projects", "agents")

GOOD_ANSWER = json.dumps({
    "summary": "Wrote the health endpoint.",
    "files": [{"path": "backend/main.py", "content": "print('hello')\n"}],
})


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(os.environ["DATABASE_URL"].removeprefix("sqlite:///"))


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Empty tables per test (restored afterwards) and a private workspace."""
    conn = _connect()
    saved = []
    for table in _TABLES:
        cursor = conn.execute(f"SELECT * FROM {table}")
        saved.append((table, [d[0] for d in cursor.description], cursor.fetchall()))
    for table, _, _ in reversed(saved):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path / "workspace")
    try:
        yield tmp_path / "workspace"
    finally:
        conn = _connect()
        for table, _, _ in reversed(saved):
            conn.execute(f"DELETE FROM {table}")
        for table, columns, rows in saved:
            if rows:
                conn.executemany(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({','.join('?' * len(columns))})",
                    rows,
                )
        conn.commit()
        conn.close()


def _worker(agent_id: str = "agent-test") -> Worker:
    settings = WorkerSettings(
        master_url="http://testserver", agent_token=master_settings().agent_token,
        agent_id=agent_id, agent_name="Test-PC", agent_owner="Tester",
        role_hint=TaskType.BACKEND, model="fake-model", provider="ollama",
        cap_coding=80, cap_reasoning=60, cap_context=40,
        heartbeat_interval_sec=10, poll_interval_sec=1,
    )
    # raise_server_exceptions=False: a master error is a 500 answer, as on a live master.
    client = MasterClient(settings.api_url, settings.agent_token,
                          http=TestClient(app, raise_server_exceptions=False))
    return Worker(settings, client)


def _seed_task(task_id: str = "t-1") -> str:
    project = repositories.create_project(ProjectCreate(
        name="Library", requirement_text="An online library where members borrow books.",
    ))
    repositories.create_tasks(project.id, [TaskCreate(
        id=task_id, title="Build the API", description="One FastAPI file.",
        type=TaskType.BACKEND, depends_on=[],
    )])
    return project.id


def _fake_chat(answers: list[str], calls: list | None = None):
    def chat(messages, *, json_mode=False, **_):
        if calls is not None:
            calls.append(messages)
        return LLMResponse(text=answers.pop(0), prompt_tokens=10, completion_tokens=20, duration_ms=5)
    return chat


# ------------------------------------------------------------------ end to end


def test_worker_completes_a_task_end_to_end(monkeypatch, _isolated):
    calls = []
    monkeypatch.setattr(executor, "chat", _fake_chat([GOOD_ANSWER], calls))
    project_id = _seed_task()
    worker = _worker()
    worker.register()

    task = worker.poll_once()

    assert task.status == TaskStatus.COMPLETED
    assert task.assigned_agent_id == "agent-test"
    files = list(_isolated.glob(f"{project_id}/*/backend/main.py"))
    assert len(files) == 1 and files[0].read_text() == "print('hello')\n"
    # The prompt carries the task and the project's requirement text.
    prompt = calls[0][1]["content"]
    assert "Build the API" in prompt and "online library" in prompt
    # Back to idle after the task.
    assert repositories.get_agent("agent-test").status == AgentStatus.IDLE


def test_nothing_to_do_returns_none(monkeypatch):
    worker = _worker()
    worker.register()
    assert worker.poll_once() is None


def test_failed_task_goes_back_to_the_queue(monkeypatch):
    monkeypatch.setattr(executor, "chat", _fake_chat(["not json", "still not json"]))
    _seed_task()
    worker = _worker()
    worker.register()

    task = worker.poll_once()

    assert task.status == TaskStatus.PENDING  # master retries it (contract section 6)
    assert task.attempt == 1


def test_registers_again_when_the_master_forgets_the_agent():
    worker = _worker("agent-new")
    assert repositories.get_agent("agent-new") is None
    worker.heartbeat_once()  # 404 -> register
    assert repositories.get_agent("agent-new") is not None


def test_poll_registers_again_on_404():
    worker = _worker("agent-late")
    assert worker.poll_once() is None
    assert repositories.get_agent("agent-late") is not None


def test_shutdown_reports_offline():
    worker = _worker()
    worker.register()
    worker.shutdown()
    assert repositories.get_agent("agent-test").status == AgentStatus.OFFLINE
    assert worker.stop.is_set()


# ------------------------------------------------------------------ executor


def test_answer_is_asked_again_once(monkeypatch):
    monkeypatch.setattr(executor, "chat", _fake_chat(["oops", GOOD_ANSWER]))
    _seed_task("t-x")
    result = executor.execute_task(repositories.get_task("t-x"), "agent-test")
    assert result.success and result.tokens_used == 60  # both answers counted


def test_model_down_gives_a_failed_result(monkeypatch):
    def down(*_, **__):
        raise RuntimeError("LLM at http://localhost:11434/v1 did not answer")
    monkeypatch.setattr(executor, "chat", down)
    _seed_task("t-y")
    result = executor.execute_task(repositories.get_task("t-y"), "agent-test")
    assert not result.success and "11434" in result.error


def test_parse_answer_accepts_wrapped_json_and_drops_bad_paths():
    text = "Here you go:\n" + json.dumps({"summary": "ok", "files": [
        {"path": "./app/main.py", "content": "a"},
        {"path": "../escape.py", "content": "b"},
        {"path": "/etc/passwd", "content": "c"},
        {"path": "APP/MAIN.PY", "content": "duplicate"},
        {"path": "notes.md"},
    ]})
    summary, files = executor.parse_answer(text)
    assert summary == "ok"
    assert [f.path for f in files] == ["app/main.py"]


def test_parse_answer_rejects_no_files():
    with pytest.raises(executor.UnusableAnswer):
        executor.parse_answer('{"summary": "nothing", "files": []}')
    with pytest.raises(executor.UnusableAnswer):
        executor.parse_answer("no json here")


def test_files_go_under_the_task_type_folder():
    text = json.dumps({"summary": "ok", "files": [
        {"path": "main.py", "content": "a"}, {"path": "backend/app.py", "content": "b"},
    ]})
    _, files = executor.parse_answer(text, "backend")
    assert [f.path for f in files] == ["backend/main.py", "backend/app.py"]


def test_clashing_files_turn_into_a_failure_and_a_requeue(monkeypatch):
    answers = [
        json.dumps({"summary": "one", "files": [{"path": "notes.md", "content": "first"}]}),
        json.dumps({"summary": "two", "files": [{"path": "notes.md", "content": "second"}]}),
    ]
    monkeypatch.setattr(executor, "chat", _fake_chat(answers))
    project = repositories.create_project(ProjectCreate(
        name="Clash", requirement_text="Two backend tasks that write the same file.",
    ))
    repositories.create_tasks(project.id, [
        TaskCreate(id=f"t-{n}", title=f"Task {n}", description="write notes",
                   type=TaskType.BACKEND, depends_on=[])
        for n in (1, 2)
    ])
    worker = _worker()
    worker.register()

    first = worker.poll_once()
    second = worker.poll_once()

    assert first.status == TaskStatus.COMPLETED
    assert second.status == TaskStatus.PENDING and second.attempt == 1  # requeued, not stuck
