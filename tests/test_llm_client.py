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


def test_timeout_comes_from_llm_timeout_sec(monkeypatch):
    monkeypatch.delenv("LLM_TIMEOUT_SEC", raising=False)
    assert llm_client._timeout_sec() == 120
    monkeypatch.setenv("LLM_TIMEOUT_SEC", "600")
    assert llm_client._timeout_sec() == 600


class _FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        from types import SimpleNamespace
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hi"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))


@pytest.fixture
def fake_model(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("LLM_MOCK", "0")
    monkeypatch.setenv("LLM_BASE_URL", "http://model/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    completions = _FakeCompletions()
    monkeypatch.setattr(llm_client, "_client", lambda base_url, api_key: SimpleNamespace(
        chat=SimpleNamespace(completions=completions)))
    return completions


def test_thinking_is_off_and_answers_are_limited_by_default(fake_model, monkeypatch):
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
    llm_client.chat(MESSAGES)
    assert fake_model.kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert fake_model.kwargs["max_tokens"] == 8192


def test_llm_think_and_llm_max_tokens_change_the_request(fake_model, monkeypatch):
    monkeypatch.setenv("LLM_THINK", "1")
    monkeypatch.setenv("LLM_MAX_TOKENS", "2000")
    llm_client.chat(MESSAGES)
    assert "extra_body" not in fake_model.kwargs
    assert fake_model.kwargs["max_tokens"] == 2000
    llm_client.chat(MESSAGES, max_tokens=50)
    assert fake_model.kwargs["max_tokens"] == 50


def test_qwen3_on_ollama_is_told_not_to_think(fake_model, monkeypatch):
    # 17 November: qwen3:4b on Ollama thought for minutes and cut its code short.
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("LLM_MODEL", "qwen3:4b")
    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "write it"}]
    llm_client.chat(messages)
    assert fake_model.kwargs["messages"][-1]["content"] == "write it\n/no_think"
    assert messages[-1]["content"] == "write it"  # the caller's list stays as it was
    monkeypatch.setenv("LLM_THINK", "1")
    llm_client.chat(messages)
    assert fake_model.kwargs["messages"][-1]["content"] == "write it"


def test_other_models_get_no_switch(fake_model, monkeypatch):
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("LLM_MODEL", "qwen2.5-coder:7b")
    llm_client.chat([{"role": "user", "content": "write it"}])
    assert fake_model.kwargs["messages"][-1]["content"] == "write it"
