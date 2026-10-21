# Events and results — S2-05 local implementation

This increment implements the two tables listed in issue #25. The original 13
repository signatures and shared TaskResult JSON shape remain unchanged.
The following additive helpers and event types are local interfaces for review;
Baran/Okan must adopt them in the Master integration and shared contract.

## Tables

- `events`: UUID id, optional project/task/agent references, type, message, UTC timestamp.
  Agent-only or platform-wide events need not have project/task references.
- `task_results`: id, task/agent references, success, summary, files JSON, error,
  duration_ms, tokens_used, UTC timestamp. All columns match the contract list.
- Foreign keys are enforced; duration and token counts cannot be negative.
- File JSON retains relative paths and complete text contents, not just disk paths.
- `create_all()` adds the new tables without clearing the original three tables.
  This does not migrate renamed columns or change existing column definitions.

## Calls from the Master

Import helpers from `dap.master.db.results`:

```python
record_event(event_type, message, *, project_id=None, task_id=None, agent_id=None) -> str
store_task_result(data: TaskResult, *, run_id: str, workspace_root: Path) -> TaskResult
get_task_result(task_id: str, *, run_id: str) -> TaskResult | None
list_task_results(task_id: str) -> list[TaskResult]
```

`record_event()` returns the new event ID; result readers return the existing
shared Pydantic model, never SQLAlchemy objects. Invalid record references raise
ValueError. A task event automatically gets its task's project ID; mismatched
project/task context is rejected.

Master supplies a run ID shared by the execution's tasks and its configured
workspace root. No model, address, token or new environment variable is hardcoded.
Master run creation/retention, the HTTP handlers and worker polling are separate
integration work and have not been added here.

## Result processing

1. Validate nonnegative metrics, task existence and assigned agent.
2. Accept a new result only while the task is assigned or in_progress.
3. Flush the result, final task status and event inside one database transaction.
4. Save UTF-8 files to `<root>/<project_id>/<run_id>/`.
5. Commit the transaction only after the file helper succeeds.

Success produces task status `completed` and event `task_completed`; failure
produces `failed` and `task_failed`. Event message JSON contains run_id and summary.
Agent busy/idle heartbeat state and project status are still managed by Master.

## Retries and history

- A deterministic UUID5 primary key derived from task ID + run ID enforces one
  final result per task/run without adding a column to the agreed schema.
- Identical delivery retries return the existing result without another row/event.
  Missing output files can be restored from the unchanged payload on retry.
- A changed final result for the same task/run raises ValueError. This is a
  delivery-retry policy, not an implementation of execution retries or scheduling.
- A newly assigned project execution with a new run ID can store another result
  without overwriting earlier results or files.
- There is no runs registry in this increment. The deterministic ID supports
  lookup when Master provides the run ID; event messages retain run context.

## Failure boundaries

Invalid paths or file-writing errors roll back result/status/event database changes.
An OS error mid-write or a database commit failure can leave uncommitted files.
They are not treated as successful results; identical retry can complete storage.
This is not a cross-resource transaction or a concurrent run writer. The caller
serializes writes per execution and must surface storage errors.

Failed-task retry counts, dependency scheduling, concurrent task claiming, HTTP
status mappings and automatic cleanup are Master integration responsibilities.

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use isolated SQLite/filesystem paths and separate writer/reader processes.
The remote Master and a real LLM are not called.
