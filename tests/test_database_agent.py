"""Offline API checks; the real-model demo is run separately."""

import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from agents.database_agent import ollama_client
from agents.database_agent.main import app


class DatabaseAgentTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {"task_type": "database_design", "description": "Design a library"}

    def test_health_checks_model(self):
        with patch.object(ollama_client, "model_available", new=AsyncMock(return_value=True)):
            self.assertEqual(self.client.get("/health").json()["status"], "available")
        with patch.object(ollama_client, "model_available", new=AsyncMock(return_value=False)):
            self.assertEqual(self.client.get("/health").status_code, 503)

    def test_task_forwards_requirement_and_returns_result(self):
        mock = AsyncMock(return_value="CREATE TABLE books (id integer PRIMARY KEY);")
        with patch.object(ollama_client, "generate", new=mock):
            response = self.client.post("/task", json=self.payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("CREATE TABLE", response.json()["result"])
            self.assertIn("Design a library", mock.call_args.args[0])

    def test_invalid_input(self):
        for payload in [dict(self.payload, task_type="unknown"), dict(self.payload, description="   ")]:
            self.assertEqual(self.client.post("/task", json=payload).status_code, 422)

    def test_ollama_failure(self):
        with patch.object(ollama_client, "generate", new=AsyncMock(side_effect=ollama_client.OllamaError("timeout", 504))):
            self.assertEqual(self.client.post("/task", json=self.payload).status_code, 504)

    def test_adapter_handles_timeout_and_truncation(self):
        import asyncio

        for response in [httpx.ReadTimeout("timeout"), httpx.Response(200, json={
            "done": True, "done_reason": "length", "response": "CREATE TABLE incomplete"
        }, request=httpx.Request("POST", "http://localhost/api/generate"))]:
            mock = AsyncMock()
            mock.__aenter__.return_value = mock
            if isinstance(response, Exception):
                mock.post.side_effect = response
            else:
                mock.post.return_value = response
            with patch.object(ollama_client.httpx, "AsyncClient", return_value=mock):
                with self.assertRaises(ollama_client.OllamaError):
                    asyncio.run(ollama_client.generate("test", "test"))


if __name__ == "__main__":
    unittest.main()
