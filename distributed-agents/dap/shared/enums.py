"""Shared enum values: the single source of truth for master, worker and database.

Do not rename, add or remove a value without updating docs/PROJECT_CONTRACT.md
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


# The Sprint 1 decomposer may only produce these four task types.
SPRINT1_TASK_TYPES: tuple[TaskType, ...] = (
    TaskType.FRONTEND,
    TaskType.BACKEND,
    TaskType.DATABASE,
    TaskType.TESTING,
)

# A failed task goes back to "pending" until it has been tried this many times.
MAX_TASK_ATTEMPTS = 3
