"""S1-09 persistence functions called by the master API and core.

Each function owns its session and returns shared Pydantic models. Importing
this module initializes the tables. Registering again refreshes the agent's
metadata and heartbeat and returns it to idle; registered_at is preserved.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select, update

from dap.master.db.database import SessionLocal, init_db
from dap.master.db.models import AgentModel, ProjectModel, TaskModel
from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus
from dap.shared.schemas import (
    Agent, AgentRegister, Capabilities, Project, ProjectCreate, Task, TaskCreate,
)

init_db()


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _agent(record: AgentModel) -> Agent:
    return Agent(
        agent_id=record.agent_id,
        name=record.name,
        owner=record.owner,
        role_hint=record.role_hint,
        model=record.model,
        provider=record.provider,
        capabilities=Capabilities(
            coding=record.cap_coding, reasoning=record.cap_reasoning, context=record.cap_context
        ),
        status=record.status,
        current_task_id=record.current_task_id,
        registered_at=_utc(record.registered_at),
        last_heartbeat_at=_utc(record.last_heartbeat_at),
    )


def _project(record: ProjectModel) -> Project:
    return Project(
        id=record.id,
        name=record.name,
        requirement_text=record.requirement_text,
        status=record.status,
        created_at=_utc(record.created_at),
        updated_at=_utc(record.updated_at),
    )


def _task(record: TaskModel) -> Task:
    return Task(
        id=record.id,
        project_id=record.project_id,
        title=record.title,
        description=record.description,
        type=record.type,
        status=record.status,
        depends_on=list(record.depends_on),
        assigned_agent_id=record.assigned_agent_id,
        assignment_reason=record.assignment_reason,
        attempt=record.attempt,
        created_at=_utc(record.created_at),
        updated_at=_utc(record.updated_at),
    )


def upsert_agent(data: AgentRegister) -> Agent:
    """Register an agent, or refresh the same agent_id without duplication."""
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        record = session.get(AgentModel, data.agent_id)
        if record is None:
            record = AgentModel(agent_id=data.agent_id, registered_at=now)
            session.add(record)
        for field in ("name", "owner", "role_hint", "model", "provider"):
            setattr(record, field, getattr(data, field))
        record.cap_coding = data.capabilities.coding
        record.cap_reasoning = data.capabilities.reasoning
        record.cap_context = data.capabilities.context
        record.status = AgentStatus.IDLE
        record.current_task_id = None
        record.last_heartbeat_at = now
        session.flush()
        return _agent(record)


def get_agent(agent_id: str) -> Agent | None:
    with SessionLocal() as session:
        record = session.get(AgentModel, agent_id)
        return _agent(record) if record is not None else None


def list_agents() -> list[Agent]:
    with SessionLocal() as session:
        records = session.scalars(select(AgentModel).order_by(AgentModel.agent_id))
        return [_agent(record) for record in records]


def touch_heartbeat(agent_id: str, status: AgentStatus, current_task_id: str | None) -> bool:
    with SessionLocal.begin() as session:
        record = session.get(AgentModel, agent_id)
        if record is None:
            return False
        record.status = AgentStatus(status)
        record.current_task_id = current_task_id
        record.last_heartbeat_at = datetime.now(timezone.utc)
        return True


def mark_stale_agents_offline(timeout_sec: int) -> int:
    """Mark agents older than the timeout offline, counting changed records."""
    if timeout_sec < 0:
        raise ValueError("timeout_sec must not be negative")
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_sec)
    with SessionLocal.begin() as session:
        result = session.execute(
            update(AgentModel)
            .where(
                AgentModel.status != AgentStatus.OFFLINE,
                func.coalesce(AgentModel.last_heartbeat_at, AgentModel.registered_at) < cutoff,
            )
            .values(status=AgentStatus.OFFLINE)
        )
        return result.rowcount


def create_project(data: ProjectCreate) -> Project:
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        record = ProjectModel(
            id=str(uuid4()),
            name=data.name,
            requirement_text=data.requirement_text,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.flush()
        return _project(record)


def get_project(project_id: str) -> Project | None:
    with SessionLocal() as session:
        record = session.get(ProjectModel, project_id)
        return _project(record) if record is not None else None


def list_projects() -> list[Project]:
    with SessionLocal() as session:
        records = session.scalars(
            select(ProjectModel).order_by(ProjectModel.created_at, ProjectModel.id)
        )
        return [_project(record) for record in records]


def set_project_status(project_id: str, status: ProjectStatus) -> None:
    with SessionLocal.begin() as session:
        record = session.get(ProjectModel, project_id)
        if record is None:
            raise ValueError(f"Project {project_id!r} does not exist")
        record.status = ProjectStatus(status)
        record.updated_at = datetime.now(timezone.utc)


def create_tasks(project_id: str, tasks: list[TaskCreate]) -> list[Task]:
    """Store a complete batch or roll it back; task IDs come from the master."""
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as session:
        if session.get(ProjectModel, project_id) is None:
            raise ValueError(f"Project {project_id!r} does not exist")
        records = [
            TaskModel(
                id=data.id,
                project_id=project_id,
                title=data.title,
                description=data.description,
                type=data.type,
                status=TaskStatus.PENDING,
                depends_on=list(data.depends_on),
                assigned_agent_id=None,
                assignment_reason=None,
                attempt=0,
                created_at=now,
                updated_at=now,
            )
            for data in tasks
        ]
        session.add_all(records)
        session.flush()
        return [_task(record) for record in records]


def list_tasks(project_id: str) -> list[Task]:
    with SessionLocal() as session:
        records = session.scalars(
            select(TaskModel)
            .where(TaskModel.project_id == project_id)
            .order_by(TaskModel.created_at, TaskModel.id)
        )
        return [_task(record) for record in records]


def get_task(task_id: str) -> Task | None:
    with SessionLocal() as session:
        record = session.get(TaskModel, task_id)
        return _task(record) if record is not None else None


def assign_task(task_id: str, agent_id: str, reason: str) -> Task:
    with SessionLocal.begin() as session:
        record = session.get(TaskModel, task_id)
        if record is None:
            raise ValueError(f"Task {task_id!r} does not exist")
        if session.get(AgentModel, agent_id) is None:
            raise ValueError(f"Agent {agent_id!r} does not exist")
        record.assigned_agent_id = agent_id
        record.assignment_reason = reason
        record.status = TaskStatus.ASSIGNED
        record.updated_at = datetime.now(timezone.utc)
        session.flush()
        return _task(record)


def retry_task(task_id: str) -> Task:
    """Contract section 6: a failed task returns to pending with attempt + 1."""
    with SessionLocal.begin() as session:
        record = session.get(TaskModel, task_id)
        if record is None:
            raise ValueError(f"Task {task_id!r} does not exist")
        record.status = TaskStatus.PENDING
        record.attempt += 1
        record.assigned_agent_id = None
        record.assignment_reason = None
        record.updated_at = datetime.now(timezone.utc)
        session.flush()
        return _task(record)
