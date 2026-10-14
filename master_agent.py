"""
master_agent.py - Master Agent & LLM Integration module (CM6453).

Responsibilities
  1. Task decomposition: turn a free-text software requirement into structured
     subtasks (Frontend, Backend, Database, Testing) as strict JSON, using a
     local Llama 3.1 model served by Ollama.
  2. Dynamic routing: score every available sub-agent on coding capability,
     reasoning capability and context window size, then assign each subtask
     to the most suitable agent.

The module only uses the Python standard library, so it runs with no extra
installs. It is written to be imported later by the FastAPI layer:

    from master_agent import decompose_requirement, assign_tasks, MOCK_AGENTS

Run the end-to-end demo with:
    ollama pull llama3.1
    ollama serve            # if not already running
    python master_agent.py
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("master_agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT", "120"))
MAX_DECOMPOSITION_ATTEMPTS = 3

CATEGORIES = ("Frontend", "Backend", "Database", "Testing")


# ---------------------------------------------------------------------------
# 1. Ollama API connection handler
# ---------------------------------------------------------------------------

class OllamaError(RuntimeError):
    """Raised when Ollama cannot be reached or returns an unusable answer."""


class OllamaClient:
    """Minimal client for Ollama's /api/chat endpoint."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _request(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama HTTP {exc.code} on {path}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned non-JSON on {path}") from exc

    def is_available(self) -> bool:
        """True if the server answers and the configured model is pulled."""
        try:
            tags = self._request("/api/tags", timeout=3)
        except OllamaError:
            return False
        names = {m.get("name", "") for m in tags.get("models", [])}
        return any(n == self.model or n.startswith(f"{self.model}:") for n in names)

    def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = True,
        temperature: float = 0.1,
    ) -> str:
        """Send a chat request and return the assistant's raw text content."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"  # Ollama constrains output to valid JSON
        response = self._request("/api/chat", payload)
        content = response.get("message", {}).get("content")
        if not content:
            raise OllamaError("Ollama returned an empty message")
        return content


# ---------------------------------------------------------------------------
# 2. Task decomposition
# ---------------------------------------------------------------------------

DECOMPOSITION_SYSTEM_PROMPT = """You are the Master Agent of a multi-agent software platform.
Break the user's software requirement into concrete, independently executable subtasks.

Rules:
- Every subtask must belong to exactly one category: Frontend, Backend, Database, Testing.
- Produce at least one subtask per category.
- complexity is an integer from 1 (trivial) to 5 (very hard).
- estimated_context_tokens is how much context (in tokens) an LLM needs to do the task well.
- dependencies lists ids of subtasks that must finish first.
- Respond with JSON only, exactly in this shape:

{
  "project_name": "string",
  "summary": "one sentence",
  "subtasks": [
    {
      "id": "T1",
      "category": "Frontend | Backend | Database | Testing",
      "title": "short title",
      "description": "what must be built",
      "complexity": 3,
      "estimated_context_tokens": 4000,
      "dependencies": []
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


def _normalise_category(raw: Any) -> str | None:
    value = str(raw or "").strip().lower()
    aliases = {
        "frontend": "Frontend", "front-end": "Frontend", "front end": "Frontend",
        "ui": "Frontend", "client": "Frontend",
        "backend": "Backend", "back-end": "Backend", "back end": "Backend",
        "api": "Backend", "server": "Backend",
        "database": "Database", "db": "Database", "data": "Database",
        "testing": "Testing", "test": "Testing", "tests": "Testing", "qa": "Testing",
    }
    return aliases.get(value)


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
        category = _normalise_category(raw.get("category"))
        title = str(raw.get("title") or "").strip()
        if category is None or not title:
            logger.warning("Dropping malformed subtask: %r", raw)
            continue
        deps = raw.get("dependencies") or []
        subtasks.append({
            "id": str(raw.get("id") or f"T{index}"),
            "category": category,
            "title": title,
            "description": str(raw.get("description") or title).strip(),
            "complexity": _clamp_int(raw.get("complexity"), 1, 5, 3),
            "estimated_context_tokens": _clamp_int(
                raw.get("estimated_context_tokens"), 500, 200_000, 4_000
            ),
            "dependencies": [str(d) for d in deps] if isinstance(deps, list) else [],
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
        task["dependencies"] = [d for d in task["dependencies"] if d in seen and d != task["id"]]

    missing = [c for c in CATEGORIES if c not in {t["category"] for t in subtasks}]
    if missing:
        logger.warning("Decomposition is missing categories: %s", ", ".join(missing))

    return {
        "project_name": str(data.get("project_name") or "Untitled project").strip(),
        "summary": str(data.get("summary") or user_prompt).strip(),
        "requirement": user_prompt,
        "subtasks": subtasks,
        "missing_categories": missing,
    }


def _fallback_decomposition(user_prompt: str) -> dict:
    """Deterministic template used when Ollama is unreachable (demo/offline mode)."""
    template = [
        ("T1", "Database", "Design data model",
         "Design the schema, entities and relations implied by the requirement.", 3, 3000, []),
        ("T2", "Backend", "Implement REST API",
         "Build CRUD endpoints and business logic on top of the data model.", 4, 8000, ["T1"]),
        ("T3", "Frontend", "Build user interface",
         "Build the pages and components that consume the REST API.", 3, 6000, ["T2"]),
        ("T4", "Testing", "Write automated tests",
         "Write unit and integration tests for the API and UI.", 3, 12000, ["T2", "T3"]),
    ]
    data = {
        "project_name": "Offline decomposition",
        "summary": user_prompt,
        "subtasks": [
            {"id": i, "category": c, "title": t, "description": d,
             "complexity": x, "estimated_context_tokens": tok, "dependencies": deps}
            for i, c, t, d, x, tok, deps in template
        ],
    }
    return validate_decomposition(data, user_prompt)


def decompose_requirement(
    user_prompt: str,
    client: OllamaClient | None = None,
    allow_fallback: bool = True,
) -> dict:
    """Break a software requirement into Frontend/Backend/Database/Testing subtasks.

    Returns a dict with project_name, summary, requirement, subtasks,
    missing_categories and source ("ollama" or "fallback").
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
        try:
            raw = client.chat(messages, json_mode=True)
            result = validate_decomposition(_extract_json(raw), user_prompt)
            result["source"] = "ollama"
            return result
        except OllamaError as exc:
            last_error = exc
            break  # server problem: retrying the same request will not help
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            logger.warning("Attempt %d: invalid decomposition (%s), retrying", attempt, exc)
            messages.append({
                "role": "user",
                "content": f"Your previous answer was invalid ({exc}). "
                           "Reply again with JSON only, following the schema exactly.",
            })

    if not allow_fallback:
        raise RuntimeError(f"Decomposition failed: {last_error}") from last_error
    logger.warning("Using offline fallback decomposition: %s", last_error)
    result = _fallback_decomposition(user_prompt)
    result["source"] = "fallback"
    return result


# ---------------------------------------------------------------------------
# 3. Mock sub-agents (replaced by the teammates' database later)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    model: str
    coding: float          # 0-10 coding capability
    reasoning: float       # 0-10 reasoning capability
    context_window: int    # tokens
    specialties: tuple[str, ...] = ()
    max_concurrent_tasks: int = 2

    @classmethod
    def from_dict(cls, d: dict) -> "AgentProfile":
        return cls(
            agent_id=d["agent_id"],
            model=d["model"],
            coding=float(d["coding"]),
            reasoning=float(d["reasoning"]),
            context_window=int(d["context_window"]),
            specialties=tuple(d.get("specialties", ())),
            max_concurrent_tasks=int(d.get("max_concurrent_tasks", 2)),
        )


# Plain dicts, the same shape a DB row / JSON API response would have.
MOCK_AGENTS: list[dict] = [
    {"agent_id": "agent-llama3",   "model": "llama3.1:8b",
     "coding": 7.0, "reasoning": 8.0, "context_window": 128_000,
     "specialties": ["Testing", "Backend"], "max_concurrent_tasks": 2},
    {"agent_id": "agent-deepseek", "model": "deepseek-coder:6.7b",
     "coding": 9.5, "reasoning": 6.5, "context_window": 16_000,
     "specialties": ["Backend", "Database"], "max_concurrent_tasks": 2},
    {"agent_id": "agent-mistral",  "model": "mistral:7b",
     "coding": 6.5, "reasoning": 7.5, "context_window": 32_000,
     "specialties": ["Frontend"], "max_concurrent_tasks": 2},
    {"agent_id": "agent-codellama", "model": "codellama:7b",
     "coding": 8.0, "reasoning": 5.5, "context_window": 16_000,
     "specialties": ["Frontend", "Backend"], "max_concurrent_tasks": 1},
]


# ---------------------------------------------------------------------------
# 4. Scoring matrix & task assignment
# ---------------------------------------------------------------------------

# How much each capability matters per task category (each row sums to 1.0).
SCORING_MATRIX: dict[str, dict[str, float]] = {
    #              coding  reasoning  context
    "Frontend": {"coding": 0.55, "reasoning": 0.30, "context": 0.15},
    "Backend":  {"coding": 0.60, "reasoning": 0.25, "context": 0.15},
    "Database": {"coding": 0.40, "reasoning": 0.45, "context": 0.15},
    "Testing":  {"coding": 0.35, "reasoning": 0.35, "context": 0.30},
}

SPECIALTY_BONUS = 0.5        # added (0-10 scale) when the agent lists the category
LOAD_PENALTY = 0.75          # subtracted per task already assigned to the agent
FULL_HEADROOM = 4.0          # window >= 4x the task's needs earns a full 10/10


def _context_score(window: int, needed: int) -> float:
    """0-10 score for how comfortably the task fits in the agent's context window.

    Log-scaled headroom: exactly fits -> 0, 2x -> 5, 4x or more -> 10.
    """
    if window <= needed:
        return 0.0
    return min(10.0, 10.0 * math.log(window / needed) / math.log(FULL_HEADROOM))


def score_agent(
    task: dict, agent: AgentProfile, current_load: int = 0, enforce_capacity: bool = True
) -> dict:
    """Score one agent for one task. Returns the total and a breakdown."""
    weights = SCORING_MATRIX.get(task["category"], SCORING_MATRIX["Backend"])
    needed = task.get("estimated_context_tokens", 4_000)

    if needed > agent.context_window:
        return {"eligible": False, "total": 0.0,
                "reason": f"needs {needed} tokens, agent has {agent.context_window}"}
    if enforce_capacity and current_load >= agent.max_concurrent_tasks:
        return {"eligible": False, "total": 0.0, "reason": "agent at capacity"}

    # Harder tasks lean more on reasoning: shift up to 10% weight from coding.
    shift = 0.025 * (task.get("complexity", 3) - 1)
    w_coding = weights["coding"] - shift
    w_reasoning = weights["reasoning"] + shift

    coding = w_coding * agent.coding
    reasoning = w_reasoning * agent.reasoning
    context = weights["context"] * _context_score(agent.context_window, needed)
    bonus = SPECIALTY_BONUS if task["category"] in agent.specialties else 0.0
    penalty = LOAD_PENALTY * current_load
    total = coding + reasoning + context + bonus - penalty

    return {
        "eligible": True,
        "total": round(total, 3),
        "breakdown": {
            "coding": round(coding, 3),
            "reasoning": round(reasoning, 3),
            "context": round(context, 3),
            "specialty_bonus": bonus,
            "load_penalty": round(penalty, 3),
        },
    }


def _ordered_by_dependencies(tasks: list[dict]) -> list[dict]:
    """Topological order so prerequisite tasks are routed first."""
    by_id = {t["id"]: t for t in tasks}
    ordered, visiting, done = [], set(), set()

    def visit(task: dict) -> None:
        if task["id"] in done or task["id"] in visiting:
            return  # already placed, or a cycle: keep original order
        visiting.add(task["id"])
        for dep in task.get("dependencies", []):
            if dep in by_id:
                visit(by_id[dep])
        visiting.discard(task["id"])
        done.add(task["id"])
        ordered.append(task)

    for t in tasks:
        visit(t)
    return ordered


def assign_tasks(decomposed_tasks: list, available_agents: list) -> list:
    """Assign every subtask to the highest-scoring eligible agent.

    available_agents may be dicts (DB rows) or AgentProfile objects.
    Returns one assignment dict per task, in dependency order.
    """
    agents = [a if isinstance(a, AgentProfile) else AgentProfile.from_dict(a)
              for a in available_agents]
    if not agents:
        raise ValueError("No agents available")

    load: dict[str, int] = {a.agent_id: 0 for a in agents}
    assignments: list[dict] = []

    for task in _ordered_by_dependencies(decomposed_tasks):
        def rank(enforce_capacity: bool) -> list:
            scored = [(a, score_agent(task, a, load[a.agent_id], enforce_capacity))
                      for a in agents]
            return sorted((s for s in scored if s[1]["eligible"]),
                          key=lambda s: s[1]["total"], reverse=True)

        eligible = rank(enforce_capacity=True)
        status = "assigned"
        if not eligible:
            # Every suitable agent is busy: queue it on the best one anyway.
            eligible = rank(enforce_capacity=False)
            status = "queued_over_capacity"

        if eligible:
            best_agent, best = eligible[0]
        else:
            # No agent's context window fits: take the largest and flag it.
            best_agent = max(agents, key=lambda a: (a.context_window, a.reasoning))
            best = {"total": 0.0, "reason": "task exceeds every agent's context window"}
            status = "assigned_with_warning"

        load[best_agent.agent_id] += 1
        assignments.append({
            "task_id": task["id"],
            "category": task["category"],
            "title": task["title"],
            "assigned_agent": best_agent.agent_id,
            "model": best_agent.model,
            "score": best["total"],
            "score_breakdown": best.get("breakdown", {}),
            "status": status,
            "note": best.get("reason"),
            "alternatives": [
                {"agent_id": a.agent_id, "score": r["total"]} for a, r in eligible[1:3]
            ],
            "dependencies": task.get("dependencies", []),
        })

    return assignments


# ---------------------------------------------------------------------------
# 5. Demo
# ---------------------------------------------------------------------------

def _print_report(decomposition: dict, assignments: list[dict]) -> None:
    print(f"\nProject: {decomposition['project_name']}  (source: {decomposition['source']})")
    print(f"Summary: {decomposition['summary']}\n")
    print(f"{'Task':<5} {'Category':<9} {'Title':<38} {'Agent':<16} {'Score':>6}")
    print("-" * 78)
    for a in assignments:
        print(f"{a['task_id']:<5} {a['category']:<9} {a['title'][:38]:<38} "
              f"{a['assigned_agent']:<16} {a['score']:>6.2f}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    requirement = "Build a Library Management System with React frontend and FastAPI backend"

    client = OllamaClient()
    if not client.is_available():
        logger.warning("Ollama model %r not reachable at %s; the demo will use the "
                       "offline fallback. Run `ollama pull %s` and `ollama serve`.",
                       client.model, client.base_url, client.model)

    decomposition = decompose_requirement(requirement, client=client)
    assignments = assign_tasks(decomposition["subtasks"], MOCK_AGENTS)

    _print_report(decomposition, assignments)
    print("Full JSON output:")
    print(json.dumps({"decomposition": decomposition, "assignments": assignments}, indent=2))


if __name__ == "__main__":
    main()
