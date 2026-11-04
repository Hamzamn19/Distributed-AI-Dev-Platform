"""Runs before any test module is imported.

Keeps tests away from the real database (data/dap.db) and from a real LLM.
"""

import os
from pathlib import Path

TEST_DB = Path("data/test.db")
TEST_DB.parent.mkdir(exist_ok=True)
TEST_DB.unlink(missing_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB.as_posix()}"
os.environ["LLM_MOCK"] = "1"


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _private_workspace(tmp_path, monkeypatch):
    """POST /projects copies the template into the workspace: keep it out of the repo."""
    from dap.master.api import tasks as tasks_api

    monkeypatch.setattr(tasks_api, "workspace_root", tmp_path / "workspace")
