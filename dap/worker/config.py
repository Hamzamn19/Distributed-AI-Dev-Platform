"""Worker settings. Every value comes from the environment (.env), never from code."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from dap.shared.enums import TaskType
from dap.shared.schemas import AgentRegister, Capabilities

load_dotenv()


@dataclass(frozen=True)
class WorkerSettings:
    master_url: str
    agent_token: str
    agent_id: str
    agent_name: str
    agent_owner: str
    role_hint: TaskType | None
    model: str
    provider: str
    cap_coding: int
    cap_reasoning: int
    cap_context: int
    heartbeat_interval_sec: int
    poll_interval_sec: int

    @property
    def api_url(self) -> str:
        """Base address of the master API, for example http://localhost:8000/api/v1."""
        return f"{self.master_url}/api/v1"

    def to_register_payload(self) -> AgentRegister:
        """The body this worker sends to POST /agents/register."""
        return AgentRegister(
            agent_id=self.agent_id,
            name=self.agent_name,
            owner=self.agent_owner,
            role_hint=self.role_hint,
            model=self.model,
            provider=self.provider,
            capabilities=Capabilities(
                coding=self.cap_coding,
                reasoning=self.cap_reasoning,
                context=self.cap_context,
            ),
        )


def get_settings() -> WorkerSettings:
    role = os.getenv("AGENT_ROLE_HINT", "").strip()
    return WorkerSettings(
        master_url=os.getenv("MASTER_URL", "http://localhost:8000").rstrip("/"),
        agent_token=os.getenv("AGENT_TOKEN", "change-me-team-secret"),
        agent_id=os.getenv("AGENT_ID", "agent-unnamed"),
        agent_name=os.getenv("AGENT_NAME", "Unnamed-PC"),
        agent_owner=os.getenv("AGENT_OWNER", "Unknown"),
        role_hint=TaskType(role) if role else None,
        model=os.getenv("LLM_MODEL", "unknown"),
        provider="ollama",
        cap_coding=int(os.getenv("AGENT_CAP_CODING", "50")),
        cap_reasoning=int(os.getenv("AGENT_CAP_REASONING", "50")),
        cap_context=int(os.getenv("AGENT_CAP_CONTEXT", "50")),
        heartbeat_interval_sec=int(os.getenv("HEARTBEAT_INTERVAL_SEC", "10")),
        poll_interval_sec=int(os.getenv("POLL_INTERVAL_SEC", "3")),
    )
