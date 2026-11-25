"""Every file an agent wrote starts with a comment naming that agent (integrator.author_line)."""

import subprocess
import sys
from datetime import datetime, timezone

from dap.master.core import integrator
from dap.shared.enums import AgentStatus, TaskStatus, TaskType
from dap.shared.schemas import Agent, Capabilities, Task

NOW = datetime(2026, 11, 22, 21, 40, tzinfo=timezone.utc)
LINE = 'Written by agent-eray (Eray-PC, model qwen2.5-coder:7b) - database task "Schema", 2026-11-22 21:40 UTC'


def task(title="Schema", kind=TaskType.DATABASE):
    return Task(id="t", project_id="p", title=title, description="", type=kind,
                status=TaskStatus.COMPLETED, created_at=NOW, updated_at=NOW)


def agent():
    return Agent(agent_id="agent-eray", name="Eray-PC", owner="Eray", role_hint=None,
                 model="qwen2.5-coder:7b", provider="ollama",
                 capabilities=Capabilities(coding=80, reasoning=55, context=70),
                 status=AgentStatus.IDLE, current_task_id=None, registered_at=NOW,
                 last_heartbeat_at=NOW, a2a_url=None)


def test_the_line_names_agent_model_task_and_time():
    assert integrator.author_line(task(), "agent-eray", agent(), NOW) == LINE
    assert integrator.author_line(task(), "agent-eray", None, NOW).startswith(
        "Written by agent-eray - database task")


def test_each_kind_of_file_gets_its_own_comment_syntax():
    w = lambda path, content: integrator.with_author(path, content, LINE)
    assert w("backend/database.py", "x = 1\n") == f"# {LINE}\nx = 1\n"
    assert w("frontend/app.js", "let a;\n") == f"// {LINE}\nlet a;\n"
    assert w("frontend/style.css", "a{}\n") == f"/* {LINE} */\na{{}}\n"
    assert w("README.md", "# App\n") == f"<!-- {LINE} -->\n# App\n"
    assert w("requirements.txt", "fastapi\n") == f"# {LINE}\nfastapi\n"
    assert w("acceptance.json", "{}") == "{}"  # JSON has no comments


def test_html_keeps_its_doctype_first():
    page = "<!doctype html>\n<html><body>Hi</body></html>\n"
    assert integrator.with_author("frontend/index.html", page, LINE) == (
        f"<!doctype html>\n<!-- {LINE} -->\n<html><body>Hi</body></html>\n")


def test_a_title_from_the_model_cannot_break_the_comment():
    line = integrator.author_line(task("Pages */ -->\nmore"), "a1", None, NOW)
    assert "*/" not in line and "-->" not in line and "\n" not in line


def test_a_python_file_with_its_comment_still_runs(tmp_path):
    source = integrator.with_author("app.py", '"""Doc."""\nprint(__doc__)\n', LINE)
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    result = subprocess.run([sys.executable, str(tmp_path / "app.py")], capture_output=True, text=True)
    assert result.stdout.strip() == "Doc."  # the docstring is still the module's docstring
