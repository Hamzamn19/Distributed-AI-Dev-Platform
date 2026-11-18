"""Register the six team agents of docs/agents.json with a running master (card S2-07).

    python scripts/seed_agents.py

MASTER_URL and AGENT_TOKEN come from .env. The agents appear on the Agents page at
once; they turn offline after HEARTBEAT_TIMEOUT_SEC because no worker program sends
their heartbeats. A real worker (python -m dap.worker.main) keeps its agent online.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

AGENTS_JSON = Path(__file__).resolve().parents[1] / "docs" / "agents.json"


def seed(client: httpx.Client, token: str, path: Path = AGENTS_JSON) -> list[str]:
    """Register every agent in the file; return their ids."""
    registered = []
    for entry in json.loads(path.read_text(encoding="utf-8")):
        response = client.post(
            "/api/v1/agents/register", json=entry, headers={"X-Agent-Token": token}
        )
        if response.status_code != 200:
            raise SystemExit(
                f"Registering {entry.get('agent_id')} failed: "
                f"{response.status_code} {response.text}"
            )
        registered.append(entry["agent_id"])
    return registered


def main() -> int:
    load_dotenv()
    master_url = os.getenv("MASTER_URL", "http://localhost:8000")
    token = os.getenv("AGENT_TOKEN", "change-me-team-secret")
    try:
        with httpx.Client(base_url=master_url, timeout=10) as client:
            ids = seed(client, token)
    except httpx.HTTPError as exc:
        print(f"Cannot reach the master at {master_url}: {exc}", file=sys.stderr)
        return 1
    print(f"Registered {len(ids)} agents at {master_url}: {', '.join(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
