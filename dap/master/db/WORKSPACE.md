# Generated file storage — S2-05 local increment

On 21 October, Can selected this layout for implementation:

```text
workspace/
  <project_id>/
    <run_id>/
      db/schema.sql
      backend/main.py
```

This is an explicit local design decision. The current shared contract says
`workspace/<project_id>/`, while issue #25/member guide say `workspace/<run-id>/`.
The team contract and Master integration still need to adopt the selected layout.

## Function

```python
save_generated_files(project_id, run_id, files, *, workspace_root) -> list[Path]
```

Import from `dap.master.db.workspace`. `files` contains the existing shared
`GeneratedFile` objects; no shared JSON schema or endpoint was changed.
The root is an explicit argument so no new environment/configuration setting is
invented. The caller supplies its configured workspace location.

## Run lifecycle for the Master integration

- Master should create a UUID4 once when a project execution starts.
- All tasks in that execution use the same run ID. A task retry keeps that ID.
- Starting a new execution uses a new ID, preserving earlier output.
- These lifecycle steps are integration requirements; this module does not
  implement or persist a run registry. The existing TaskResult has no run ID;
  the Master must retain or resolve it before calling this function.

## Existing files and failures

- Files are UTF-8 text and are never executed by this module.
- An identical repeat is a no-op, preserving the existing file.
- Different content at an existing path raises FileExistsError. A later attempt
  producing revised content needs an explicit policy before overwriting is allowed.
- Relative paths can contain subdirectories. Absolute paths, traversal, filesystem
  links, Windows special names and duplicate/overlapping paths are rejected.
- Paths and existing contents are checked before any writes. This is not a
  multi-file transaction: an OS error during writing can leave partial output.
  The caller must report the failure and must not mark that result completed.
- The caller serializes writes to an execution. Concurrent writes and database/file
  atomicity are not implemented in this increment.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_workspace.py -q
```

Tests use real temporary files, including a separate process reading saved output.
No model, remote Master, Tailscale or new dependency is needed.
