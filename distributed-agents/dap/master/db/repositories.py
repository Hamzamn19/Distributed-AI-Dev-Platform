"""The only door to the database. Can writes these functions, Baran calls them.

Owner: Can - card S1-09.

Rules:
- Each function opens and closes its own session.
- Functions take and return the models in dap.shared.schemas, never ORM objects.
- Create ids with str(uuid.uuid4()) and times with datetime.now(timezone.utc).
- SQLite returns datetimes without a timezone. Attach UTC again before building
  a schema object (value.replace(tzinfo=timezone.utc)); the schemas reject
  naive datetimes on purpose.
- The Capabilities object maps to the cap_coding, cap_reasoning and
  cap_context columns.

Keep the signatures exactly as they are. A change goes through
docs/PROJECT_CONTRACT.md first.
"""

from dap.shared.enums import AgentStatus, ProjectStatus
from dap.shared.schemas import (
    Agent,
    AgentRegister,
    Project,
    ProjectCreate,
    Task,
    TaskCreate,
)

_TODO = "S1-09: implement this repository function"

# ----------------------------------------------------------------- agents


def upsert_agent(data: AgentRegister) -> Agent:
    """Insert the agent, or update it when agent_id already exists. Status becomes idle."""
    raise NotImplementedError(_TODO)


def get_agent(agent_id: str) -> Agent | None:
    raise NotImplementedError(_TODO)


def list_agents() -> list[Agent]:
    raise NotImplementedError(_TODO)


def touch_heartbeat(
    agent_id: str, status: AgentStatus, current_task_id: str | None
) -> bool:
    """Store the heartbeat. Return False when the agent is not registered."""
    raise NotImplementedError(_TODO)


def mark_stale_agents_offline(timeout_sec: int) -> int:
    """Set agents silent for longer than timeout_sec to offline. Return how many changed."""
    raise NotImplementedError(_TODO)


# --------------------------------------------------------------- projects


def create_project(data: ProjectCreate) -> Project:
    """Store a new project with status "created"."""
    raise NotImplementedError(_TODO)


def get_project(project_id: str) -> Project | None:
    raise NotImplementedError(_TODO)


def list_projects() -> list[Project]:
    raise NotImplementedError(_TODO)


def set_project_status(project_id: str, status: ProjectStatus) -> None:
    raise NotImplementedError(_TODO)


# ------------------------------------------------------------------ tasks


def create_tasks(project_id: str, tasks: list[TaskCreate]) -> list[Task]:
    """Store the tasks with status "pending" and attempt 0."""
    raise NotImplementedError(_TODO)


def list_tasks(project_id: str) -> list[Task]:
    raise NotImplementedError(_TODO)


def get_task(task_id: str) -> Task | None:
    raise NotImplementedError(_TODO)


def assign_task(task_id: str, agent_id: str, reason: str) -> Task:
    """Set assigned_agent_id and assignment_reason; status becomes "assigned"."""
    raise NotImplementedError(_TODO)
