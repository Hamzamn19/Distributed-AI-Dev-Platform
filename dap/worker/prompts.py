"""Prompts the worker sends to its local model, one per task type.

Owner: Eray - Sprint 3.

The model gets the requirement, its task, the template file(s) it must fill
(templates/webapp/ in this repository), the files of the tasks it depends on,
and the exact answer format, plain text blocks instead of JSON, so the code is
written as it is saved (small models break code they must escape inside JSON):

    SUMMARY: one sentence
    === FILE: backend/database.py ===
    ...the whole file...
    === END FILE ===

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
        "EVERY table, plus one function per business rule or action of the requirement. "
        "The search of list_<things> must really filter a text column (LIKE ? with "
        "f'%{search}%'): searching a stored value finds it, a search that matches "
        "nothing answers an empty list."
    ),
    TaskType.BACKEND: (
        "Write the FastAPI routes under /api for every table of backend/database.py: list "
        "with search, get, create, update, delete, one route per action of the requirement "
        "and GET /api/stats. Pass the ?search= query parameter of the list routes on to the "
        "list function (def list_<things>(search: str | None = None)). Validate input with "
        "pydantic Field limits. Call only functions that backend/database.py really "
        "defines, with their exact parameters."
    ),
    TaskType.FRONTEND: (
        "Write a clear, modern one-page interface in plain HTML and JavaScript (no build "
        "step, no framework): a dashboard with counts, then one section per record type "
        "with a search box, a table with Edit and Delete buttons, and a form to add and "
        "edit, plus buttons for the actions of the requirement. Use the ready CSS classes "
        "and the helpers of lib.js; wire every search box with wireSearch(...) so it calls "
        "the list route with ?search=...; call only the /api routes of backend/main.py."
    ),
    TaskType.TESTING: (
        "Write pytest tests with the ready TestClient. The master already tries list, "
        "create, get, update and delete of every record itself, so test what only the "
        "requirement says: one short create-and-list test per record type, then one test "
        "per business rule (a broken rule answers 400) and per action of the requirement. "
        "Use only the routes and fields that backend/main.py really has."
    ),
    TaskType.REVISION: (
        "The application is already built and works. A follow-up request from the user "
        "asks for a change on top of it. Change as little as possible: keep every table, "
        "function name, route, element id and test the other agents wrote, unless the "
        "request itself asks to change them, and make the requested change work with "
        "them. Write ONLY the files the request actually changes, complete with the "
        "change; the files you do not write stay as they are."
    ),
}

FILE_START = "=== FILE: {path} ==="
FILE_END = "=== END FILE ==="

ANSWER_FORMAT_HEAD = (
    "Answer in exactly this format, with nothing before or after it:\n"
    "SUMMARY: one sentence about what you wrote\n"
    f"{FILE_START.format(path='<one of the allowed paths>')}\n"
    "<the whole file, exactly as it is saved>\n"
    f"{FILE_END}"
)
ANSWER_FORMAT = f"{ANSWER_FORMAT_HEAD}\nWrite one FILE block for every allowed path."


def template_text(path: str) -> str:
    """The template of one target file, or an empty string when there is none."""
    file = TEMPLATE_DIR / path
    return file.read_text(encoding="utf-8") if file.is_file() else ""


def build_messages(payload: DapTaskPayload) -> list[dict]:
    allowed = ", ".join(payload.target_files)
    # A revision task starts from the files the agents already wrote, not from the
    # template: the templates would only tempt the model to start over.
    revision = payload.type == TaskType.REVISION
    answer_format = (
        "Write one FILE block for each file you change, at least one."
        if revision else
        "Write one FILE block for every allowed path."
    )
    system = (
        f"You are the {payload.type.value} developer in a team of AI agents that builds "
        "one web application together. Each agent writes only its own files.\n"
        f"{GUIDE.get(payload.type, 'Write the files of your task.')}\n"
        f"You may write only these files: {allowed}.\n"
        + ("The task description carries the follow-up request: apply exactly that "
           "change, and keep the rest of the application as it is.\n"
           if revision else
           "The task description is a short summary: your files must cover every record, "
           "field, rule and action of the whole requirement for your part. Write every "
           "one of your files completely.\n")
        + "Rules for the files:\n"
        + ("- Start from the current files below: change only what the request needs "
           "and keep the rest exactly as it is. Do not rewrite a file that the request "
           "does not touch.\n"
           if revision else
           "- Start from the template: keep its import lines, the parts it marks as ready or "
           "required (for example the last line of backend/main.py), and follow its comments.\n")
        + "- Use exactly the function names, routes, fields and element ids of the files you "
        "get from the other agents; do not invent other names.\n"
        "- Write complete, working, modern code for the whole requirement: no placeholders, "
        "no TODO, no example code left over.\n"
        "- Inside a FILE block write plain source code: no Markdown, no ``` fences, no "
        "JSON, no escaping.\n"
        "- Do not explain and do not plan in text: answer at once with the SUMMARY line "
        "and the FILE blocks.\n"
        f"{ANSWER_FORMAT_HEAD}\n{answer_format}"
    )
    parts = [
        f"Requirement of the application:\n{payload.requirement_text.strip()}",
        f"Your task: {payload.title}\n{payload.description}",
    ]
    for path in payload.target_files:
        template = "" if revision else template_text(path)
        if template:
            parts.append(f"Template of {path} (fill it in):\n{template}")
    for file in payload.dependency_files:
        parts.append(f"Already written by another agent, {file.path}:\n{file.content}")
    parts.append(f"Allowed paths: {json.dumps(payload.target_files)}")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
