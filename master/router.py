from __future__ import annotations

import logging
from typing import Optional

from config import QUEUE_PENALTY, SPECIALTY_BONUS, TASK_WEIGHTS, AgentProfile

logger = logging.getLogger("router")


def score_agent(task: dict, agent: AgentProfile, queue_length: int = 0) -> dict:
    """Score one agent for one task with the CM6453 formula.

    S = (w_c * C) + (w_r * R) + (w_x * X) + (10 * u) - (15 * q)

    C, R, X are the agent's 0-100 coding, reasoning and context scores,
    u is 1 when the agent specialises in the task type, q is its active queue.
    """
    task_type = task["task_type"]
    weights = TASK_WEIGHTS.get(task_type, TASK_WEIGHTS["backend"])
    needed = task.get("estimated_context_tokens", 0)

    if agent.context_window and needed > agent.context_window:
        return {"eligible": False, "total": 0.0,
                "reason": f"needs {needed} tokens, agent has {agent.context_window}"}

    u = 1 if task_type in agent.specialties else 0
    coding = weights["w_c"] * agent.coding
    reasoning = weights["w_r"] * agent.reasoning
    context = weights["w_x"] * agent.context
    bonus = SPECIALTY_BONUS * u
    penalty = QUEUE_PENALTY * queue_length
    total = coding + reasoning + context + bonus - penalty

    return {
        "eligible": True,
        "total": round(total, 3),
        "breakdown": {
            "coding": round(coding, 3),
            "reasoning": round(reasoning, 3),
            "context": round(context, 3),
            "specialty_bonus": bonus,
            "queue_penalty": penalty,
            "u": u,
            "q": queue_length,
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
        for dep in task.get("depends_on", []):
            if dep in by_id:
                visit(by_id[dep])
        visiting.discard(task["id"])
        done.add(task["id"])
        ordered.append(task)

    for t in tasks:
        visit(t)
    return ordered


def assign_tasks(
    decomposed_tasks: list,
    available_agents: list,
    queue_lengths: Optional[dict[str, int]] = None,
) -> list:
    """Assign every subtask to the highest-scoring eligible agent.

    available_agents may be dicts (DB rows) or AgentProfile objects.
    queue_lengths holds each agent's active tasks before this batch (q);
    every assignment made here adds one to that agent's queue.
    Returns one assignment dict per task, in dependency order.
    """
    agents = [a if isinstance(a, AgentProfile) else AgentProfile.from_dict(a)
              for a in available_agents]
    if not agents:
        raise ValueError("No agents available")

    queue = {a.agent_id: (queue_lengths or {}).get(a.agent_id, 0) for a in agents}
    assignments: list[dict] = []

    for task in _ordered_by_dependencies(decomposed_tasks):
        scored = [(a, score_agent(task, a, queue[a.agent_id])) for a in agents]
        w = TASK_WEIGHTS.get(task["task_type"], TASK_WEIGHTS["backend"])
        logger.info("[SCORE] %s (%s) w_c=%.1f w_r=%.1f w_x=%.1f", task["id"],
                    task["task_type"], w["w_c"], w["w_r"], w["w_x"])
        for a, r in scored:
            if r["eligible"]:
                b = r["breakdown"]
                logger.info("        %-12s S=%6.1f  (C=%g R=%g X=%g u=%d q=%d)", a.agent_id,
                            r["total"], a.coding, a.reasoning, a.context, b["u"], b["q"])
            else:
                logger.info("        %-12s uygun değil: %s", a.agent_id, r["reason"])
        eligible = sorted((s for s in scored if s[1]["eligible"]),
                          key=lambda s: s[1]["total"], reverse=True)
        status = "assigned"

        if eligible:
            best_agent, best = eligible[0]
        else:
            # No agent's context window fits: take the largest and flag it.
            best_agent = max(agents, key=lambda a: (a.context_window, a.context))
            best = {"total": 0.0, "reason": "task exceeds every agent's context window"}
            status = "assigned_with_warning"

        queue[best_agent.agent_id] += 1
        logger.info("[ASSIGN] Task %s -> %s (Score: %.1f)", task["id"], best_agent.agent_id,
                    best["total"])
        assignments.append({
            "task_id": task["id"],
            "task_type": task["task_type"],
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
            "depends_on": task.get("depends_on", []),
        })

    return assignments
