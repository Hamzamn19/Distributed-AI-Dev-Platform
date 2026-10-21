"""Agent endpoints.

Owner: Baran - card S1-05.

Paths are relative to /api/v1 (see docs/contracts/PROJECT_CONTRACT.md):

    POST /agents/register              body AgentRegister -> 200 Agent
        The same agent_id registering again updates the existing record.
    POST /agents/{agent_id}/heartbeat  body Heartbeat     -> 200 HeartbeatAck
        404 when the agent is not registered (the worker then registers again).
    GET  /agents                                           -> 200 list[Agent]
        Marks agents without a recent heartbeat offline before answering.

register and heartbeat need the "X-Agent-Token" header to equal AGENT_TOKEN;
otherwise the answer is 401 with {"detail": "..."}. GET /agents needs no token.
"""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException

from dap.master.config import get_settings
from dap.master.db import repositories
from dap.shared.schemas import Agent, AgentRegister, Heartbeat, HeartbeatAck

router = APIRouter(prefix="/agents", tags=["agents"])


def require_agent_token(x_agent_token: str | None = Header(default=None)) -> None:
    expected = get_settings().agent_token
    if x_agent_token is None or not secrets.compare_digest(
        x_agent_token.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or wrong X-Agent-Token")


@router.post("/register", response_model=Agent, dependencies=[Depends(require_agent_token)])
def register_agent(body: AgentRegister) -> Agent:
    return repositories.upsert_agent(body)


@router.post(
    "/{agent_id}/heartbeat",
    response_model=HeartbeatAck,
    dependencies=[Depends(require_agent_token)],
)
def heartbeat(agent_id: str, body: Heartbeat) -> HeartbeatAck:
    if not repositories.touch_heartbeat(agent_id, body.status, body.current_task_id):
        raise HTTPException(status_code=404, detail=f"Agent {agent_id!r} is not registered")
    return HeartbeatAck()


@router.get("", response_model=list[Agent])
def list_agents() -> list[Agent]:
    repositories.mark_stale_agents_offline(get_settings().heartbeat_timeout_sec)
    return repositories.list_agents()
