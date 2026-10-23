"""End-to-end check on one PC with LLM_MOCK=1 (Sprint 3).

    python scripts/e2e_local.py

Starts the master and two workers (A2A ports 9001 and 9002) as subprocesses,
with a temporary database and temporary env files, so data/dap.db and your .env
files are not touched. Then: workers registered -> project from
docs/sample_requirements/orta.md -> decompose -> assign -> run -> completed ->
workspace/<project_id>/ has the template files and four commits. Prints
E2E PASSED, or E2E FAILED and the step that failed (exit 1). The processes are
always stopped at the end; their logs are printed when a step fails.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[1]
TOKEN = "e2e-local-token"
WORKER_PORTS = (9001, 9002)
REQUIREMENT = REPO / "docs" / "sample_requirements" / "orta.md"
EXPECTED_FILES = [
    ".gitignore", "README.md", "backend/database.py", "backend/main.py",
    "frontend/app.js", "frontend/index.html", "requirements.txt", "tests/test_app.py",
]


class StepFailed(Exception):
    pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_for(step: str, check, timeout: float, interval: float = 0.5):
    """Call check() until it returns something truthy; StepFailed after timeout."""
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            result = check()
            if result:
                return result
        except httpx.HTTPError as exc:
            last = exc
        time.sleep(interval)
    raise StepFailed(f"{step} (waited {timeout:g} s{f'; last error: {last}' if last else ''})")


def start(command: list[str], env: dict, log: Path) -> subprocess.Popen:
    out = open(log, "w", encoding="utf-8")
    return subprocess.Popen(command, cwd=REPO, env=env, stdout=out, stderr=subprocess.STDOUT)


def main() -> int:
    for port in WORKER_PORTS:
        if not port_free(port):
            print(f"E2E FAILED at setup: port {port} is in use (stop the workers on this PC first)")
            return 1
    master_port = free_port()
    master_url = f"http://127.0.0.1:{master_port}"
    api = f"{master_url}/api/v1"
    tmp = Path(tempfile.mkdtemp(prefix="dap-e2e-"))
    processes: list[tuple[str, subprocess.Popen, Path]] = []

    base_env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "AGENT_", "WORKER_"))}
    master_env = {**base_env, "LLM_MOCK": "1", "AGENT_TOKEN": TOKEN,
                  "DATABASE_URL": f"sqlite:///{(tmp / 'e2e.db').as_posix()}",
                  "MASTER_HOST": "127.0.0.1", "MASTER_PORT": str(master_port),
                  "A2A_POLL_INTERVAL_SEC": "0.5", "HEARTBEAT_TIMEOUT_SEC": "30"}
    try:
        print(f"Master on {master_url}, workers on {WORKER_PORTS}, temporary files in {tmp}")
        log = tmp / "master.log"
        processes.append(("master", start([sys.executable, "-m", "dap.master"], master_env, log), log))
        wait_for("master /api/v1/health", lambda: httpx.get(f"{api}/health").status_code == 200, 30)
        print("ok  master started")

        for number, port in enumerate(WORKER_PORTS, start=1):
            env_file = tmp / f".env.e2e{number}"
            env_file.write_text("\n".join([
                f"AGENT_TOKEN={TOKEN}", f"MASTER_URL={master_url}", "LLM_MOCK=1",
                "MOCK_DELAY_SEC=0", "LLM_MODEL=mock-model", f"AGENT_ID=agent-e2e-{number}",
                f"AGENT_NAME=E2E-{number}", "AGENT_OWNER=e2e_local.py",
                f"AGENT_ROLE_HINT={'backend' if number == 1 else 'frontend'}",
                "WORKER_HOST=127.0.0.1", f"WORKER_PORT={port}",
                f"WORKER_PUBLIC_URL=http://127.0.0.1:{port}", "HEARTBEAT_INTERVAL_SEC=2",
            ]) + "\n", encoding="utf-8")
            log = tmp / f"worker{number}.log"
            processes.append((f"worker{number}", start(
                [sys.executable, "-m", "dap.worker.main", "--env-file", str(env_file)],
                base_env, log), log))

        def workers_ready():
            agents = {a["agent_id"]: a for a in httpx.get(f"{api}/agents").json()}
            return all(agents.get(f"agent-e2e-{n}", {}).get("a2a_url") for n in (1, 2))

        wait_for("both workers registered with an A2A address", workers_ready, 30)
        for number in (1, 2):
            card = httpx.get(f"{api}/agents/agent-e2e-{number}/card")
            if card.status_code != 200:
                raise StepFailed(f"master cannot reach worker {number}: {card.text}")
        print("ok  two workers registered and reachable over A2A")

        text = REQUIREMENT.read_text(encoding="utf-8")
        project = httpx.post(f"{api}/projects", json={"name": "E2E library", "requirement_text": text})
        if project.status_code != 201:
            raise StepFailed(f"create project: {project.status_code} {project.text}")
        pid = project.json()["id"]
        tasks = httpx.post(f"{api}/projects/{pid}/decompose", timeout=60).json()
        if [t["type"] for t in tasks] != ["database", "backend", "frontend", "testing"]:
            raise StepFailed(f"decompose: unexpected tasks {[t['type'] for t in tasks]}")
        assigned = httpx.post(f"{api}/projects/{pid}/assign").json()
        if not all(t["assigned_agent_id"] for t in assigned):
            raise StepFailed("assign: a task has no agent")
        print(f"ok  project {pid}: 4 tasks decomposed and assigned")

        run = httpx.post(f"{api}/projects/{pid}/run")
        if run.status_code != 202:
            raise StepFailed(f"run: {run.status_code} {run.text}")
        final = wait_for("project completed", lambda: (
            lambda s: s if s in ("completed", "failed") else None)(
            httpx.get(f"{api}/projects/{pid}").json()["status"]), 120)
        if final != "completed":
            failed = [r for r in httpx.get(f"{api}/projects/{pid}/results").json() if not r["success"]]
            raise StepFailed(f"run ended as {final}: {[r['error'] for r in failed]}")
        print("ok  run completed on the workers")

        files = httpx.get(f"{api}/projects/{pid}/files").json()
        if files != EXPECTED_FILES:
            raise StepFailed(f"workspace files: {files}")
        folder = REPO / "workspace" / pid
        log_lines = subprocess.run(["git", "log", "--format=%s"], cwd=folder, capture_output=True,
                                   text=True).stdout.splitlines()
        if len(log_lines) != 4:
            raise StepFailed(f"git log in {folder} has {len(log_lines)} commits: {log_lines}")
        print(f"ok  workspace/{pid}/ has the template files and 4 commits")
    except StepFailed as exc:
        print(f"E2E FAILED at {exc}")
        for name, process, log in processes:
            process.terminate()
            process.wait(10)
            print(f"--- {name} log ---\n{log.read_text(encoding='utf-8', errors='replace')[-3000:]}")
        return 1
    finally:
        for _, process, _ in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(10)
    print("E2E PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
