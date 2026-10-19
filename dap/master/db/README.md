# Master database (S1-09, S2-05)

Owner: Can. This package stores the platform's agents, projects and tasks.
It follows `docs/contracts/PROJECT_CONTRACT.md`; API/core code calls repository
functions and does not handle SQLAlchemy sessions directly.

## Status

- `database.py`, the three ORM tables and all 13 repository functions are implemented.
- 21 database tests cover registration, heartbeats, projects/tasks, assignment,
  constraints, atomic rollback and persistence across separate processes.
- S2-05 agent/project checks additionally verify busy-agent re-registration,
  refreshed heartbeats preventing stale detection, and isolated project status updates.
- `docs/database.md` contains the ER diagram and sample queries.
- Master API wiring belongs to Baran and is not changed by this card.

## Setup and run

From the repository root, install the existing `requirements.txt` into `.venv`.
The database address comes from `get_settings().database_url`, which reads
`DATABASE_URL`. Its current configured default is `sqlite:///./data/dap.db`.

```powershell
.\.venv\Scripts\python.exe -c "from dap.master.db import repositories; print(repositories.list_agents())"
.\.venv\Scripts\python.exe -m pytest tests/test_repositories.py -q
```

Importing `repositories` calls `init_db()` once, creating missing tables and the
SQLite parent directory. It never drops tables or clears existing records.
Restart the process after changing `DATABASE_URL`.

## Input and output

Inputs and returned records are the Pydantic models in `dap/shared/schemas.py`.
Every function owns its session. Writes commit on success and roll back on
failure. SQLite foreign keys are enabled. Enum columns also have database CHECK
constraints so direct SQL cannot store an invented status or task type.

Timestamps are stored as UTC. SQLite removes timezone information, so each read
restores UTC before returning shared models. Agent capability scores map to
the three `cap_*` columns.

Repeated registration refreshes metadata and heartbeat, resets the agent to
`idle` with no current task, and preserves its first `registered_at` value.
Unknown agent lookup returns `None`; an unknown heartbeat returns `False`.
Stale detection counts agents that changed to `offline`; an agent with no
heartbeat is checked against its registration time.

Projects receive UUID4 IDs and initially have status `created`. Tasks retain
the IDs supplied by the master and initially have status `pending`. A task
batch is stored in one transaction, so a duplicate ID rolls back the whole
batch. Assignment stores the chosen agent, reason and status `assigned`.
Getters return `None` for missing IDs. Writes that require a missing parent
or record raise `ValueError`; database constraint violations raise SQLAlchemy
exceptions. Selection belongs to the master; workers execute tasks in later sprints.

Full database documentation: [`docs/database.md`](../../../docs/database.md).

## Local environment note

Verified with Python 3.12 and SQLAlchemy 2.0.54. During local setup, installing
`PyYAML==6.0.2` first resolved the `uvicorn[standard]` dependency resolver error.
It satisfies the existing requirements; no shared dependency file was changed.

`data/` is local runtime data and is excluded from Git. Tests use an isolated
test database and never open `data/dap.db`.
