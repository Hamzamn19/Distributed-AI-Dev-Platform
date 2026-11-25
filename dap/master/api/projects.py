"""Project and task endpoints.

Owner: Baran - cards S1-05 and S1-06.

Endpoints to add (paths are relative to /api/v1, see docs/contracts/PROJECT_CONTRACT.md):

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
    POST /projects/{id}/run                           -> 202 Project, 409  (Sprint 3)
        Starts dap.master.core.orchestrator in a background thread. When agents
        are registered and online but none is idle, the project enters the run
        queue (Sprint 4): a watcher starts it when an agent is free again.
    GET  /projects/{id}/results                       -> 200 list[TaskResult]
    GET  /projects/{id}/files                         -> 200 list[str]
    GET  /projects/{id}/files/{path}                  -> 200 text, 404
    POST /projects/{id}/cancel                        -> 200 Project, 409  (Sprint 3)
        Stops the run (core/orchestrator.cancel): unfinished tasks fail.
    POST /projects/{id}/preview                       -> 200 {"project_id", "port"}
        Runs the generated application on PREVIEW_PORT (core/preview.py); 409 when
        it has no backend/main.py yet, 502 when it does not start.
    POST /projects/{id}/followup  body FollowupCreate -> 202 Project  (Sprint 4)
        A change on the finished application (core/followup.py): one `revision`
        task over the finished tasks, then the run starts on its own. 404, 409
        while a run is going or when the application is not completed.
    GET  /projects/{id}/export                        -> 200 zip  (Sprint 4)
        The generated application as one zip (integrator.export_zip): the app
        files, the helpers and acceptance.json, without .git, app.db and
        __pycache__. 404, 409 when the project has no files yet.

Status: all endpoints are done. After a successful decompose the project is "in_progress"
(the enum has no "decomposed"); while the model works it is "decomposing".

Rules:
- Use only the functions in dap.master.db.repositories. No SQL or session here.
- When the LLM is down or keeps returning broken JSON: answer with a clear
  {"detail": "..."} error, set the project status to "failed", never crash.
"""

import logging

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse

from dap.master.config import get_settings
from dap.master.core import decomposer, followup, integrator, orchestrator, preview, selector
from dap.master.db import repositories, results
from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus
from dap.shared.schemas import FollowupCreate, Project, ProjectCreate, Task, TaskResult

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


@router.post("/{project_id}/assign", response_model=list[Task])
def assign_project(project_id: str) -> list[Task]:
    _get_project_or_404(project_id)
    tasks = repositories.list_tasks(project_id)
    if not tasks:
        raise HTTPException(status_code=409, detail="Project has no tasks; decompose it first")

    # An agent without a recent heartbeat must not get work (contract section 8).
    repositories.mark_stale_agents_offline(get_settings().heartbeat_timeout_sec)
    agents = repositories.list_agents()
    by_id = {task.id: task for task in tasks}
    done: set[str] = set()
    ordered: list[Task] = []

    def visit(task: Task) -> None:
        if task.id in done:
            return
        done.add(task.id)
        for dep_id in task.depends_on:
            if dep_id in by_id:
                visit(by_id[dep_id])
        ordered.append(task)

    for task in tasks:
        visit(task)

    for task in ordered:
        if task.status != TaskStatus.PENDING:
            continue
        choice = selector.select_agent(task, agents)
        if choice is None:
            continue
        agent, reason = choice
        repositories.assign_task(task.id, agent.agent_id, reason)
    return repositories.list_tasks(project_id)


@router.post("/{project_id}/run", response_model=Project, status_code=202)
def run_project(project_id: str) -> Project:
    """Send the assigned tasks to the workers over A2A; follow /tasks for the progress.

    When every online agent is busy, the project is queued and starts when an
    agent is free again (Sprint 4).
    """
    project = _get_project_or_404(project_id)
    if not repositories.list_tasks(project_id):
        raise HTTPException(status_code=409, detail="Project has no tasks; decompose it first")
    if orchestrator.is_running(project_id):
        raise HTTPException(status_code=409, detail="This project is already running")
    if orchestrator.is_queued(project_id):
        raise HTTPException(status_code=409, detail="This project is already in the run queue")
    repositories.mark_stale_agents_offline(get_settings().heartbeat_timeout_sec)
    online = [a for a in repositories.list_agents() if a.status != AgentStatus.OFFLINE]
    if online and not any(a.status == AgentStatus.IDLE for a in online):
        orchestrator.enqueue_run(project_id)
        results.record_event("run_queued", "all agents are busy; the run starts "
                             "when one is free again", project_id=project_id)
        return project
    if not orchestrator.start_run(project_id):
        raise HTTPException(status_code=409, detail="This project is already running")
    return project


@router.get("/{project_id}/results", response_model=list[TaskResult])
def list_results(project_id: str) -> list[TaskResult]:
    _get_project_or_404(project_id)
    return results.list_project_results(project_id)


@router.get("/{project_id}/files", response_model=list[str])
def list_files(project_id: str) -> list[str]:
    _get_project_or_404(project_id)
    return integrator.list_files(project_id)


@router.get("/{project_id}/files/{path:path}", response_class=PlainTextResponse)
def read_file(project_id: str, path: str) -> str:
    _get_project_or_404(project_id)
    try:
        return integrator.read_file(project_id, path)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail=f"File {path!r} not found")


@router.get("/{project_id}/export")
def export_project(project_id: str):
    """Download the generated application as one zip."""
    _get_project_or_404(project_id)
    try:
        content, filename = integrator.export_zip(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=f"Nothing to export: {exc}") from exc
    return Response(content=content, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{project_id}/preview")
def start_preview(project_id: str) -> dict:
    """Run the project's generated application; the UI opens http://<master>:<port>/."""
    _get_project_or_404(project_id)
    try:
        port = preview.start(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail=f"Cannot open the app: {exc}")
    except preview.PreviewError as exc:
        raise HTTPException(status_code=502, detail=f"The app does not start: {exc}")
    return {"project_id": project_id, "port": port}


@router.post("/{project_id}/cancel", response_model=Project)
def cancel_project(project_id: str) -> Project:
    """Stop the project's run: unfinished tasks and the project become failed."""
    _get_project_or_404(project_id)
    if not orchestrator.cancel(project_id):
        raise HTTPException(status_code=409, detail="This project is not running")
    return _get_project_or_404(project_id)


@router.post("/{project_id}/followup", response_model=Project, status_code=202)
def followup_project(project_id: str, body: FollowupCreate) -> Project:
    """Apply a change to the finished application: one revision task, then a run.

    The tasks endpoint list shows the progress like any run; the revision task is
    the last one in GET /tasks.
    """
    project = _get_project_or_404(project_id)
    if orchestrator.is_running(project_id):
        raise HTTPException(status_code=409, detail="This project is running; wait for it to finish")
    try:
        followup.create_followup(project_id, body.instruction)
    except followup.FollowupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not orchestrator.start_run(project_id):
        raise HTTPException(status_code=409, detail="This project is already running")
    return project
