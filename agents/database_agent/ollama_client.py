"""Small HTTP adapter for the locally running Ollama server."""

import os

import httpx

MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


class OllamaError(Exception):
    def __init__(self, detail: str, status_code: int = 503):
        super().__init__(detail)
        self.status_code = status_code


async def model_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            response = await client.get(f"{BASE_URL}/api/tags")
            response.raise_for_status()
            models = response.json()["models"]
            return any(m.get("name") == MODEL for m in models)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return False


async def generate(prompt: str, system: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
            response = await client.post(
                f"{BASE_URL}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "keep_alive": "10m",
                    # Short context and one request at a time suit 6 GB VRAM.
                    "options": {"num_ctx": 4096, "num_predict": 1800, "temperature": 0.2},
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise OllamaError("Ollama took too long. Retry with a smaller requirement.", 504) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise OllamaError(f"Model not installed. Run: ollama pull {MODEL}") from exc
        raise OllamaError("Ollama could not generate a response.", 502) from exc
    except httpx.RequestError as exc:
        raise OllamaError("Cannot reach Ollama. Start Ollama and retry.") from exc
    except ValueError as exc:
        raise OllamaError("Ollama returned invalid JSON.", 502) from exc

    if not isinstance(data, dict):
        raise OllamaError("Ollama returned an unexpected response.", 502)
    result = data.get("response")
    if data.get("error") or data.get("done") is not True or not isinstance(result, str) or not result.strip():
        raise OllamaError("Ollama returned no complete result.", 502)
    if data.get("done_reason") == "length":
        raise OllamaError("Output reached the token limit. Retry with a smaller schema.", 502)
    return result.strip()
