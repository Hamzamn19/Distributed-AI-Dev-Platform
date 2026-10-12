"""HTTP calls from the worker to the master (httpx).

Owner: Eray - card S1-07.

- Base address: WorkerSettings.api_url.
- Every request carries the header "X-Agent-Token": WorkerSettings.agent_token.
- Bodies and answers use the models in dap.shared.schemas
  (model_dump(mode="json") to send, Model.model_validate(...) to read).
- A 404 from heartbeat means the master forgot this worker (for example after
  a restart): register again.
"""

from dap.shared.schemas import Agent, AgentRegister, Heartbeat


def register(payload: AgentRegister) -> Agent:
    """POST /agents/register."""
    raise NotImplementedError("S1-07: implement register()")


def send_heartbeat(agent_id: str, heartbeat: Heartbeat) -> bool:
    """POST /agents/{agent_id}/heartbeat. Return False on 404 (not registered)."""
    raise NotImplementedError("S1-07: implement send_heartbeat()")
