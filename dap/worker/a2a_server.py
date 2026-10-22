"""The worker's A2A server (A2A protocol v1.0, HTTP+JSON; contract section 13).

Owner: Eray - Sprint 3.

    GET  /.well-known/agent-card.json   who this agent is (no token)
    POST /message:send                  queue a task, answer {"task": Task} at once
    GET  /tasks/{id}                    the task's state and, when done, its files

Requests from the master carry X-Agent-Token (401 when wrong) and A2A-Version: 1.0.
Errors use the contract's {"detail": "..."}: unknown task 404, bad body 422.
"""

import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from dap import __version__
from dap.shared.schemas import (
    AgentCard,
    AgentInterface,
    AgentSkill,
    DapTaskPayload,
    SendMessageRequest,
    SendMessageResponse,
    first_data,
)
from dap.worker.config import WorkerSettings
from dap.worker.executor import Executor

JSON_TYPES = ("application/json", "application/a2a+json")


def agent_card(settings: WorkerSettings, public_url: str) -> AgentCard:
    role = settings.role_hint.value if settings.role_hint else "general"
    return AgentCard(
        name=settings.agent_id,
        description=f"DAP worker on {settings.agent_name} running {settings.model}",
        version=__version__,
        supported_interfaces=[AgentInterface(url=public_url)],
        skills=[AgentSkill(id=role, name=role, description=f"{role} tasks of a generated web app",
                           tags=[role])],
    )


def create_app(settings: WorkerSettings, executor: Executor, public_url: str) -> FastAPI:
    app = FastAPI(title=f"DAP worker {settings.agent_id}", version=__version__)

    def require_token(x_agent_token: str | None = Header(default=None)) -> None:
        if x_agent_token is None or not secrets.compare_digest(
            x_agent_token.encode(), settings.agent_token.encode()
        ):
            raise HTTPException(status_code=401, detail="Missing or wrong X-Agent-Token")

    @app.get("/.well-known/agent-card.json")
    def get_agent_card() -> JSONResponse:
        return JSONResponse(agent_card(settings, public_url).to_wire())

    @app.post("/message:send", dependencies=[Depends(require_token)])
    async def send_message(request: Request) -> JSONResponse:
        content_type = request.headers.get("content-type", "").split(";")[0].strip()
        if content_type not in JSON_TYPES:
            raise HTTPException(status_code=422, detail=f"Content-Type must be one of {JSON_TYPES}")
        try:
            body = SendMessageRequest.model_validate_json(await request.body())
            payload = DapTaskPayload.model_validate(first_data(body.message.parts))
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=f"Bad message: {exc.errors()[0]['msg']}")
        task = executor.submit(payload, body.message.context_id)
        return JSONResponse(SendMessageResponse(task=task).to_wire())

    @app.get("/tasks/{task_id}", dependencies=[Depends(require_token)])
    def get_task(task_id: str) -> JSONResponse:
        task = executor.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return JSONResponse(task.to_wire())

    return app
