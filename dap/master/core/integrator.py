"""Writes the generated application into workspace/<project_id>/ (a git repository).

Owner: Baran - Sprint 3 (contract section 12).

    prepare(project_id)                         copy the template, git init (first use)
    commit_task(project_id, task, agent_id, files)
        write the task's files, commit "<type>: <title> (by <agent_id>)"
    commit_master_file(project_id, path, content, message)
        a file the master writes itself (acceptance.json), with its own commit
    list_files(project_id) -> list[str]         relative paths, without .git
    read_file(project_id, path) -> str          ValueError for a path outside the folder

Paths are checked with dap.master.db.workspace.check_paths and must stay inside
the project folder. Without git the files are still written, with a warning.
"""

import logging
import shutil
import subprocess
import threading
from pathlib import Path

from dap.master.db.workspace import check_paths
from dap.shared.enums import TaskType
from dap.shared.schemas import GeneratedFile, Task

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT / "workspace"  # never committed (.gitignore); tests replace it
TEMPLATE_DIR = REPO_ROOT / "templates" / "webapp"

# The files each task type fills (contract section 12, decision D8).
TEMPLATE_FILES: dict[TaskType, list[str]] = {
    TaskType.DATABASE: ["backend/database.py"],
    TaskType.BACKEND: ["backend/main.py"],
    TaskType.FRONTEND: ["frontend/index.html"],
    TaskType.TESTING: ["tests/test_app.py"],
}

_lock = threading.Lock()  # tasks finish in parallel; writes and commits go one by one


def project_dir(project_id: str) -> Path:
    return WORKSPACE_ROOT / project_id


def _git(folder: Path, *args: str) -> bool:
    """Run one git command in the folder; False (with a warning) when git is missing or fails."""
    if shutil.which("git") is None:
        logger.warning("git is not installed: files are written without commits")
        return False
    command = ["git", "-c", "user.name=DAP master", "-c", "user.email=dap-master@localhost",
               *args]
    result = subprocess.run(command, cwd=folder, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("git %s failed in %s: %s", args[0], folder, result.stderr.strip())
        return False
    return True


def prepare(project_id: str) -> Path:
    """Create the project folder from the template and make it a git repository."""
    folder = project_dir(project_id)
    with _lock:
        if not folder.exists():
            if TEMPLATE_DIR.is_dir():
                shutil.copytree(TEMPLATE_DIR, folder)
            else:
                folder.mkdir(parents=True)
        if not (folder / ".git").exists():
            _git(folder, "init", "--quiet")
    return folder


def _target(folder: Path, path: str) -> Path:
    target = (folder / path).resolve()
    if not target.is_relative_to(folder.resolve()):
        raise ValueError(f"path outside the project folder: {path!r}")
    return target


def commit_task(project_id: str, task: Task, agent_id: str, files: list[GeneratedFile]) -> None:
    """Write a completed task's files and commit them (one commit per task)."""
    check_paths(files)
    folder = prepare(project_id)
    with _lock:
        targets = [(_target(folder, file.path), file.content) for file in files]
        for target, content in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        if _git(folder, "add", "--all"):
            _git(folder, "commit", "--quiet", "--allow-empty", "-m",
                 f"{task.type.value}: {task.title} (by {agent_id})")


def commit_master_file(project_id: str, path: str, content: str, message: str) -> None:
    """Write one file of the master's own (acceptance.json) and commit it."""
    folder = prepare(project_id)
    with _lock:
        target = _target(folder, path)
        target.write_text(content, encoding="utf-8", newline="\n")
        if _git(folder, "add", "--", path):
            _git(folder, "commit", "--quiet", "-m", message)


def list_files(project_id: str) -> list[str]:
    folder = project_dir(project_id)
    if not folder.is_dir():
        return []
    return sorted(
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(folder).parts
    )


def read_file(project_id: str, path: str) -> str:
    """The text of one generated file. ValueError: outside the folder; FileNotFoundError."""
    folder = project_dir(project_id)
    target = _target(folder, path)
    if ".git" in target.relative_to(folder.resolve()).parts or not target.is_file():
        raise FileNotFoundError(path)
    return target.read_text(encoding="utf-8", errors="replace")
