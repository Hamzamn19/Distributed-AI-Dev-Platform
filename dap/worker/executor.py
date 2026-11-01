"""Run one task with the local model and build its TaskResult (card S2-03).

Owner: Eray. The model is asked for one JSON object:

    {"summary": "one or two sentences", "files": [{"path": "app/main.py", "content": "..."}]}

`path` is relative; the master saves the files under
workspace/<project_id>/<run_id>/ (dap/master/db/workspace.py checks them again).
Every path is put under a folder named after the task type (backend/, frontend/,
...) unless it already starts with it, so two tasks of one run do not write the
same file.
A broken answer is asked again once; after that the result is a failure and
the master decides about a retry (contract section 6).
"""

import json
import re
import time

from dap.shared.llm_client import chat
from dap.shared.schemas import GeneratedFile, Task, TaskResult

REQUIREMENT_LIMIT = 3000  # characters; keeps the prompt inside a 4096-token window
ATTEMPTS = 2  # first answer + one retry when the answer is not usable

TYPE_GUIDE = {
    "requirements_analysis": "Write the analysis as Markdown (for example docs/analysis.md).",
    "frontend": "Write plain HTML, CSS and JavaScript files (for example frontend/index.html).",
    "backend": "Write Python with FastAPI (for example backend/main.py).",
    "database": "Write the SQL schema for SQLite (for example database/schema.sql).",
    "testing": "Write pytest test files (for example tests/test_app.py).",
    "code_review": "Write the review as Markdown (for example review/notes.md).",
    "integration": "Write the glue code or configuration needed to connect the parts.",
    "documentation": "Write the documentation as Markdown (for example README.md).",
}

SYSTEM_PROMPT = (
    "You are a software engineer agent in a team that builds a small web application. "
    "Do only the task you are given. Answer with one JSON object and nothing else, in this shape: "
    '{"summary": "one or two sentences about what you made", '
    '"files": [{"path": "relative/path.ext", "content": "the full file content"}]}. '
    "Paths are relative, use forward slashes, and never start with / or contain ..; "
    "give at least one file and keep files short and complete."
)

_BAD_CHARS = set('<>:"|?*')


class UnusableAnswer(ValueError):
    pass


def build_messages(task: Task, requirement_text: str | None) -> list[dict]:
    guide = TYPE_GUIDE.get(str(task.type), "")
    parts = [f"Task type: {task.type}", f"Task title: {task.title}", f"Task description: {task.description}"]
    if guide:
        parts.append(f"Output: {guide}")
    if requirement_text:
        parts.append("Project requirement (for context):\n" + requirement_text[:REQUIREMENT_LIMIT])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def clean_path(value: str) -> str | None:
    """A safe relative path with forward slashes, or None when it cannot be one."""
    path = str(value).strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    if not path or path.startswith("/") or any(
        part in ("", ".", "..") or any(c in _BAD_CHARS or ord(c) < 32 for c in part) for part in parts
    ):
        return None
    return path


def parse_answer(text: str, folder: str = "") -> tuple[str, list[GeneratedFile]]:
    """Read the model's JSON answer; raise UnusableAnswer when it has no usable file.

    `folder` (the task type) is put in front of every path that does not start with it.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)  # JSON wrapped in other text
        if not match:
            raise UnusableAnswer("the answer is not JSON")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            raise UnusableAnswer("the answer is not JSON")
    if not isinstance(data, dict):
        raise UnusableAnswer("the answer is not a JSON object")

    files: list[GeneratedFile] = []
    seen: set[str] = set()
    for item in data.get("files") or []:
        if not isinstance(item, dict) or not isinstance(item.get("content"), str):
            continue
        path = clean_path(item.get("path", ""))
        if path is not None and folder and not path.casefold().startswith(folder.casefold() + "/"):
            path = f"{folder}/{path}"
        if path is None or path.casefold() in seen:
            continue
        seen.add(path.casefold())
        files.append(GeneratedFile(path=path, content=item["content"]))
    if not files:
        raise UnusableAnswer("the answer has no usable file")
    summary = str(data.get("summary") or f"{len(files)} file(s) generated").strip()
    return summary, files


def execute_task(task: Task, agent_id: str, requirement_text: str | None = None) -> TaskResult:
    """Ask the local model to do the task; never raises for a model problem."""
    messages = build_messages(task, requirement_text)
    tokens = 0
    start = time.perf_counter()
    error = "no answer"
    for _ in range(ATTEMPTS):
        try:
            reply = chat(messages, json_mode=True)
        except RuntimeError as exc:  # model server down: llm_client already retried
            error = str(exc)
            break
        tokens += reply.prompt_tokens + reply.completion_tokens
        try:
            summary, files = parse_answer(reply.text, str(task.type))
        except UnusableAnswer as exc:
            error = f"model answer unusable: {exc}"
            continue
        return TaskResult(
            task_id=task.id, agent_id=agent_id, success=True, summary=summary, files=files,
            duration_ms=int((time.perf_counter() - start) * 1000), tokens_used=tokens,
        )
    return TaskResult(
        task_id=task.id, agent_id=agent_id, success=False, summary="Task failed", files=[],
        error=error, duration_ms=int((time.perf_counter() - start) * 1000), tokens_used=tokens,
    )
