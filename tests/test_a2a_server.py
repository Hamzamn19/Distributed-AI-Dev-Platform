"""The worker's A2A server and executor (LLM_MOCK=1 from tests/conftest.py)."""

import threading
import time

import pytest
from fastapi.testclient import TestClient

from dap.shared.enums import AgentStatus
from dap.shared.llm_client import LLMResponse
from dap.shared.schemas import DapTaskOutput, GeneratedFile
from dap.worker import config, executor as executor_module
from dap.worker.a2a_server import create_app
from dap.worker.executor import MOCK_FILES, Executor

TOKEN = "worker-test-token"
URL = "http://127.0.0.1:9001"
HEADERS = {"X-Agent-Token": TOKEN, "A2A-Version": "1.0"}

PAYLOAD = {
    "task_id": "task-db",
    "project_id": "project-1",
    "type": "database",
    "title": "Design database schema",
    "description": "Tables for books and members",
    "requirement_text": "A library system where members borrow books.",
    "target_files": ["backend/database.py"],
    "dependency_files": [],
}


def _message(payload=PAYLOAD, title="Design database schema"):
    return {
        "message": {
            "messageId": "m-1", "role": "ROLE_USER", "contextId": payload["project_id"],
            "parts": [{"text": title}, {"data": payload, "mediaType": "application/json"}],
        },
        "configuration": {"returnImmediately": True},
    }


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", TOKEN)
    monkeypatch.setenv("AGENT_ID", "agent-local-1")
    monkeypatch.setenv("AGENT_NAME", "Local-PC")
    monkeypatch.setenv("AGENT_ROLE_HINT", "backend")
    monkeypatch.setenv("LLM_MODEL", "qwen3:4b")
    return config.get_settings()


def _client(settings, executor=None):
    executor = executor or Executor()
    return TestClient(create_app(settings, executor, URL)), executor


def _wait(client, task_id, states=("TASK_STATE_COMPLETED", "TASK_STATE_FAILED")):
    for _ in range(100):
        task = client.get(f"/tasks/{task_id}", headers=HEADERS).json()
        if task["status"]["state"] in states:
            return task
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish: {task}")


def test_agent_card_needs_no_token_and_has_the_contract_shape(settings):
    client, _ = _client(settings)
    card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "agent-local-1"
    assert card["description"] == "DAP worker on Local-PC running qwen3:4b"
    assert card["supportedInterfaces"] == [
        {"url": URL, "protocolBinding": "HTTP+JSON", "protocolVersion": "1.0"}]
    assert card["capabilities"] == {"streaming": False, "pushNotifications": False}
    assert card["defaultInputModes"] == card["defaultOutputModes"] == ["application/json"]
    assert card["skills"][0]["id"] == "backend"


def test_wrong_token_gives_401(settings):
    client, _ = _client(settings)
    wrong = {"X-Agent-Token": "wrong"}
    assert client.post("/message:send", json=_message(), headers=wrong).status_code == 401
    assert client.get("/tasks/anything", headers=wrong).status_code == 401
    assert client.post("/message:send", json=_message()).status_code == 401


def test_send_then_poll_until_completed_with_files(settings):
    client, _ = _client(settings)
    answer = client.post("/message:send", json=_message(), headers=HEADERS)
    assert answer.status_code == 200
    task = answer.json()["task"]
    assert task["status"]["state"] in ("TASK_STATE_SUBMITTED", "TASK_STATE_WORKING")
    assert task["contextId"] == "project-1"

    done = _wait(client, task["id"])
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"
    artifact = done["artifacts"][0]
    assert artifact["name"] == "result"
    output = DapTaskOutput.model_validate(artifact["parts"][0]["data"])
    assert [f.path for f in output.files] == ["backend/database.py"]
    assert output.files[0].content == MOCK_FILES["backend/database.py"]


def test_a2a_json_content_type_is_accepted(settings):
    client, _ = _client(settings)
    import json

    answer = client.post("/message:send", content=json.dumps(_message()),
                         headers={**HEADERS, "Content-Type": "application/a2a+json"})
    assert answer.status_code == 200


def test_unknown_task_gives_404(settings):
    client, _ = _client(settings)
    answer = client.get("/tasks/no-such-task", headers=HEADERS)
    assert answer.status_code == 404
    assert answer.json() == {"detail": "task not found"}


def test_message_without_a_dap_payload_gives_422(settings):
    client, _ = _client(settings)
    body = _message()
    body["message"]["parts"] = [{"text": "no data part"}]
    assert client.post("/message:send", json=body, headers=HEADERS).status_code == 422
    assert client.post("/message:send", json={"nonsense": 1}, headers=HEADERS).status_code == 422


def test_a_file_outside_target_files_fails_the_task(settings):
    def wrong_path(payload):
        return DapTaskOutput(summary="x", files=[GeneratedFile(path="../evil.py", content="x")])

    client, _ = _client(settings, Executor(run=wrong_path))
    task_id = client.post("/message:send", json=_message(), headers=HEADERS).json()["task"]["id"]
    failed = _wait(client, task_id)
    assert failed["status"]["state"] == "TASK_STATE_FAILED"
    reason = failed["status"]["message"]["parts"][0]["text"]
    assert "file outside target_files: ../evil.py" in reason
    assert failed["artifacts"] == []


def test_a_missing_target_file_fails_the_task(settings):
    client, _ = _client(settings, Executor(run=lambda p: DapTaskOutput(summary="x", files=[])))
    task_id = client.post("/message:send", json=_message(), headers=HEADERS).json()["task"]["id"]
    assert "did not write: backend/database.py" in (
        _wait(client, task_id)["status"]["message"]["parts"][0]["text"])


def test_tasks_run_one_at_a_time_in_the_order_received(settings):
    gate = threading.Event()
    order = []

    def slow(payload):
        order.append(payload.task_id)
        gate.wait(5)
        return DapTaskOutput(summary="ok", files=[
            GeneratedFile(path=p, content="x") for p in payload.target_files])

    executor = Executor(run=slow)
    client, _ = _client(settings, executor)
    first = client.post("/message:send", json=_message(), headers=HEADERS).json()["task"]["id"]
    second_payload = {**PAYLOAD, "task_id": "task-api", "target_files": ["backend/main.py"]}
    second = client.post("/message:send", json=_message(second_payload),
                         headers=HEADERS).json()["task"]["id"]
    _wait(client, first, states=("TASK_STATE_WORKING",))
    assert client.get(f"/tasks/{second}", headers=HEADERS).json()["status"]["state"] == \
        "TASK_STATE_SUBMITTED"
    assert executor.status() == (AgentStatus.BUSY, "task-db")
    gate.set()
    _wait(client, first)
    _wait(client, second)
    assert order == ["task-db", "task-api"]
    for _ in range(50):
        if executor.status() == (AgentStatus.IDLE, None):
            break
        time.sleep(0.02)
    assert executor.status() == (AgentStatus.IDLE, None)


def test_real_mode_reads_the_models_json_answer(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "0")
    database = MOCK_FILES["backend/database.py"]
    answer = "```json\n" + __import__("json").dumps({"summary": "tables", "files": [
        {"path": "backend/database.py", "content": database}]}) + "\n```"
    monkeypatch.setattr(executor_module, "chat", lambda messages, json_mode: LLMResponse(
        text=answer, prompt_tokens=10, completion_tokens=20, duration_ms=30))
    from dap.shared.schemas import DapTaskPayload

    output = executor_module.execute(DapTaskPayload.model_validate(PAYLOAD))
    assert output.summary == "tables"
    assert output.files[0].content == database
    assert (output.prompt_tokens, output.completion_tokens, output.duration_ms) == (10, 20, 30)


def test_prompt_contains_requirement_task_targets_and_dependencies():
    from dap.shared.schemas import DapTaskPayload
    from dap.worker.prompts import build_messages

    payload = DapTaskPayload.model_validate({
        **PAYLOAD, "type": "backend", "target_files": ["backend/main.py"],
        "dependency_files": [{"path": "backend/database.py", "content": "def list_items(): ..."}],
    })
    system, user = build_messages(payload)
    assert "backend developer" in system["content"]
    assert "backend/main.py" in system["content"]
    assert '"files"' in system["content"]
    assert "A library system" in user["content"]
    assert "def list_items(): ..." in user["content"]


def test_markdown_fences_around_a_file_are_removed(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "0")
    database = MOCK_FILES["backend/database.py"]
    fenced = f"```python\n{database}```"
    answer = '{"summary": "s", "files": [{"path": "backend/database.py", "content": %s}]}' % (
        __import__("json").dumps(fenced))
    monkeypatch.setattr(executor_module, "chat", lambda messages, json_mode: LLMResponse(
        text=answer, prompt_tokens=1, completion_tokens=1, duration_ms=1))
    from dap.shared.schemas import DapTaskPayload

    output = executor_module.execute(DapTaskPayload.model_validate(PAYLOAD))
    assert output.files[0].content == database.rstrip("\n")


@pytest.mark.parametrize("content,reason", [
    ("   \n", "empty file: backend/database.py"),
    ("def broken(:\n    pass\n", "syntax error in backend/database.py, line 1"),
])
def test_empty_or_broken_python_fails_the_task(settings, content, reason):
    def output(payload):
        return DapTaskOutput(summary="x", files=[GeneratedFile(path="backend/database.py",
                                                               content=content)])

    client, _ = _client(settings, Executor(run=output))
    task_id = client.post("/message:send", json=_message(), headers=HEADERS).json()["task"]["id"]
    failed = _wait(client, task_id)
    assert failed["status"]["state"] == "TASK_STATE_FAILED"
    assert reason in failed["status"]["message"]["parts"][0]["text"]
