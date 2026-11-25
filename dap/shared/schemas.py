"""Shared data models (Pydantic v2): the shapes that travel between modules.

Rules (docs/contracts/PROJECT_CONTRACT.md):
- Field names are snake_case everywhere, including the frontend.
- Project and task ids are UUID4 strings created by the master.
- Time fields end with "_at", are timezone-aware UTC and serialize as ISO 8601.
- A field without a value is sent as null, never left out.
- Unknown fields are rejected, so a misspelled field name fails loudly.
- Exception: the A2A wire models at the end use the protocol's camelCase names
  and ignore unknown fields, because the A2A specification may add fields.

Do not change a field without updating docs/contracts/PROJECT_CONTRACT.md first.
"""

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from dap.shared.enums import A2ATaskState, AgentStatus, ProjectStatus, TaskStatus, TaskType

# Shortest and longest requirement text the master accepts (outside gives HTTP 422).
MIN_REQUIREMENT_LENGTH = 20
MAX_REQUIREMENT_LENGTH = 12000


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
    # Address of the worker's A2A server, for example http://100.x.y.z:9000 (Sprint 3).
    a2a_url: str | None = None


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
    requirement_text: str = Field(
        min_length=MIN_REQUIREMENT_LENGTH, max_length=MAX_REQUIREMENT_LENGTH
    )


class Project(ContractModel):
    id: str
    name: str
    requirement_text: str
    status: ProjectStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FollowupCreate(ContractModel):
    """Body of POST /projects/{id}/followup: a change on the finished application.

    The master turns it into one `revision` task over the finished tasks and runs
    it (Sprint 4; contract sections 8 and 9).
    """

    instruction: str = Field(min_length=10, max_length=2000)


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
    """One stored result of a task (task_results table, GET /projects/{id}/results).

    The master builds it from the DapTaskOutput the worker returns over A2A.
    """

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


# --------------------------------------------- task payloads inside A2A messages


class DapTaskPayload(ContractModel):
    """What the master sends a worker: the data part of the A2A message."""

    task_id: str
    project_id: str
    type: TaskType
    title: str
    description: str
    requirement_text: str
    target_files: list[str]
    # Files of the tasks this one depends on, already completed.
    dependency_files: list[GeneratedFile] = Field(default_factory=list)


class DapTaskOutput(ContractModel):
    """What a worker returns: the data part of the A2A artifact named "result"."""

    summary: str
    files: list[GeneratedFile] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: int = 0


# ------------------------------------- A2A wire models (protocol v1.0, HTTP+JSON)


class A2AModel(BaseModel):
    """camelCase on the wire, unknown fields ignored. Serialize with to_wire()."""

    model_config = ConfigDict(extra="ignore", alias_generator=to_camel, populate_by_name=True)

    def to_wire(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class AgentInterface(A2AModel):
    url: str
    protocol_binding: str = "HTTP+JSON"
    protocol_version: str = "1.0"


class A2ACapabilities(A2AModel):
    streaming: bool = False
    push_notifications: bool = False


class AgentSkill(A2AModel):
    id: str
    name: str
    description: str
    tags: list[str] = Field(default_factory=list)


class AgentCard(A2AModel):
    """GET /.well-known/agent-card.json on a worker."""

    name: str
    description: str
    version: str
    supported_interfaces: list[AgentInterface]
    capabilities: A2ACapabilities = Field(default_factory=A2ACapabilities)
    default_input_modes: list[str] = Field(default_factory=lambda: ["application/json"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["application/json"])
    skills: list[AgentSkill] = Field(default_factory=list)


class Part(A2AModel):
    """Exactly one of text or data is set; the member name tells the kind."""

    text: str | None = None
    data: Any | None = None
    media_type: str | None = None


def first_data(parts: list[Part]) -> Any | None:
    """The content of the first data part, or None."""
    return next((part.data for part in parts if part.data is not None), None)


class Message(A2AModel):
    message_id: str
    role: Literal["ROLE_USER", "ROLE_AGENT"]
    context_id: str | None = None
    parts: list[Part]


class TaskStatusA2A(A2AModel):
    state: A2ATaskState
    message: Message | None = None  # on failure: a text part with the reason
    timestamp: AwareDatetime | None = None


class Artifact(A2AModel):
    artifact_id: str
    name: str | None = None
    parts: list[Part]


class A2ATask(A2AModel):
    """Body of GET /tasks/{id}; wrapped in "task" in the message:send answer."""

    id: str
    context_id: str | None = None
    status: TaskStatusA2A
    artifacts: list[Artifact] = Field(default_factory=list)


class SendMessageConfiguration(A2AModel):
    return_immediately: bool = False


class SendMessageRequest(A2AModel):
    """Body of POST /message:send on a worker."""

    message: Message
    configuration: SendMessageConfiguration | None = None


class SendMessageResponse(A2AModel):
    task: A2ATask
