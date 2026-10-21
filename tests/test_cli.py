from fastapi.testclient import TestClient

from dap.master import cli
from dap.master.api import projects
from dap.master.main import app

client = TestClient(app)


def test_agents_command_prints_a_table(capsys, monkeypatch):
    assert cli.main(["agents"], client=client) == 0
    out = capsys.readouterr().out
    assert "agent" in out or "No agents registered" in out


def test_project_command_decomposes_and_assigns(capsys, monkeypatch):
    from dap.master.db import repositories
    from dap.shared.schemas import AgentRegister, Capabilities

    agent = repositories.upsert_agent(AgentRegister(
        agent_id="cli-agent", name="cli", owner="t", model="m",
        capabilities=Capabilities(coding=70, reasoning=70, context=70),
    ))
    monkeypatch.setattr(projects.repositories, "list_agents", lambda: [agent])
    code = cli.main(["project", "A library app where members borrow books.", "--name", "Lib"],
                    client=client)
    out = capsys.readouterr().out
    assert code == 0
    assert "Build REST API" in out and "cli-agent" in out and "S=" in out


def test_project_command_reports_server_errors(monkeypatch):
    import pytest

    with pytest.raises(SystemExit) as exc:
        cli.main(["project", "short"], client=client)
    assert "422" in str(exc.value)
