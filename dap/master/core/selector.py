"""Agent selection: scores the agents for one task (contract section 8).

Owner: Baran - card S2-02.

    select_agent(task, agents, queue=None) -> (agent, reason) | None

    S = w_c * C + w_r * R + w_x * X + 10 * u - 15 * q

The highest S wins. On a tie the agent whose role_hint equals the task type
wins, then the smaller agent_id. Offline agents are not candidates; with no
candidate None is returned and the task stays pending.

This module has no database access: the caller passes q (number of "assigned"
or "in_progress" tasks per agent_id) in `queue`.
"""

from dap.shared.enums import AgentStatus, TaskType
from dap.shared.schemas import Agent, Task

ROLE_BONUS = 10
QUEUE_PENALTY = 15

# Weights (w_c, w_r, w_x) per task type: contract section 9.
WEIGHTS: dict[TaskType, tuple[float, float, float]] = {
    TaskType.FRONTEND: (0.6, 0.2, 0.2),
    TaskType.BACKEND: (0.5, 0.3, 0.2),
    TaskType.DATABASE: (0.4, 0.4, 0.2),
    TaskType.TESTING: (0.4, 0.4, 0.2),
    TaskType.CODE_REVIEW: (0.2, 0.5, 0.3),
    TaskType.INTEGRATION: (0.3, 0.3, 0.4),
    TaskType.REQUIREMENTS_ANALYSIS: (0.1, 0.6, 0.3),
    TaskType.DOCUMENTATION: (0.1, 0.4, 0.5),
}


def score(task: Task, agent: Agent, queued: int = 0) -> tuple[float, str]:
    """Return S and a short text with its parts."""
    w_c, w_r, w_x = WEIGHTS[task.type]
    caps = agent.capabilities
    coding = w_c * caps.coding
    reasoning = w_r * caps.reasoning
    context = w_x * caps.context
    role = ROLE_BONUS if agent.role_hint == task.type else 0
    queue = QUEUE_PENALTY * queued
    total = coding + reasoning + context + role - queue
    reason = (
        f"S={total:.1f} (coding {coding:.1f}, reasoning {reasoning:.1f}, "
        f"context {context:.1f}, role +{role}, queue -{queue})"
    )
    return total, reason


def select_agent(
    task: Task, agents: list[Agent], queue: dict[str, int] | None = None
) -> tuple[Agent, str] | None:
    queue = queue or {}
    best: tuple[Agent, float, str] | None = None
    for agent in agents:
        if agent.status == AgentStatus.OFFLINE:
            continue
        total, reason = score(task, agent, queue.get(agent.agent_id, 0))
        if best is None or _beats(agent, total, best[0], best[1], task):
            best = (agent, total, reason)
    return (best[0], best[2]) if best else None


def _beats(a: Agent, a_score: float, b: Agent, b_score: float, task: Task) -> bool:
    """True when a is chosen over b: higher S, then role match, then smaller agent_id."""
    if round(a_score, 9) != round(b_score, 9):
        return a_score > b_score
    a_role, b_role = a.role_hint == task.type, b.role_hint == task.type
    if a_role != b_role:
        return a_role
    return a.agent_id < b.agent_id
