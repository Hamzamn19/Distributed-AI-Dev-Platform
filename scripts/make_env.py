"""Write this PC's .env for a worker, from docs/agents.json (Sprint 3).

    python scripts/make_env.py --agent agent-hamza --master http://100.109.95.6:8000 --mock

Only the team token has to be shared, privately; the script asks for it and does not
show it. Everything else comes from docs/agents.json (name, owner, role, model, scores)
and from this PC (its Tailscale address for WORKER_PUBLIC_URL).

    --agent    your agent id in docs/agents.json, for example agent-hamza
    --master   the master's address: http://<master Tailscale IP>:8000
    --mock     LLM_MOCK=1 (no model needed, for a first network test); default LLM_MOCK=0
    --model    a different local model than the one in docs/agents.json
    --force    replace an existing .env (the old one is kept as .env.bak)

The new .env is never committed (.gitignore). Then: python -m dap.worker.main
"""

import argparse
import getpass
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dap.worker.config import _tailscale_ip  # noqa: E402

AGENTS_JSON = REPO / "docs" / "agents.json"


def build(agent: dict, token: str, master: str, mock: bool, model: str | None,
          public_url: str) -> str:
    caps = agent["capabilities"]
    lines = [
        f"# Worker settings of {agent['owner']} ({agent['agent_id']}), written by",
        "# scripts/make_env.py. Never commit this file; it holds the team token.",
        f"AGENT_TOKEN={token}",
        f"MASTER_URL={master.rstrip('/')}",
        "",
        "# The local model on this PC (`ollama list`)",
        "LLM_BASE_URL=http://localhost:11434/v1",
        "LLM_API_KEY=ollama",
        f"LLM_MODEL={model or agent['model']}",
        f"LLM_MOCK={1 if mock else 0}",
        "LLM_TIMEOUT_SEC=600",
        "# 0: reasoning models answer without thinking first (minutes and tokens saved)",
        "LLM_THINK=0",
        "LLM_MAX_TOKENS=8192",
        "",
        "# Who this agent is (docs/agents.json)",
        f"AGENT_ID={agent['agent_id']}",
        f"AGENT_NAME={agent['name']}",
        f"AGENT_OWNER={agent['owner']}",
        f"AGENT_ROLE_HINT={agent['role_hint'] or ''}",
        f"AGENT_CAP_CODING={caps['coding']}",
        f"AGENT_CAP_REASONING={caps['reasoning']}",
        f"AGENT_CAP_CONTEXT={caps['context']}",
        "HEARTBEAT_INTERVAL_SEC=10",
        "",
        "# This worker's A2A server; the master sends tasks to it (allow port 9000)",
        "WORKER_HOST=0.0.0.0",
        "WORKER_PORT=9000",
        f"WORKER_PUBLIC_URL={public_url}",
        "# With LLM_MOCK=1: seconds a mock task takes, so the Agents page shows busy",
        "MOCK_DELAY_SEC=15",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, *, token: str | None = None,
         output: Path = REPO / ".env", tailscale_ip=_tailscale_ip) -> int:
    parser = argparse.ArgumentParser(description="Write this PC's worker .env.")
    parser.add_argument("--agent", required=True, help="agent id in docs/agents.json")
    parser.add_argument("--master", required=True, help="http://<master Tailscale IP>:8000")
    parser.add_argument("--mock", action="store_true", help="LLM_MOCK=1 (no model needed)")
    parser.add_argument("--model", help="local model instead of the one in docs/agents.json")
    parser.add_argument("--force", action="store_true", help="replace an existing .env")
    args = parser.parse_args(argv)

    agents = {a["agent_id"]: a for a in json.loads(AGENTS_JSON.read_text(encoding="utf-8"))}
    if args.agent not in agents:
        print(f"Unknown agent {args.agent!r}. Known: {', '.join(sorted(agents))}")
        return 1
    if not args.master.startswith(("http://", "https://")):
        print("--master must look like http://100.x.y.z:8000")
        return 1
    if output.exists() and not args.force:
        print(f"{output.name} already exists; run again with --force to replace it "
              f"(the old file is kept as {output.name}.bak).")
        return 1

    if token is None:
        token = getpass.getpass("Team token (AGENT_TOKEN, from the master's owner; not shown): ")
    token = token.strip()
    if not token:
        print("No token given; nothing written.")
        return 1

    address = tailscale_ip()
    public_url = f"http://{address}:9000" if address else ""
    if output.exists():
        shutil.copyfile(output, output.with_name(output.name + ".bak"))
    output.write_text(build(agents[args.agent], token, args.master, args.mock, args.model,
                            public_url), encoding="utf-8")

    agent = agents[args.agent]
    print(f"Wrote {output.name} for {args.agent} ({agent['owner']}): "
          f"model {args.model or agent['model']}, LLM_MOCK={1 if args.mock else 0}, "
          f"master {args.master.rstrip('/')}")
    print(f"A2A address: {public_url}" if public_url else
          "Tailscale gave no address: start Tailscale, or write WORKER_PUBLIC_URL="
          "http://<this PC's Tailscale IP>:9000 into .env yourself.")
    print("Next: python -m dap.worker.main   then   python scripts/check_connection.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
