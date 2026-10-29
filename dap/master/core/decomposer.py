"""Task breakdown: turns a requirement text into tasks with the local LLM.

Owner: Baran - card S1-06.

    decompose(requirement_text: str) -> list[TaskCreate]

The model is asked for (member guide, agreement 2):

    {"tasks": [{"key", "title", "description", "type", "depends_on"}]}

"key" is a temporary name inside the answer. Every task gets a UUID4 here.

Rules (Sprint 3, contract section 12):
- Exactly one task of each Sprint 1 type (SPRINT1_TASK_TYPES); each fills fixed
  template files, so two tasks of one type would overwrite each other.
- The order and the dependencies are fixed here, whatever the model answered:
  database -> backend -> frontend -> testing (testing also depends on backend).
  The model writes the titles and descriptions for the requirement.
- A broken answer is retried once; after that a fixed template with one task
  per type is returned.
- When the model cannot be reached, chat() raises RuntimeError. It is not
  caught here: /decompose sets the project to "failed" and answers 502.
"""

import json
import logging
import re
import uuid

from dap.shared.enums import SPRINT1_TASK_TYPES, TaskType
from dap.shared.llm_client import chat
from dap.shared.schemas import TaskCreate

logger = logging.getLogger(__name__)

ATTEMPTS = 2  # first answer + one retry

# Fixed order and dependencies of the four Sprint 3 tasks (contract section 12).
ORDER = [TaskType.DATABASE, TaskType.BACKEND, TaskType.FRONTEND, TaskType.TESTING]
DEPENDS_ON: dict[TaskType, list[TaskType]] = {
    TaskType.DATABASE: [],
    TaskType.BACKEND: [TaskType.DATABASE],
    TaskType.FRONTEND: [TaskType.BACKEND],
    TaskType.TESTING: [TaskType.BACKEND, TaskType.FRONTEND],
}

_TYPE_NAMES = ", ".join(t.value for t in SPRINT1_TASK_TYPES)

SYSTEM_PROMPT = f"""You are the Master Agent of a multi-agent software platform.
Break the user's software requirement into small, concrete development tasks.

Rules:
- Produce exactly four tasks, one of each type: {_TYPE_NAMES}.
- The four tasks build one small web application from a fixed template:
  database = SQLite tables and functions, backend = FastAPI routes under /api,
  frontend = one HTML page with JavaScript, testing = pytest tests of the API.
- Write titles and descriptions for THIS requirement, whatever its domain, so each
  developer builds the same application with the same names:
  database: every table (plural snake_case) with its columns and links, the
    business rules (limits, states, checks) and the actions (for example
    "complete a task", "borrow an item");
  backend: the /api/<table> routes of every table and one route per action;
  frontend: one section per table with its form fields and action buttons;
  testing: the routes, rules and actions to test.
  Use the same table and field names in all four descriptions.
- "key" is a short unique name such as "T1".
- "depends_on" lists the keys of tasks that must finish first
  (database first, then backend, then frontend, testing last).
- Answer with JSON only, exactly in this shape:

{{
  "tasks": [
    {{"key": "T1", "title": "short title", "description": "what must be done",
      "type": "database", "depends_on": []}}
  ]
}}"""

# Fallback when the model keeps answering with broken JSON: one task per type.
FALLBACK_TASKS = [
    {"key": "T1", "type": "database", "title": "Design database schema",
     "description": "Define the tables and relations the application needs.",
     "depends_on": []},
    {"key": "T2", "type": "backend", "title": "Build REST API",
     "description": "Implement the backend endpoints on top of the database.",
     "depends_on": ["T1"]},
    {"key": "T3", "type": "frontend", "title": "Build web pages",
     "description": "Create the user interface that calls the REST API.",
     "depends_on": ["T2"]},
    {"key": "T4", "type": "testing", "title": "Write tests",
     "description": "Test the API and the web pages.",
     "depends_on": ["T2", "T3"]},
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


def _to_task_creates(data: object) -> list[TaskCreate]:
    """Validate the model's answer and turn it into TaskCreate objects.

    Raises ValueError when the answer cannot be used.
    """
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError('answer has no "tasks" list')
    raw_tasks = data["tasks"]
    if not raw_tasks:
        raise ValueError("answer has no tasks")

    allowed = {t.value for t in SPRINT1_TASK_TYPES}
    ids: dict[str, str] = {}
    for index, raw in enumerate(raw_tasks, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"task {index} is not an object")
        task_type = str(raw.get("type") or "").strip().lower()
        if task_type not in allowed:
            raise ValueError(f"task {index} has type {task_type!r}, expected one of {_TYPE_NAMES}")
        if not str(raw.get("title") or "").strip():
            raise ValueError(f"task {index} has no title")
        key = str(raw.get("key") or f"T{index}")
        if key in ids:
            raise ValueError(f"duplicate key {key!r}")
        ids[key] = str(uuid.uuid4())

    types = [str(raw["type"]).strip().lower() for raw in raw_tasks]
    missing = allowed - set(types)
    if missing:
        raise ValueError(f"missing task types: {', '.join(sorted(missing))}")
    doubled = sorted({kind for kind in types if types.count(kind) > 1})
    if doubled:
        raise ValueError(f"more than one task of type {', '.join(doubled)}; expected one of each")

    # One task per type, in the fixed order, with the fixed dependencies.
    by_type = {TaskType(kind): raw for kind, raw in zip(types, raw_tasks)}
    type_ids = {kind: str(uuid.uuid4()) for kind in ORDER}
    tasks = []
    for kind in ORDER:
        raw = by_type[kind]
        title = str(raw["title"]).strip()
        tasks.append(TaskCreate(
            id=type_ids[kind],
            title=title,
            description=str(raw.get("description") or title).strip(),
            type=kind,
            depends_on=[type_ids[dep] for dep in DEPENDS_ON[kind]],
        ))
    return tasks


def decompose(requirement_text: str) -> list[TaskCreate]:
    """Break a requirement into four tasks: database, backend, frontend, testing."""
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
    return _to_task_creates({"tasks": FALLBACK_TASKS})
