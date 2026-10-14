from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from config import MAX_DECOMPOSITION_ATTEMPTS, TASK_TYPES
from ollama_client import OllamaClient, OllamaError

logger = logging.getLogger("decomposer")

DECOMPOSITION_SYSTEM_PROMPT = """You are the Master Agent of a multi-agent software platform.
Break the user's software requirement document into concrete, independently executable subtasks.

Rules:
- Every subtask has exactly one task_type: analysis, database, backend, frontend,
  testing, review, integration, documentation.
- Produce at least one subtask per type.
- complexity is an integer from 1 (trivial) to 5 (very hard).
- estimated_context_tokens is how much context (in tokens) an LLM needs to do the task well.
- acceptance_criteria lists short, checkable conditions for the task to count as done.
- depends_on lists ids of subtasks that must finish first
  (e.g. analysis first, integration after frontend/backend/database, testing and review near the end).
- Respond with JSON only, exactly in this shape:

{
  "project_name": "string",
  "summary": "one sentence",
  "subtasks": [
    {
      "id": "T1",
      "task_type": "analysis | database | backend | frontend | testing | review | integration | documentation",
      "title": "short title",
      "description": "what must be done",
      "acceptance_criteria": ["..."],
      "complexity": 3,
      "estimated_context_tokens": 4000,
      "depends_on": []
    }
  ]
}"""


def _extract_json(text: str) -> dict:
    """Parse JSON from model output, tolerating code fences or stray prose."""
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


_TYPE_ALIASES = {
    "requirements": "analysis", "requirements analysis": "analysis", "analyse": "analysis",
    "design": "analysis", "architecture": "analysis",
    "db": "database", "data": "database", "schema": "database",
    "back-end": "backend", "back end": "backend", "api": "backend", "server": "backend",
    "front-end": "frontend", "front end": "frontend", "ui": "frontend", "client": "frontend",
    "test": "testing", "tests": "testing", "qa": "testing",
    "code review": "review", "code-review": "review",
    "integrate": "integration", "deployment": "integration", "devops": "integration",
    "docs": "documentation", "doc": "documentation",
}


def _normalise_type(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    if value in TASK_TYPES:
        return value
    return _TYPE_ALIASES.get(value)


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def validate_decomposition(data: Any, user_prompt: str) -> dict:
    """Validate and normalise a decomposition into the platform's strict schema.

    Raises ValueError if the payload is unusable (so the caller can retry).
    """
    if not isinstance(data, dict):
        raise ValueError("Decomposition must be a JSON object")
    raw_tasks = data.get("subtasks") or data.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise ValueError("Decomposition has no subtasks list")

    subtasks: list[dict] = []
    for index, raw in enumerate(raw_tasks, start=1):
        if not isinstance(raw, dict):
            continue
        task_type = _normalise_type(
            raw.get("task_type") or raw.get("type") or raw.get("category"))
        title = str(raw.get("title") or "").strip()
        if task_type is None or not title:
            logger.warning("Dropping malformed subtask: %r", raw)
            continue
        deps = raw.get("depends_on") or raw.get("dependencies") or []
        criteria = raw.get("acceptance_criteria") or []
        subtasks.append({
            "id": str(raw.get("id") or f"T{index}"),
            "task_type": task_type,
            "title": title,
            "description": str(raw.get("description") or title).strip(),
            "acceptance_criteria": ([str(c).strip() for c in criteria if str(c).strip()]
                                    if isinstance(criteria, list) else [str(criteria)]),
            "complexity": _clamp_int(raw.get("complexity"), 1, 5, 3),
            "estimated_context_tokens": _clamp_int(
                raw.get("estimated_context_tokens"), 500, 200_000, 4_000
            ),
            "depends_on": [str(d) for d in deps] if isinstance(deps, list) else [],
        })

    if not subtasks:
        raise ValueError("No valid subtasks after normalisation")

    # Ids must be unique, and dependencies may only reference known ids.
    seen: set[str] = set()
    for i, task in enumerate(subtasks, start=1):
        if task["id"] in seen:
            task["id"] = f"T{i}"
        seen.add(task["id"])
    for task in subtasks:
        task["depends_on"] = [d for d in task["depends_on"] if d in seen and d != task["id"]]

    missing = [t for t in TASK_TYPES if t not in {s["task_type"] for s in subtasks}]
    if missing:
        logger.warning("Decomposition is missing task types: %s", ", ".join(missing))

    return {
        "project_name": str(data.get("project_name") or "Untitled project").strip(),
        "summary": str(data.get("summary") or user_prompt).strip(),
        "requirement": user_prompt,
        "subtasks": subtasks,
        "missing_types": missing,
    }


def _fallback_decomposition(user_prompt: str) -> dict:
    """Deterministic template used when Ollama is unreachable (demo/offline mode)."""
    template = [
        ("T1", "analysis", "Analyse requirements",
         "Extract functional and non-functional requirements and user stories.", 3, 6000, []),
        ("T2", "database", "Design data model",
         "Design the schema, entities and relations implied by the requirement.", 3, 3000, ["T1"]),
        ("T3", "backend", "Implement REST API",
         "Build CRUD endpoints and business logic on top of the data model.", 4, 8000, ["T2"]),
        ("T4", "frontend", "Build user interface",
         "Build the pages and components that consume the REST API.", 3, 6000, ["T1"]),
        ("T5", "integration", "Integrate components",
         "Wire frontend, backend and database together into one runnable app.", 3, 10000,
         ["T3", "T4"]),
        ("T6", "testing", "Write automated tests",
         "Write unit and integration tests for the API and UI.", 3, 12000, ["T5"]),
        ("T7", "review", "Review code",
         "Review the generated code for bugs, security issues and style.", 3, 12000, ["T5"]),
        ("T8", "documentation", "Write documentation",
         "Write the README, API reference and setup guide.", 2, 8000, ["T6", "T7"]),
    ]
    data = {
        "project_name": "Offline decomposition",
        "summary": user_prompt,
        "subtasks": [
            {"id": i, "task_type": c, "title": t, "description": d,
             "complexity": x, "estimated_context_tokens": tok, "depends_on": deps}
            for i, c, t, d, x, tok, deps in template
        ],
    }
    return validate_decomposition(data, user_prompt)


def decompose_requirement(
    user_prompt: str,
    client: OllamaClient | None = None,
    allow_fallback: bool = True,
) -> dict:
    """Break a software requirement into subtasks of the 8 platform task types.

    Returns a dict with project_name, summary, requirement, subtasks,
    missing_types and source ("ollama" or "fallback").
    """
    if not user_prompt or not user_prompt.strip():
        raise ValueError("user_prompt must not be empty")

    client = client or OllamaClient()
    messages = [
        {"role": "system", "content": DECOMPOSITION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Requirement: {user_prompt.strip()}"},
    ]
    last_error: Exception | None = None

    for attempt in range(1, MAX_DECOMPOSITION_ATTEMPTS + 1):
        logger.info("[DECOMPOSE] %s modeline gönderiliyor (deneme %d/%d)...",
                    client.model, attempt, MAX_DECOMPOSITION_ATTEMPTS)
        started = time.monotonic()
        try:
            raw = client.chat(messages, json_mode=True)
            logger.info("[DECOMPOSE] Model %.1f sn'de yanıt verdi, JSON doğrulanıyor",
                        time.monotonic() - started)
            result = validate_decomposition(_extract_json(raw), user_prompt)
            result["source"] = "ollama"
            logger.info("[DECOMPOSE] %d görev çıkarıldı: %s", len(result["subtasks"]),
                        result["project_name"])
            return result
        except OllamaError as exc:
            last_error = exc
            logger.warning("[DECOMPOSE] Ollama'ya ulaşılamadı: %s", exc)
            break  # server problem: retrying the same request will not help
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("[DECOMPOSE] Deneme %d geçersiz JSON (%s), tekrar deneniyor",
                           attempt, exc)
            messages.append({
                "role": "user",
                "content": f"Your previous answer was invalid ({exc}). "
                           "Reply again with JSON only, following the schema exactly.",
            })

    if not allow_fallback:
        raise RuntimeError(f"Decomposition failed: {last_error}") from last_error
    logger.warning("[DECOMPOSE] Çevrimdışı yedek şablon kullanılıyor (8 görev)")
    result = _fallback_decomposition(user_prompt)
    result["source"] = "fallback"
    return result
