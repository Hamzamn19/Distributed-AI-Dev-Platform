"""LLM client shared by the master and the workers.

Talks to a local model (Ollama) through the OpenAI-compatible
/v1/chat/completions API. Settings come from the environment (.env):

    LLM_BASE_URL   for example http://localhost:11434/v1
    LLM_API_KEY    any non-empty text for Ollama, for example "ollama"
    LLM_MODEL      for example qwen3:4b
    LLM_MOCK       1 = no model call, return a fixed valid answer
    LLM_TIMEOUT_SEC  seconds to wait for one answer (default 120; 600 on worker PCs)
    LLM_THINK      0 (default) = ask reasoning models (Qwen3, Gemma, ...) not to think
                   first; their hidden thinking cost minutes and thousands of tokens
    LLM_MAX_TOKENS most tokens of one answer when the caller gives none (default 8192),
                   so a runaway answer stops instead of running until the timeout

Contract (docs/contracts/PROJECT_CONTRACT.md, section 8):

    chat(messages, *, temperature=0.2, max_tokens=None, json_mode=False) -> LLMResponse
    health_check() -> bool

When the model cannot be reached, chat() raises RuntimeError.
"""

import json
import os
import re
import time
from collections.abc import Callable

from dotenv import load_dotenv
from openai import OpenAI

from dap.shared.schemas import LLMResponse

load_dotenv()

DEFAULT_TIMEOUT_SEC = 120
DEFAULT_MAX_TOKENS = 8192
# Switches thinking off in llama.cpp's llama-server (Gemma, Qwen3 chat templates).
# Ollama ignores the field; its models without thinking (qwen2.5, llama3.1) need nothing.
# For a guarantee start llama-server with --reasoning-budget 0.
NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
# Qwen3's own switch, written into the conversation, which Ollama passes on: without
# it qwen3 on Ollama thinks for minutes and runs out of tokens before the code ends
# (17 November test: database.py with four of its five functions missing).
NO_THINK_SWITCH = "/no_think"
SWITCH_MODELS = ("qwen3",)


def _with_switch(messages: list[dict], model: str) -> list[dict]:
    """The messages with /no_think after the last user message, for Qwen3 models."""
    users = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if not model.lower().startswith(SWITCH_MODELS) or not users:
        return messages
    last = users[-1]
    changed = [dict(m) for m in messages]
    changed[last]["content"] = f"{changed[last]['content']}\n{NO_THINK_SWITCH}"
    return changed
ATTEMPTS = 2  # first try + one retry

MOCK_TEXT = "mock response"

# Same shape the decomposer asks the model for (member guide, agreement 2).
MOCK_JSON = {
    "tasks": [
        {
            "key": "T1",
            "title": "Design database schema",
            "description": "Define the tables and relations the application needs.",
            "type": "database",
            "depends_on": [],
        },
        {
            "key": "T2",
            "title": "Build REST API",
            "description": "Implement the backend endpoints on top of the database.",
            "type": "backend",
            "depends_on": ["T1"],
        },
        {
            "key": "T3",
            "title": "Build web pages",
            "description": "Create the user interface that calls the REST API.",
            "type": "frontend",
            "depends_on": ["T2"],
        },
        {
            "key": "T4",
            "title": "Write tests",
            "description": "Test the API and the web pages.",
            "type": "testing",
            "depends_on": ["T2", "T3"],
        },
    ]
}

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _is_mock() -> bool:
    return os.getenv("LLM_MOCK", "0").strip() == "1"


def _settings() -> tuple[str, str, str]:
    """Read the address, key and model at call time, so tests can change them."""
    return (
        os.getenv("LLM_BASE_URL", ""),
        os.getenv("LLM_API_KEY", ""),
        os.getenv("LLM_MODEL", ""),
    )


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks that reasoning models such as Qwen3 add."""
    return _THINK_BLOCK.sub("", text).strip()


def _timeout_sec() -> float:
    return float(os.getenv("LLM_TIMEOUT_SEC", str(DEFAULT_TIMEOUT_SEC)))


def _max_tokens() -> int:
    return int(os.getenv("LLM_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)))


def _thinking() -> bool:
    return os.getenv("LLM_THINK", "0").strip() == "1"


def _client(base_url: str, api_key: str) -> OpenAI:
    # The openai package retries by itself; we do our own single retry instead.
    return OpenAI(base_url=base_url, api_key=api_key, timeout=_timeout_sec(), max_retries=0)


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    json_mode: bool = False,
    on_chunk: Callable[[int, str], None] | None = None,
) -> LLMResponse:
    """Send a chat request to the model and return its answer.

    on_chunk (streaming, Sprint 4): called during the answer with the running
    (generated_tokens, text_tail) so a caller can show the model writing live;
    the request goes out with stream: true and the chunks are joined.
    """
    if _is_mock():
        text = json.dumps(MOCK_JSON) if json_mode else MOCK_TEXT
        return LLMResponse(text=text, prompt_tokens=0, completion_tokens=0, duration_ms=0)

    base_url, api_key, model = _settings()
    if not base_url or not model:
        raise RuntimeError("LLM_BASE_URL and LLM_MODEL must be set in .env")

    kwargs: dict = {"model": model, "messages": messages, "temperature": temperature,
                    "max_tokens": max_tokens if max_tokens is not None else _max_tokens()}
    if not _thinking():
        kwargs["extra_body"] = NO_THINKING
        kwargs["messages"] = _with_switch(messages, model)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    if on_chunk is not None:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

    client = _client(base_url, api_key or "none")
    last_error: Exception | None = None
    for _ in range(ATTEMPTS):
        start = time.perf_counter()
        try:
            if on_chunk is None:
                response = client.chat.completions.create(**kwargs)
            else:
                return _chat_streaming(client, kwargs, base_url, model, start, on_chunk)
        except Exception as exc:  # connection refused, timeout, HTTP error ...
            last_error = exc
            continue
        duration_ms = int((time.perf_counter() - start) * 1000)
        usage = response.usage
        return LLMResponse(
            text=strip_think(response.choices[0].message.content or ""),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            duration_ms=duration_ms,
        )

    raise RuntimeError(
        f"LLM at {base_url} (model {model}) did not answer after {ATTEMPTS} attempts: {last_error}"
    )


def _chat_streaming(client, kwargs: dict, base_url: str, model: str,
                    start: float, on_chunk: Callable[[int, str], None]) -> LLMResponse:
    """The streaming answer: join the chunks and report the progress while it runs."""
    text_parts: list[str] = []
    usage = None
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            usage = chunk.usage
        if not chunk.choices:
            continue
        piece = chunk.choices[0].delta.content or ""
        if piece:
            text_parts.append(piece)
            text = "".join(text_parts)
            # the full answer so far: the caller derives the current file and the tail
            on_chunk(len(text) // 4, text)
    text = "".join(text_parts)
    completion_tokens = usage.completion_tokens if usage else max(len(text) // 4, 1)
    return LLMResponse(
        text=strip_think(text),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=completion_tokens,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


def health_check() -> bool:
    """True when the model server answers (always True in mock mode)."""
    if _is_mock():
        return True
    base_url, api_key, _ = _settings()
    if not base_url:
        return False
    try:
        _client(base_url, api_key or "none").with_options(timeout=5).models.list()
        return True
    except Exception:
        return False
