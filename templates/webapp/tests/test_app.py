"""Tests of the generated application. Run from the application folder:

    python -m pytest

Filled by: the TESTING task.
Relies on: the /api routes of backend/main.py (and so on backend/database.py).

Rules every agent follows:
- Keep everything above the line "--- write below this line ---" unchanged: the tests use
  a fresh database file of their own, never app.db.
- Use the `client` below; do not start a server.
- For every record type: create (201), list (the new record is in it), search, get one,
  get a missing id (404), update, delete (204, then 404); post invalid data (422).
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
