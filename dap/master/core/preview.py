"""Runs one generated application on the master PC, for "Open the app" in the UI.

Owner: Baran - Sprint 3.

    start(project_id) -> int     the port; stops the application that ran before
    stop()                       also called when the master exits
    running() -> str | None      the project whose application runs now

The application of workspace/<project_id>/ is started as `uvicorn backend.main:app`
on PREVIEW_PORT (all addresses, so every PC on the tailnet can open it). Only one
application runs at a time. It keeps its own app.db in its folder (.gitignore of the
generated application), so what users add in the browser stays there.
"""

import atexit
import os
import subprocess
import sys
import threading
import time

import httpx

from dap.master.config import get_settings
from dap.master.core import integrator

START_TIMEOUT_SEC = 20


class PreviewError(Exception):
    """The application could not start; the message says why."""


_lock = threading.Lock()
_process: subprocess.Popen | None = None
_project: str | None = None
_log = None


def running() -> str | None:
    with _lock:
        return _project if _process is not None and _process.poll() is None else None


def stop() -> None:
    global _process, _project, _log
    with _lock:
        if _process is not None and _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(10)
            except subprocess.TimeoutExpired:
                _process.kill()
        if _log is not None:
            _log.close()
        _process, _project, _log = None, None, None


atexit.register(stop)


def _last_lines(path, count: int = 6) -> str:
    try:
        lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.strip()]
    except OSError:
        return ""
    return "\n".join(lines[-count:])


def start(project_id: str, port: int | None = None) -> int:
    """Start the project's application (stopping the one before) and wait until it answers."""
    global _process, _project, _log
    folder = integrator.project_dir(project_id)
    if not (folder / "backend" / "main.py").is_file():
        raise FileNotFoundError("the project has no backend/main.py yet")
    port = port or get_settings().preview_port
    stop()
    log_path = folder.parent / f".preview-{project_id}.log"  # outside the project's git folder
    with _lock:
        _log = open(log_path, "w", encoding="utf-8")
        _process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0",
             "--port", str(port)],
            cwd=folder, stdout=_log, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        _project = project_id
        process = _process
    end = time.monotonic() + START_TIMEOUT_SEC
    while time.monotonic() < end:
        if process.poll() is not None:
            stop()
            raise PreviewError("the application stopped at start:\n" + _last_lines(log_path))
        try:
            if httpx.get(f"http://127.0.0.1:{port}/", timeout=2).status_code < 500:
                return port
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    stop()
    raise PreviewError(f"the application did not answer within {START_TIMEOUT_SEC} s:\n"
                       + _last_lines(log_path))
