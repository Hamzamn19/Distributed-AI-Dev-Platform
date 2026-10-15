from fastapi.testclient import TestClient

from dap.master.main import app
from dap.shared.schemas import Agent

client = TestClient(app)


def test_list_agents_needs_no_token_and_returns_contract_agents():
    response = client.get("/api/v1/agents")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    for entry in body:
        Agent.model_validate(entry)


def test_list_agents_allows_frontend_origin():
    response = client.get("/api/v1/agents", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] in ("*", "http://localhost:5173")
