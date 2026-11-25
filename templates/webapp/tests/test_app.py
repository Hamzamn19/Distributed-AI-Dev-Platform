"""Tests of the generated application. Run from the application folder:

    python -m pytest

Filled by: the TESTING task.
Relies on: the /api routes of backend/main.py (and so on backend/database.py).

Rules every agent follows:
- Keep everything above the line "--- write below this line ---" unchanged. The ready
  tests/conftest.py gives the tests a fresh database file of their own (never app.db)
  and a `client` fixture: use the `client` below, or take it as a parameter
  (def test_x(client): ...). Do not start a server and do not write a conftest.py.
- The master's acceptance check already tries list, search, create, get, update and
  delete of every record type. Here: one short test per record type (create answers 201,
  the new record is in the list), then what only the requirement says:
- One test per business rule and action of the requirement (a broken rule answers 400).
- Use only routes and fields that backend/main.py really has.
- Each test creates the data it needs; tests must not depend on each other's order.
"""

from fastapi.testclient import TestClient

from backend.main import app  # tests/conftest.py has already pointed it at a test database

client = TestClient(app)


# --- write below this line ---
# def test_...():
