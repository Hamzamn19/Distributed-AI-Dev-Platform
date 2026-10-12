"""Project and task endpoints.

Owner: Baran - cards S1-05 and S1-06.

Endpoints to add (paths are relative to /api/v1, see docs/PROJECT_CONTRACT.md):

    POST /projects                 body ProjectCreate -> 201 Project      (S1-05)
        A missing or too short requirement_text gives 422 automatically.
    GET  /projects                                    -> 200 list[Project] (S1-05)
    GET  /projects/{id}                               -> 200 Project, 404  (S1-05)
    GET  /projects/{id}/tasks                         -> 200 list[Task]    (S1-05)
    POST /projects/{id}/decompose                     -> 200 list[Task]    (S1-06)
        Calls dap.master.core.decomposer and stores the tasks.
    POST /projects/{id}/assign                        -> 200 list[Task]    (S1-06)
        Calls dap.master.core.selector; fills assigned_agent_id and
        assignment_reason.

Rules:
- Use only the functions in dap.master.db.repositories. No SQL or session here.
- When the LLM is down or keeps returning broken JSON: answer with a clear
  {"detail": "..."} error, set the project status to "failed", never crash.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["projects"])
