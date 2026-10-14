"""S1-09 tables, matching PROJECT_CONTRACT.md section 8.

agents: agent_id, name, owner, role_hint, model, provider, cap_coding,
        cap_reasoning, cap_context, status, current_task_id, registered_at,
        last_heartbeat_at.
projects: id, name, requirement_text, status, created_at, updated_at.
tasks: id, project_id, title, description, type, status, depends_on,
       assigned_agent_id, assignment_reason, attempt, created_at, updated_at.

Enum values are imported from dap.shared.enums. Timestamps are UTC; SQLite
reads them without timezone information, which repositories restore.
"""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from dap.master.db.database import Base
from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus, TaskType


def enum_column(enum_class, name):
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class AgentModel(Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint("cap_coding BETWEEN 0 AND 100", name="agent_cap_coding"),
        CheckConstraint("cap_reasoning BETWEEN 0 AND 100", name="agent_cap_reasoning"),
        CheckConstraint("cap_context BETWEEN 0 AND 100", name="agent_cap_context"),
    )

    agent_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(String)
    role_hint: Mapped[TaskType | None] = mapped_column(enum_column(TaskType, "agent_role_hint"))
    model: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    cap_coding: Mapped[int] = mapped_column(Integer)
    cap_reasoning: Mapped[int] = mapped_column(Integer)
    cap_context: Mapped[int] = mapped_column(Integer)
    status: Mapped[AgentStatus] = mapped_column(enum_column(AgentStatus, "agent_status"))
    current_task_id: Mapped[str | None] = mapped_column(String)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    requirement_text: Mapped[str] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(enum_column(ProjectStatus, "project_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("attempt >= 0", name="task_attempt_nonnegative"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[TaskType] = mapped_column(enum_column(TaskType, "task_type"))
    status: Mapped[TaskStatus] = mapped_column(enum_column(TaskStatus, "task_status"))
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("agents.agent_id"))
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
