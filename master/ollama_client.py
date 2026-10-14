from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS

class OllamaError(RuntimeError):
    """Raised when Ollama cannot be reached or returns an unusable answer."""

class OllamaClient:
    """Minimal client for Ollama's /api/chat endpoint."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout: float = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _request(self, path: str, payload: dict | None = None, timeout: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama HTTP {exc.code} on {path}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama returned non-JSON on {path}") from exc

    def installed_models(self) -> list[str]:
        """Names of the models pulled into Ollama, e.g. ["llama3.1:latest"]."""
        tags = self._request("/api/tags", timeout=3)
        return [m.get("name", "") for m in tags.get("models", [])]

    def is_available(self) -> bool:
        """True if the server answers and the configured model is pulled."""
        try:
            tags = self._request("/api/tags", timeout=3)
        except OllamaError:
            return False
        names = {m.get("name", "") for m in tags.get("models", [])}
        return any(n == self.model or n.startswith(f"{self.model}:") for n in names)

    def chat(
        self,
        messages: list[dict[str, str]],
        json_mode: bool = True,
        temperature: float = 0.1,
    ) -> str:
        """Send a chat request and return the assistant's raw text content."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"  # Ollama constrains output to valid JSON
        response = self._request("/api/chat", payload)
        content = response.get("message", {}).get("content")
        if not content:
            raise OllamaError("Ollama returned an empty message")
        return content


def resolve_model(name: str, installed: list[str]) -> str | None:
    """Match "qwen2.5" to an installed tag ("qwen2.5:latest" or "qwen2.5:7b"); None if absent."""
    if name in installed or f"{name}:latest" in installed:
        return name
    return next((n for n in installed if n.startswith(f"{name}:")), None)
