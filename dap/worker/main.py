"""Worker program: an A2A server that runs tasks, plus registration and heartbeats.

Owner: Eray - cards S1-07 and Sprint 3.

    python -m dap.worker.main
    python -m dap.worker.main --env-file .env.worker1

The A2A server (a2a_server.py) listens on WORKER_HOST:WORKER_PORT; the master
sends tasks to it. The worker registers with its A2A address (WORKER_PUBLIC_URL,
or the Tailscale address) and every HEARTBEAT_INTERVAL_SEC sends its status:
busy with the task id while a task runs or waits, idle otherwise.

When the master does not answer as expected:
- The master is down or unreachable: log it and try again next time.
- The master answers 404 (it does not know this agent): register again.
- A wrong AGENT_TOKEN gives 401: log it clearly and keep trying.
Stop with Ctrl+C.
"""

import argparse
import logging
import os
import threading
import time
from collections.abc import Callable

import httpx
import uvicorn

from dap.shared.enums import AgentStatus
from dap.shared.schemas import Heartbeat
from dap.worker.config import WorkerSettings, get_settings, load_env, resolve_public_url

API = "/api/v1"

logger = logging.getLogger("dap.worker")

# Returns the status and current task id the heartbeat reports (idle until Sprint 3).
StatusSource = Callable[[], tuple[AgentStatus, str | None]]


def _idle() -> tuple[AgentStatus, str | None]:
    return AgentStatus.IDLE, None


def _headers(settings: WorkerSettings) -> dict[str, str]:
    return {"X-Agent-Token": settings.agent_token}


def register(client: httpx.Client, settings: WorkerSettings, a2a_url: str | None = None) -> None:
    """POST /agents/register; raises httpx.HTTPError when it does not succeed."""
    body = settings.to_register_payload(a2a_url).model_dump(mode="json")
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
    a2a_url: str | None = None,
) -> None:
    """Register, then send a heartbeat every interval until stop is set."""
    registered = False
    while not stop.is_set():
        try:
            if not registered:
                register(client, settings, a2a_url)
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


def start_a2a_server(settings: WorkerSettings, executor, public_url: str) -> uvicorn.Server:
    """Run the A2A server in a background thread; stop the program if the port is taken."""
    from dap.worker.a2a_server import create_app

    app = create_app(settings, executor, public_url)
    server = uvicorn.Server(uvicorn.Config(
        app, host=settings.worker_host, port=settings.worker_port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="a2a-server", daemon=True)
    thread.start()
    for _ in range(100):  # up to 10 s
        if server.started:
            return server
        if not thread.is_alive():
            break
        time.sleep(0.1)
    raise SystemExit(
        f"The A2A server could not start on {settings.worker_host}:{settings.worker_port}. "
        "Is another worker using this port? Set a different WORKER_PORT in the env file.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="dap.worker.main")
    parser.add_argument("--env-file", help="read this file instead of .env")
    args = parser.parse_args(argv)

    load_env(args.env_file)
    # A revision task sends the whole generated application to the model; on a
    # worker PC that answer takes minutes (the master's decomposition is short,
    # so its own default of 120 s stays). Nothing set means the documented 600.
    if not os.getenv("LLM_TIMEOUT_SEC"):
        os.environ["LLM_TIMEOUT_SEC"] = "600"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from dap.worker.executor import Executor  # after load_env: reads LLM_* settings

    settings = get_settings()
    public_url = resolve_public_url(settings)
    executor = Executor()
    server = start_a2a_server(settings, executor, public_url)
    logger.info("Worker %s (%s): A2A server on %s:%s, public address %s, master %s",
                settings.agent_id, settings.model, settings.worker_host, settings.worker_port,
                public_url, settings.master_url)

    stop = threading.Event()
    with httpx.Client(base_url=settings.master_url, timeout=10) as client:
        try:
            run(client, settings, stop, status=executor.status, a2a_url=public_url)
        except KeyboardInterrupt:
            stop.set()
            server.should_exit = True
            logger.info("Worker stopped")


if __name__ == "__main__":
    main()
