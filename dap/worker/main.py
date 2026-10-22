"""Worker program: registers with the master and keeps sending heartbeats.

Owner: Eray - card S1-07 (Sprint 3 adds the A2A server that runs tasks).

    python -m dap.worker.main
    python -m dap.worker.main --env-file .env.worker1

Every HEARTBEAT_INTERVAL_SEC the worker sends its status to the master.
- The master is down or unreachable: log it and try again next time.
- The master answers 404 (it does not know this agent): register again.
- A wrong AGENT_TOKEN gives 401: log it clearly and keep trying.
Stop with Ctrl+C.
"""

import argparse
import logging
import threading
from collections.abc import Callable

import httpx

from dap.shared.enums import AgentStatus
from dap.shared.schemas import Heartbeat
from dap.worker.config import WorkerSettings, get_settings, load_env

API = "/api/v1"

logger = logging.getLogger("dap.worker")

# Returns the status and current task id the heartbeat reports (idle until Sprint 3).
StatusSource = Callable[[], tuple[AgentStatus, str | None]]


def _idle() -> tuple[AgentStatus, str | None]:
    return AgentStatus.IDLE, None


def _headers(settings: WorkerSettings) -> dict[str, str]:
    return {"X-Agent-Token": settings.agent_token}


def register(client: httpx.Client, settings: WorkerSettings) -> None:
    """POST /agents/register; raises httpx.HTTPError when it does not succeed."""
    body = settings.to_register_payload().model_dump(mode="json")
    response = client.post(f"{API}/agents/register", json=body, headers=_headers(settings))
    response.raise_for_status()


def send_heartbeat(
    client: httpx.Client,
    settings: WorkerSettings,
    status: AgentStatus,
    current_task_id: str | None,
) -> bool:
    """POST the heartbeat. False when the master does not know this agent (404)."""
    body = Heartbeat(status=status, current_task_id=current_task_id).model_dump(mode="json")
    response = client.post(
        f"{API}/agents/{settings.agent_id}/heartbeat", json=body, headers=_headers(settings)
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    return True


def run(
    client: httpx.Client,
    settings: WorkerSettings,
    stop: threading.Event,
    status: StatusSource = _idle,
) -> None:
    """Register, then send a heartbeat every interval until stop is set."""
    registered = False
    while not stop.is_set():
        try:
            if not registered:
                register(client, settings)
                registered = True
                logger.info("Registered %s with %s", settings.agent_id, settings.master_url)
            elif not send_heartbeat(client, settings, *status()):
                logger.warning("The master does not know %s; registering again", settings.agent_id)
                registered = False
                continue
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            if exc.response.status_code == 401:
                detail = "wrong AGENT_TOKEN (it must be the same as on the master)"
            logger.error("Master answered %s: %s", exc.response.status_code, detail)
        except httpx.HTTPError as exc:
            logger.warning("Cannot reach the master at %s: %s", settings.master_url, exc)
        stop.wait(settings.heartbeat_interval_sec)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dap.worker.main")
    parser.add_argument("--env-file", help="read this file instead of .env")
    args = parser.parse_args(argv)

    load_env(args.env_file)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    logger.info("Worker %s (%s) starting, master %s", settings.agent_id, settings.model,
                settings.master_url)

    stop = threading.Event()
    with httpx.Client(base_url=settings.master_url, timeout=10) as client:
        try:
            run(client, settings, stop)
        except KeyboardInterrupt:
            stop.set()
            logger.info("Worker stopped")


if __name__ == "__main__":
    main()
