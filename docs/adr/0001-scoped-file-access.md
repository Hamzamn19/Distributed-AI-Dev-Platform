# ADR 0001: Give the model one scoped folder instead of a shell

- Date: 2026-10-07
- Card: local AI assistant file access
- Status: accepted

## What we tried

The shared Gemma assistant needs to work with files on this machine. Three options:

1. **Jupyter tool** — Open WebUI ships one; the model writes and runs Python.
2. **Shell tool** — direct command execution.
3. **Custom `project_files` tool** — four operations (list, read, write, edit)
   behind a path resolver that refuses anything outside one directory.

## Result

Option 1 was rejected before building: a Jupyter kernel can run `os.system`, so it
is a shell under a different name, and the requirement was explicitly one project
folder and no shell. Option 2 is the requirement stated backwards.

Option 3 was built and tested with six escape attempts — `../.bashrc`,
`../../.ssh/id_rsa`, `/etc/shadow`, `list ../..`, `write /etc/cron.d/pwn`,
`edit /home/hamzah/.bashrc`. All six were refused, and no file was created outside
the folder. Absolute paths are resolved *inside* the root rather than trusted, so
`/etc/shadow` becomes `project-files/etc/shadow` and simply does not exist.

The tool does not modify anything — `write` and `edit` go through the resolver first.

## Decision (keep it / use the fallback)

**Keep the custom tool.** The model reads and edits exactly one folder, has no
shell, and the boundary is enforced in code rather than by a prompt instruction.
Root is `local-stack/project-files/`.
