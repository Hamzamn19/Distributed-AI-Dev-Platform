#!/usr/bin/env python3
"""Log background-chat task failures instead of losing them silently.

Stock `create_task` registers only a cleanup callback. If the chat coroutine
raises, the exception is never retrieved: no assistant message, no log line,
and the UI sits on "Loading..." forever while the task list reports nothing.

This inserts a done-callback that logs the exception (or a short OK note), so a
failed background generation is diagnosable from the journal.

It is idempotent: running it against an already-patched file changes nothing.

    python3 03-task-failure-log.py /path/to/site-packages
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

MARKER = "_report_failure"

OLD_BLOCK = """    task = asyncio.create_task(coroutine)  # Create the task

    # Add a done callback for cleanup
    task.add_done_callback(lambda t: asyncio.create_task(cleanup_task(redis, task_id, id)))
"""

NEW_BLOCK = """    task = asyncio.create_task(coroutine)  # Create the task

    # Report failures first. Without this, an exception raised inside the
    # coroutine is never retrieved (cleanup_task does not touch it), so the task
    # just vanishes: no assistant message, no log line, nothing to diagnose.
    def _report_failure(done_task, _task_id=task_id):
        if done_task.cancelled():
            log.error('Background chat task %s was cancelled', _task_id)
            return
        exc = done_task.exception()
        if exc is not None:
            log.error('Background chat task %s failed: %r', _task_id, exc, exc_info=exc)

    task.add_done_callback(_report_failure)
    # Add a done callback for cleanup
    task.add_done_callback(lambda t: asyncio.create_task(cleanup_task(redis, task_id, id)))
"""


def main(site_packages: str) -> int:
    target = Path(site_packages) / "open_webui" / "tasks.py"
    if not target.is_file():
        print(f"  FAIL: not found: {target}")
        return 1

    src = target.read_text(encoding="utf-8")

    if MARKER in src:
        print("  already up to date — nothing to do")
        return 0

    if OLD_BLOCK not in src:
        print("  FAIL: create_task block not recognised — Open WebUI changed this file")
        return 1

    src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

    ast.parse(src)
    target.write_text(src, encoding="utf-8")
    print("  - create_task now logs background failures")
    print(f"  wrote {target}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
