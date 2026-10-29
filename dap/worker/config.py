"""Worker settings. Every value comes from the environment (.env), never from code.

dap.worker.main calls load_env() first: it reads .env, or the file given with
--env-file instead (so two workers can run on one PC with .env.worker1/.env.worker2).
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from dap.shared.enums import TaskType
from dap.shared.schemas import AgentRegister, Capabilities

logger = logging.getLogger("dap.worker")

# Where the Tailscale command usually is when it is not on PATH.
TAILSCALE_WINDOWS = Path("C:/Program Files/Tailscale/tailscale.exe")
TAILSCALE_MACOS = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")


def load_env(env_file: str | None = None) -> None:
    """Load .env, or env_file instead; values in env_file win over the environment."""
    if env_file is None:
        load_dotenv()
        return
    if not Path(env_file).is_file():
        raise SystemExit(f"Env file not found: {env_file}")
    load_dotenv(env_file, override=True)


@dataclass(frozen=True)
class WorkerSettings:
    master_url: str
    agent_token: str
    agent_id: str
    agent_name: str
    agent_owner: str
    role_hint: TaskType | None
    model: str
    provider: str
    cap_coding: int
    cap_reasoning: int
    cap_context: int
    heartbeat_interval_sec: int
    worker_host: str
    worker_port: int
    worker_public_url: str  # empty: see resolve_public_url()

    @property
    def api_url(self) -> str:
        """Base address of the master API, for example http://localhost:8000/api/v1."""
        return f"{self.master_url}/api/v1"

    def to_register_payload(self, a2a_url: str | None = None) -> AgentRegister:
        """The body this worker sends to POST /agents/register."""
        return AgentRegister(
            agent_id=self.agent_id,
            name=self.agent_name,
            owner=self.agent_owner,
            role_hint=self.role_hint,
            model=self.model,
            provider=self.provider,
            capabilities=Capabilities(
                coding=self.cap_coding,
                reasoning=self.cap_reasoning,
                context=self.cap_context,
            ),
            a2a_url=a2a_url,
        )


def get_settings() -> WorkerSettings:
    role = os.getenv("AGENT_ROLE_HINT", "").strip()
    return WorkerSettings(
        master_url=os.getenv("MASTER_URL", "http://localhost:8000").rstrip("/"),
        agent_token=os.getenv("AGENT_TOKEN", "change-me-team-secret"),
        agent_id=os.getenv("AGENT_ID", "agent-unnamed"),
        agent_name=os.getenv("AGENT_NAME", "Unnamed-PC"),
        agent_owner=os.getenv("AGENT_OWNER", "Unknown"),
        role_hint=TaskType(role) if role else None,
        model=os.getenv("LLM_MODEL", "unknown"),
        provider="ollama",
        cap_coding=int(os.getenv("AGENT_CAP_CODING", "50")),
        cap_reasoning=int(os.getenv("AGENT_CAP_REASONING", "50")),
        cap_context=int(os.getenv("AGENT_CAP_CONTEXT", "50")),
        heartbeat_interval_sec=int(os.getenv("HEARTBEAT_INTERVAL_SEC", "10")),
        worker_host=os.getenv("WORKER_HOST", "0.0.0.0"),
        worker_port=int(os.getenv("WORKER_PORT", "9000")),
        worker_public_url=os.getenv("WORKER_PUBLIC_URL", "").strip().rstrip("/"),
    )


def _tailscale_ip() -> str | None:
    """This PC's Tailscale IPv4 address (`tailscale ip -4`), or None."""
    command = shutil.which("tailscale") or next(
        (str(path) for path in (TAILSCALE_WINDOWS, TAILSCALE_MACOS) if path.is_file()), None
    )
    if command is None:
        return None
    try:
        answer = subprocess.run([command, "ip", "-4"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    address = answer.stdout.strip().splitlines()[0] if answer.stdout.strip() else ""
    return address if answer.returncode == 0 and address.startswith("100.") else None


def resolve_public_url(settings: WorkerSettings) -> str:
    """The address the master uses for this worker's A2A server.

    WORKER_PUBLIC_URL when set; otherwise this PC's Tailscale address; otherwise
    127.0.0.1, which only works when the master runs on this PC (with a warning).
    """
    if settings.worker_public_url:
        return settings.worker_public_url
    address = _tailscale_ip()
    if address:
        return f"http://{address}:{settings.worker_port}"
    url = f"http://127.0.0.1:{settings.worker_port}"
    logger.warning(
        "WORKER_PUBLIC_URL is empty and Tailscale gave no address; using %s. "
        "A master on another PC cannot reach this worker: set WORKER_PUBLIC_URL "
        "to http://<this PC's Tailscale IP>:%s in the env file.", url, settings.worker_port)
    return url
