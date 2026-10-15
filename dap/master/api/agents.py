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

Status: GET /agents is done. Until Can's dap/master/db/repositories.py is in
main, it answers with the six team agents from docs/agents.json (status
"offline") so the frontend gets contract-shaped data. Once the repository
exists, the real database is used and the mock is no longer reached.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from dap.master.config import get_settings
from dap.shared.enums import AgentStatus
from dap.shared.schemas import Agent, AgentRegister

try:
    from dap.master.db import repositories
except ImportError:  # Can's repository (dap/master/db/) is not in main yet
    repositories = None

AGENTS_INVENTORY = Path(__file__).resolve().parents[3] / "docs" / "agents.json"

router = APIRouter(prefix="/agents", tags=["agents"])


def _mock_agents() -> list[Agent]:
    """The team's agents from docs/agents.json, shown as not yet registered."""
    entries = json.loads(AGENTS_INVENTORY.read_text("utf-8"))
    now = datetime.now(timezone.utc)
    return [
        Agent(
            **AgentRegister.model_validate(entry).model_dump(),
            status=AgentStatus.OFFLINE,
            registered_at=now,
        )
        for entry in entries
    ]


@router.get("", response_model=list[Agent])
def list_agents() -> list[Agent]:
    if repositories is None:
        return _mock_agents()
    repositories.mark_stale_agents_offline(get_settings().heartbeat_timeout_sec)
    return repositories.list_agents()
