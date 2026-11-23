"""Task breakdown: turns a requirement text into tasks with the local LLM.

Owner: Baran - card S1-06.

    decompose(requirement_text: str) -> list[TaskCreate]

The model is asked for:

    {"records": ["customers", "orders"],
     "tasks": [{"title", "description", "type"}]}

Rules:
- Exactly one task per Sprint 1 type, always in the order database -> backend
  -> frontend -> testing. The order and the dependencies between the tasks are
  fixed here (each task waits for the one before it; testing also waits for
  the backend); whatever the model says about order or depends_on is ignored.
  If a type appears twice, the first one is used.
- "records" are the table names of the application: at least 1, at most 12
  (MAX_RECORDS). An answer without a usable "records" list is broken. The line
  "Records: customers, orders. This task covers all of them." is added to the
  end of every description.
- A broken answer is retried once; after that a fixed template is returned
  (it has no records, so no Records line: the table names are unknown).
- When the model cannot be reached, chat() raises RuntimeError. It is not
  caught here: /decompose sets the project to "failed" and answers 502.
"""

import json
import logging
import re
import uuid

from dap.shared.enums import TaskType
from dap.shared.llm_client import chat
from dap.shared.schemas import TaskCreate

logger = logging.getLogger(__name__)

ATTEMPTS = 2  # first answer + one retry
MAX_RECORDS = 12

# Fixed order of the tasks and what each one waits for.
TASK_ORDER = [TaskType.DATABASE, TaskType.BACKEND, TaskType.FRONTEND, TaskType.TESTING]
_DEPENDS_ON = {
    TaskType.DATABASE: [],
    TaskType.BACKEND: [TaskType.DATABASE],
    TaskType.FRONTEND: [TaskType.BACKEND],
    TaskType.TESTING: [TaskType.BACKEND, TaskType.FRONTEND],
}
_TYPE_NAMES = ", ".join(t.value for t in TASK_ORDER)

SYSTEM_PROMPT = f"""You are the Master Agent of a multi-agent software platform.
Break the user's software requirement into exactly {len(TASK_ORDER)} development tasks.

Rules:
- One task of each type: {_TYPE_NAMES}. No other types, no second task of a type.
- "records" lists the database table names of the application, in lowercase
  with underscores, for example "customers", "orders".
- Answer with JSON only, exactly in this shape:

{{
  "records": ["customers", "orders"],
  "tasks": [
    {{"title": "short title", "description": "what must be done",
      "type": "database"}}
  ]
}}"""

# Fallback when the model keeps answering with broken JSON: one task per type.
FALLBACK_TASKS = [
    {"type": "database", "title": "Design database schema",
     "description": "Define the tables and relations the application needs."},
    {"type": "backend", "title": "Build REST API",
     "description": "Implement the backend endpoints on top of the database."},
    {"type": "frontend", "title": "Build web pages",
     "description": "Create the user interface that calls the REST API."},
    {"type": "testing", "title": "Write tests",
     "description": "Test the API and the web pages."},
]


def _extract_json(text: str) -> dict:
    """Parse JSON from the model's answer, tolerating code fences or stray prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _table_names(data: dict) -> list[str]:
    """The table names from "records" (1 to MAX_RECORDS); otherwise ValueError.

    Anything that is not a plain snake_case name is dropped, repeats are
    removed; what is left must still be 1 to MAX_RECORDS names.
    """
    raw = data.get("records")
    if not isinstance(raw, list):
        raise ValueError('answer has no "records" list')
    names = []
    for item in raw:
        name = str(item).strip().lower()
        if re.fullmatch(r"[a-z_][a-z0-9_]*", name) and name not in names:
            names.append(name)
    if not names:
        raise ValueError('"records" has no usable table name')
    if len(names) > MAX_RECORDS:
        raise ValueError(f'"records" has {len(names)} names, at most {MAX_RECORDS} are allowed')
    return names


def _to_task_creates(data: object, *, with_records: bool = True) -> list[TaskCreate]:
    """Validate the model's answer and turn it into TaskCreate objects.

    Raises ValueError when the answer cannot be used.
    """
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError('answer has no "tasks" list')

    allowed = {t.value for t in TASK_ORDER}
    first_of_type: dict[str, dict] = {}
    for index, raw in enumerate(data["tasks"], start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"task {index} is not an object")
        task_type = str(raw.get("type") or "").strip().lower()
        if task_type not in allowed:
            raise ValueError(f"task {index} has type {task_type!r}, expected one of {_TYPE_NAMES}")
        if not str(raw.get("title") or "").strip():
            raise ValueError(f"task {index} has no title")
        first_of_type.setdefault(task_type, raw)

    missing = allowed - set(first_of_type)
    if missing:
        raise ValueError(f"missing task types: {', '.join(sorted(missing))}")

    records_line = ""
    if with_records:
        tables = _table_names(data)
        records_line = f"\n\nRecords: {', '.join(tables)}. This task covers all of them."
    ids = {task_type: str(uuid.uuid4()) for task_type in TASK_ORDER}
    tasks = []
    for task_type in TASK_ORDER:
        raw = first_of_type[task_type.value]
        title = str(raw["title"]).strip()
        description = str(raw.get("description") or title).strip()
        description += records_line
        tasks.append(TaskCreate(
            id=ids[task_type],
            title=title,
            description=description,
            type=task_type,
            depends_on=[ids[dep] for dep in _DEPENDS_ON[task_type]],
        ))
    return tasks


def decompose(requirement_text: str) -> list[TaskCreate]:
    """Break a requirement into four tasks: database, backend, frontend, testing (in that order)."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Requirement:\n{requirement_text.strip()}"},
    ]
    for attempt in range(1, ATTEMPTS + 1):
        answer = chat(messages, json_mode=True)  # RuntimeError when the model is down
        try:
            return _to_task_creates(_extract_json(answer.text))
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("Decomposition attempt %d/%d unusable: %s", attempt, ATTEMPTS, exc)
            messages.append({"role": "assistant", "content": answer.text})
            messages.append({
                "role": "user",
                "content": f"Your answer was invalid ({exc}). "
                           "Answer again with JSON only, following the shape exactly.",
            })
    logger.warning("Using the fixed fallback template (%d tasks)", len(FALLBACK_TASKS))
    return _to_task_creates({"tasks": FALLBACK_TASKS}, with_records=False)
