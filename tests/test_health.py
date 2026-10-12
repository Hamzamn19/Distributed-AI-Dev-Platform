from fastapi.testclient import TestClient

from dap import __version__
from dap.master.main import app

client = TestClient(app)


def test_health_returns_ok_and_version():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_api_docs_are_served():
    assert client.get("/docs").status_code == 200
