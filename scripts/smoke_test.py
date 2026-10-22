"""One-command check of a running master (card S2-07).

    python scripts/smoke_test.py

Start the master with LLM_MOCK=1 first. The script walks health -> register ->
project -> decompose -> assign -> tasks and prints SMOKE TEST PASSED (exit 0) or
the step that failed (exit 1). MASTER_URL and AGENT_TOKEN come from .env.

It registers one agent, "agent-smoke-test"; it turns offline after
HEARTBEAT_TIMEOUT_SEC because nothing sends its heartbeats.
"""

import os
import sys

import httpx
from dotenv import load_dotenv

SMOKE_AGENT = {
    "agent_id": "agent-smoke-test",
    "name": "Smoke-Test",
    "owner": "smoke_test.py",
    "role_hint": None,
    "model": "smoke",
    "provider": "ollama",
    "capabilities": {"coding": 50, "reasoning": 50, "context": 50},
}
PROJECT = {
    "name": "Smoke test",
    "requirement_text": "A small library app where members borrow and return books.",
}
TASK_TYPES = {"database", "backend", "frontend", "testing"}


class StepFailed(Exception):
    pass


def _call(client: httpx.Client, step: str, method: str, path: str, expect: int, **kwargs):
    try:
        response = client.request(method, f"/api/v1{path}", **kwargs)
    except httpx.HTTPError as exc:
        raise StepFailed(f"{step}: cannot reach the master ({exc})") from exc
    if response.status_code != expect:
        raise StepFailed(f"{step}: expected {expect}, got {response.status_code} {response.text}")
    return response.json()


def smoke(client: httpx.Client, token: str, log=print) -> None:
    """Raise StepFailed naming the first step that does not work."""
    health = _call(client, "health", "GET", "/health", 200)
    log(f"ok  health (version {health['version']})")

    _call(client, "register", "POST", "/agents/register", 200,
          json=SMOKE_AGENT, headers={"X-Agent-Token": token})
    log("ok  register")

    project = _call(client, "project", "POST", "/projects", 201, json=PROJECT)
    pid = project["id"]
    log(f"ok  project {pid}")

    tasks = _call(client, "decompose", "POST", f"/projects/{pid}/decompose", 200)
    types = {task["type"] for task in tasks}
    if not TASK_TYPES <= types:
        raise StepFailed(f"decompose: missing task types {sorted(TASK_TYPES - types)}")
    log(f"ok  decompose ({len(tasks)} tasks)")

    assigned = _call(client, "assign", "POST", f"/projects/{pid}/assign", 200)
    if not all(task["assigned_agent_id"] and task["assignment_reason"] for task in assigned):
        raise StepFailed("assign: a task has no agent or no reason")
    log("ok  assign")

    listed = _call(client, "tasks", "GET", f"/projects/{pid}/tasks", 200)
    if [t["id"] for t in listed] != [t["id"] for t in assigned]:
        raise StepFailed("tasks: the stored tasks differ from the assigned ones")
    log("ok  tasks")


def main() -> int:
    load_dotenv()
    master_url = os.getenv("MASTER_URL", "http://localhost:8000")
    token = os.getenv("AGENT_TOKEN", "change-me-team-secret")
    print(f"Smoke test against {master_url}")
    try:
        with httpx.Client(base_url=master_url, timeout=60) as client:
            smoke(client, token)
    except StepFailed as exc:
        print(f"SMOKE TEST FAILED at {exc}")
        return 1
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
