"""Minimal OpenAI-compatible shim for Ollama that disables thinking (think:false).

The team's llm_client talks OpenAI /v1; Ollama 0.35.1 answers thinking models on
/v1 with an empty content (the reasoning goes to a separate field the client does
not read). This shim forwards /v1/chat/completions to the native /api/chat with
think=false and maps the answer back. Run:

    python /tmp/ollama_v1_shim.py 8787
Then use LLM_BASE_URL=http://127.0.0.1:8787/v1
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

OLLAMA = "http://127.0.0.1:11434"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/") in ("/v1/models", "/models"):
            r = httpx.get(f"{OLLAMA}/api/tags", timeout=10)
            models = [{"id": m["name"], "object": "model", "owned_by": "library"}
                      for m in r.json().get("models", [])]
            self._send(200, {"object": "list", "data": models})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if "chat/completions" not in self.path:
            self._send(404, {"error": "not found"})
            return
        options = {}
        if "temperature" in body:
            options["temperature"] = body["temperature"]
        if body.get("max_tokens"):
            options["num_predict"] = body["max_tokens"]
        payload = {
            "model": body.get("model"),
            "messages": body.get("messages", []),
            "stream": False,
            "think": False,          # the whole point of this shim
            "keep_alive": "2h",      # keep the model loaded between calls
            "options": options,
        }
        if body.get("response_format", {}).get("type") == "json_object":
            payload["format"] = "json"
        start = time.perf_counter()
        r = httpx.post(f"{OLLAMA}/api/chat", json=payload, timeout=600)
        duration = int((time.perf_counter() - start) * 1000)
        if r.status_code != 200:
            self._send(502, {"error": {"message": r.text[:500]}})
            return
        d = r.json()
        m = d.get("message", {})
        usage = {
            "prompt_tokens": d.get("prompt_eval_count", 0),
            "completion_tokens": d.get("eval_count", 0),
            "total_tokens": d.get("prompt_eval_count", 0) + d.get("eval_count", 0),
        }
        self._send(200, {
            "id": "shim", "object": "chat.completion", "created": int(time.time()),
            "model": body.get("model"),
            "choices": [{"index": 0, "finish_reason": d.get("done_reason", "stop"),
                         "message": {"role": "assistant", "content": m.get("content") or ""}}],
            "usage": usage,
            "shim_duration_ms": duration,
        })


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    print(f"shim on :{port} -> {OLLAMA} (think disabled)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
