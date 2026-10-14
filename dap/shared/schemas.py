"""Shared data models (Pydantic v2): the shapes that travel between modules.

Rules (docs/PROJECT_CONTRACT.md):
- Field names are snake_case everywhere, including the frontend.
- Project and task ids are UUID4 strings created by the master.
- Time fields end with "_at", are timezone-aware UTC and serialize as ISO 8601.
- A field without a value is sent as null, never left out.
- Unknown fields are rejected, so a misspelled field name fails loudly.

Do not change a field without updating docs/PROJECT_CONTRACT.md first.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus, TaskType

# Shortest requirement text the master accepts (shorter gives HTTP 422).
MIN_REQUIREMENT_LENGTH = 20


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------- agents


class Capabilities(ContractModel):
    """Capability scores from 0 to 100."""

    coding: int = Field(ge=0, le=100)
    reasoning: int = Field(ge=0, le=100)
    context: int = Field(ge=0, le=100)


class AgentRegister(ContractModel):
    """Body of POST /agents/register."""

    agent_id: str = Field(min_length=1)
    name: str
    owner: str
    role_hint: TaskType | None = None
    model: str
    provider: str = "ollama"
    capabilities: Capabilities


class Agent(AgentRegister):
    status: AgentStatus
    current_task_id: str | None = None
    registered_at: AwareDatetime
    last_heartbeat_at: AwareDatetime | None = None


class Heartbeat(ContractModel):
    """Body of POST /agents/{agent_id}/heartbeat."""

    status: AgentStatus
    current_task_id: str | None = None


class HeartbeatAck(ContractModel):
    ok: bool = True


# --------------------------------------------------------------- projects


class ProjectCreate(ContractModel):
    """Body of POST /projects."""

    name: str = Field(min_length=1)
    requirement_text: str = Field(min_length=MIN_REQUIREMENT_LENGTH)


class Project(ContractModel):
    id: str
    name: str
    requirement_text: str
    status: ProjectStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


# ------------------------------------------------------------------ tasks


class TaskCreate(ContractModel):
    """One task produced by the decomposer, before it is stored."""

    id: str
    title: str = Field(min_length=1)
    description: str
    type: TaskType
    depends_on: list[str] = Field(default_factory=list)


class Task(ContractModel):
    id: str
    project_id: str
    title: str
    description: str
    type: TaskType
    status: TaskStatus
    depends_on: list[str] = Field(default_factory=list)
    assigned_agent_id: str | None = None
    assignment_reason: str | None = None
    attempt: int = 0
    created_at: AwareDatetime
    updated_at: AwareDatetime


class GeneratedFile(ContractModel):
    path: str
    content: str


class TaskResult(ContractModel):
    """Body of POST /tasks/{id}/result (Sprint 3)."""

    task_id: str
    agent_id: str
    success: bool
    summary: str
    files: list[GeneratedFile] = Field(default_factory=list)
    error: str | None = None
    duration_ms: int
    tokens_used: int


# ------------------------------------------------------------------ other


class LLMResponse(ContractModel):
    """Return value of dap.shared.llm_client.chat()."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


class HealthResponse(ContractModel):
    status: str = "ok"
    version: str
