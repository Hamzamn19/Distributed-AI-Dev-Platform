"""Agent endpoints.

Owner: Baran - card S1-05.

Endpoints to add (paths are relative to /api/v1, see docs/PROJECT_CONTRACT.md):

    POST /agents/register              body AgentRegister -> 200 Agent
        The same agent_id registering again updates the existing record.
    POST /agents/{agent_id}/heartbeat  body Heartbeat     -> 200 HeartbeatAck
        404 when the agent is not registered (the worker then registers again).
    GET  /agents                                           -> 200 list[Agent]
        Before answering, call mark_stale_agents_offline(HEARTBEAT_TIMEOUT_SEC).

Rules:
- register and heartbeat need the "X-Agent-Token" header to equal AGENT_TOKEN;
  otherwise answer 401 with {"detail": "..."}. GET /agents needs no token.
- Use only the functions in dap.master.db.repositories. No SQL or session here.
- Request and response models come from dap.shared.schemas.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])
