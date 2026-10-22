"""Runs the tasks the master sends, one at a time, in the order received.

Owner: Eray - Sprint 3.

For each task: build the prompt (prompts.py), ask the local model with
chat(json_mode=True), read {"summary", "files"} from the answer and check that
every file is one of the task's target_files. Any error makes the task
TASK_STATE_FAILED with a message that explains it.

With LLM_MOCK=1 no model is asked: every target file gets a fixed, working
content (MOCK_FILES), so the whole flow can be tested without Ollama.
"""

import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from dap.shared.enums import A2ATaskState, AgentStatus
from dap.shared.llm_client import chat
from dap.shared.schemas import (
    A2ATask,
    Artifact,
    DapTaskOutput,
    DapTaskPayload,
    GeneratedFile,
    Message,
    Part,
    TaskStatusA2A,
)
from dap.worker import prompts

logger = logging.getLogger("dap.worker")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ running one task


def _extract_json(text: str) -> dict:
    """Parse the model's JSON answer, tolerating code fences or stray prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("the model did not answer with JSON") from None
        return json.loads(text[start : end + 1])


def check_output(payload: DapTaskPayload, output: DapTaskOutput) -> None:
    """Every target file is written, and nothing else. Raises ValueError."""
    allowed = set(payload.target_files)
    written = [file.path for file in output.files]
    outside = [path for path in written if path not in allowed]
    if outside:
        raise ValueError(f"file outside target_files: {', '.join(outside)}")
    missing = [path for path in payload.target_files if path not in written]
    if missing:
        raise ValueError(f"the model did not write: {', '.join(missing)}")


def execute(payload: DapTaskPayload) -> DapTaskOutput:
    """Do one task with the local model (or the mock) and return its files."""
    if os.getenv("LLM_MOCK", "0").strip() == "1":
        files = [GeneratedFile(path=path, content=MOCK_FILES.get(path, f"# {path}\n"))
                 for path in payload.target_files]
        return DapTaskOutput(summary=f"Mock output for: {payload.title}", files=files)

    answer = chat(prompts.build_messages(payload), json_mode=True)  # RuntimeError: model down
    data = _extract_json(answer.text)
    files = [GeneratedFile(path=str(f.get("path", "")), content=str(f.get("content", "")))
             for f in data.get("files", []) if isinstance(f, dict)]
    return DapTaskOutput(
        summary=str(data.get("summary") or payload.title),
        files=files,
        prompt_tokens=answer.prompt_tokens,
        completion_tokens=answer.completion_tokens,
        duration_ms=answer.duration_ms,
    )


# ------------------------------------------------------------ the queue of A2A tasks


class Executor:
    """In-memory A2A task store plus one thread that runs the tasks in order."""

    def __init__(self, run: Callable[[DapTaskPayload], DapTaskOutput] = execute):
        self._run = run
        self._tasks: dict[str, A2ATask] = {}
        self._payloads: dict[str, DapTaskPayload] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._current: str | None = None
        threading.Thread(target=self._loop, name="executor", daemon=True).start()

    def submit(self, payload: DapTaskPayload, context_id: str | None) -> A2ATask:
        """Store a new task as SUBMITTED and queue it; returns at once."""
        task = A2ATask(
            id=str(uuid.uuid4()),
            context_id=context_id,
            status=TaskStatusA2A(state=A2ATaskState.SUBMITTED, timestamp=_now()),
        )
        with self._lock:
            self._tasks[task.id] = task
            self._payloads[task.id] = payload
        self._queue.put(task.id)
        logger.info("Queued task %s (%s: %s)", task.id, payload.type.value, payload.title)
        return task.model_copy(deep=True)

    def get(self, task_id: str) -> A2ATask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def status(self) -> tuple[AgentStatus, str | None]:
        """For the heartbeat: busy with the master's task id while work is waiting."""
        with self._lock:
            if self._current is not None:
                return AgentStatus.BUSY, self._payloads[self._current].task_id
        if not self._queue.empty():
            return AgentStatus.BUSY, None
        return AgentStatus.IDLE, None

    def _set(self, task_id: str, state: A2ATaskState, *, error: str | None = None,
             output: DapTaskOutput | None = None) -> None:
        with self._lock:
            task = self._tasks[task_id]
            message = None
            if error is not None:
                message = Message(message_id=str(uuid.uuid4()), role="ROLE_AGENT",
                                  parts=[Part(text=error)])
            task.status = TaskStatusA2A(state=state, message=message, timestamp=_now())
            if output is not None:
                task.artifacts = [Artifact(
                    artifact_id=str(uuid.uuid4()), name="result",
                    parts=[Part(data=output.model_dump(mode="json"),
                                media_type="application/json")],
                )]

    def _loop(self) -> None:
        while True:
            task_id = self._queue.get()
            payload = self._payloads[task_id]
            with self._lock:
                self._current = task_id
            self._set(task_id, A2ATaskState.WORKING)
            logger.info("Working on %s (%s)", task_id, payload.title)
            start = time.perf_counter()
            try:
                output = self._run(payload)
                check_output(payload, output)
                if not output.duration_ms:
                    output.duration_ms = int((time.perf_counter() - start) * 1000)
                self._set(task_id, A2ATaskState.COMPLETED, output=output)
                logger.info("Completed %s: %s", task_id, output.summary)
            except Exception as exc:  # the model, the JSON or the files: report, never crash
                self._set(task_id, A2ATaskState.FAILED, error=f"{type(exc).__name__}: {exc}")
                logger.error("Task %s failed: %s", task_id, exc)
            finally:
                with self._lock:
                    self._current = None


# ------------------------------------------- LLM_MOCK=1: a small app that really runs
# One working "items" application. Phase 5 checks that these files, written into
# the template, start with `uvicorn backend.main:app` and answer on /api/items.

MOCK_FILES: dict[str, str] = {
    "backend/database.py": '''"""SQLite storage (mock output): one table of items."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "app.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
        )


def list_items() -> list[dict]:
    with connect() as connection:
        return [dict(row) for row in connection.execute("SELECT id, name FROM items ORDER BY id")]


def add_item(name: str) -> dict:
    with connect() as connection:
        cursor = connection.execute("INSERT INTO items (name) VALUES (?)", (name,))
        return {"id": cursor.lastrowid, "name": name}
''',
    "backend/main.py": '''"""FastAPI routes (mock output). Run from the app folder: uvicorn backend.main:app"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import database

app = FastAPI(title="Generated app")
database.init_db()


class ItemIn(BaseModel):
    name: str


@app.get("/api/items")
def list_items() -> list[dict]:
    return database.list_items()


@app.post("/api/items", status_code=201)
def add_item(item: ItemIn) -> dict:
    return database.add_item(item.name)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
''',
    "frontend/index.html": '''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Generated app</title></head>
<body>
  <h1>Items</h1>
  <form id="add"><input id="name" placeholder="Name" required> <button>Add</button></form>
  <ul id="items"></ul>
  <script src="app.js"></script>
</body>
</html>
''',
    "frontend/app.js": '''// Mock output: lists the items and adds new ones through the /api routes.
async function load() {
  const items = await (await fetch("/api/items")).json();
  document.getElementById("items").innerHTML = items.map((i) => `<li>${i.name}</li>`).join("");
}

document.getElementById("add").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("name");
  await fetch("/api/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name.value }),
  });
  name.value = "";
  load();
});

load();
''',
    "tests/test_app.py": '''"""Tests of the generated backend (mock output). Run from the app folder: python -m pytest"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


def test_add_and_list_items():
    created = client.post("/api/items", json={"name": "First"})
    assert created.status_code == 201
    assert any(item["name"] == "First" for item in client.get("/api/items").json())
''',
}
