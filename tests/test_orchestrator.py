"""Orchestrator, integrator and the run/results/files endpoints, with a fake A2A client."""

import subprocess
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from dap.master.a2a_client import A2AError
from dap.master.core import acceptance, integrator, orchestrator
from dap.master.db import database, repositories, results
from dap.master.main import app
from dap.shared.enums import A2ATaskState, AgentStatus, ProjectStatus, TaskStatus, TaskType
from dap.shared.schemas import (
    A2ATask,
    AgentRegister,
    Artifact,
    Capabilities,
    DapTaskOutput,
    GeneratedFile,
    Message,
    Part,
    ProjectCreate,
    TaskCreate,
    TaskStatusA2A,
)

REAL_CHECK = acceptance.check
STARTED = {"started": True, "error": None, "summary": "1 of 1 checks passed", "passed": 1,
           "failed": 0, "rules": 0, "checks": []}


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh database and workspace for each test; the acceptance check always passes
    (the fake files are no application), except where a test puts the real one back."""
    engine = create_engine(f"sqlite:///{(tmp_path / 'run.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(repositories, "SessionLocal", sessions)
    monkeypatch.setattr(results, "SessionLocal", sessions)
    monkeypatch.setattr(integrator, "WORKSPACE_ROOT", tmp_path / "workspace")
    monkeypatch.setattr(integrator, "TEMPLATE_DIR", tmp_path / "no-template")
    monkeypatch.setattr(acceptance, "check", lambda pid, records=(): dict(STARTED))
    yield
    engine.dispose()


def agent(agent_id: str, role: TaskType | None = None, url: str | None = "auto"):
    return repositories.upsert_agent(AgentRegister(
        agent_id=agent_id, name=agent_id, owner="t", role_hint=role, model="m",
        capabilities=Capabilities(coding=60, reasoning=60, context=60),
        a2a_url=f"http://{agent_id}:9000" if url == "auto" else url,
    ))


def project(*specs):
    """specs: (key, type, [dependency keys], agent_id). Returns (project_id, {key: task_id})."""
    created = repositories.create_project(ProjectCreate(
        name="Library", requirement_text="A library where members borrow books."))
    ids = {key: str(uuid4()) for key, *_ in specs}
    repositories.create_tasks(created.id, [
        TaskCreate(id=ids[key], title=f"{kind.value} task", description="d", type=kind,
                   depends_on=[ids[d] for d in deps])
        for key, kind, deps, _ in specs])
    for key, _, _, agent_id in specs:
        if agent_id:
            repositories.assign_task(ids[key], agent_id, "test")
    return created.id, ids


APP = [("db", TaskType.DATABASE, [], "a1"), ("api", TaskType.BACKEND, ["db"], "a2"),
       ("ui", TaskType.FRONTEND, ["api"], "a1"), ("test", TaskType.TESTING, ["api", "ui"], "a2")]


class FakeA2A:
    """Answers like workers: each task is completed after `polls` status requests."""

    def __init__(self, polls=1, fail=(), never=(), unreachable=()):
        self.polls, self.fail, self.never, self.unreachable = polls, fail, never, unreachable
        self.tasks: dict[str, list] = {}
        self.events: list[tuple[str, str]] = []
        self.sent = []

    def send_task(self, url, payload, token):
        remote_id = f"remote-{len(self.sent)}"
        self.sent.append((url, payload))
        self.tasks[remote_id] = [payload, 0]
        self.events.append(("send", payload.type.value))
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.SUBMITTED))

    def get_task(self, url, remote_id, token):
        payload, asked = self.tasks[remote_id]
        self.tasks[remote_id][1] += 1
        if payload.type.value in self.unreachable:
            raise A2AError("worker not reachable")
        if payload.type.value in self.never or asked + 1 < self.polls:
            return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.WORKING))
        self.events.append(("done", payload.type.value))
        if payload.type.value in self.fail:
            return A2ATask(id=remote_id, status=TaskStatusA2A(
                state=A2ATaskState.FAILED,
                message=Message(message_id="m", role="ROLE_AGENT", parts=[Part(text="model broke")])))
        output = DapTaskOutput(summary=f"{payload.type.value} done", files=[
            GeneratedFile(path=p, content=f"{payload.type.value} by {url}\n")
            for p in payload.target_files], prompt_tokens=5, completion_tokens=7, duration_ms=9)
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.COMPLETED),
                       artifacts=[Artifact(artifact_id="a", name="result",
                                           parts=[Part(data=output.model_dump(mode="json"))])])


def statuses(pid):
    return {t.type.value: t.status for t in repositories.list_tasks(pid)}


def git_log(pid):
    folder = integrator.project_dir(pid)
    return subprocess.run(["git", "log", "--format=%s"], cwd=folder, capture_output=True,
                          text=True).stdout.splitlines()


def test_dependencies_decide_the_order_and_files_are_passed_on(db):
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    fake = FakeA2A()
    assert orchestrator.run_project(pid, client=fake, poll_interval=0) == ProjectStatus.COMPLETED
    assert [p.type.value for _, p in fake.sent] == ["database", "backend", "frontend", "testing"]
    backend = fake.sent[1][1]
    assert [f.path for f in backend.dependency_files] == ["backend/database.py"]
    assert backend.target_files == ["backend/main.py"]
    assert "library" in backend.requirement_text
    assert set(statuses(pid).values()) == {TaskStatus.COMPLETED}
    assert repositories.get_project(pid).status == ProjectStatus.COMPLETED
    assert len(results.list_project_results(pid)) == 4
    page = integrator.read_file(pid, "frontend/index.html")
    assert page.startswith('<!-- Written by a1 (a1, model m) - frontend task "frontend task", ')
    assert page.endswith(" -->\nfrontend by http://a1:9000\n")
    log = git_log(pid)
    assert len(log) == 4
    assert log[-1] == "database: database task (by a1)"
    assert all(t.attempt == 1 for t in repositories.list_tasks(pid))


def test_an_application_that_does_not_start_fails_the_project(db, monkeypatch):
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    monkeypatch.setattr(acceptance, "check", REAL_CHECK)  # the fake files cannot start
    assert orchestrator.run_project(pid, client=FakeA2A(), poll_interval=0) == ProjectStatus.FAILED
    assert set(statuses(pid).values()) == {TaskStatus.COMPLETED}
    report = integrator.read_file(pid, acceptance.ACCEPTANCE_FILE)
    assert '"started": false' in report
    assert git_log(pid)[0] == "master: acceptance check (the application does not start)"


def test_independent_tasks_on_different_agents_run_in_parallel(db):
    agent("a1"), agent("a2")
    pid, _ = project(("db", TaskType.DATABASE, [], "a1"), ("ui", TaskType.FRONTEND, [], "a2"))
    fake = FakeA2A(polls=3)
    orchestrator.run_project(pid, client=fake, poll_interval=0)
    assert fake.events[:2] == [("send", "database"), ("send", "frontend")]


def test_a_second_run_sends_the_failed_tasks_again(db):
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    assert orchestrator.run_project(pid, client=FakeA2A(fail=("database",)), poll_interval=0) \
        == ProjectStatus.FAILED
    again = FakeA2A()
    assert orchestrator.run_project(pid, client=again, poll_interval=0) == ProjectStatus.COMPLETED
    assert [p.type.value for _, p in again.sent] == ["database", "backend", "frontend", "testing"]
    assert set(statuses(pid).values()) == {TaskStatus.COMPLETED}
    tries = {t.type.value: t.attempt for t in repositories.list_tasks(pid)}
    assert tries == {"database": 2, "backend": 1, "frontend": 1, "testing": 1}


def test_a_failed_dependency_fails_the_tasks_after_it(db):
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    fake = FakeA2A(fail=("database",))
    assert orchestrator.run_project(pid, client=fake, poll_interval=0) == ProjectStatus.FAILED
    assert [p.type.value for _, p in fake.sent] == ["database"]
    assert set(statuses(pid).values()) == {TaskStatus.FAILED}
    errors = {r.error for r in results.list_project_results(pid)}
    assert errors == {"model broke", "dependency failed"}


def test_a_task_that_never_finishes_times_out(db):
    agent("a1")
    pid, _ = project(("db", TaskType.DATABASE, [], "a1"))
    orchestrator.run_project(pid, client=FakeA2A(never=("database",)), poll_interval=0,
                             task_timeout=0)
    assert statuses(pid)["database"] == TaskStatus.FAILED
    assert results.list_project_results(pid)[0].error.startswith("timeout")


def test_an_unreachable_worker_fails_the_task_after_three_tries(db):
    agent("a1")
    pid, _ = project(("db", TaskType.DATABASE, [], "a1"))
    fake = FakeA2A(unreachable=("database",))
    orchestrator.run_project(pid, client=fake, poll_interval=0)
    assert statuses(pid)["database"] == TaskStatus.FAILED
    assert results.list_project_results(pid)[0].error.startswith("worker unreachable")
    assert fake.tasks["remote-0"][1] == 3


def test_an_offline_agent_is_replaced_by_an_online_one(db):
    agent("gone"), agent("here")
    repositories.touch_heartbeat("gone", AgentStatus.OFFLINE, None)
    pid, ids = project(("db", TaskType.DATABASE, [], "gone"))
    fake = FakeA2A()
    assert orchestrator.run_project(pid, client=fake, poll_interval=0) == ProjectStatus.COMPLETED
    assert fake.sent[0][0] == "http://here:9000"
    task = repositories.get_task(ids["db"])
    assert task.assigned_agent_id == "here"
    assert task.assignment_reason.startswith("reassigned at run")


def test_an_agent_without_a2a_address_is_replaced_and_none_online_fails(db):
    agent("old-inventory", url=None)
    pid, _ = project(("db", TaskType.DATABASE, [], "old-inventory"), ("api", TaskType.BACKEND, [], None))
    assert orchestrator.run_project(pid, client=FakeA2A(), poll_interval=0) == ProjectStatus.FAILED
    assert set(statuses(pid).values()) == {TaskStatus.FAILED}
    assert {r.error for r in results.list_project_results(pid)} == {"no online agent"}


def test_one_agent_can_take_several_tasks(db):
    agent("only")
    pid, _ = project(*[(k, t, d, "only") for k, t, d, _ in APP])
    fake = FakeA2A()
    assert orchestrator.run_project(pid, client=fake, poll_interval=0) == ProjectStatus.COMPLETED
    assert {url for url, _ in fake.sent} == {"http://only:9000"}


def test_start_run_refuses_a_second_run_of_the_same_project(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(orchestrator, "run_project", lambda pid: release.wait(5))
    assert orchestrator.start_run("p-1")
    assert not orchestrator.start_run("p-1")
    release.set()
    for _ in range(100):
        if not orchestrator.is_running("p-1"):
            break
        threading.Event().wait(0.02)
    assert orchestrator.start_run("p-1")
    release.set()


# ------------------------------------------------------------------- integrator


def _task(kind=TaskType.DATABASE):
    from datetime import datetime, timezone

    from dap.shared.schemas import Task

    now = datetime.now(timezone.utc)
    return Task(id="t", project_id="p", title="Schema", description="", type=kind,
                status=TaskStatus.IN_PROGRESS, created_at=now, updated_at=now)


def test_integrator_copies_the_template_writes_files_and_commits(db, tmp_path, monkeypatch):
    template = tmp_path / "template"
    (template / "backend").mkdir(parents=True)
    (template / "README.md").write_text("how to run", encoding="utf-8")
    monkeypatch.setattr(integrator, "TEMPLATE_DIR", template)
    integrator.commit_task("p-1", _task(), "a1", [GeneratedFile(path="backend/database.py",
                                                               content="import sqlite3\n")])
    assert integrator.list_files("p-1") == ["README.md", "backend/database.py"]
    assert git_log("p-1") == ["database: Schema (by a1)"]


def test_integrator_refuses_paths_outside_the_project(db, tmp_path):
    with pytest.raises(ValueError):
        integrator.commit_task("p-1", _task(), "a1", [GeneratedFile(path="../escape.py", content="x")])
    with pytest.raises(ValueError):
        integrator.commit_task("p-1", _task(), "a1", [GeneratedFile(path="C:/x.py", content="x")])
    assert not (tmp_path / "workspace" / "escape.py").exists()
    with pytest.raises(ValueError):
        integrator.read_file("p-1", "../../run.db")


def test_integrator_without_git_still_writes_the_files(db, monkeypatch, caplog):
    monkeypatch.setattr(integrator.shutil, "which", lambda name: None)
    integrator.commit_task("p-2", _task(), "a1", [GeneratedFile(path="backend/database.py",
                                                               content="x")])
    assert integrator.read_file("p-2", "backend/database.py").endswith(" UTC\nx")
    assert not (integrator.project_dir("p-2") / ".git").exists()
    assert "git is not installed" in caplog.text


# -------------------------------------------------------------------- endpoints


def test_run_results_and_files_endpoints(db, monkeypatch):
    client = TestClient(app)
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    started = []
    monkeypatch.setattr(orchestrator, "start_run", lambda p: not started.append(p) and len(started) == 1)

    answer = client.post(f"/api/v1/projects/{pid}/run")
    assert answer.status_code == 202
    assert answer.json()["id"] == pid
    assert client.post(f"/api/v1/projects/{pid}/run").status_code == 409

    orchestrator.run_project(pid, client=FakeA2A(), poll_interval=0)
    listed = client.get(f"/api/v1/projects/{pid}/results").json()
    assert len(listed) == 4 and all(r["success"] for r in listed)
    files = client.get(f"/api/v1/projects/{pid}/files").json()
    assert "backend/main.py" in files and not any(f.startswith(".git") for f in files)
    content = client.get(f"/api/v1/projects/{pid}/files/backend/main.py")
    assert content.status_code == 200
    assert content.text.startswith("# Written by a2 (a2, model m) - backend task")
    assert content.text.endswith("\nbackend by http://a2:9000\n")
    assert client.get(f"/api/v1/projects/{pid}/files/..%2F..%2Frun.db").status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/files/.git/config").status_code == 404
    assert client.get(f"/api/v1/projects/{pid}/files/missing.py").status_code == 404


def test_run_without_tasks_gives_409(db):
    client = TestClient(app)
    created = repositories.create_project(ProjectCreate(
        name="Empty", requirement_text="A library where members borrow books."))
    assert client.post(f"/api/v1/projects/{created.id}/run").status_code == 409
    assert client.post("/api/v1/projects/unknown/run").status_code == 404


def test_a_task_gets_the_files_of_every_earlier_task_in_its_chain(db):
    agent("a1"), agent("a2")
    pid, _ = project(*APP)
    fake = FakeA2A()
    orchestrator.run_project(pid, client=fake, poll_interval=0)
    testing = [p for _, p in fake.sent if p.type.value == "testing"][0]
    assert sorted(f.path for f in testing.dependency_files) == [
        "backend/database.py", "backend/main.py", "frontend/index.html"]
