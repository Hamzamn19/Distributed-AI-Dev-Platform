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

import httpx  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture
def master_http() -> httpx.Client:
    """A real httpx.Client whose requests go to the master app, without a network.

    Workers and scripts use httpx; FastAPI's TestClient is built on httpx2, whose
    errors are not httpx errors, so TestClient cannot stand in for their client.
    """
    from fastapi.testclient import TestClient

    from dap.master.main import app

    master = TestClient(app)

    def forward(request: httpx.Request) -> httpx.Response:
        answer = master.request(
            request.method, request.url.raw_path.decode(),
            content=request.content, headers=dict(request.headers),
        )
        return httpx.Response(answer.status_code, headers=answer.headers, content=answer.content)

    return httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(forward))
