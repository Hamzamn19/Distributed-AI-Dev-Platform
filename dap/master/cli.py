"""Small command line helper for the master (httpx only).

Owner: Baran.

    python -m dap.master.cli agents
    python -m dap.master.cli project <file or text> [--name NAME]

The master address comes from MASTER_URL in .env (no default).
"""

import argparse
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

API = "/api/v1"


def _table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    lines = [" | ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip()
             for row in [header, *rows]]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def _get(client: httpx.Client, method: str, path: str, **kwargs):
    response = client.request(method, f"{API}{path}", **kwargs)
    if response.status_code >= 400:
        detail = response.json().get("detail", response.text) if response.content else ""
        raise SystemExit(f"Error {response.status_code} from {path}: {detail}")
    return response.json()


def show_agents(client: httpx.Client) -> str:
    agents = _get(client, "GET", "/agents")
    if not agents:
        return "No agents registered."
    rows = [[a["agent_id"], a["model"], a["role_hint"] or "-", a["status"]] for a in agents]
    return _table(rows, ["agent", "model", "role", "status"])


def run_project(client: httpx.Client, requirement: str, name: str) -> str:
    project = _get(client, "POST", "/projects",
                   json={"name": name, "requirement_text": requirement})
    pid = project["id"]
    _get(client, "POST", f"/projects/{pid}/decompose")
    tasks = _get(client, "POST", f"/projects/{pid}/assign")
    titles = {t["id"]: t["title"] for t in tasks}
    rows = [
        [t["title"], t["type"], t["status"], t["assigned_agent_id"] or "-",
         ", ".join(titles.get(d, d) for d in t["depends_on"]) or "-"]
        for t in tasks
    ]
    out = [f"Project {pid} ({name})", _table(rows, ["task", "type", "status", "agent", "after"])]
    out += [f"  {t['title']}: {t['assignment_reason']}" for t in tasks if t["assignment_reason"]]
    return "\n".join(out)


def main(argv: list[str] | None = None, client: httpx.Client | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dap.master.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("agents", help="list registered agents")
    project = sub.add_parser("project", help="create, decompose and assign a project")
    project.add_argument("requirement", help="path of a text file, or the text itself")
    project.add_argument("--name", default="CLI project")
    args = parser.parse_args(argv)

    if client is None:
        load_dotenv()
        base_url = os.getenv("MASTER_URL")
        if not base_url:
            sys.exit("MASTER_URL is not set. Add MASTER_URL=... to .env (see .env.example).")
        client = httpx.Client(base_url=base_url, timeout=300)
    try:
        if args.command == "agents":
            print(show_agents(client))
        else:
            path = Path(args.requirement)
            text = path.read_text("utf-8") if path.is_file() else args.requirement
            print(run_project(client, text, args.name))
    except httpx.HTTPError as exc:
        print(f"Cannot reach the master: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
