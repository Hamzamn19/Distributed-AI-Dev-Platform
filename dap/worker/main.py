"""Worker loop (card S2-03). Run from the repository root:

    python -m dap.worker.main

Owner: Eray. What it does:

1. Registers with the master (waits and tries again while the master is down).
2. Sends a heartbeat every HEARTBEAT_INTERVAL_SEC from a background thread, so
   a long model call does not make the agent look offline; on 404 it registers
   again.
3. Asks for work every POLL_INTERVAL_SEC (GET /agents/{id}/tasks/next).
4. Runs a task with the local model (status busy), posts the TaskResult
   (one retry when the post fails), then goes back to idle.
5. Ctrl+C stops it cleanly and sends a last heartbeat with status offline.

Settings come only from .env through dap/worker/config.py.
"""

import logging
import threading
import time

import httpx

from dap.shared.enums import AgentStatus
from dap.shared.schemas import Heartbeat, Task, TaskResult
from dap.worker.config import WorkerSettings, get_settings
from dap.worker.executor import execute_task
from dap.worker.master_client import MASTER_ERRORS, AgentNotRegistered, MasterClient, MasterError

log = logging.getLogger("dap.worker")

RETRY_WAIT_SEC = 5
POST_ATTEMPTS = 2


class Worker:
    def __init__(self, settings: WorkerSettings, client: MasterClient):
        self.settings = settings
        self.client = client
        self.stop = threading.Event()
        self._lock = threading.Lock()
        self._status = AgentStatus.IDLE
        self._task_id: str | None = None

    # --- state shared with the heartbeat thread ---------------------------

    def _set_state(self, status: AgentStatus, task_id: str | None) -> None:
        with self._lock:
            self._status, self._task_id = status, task_id

    def _heartbeat_body(self) -> Heartbeat:
        with self._lock:
            return Heartbeat(status=self._status, current_task_id=self._task_id)

    # --- registration and heartbeat ---------------------------------------

    def register(self) -> None:
        """Register; keep trying while the master cannot be reached."""
        while not self.stop.is_set():
            try:
                self.client.register(self.settings.to_register_payload())
                log.info("registered as %s at %s", self.settings.agent_id, self.settings.master_url)
                return
            except (*MASTER_ERRORS, ValueError) as exc:
                log.warning("master not reachable (%s); trying again in %s s", exc, RETRY_WAIT_SEC)
                self.stop.wait(RETRY_WAIT_SEC)

    def heartbeat_once(self) -> None:
        try:
            if not self.client.send_heartbeat(self.settings.agent_id, self._heartbeat_body()):
                log.warning("master does not know this agent (404); registering again")
                self.register()
        except MASTER_ERRORS as exc:
            log.warning("heartbeat failed: %s", exc)

    def _heartbeat_loop(self) -> None:
        while not self.stop.wait(self.settings.heartbeat_interval_sec):
            self.heartbeat_once()

    # --- tasks ---------------------------------------------------------------

    def _post_result(self, result: TaskResult) -> Task | None:
        for attempt in range(1, POST_ATTEMPTS + 1):
            try:
                return self.client.post_result(result)
            except MasterError as exc:
                code = exc.status_code
                if result.files and (code == 409 or code >= 500):
                    # The master could not store the files (for example they clash
                    # with this run's output). Report a failure without files, so
                    # the master requeues the task instead of leaving it assigned.
                    detail = exc.text[:200]
                    log.warning("master refused the files (%s %s); reporting a failure", code, detail)
                    result = result.model_copy(update={
                        "success": False, "files": [], "summary": "Task failed",
                        "error": f"master could not store the files ({code}): {detail}",
                    })
                    continue
                if code < 500:
                    log.warning("master refused the result: %s", exc)
                    return None
                log.warning("posting the result failed (attempt %s): %s", attempt, exc)
                if attempt < POST_ATTEMPTS:
                    self.stop.wait(RETRY_WAIT_SEC)
            except MASTER_ERRORS as exc:
                log.warning("posting the result failed (attempt %s): %s", attempt, exc)
                if attempt < POST_ATTEMPTS:
                    self.stop.wait(RETRY_WAIT_SEC)
        return None

    def run_task(self, task: Task) -> Task | None:
        log.info("task %s (%s): %s", task.id, task.type, task.title)
        self._set_state(AgentStatus.BUSY, task.id)
        self.heartbeat_once()  # tell the master right away that this agent is busy
        try:
            project = None
            try:
                project = self.client.get_project(task.project_id)
            except MASTER_ERRORS:
                pass  # the task can still run without the requirement text
            result = execute_task(task, self.settings.agent_id,
                                  project.requirement_text if project else None)
            if result.success:
                log.info("done: %s file(s), %s tokens, %s ms",
                         len(result.files), result.tokens_used, result.duration_ms)
            else:
                log.warning("task failed: %s", result.error)
            updated = self._post_result(result)
            if updated is not None:
                log.info("master says task %s is %s", updated.id, updated.status)
            return updated
        finally:
            self._set_state(AgentStatus.IDLE, None)
            self.heartbeat_once()

    def poll_once(self) -> Task | None:
        """Ask for one task and run it. Returns the master's answer for that task."""
        try:
            task = self.client.next_task(self.settings.agent_id)
        except AgentNotRegistered:
            log.warning("master does not know this agent (404); registering again")
            self.register()
            return None
        except MASTER_ERRORS as exc:
            log.warning("asking for work failed: %s", exc)
            return None
        return self.run_task(task) if task else None

    def run(self) -> None:
        self.register()
        self.heartbeat_once()
        beat = threading.Thread(target=self._heartbeat_loop, name="heartbeat", daemon=True)
        beat.start()
        log.info("waiting for tasks (poll every %s s, Ctrl+C to stop)", self.settings.poll_interval_sec)
        while not self.stop.is_set():
            if self.poll_once() is None:
                self.stop.wait(self.settings.poll_interval_sec)

    def shutdown(self) -> None:
        self.stop.set()
        try:
            self.client.send_heartbeat(self.settings.agent_id,
                                       Heartbeat(status=AgentStatus.OFFLINE, current_task_id=None))
        except MASTER_ERRORS:
            pass
        self.client.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "openai"):  # one line per request is too much
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    worker = Worker(settings, MasterClient(settings.api_url, settings.agent_token))
    try:
        worker.run()
    except KeyboardInterrupt:
        log.info("Ctrl+C: stopping")
    finally:
        worker.shutdown()
        log.info("stopped")


if __name__ == "__main__":
    main()
