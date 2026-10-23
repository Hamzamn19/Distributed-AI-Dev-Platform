"""Prompts the worker sends to its local model, one per task type.

Owner: Eray - Sprint 3.

The model gets the requirement, its task, the template file(s) it must fill
(templates/webapp/ in this repository), the files of the tasks it depends on,
and the exact answer format:

    {"summary": "...", "files": [{"path": "...", "content": "..."}]}
"""

import json
from pathlib import Path

from dap.shared.enums import TaskType
from dap.shared.schemas import DapTaskPayload

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "webapp"

# What each task type is about; the template files carry the exact names.
GUIDE: dict[TaskType, str] = {
    TaskType.DATABASE: (
        "Write the SQLite storage of the application in Python (sqlite3 module only): "
        "create the tables the requirement needs and simple functions to add, list, "
        "update and delete records."
    ),
    TaskType.BACKEND: (
        "Write the FastAPI application: JSON routes under /api that use the functions "
        "of backend/database.py, and serve the frontend/ folder at /."
    ),
    TaskType.FRONTEND: (
        "Write the web pages in plain HTML and JavaScript (no build step, no "
        "framework): show the data and forms that call the /api routes with fetch()."
    ),
    TaskType.TESTING: (
        "Write pytest tests for the backend with fastapi.testclient.TestClient: call "
        "the /api routes and check the answers."
    ),
}

ANSWER_FORMAT = (
    'Answer with JSON only, exactly in this shape:\n'
    '{"summary": "one sentence about what you wrote", '
    '"files": [{"path": "<one of the allowed paths>", "content": "<the whole file>"}]}'
)


def template_text(path: str) -> str:
    """The template of one target file, or an empty string when there is none."""
    file = TEMPLATE_DIR / path
    return file.read_text(encoding="utf-8") if file.is_file() else ""


def build_messages(payload: DapTaskPayload) -> list[dict]:
    allowed = ", ".join(payload.target_files)
    system = (
        f"You are the {payload.type.value} developer in a team of AI agents that builds "
        "one small web application together. Each agent writes only its own files.\n"
        f"{GUIDE.get(payload.type, 'Write the files of your task.')}\n"
        f"You may write only these files: {allowed}. Write every one of them completely.\n"
        "Rules for the files:\n"
        "- Start from the template: keep its import lines and every line it marks as "
        "required (for example the last line of backend/main.py), and fill in the rest.\n"
        "- Use exactly the function names, routes and element ids of the files you get "
        "from the other agents; do not invent other names.\n"
        '- "content" is the whole file as plain source code: no Markdown, no ``` fences.\n'
        "- Keep the names that the template comments and the other files rely on.\n"
        f"{ANSWER_FORMAT}"
    )
    parts = [
        f"Requirement of the application:\n{payload.requirement_text.strip()}",
        f"Your task: {payload.title}\n{payload.description}",
    ]
    for path in payload.target_files:
        template = template_text(path)
        if template:
            parts.append(f"Template of {path} (fill it in):\n{template}")
    for file in payload.dependency_files:
        parts.append(f"Already written by another agent, {file.path}:\n{file.content}")
    parts.append(f"Allowed paths: {json.dumps(payload.target_files)}")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
