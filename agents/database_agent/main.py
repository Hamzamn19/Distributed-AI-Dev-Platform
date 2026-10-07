"""Master/API client -> FastAPI -> Ollama -> schema text."""

import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import ollama_client
from .prompts import SYSTEM_PROMPT, build_prompt

app = FastAPI(title="Database Agent", version="0.1.0")
generation_lock = asyncio.Lock()


class TaskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    task_type: Literal["database_design"]
    description: str = Field(min_length=1, max_length=4000)


class TaskResponse(BaseModel):
    agent: str = "database-agent"
    status: str = "completed"
    model: str
    task_type: str
    result: str


@app.get("/health")
async def health():
    if not await ollama_client.model_available():
        raise HTTPException(503, detail={
            "agent": "database-agent", "status": "unavailable", "model": ollama_client.MODEL,
            "message": "Start Ollama and install the configured model.",
        })
    return {"agent": "database-agent", "status": "available", "model": ollama_client.MODEL}


@app.post("/task", response_model=TaskResponse)
async def task(request: TaskRequest):
    # Fail quickly if busy instead of building an unbounded queue on the laptop.
    if generation_lock.locked():
        raise HTTPException(429, "Database Agent is busy. Retry when the current task finishes.")
    async with generation_lock:
        try:
            result = await ollama_client.generate(build_prompt(request.description), SYSTEM_PROMPT)
        except ollama_client.OllamaError as exc:
            raise HTTPException(exc.status_code, str(exc)) from exc
    return TaskResponse(model=ollama_client.MODEL, task_type=request.task_type, result=result)
