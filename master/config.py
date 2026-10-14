from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Read master/.env (next to this file) so `python main.py` works without exporting
# variables. Values already set in the real environment take precedence.
load_dotenv(Path(__file__).resolve().parent / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT", "120"))
MAX_DECOMPOSITION_ATTEMPTS = 3
CONTRACT_VERSION = "1.0"

# --- Server / security -------------------------------------------------------
HOST = os.getenv("DAP_HOST", "0.0.0.0")
PORT = int(os.getenv("DAP_PORT", "8000"))
DAP_TOKEN = os.getenv("DAP_TOKEN", "")          # every request must send X-DAP-Token
DB_PATH = Path(os.getenv("DAP_DB_PATH", Path(__file__).resolve().parent / "data" / "dap.db"))

HEARTBEAT_INTERVAL_SECONDS = 10                 # agents are expected to ping this often
HEARTBEAT_TIMEOUT_SECONDS = 30                  # silent this long -> marked offline

# --- Task types & scoring ----------------------------------------------------
TASK_TYPES = (
    "analysis", "database", "backend", "frontend",
    "testing", "review", "integration", "documentation",
)

# S = (w_c * C) + (w_r * R) + (w_x * X) + (10 * u) - (15 * q)
# Weight coefficients per task type from the CM6453 sprint plan ("Atama skoru").
# They are the initial suggestions; tuning is planned for Sprint 5.
TASK_WEIGHTS: dict[str, dict[str, float]] = {
    #                  w_c           w_r           w_x
    "analysis":      {"w_c": 0.1, "w_r": 0.6, "w_x": 0.3},
    "database":      {"w_c": 0.4, "w_r": 0.4, "w_x": 0.2},
    "backend":       {"w_c": 0.5, "w_r": 0.3, "w_x": 0.2},
    "frontend":      {"w_c": 0.6, "w_r": 0.2, "w_x": 0.2},
    "testing":       {"w_c": 0.4, "w_r": 0.4, "w_x": 0.2},
    "review":        {"w_c": 0.2, "w_r": 0.5, "w_x": 0.3},
    "integration":   {"w_c": 0.3, "w_r": 0.3, "w_x": 0.4},
    "documentation": {"w_c": 0.1, "w_r": 0.4, "w_x": 0.5},
}
SPECIALTY_BONUS = 10        # 10 * u
QUEUE_PENALTY = 15          # 15 * q


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    model: str
    coding: float          # C: 0-100 coding capability (measured by the Sprint 2 benchmark)
    reasoning: float       # R: 0-100 reasoning capability
    context: float         # X: 0-100 context capacity
    specialties: tuple[str, ...] = ()
    context_window: int = 0    # optional, tokens; 0 = unknown (no hard limit check)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentProfile":
        return cls(
            agent_id=d["agent_id"],
            model=d["model"],
            coding=float(d["coding"]),
            reasoning=float(d["reasoning"]),
            context=float(d["context"]),
            specialties=tuple(s.lower() for s in d.get("specialties", ())),
            context_window=int(d.get("context_window") or 0),
        )


# Plain dicts, the same shape a DB row / JSON API response would have.
# Profiles mirror the Agent A/B/C example in the CM6453 spec.
MOCK_AGENTS: list[dict] = [
    {"agent_id": "agent-a", "model": "llama3.1:8b",
     "coding": 90, "reasoning": 85, "context": 95, "context_window": 128_000,
     "specialties": ["backend", "testing"]},
    {"agent_id": "agent-b", "model": "mistral:7b",
     "coding": 75, "reasoning": 95, "context": 70, "context_window": 32_000,
     "specialties": ["analysis", "documentation", "review"]},
    {"agent_id": "agent-c", "model": "deepseek-coder:6.7b",
     "coding": 95, "reasoning": 70, "context": 80, "context_window": 16_000,
     "specialties": ["frontend", "database"]},
]
