"""Shared enum values: the single source of truth for master, worker and database.

Do not rename, add or remove a value without updating docs/contracts/PROJECT_CONTRACT.md
first. The frontend mirrors these values in frontend/src/api/types.ts.
"""

from enum import StrEnum


class AgentStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class TaskType(StrEnum):
    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    TESTING = "testing"
    CODE_REVIEW = "code_review"
    INTEGRATION = "integration"
    DOCUMENTATION = "documentation"


class TaskStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectStatus(StrEnum):
    CREATED = "created"
    DECOMPOSING = "decomposing"
    IN_PROGRESS = "in_progress"
    INTEGRATING = "integrating"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATaskState(StrEnum):
    """Task states on the A2A wire (protocol v1.0); only the four we use."""

    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"


# How the master stores a worker's A2A task state.
A2A_TO_TASK_STATUS: dict[A2ATaskState, TaskStatus] = {
    A2ATaskState.SUBMITTED: TaskStatus.IN_PROGRESS,
    A2ATaskState.WORKING: TaskStatus.IN_PROGRESS,
    A2ATaskState.COMPLETED: TaskStatus.COMPLETED,
    A2ATaskState.FAILED: TaskStatus.FAILED,
}


# The Sprint 1 decomposer may only produce these four task types.
SPRINT1_TASK_TYPES: tuple[TaskType, ...] = (
    TaskType.FRONTEND,
    TaskType.BACKEND,
    TaskType.DATABASE,
    TaskType.TESTING,
)

# A failed task goes back to "pending" until it has been tried this many times.
MAX_TASK_ATTEMPTS = 3
