"""Template copy: gives a new project its starting files.

Owner: Baran - Sprint 3.

    copy_template(project_id) -> Path

Copies the content of templates/webapp/ straight into workspace/<project_id>/.
There is no run folder any more; the agents' files are written over the copy.

POST /projects calls it (dap.master.api.projects.create_project). The workspace
folder is the same one the worker endpoints write to (tasks_api.workspace_root).
"""

import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO_ROOT / "templates" / "webapp"
WORKSPACE_DIR = Path("workspace")  # relative to the working directory, like dap.master.api.tasks

# Run leftovers that must not travel into a new project.
_IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.db", ".venv")


def copy_template(
    project_id: str,
    template_dir: Path | None = None,
    workspace_root: Path | None = None,
) -> Path:
    """Copy the template into <workspace_root>/<project_id>/ and return that folder.

    Raises ValueError for an unsafe project id, FileNotFoundError when the
    template folder does not exist, FileExistsError when the project already
    has a folder (an existing project is never overwritten).
    """
    template_dir = TEMPLATE_DIR if template_dir is None else template_dir
    workspace_root = WORKSPACE_DIR if workspace_root is None else workspace_root
    if not re.fullmatch(r"[A-Za-z0-9_-]+", project_id):
        raise ValueError("Project ID must contain only letters, digits, '-' or '_'")
    if not template_dir.is_dir():
        raise FileNotFoundError(f"Template folder not found: {template_dir}")
    target = workspace_root / project_id
    if target.exists():
        raise FileExistsError(f"Workspace of project {project_id!r} already exists")
    shutil.copytree(template_dir, target, ignore=_IGNORED)
    return target
