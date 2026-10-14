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
