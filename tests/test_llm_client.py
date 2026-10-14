"""Tests for dap.shared.llm_client. tests/conftest.py sets LLM_MOCK=1."""

import json

import pytest

from dap.shared import llm_client
from dap.shared.enums import SPRINT1_TASK_TYPES
from dap.shared.schemas import LLMResponse

MESSAGES = [{"role": "user", "content": "Say hello"}]


def test_mock_plain_text():
    result = llm_client.chat(MESSAGES)
    assert isinstance(result, LLMResponse)
    assert result.text == "mock response"
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


def test_mock_json_has_every_sprint1_type():
    result = llm_client.chat(MESSAGES, json_mode=True)
    tasks = json.loads(result.text)["tasks"]
    types = {task["type"] for task in tasks}
    assert {str(t.value) for t in SPRINT1_TASK_TYPES} <= types
    for task in tasks:
        assert set(task) == {"key", "title", "description", "type", "depends_on"}


def test_strip_think():
    assert llm_client.strip_think("<think>\nhmm\n</think>\n\nHello") == "Hello"
    assert llm_client.strip_think("Hello") == "Hello"


def test_health_check_in_mock_mode():
    assert llm_client.health_check() is True


def test_unreachable_model_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "0")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")  # nothing listens here
    monkeypatch.setenv("LLM_MODEL", "test-model")
    with pytest.raises(RuntimeError, match="127.0.0.1:9"):
        llm_client.chat(MESSAGES)
    assert llm_client.health_check() is False
