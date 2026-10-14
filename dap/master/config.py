"""Master settings. Every value comes from the environment (.env), never from code."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class MasterSettings:
    agent_token: str
    host: str
    port: int
    database_url: str
    cors_origins: list[str]
    heartbeat_timeout_sec: int


def get_settings() -> MasterSettings:
    origins = os.getenv("CORS_ORIGINS", "*")
    return MasterSettings(
        agent_token=os.getenv("AGENT_TOKEN", "change-me-team-secret"),
        host=os.getenv("MASTER_HOST", "0.0.0.0"),
        port=int(os.getenv("MASTER_PORT", "8000")),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/dap.db"),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        heartbeat_timeout_sec=int(os.getenv("HEARTBEAT_TIMEOUT_SEC", "30")),
    )
