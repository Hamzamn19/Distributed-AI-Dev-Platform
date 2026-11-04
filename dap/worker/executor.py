"""Run one task with the local model and build its TaskResult (cards S2-03, S3).

Owner: Eray. From Sprint 3 a task fills one fixed file of the template
(contract 12.2):

    database  -> backend/database.py
    backend   -> backend/main.py
    frontend  -> frontend/index.html
    testing   -> tests/test_app.py

The prompt carries the task (its description ends with the master's
"Records: ..." line, contract 12.3), the template version of the target file
from templates/webapp/ (its header comment says what goes in), and the files
of the tasks this task depends on (GET /tasks/{id}/inputs). The model answers
one JSON object:

    {"summary": "one or two sentences", "content": "the full file"}

Only the target file is sent to the master. An answer without it is asked
again once; after that the result is a failure and the master decides about a
retry (contract section 6).
"""

import json
import re
import time
from pathlib import Path

from dap.shared.llm_client import chat
from dap.shared.schemas import GeneratedFile, Task, TaskResult

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "webapp"

TARGET_FILE = {
    "database": "backend/database.py",
    "backend": "backend/main.py",
    "frontend": "frontend/index.html",
    "testing": "tests/test_app.py",
}

REQUIREMENT_LIMIT = 3000  # characters; keeps the prompt inside a small context window
INPUT_LIMIT = 6000  # characters per input file
ATTEMPTS = 2  # first answer + one retry when the answer is not usable

SYSTEM_PROMPT = (
    "You are a software engineer agent in a team that fills in a fixed web application "
    "template. You write exactly one file: the target file named in the task. Keep the "
    "structure and the rules of its template version, replace its example with the "
    "project's own tables and fields, and use the names from the files you are given. "
    "Answer with one JSON object and nothing else: "
    '{"summary": "one or two sentences about what you wrote", '
    '"content": "the complete content of the target file"}.'
)


class UnusableAnswer(ValueError):
    pass


def target_file(task: Task) -> str | None:
    return TARGET_FILE.get(str(task.type))


def template_text(path: str, template_dir: Path = TEMPLATE_DIR) -> str | None:
    """The template version of a target file, or None when the template has none yet."""
    file = template_dir / path
    return file.read_text(encoding="utf-8") if file.is_file() else None


def build_messages(task: Task, target: str, requirement_text: str | None = None,
                   inputs: list[GeneratedFile] | None = None,
                   template_dir: Path = TEMPLATE_DIR) -> list[dict]:
    parts = [
        f"Target file: {target}",
        f"Task type: {task.type}",
        f"Task title: {task.title}",
        f"Task description: {task.description}",
    ]
    if requirement_text:
        parts.append("Project requirement:\n" + requirement_text[:REQUIREMENT_LIMIT])
    for item in inputs or []:
        parts.append(f"File {item.path} (written by an earlier task; use its names):\n"
                     + item.content[:INPUT_LIMIT])
    template = template_text(target, template_dir)
    if template:
        parts.append(f"Template version of {target} (replace its example, keep its rules):\n"
                     + template)
    parts.append(f'Answer with {{"summary": "...", "content": "<the complete {target}>"}}.')
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def _load_json(text: str) -> dict:
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
    return data


def _strip_fence(content: str) -> str:
    """Drop a ```lang ... ``` wrapper that some models put around the file."""
    match = re.fullmatch(r"\s*```[\w.+-]*\n(.*?)\n?```\s*", content, re.DOTALL)
    return match.group(1) if match else content


def parse_answer(text: str, target: str) -> tuple[str, GeneratedFile]:
    """The summary and the target file from the model's JSON answer.

    Accepted: {"content": ...}, or the Sprint 2 shape {"files": [{"path", "content"}]}
    with a file whose path, or file name, is the target's. Any other file is dropped.
    """
    data = _load_json(text)
    content = data.get("content")
    if not isinstance(content, str):
        content = None
        name = target.rsplit("/", 1)[-1]
        for item in data.get("files") or []:
            if not isinstance(item, dict) or not isinstance(item.get("content"), str):
                continue
            path = str(item.get("path", "")).strip().replace("\\", "/").lstrip("./")
            if path == target or path.rsplit("/", 1)[-1] == name:
                content = item["content"]
                break
    if content is None or not content.strip():
        raise UnusableAnswer(f"the answer has no content for {target}")
    summary = str(data.get("summary") or f"Wrote {target}").strip()
    return summary, GeneratedFile(path=target, content=_strip_fence(content))


def execute_task(task: Task, agent_id: str, requirement_text: str | None = None,
                 inputs: list[GeneratedFile] | None = None) -> TaskResult:
    """Ask the local model to fill the task's target file; never raises for a model problem."""
    start = time.perf_counter()
    target = target_file(task)
    if target is None:
        return TaskResult(
            task_id=task.id, agent_id=agent_id, success=False, summary="Task failed", files=[],
            error=f"no target file for task type {task.type} (contract 12.2)",
            duration_ms=0, tokens_used=0,
        )

    messages = build_messages(task, target, requirement_text, inputs)
    tokens = 0
    error = "no answer"
    for _ in range(ATTEMPTS):
        try:
            reply = chat(messages, json_mode=True)
        except RuntimeError as exc:  # model server down: llm_client already retried
            error = str(exc)
            break
        tokens += reply.prompt_tokens + reply.completion_tokens
        try:
            summary, file = parse_answer(reply.text, target)
        except UnusableAnswer as exc:
            error = f"model answer unusable: {exc}"
            continue
        return TaskResult(
            task_id=task.id, agent_id=agent_id, success=True, summary=summary, files=[file],
            duration_ms=int((time.perf_counter() - start) * 1000), tokens_used=tokens,
        )
    return TaskResult(
        task_id=task.id, agent_id=agent_id, success=False, summary="Task failed", files=[],
        error=error, duration_ms=int((time.perf_counter() - start) * 1000), tokens_used=tokens,
    )
