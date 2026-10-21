from fastapi.testclient import TestClient

from dap.master.config import get_settings
from dap.master.main import app
from dap.shared.schemas import Agent

client = TestClient(app)

REGISTER = {
    "agent_id": "reg-agent",
    "name": "Reg PC",
    "owner": "Tester",
    "role_hint": "backend",
    "model": "qwen3:4b",
    "provider": "ollama",
    "capabilities": {"coding": 60, "reasoning": 50, "context": 40},
}


def _auth() -> dict:
    return {"X-Agent-Token": get_settings().agent_token}


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


def test_register_and_heartbeat_need_the_token():
    for headers in ({}, {"X-Agent-Token": "wrong"}):
        r = client.post("/api/v1/agents/register", json=REGISTER, headers=headers)
        assert r.status_code == 401
        assert "detail" in r.json()
        r = client.post("/api/v1/agents/reg-agent/heartbeat",
                        json={"status": "idle"}, headers=headers)
        assert r.status_code == 401


def test_register_returns_agent_and_it_appears_in_the_list():
    response = client.post("/api/v1/agents/register", json=REGISTER, headers=_auth())
    assert response.status_code == 200
    agent = Agent.model_validate(response.json())
    assert agent.agent_id == "reg-agent" and agent.status == "idle"
    listed = client.get("/api/v1/agents").json()
    assert "reg-agent" in [a["agent_id"] for a in listed]


def test_registering_twice_updates_the_record():
    client.post("/api/v1/agents/register", json=REGISTER, headers=_auth())
    changed = dict(REGISTER, model="llama3.1", capabilities={"coding": 90, "reasoning": 80, "context": 70})
    response = client.post("/api/v1/agents/register", json=changed, headers=_auth())
    assert response.status_code == 200
    assert response.json()["model"] == "llama3.1"
    ids = [a["agent_id"] for a in client.get("/api/v1/agents").json()]
    assert ids.count("reg-agent") == 1


def test_register_rejects_unknown_fields():
    body = dict(REGISTER, surprise=1)
    assert client.post("/api/v1/agents/register", json=body, headers=_auth()).status_code == 422


def test_heartbeat_updates_status_and_returns_ok():
    client.post("/api/v1/agents/register", json=REGISTER, headers=_auth())
    response = client.post("/api/v1/agents/reg-agent/heartbeat",
                           json={"status": "busy", "current_task_id": None}, headers=_auth())
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    agents = {a["agent_id"]: a for a in client.get("/api/v1/agents").json()}
    assert agents["reg-agent"]["status"] == "busy"


def test_heartbeat_of_unknown_agent_gives_404():
    response = client.post("/api/v1/agents/nobody/heartbeat",
                           json={"status": "idle"}, headers=_auth())
    assert response.status_code == 404
    assert "detail" in response.json()
