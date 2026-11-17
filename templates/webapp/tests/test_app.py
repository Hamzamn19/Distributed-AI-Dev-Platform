"""Tests of the generated application. Run from the application folder:

    python -m pytest

Filled by: the TESTING task.
Relies on: the /api routes of backend/main.py (and so on backend/database.py).

Rules every agent follows:
- Keep everything above the line "--- write below this line ---" unchanged: the tests use
  a fresh database file of their own, never app.db.
- Use the `client` below; do not start a server.
- The master's acceptance check already tries list, search, create, get, update and
  delete of every record type. Here: one short test per record type (create answers 201,
  the new record is in the list), then what only the requirement says:
- One test per business rule and action of the requirement (a broken rule answers 400).
- Use only routes and fields that backend/main.py really has.
- Each test creates the data it needs; tests must not depend on each other's order.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the application folder

from fastapi.testclient import TestClient  # noqa: E402

from backend import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"  # before the app creates its tables

from backend.main import app  # noqa: E402

client = TestClient(app)


# --- write below this line ---
# def test_...():
