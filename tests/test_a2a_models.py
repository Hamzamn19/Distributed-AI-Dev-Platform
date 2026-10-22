"""A2A wire models: each example of the contract's A2A section round-trips exactly."""

import pytest
from pydantic import ValidationError

from dap.shared.enums import A2A_TO_TASK_STATUS, A2ATaskState, TaskStatus
from dap.shared.schemas import (
    A2ATask,
    AgentCard,
    AgentRegister,
    DapTaskOutput,
    DapTaskPayload,
    SendMessageRequest,
    SendMessageResponse,
    first_data,
)

PAYLOAD = {
    "task_id": "7f3d1c44-0000-4000-8000-000000000001",
    "project_id": "0b5c2a9e-0000-4000-8000-000000000002",
    "type": "database",
    "title": "Design database schema",
    "description": "Tables for books and members",
    "requirement_text": "A library system where members borrow books.",
    "target_files": ["backend/database.py"],
    "dependency_files": [],
}

OUTPUT = {
    "summary": "Created the tables",
    "files": [{"path": "backend/database.py", "content": "import sqlite3\n"}],
    "prompt_tokens": 120,
    "completion_tokens": 300,
    "duration_ms": 4100,
}

AGENT_CARD = {
    "name": "agent-okan",
    "description": "DAP worker on Okan-PC running qwen3:4b",
    "version": "0.1.0",
    "supportedInterfaces": [
        {"url": "http://100.64.0.7:9000", "protocolBinding": "HTTP+JSON", "protocolVersion": "1.0"}
    ],
    "capabilities": {"streaming": False, "pushNotifications": False},
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {"id": "integration", "name": "integration", "description": "Integration tasks",
         "tags": ["integration"]}
    ],
}

SEND_REQUEST = {
    "message": {
        "messageId": "11111111-0000-4000-8000-000000000003",
        "role": "ROLE_USER",
        "contextId": PAYLOAD["project_id"],
        "parts": [
            {"text": "Design database schema"},
            {"data": PAYLOAD, "mediaType": "application/json"},
        ],
    },
    "configuration": {"returnImmediately": True},
}

SEND_RESPONSE = {"task": {
    "id": "22222222-0000-4000-8000-000000000004",
    "contextId": PAYLOAD["project_id"],
    "status": {"state": "TASK_STATE_WORKING", "timestamp": "2026-10-22T18:00:00Z"},
    "artifacts": [],
}}

TASK_COMPLETED = {
    "id": "22222222-0000-4000-8000-000000000004",
    "contextId": PAYLOAD["project_id"],
    "status": {"state": "TASK_STATE_COMPLETED", "timestamp": "2026-10-22T18:00:05Z"},
    "artifacts": [{
        "artifactId": "33333333-0000-4000-8000-000000000005",
        "name": "result",
        "parts": [{"data": OUTPUT, "mediaType": "application/json"}],
    }],
}

TASK_FAILED = {
    "id": "22222222-0000-4000-8000-000000000004",
    "status": {
        "state": "TASK_STATE_FAILED",
        "message": {"messageId": "44444444-0000-4000-8000-000000000006", "role": "ROLE_AGENT",
                    "parts": [{"text": "file outside target_files: ../x.py"}]},
        "timestamp": "2026-10-22T18:00:05Z",
    },
    "artifacts": [],
}


@pytest.mark.parametrize("model,example", [
    (AgentCard, AGENT_CARD),
    (SendMessageRequest, SEND_REQUEST),
    (SendMessageResponse, SEND_RESPONSE),
    (A2ATask, TASK_COMPLETED),
    (A2ATask, TASK_FAILED),
])
def test_wire_examples_round_trip_exactly(model, example):
    assert model.model_validate(example).to_wire() == example


def test_parts_have_no_kind_field():
    request = SendMessageRequest.model_validate(SEND_REQUEST).to_wire()
    for part in request["message"]["parts"]:
        assert "kind" not in part


def test_unknown_wire_fields_are_ignored():
    task = A2ATask.model_validate({**TASK_COMPLETED, "history": [], "metadata": {"x": 1}})
    assert "history" not in task.to_wire()


def test_payload_and_output_travel_in_data_parts():
    request = SendMessageRequest.model_validate(SEND_REQUEST)
    payload = DapTaskPayload.model_validate(first_data(request.message.parts))
    assert payload.target_files == ["backend/database.py"]
    task = A2ATask.model_validate(TASK_COMPLETED)
    output = DapTaskOutput.model_validate(first_data(task.artifacts[0].parts))
    assert output.files[0].path == "backend/database.py"


def test_dap_payload_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DapTaskPayload.model_validate({**PAYLOAD, "targetFiles": []})


def test_a2a_states_map_to_task_status():
    assert {state.value for state in A2ATaskState} == {
        "TASK_STATE_SUBMITTED", "TASK_STATE_WORKING", "TASK_STATE_COMPLETED", "TASK_STATE_FAILED"}
    assert A2A_TO_TASK_STATUS[A2ATaskState.SUBMITTED] == TaskStatus.IN_PROGRESS
    assert A2A_TO_TASK_STATUS[A2ATaskState.WORKING] == TaskStatus.IN_PROGRESS
    assert A2A_TO_TASK_STATUS[A2ATaskState.COMPLETED] == TaskStatus.COMPLETED
    assert A2A_TO_TASK_STATUS[A2ATaskState.FAILED] == TaskStatus.FAILED


def test_agent_register_accepts_an_a2a_url_and_defaults_to_null():
    base = {"agent_id": "a", "name": "A", "owner": "o", "model": "m",
            "capabilities": {"coding": 1, "reasoning": 1, "context": 1}}
    assert AgentRegister.model_validate(base).a2a_url is None
    assert AgentRegister.model_validate({**base, "a2a_url": "http://100.64.0.7:9000"}).a2a_url
