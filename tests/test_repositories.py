"""S1-09: exercise real SQLite persistence and the shared return models."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from dap.master.db import database, repositories
from dap.master.db.models import AgentModel
from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus, TaskType
from dap.shared.schemas import Agent, AgentRegister, Capabilities, Project, ProjectCreate, Task, TaskCreate


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Each test owns a new file database; production data is never opened."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{(tmp_path / 'repository.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    database.Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(repositories, "SessionLocal", sessions)
    yield engine, sessions
    engine.dispose()


@pytest.fixture
def registration():
    return AgentRegister(
        agent_id="agent-can",
        name="Can-PC",
        owner="Can",
        role_hint=TaskType.DATABASE,
        model="test-model",
        capabilities=Capabilities(coding=70, reasoning=60, context=50),
    )


def test_import_initializes_all_tables():
    assert set(inspect(database.engine).get_table_names()) == {"agents", "projects", "tasks"}
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_agent_round_trip_and_unknown_lookup(store, registration):
    created = repositories.upsert_agent(registration)
    assert isinstance(created, Agent)
    assert created.status == AgentStatus.IDLE
    assert repositories.get_agent(registration.agent_id) == created
    assert repositories.list_agents() == [created]
    assert repositories.get_agent("unknown") is None
    assert created.registered_at.tzinfo == timezone.utc
    assert created.model_dump(mode="json")["last_heartbeat_at"].endswith("Z")


def test_registration_updates_without_duplicates(store, registration):
    first = repositories.upsert_agent(registration)
    changed = registration.model_copy(update={
        "name": "Updated-PC", "capabilities": Capabilities(coding=90, reasoning=80, context=70)
    })
    second = repositories.upsert_agent(changed)
    assert len(repositories.list_agents()) == 1
    assert second.name == "Updated-PC"
    assert second.capabilities.coding == 90
    assert second.registered_at == first.registered_at


def test_heartbeat_updates_state_and_unknown_returns_false(store, registration):
    repositories.upsert_agent(registration)
    assert repositories.touch_heartbeat("unknown", AgentStatus.IDLE, None) is False
    assert repositories.touch_heartbeat(registration.agent_id, AgentStatus.BUSY, "task-1") is True
    agent = repositories.get_agent(registration.agent_id)
    assert agent.status == AgentStatus.BUSY
    assert agent.current_task_id == "task-1"
    assert agent.last_heartbeat_at.tzinfo == timezone.utc


def test_stale_agents_and_re_registration(store, registration):
    repositories.upsert_agent(registration)
    fresh = registration.model_copy(update={"agent_id": "agent-fresh"})
    repositories.upsert_agent(fresh)
    with store[1].begin() as session:
        record = session.get(AgentModel, registration.agent_id)
        record.last_heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    assert repositories.mark_stale_agents_offline(30) == 1
    assert repositories.get_agent(registration.agent_id).status == AgentStatus.OFFLINE
    assert repositories.get_agent(fresh.agent_id).status == AgentStatus.IDLE
    assert repositories.mark_stale_agents_offline(30) == 0
    assert repositories.upsert_agent(registration).status == AgentStatus.IDLE


def test_stale_agent_without_heartbeat_uses_registration_time(store, registration):
    repositories.upsert_agent(registration)
    with store[1].begin() as session:
        record = session.get(AgentModel, registration.agent_id)
        record.last_heartbeat_at = None
        record.registered_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    assert repositories.mark_stale_agents_offline(30) == 1


@pytest.mark.parametrize("field,value", [("status", "done"), ("role_hint", "invented")])
def test_sqlite_rejects_invalid_agent_enums(store, registration, field, value):
    repositories.upsert_agent(registration)
    with pytest.raises(IntegrityError):
        with store[0].begin() as connection:
            connection.execute(text(f"UPDATE agents SET {field} = :value"), {"value": value})
    assert repositories.get_agent(registration.agent_id).status == AgentStatus.IDLE


@pytest.fixture
def project_data():
    return ProjectCreate(name="Library", requirement_text="Build a library management application.")


def task_data(task_type=TaskType.DATABASE, depends_on=None):
    return TaskCreate(
        id=str(uuid4()), title="Implement library", description="Create the required component",
        type=task_type, depends_on=depends_on or [],
    )


def test_project_round_trip_and_status(store, project_data):
    project = repositories.create_project(project_data)
    assert isinstance(project, Project)
    assert UUID(project.id).version == 4
    assert project.status == ProjectStatus.CREATED
    assert repositories.get_project(project.id) == project
    assert repositories.list_projects() == [project]
    assert repositories.get_project("unknown") is None
    repositories.set_project_status(project.id, ProjectStatus.IN_PROGRESS)
    changed = repositories.get_project(project.id)
    assert changed.status == ProjectStatus.IN_PROGRESS
    assert changed.updated_at >= project.updated_at
    assert changed.updated_at.tzinfo == timezone.utc
    with pytest.raises(ValueError):
        repositories.set_project_status("unknown", ProjectStatus.FAILED)


def test_task_batch_dependencies_and_project_filter(store, project_data):
    first_project = repositories.create_project(project_data)
    second_project = repositories.create_project(project_data)
    first = task_data()
    second = task_data(TaskType.BACKEND, [first.id])
    tasks = repositories.create_tasks(first_project.id, [first, second])
    assert all(isinstance(task, Task) for task in tasks)
    assert [task.id for task in tasks] == [first.id, second.id]
    assert all(task.status == TaskStatus.PENDING and task.attempt == 0 for task in tasks)
    assert tasks[1].depends_on == [first.id]
    assert tasks[0].assigned_agent_id is None and tasks[0].assignment_reason is None
    assert repositories.get_task(second.id) == tasks[1]
    assert {task.id for task in repositories.list_tasks(first_project.id)} == {first.id, second.id}
    assert repositories.list_tasks(second_project.id) == []
    assert repositories.get_task("unknown") is None
    assert repositories.list_tasks("unknown") == []
    with pytest.raises(ValueError):
        repositories.create_tasks("unknown", [task_data()])


def test_assignment_and_missing_records(store, project_data, registration):
    agent = repositories.upsert_agent(registration)
    project = repositories.create_project(project_data)
    task = repositories.create_tasks(project.id, [task_data()])[0]
    for task_id, agent_id in [("unknown", agent.agent_id), (task.id, "unknown")]:
        with pytest.raises(ValueError):
            repositories.assign_task(task_id, agent_id, "Match")
    assert repositories.get_task(task.id).status == TaskStatus.PENDING
    assigned = repositories.assign_task(task.id, agent.agent_id, "role_hint matches database")
    assert assigned.status == TaskStatus.ASSIGNED
    assert assigned.assigned_agent_id == agent.agent_id
    assert assigned.assignment_reason == "role_hint matches database"
    assert assigned.updated_at >= task.updated_at
    assert repositories.get_task(task.id) == assigned


def test_failed_task_batch_rolls_back_every_insert(store, project_data):
    project = repositories.create_project(project_data)
    existing = task_data()
    repositories.create_tasks(project.id, [existing])
    new_task = task_data()
    with pytest.raises(IntegrityError):
        repositories.create_tasks(project.id, [new_task, existing])
    assert repositories.get_task(new_task.id) is None
    assert [task.id for task in repositories.list_tasks(project.id)] == [existing.id]
    assert repositories.create_tasks(project.id, [new_task])[0].id == new_task.id


@pytest.mark.parametrize("table,field", [("projects", "status"), ("tasks", "status"), ("tasks", "type")])
def test_sqlite_rejects_invalid_project_task_enums(store, project_data, table, field):
    project = repositories.create_project(project_data)
    repositories.create_tasks(project.id, [task_data()])
    with pytest.raises(IntegrityError):
        with store[0].begin() as connection:
            connection.execute(text(f"UPDATE {table} SET {field} = :value"), {"value": "invented"})
    assert repositories.get_project(project.id).status == ProjectStatus.CREATED


@pytest.mark.parametrize("field", ["project_id", "assigned_agent_id"])
def test_sqlite_rejects_orphan_task_references(store, project_data, field):
    project = repositories.create_project(project_data)
    task = repositories.create_tasks(project.id, [task_data()])[0]
    with pytest.raises(IntegrityError):
        with store[0].begin() as connection:
            connection.execute(text(f"UPDATE tasks SET {field} = :value"), {"value": "unknown"})
    assert repositories.get_task(task.id).assigned_agent_id is None


def test_records_survive_process_restart(tmp_path, registration, project_data):
    """Two actual processes use one file; no mocked persistence or shared session."""
    repo_root = Path(__file__).resolve().parent.parent
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{(tmp_path / 'restart' / 'platform.db').as_posix()}"
    writer = '''
import json, sys
from dap.master.db import repositories as r
from dap.shared.schemas import AgentRegister, ProjectCreate, TaskCreate
from dap.shared.enums import ProjectStatus
data = json.loads(sys.argv[1])
agent = r.upsert_agent(AgentRegister.model_validate(data['agent']))
project = r.create_project(ProjectCreate.model_validate(data['project']))
tasks = r.create_tasks(project.id, [TaskCreate.model_validate(item) for item in data['tasks']])
r.assign_task(tasks[1].id, agent.agent_id, 'database role matches')
r.set_project_status(project.id, ProjectStatus.IN_PROGRESS)
print(json.dumps({'agent': agent.agent_id, 'project': project.id, 'tasks': [t.id for t in tasks]}))
'''
    first_task = task_data()
    second_task = task_data(depends_on=[first_task.id])
    payload = json.dumps({
        "agent": registration.model_dump(mode="json"),
        "project": project_data.model_dump(mode="json"),
        "tasks": [first_task.model_dump(mode="json"), second_task.model_dump(mode="json")],
    })
    written = subprocess.run(
        [sys.executable, "-c", writer, payload], cwd=repo_root, env=environment,
        capture_output=True, text=True, check=True, timeout=30,
    )
    identifiers = json.loads(written.stdout)
    reader = '''
import json, sys
from dap.master.db import repositories as r
ids = json.loads(sys.argv[1])
print(json.dumps({
    'agent': r.get_agent(ids['agent']).model_dump(mode='json'),
    'project': r.get_project(ids['project']).model_dump(mode='json'),
    'tasks': [r.get_task(task_id).model_dump(mode='json') for task_id in ids['tasks']],
    'task_count': len(r.list_tasks(ids['project'])),
}))
'''
    read = subprocess.run(
        [sys.executable, "-c", reader, json.dumps(identifiers)], cwd=repo_root, env=environment,
        capture_output=True, text=True, check=True, timeout=30,
    )
    restored = json.loads(read.stdout)
    assert restored["agent"]["agent_id"] == registration.agent_id
    assert restored["project"]["status"] == ProjectStatus.IN_PROGRESS
    assert restored["task_count"] == 2
    assert restored["tasks"][1]["depends_on"] == [first_task.id]
    assert restored["tasks"][1]["assigned_agent_id"] == registration.agent_id
    assert restored["tasks"][1]["assignment_reason"] == "database role matches"
    assert all(task["created_at"].endswith("Z") for task in restored["tasks"])
