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
