"""Follow-up requests on a finished application (Sprint 4).

Owner: Baran (master core) - Sprint 4; built with the team, adoption review pending.

    create_followup(project_id, instruction) -> Task
        One `revision` task over every finished task of a completed project.
    revision_files(project_id) -> list[str]
        The application files a revision task may rewrite (its target_files).

The user asks for a change on the application the agents already built ("add a
due date to every task", "improve the error messages"). The master creates one
`revision` task that depends on all finished tasks - so the run hands it the
current files of every task (contract section 8) - and records the request in
the project history (`results.record_event("followup", ...)`). The worker gets
the instruction, the whole requirement and the current files, and returns every
allowed file complete; unchanged files come back as they are. The run then does
what every run does: commit the files, run the acceptance check, and set the
project to completed or failed again.

Rules of a follow-up request:
- The project must exist and its application must be complete (status
  `completed`); while a run is going the request is refused (HTTP 409, the API
  endpoint checks `orchestrator.is_running` - core does not import orchestrator).
- The task type is `revision` (contract sections 6 and 9); nothing else changes:
  same statuses, same retry rules, same acceptance check afterwards.
- The instruction is stored in the task description (the worker prompt uses it)
  and as a `followup` event.
"""

import uuid

from dap.master.core import integrator
from dap.master.db import repositories, results
from dap.shared.enums import ProjectStatus, TaskType
from dap.shared.schemas import Task, TaskCreate

MAX_INSTRUCTION_LENGTH = 2000

# The files the agents write (contract section 12): what a revision may rewrite.
AGENT_FILES: tuple[str, ...] = tuple(
    sorted(path for paths in integrator.TEMPLATE_FILES.values() for path in paths)
)


class FollowupError(Exception):
    """A follow-up request the master refuses (the API endpoint answers 409)."""


def revision_files(project_id: str) -> list[str]:
    """The agent files of this application that exist right now (the target_files).

    Without a written workspace (it was deleted) every agent file is allowed.
    """
    written = set(integrator.list_files(project_id))
    known = [path for path in AGENT_FILES if path in written]
    return known or list(AGENT_FILES)


def create_followup(project_id: str, instruction: str) -> Task:
    """Create the revision task of one follow-up request; the caller starts the run."""
    text = " ".join(instruction.split())
    if len(text) < 10:
        raise FollowupError("Describe the change in at least 10 characters")
    if len(text) > MAX_INSTRUCTION_LENGTH:
        raise FollowupError(f"The instruction is longer than {MAX_INSTRUCTION_LENGTH} characters")
    project = repositories.get_project(project_id)
    if project is None:
        raise FollowupError(f"Project {project_id!r} not found")
    if project.status != ProjectStatus.COMPLETED:
        raise FollowupError(
            "Follow-up requests need a completed application; run the project first")
    finished = repositories.list_tasks(project_id)
    if not finished:
        raise FollowupError("The project has no finished tasks")

    title = text if len(text) <= 60 else text[:57] + "..."
    task = repositories.create_tasks(project_id, [TaskCreate(
        id=str(uuid.uuid4()),
        title=f"Follow-up: {title}",
        # One line of description, so the worker prompt reads it as one instruction.
        description=f"Follow-up request from the user, over the finished application: {text}",
        type=TaskType.REVISION,
        # Every finished task: the run passes their files on as dependency_files.
        depends_on=[t.id for t in finished],
    )])[0]
    results.record_event("followup", text, project_id=project_id)
    return task
