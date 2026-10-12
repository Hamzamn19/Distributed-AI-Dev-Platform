"""Contract tests: fail when someone changes a shared name or value by accident.

If one of these fails, do not "fix" the test. Check docs/PROJECT_CONTRACT.md:
either the code drifted from the contract, or the contract needs a team decision.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from dap.shared.enums import AgentStatus, ProjectStatus, TaskStatus, TaskType
from dap.shared.schemas import Agent, AgentRegister, Heartbeat, ProjectCreate, Task

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENT_JSON = {
    "agent_id": "agent-okan",
    "name": "Okan-PC",
    "owner": "Okan",
    "role_hint": "integration",
    "model": "qwen3:4b",
    "provider": "ollama",
    "capabilities": {"coding": 60, "reasoning": 60, "context": 50},
    "status": "idle",
    "current_task_id": None,
    "registered_at": "2026-10-05T18:00:00Z",
    "last_heartbeat_at": "2026-10-05T18:00:10Z",
}

TASK_JSON = {
    "id": "7f3d1c44-0000-4000-8000-000000000001",
    "project_id": "0b5c2a9e-0000-4000-8000-000000000001",
    "title": "Design database schema",
    "description": "Tables for books and members",
    "type": "database",
    "status": "pending",
    "depends_on": [],
    "assigned_agent_id": None,
    "assignment_reason": None,
    "attempt": 0,
    "created_at": "2026-10-05T18:06:00Z",
    "updated_at": "2026-10-05T18:06:00Z",
}


def test_enum_values_match_contract():
    assert [s.value for s in AgentStatus] == ["idle", "busy", "offline"]
    assert [t.value for t in TaskType] == [
        "requirements_analysis",
        "frontend",
        "backend",
        "database",
        "testing",
        "code_review",
        "integration",
        "documentation",
    ]
    assert [s.value for s in TaskStatus] == [
        "pending",
        "assigned",
        "in_progress",
        "completed",
        "failed",
    ]
    assert [s.value for s in ProjectStatus] == [
        "created",
        "decomposing",
        "in_progress",
        "integrating",
        "completed",
        "failed",
    ]


def test_agent_example_round_trips():
    agent = Agent.model_validate(AGENT_JSON)
    assert agent.model_dump(mode="json") == AGENT_JSON


def test_task_example_round_trips():
    task = Task.model_validate(TASK_JSON)
    assert task.model_dump(mode="json") == TASK_JSON


def test_missing_values_are_sent_as_null():
    dumped = Task.model_validate(TASK_JSON).model_dump(mode="json")
    assert "assigned_agent_id" in dumped and dumped["assigned_agent_id"] is None


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Heartbeat.model_validate({"status": "idle", "currentTaskId": None})


def test_unknown_enum_value_is_rejected():
    with pytest.raises(ValidationError):
        Heartbeat.model_validate({"status": "done"})


def test_naive_datetime_is_rejected():
    bad = dict(AGENT_JSON, registered_at="2026-10-05T18:00:00")
    with pytest.raises(ValidationError):
        Agent.model_validate(bad)


def test_utc_datetime_serializes_with_z():
    agent = Agent.model_validate(
        dict(AGENT_JSON, registered_at=datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc))
    )
    assert agent.model_dump(mode="json")["registered_at"] == "2026-10-05T18:00:00Z"


def test_short_requirement_is_rejected():
    with pytest.raises(ValidationError):
        ProjectCreate(name="Library", requirement_text="too short")


def test_capability_scores_stay_between_0_and_100():
    bad = dict(AGENT_JSON, capabilities={"coding": 101, "reasoning": 60, "context": 50})
    with pytest.raises(ValidationError):
        Agent.model_validate(bad)


def test_agents_inventory_matches_register_schema():
    """docs/agents.json is what scripts/seed_agents.py will send to the master."""
    entries = json.loads((REPO_ROOT / "docs" / "agents.json").read_text("utf-8"))
    agents = [AgentRegister.model_validate(entry) for entry in entries]
    ids = [a.agent_id for a in agents]
    assert len(ids) == len(set(ids)) == 6
