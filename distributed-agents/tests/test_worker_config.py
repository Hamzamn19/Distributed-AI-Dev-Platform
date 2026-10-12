from dap.worker.config import get_settings


def test_worker_settings_build_a_valid_register_payload(monkeypatch):
    monkeypatch.setenv("MASTER_URL", "http://100.64.0.1:8000/")
    monkeypatch.setenv("AGENT_ID", "agent-test")
    monkeypatch.setenv("AGENT_NAME", "Test-PC")
    monkeypatch.setenv("AGENT_OWNER", "Test")
    monkeypatch.setenv("AGENT_ROLE_HINT", "backend")
    monkeypatch.setenv("LLM_MODEL", "some-model:4b")
    monkeypatch.setenv("AGENT_CAP_CODING", "70")

    settings = get_settings()
    payload = settings.to_register_payload()

    assert settings.api_url == "http://100.64.0.1:8000/api/v1"
    assert payload.agent_id == "agent-test"
    assert payload.role_hint == "backend"
    assert payload.model == "some-model:4b"
    assert payload.capabilities.coding == 70
