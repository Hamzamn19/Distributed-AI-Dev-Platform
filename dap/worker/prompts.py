"""Prompts the worker sends to its local model, one per task type.

Owner: Eray - Sprint 3.

The model gets the requirement, its task, the template file(s) it must fill
(templates/webapp/ in this repository), the files of the tasks it depends on,
and the exact answer format:

    {"summary": "...", "files": [{"path": "...", "content": "..."}]}

The prompts are written for any requirement: the records, fields and rules come
from the requirement and the task description, never from here.
"""

import json
from pathlib import Path

from dap.shared.enums import TaskType
from dap.shared.schemas import DapTaskPayload

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "webapp"

# What each task type is about; the template files carry the exact names and rules.
GUIDE: dict[TaskType, str] = {
    TaskType.DATABASE: (
        "Write the SQLite storage in Python (sqlite3 through the helpers of backend/db.py). "
        "Find every kind of record in the requirement (its nouns: people, things, events) "
        "with its fields and links; create one table per kind with sensible constraints "
        "and sample data; write all five list_/get_/add_/update_/delete_ functions for "
        "EVERY table, plus one function per business rule or action of the requirement."
    ),
    TaskType.BACKEND: (
        "Write the FastAPI routes under /api for every table of backend/database.py: list "
        "with search, get, create, update, delete, one route per action of the requirement "
        "and GET /api/stats. Validate input with pydantic Field limits. Call only functions "
        "that backend/database.py really defines, with their exact parameters."
    ),
    TaskType.FRONTEND: (
        "Write a clear, modern one-page interface in plain HTML and JavaScript (no build "
        "step, no framework): a dashboard with counts, then one section per record type "
        "with a search box, a table with Edit and Delete buttons, and a form to add and "
        "edit, plus buttons for the actions of the requirement. Use the ready CSS classes "
        "and the helpers of lib.js; call only the /api routes of backend/main.py."
    ),
    TaskType.TESTING: (
        "Write pytest tests with the ready TestClient for every route of backend/main.py: "
        "create, list, search, get, missing id (404), update, delete, invalid data (422), "
        "and one test per business rule (400). Use only the routes and fields that "
        "backend/main.py really has."
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
        "one web application together. Each agent writes only its own files.\n"
        f"{GUIDE.get(payload.type, 'Write the files of your task.')}\n"
        f"You may write only these files: {allowed}. Write every one of them completely.\n"
        "Rules for the files:\n"
        "- Start from the template: keep its import lines, the parts it marks as ready or "
        "required (for example the last line of backend/main.py), and follow its comments.\n"
        "- Use exactly the function names, routes, fields and element ids of the files you "
        "get from the other agents; do not invent other names.\n"
        "- Write complete, working, modern code for the whole requirement: no placeholders, "
        "no TODO, no example code left over.\n"
        '- "content" is the whole file as plain source code: no Markdown, no ``` fences.\n'
        "- Do not explain and do not plan in text: answer at once with the JSON.\n"
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
