"""HTTP calls from a worker to the master (card S2-03).

Owner: Eray. Paths are relative to /api/v1 (docs/contracts/PROJECT_CONTRACT.md):

    POST /agents/register              AgentRegister -> Agent
    POST /agents/{id}/heartbeat        Heartbeat     -> {"ok": true}, 404 when unknown
    GET  /agents/{id}/tasks/next                     -> 200 Task, 204 when none, 404 when unknown
    POST /tasks/{id}/result            TaskResult    -> Task
    GET  /projects/{id}                              -> Project (requirement text for the prompt)

The address and the token come from dap/worker/config.py (.env), never from code.
"""

import httpx

from dap.shared.schemas import Agent, AgentRegister, Heartbeat, Project, Task, TaskResult

TIMEOUT_SEC = 30


class AgentNotRegistered(Exception):
    """The master answered 404 for this agent: register again."""


class MasterError(Exception):
    """The master answered with an error status (4xx or 5xx)."""

    def __init__(self, status_code: int, text: str):
        super().__init__(f"{status_code}: {text[:200]}")
        self.status_code = status_code
        self.text = text


# Everything that means "the master did not do it": no connection or an error answer.
MASTER_ERRORS = (httpx.HTTPError, MasterError)


def _check(response) -> None:
    if response.status_code >= 400:
        raise MasterError(response.status_code, response.text)


class MasterClient:
    def __init__(self, api_url: str, agent_token: str, http: httpx.Client | None = None):
        # Tests pass FastAPI's TestClient (an httpx.Client) as `http`.
        self._http = http or httpx.Client(timeout=TIMEOUT_SEC)
        self._api_url = api_url.rstrip("/")
        self._headers = {"X-Agent-Token": agent_token}

    def _url(self, path: str) -> str:
        return f"{self._api_url}{path}"

    def register(self, payload: AgentRegister) -> Agent:
        response = self._http.post(
            self._url("/agents/register"), json=payload.model_dump(mode="json"), headers=self._headers
        )
        _check(response)
        return Agent.model_validate(response.json())

    def send_heartbeat(self, agent_id: str, heartbeat: Heartbeat) -> bool:
        """False when the master does not know this agent (404)."""
        response = self._http.post(
            self._url(f"/agents/{agent_id}/heartbeat"),
            json=heartbeat.model_dump(mode="json"),
            headers=self._headers,
        )
        if response.status_code == 404:
            return False
        _check(response)
        return True

    def next_task(self, agent_id: str) -> Task | None:
        """The next task for this agent, or None when there is nothing to do."""
        response = self._http.get(self._url(f"/agents/{agent_id}/tasks/next"), headers=self._headers)
        if response.status_code == 204:
            return None
        if response.status_code == 404:
            raise AgentNotRegistered(agent_id)
        _check(response)
        return Task.model_validate(response.json())

    def get_project(self, project_id: str) -> Project | None:
        response = self._http.get(self._url(f"/projects/{project_id}"))
        if response.status_code == 404:
            return None
        _check(response)
        return Project.model_validate(response.json())

    def post_result(self, result: TaskResult) -> Task:
        response = self._http.post(
            self._url(f"/tasks/{result.task_id}/result"),
            json=result.model_dump(mode="json"),
            headers=self._headers,
        )
        _check(response)
        return Task.model_validate(response.json())

    def close(self) -> None:
        self._http.close()
