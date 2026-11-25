"""The master's A2A client: talks to the workers' A2A servers (contract section 13).

Owner: Baran - Sprint 3.

    get_agent_card(url) -> AgentCard
    send_task(url, payload, token) -> A2ATask      POST /message:send, returnImmediately
    get_task(url, remote_id, token) -> A2ATask     GET /tasks/{id}

Every call carries X-Agent-Token and A2A-Version: 1.0. Any problem (worker not
reachable, wrong token, unexpected answer) raises A2AError with a clear message.
"""

import uuid

import httpx
from pydantic import ValidationError

from dap.shared.schemas import (
    A2ATask,
    AgentCard,
    DapTaskPayload,
    Message,
    Part,
    SendMessageConfiguration,
    SendMessageRequest,
    SendMessageResponse,
)

TIMEOUT_SEC = 10
A2A_VERSION = "1.0"


class A2AError(Exception):
    """A worker could not be reached or answered something unusable."""


def _headers(token: str | None) -> dict[str, str]:
    headers = {"A2A-Version": A2A_VERSION}
    if token is not None:
        headers["X-Agent-Token"] = token
    return headers


def _call(method: str, url: str, token: str | None, **kwargs) -> dict:
    try:
        response = httpx.request(method, url, headers=_headers(token), timeout=TIMEOUT_SEC,
                                 **kwargs)
    except httpx.HTTPError as exc:
        raise A2AError(f"worker at {url} not reachable: {exc}") from exc
    if response.status_code == 401:
        raise A2AError(f"worker at {url} refused the AGENT_TOKEN (401)")
    if response.status_code >= 400:
        raise A2AError(f"worker at {url} answered {response.status_code}: {response.text}")
    try:
        return response.json()
    except ValueError as exc:
        raise A2AError(f"worker at {url} did not answer with JSON") from exc


def get_agent_card(url: str) -> AgentCard:
    data = _call("GET", f"{url}/.well-known/agent-card.json", None)
    try:
        return AgentCard.model_validate(data)
    except ValidationError as exc:
        raise A2AError(f"bad agent card from {url}: {exc}") from exc


def send_task(url: str, payload: DapTaskPayload, token: str) -> A2ATask:
    request = SendMessageRequest(
        message=Message(
            message_id=str(uuid.uuid4()),
            role="ROLE_USER",
            context_id=payload.project_id,
            parts=[Part(text=payload.title),
                   Part(data=payload.model_dump(mode="json"), media_type="application/json")],
        ),
        configuration=SendMessageConfiguration(return_immediately=True),
    )
    data = _call("POST", f"{url}/message:send", token, json=request.to_wire())
    try:
        return SendMessageResponse.model_validate(data).task
    except ValidationError as exc:
        raise A2AError(f"bad message:send answer from {url}: {exc}") from exc


def get_task(url: str, remote_id: str, token: str) -> A2ATask:
    data = _call("GET", f"{url}/tasks/{remote_id}", token)
    try:
        return A2ATask.model_validate(data)
    except ValidationError as exc:
        raise A2AError(f"bad task answer from {url}: {exc}") from exc


def cancel_task(url: str, remote_id: str, token: str) -> None:
    """A2A CancelTask: ask the worker to stop the task at its next check.

    Best effort: a problem raises A2AError; the master's own cancel already
    marked the task failed, so the caller may ignore it.
    """
    _call("POST", f"{url}/tasks/{remote_id}:cancel", token)
