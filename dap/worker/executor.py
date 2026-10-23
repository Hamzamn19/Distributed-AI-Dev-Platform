"""Runs the tasks the master sends, one at a time, in the order received.

Owner: Eray - Sprint 3.

For each task: build the prompt (prompts.py), ask the local model with
chat(json_mode=True), read {"summary", "files"} from the answer (Markdown code
fences around a file's content are removed) and check the files: exactly the
task's target_files, none empty, Python files without syntax errors, and every
Python file really loads (verify(): the template, the dependency files and the
new files are written to a temporary folder and each new .py file is run once).

Self-correction: when a check fails, the model gets the problem (for example
"NameError: name 'database' is not defined") and answers again, at most
FIX_ROUNDS times. Still wrong after that: TASK_STATE_FAILED with the problem.

With LLM_MOCK=1 no model is asked: every target file gets a fixed, working
content (MOCK_FILES), so the whole flow can be tested without Ollama.
MOCK_DELAY_SEC (default 0) makes a mock task take that long, so a demo can
show the agent as busy.
"""

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
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
    try:  # a plain JSON answer may itself contain ``` inside a file's content
        return json.loads(text)
    except json.JSONDecodeError:
        pass
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


_FENCE = re.compile(r"^\s*```[\w+.-]*[ \t]*\r?\n(.*?)\r?\n?```\s*$", re.DOTALL)


def clean_content(text: str) -> str:
    """Remove the Markdown code fence a model may wrap around a whole file."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def check_output(payload: DapTaskPayload, output: DapTaskOutput) -> None:
    """Exactly the target files, none empty, Python that compiles. Raises ValueError."""
    allowed = set(payload.target_files)
    written = [file.path for file in output.files]
    outside = [path for path in written if path not in allowed]
    if outside:
        raise ValueError(f"file outside target_files: {', '.join(outside)}")
    missing = [path for path in payload.target_files if path not in written]
    if missing:
        raise ValueError(f"the model did not write: {', '.join(missing)}")
    for file in output.files:
        if not file.content.strip():
            raise ValueError(f"empty file: {file.path}")
        if file.path.endswith(".py"):
            try:
                compile(file.content, file.path, "exec")
            except SyntaxError as exc:
                raise ValueError(f"syntax error in {file.path}, line {exc.lineno}: {exc.msg}") from None


FIX_ROUNDS = 2          # extra answers the model may give after a failed check
VERIFY_TIMEOUT_SEC = 60

# Runs one generated file once, from the application folder, as `python <file>` would.
_RUN_FILE = (
    "import runpy, sys; sys.path.insert(0, '.'); "
    "runpy.run_path(sys.argv[1], run_name='dap_check')"
)


def verify(payload: DapTaskPayload, output: DapTaskOutput) -> str | None:
    """Load every new Python file next to the template and the dependency files.

    Returns the problem as a short text (the last lines of the error), or None.
    """
    python_files = [f.path for f in output.files if f.path.endswith(".py")]
    if not python_files:
        return None
    with tempfile.TemporaryDirectory(prefix="dap-check-") as folder:
        root = Path(folder)
        if prompts.TEMPLATE_DIR.is_dir():
            shutil.copytree(prompts.TEMPLATE_DIR, root, dirs_exist_ok=True)
        for file in [*payload.dependency_files, *output.files]:
            target = root / file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file.content, encoding="utf-8")
        for path in python_files:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", _RUN_FILE, path], cwd=root,
                    capture_output=True, text=True, timeout=VERIFY_TIMEOUT_SEC)
            except subprocess.TimeoutExpired:
                return f"{path} did not finish loading within {VERIFY_TIMEOUT_SEC} s"
            if result.returncode != 0:
                lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
                return f"{path} fails when it is loaded:\n" + "\n".join(lines[-4:])
    return None


def _read_answer(text: str, payload: DapTaskPayload) -> DapTaskOutput:
    data = _extract_json(text)
    files = [GeneratedFile(path=str(f.get("path", "")),
                           content=clean_content(str(f.get("content", ""))))
             for f in data.get("files", []) if isinstance(f, dict)]
    return DapTaskOutput(summary=str(data.get("summary") or payload.title), files=files)


def execute(payload: DapTaskPayload) -> DapTaskOutput:
    """Do one task with the local model (or the mock) and return its files."""
    if os.getenv("LLM_MOCK", "0").strip() == "1":
        time.sleep(float(os.getenv("MOCK_DELAY_SEC", "0")))
        files = [GeneratedFile(path=path, content=MOCK_FILES.get(path, f"# {path}\n"))
                 for path in payload.target_files]
        return DapTaskOutput(summary=f"Mock output for: {payload.title}", files=files)

    messages = prompts.build_messages(payload)
    prompt_tokens = completion_tokens = duration_ms = 0
    problem = ""
    for round_number in range(1 + FIX_ROUNDS):
        answer = chat(messages, json_mode=True)  # RuntimeError: model down
        prompt_tokens += answer.prompt_tokens
        completion_tokens += answer.completion_tokens
        duration_ms += answer.duration_ms
        try:
            output = _read_answer(answer.text, payload)
            check_output(payload, output)
            problem = verify(payload, output) or ""
        except (ValueError, json.JSONDecodeError) as exc:
            problem = str(exc)
        if not problem:
            output.prompt_tokens, output.completion_tokens = prompt_tokens, completion_tokens
            output.duration_ms = duration_ms
            if round_number:
                output.summary += f" (corrected {round_number}x)"
            return output
        logger.warning("Task %s, answer %d: %s", payload.title, round_number + 1, problem)
        messages = [*messages, {"role": "assistant", "content": answer.text}, {
            "role": "user",
            "content": f"Your files have this problem:\n{problem}\n\nFix it. Answer again "
                       "with the complete corrected files, in the same JSON shape, with the "
                       "same paths and no Markdown fences.",
        }]
    raise ValueError(f"still wrong after {FIX_ROUNDS} corrections: {problem}")


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
