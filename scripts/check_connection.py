"""Check the connection of a worker PC to the master over the tailnet (Sprint 3).

    python scripts/check_connection.py                         reads .env
    python scripts/check_connection.py --env-file .env.worker1

Run it on a worker PC while the master runs (start the worker too, for checks 4-6).
Each check prints OK or the most likely fix:

    1. this PC's Tailscale address (tailscale ip -4)
    2. the master answers at MASTER_URL/api/v1/health
    3. the master accepts AGENT_TOKEN
    4. this worker's A2A server answers on this PC
    5. this worker's A2A server answers at WORKER_PUBLIC_URL
    6. the master reaches this worker (it fetches the agent card for AGENT_ID)

Nothing is changed on the master: the token check uses an agent id that does not exist.
"""

import argparse
import sys

import httpx

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from dap.worker import config  # noqa: E402

PROBE_AGENT = "check-connection-probe"


def checks(settings: config.WorkerSettings, public_url: str, tailscale_ip: str | None,
           http=httpx) -> list[tuple[str, bool, str]]:
    """Run the checks; each is (name, ok, message)."""
    out: list[tuple[str, bool, str]] = []
    master = settings.master_url
    api = f"{master}/api/v1"

    local_only = all(host in url for url in (master, public_url) for host in ("127.0.0.1",)) or (
        "localhost" in master and "127.0.0.1" in public_url)
    if tailscale_ip:
        out.append(("Tailscale address", True, tailscale_ip))
    elif local_only:
        out.append(("Tailscale address", True, "not needed: the master and this worker are on this PC"))
    else:
        out.append(("Tailscale address", False,
                    "no Tailscale address: start Tailscale and sign in with the team account"))

    try:
        health = http.get(f"{api}/health", timeout=5)
        out.append(("master health", health.status_code == 200,
                    f"{master} answers" if health.status_code == 200 else
                    f"{master} answered {health.status_code}: is MASTER_URL the master's address?"))
    except httpx.HTTPError as exc:
        out.append(("master health", False,
                    f"cannot reach {master} ({type(exc).__name__}). Check: master started with "
                    "python -m dap.master; MASTER_URL uses the master's Tailscale IP and port 8000; "
                    "Tailscale is on on both PCs; the master PC's firewall allows port 8000"))
        return out

    probe = http.post(f"{api}/agents/{PROBE_AGENT}/heartbeat", timeout=5,
                      json={"status": "idle", "current_task_id": None},
                      headers={"X-Agent-Token": settings.agent_token})
    token_ok = probe.status_code == 404
    out.append(("AGENT_TOKEN", token_ok, "accepted by the master" if token_ok else
                "refused (401): AGENT_TOKEN must be the same as in the master's .env"
                if probe.status_code == 401 else f"unexpected answer {probe.status_code}"))

    local = f"http://127.0.0.1:{settings.worker_port}/.well-known/agent-card.json"
    try:
        local_ok = http.get(local, timeout=5).status_code == 200
    except httpx.HTTPError:
        local_ok = False
    out.append(("A2A server on this PC", local_ok, f"answers on port {settings.worker_port}"
                if local_ok else "no answer: start the worker (python -m dap.worker.main) and "
                f"check WORKER_PORT={settings.worker_port}"))

    try:
        public_ok = http.get(f"{public_url}/.well-known/agent-card.json", timeout=5).status_code == 200
    except httpx.HTTPError:
        public_ok = False
    out.append(("A2A server at WORKER_PUBLIC_URL", public_ok, f"{public_url} answers" if public_ok
                else f"{public_url} does not answer: WORKER_PUBLIC_URL must be "
                f"http://<this PC's Tailscale IP>:{settings.worker_port}"
                + ("" if local_ok else " (and the worker must be running)")))

    card = http.get(f"{api}/agents/{settings.agent_id}/card", timeout=15)
    if card.status_code == 200:
        out.append(("master reaches this worker", True, "the master can send tasks here"))
    elif card.status_code == 404:
        out.append(("master reaches this worker", False,
                    f"{settings.agent_id} is not registered or has no A2A address: start the worker"))
    elif not local_ok:
        out.append(("master reaches this worker", False,
                    "the worker is not running on this PC: start it, then run this check again"))
    else:
        out.append(("master reaches this worker", False,
                    f"the master cannot reach {public_url}. Most likely Windows Firewall on THIS "
                    f"PC blocks port {settings.worker_port}: allow Python, or run as administrator: "
                    f'New-NetFirewallRule -DisplayName "DAP worker {settings.worker_port}" '
                    f"-Direction Inbound -Protocol TCP -LocalPort {settings.worker_port} -Action Allow"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check this worker PC's connection.")
    parser.add_argument("--env-file", help="read this file instead of .env")
    args = parser.parse_args(argv)
    config.load_env(args.env_file)
    settings = config.get_settings()
    public_url = config.resolve_public_url(settings)
    print(f"Worker {settings.agent_id}, master {settings.master_url}, A2A address {public_url}\n")
    results = checks(settings, public_url, config._tailscale_ip())
    for name, ok, message in results:
        print(f"{'OK  ' if ok else 'FAIL'}  {name}: {message}")
    passed = all(ok for _, ok, _ in results) and len(results) == 6
    print("\nAll checks passed." if passed else "\nFix the first FAIL line and run the check again.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
