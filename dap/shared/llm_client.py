"""LLM client shared by the master and the workers.

Talks to a local model (Ollama) through the OpenAI-compatible
/v1/chat/completions API. Settings come from the environment (.env):

    LLM_BASE_URL   for example http://localhost:11434/v1
    LLM_API_KEY    any non-empty text for Ollama, for example "ollama"
    LLM_MODEL      for example qwen3:4b
    LLM_MOCK       1 = no model call, return a fixed valid answer

Contract (docs/contracts/PROJECT_CONTRACT.md, section 8):

    chat(messages, *, temperature=0.2, max_tokens=None, json_mode=False) -> LLMResponse
    health_check() -> bool

When the model cannot be reached, chat() raises RuntimeError.
"""

import json
import os
import re
import time

from dotenv import load_dotenv
from openai import OpenAI

from dap.shared.schemas import LLMResponse

load_dotenv()

TIMEOUT_SEC = 120
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


def _client(base_url: str, api_key: str) -> OpenAI:
    # The openai package retries by itself; we do our own single retry instead.
    return OpenAI(base_url=base_url, api_key=api_key, timeout=TIMEOUT_SEC, max_retries=0)


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> LLMResponse:
    """Send a chat request to the model and return its answer."""
    if _is_mock():
        text = json.dumps(MOCK_JSON) if json_mode else MOCK_TEXT
        return LLMResponse(text=text, prompt_tokens=0, completion_tokens=0, duration_ms=0)

    base_url, api_key, model = _settings()
    if not base_url or not model:
        raise RuntimeError("LLM_BASE_URL and LLM_MODEL must be set in .env")

    kwargs: dict = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    client = _client(base_url, api_key or "none")
    last_error: Exception | None = None
    for _ in range(ATTEMPTS):
        start = time.perf_counter()
        try:
            response = client.chat.completions.create(**kwargs)
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
