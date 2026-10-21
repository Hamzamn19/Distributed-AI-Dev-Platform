"""S2-05 local result/event persistence, ready for Master integration review.

Uses the unchanged shared TaskResult payload. Master supplies one run ID per
execution and an explicit workspace root. These additive helper signatures
must be adopted by the API owner; existing contract functions are unchanged.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select

from dap.master.db.database import SessionLocal, init_db
from dap.master.db.models import AgentModel, EventModel, ProjectModel, TaskModel, TaskResultModel
from dap.master.db.workspace import save_generated_files
from dap.shared.enums import TaskStatus
from dap.shared.schemas import TaskResult

init_db()


def _result_id(task_id: str, run_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps(["dap-result", task_id, run_id])))


def _payload(record: TaskResultModel) -> TaskResult:
    return TaskResult(
        task_id=record.task_id, agent_id=record.agent_id, success=record.success,
        summary=record.summary, files=record.files, error=record.error,
        duration_ms=record.duration_ms, tokens_used=record.tokens_used,
    )


def record_event(
    event_type: str,
    message: str,
    *,
    project_id: str | None = None,
    task_id: str | None = None,
    agent_id: str | None = None,
) -> str:
    """Append history and return its ID. A task supplies its project context."""
    if not event_type.strip():
        raise ValueError("Event type must not be empty")
    with SessionLocal.begin() as session:
        if task_id is not None:
            task = session.get(TaskModel, task_id)
            if task is None:
                raise ValueError("Task does not exist")
            if project_id is not None and project_id != task.project_id:
                raise ValueError("Event project does not match its task")
            project_id = task.project_id
        if project_id is not None and session.get(ProjectModel, project_id) is None:
            raise ValueError("Project does not exist")
        if agent_id is not None and session.get(AgentModel, agent_id) is None:
            raise ValueError("Agent does not exist")
        identifier = str(uuid4())
        session.add(EventModel(
            id=identifier, project_id=project_id, task_id=task_id, agent_id=agent_id,
            type=event_type, message=message,
        ))
    return identifier


def get_task_result(task_id: str, *, run_id: str) -> TaskResult | None:
    with SessionLocal() as session:
        record = session.get(TaskResultModel, _result_id(task_id, run_id))
        return _payload(record) if record is not None else None


def list_task_results(task_id: str) -> list[TaskResult]:
    with SessionLocal() as session:
        records = session.scalars(
            select(TaskResultModel).where(TaskResultModel.task_id == task_id)
            .order_by(TaskResultModel.created_at, TaskResultModel.id)
        )
        return [_payload(record) for record in records]


def store_task_result(data: TaskResult, *, run_id: str, workspace_root: Path) -> TaskResult:
    """Persist one final result per task/run and its files, status and history.

    Identical delivery retries are idempotent. Changed results for the same
    task/run are rejected. Task execution retries/reassignment belong to Master.
    The caller serializes writes to a run. Filesystem and database are not a
    distributed transaction; a write/commit error must be reported as failure.
    """
    data = TaskResult.model_validate(data.model_dump())
    if data.duration_ms < 0 or data.tokens_used < 0:
        raise ValueError("Result duration and token count must be nonnegative")
    if not run_id:
        raise ValueError("Run ID must not be empty")
    with SessionLocal.begin() as session:
        task = session.get(TaskModel, data.task_id)
        if task is None:
            raise ValueError("Task does not exist")
        if task.assigned_agent_id != data.agent_id:
            raise ValueError("Result agent is not assigned to this task")
        existing = session.get(TaskResultModel, _result_id(data.task_id, run_id))
        if existing is not None:
            if _payload(existing) != data:
                raise ValueError("A different result already exists for this task/run")
            save_generated_files(task.project_id, run_id, data.files, workspace_root=workspace_root)
            return _payload(existing)
        if task.status not in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
            raise ValueError("Task must be assigned or in progress before accepting a result")
        now = datetime.now(timezone.utc)
        record = TaskResultModel(
            id=_result_id(data.task_id, run_id),
            **data.model_dump(mode="json"), created_at=now,
        )
        session.add(record)
        task.status = TaskStatus.COMPLETED if data.success else TaskStatus.FAILED
        task.updated_at = now
        session.add(EventModel(
            project_id=task.project_id, task_id=task.id, agent_id=data.agent_id,
            type="task_completed" if data.success else "task_failed",
            message=json.dumps({"run_id": run_id, "summary": data.summary}), created_at=now,
        ))
        session.flush()
        save_generated_files(task.project_id, run_id, data.files, workspace_root=workspace_root)
    return data
