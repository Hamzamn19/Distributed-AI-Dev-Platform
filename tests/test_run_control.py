"""Sprint 4 run control: the export zip, the contextId round trip, A2A CancelTask,
the in-run retry on a different agent, and the run queue."""

import subprocess
import threading
import zipfile
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import dap.master.a2a_client as a2a_client
from dap.master.core import acceptance, integrator, orchestrator
from dap.master.db import database, repositories, results
from dap.master.main import app
from dap.shared.enums import (
    A2ATaskState,
    AgentStatus,
    ProjectStatus,
    TaskStatus,
    TaskType,
)
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
from dap.worker.executor import Executor, live_progress
import dap.worker.executor as executor_module
from dap.master.core import followup as followup_module

CHANGE = "Add a due date to every task and sort the list by it."

REAL_CHECK = acceptance.check
STARTED = {"started": True, "error": None, "summary": "1 of 1 checks passed", "passed": 1,
           "failed": 0, "rules": 0, "checks": []}


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh database and workspace; the acceptance check always passes."""
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
    monkeypatch.setenv("AGENT_TOKEN", "t")
    monkeypatch.setenv("LLM_MOCK", "0")  # no .env of the machine (a real .env sets LLM_MOCK=1)
    yield
    engine.dispose()


def agent(agent_id: str, status: AgentStatus = AgentStatus.IDLE):
    registered = repositories.upsert_agent(AgentRegister(
        agent_id=agent_id, name=agent_id, owner="t", role_hint=None, model="m",
        capabilities=Capabilities(coding=60, reasoning=60, context=60),
        a2a_url=f"http://{agent_id}:9000",
    ))
    repositories.touch_heartbeat(agent_id, status, None)
    return registered


def make_project(assign: bool = True) -> str:
    created = repositories.create_project(ProjectCreate(
        name="My Library!", requirement_text="A library where members borrow books."))
    ids = {kind: str(uuid4()) for kind in ("db", "api", "ui", "test")}
    repositories.create_tasks(created.id, [
        TaskCreate(id=ids[kind], title=f"{kind} task", description="d", type=kind_)
        for kind, kind_ in (("db", TaskType.DATABASE), ("api", TaskType.BACKEND),
                            ("ui", TaskType.FRONTEND), ("test", TaskType.TESTING))])
    if assign:
        agent("a1"), agent("a2")
        repositories.assign_task(ids["db"], "a1", "test")
        repositories.assign_task(ids["api"], "a2", "test")
        repositories.assign_task(ids["ui"], "a1", "test")
        repositories.assign_task(ids["test"], "a2", "test")
    return created.id


class FakeA2A:
    """Answers like workers; `fail_sends` fails the first N sends of one type."""

    def __init__(self, polls=1, fail_sends=()):
        self.polls, self.fail_sends = polls, dict(fail_sends)
        self.tasks: dict[str, list] = {}
        self.sent: list[tuple[str, object]] = []
        self.remote_ids: list[str] = []
        self.cancelled: list[str] = []

    def send_task(self, url, payload, token):
        remote_id = f"remote-{len(self.sent)}"
        self.sent.append((url, payload))
        self.remote_ids.append(remote_id)
        self.tasks[remote_id] = [payload, 0]
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.SUBMITTED))

    def get_task(self, url, remote_id, token):
        payload, asked = self.tasks[remote_id]
        self.tasks[remote_id][1] += 1
        fail_n = self.fail_sends.get(payload.type.value)
        if fail_n is not None and asked >= fail_n[0] and fail_n[1] > 0:
            self.fail_sends[payload.type.value] = (fail_n[0], fail_n[1] - 1)
            return A2ATask(id=remote_id, status=TaskStatusA2A(
                state=A2ATaskState.FAILED,
                message=Message(message_id="m", role="ROLE_AGENT", parts=[Part(text="boom")])))
        if asked + 1 < self.polls:
            return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.WORKING))
        output = DapTaskOutput(summary=f"{payload.type.value} done", files=[
            GeneratedFile(path=p, content=f"{payload.type.value} by {url}\n")
            for p in payload.target_files], prompt_tokens=5, completion_tokens=7, duration_ms=9)
        return A2ATask(id=remote_id, status=TaskStatusA2A(state=A2ATaskState.COMPLETED),
                       artifacts=[Artifact(artifact_id="a", name="result",
                                           parts=[Part(data=output.model_dump(mode="json"))])])

    def cancel_task(self, url, remote_id, token):
        self.cancelled.append(remote_id)


def run_to_completion(pid: str, fake=None) -> None:
    agent("a1"), agent("a2")
    assert orchestrator.run_project(pid, client=fake or FakeA2A(), poll_interval=0) \
        == ProjectStatus.COMPLETED


def git_log(pid):
    folder = integrator.project_dir(pid)
    return subprocess.run(["git", "log", "--format=%s"], cwd=folder, capture_output=True,
                          text=True).stdout.splitlines()


# ------------------------------------------------------------------- (6) export zip


def test_export_zips_the_generated_application_without_the_runtime(db):
    pid = make_project()
    run_to_completion(pid)
    client = TestClient(app)
    answer = client.get(f"/api/v1/projects/{pid}/export")
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "application/zip"
    assert 'filename="My_Library.zip"' in answer.headers["content-disposition"]
    names = zipfile.ZipFile(BytesIO(answer.content)).namelist()
    assert "backend/main.py" in names and "frontend/index.html" in names
    assert not any(".git" in n or n.endswith("app.db") for n in names)


def test_export_needs_files(db):
    client = TestClient(app)
    pid = make_project()
    assert client.get(f"/api/v1/projects/{pid}/export").status_code == 409
    assert client.get("/api/v1/projects/nope/export").status_code == 404


# ------------------------------------------------------------------- (3) contextId


def test_the_context_id_is_the_project_id_on_the_whole_round_trip(db, monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, timeout=None, **kwargs):
        captured["body"] = kwargs["json"]

        class Answer:
            status_code = 200
            text = ""

            def json(self):
                return {"task": {"id": "remote-1",
                                 "status": {"state": "TASK_STATE_WORKING"}}}

        return Answer()

    monkeypatch.setattr(a2a_client.httpx, "request", fake_request)
    payload = DapTaskPayload(
        task_id="t1", project_id="proj-1", type=TaskType.DATABASE, title="database",
        description="d", requirement_text="r", target_files=["backend/database.py"])
    a2a_client.send_task("http://a1:9000", payload, "t")
    assert captured["body"]["message"]["contextId"] == "proj-1"

    # The worker stores the context and answers it with the task (contract section 13).
    executor = Executor(run=lambda p: DapTaskOutput(summary="s"))
    stored = executor.submit(payload, "proj-1")
    for _ in range(100):
        task = executor.get(stored.id)
        if task.status.state in (A2ATaskState.COMPLETED, A2ATaskState.FAILED):
            break
        threading.Event().wait(0.05)
    assert executor.get(stored.id).context_id == "proj-1"


# ------------------------------------------------------------------- (2) CancelTask


def test_the_worker_cancels_a_running_task(db):
    gate = threading.Event()
    started = threading.Event()

    def slow_run(payload):
        started.set()
        gate.wait(5)  # the model is working; the master cancels in the meantime
        return DapTaskOutput(summary="s", files=[GeneratedFile(path="backend/database.py",
                                                              content="x")])

    executor = Executor(run=slow_run)
    payload = DapTaskPayload(
        task_id="t1", project_id="p", type=TaskType.DATABASE, title="database",
        description="d", requirement_text="r", target_files=["backend/database.py"])
    remote = executor.submit(payload, "p")
    assert started.wait(2)
    assert executor.cancel(remote.id) is True
    assert executor.cancel(remote.id) is True  # still open; the second call changes nothing
    gate.set()
    for _ in range(100):
        task = executor.get(remote.id)
        if task.status.state == A2ATaskState.CANCELED:
            break
        threading.Event().wait(0.05)
    else:
        pytest.fail("the task never became TASK_STATE_CANCELED")
    assert task.artifacts == []  # the answer of the cancelled work is thrown away
    assert "cancelled by the user" in task.status.message.parts[0].text


def test_the_worker_cancels_a_queued_task_before_it_starts(db):
    ran = threading.Event()
    gate = threading.Event()

    def first_blocks(payload):
        if payload.task_id == "t1":
            gate.wait(5)
        else:
            ran.set()
        return DapTaskOutput(summary="s")

    executor = Executor(run=first_blocks)
    payload = DapTaskPayload(
        task_id="t1", project_id="p", type=TaskType.DATABASE, title="database",
        description="d", requirement_text="r", target_files=["backend/database.py"])
    first = executor.submit(payload, "p")
    for _ in range(100):  # wait until the first task is the one running
        if executor.get(first.id).status.state == A2ATaskState.WORKING:
            break
        threading.Event().wait(0.05)
    second = executor.submit(payload.model_copy(update={"task_id": "t2"}), "p")
    assert executor.cancel(second.id) is True
    assert executor.cancel("nope") is False
    gate.set()
    for _ in range(100):
        task = executor.get(second.id)
        if task.status.state == A2ATaskState.CANCELED:
            break
        threading.Event().wait(0.05)
    else:
        pytest.fail("the queued task never became TASK_STATE_CANCELED")
    assert not ran.is_set()  # the cancelled task never started


def test_a_cancelled_run_asks_its_workers_to_stop(db):
    pid = make_project()
    fake = FakeA2A()
    agent("a1"), agent("a2")
    threading.Timer(0.05, orchestrator.cancel, args=(pid,)).start()
    orchestrator.run_project(pid, client=fake, poll_interval=0.02, task_timeout=60)
    assert repositories.get_project(pid).status == ProjectStatus.FAILED
    assert fake.cancelled, "the master must send A2A CancelTask to the workers it sent to"
    assert set(fake.cancelled) <= {remote for remote, _ in
                                   [(f"remote-{i}") for i in range(len(fake.sent))]}


def test_a_cancelled_run_asks_its_workers_to_stop(db):
    pid = make_project()
    fake = FakeA2A(polls=2)  # the first task is still working when Cancel is pressed

    def cancel_on_first_send(url, payload, token):
        orchestrator.cancel(pid)  # the user presses Cancel while the first task runs
        return FakeA2A.send_task(fake, url, payload, token)

    fake.send_task = cancel_on_first_send
    agent("a1"), agent("a2")
    orchestrator._running.add(pid)  # as start_run does, without its thread
    try:
        orchestrator.run_project(pid, client=fake, poll_interval=0.02, task_timeout=60)
    finally:
        orchestrator._running.discard(pid)
    assert repositories.get_project(pid).status == ProjectStatus.FAILED
    assert fake.cancelled, "the master must send A2A CancelTask to the workers it sent to"
    assert set(fake.cancelled) <= set(fake.remote_ids)  # only the tasks it had sent


# ------------------------------------------------------- (8) retry on another agent


def test_a_worker_failure_is_retried_on_a_different_agent_within_the_run(db):
    pid = make_project()
    # The database task fails on a1, then once on the retry agent, then it works.
    fake = FakeA2A(fail_sends={"database": (0, 2)})
    status = orchestrator.run_project(pid, client=fake, poll_interval=0)
    assert status == ProjectStatus.COMPLETED
    tasks = {t.type.value: t for t in repositories.list_tasks(pid)}
    assert tasks["database"].attempt == 3
    assert tasks["database"].assigned_agent_id == "a1"  # third try went back to a1
    reasons = tasks["database"].assignment_reason
    assert "retry after: boom" in reasons
    retry_events = [e for e in _events(pid) if e[0] == "task_retry"]
    assert len(retry_events) == 2
    assert statuses(pid).count(TaskStatus.COMPLETED) == 4


def test_a_failure_with_no_other_agent_is_not_retried(db):
    repositories.upsert_agent(AgentRegister(
        agent_id="only", name="only", owner="t", role_hint=None, model="m",
        capabilities=Capabilities(coding=60, reasoning=60, context=60),
        a2a_url="http://only:9000"))
    pid = make_project(assign=False)
    for task in repositories.list_tasks(pid):
        repositories.assign_task(task.id, "only", "test")
    fake = FakeA2A(fail_sends={"database": (0, 99)})
    status = orchestrator.run_project(pid, client=fake, poll_interval=0)
    assert status == ProjectStatus.FAILED
    tasks = {t.type.value: t for t in repositories.list_tasks(pid)}
    assert tasks["database"].attempt == 1  # no other agent: no retry within the run
    assert [p.type.value for _, p in fake.sent].count("database") == 1


def _events(pid):
    with results.SessionLocal() as session:
        return [(e.type, e.message) for e in session.query(results.EventModel)
                .filter_by(project_id=pid).all()]


def statuses(pid):
    return [t.status for t in repositories.list_tasks(pid)]


# ------------------------------------------------------------------- (10) run queue


def test_a_run_with_only_busy_agents_is_queued_and_starts_when_one_is_free(db, monkeypatch):
    pid = make_project()  # the agents are registered here, then made busy
    agent("a1", AgentStatus.BUSY), agent("a2", AgentStatus.BUSY)
    fake = FakeA2A()
    monkeypatch.setattr("dap.master.a2a_client.send_task", fake.send_task)
    monkeypatch.setattr("dap.master.a2a_client.get_task", fake.get_task)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: _settings(0.05))
    client = TestClient(app)

    answer = client.post(f"/api/v1/projects/{pid}/run")
    assert answer.status_code == 202
    assert orchestrator.is_queued(pid)
    assert orchestrator.queue_position(pid) == 1
    assert repositories.get_project(pid).status == ProjectStatus.CREATED  # waiting

    # a1 becomes free: the watcher starts the queued run, which completes
    repositories.touch_heartbeat("a1", AgentStatus.IDLE, None)
    for _ in range(200):
        if repositories.get_project(pid).status in (ProjectStatus.COMPLETED,
                                                    ProjectStatus.FAILED):
            break
        threading.Event().wait(0.05)
    assert repositories.get_project(pid).status == ProjectStatus.COMPLETED
    assert not orchestrator.is_queued(pid)
    assert [p.type.value for _, p in fake.sent] == ["database", "backend", "frontend",
                                                    "testing"]
    events = [e[0] for e in _events(pid)]
    assert "run_queued" in events and "run_started_from_queue" in events


def test_a_run_without_any_registered_agent_starts_at_once(db):
    pid = make_project()
    client = TestClient(app)
    answer = client.post(f"/api/v1/projects/{pid}/run")
    assert answer.status_code == 202
    assert not orchestrator.is_queued(pid)  # no agents at all: the old behaviour
    assert orchestrator.is_running(pid)
    for _ in range(100):  # the thread must end before the test tears the database down;
        # "could not send" is retried on the other agent, so the run takes some rounds
        if not orchestrator.is_running(pid):
            break
        threading.Event().wait(0.3)
    assert repositories.get_project(pid).status == ProjectStatus.FAILED  # no worker answered


def test_cancel_removes_a_queued_project(db):
    pid = make_project()  # the agents are registered here, then made busy
    agent("a1", AgentStatus.BUSY), agent("a2", AgentStatus.BUSY)
    orchestrator.enqueue_run(pid)
    assert orchestrator.cancel(pid) is True
    assert not orchestrator.is_queued(pid)


def _settings(poll: float):
    from dap.master.config import MasterSettings
    return MasterSettings(agent_token="t", host="h", port=1, database_url="s",
                          cors_origins=[], heartbeat_timeout_sec=30, task_timeout_sec=900,
                          a2a_poll_interval_sec=poll, run_mode="sequential", preview_port=8100)


# -------------------------------------------------------- (streaming) live writing


def test_the_live_report_tracks_the_current_file_and_the_tail():
    executor_module._live_start("t9", "backend")
    report = executor_module._live_report(2, "backend")
    report(30, "intro\n=== FILE: backend/api.py ===\nimport fastapi\n...code code")
    progress = executor_module.live_progress("t9")
    assert progress["current_file"] == "backend/api.py"
    assert progress["generated_tokens"] == 30
    assert progress["tail"].endswith("code")
    report(40, "=== FILE: backend/database.py ===\nCREATE TABLE")
    assert executor_module.live_progress("t9")["current_file"] == "backend/database.py"
    executor_module._live_end()


def test_the_worker_reports_the_writing_progress_of_a_running_task(db, monkeypatch):
    """The on_chunk callback of chat() fills the executor's live view while the task runs."""
    import dap.shared.llm_client as llm
    monkeypatch.setenv("LLM_BASE_URL", "http://fake:1/v1")
    monkeypatch.setenv("LLM_MODEL", "fake")
    seen: list[tuple] = []

    def streaming_run(payload):
        llm.chat([{"role": "user", "content": "write"}],
                 on_chunk=lambda tokens, tail: seen.append((tokens, tail)))
        return DapTaskOutput(summary="s", files=[GeneratedFile(path="backend/database.py",
                                                              content="x")])

    from types import SimpleNamespace
    chunks = [
        SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="AB"))]),
        SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="CD"))]),
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2), choices=[]),
    ]

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return iter(chunks)

    class FakeChat:
        completions = FakeCompletions

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llm, "_client", lambda *a, **k: FakeClient())
    executor = Executor(run=streaming_run)
    payload = DapTaskPayload(
        task_id="t1", project_id="p", type=TaskType.DATABASE, title="database",
        description="d", requirement_text="r", target_files=["backend/database.py"])
    remote = executor.submit(payload, "p")
    for _ in range(100):
        task = executor.get(remote.id)
        if task.status.state == A2ATaskState.COMPLETED:
            break
        threading.Event().wait(0.05)
    assert seen, "on_chunk must fire while the model writes"
    assert seen[-1][1] == "ABCD"
    assert live_progress(remote.id) == {}  # the task finished: the live view is empty again


def test_chat_streams_the_chunks_and_reports_the_tail(db, monkeypatch):
    from types import SimpleNamespace
    import dap.shared.llm_client as llm
    monkeypatch.setenv("LLM_BASE_URL", "http://fake:1/v1")
    monkeypatch.setenv("LLM_MODEL", "fake")

    chunks = [
        SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="AB"))]),
        SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=SimpleNamespace(content="CD"))]),
        SimpleNamespace(usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2), choices=[]),
    ]
    calls = {}

    class FakeCompletions:
        @staticmethod
        def create(**kwargs):
            calls.update(kwargs)
            return iter(chunks)

    class FakeChat:
        completions = FakeCompletions

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llm, "_client", lambda *a, **k: FakeClient())
    seen: list[tuple[int, str]] = []
    answer = llm.chat([{"role": "user", "content": "hi"}], on_chunk=lambda t, tail: seen.append((t, tail)))
    assert answer.text == "ABCD"
    assert answer.completion_tokens == 2
    assert calls["stream"] is True
    assert seen[-1][1] == "ABCD"


def test_the_master_live_endpoint_proxies_the_worker(db, monkeypatch):
    pid = make_project()
    client = TestClient(app)
    assert client.get(f"/api/v1/projects/{pid}/live").json() == []  # nothing runs

    agent("a1")
    (task,) = repositories.create_tasks(pid, [TaskCreate(
        id="rev1", type=TaskType.REVISION, title="t", description="d")])
    repositories.assign_task(task.id, "a1", "live")
    repositories.set_task_status(task.id, TaskStatus.IN_PROGRESS, remote_task_id="r1")
    progress = {"round": 1, "type": "revision", "generated_tokens": 120, "tail": "=== FILE: b"}
    monkeypatch.setattr(a2a_client, "get_progress", lambda url, remote_id, token: progress)
    answer = client.get(f"/api/v1/projects/{pid}/live")
    assert answer.status_code == 200
    (entry,) = answer.json()
    assert entry["type"] == "revision" and entry["generated_tokens"] == 120

    # a task that stopped generating between polls is skipped, not shown broken
    monkeypatch.setattr(a2a_client, "get_progress", lambda url, remote_id, token: {})
    assert client.get(f"/api/v1/projects/{pid}/live").json() == []
