"""Follow-up requests on a finished application (Sprint 4): the endpoint, the
revision task it creates, the run that applies the change, and the worker prompt."""

import subprocess
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from dap.master.a2a_client import A2AError
from dap.master.core import acceptance, integrator, orchestrator
from dap.master.core import followup as followup_module
from dap.master.db import database, repositories, results
from dap.master.main import app
from dap.shared.enums import A2ATaskState, ProjectStatus, TaskStatus, TaskType
from dap.shared.schemas import (
    A2ATask,
    AgentRegister,
    Artifact,
    Capabilities,
    DapTaskOutput,
    DapTaskPayload,
    GeneratedFile,
    Message,
    Part,
    ProjectCreate,
    TaskCreate,
    TaskStatusA2A,
)
from dap.worker import prompts

REAL_CHECK = acceptance.check
STARTED = {"started": True, "error": None, "summary": "1 of 1 checks passed", "passed": 1,
           "failed": 0, "rules": 0, "checks": []}
APP_FILES = ["backend/database.py", "backend/main.py", "frontend/index.html", "tests/test_app.py"]
CHANGE = "Add a due date to every task and sort the list by it."


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh database and workspace for each test; the acceptance check always passes."""
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


def agent(agent_id: str):
    return repositories.upsert_agent(AgentRegister(
        agent_id=agent_id, name=agent_id, owner="t", role_hint=None, model="m",
        capabilities=Capabilities(coding=60, reasoning=60, context=60),
        a2a_url=f"http://{agent_id}:9000",
    ))


def make_project() -> str:
    created = repositories.create_project(ProjectCreate(
        name="Library", requirement_text="A library where members borrow books."))
    ids = {kind: str(uuid4()) for kind in ("db", "api", "ui", "test")}
    repositories.create_tasks(created.id, [
        TaskCreate(id=ids["db"], title="database task", description="d", type=TaskType.DATABASE),
        TaskCreate(id=ids["api"], title="backend task", description="d", type=TaskType.BACKEND,
                   depends_on=[ids["db"]]),
        TaskCreate(id=ids["ui"], title="frontend task", description="d", type=TaskType.FRONTEND,
                   depends_on=[ids["api"]]),
        TaskCreate(id=ids["test"], title="testing task", description="d", type=TaskType.TESTING,
                   depends_on=[ids["api"], ids["ui"]]),
    ])
    return created.id


class FakeA2A:
    """Like the workers: every task completed after one status request."""

    def __init__(self):
        self.sent = []

    def send_task(self, url, payload, token):
        remote_id = f"remote-{len(self.sent)}"
        self.sent.append((url, payload))
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.SUBMITTED))

    def get_task(self, url, remote_id, token):
        payload = self.sent[int(remote_id.split("-")[1])][1]
        output = DapTaskOutput(summary=f"{payload.type.value} done", files=[
            GeneratedFile(path=p, content=f"{payload.type.value} by {url}\n")
            for p in payload.target_files], prompt_tokens=5, completion_tokens=7, duration_ms=9)
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.COMPLETED),
                       artifacts=[Artifact(artifact_id="a", name="result",
                                           parts=[Part(data=output.model_dump(mode="json"))])])


def fake_worker(monkeypatch, fake):
    """The endpoint's run uses the real a2a_client module; point it at the fake."""
    monkeypatch.setattr("dap.master.a2a_client.send_task", fake.send_task)
    monkeypatch.setattr("dap.master.a2a_client.get_task", fake.get_task)


def finish_project(pid: str) -> None:
    agent("a1"), agent("a2")
    assert orchestrator.run_project(pid, client=FakeA2A(), poll_interval=0) \
        == ProjectStatus.COMPLETED


def git_log(pid):
    folder = integrator.project_dir(pid)
    return subprocess.run(["git", "log", "--format=%s"], cwd=folder, capture_output=True,
                          text=True).stdout.splitlines()


# ------------------------------------------------------------------- the endpoint


def test_a_followup_creates_a_revision_task_over_every_finished_task(db, monkeypatch):
    pid = make_project()
    finish_project(pid)
    fake = FakeA2A()
    fake_worker(monkeypatch, fake)
    client = TestClient(app)

    answer = client.post(f"/api/v1/projects/{pid}/followup",
                         json={"instruction": CHANGE})
    assert answer.status_code == 202
    tasks = repositories.list_tasks(pid)
    assert [t.type.value for t in tasks] == ["database", "backend", "frontend", "testing",
                                             "revision"]
    revision = tasks[-1]
    assert revision.title == "Follow-up: Add a due date to every task and sort the list by it."
    assert CHANGE in revision.description
    assert revision.depends_on == [t.id for t in tasks[:4]]
    assert revision.status == TaskStatus.PENDING

    # The run the endpoint started applies the change and completes the project again.
    _wait(pid, fake)
    assert repositories.get_project(pid).status == ProjectStatus.COMPLETED
    assert [p.type.value for _, p in fake.sent] == ["revision"]
    assert [t.status for t in repositories.list_tasks(pid)] == [TaskStatus.COMPLETED] * 5
    assert f"revision: Follow-up: {CHANGE} (by a1)" in git_log(pid)
    events = [e for e in _events(pid) if e[0] == "followup"]
    assert events and events[0][1] == CHANGE


def _events(pid):
    with results.SessionLocal() as session:
        return [(e.type, e.message) for e in session.query(results.EventModel)
                .filter_by(project_id=pid).all() if e.type == "followup"]


def test_a_followup_is_refused_without_a_completed_application(db, monkeypatch):
    client = TestClient(app)
    body = {"instruction": CHANGE}
    assert client.post("/api/v1/projects/nope/followup", json=body).status_code == 404

    pid = make_project()  # created, no tasks yet
    assert client.post(f"/api/v1/projects/{pid}/followup", json=body).status_code == 409

    repositories.set_project_status(pid, ProjectStatus.FAILED)  # a failed application
    assert client.post(f"/api/v1/projects/{pid}/followup", json=body).status_code == 409

    finish_project(pid)
    monkeypatch.setattr(orchestrator, "is_running", lambda _pid: True)  # a run is going
    assert client.post(f"/api/v1/projects/{pid}/followup", json=body).status_code == 409
    assert len(repositories.list_tasks(pid)) == 4  # nothing was created

    monkeypatch.setattr(orchestrator, "is_running", lambda _pid: False)
    assert client.post(f"/api/v1/projects/{pid}/followup",
                       json={"instruction": "short"}).status_code == 422  # too short


def test_the_revision_run_sends_the_current_files(db, monkeypatch):
    pid = make_project()
    finish_project(pid)
    fake = FakeA2A()
    fake_worker(monkeypatch, fake)
    client = TestClient(app)
    assert client.post(f"/api/v1/projects/{pid}/followup", json={"instruction": CHANGE}) \
        .status_code == 202
    _wait(pid, fake)

    (_url, payload), = fake.sent
    assert payload.type == TaskType.REVISION
    assert payload.target_files == APP_FILES  # every application file may change
    # The worker gets the current files of all finished tasks, newest version last.
    by_path = {f.path: f.content for f in payload.dependency_files}
    assert sorted(by_path) == APP_FILES
    assert by_path["backend/database.py"] == "database by http://a1:9000\n"
    assert by_path["frontend/index.html"].startswith("frontend by http://a")
    assert by_path["tests/test_app.py"].startswith("testing by http://a")


def _wait(pid, fake=None):
    """Wait for the follow-up run to end; `fake` is set once the revision was sent."""
    for _ in range(200):
        status = repositories.get_project(pid).status
        sent = fake is None or len(fake.sent) > 0
        if status in (ProjectStatus.COMPLETED, ProjectStatus.FAILED) and sent:
            return
        threading.Event().wait(0.05)
    pytest.fail("the follow-up run did not finish")


def test_a_failed_revision_can_be_run_again(db):
    pid = make_project()
    finish_project(pid)
    followup_module.create_followup(pid, CHANGE)
    broken = FakeA2A()
    broken.get_task = lambda url, remote_id, token: A2ATask(  # the model gives up
        id=remote_id, status=TaskStatusA2A(
            state=A2ATaskState.FAILED,
            message=Message(message_id="m", role="ROLE_AGENT", parts=[Part(text="model broke")])))
    assert orchestrator.run_project(pid, client=broken, poll_interval=0) == ProjectStatus.FAILED
    assert [t.status for t in repositories.list_tasks(pid)][-1] == TaskStatus.FAILED

    again = FakeA2A()
    assert orchestrator.run_project(pid, client=again, poll_interval=0) == ProjectStatus.COMPLETED
    assert [p.type.value for _, p in again.sent] == ["revision"]
    tries = repositories.list_tasks(pid)[-1]
    assert tries.attempt == 2
    assert [t.status for t in repositories.list_tasks(pid)] == [TaskStatus.COMPLETED] * 5


# ------------------------------------------------------------------- the worker side


def test_the_revision_prompt_uses_the_current_files_not_the_template(tmp_path, monkeypatch):
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "main.py").write_text("# the template\n")
    monkeypatch.setattr(prompts, "TEMPLATE_DIR", tmp_path)

    revision = DapTaskPayload(
        task_id="t", project_id="p", type=TaskType.REVISION, title="Follow-up: add sorting",
        description=f"Follow-up request from the user, over the finished application: {CHANGE}",
        requirement_text="A library where members borrow books.", target_files=APP_FILES,
        dependency_files=[GeneratedFile(path="backend/main.py", content="# the real app\n")])
    system, user = (m["content"] for m in prompts.build_messages(revision))
    assert "follow-up request" in system.lower()
    assert "keep the rest exactly as it is" in system
    assert "Template of" not in user  # no template: start from the real files
    assert "# the real app" in user
    assert CHANGE in user

    normal = revision.model_copy(update={"type": TaskType.BACKEND, "title": "backend task",
                                         "description": "d"})
    system, user = (m["content"] for m in prompts.build_messages(normal))
    assert "Template of backend/main.py" in user  # a build task still starts from it
