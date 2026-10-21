"""Task breakdown: turns a requirement text into tasks with the local LLM.

Owner: Baran - card S1-06.

    decompose(requirement_text: str) -> list[TaskCreate]

The model is asked for (member guide, agreement 2):

    {"tasks": [{"key", "title", "description", "type", "depends_on"}]}

"key" is a temporary name inside the answer and "depends_on" lists keys. Every
task gets a UUID4 here and the keys in depends_on are translated to those ids.

Rules:
- Only the Sprint 1 types are accepted (SPRINT1_TASK_TYPES), and each of them
  must appear at least once.
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

_TYPE_NAMES = ", ".join(t.value for t in SPRINT1_TASK_TYPES)

SYSTEM_PROMPT = f"""You are the Master Agent of a multi-agent software platform.
Break the user's software requirement into small, concrete development tasks.

Rules:
- Every task has exactly one type: {_TYPE_NAMES}.
- Produce at least one task of each type.
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

    missing = allowed - {str(raw["type"]).strip().lower() for raw in raw_tasks}
    if missing:
        raise ValueError(f"missing task types: {', '.join(sorted(missing))}")

    tasks = []
    for index, raw in enumerate(raw_tasks, start=1):
        key = str(raw.get("key") or f"T{index}")
        deps = raw.get("depends_on")
        deps = deps if isinstance(deps, list) else []
        title = str(raw["title"]).strip()
        tasks.append(TaskCreate(
            id=ids[key],
            title=title,
            description=str(raw.get("description") or title).strip(),
            type=TaskType(str(raw["type"]).strip().lower()),
            # Unknown keys and self-references are dropped instead of failing.
            depends_on=[ids[str(d)] for d in deps if str(d) in ids and str(d) != key],
        ))
    return tasks


def decompose(requirement_text: str) -> list[TaskCreate]:
    """Break a requirement into Sprint 1 tasks (frontend, backend, database, testing)."""
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
