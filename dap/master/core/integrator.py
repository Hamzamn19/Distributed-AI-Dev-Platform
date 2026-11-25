"""Writes the generated application into workspace/<project_id>/ (a git repository).

Owner: Baran - Sprint 3 (contract section 12).

    prepare(project_id)                         copy the template, git init (first use)
    commit_task(project_id, task, agent_id, files, agent=None)
        write the task's files, commit "<type>: <title> (by <agent_id>)"; every file
        starts with a comment saying which agent (and model) wrote it (author_line)
    commit_master_file(project_id, path, content, message)
        a file the master writes itself (acceptance.json), with its own commit
    list_files(project_id) -> list[str]         relative paths, without .git
    read_file(project_id, path) -> str          ValueError for a path outside the folder

Paths are checked with dap.master.db.workspace.check_paths and must stay inside
the project folder. Without git the files are still written, with a warning.
"""

import io
import logging
import re
import shutil
import subprocess
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dap.master.db.workspace import check_paths
from dap.shared.enums import TaskType
from dap.shared.schemas import Agent, GeneratedFile, Task

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


# The comment syntax of each kind of file the agents write: (start, end).
_COMMENT = {".py": ("# ", ""), ".txt": ("# ", ""), ".js": ("// ", ""), ".css": ("/* ", " */"),
            ".html": ("<!-- ", " -->"), ".md": ("<!-- ", " -->")}


def author_line(task: Task, agent_id: str, agent: Agent | None = None,
                when: datetime | None = None) -> str:
    """'Written by agent-eray (Eray-PC, model qwen2.5-coder:7b) - database task "...", <time>'."""
    who = f"{agent_id} ({agent.name}, model {agent.model})" if agent else agent_id
    # A title comes from the model: nothing in it may close the comment or break the line.
    title = " ".join(task.title.split()).replace("*/", "*").replace("--", "-")
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    return f'Written by {who} - {task.type.value} task "{title}", {stamp}'


def with_author(path: str, content: str, line: str) -> str:
    """The file with the author comment as its first line (in HTML after the doctype)."""
    suffix = Path(path).suffix.lower()
    if suffix not in _COMMENT:
        return content
    start, end = _COMMENT[suffix]
    comment = f"{start}{line}{end}\n"
    keep_first = (suffix == ".html" and content.lstrip().lower().startswith("<!doctype")
                  or suffix == ".py" and content.startswith("#!"))
    if keep_first:
        first, _, rest = content.lstrip().partition("\n")
        return f"{first}\n{comment}{rest}"
    return comment + content


def commit_task(project_id: str, task: Task, agent_id: str, files: list[GeneratedFile],
                agent: Agent | None = None) -> None:
    """Write a completed task's files, each with its author comment, and commit them."""
    check_paths(files)
    folder = prepare(project_id)
    line = author_line(task, agent_id, agent)
    with _lock:
        targets = [(_target(folder, file.path), with_author(file.path, file.content, line))
                   for file in files]
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


RUNTIME_JUNK = {"app.db", "acceptance-check"}  # never inside the export


def export_zip(project_id: str) -> tuple[bytes, str]:
    """The generated application as one zip; (content, suggested filename).

    The application files, the templates' helpers (db.py, lib.js, style.css) and
    acceptance.json are inside; .git, app.db and __pycache__ are not. FileNotFoundError:
    the project has no files yet.
    """
    folder = project_dir(project_id)
    if not folder.is_dir() or not any(path.is_file() for path in folder.rglob("*")):
        raise FileNotFoundError(f"project {project_id!r} has no files yet")
    from dap.master.db import repositories  # only for the suggested name; no cycle at import
    project = repositories.get_project(project_id)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", (project.name if project else "")).strip("_")[:40]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder)
            if (".git" in relative.parts or "__pycache__" in relative.parts
                    or path.name in RUNTIME_JUNK or not path.is_file()):
                continue
            archive.write(path, arcname=relative.as_posix())
    return buffer.getvalue(), f"{name or 'generated-app'}.zip"
