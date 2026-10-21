from datetime import datetime, timezone

from dap.master.core.selector import select_agent
from dap.shared.enums import AgentStatus, TaskStatus, TaskType
from dap.shared.schemas import Agent, Capabilities, Task

NOW = datetime.now(timezone.utc)


def _agent(agent_id, coding, reasoning, context, role=None, status=AgentStatus.IDLE) -> Agent:
    return Agent(
        agent_id=agent_id, name=agent_id, owner="x", role_hint=role, model="m",
        capabilities=Capabilities(coding=coding, reasoning=reasoning, context=context),
        status=status, registered_at=NOW,
    )


def _task(task_type=TaskType.BACKEND) -> Task:
    return Task(
        id="t1", project_id="p1", title="t", description="d", type=task_type,
        status=TaskStatus.PENDING, created_at=NOW, updated_at=NOW,
    )


def test_highest_score_wins_and_reason_shows_parts():
    agents = [_agent("a", 90, 50, 50), _agent("b", 60, 60, 60), _agent("c", 40, 90, 90)]
    chosen, reason = select_agent(_task(TaskType.BACKEND), agents)
    # backend 0.5/0.3/0.2: a=70.0, b=60.0, c=65.0
    assert chosen.agent_id == "a"
    assert reason.startswith("S=70.0")
    assert "coding 45.0" in reason and "queue -0" in reason


def test_weights_depend_on_task_type():
    agents = [_agent("coder", 90, 40, 40), _agent("thinker", 40, 90, 40)]
    assert select_agent(_task(TaskType.FRONTEND), agents)[0].agent_id == "coder"
    assert select_agent(_task(TaskType.REQUIREMENTS_ANALYSIS), agents)[0].agent_id == "thinker"


def test_role_hint_adds_ten_points():
    agents = [_agent("a", 60, 60, 60), _agent("b", 56, 56, 56, role=TaskType.BACKEND)]
    chosen, reason = select_agent(_task(), agents)
    assert chosen.agent_id == "b"
    assert "role +10" in reason


def test_equal_score_and_no_role_goes_to_smaller_agent_id():
    agents = [_agent("z", 50, 50, 50), _agent("m", 50, 50, 50)]
    assert select_agent(_task(), agents)[0].agent_id == "m"


def test_equal_score_prefers_role_hint():
    # a: 0.5*10 + 0.3*10 + 0.2*10 = 10.0; b: 0 + 10 role = 10.0 -> tie
    plain = _agent("a", 10, 10, 10)
    hinted = _agent("b", 0, 0, 0, role=TaskType.BACKEND)
    assert select_agent(_task(), [plain, hinted])[0].agent_id == "b"
    assert select_agent(_task(), [hinted, plain])[0].agent_id == "b"


def test_loaded_agent_loses():
    agents = [_agent("a", 80, 80, 80), _agent("b", 70, 70, 70)]
    assert select_agent(_task(), agents, {"a": 1})[0].agent_id == "b"
    assert select_agent(_task(), agents, {"a": 0})[0].agent_id == "a"


def test_offline_agents_are_not_candidates():
    agents = [_agent("a", 99, 99, 99, status=AgentStatus.OFFLINE), _agent("b", 10, 10, 10)]
    assert select_agent(_task(), agents)[0].agent_id == "b"


def test_busy_agents_can_still_be_chosen():
    agents = [_agent("a", 90, 90, 90, status=AgentStatus.BUSY)]
    assert select_agent(_task(), agents)[0].agent_id == "a"


def test_no_candidate_gives_none():
    assert select_agent(_task(), []) is None
    assert select_agent(_task(), [_agent("a", 1, 1, 1, status=AgentStatus.OFFLINE)]) is None
