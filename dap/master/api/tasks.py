"""Worker endpoints: the worker loop's door into the master.

Owner: Baran - card S2-01 (worker endpoints, team authorization 23 October;
built with Hamza to unblock S2-03).

Paths are relative to /api/v1 (docs/contracts/PROJECT_CONTRACT.md):

    GET  /agents/{agent_id}/tasks/next  -> 200 Task or 204
        The worker's own assigned task first; otherwise the oldest pending
        task whose depends_on entries are all completed (FR-13) is assigned
        to the asking agent. 404 for an unknown agent.
    POST /tasks/{id}/result  body TaskResult -> 200 Task
        Persists the result through dap.master.db.results (status, history
        event) and writes the generated files under workspace/. A failed
        result requeues the task with attempt + 1 while the contract allows
        more attempts (section 6: at most 3 attempts).

Both need the X-Agent-Token header (shared agreement 3).

Run identifier: there is no runs table in the contract, so the master keeps
one UUID4 per project execution in memory. A requeued task rotates the
project's run ID, because results are stored one final result per task/run
(dap/master/db/RESULTS.md) - the retry's new answer must not collide with
the failed one. Files of earlier runs stay untouched. A master restart
starts new run IDs; the contract-level runs registry is Okan's decision.

Generated files go to `workspace/` relative to the working directory (the
repository root per the run commands; .gitignore covers it). Tests replace
`workspace_root`.
"""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from dap.master.api.agents import require_agent_token
from dap.master.db import repositories
from dap.master.db.results import store_task_result
from dap.shared.enums import TaskStatus
from dap.shared.schemas import Task, TaskResult

router = APIRouter(tags=["worker"])

MAX_ATTEMPTS = 3
workspace_root = Path("workspace")

# project_id -> run ID of its current execution (see the module docstring).
_run_ids: dict[str, str] = {}


def _run_id_for(project_id: str) -> str:
    if project_id not in _run_ids:
        _run_ids[project_id] = str(uuid4())
    return _run_ids[project_id]


def _rotate_run(project_id: str) -> None:
    _run_ids[project_id] = str(uuid4())


def _dependencies_completed(task: Task) -> bool:
    for dependency_id in task.depends_on:
        dependency = repositories.get_task(dependency_id)
        if dependency is None or dependency.status != TaskStatus.COMPLETED:
            return False
    return True


@router.get(
    "/agents/{agent_id}/tasks/next",
    response_model=Task,
    dependencies=[Depends(require_agent_token)],
)
def next_task(agent_id: str) -> Task | Response:
    """Hand out the next task: the agent's own first, then the oldest ready."""
    if repositories.get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} is not registered")

    for project in repositories.list_projects():
        for task in repositories.list_tasks(project.id):
            if task.status == TaskStatus.ASSIGNED and task.assigned_agent_id == agent_id:
                return task

    for project in repositories.list_projects():
        for task in repositories.list_tasks(project.id):
            if task.status == TaskStatus.PENDING and _dependencies_completed(task):
                return repositories.assign_task(
                    task.id, agent_id, "polled by the agent; dependencies completed"
                )

    return Response(status_code=204)


@router.post(
    "/tasks/{task_id}/result",
    response_model=Task,
    dependencies=[Depends(require_agent_token)],
)
def post_result(task_id: str, body: TaskResult) -> Task:
    """Accept one final result for a task and answer with its new state."""
    task = repositories.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} does not exist")
    if body.task_id != task_id:
        raise HTTPException(
            status_code=422, detail="TaskResult.task_id must equal the path task id"
        )
    if body.agent_id != task.assigned_agent_id:
        raise HTTPException(
            status_code=403, detail=f"Task {task_id!r} is not assigned to this agent"
        )
    if body.duration_ms < 0 or body.tokens_used < 0:
        raise HTTPException(
            status_code=422, detail="Result duration and token count must be nonnegative"
        )

    try:
        store_task_result(body, run_id=_run_id_for(task.project_id),
                          workspace_root=workspace_root)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    if not body.success and task.attempt < MAX_ATTEMPTS - 1:
        # Contract section 6: back to pending with attempt + 1, at most 3 attempts.
        task = repositories.retry_task(task_id)
        _rotate_run(task.project_id)
    else:
        task = repositories.get_task(task_id)
    return task
