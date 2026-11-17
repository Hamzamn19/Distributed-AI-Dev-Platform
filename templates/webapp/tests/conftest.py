"""Ready test setup of the generated application. Not written by the agents.

Every test run gets a fresh database file of its own (never app.db), and the
`client` fixture, so a test may use the `client` of test_app.py directly or ask
for it as a parameter:

    def test_add(client):
        assert client.post("/api/<things>", json={...}).status_code == 201
"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the application folder

from backend import db  # noqa: E402

db.DB_PATH = Path(tempfile.mkdtemp()) / "test.db"  # before the app creates its tables

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def tables() -> None:
    """The tables exist before every test, even when a test file points db.DB_PATH at
    another file of its own (init_db() may run any number of times)."""
    from backend import database

    database.init_db()
