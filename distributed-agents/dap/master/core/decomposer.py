"""Turns a requirement document into a list of tasks with the LLM.

Owner: Baran - card S1-06.

Sprint 1 behaviour:
- Ask the model (dap.shared.llm_client.chat with json_mode=True) for a JSON
  list of tasks. Allowed types are dap.shared.enums.SPRINT1_TASK_TYPES.
- Validate every task with TaskCreate. Give each task a UUID4 id and translate
  the model's own references into those ids in depends_on.
- If the JSON is broken, or a type is missing or unknown: retry once, then fall
  back to a fixed template with one task per type.
- Expect at least one task for each of the four types.
"""

from dap.shared.schemas import TaskCreate


def decompose(requirement_text: str) -> list[TaskCreate]:
    """Return the tasks for one requirement document."""
    raise NotImplementedError("S1-06: implement decompose()")
