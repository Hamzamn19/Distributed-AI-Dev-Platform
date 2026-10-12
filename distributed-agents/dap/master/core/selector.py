"""Chooses which agent gets a task.

Owner: Baran - card S1-06.

Sprint 1 rule: the task goes to the agent whose role_hint equals the task type.
Whether the agent is online is not checked yet. When no agent matches, return
None and leave the task "pending".

Sprint 2 replaces the rule with capability scores; the function signature and
the /assign endpoint stay the same.
"""

from dap.shared.schemas import Agent, Task


def select_agent(task: Task, agents: list[Agent]) -> tuple[Agent, str] | None:
    """Return (agent, assignment_reason) or None when no agent fits."""
    raise NotImplementedError("S1-06: implement select_agent()")
