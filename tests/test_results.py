"""S2-05: real SQLite result/event storage and durable generated files."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from dap.master.db import database, repositories, results
from dap.master.db.models import AgentModel, EventModel, ProjectModel, TaskModel, TaskResultModel
from dap.shared.enums import TaskStatus, TaskType
from dap.shared.schemas import AgentRegister, Capabilities, GeneratedFile, ProjectCreate, TaskCreate, TaskResult


@pytest.fixture
def store(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'results.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(repositories, "SessionLocal", sessions)
    monkeypatch.setattr(results, "SessionLocal", sessions)
    yield engine, sessions
    engine.dispose()


@pytest.fixture
def task_result(store):
    agent = repositories.upsert_agent(AgentRegister(
        agent_id="agent-can", name="Can", owner="Can", model="test-model",
        capabilities=Capabilities(coding=70, reasoning=60, context=50),
    ))
    project = repositories.create_project(ProjectCreate(
        name="Library", requirement_text="Build a library application with books and members."
    ))
    task = repositories.create_tasks(project.id, [TaskCreate(
        id=str(uuid4()), title="Database", description="Create schema", type=TaskType.DATABASE,
    )])[0]
    repositories.assign_task(task.id, agent.agent_id, "Database capability")
    return TaskResult(
        task_id=task.id, agent_id=agent.agent_id, success=True, summary="Schema created",
        files=[GeneratedFile(path="db/schema.sql", content="CREATE TABLE books (id INTEGER PRIMARY KEY);\n")],
        duration_ms=120, tokens_used=42,
    )


def counts(store):
    with store[1]() as session:
        return (
            session.scalar(select(func.count()).select_from(TaskResultModel)),
            session.scalar(select(func.count()).select_from(EventModel)),
        )


def test_result_saves_payload_files_status_and_one_event(store, task_result, tmp_path):
    root = tmp_path / "workspace"
    saved = results.store_task_result(task_result, run_id="run-1", workspace_root=root)
    assert saved == task_result
    assert results.get_task_result(saved.task_id, run_id="run-1") == saved
    assert results.get_task_result(saved.task_id, run_id="other") is None
    assert results.list_task_results(saved.task_id) == [saved]
    task = repositories.get_task(saved.task_id)
    assert task.status == TaskStatus.COMPLETED
    assert (root / task.project_id / "run-1/db/schema.sql").read_text("utf-8") == saved.files[0].content
    assert counts(store) == (1, 1)
    with store[1]() as session:
        history = session.scalar(select(EventModel))
        assert history.type == "task_completed"
        assert history.project_id == task.project_id
        assert history.agent_id == saved.agent_id
        assert json.loads(history.message)["run_id"] == "run-1"


def test_delivery_retry_is_idempotent_and_changed_result_is_rejected(store, task_result, tmp_path):
    root = tmp_path / "workspace"
    results.store_task_result(task_result, run_id="run-1", workspace_root=root)
    original_task = repositories.get_task(task_result.task_id)
    assert results.store_task_result(task_result, run_id="run-1", workspace_root=root) == task_result
    with pytest.raises(ValueError, match="different result"):
        results.store_task_result(
            task_result.model_copy(update={"summary": "Changed"}), run_id="run-1", workspace_root=root
        )
    assert counts(store) == (1, 1)
    assert repositories.get_task(task_result.task_id) == original_task


def test_failed_task_result_is_preserved_for_master_retry_decision(store, task_result, tmp_path):
    failed = task_result.model_copy(update={"success": False, "error": "Model failed", "files": []})
    assert results.store_task_result(failed, run_id="run-1", workspace_root=tmp_path) == failed
    assert repositories.get_task(failed.task_id).status == TaskStatus.FAILED
    assert results.get_task_result(failed.task_id, run_id="run-1").error == "Model failed"
    with store[1]() as session:
        assert session.scalar(select(EventModel.type)) == "task_failed"


@pytest.mark.parametrize("field,value", [
    ("task_id", "missing"), ("agent_id", "other-agent"),
    ("duration_ms", -1), ("tokens_used", -1),
])
def test_invalid_result_does_not_change_storage(store, task_result, tmp_path, field, value):
    before = repositories.get_task(task_result.task_id)
    with pytest.raises(ValueError):
        results.store_task_result(
            task_result.model_copy(update={field: value}), run_id="run-1", workspace_root=tmp_path / "workspace"
        )
    assert counts(store) == (0, 0)
    assert repositories.get_task(task_result.task_id) == before
    assert not (tmp_path / "workspace").exists()


def test_bad_file_path_rolls_back_result_status_and_event(store, task_result, tmp_path):
    before = repositories.get_task(task_result.task_id)
    invalid = task_result.model_copy(update={"files": [GeneratedFile(path="../escape.sql", content="bad")]})
    with pytest.raises(ValueError):
        results.store_task_result(invalid, run_id="run-1", workspace_root=tmp_path / "workspace")
    assert counts(store) == (0, 0)
    assert repositories.get_task(task_result.task_id) == before


def test_write_error_does_not_complete_task(store, task_result, tmp_path, monkeypatch):
    def fail_write(*args, **kwargs):
        raise OSError("Disk unavailable")

    before = repositories.get_task(task_result.task_id)
    monkeypatch.setattr(results, "save_generated_files", fail_write)
    with pytest.raises(OSError, match="Disk unavailable"):
        results.store_task_result(task_result, run_id="run-1", workspace_root=tmp_path)
    assert counts(store) == (0, 0)
    assert repositories.get_task(task_result.task_id) == before


def test_new_run_preserves_older_result_and_files(store, task_result, tmp_path):
    results.store_task_result(task_result, run_id="run-1", workspace_root=tmp_path)
    repositories.assign_task(task_result.task_id, task_result.agent_id, "New execution")
    revised = task_result.model_copy(update={
        "files": [GeneratedFile(path="db/schema.sql", content="-- revised schema\n")],
    })
    results.store_task_result(revised, run_id="run-2", workspace_root=tmp_path)
    assert results.get_task_result(task_result.task_id, run_id="run-1") == task_result
    assert results.get_task_result(task_result.task_id, run_id="run-2") == revised
    assert len(results.list_task_results(task_result.task_id)) == 2
    project_id = repositories.get_task(task_result.task_id).project_id
    assert (tmp_path / project_id / "run-1/db/schema.sql").read_text("utf-8") == task_result.files[0].content
    assert counts(store) == (2, 2)


def test_event_context_and_invalid_project_are_checked(store, task_result):
    task = repositories.get_task(task_result.task_id)
    identifier = results.record_event("task_note", "Manual note", task_id=task.id, agent_id=task_result.agent_id)
    agent_event = results.record_event("agent_note", "Agent only", agent_id=task_result.agent_id)
    with store[1]() as session:
        assert session.get(EventModel, identifier).project_id == task.project_id
        assert session.get(EventModel, agent_event).project_id is None
    with pytest.raises(ValueError):
        results.record_event("task_note", "Wrong project", task_id=task.id, project_id="other")
    with pytest.raises(ValueError):
        results.record_event("", "Missing event type")
    assert counts(store) == (0, 2)


@pytest.mark.parametrize("statement", [
    "UPDATE task_results SET tokens_used = -1",
    "UPDATE task_results SET duration_ms = -1",
    "UPDATE task_results SET task_id = 'unknown'",
    "UPDATE events SET agent_id = 'unknown'",
])
def test_result_and_event_database_constraints(store, task_result, tmp_path, statement):
    results.store_task_result(task_result, run_id="run-1", workspace_root=tmp_path)
    with pytest.raises(IntegrityError):
        with store[0].begin() as connection:
            connection.execute(text(statement))
    assert counts(store) == (1, 1)


def test_create_all_adds_new_tables_without_losing_existing_records(monkeypatch):
    # Start a second database with only the three original tables.
    legacy = create_engine("sqlite://")
    database.Base.metadata.create_all(legacy, tables=[AgentModel.__table__, ProjectModel.__table__, TaskModel.__table__])
    with legacy.begin() as connection:
        connection.execute(ProjectModel.__table__.insert().values(
            id="old-project", name="Old project", requirement_text="Existing requirement text",
            status="created", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        ))
    monkeypatch.setattr(database, "engine", legacy)
    database.init_db()
    assert set(inspect(legacy).get_table_names()) == {"agents", "projects", "tasks", "events", "task_results"}
    with legacy.connect() as connection:
        assert connection.scalar(text("SELECT name FROM projects WHERE id = 'old-project'")) == "Old project"
    legacy.dispose()


def test_result_events_and_files_survive_separate_processes(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    writer = '''
import sys
from uuid import uuid4
from pathlib import Path
from dap.master.db import repositories as r, results
from dap.shared.schemas import AgentRegister, Capabilities, ProjectCreate, TaskCreate, TaskResult, GeneratedFile
from dap.shared.enums import TaskType
a=r.upsert_agent(AgentRegister(agent_id='agent-can',name='Can',owner='Can',model='test',capabilities=Capabilities(coding=70,reasoning=60,context=50)))
p=r.create_project(ProjectCreate(name='Library',requirement_text='Build a library application with books.'))
t=r.create_tasks(p.id,[TaskCreate(id=str(uuid4()),title='Schema',description='Create schema',type=TaskType.DATABASE)])[0]
r.assign_task(t.id,a.agent_id,'Match')
results.store_task_result(TaskResult(task_id=t.id,agent_id=a.agent_id,success=True,summary='Done',files=[GeneratedFile(path='db/schema.sql',content='-- durable SQL')],duration_ms=123,tokens_used=45),run_id='run-1',workspace_root=Path(sys.argv[1]))
print(t.id)
'''
    root = tmp_path / "workspace"
    written = subprocess.run([sys.executable, "-c", writer, str(root)], cwd=repo_root, env=environment, capture_output=True, text=True, check=True, timeout=30)
    reader = '''
import json,sys
from pathlib import Path
from sqlalchemy import select,func
from dap.master.db import repositories as r,results
from dap.master.db.database import SessionLocal
from dap.master.db.models import EventModel
t=r.get_task(sys.argv[1]); result=results.get_task_result(t.id,run_id='run-1')
with SessionLocal() as session: count=session.scalar(select(func.count()).select_from(EventModel))
print(json.dumps({'status':t.status.value,'summary':result.summary,'tokens':result.tokens_used,'duration':result.duration_ms,'events':count,'sql':(Path(sys.argv[2])/t.project_id/'run-1/db/schema.sql').read_text('utf-8')}))
'''
    read = subprocess.run([sys.executable, "-c", reader, written.stdout.strip(), str(root)], cwd=repo_root, env=environment, capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(read.stdout) == {
        "status": "completed", "summary": "Done", "tokens": 45,
        "duration": 123, "events": 1, "sql": "-- durable SQL",
    }
