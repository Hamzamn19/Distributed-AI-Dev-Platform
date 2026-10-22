"""Worker registration and heartbeat against the real master app (no network)."""

import httpx
from fastapi.testclient import TestClient

from dap.master.db import repositories
from dap.master.main import app
from dap.shared.enums import AgentStatus
from dap.worker import config, main as worker


def _settings(monkeypatch, agent_id: str, token: str | None = None):
    monkeypatch.setenv("AGENT_ID", agent_id)
    monkeypatch.setenv("AGENT_NAME", f"{agent_id}-PC")
    monkeypatch.setenv("AGENT_OWNER", "Test")
    monkeypatch.setenv("AGENT_ROLE_HINT", "backend")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SEC", "0")
    if token is not None:
        monkeypatch.setenv("AGENT_TOKEN", token)
    return config.get_settings()


_master = TestClient(app)


def _master_client() -> httpx.Client:
    """A real httpx.Client (as the worker uses) whose requests go to the master app.

    TestClient itself is built on httpx2, so its errors are not httpx errors.
    """

    def forward(request: httpx.Request) -> httpx.Response:
        answer = _master.request(
            request.method, request.url.raw_path.decode(),
            content=request.content, headers=dict(request.headers),
        )
        return httpx.Response(answer.status_code, headers=answer.headers, content=answer.content)

    return httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(forward))


class StopAfter:
    """A stop event that is set after `rounds` waits."""

    def __init__(self, rounds: int):
        self.rounds = rounds

    def is_set(self) -> bool:
        return self.rounds <= 0

    def wait(self, _timeout: float) -> None:
        self.rounds -= 1


def test_register_then_heartbeat(monkeypatch):
    settings = _settings(monkeypatch, "worker-test-a")
    client = _master_client()
    worker.register(client, settings)
    assert repositories.get_agent("worker-test-a").status == AgentStatus.IDLE

    assert worker.send_heartbeat(client, settings, AgentStatus.BUSY, "task-1")
    agent = repositories.get_agent("worker-test-a")
    assert agent.status == AgentStatus.BUSY
    assert agent.current_task_id == "task-1"


def test_heartbeat_of_unregistered_worker_returns_false(monkeypatch):
    settings = _settings(monkeypatch, "worker-test-unknown")
    assert not worker.send_heartbeat(_master_client(), settings, AgentStatus.IDLE, None)


def test_run_registers_and_registers_again_after_a_404(monkeypatch):
    settings = _settings(monkeypatch, "worker-test-b")
    client = _master_client()
    calls = []
    original = worker.send_heartbeat

    def first_heartbeat_unknown(*args):
        calls.append(args)
        return False if len(calls) == 1 else original(*args)

    monkeypatch.setattr(worker, "send_heartbeat", first_heartbeat_unknown)
    registrations = []
    real_register = worker.register

    def counting_register(c, s):
        registrations.append(s.agent_id)
        real_register(c, s)

    monkeypatch.setattr(worker, "register", counting_register)
    worker.run(client, settings, StopAfter(3))
    assert registrations == ["worker-test-b", "worker-test-b"]
    assert len(calls) == 2


def test_wrong_token_is_logged_and_does_not_crash(monkeypatch, caplog):
    settings = _settings(monkeypatch, "worker-test-c", token="wrong-token")
    monkeypatch.setenv("AGENT_TOKEN", "the-master-token")  # the master reads this one
    worker.run(_master_client(), settings, StopAfter(1))
    assert "wrong AGENT_TOKEN" in caplog.text
    assert repositories.get_agent("worker-test-c") is None


def test_unreachable_master_is_logged_and_does_not_crash(monkeypatch, caplog):
    settings = _settings(monkeypatch, "worker-test-d")

    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(base_url="http://master.invalid", transport=httpx.MockTransport(refuse))
    worker.run(client, settings, StopAfter(2))
    assert "Cannot reach the master" in caplog.text


def test_env_file_replaces_dotenv_values(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_ID", "from-environment")
    env_file = tmp_path / ".env.worker1"
    env_file.write_text("AGENT_ID=agent-from-file\nWORKER_TEST_ONLY=1\n", encoding="utf-8")
    monkeypatch.delenv("WORKER_TEST_ONLY", raising=False)
    config.load_env(str(env_file))
    assert config.get_settings().agent_id == "agent-from-file"
    monkeypatch.delenv("WORKER_TEST_ONLY")


def test_missing_env_file_stops_with_a_message(tmp_path):
    import pytest

    with pytest.raises(SystemExit, match="Env file not found"):
        config.load_env(str(tmp_path / "missing.env"))
