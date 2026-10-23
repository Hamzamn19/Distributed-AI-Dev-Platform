"""scripts/seed_agents.py and scripts/smoke_test.py against the master app (LLM_MOCK=1)."""

import importlib.util
from pathlib import Path

import pytest

from dap.master.db import repositories

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
TOKEN = "change-me-team-secret"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def team_token(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", TOKEN)


def test_seed_registers_the_six_team_agents(master_http):
    ids = _load("seed_agents").seed(master_http, TOKEN)
    assert len(ids) == 6
    for agent_id in ids:
        assert repositories.get_agent(agent_id) is not None


def test_seed_with_a_wrong_token_stops_with_a_message(master_http):
    with pytest.raises(SystemExit, match="401"):
        _load("seed_agents").seed(master_http, "wrong-token")


def test_smoke_passes_against_the_master(master_http):
    lines = []
    _load("smoke_test").smoke(master_http, TOKEN, log=lines.append)
    assert [line.split()[1] for line in lines] == [
        "health", "register", "project", "decompose", "assign", "tasks"]


def test_smoke_names_the_failing_step(master_http):
    smoke = _load("smoke_test")
    with pytest.raises(smoke.StepFailed, match="^register"):
        smoke.smoke(master_http, "wrong-token", log=lambda line: None)


class FakeHttp:
    """Answers like a master and a worker; `down` lists the parts that do not answer."""

    def __init__(self, down=(), token_status=404, card_status=200):
        self.down, self.token_status, self.card_status = down, token_status, card_status

    def _answer(self, url, status):
        import httpx

        return httpx.Response(status, request=httpx.Request("GET", url))

    def get(self, url, timeout):
        import httpx

        if "/api/v1/health" in url:
            if "master" in self.down:
                raise httpx.ConnectError("refused")
            return self._answer(url, 200)
        if "/card" in url:
            return self._answer(url, self.card_status)
        if "worker" in self.down:
            raise httpx.ConnectError("refused")
        return self._answer(url, 200)

    def post(self, url, timeout, json, headers):
        return self._answer(url, self.token_status)


def _check(monkeypatch, **fake):
    check = _load("check_connection")
    monkeypatch.setenv("MASTER_URL", "http://100.64.0.1:8000")
    monkeypatch.setenv("WORKER_PORT", "9000")
    settings = check.config.get_settings()
    return {name: (ok, message) for name, ok, message in
            check.checks(settings, "http://100.64.0.2:9000", "100.64.0.2", http=FakeHttp(**fake))}


def test_check_connection_all_ok(monkeypatch):
    results = _check(monkeypatch)
    assert len(results) == 6 and all(ok for ok, _ in results.values())


def test_check_connection_names_the_likely_fix(monkeypatch):
    assert "MASTER_URL" in _check(monkeypatch, down=("master",))["master health"][1]
    assert "same as in the master" in _check(monkeypatch, token_status=401)["AGENT_TOKEN"][1]
    not_running = _check(monkeypatch, down=("worker",), card_status=502)
    assert "start the worker" in not_running["A2A server on this PC"][1]
    assert "not running" in not_running["master reaches this worker"][1]
    firewall = _check(monkeypatch, card_status=502)["master reaches this worker"]
    assert not firewall[0] and "Firewall" in firewall[1]
