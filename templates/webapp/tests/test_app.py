"""Tests of the generated application. Run from the application folder:

    python -m pytest

Filled by: the TESTING task.
Relies on: the /api routes of backend/main.py (and so on backend/database.py).

Rules every agent follows:
- Use fastapi.testclient.TestClient(app); do not start a server.
- One test function per route or rule of the requirement; check the status code
  and the important fields of the answer.
- Tests must not depend on each other's order or on data they did not create.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the application folder

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


# def test_...():
