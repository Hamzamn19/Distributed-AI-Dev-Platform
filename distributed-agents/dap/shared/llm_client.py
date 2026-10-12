"""LLM client shared by master and worker.

Owner: Eray - card S1-07.

Contract (docs/PROJECT_CONTRACT.md, section 8):
- Reads LLM_BASE_URL, LLM_API_KEY, LLM_MODEL and LLM_MOCK from the environment.
- Talks to an OpenAI-compatible /v1/chat/completions endpoint (Ollama locally)
  through the "openai" package.
- Removes a <think>...</think> block from the answer if the model returns one.
- When LLM_MOCK=1 it does not call any model and returns a fixed, valid answer,
  so tests and PCs without Ollama still work.
- Uses a timeout and retries once; raises a clear exception when the model
  server is down.

Keep the two function signatures below exactly as they are: the master
(decomposer) and the worker (executor) both call them.
"""

from dap.shared.schemas import LLMResponse


def chat(
    messages: list[dict],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> LLMResponse:
    """Send chat messages to the model and return its answer."""
    raise NotImplementedError("S1-07: implement chat()")


def health_check() -> bool:
    """Return True when the model server answers (always True in mock mode)."""
    raise NotImplementedError("S1-07: implement health_check()")
