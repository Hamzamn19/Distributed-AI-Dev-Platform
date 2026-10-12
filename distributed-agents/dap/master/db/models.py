"""SQLAlchemy ORM tables.

Owner: Can - card S1-09.

Sprint 1 tables (docs/PROJECT_CONTRACT.md, section 8):

    agents    agent_id (PK), name, owner, role_hint, model, provider,
              cap_coding, cap_reasoning, cap_context, status,
              current_task_id, registered_at, last_heartbeat_at
    projects  id (PK), name, requirement_text, status, created_at, updated_at
    tasks     id (PK), project_id (FK), title, description, type, status,
              depends_on (JSON), assigned_agent_id (FK, nullable),
              assignment_reason, attempt, created_at, updated_at

"type" and "status" columns accept only the values in dap.shared.enums.
ORM objects never leave this package: repositories.py converts them to the
models in dap.shared.schemas.
"""
