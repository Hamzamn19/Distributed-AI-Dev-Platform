"""Project and task endpoints.

Owner: Baran - cards S1-05 and S1-06.

Endpoints to add (paths are relative to /api/v1, see docs/PROJECT_CONTRACT.md):

    POST /projects                 body ProjectCreate -> 201 Project      (S1-05)
        A missing or too short requirement_text gives 422 automatically.
    GET  /projects                                    -> 200 list[Project] (S1-05)
    GET  /projects/{id}                               -> 200 Project, 404  (S1-05)
    GET  /projects/{id}/tasks                         -> 200 list[Task]    (S1-05)
    POST /projects/{id}/decompose                     -> 200 list[Task]    (S1-06)
        Calls dap.master.core.decomposer and stores the tasks.
    POST /projects/{id}/assign                        -> 200 list[Task]    (S1-06)
        Calls dap.master.core.selector; fills assigned_agent_id and
        assignment_reason.

Status: create, list, get, tasks and decompose are done. /assign waits for
core/selector.py. After a successful decompose the project is "in_progress"
(the enum has no "decomposed"); while the model works it is "decomposing".

Rules:
- Use only the functions in dap.master.db.repositories. No SQL or session here.
- When the LLM is down or keeps returning broken JSON: answer with a clear
  {"detail": "..."} error, set the project status to "failed", never crash.
"""

import logging

from fastapi import APIRouter, HTTPException

from dap.master.core import decomposer
from dap.master.db import repositories
from dap.shared.enums import ProjectStatus
from dap.shared.schemas import Project, ProjectCreate, Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_project_or_404(project_id: str) -> Project:
    project = repositories.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id!r} not found")
    return project


@router.post("", response_model=Project, status_code=201)
def create_project(body: ProjectCreate) -> Project:
    return repositories.create_project(body)


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    return repositories.list_projects()


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    return _get_project_or_404(project_id)


@router.get("/{project_id}/tasks", response_model=list[Task])
def list_tasks(project_id: str) -> list[Task]:
    _get_project_or_404(project_id)
    return repositories.list_tasks(project_id)


@router.post("/{project_id}/decompose", response_model=list[Task])
def decompose_project(project_id: str) -> list[Task]:
    project = _get_project_or_404(project_id)
    existing = repositories.list_tasks(project_id)
    if existing:
        return existing

    repositories.set_project_status(project_id, ProjectStatus.DECOMPOSING)
    try:
        task_creates = decomposer.decompose(project.requirement_text)
    except RuntimeError as exc:
        logger.error("Decomposition of project %s failed: %s", project_id, exc)
        repositories.set_project_status(project_id, ProjectStatus.FAILED)
        raise HTTPException(status_code=502, detail=f"Decomposition failed: {exc}") from exc

    tasks = repositories.create_tasks(project_id, task_creates)
    repositories.set_project_status(project_id, ProjectStatus.IN_PROGRESS)
    return tasks
