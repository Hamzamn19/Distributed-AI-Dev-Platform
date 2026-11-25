"""One-PC end-to-end run with the real local model (based on scripts/e2e_local.py).

Master and two workers all use gemma4-26b through the local /v1 shim (think:false)
on 127.0.0.1:8787. Requirement: docs/sample_requirements/kisa.md (the smallest
sample). Prints E2E PASSED, or E2E FAILED and the failing step (exit 1).
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

REPO = Path("/home/hamzah/Documents/Distributed-AI-Dev-Platform")
TOKEN = "e2e-real-token"
WORKER_PORTS = (9001, 9002)
REQUIREMENT = REPO / "docs" / "sample_requirements" / "kisa.md"
EXPECTED_FILES = [
    ".gitignore", "README.md", "acceptance.json", "backend/database.py", "backend/db.py", "backend/main.py",
    "frontend/index.html", "frontend/lib.js", "frontend/style.css",
    "requirements.txt", "tests/conftest.py", "tests/test_app.py",
]

LLM = {
    "LLM_BASE_URL": "http://127.0.0.1:8787/v1",  # shim: /v1 -> Ollama /api/chat with think:false
    "LLM_API_KEY": "ollama",
    "LLM_MODEL": "gemma4-26b",
    "LLM_THINK": "0",
    "LLM_TIMEOUT_SEC": "300",
    "LLM_MAX_TOKENS": "8192",
}


class StepFailed(Exception):
    pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_for(step: str, check, timeout: float, interval: float = 1.0):
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
            print(f"E2E FAILED at setup: port {port} is in use")
            return 1
    master_port = free_port()
    master_url = f"http://127.0.0.1:{master_port}"
    api = f"{master_url}/api/v1"
    tmp = Path(tempfile.mkdtemp(prefix="dap-e2e-real-"))
    processes: list[tuple[str, subprocess.Popen, Path]] = []

    base_env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "AGENT_", "WORKER_"))}
    master_env = {**base_env, **LLM, "AGENT_TOKEN": TOKEN,
                  "DATABASE_URL": f"sqlite:///{(tmp / 'e2e.db').as_posix()}",
                  "MASTER_HOST": "127.0.0.1", "MASTER_PORT": str(master_port),
                  "TASK_TIMEOUT_SEC": "1200",
                  "A2A_POLL_INTERVAL_SEC": "0.5", "HEARTBEAT_TIMEOUT_SEC": "30"}
    try:
        print(f"Master on {master_url}, workers on {WORKER_PORTS}, temporary files in {tmp}", flush=True)
        log = tmp / "master.log"
        processes.append(("master", start([sys.executable, "-m", "dap.master"], master_env, log), log))
        wait_for("master /api/v1/health", lambda: httpx.get(f"{api}/health").status_code == 200, 30)
        print("ok  master started", flush=True)

        for number, port in enumerate(WORKER_PORTS, start=1):
            env_file = tmp / f".env.e2e{number}"
            env_file.write_text("\n".join([
                f"AGENT_TOKEN={TOKEN}", f"MASTER_URL={master_url}",
                *(f"{k}={v}" for k, v in LLM.items()),
                f"AGENT_ID=agent-e2e-{number}",
                f"AGENT_NAME=E2E-Real-{number}", "AGENT_OWNER=e2e_real.py",
                f"AGENT_ROLE_HINT={'backend' if number == 1 else 'frontend'}",
                "AGENT_CAP_CODING=80", "AGENT_CAP_REASONING=80", "AGENT_CAP_CONTEXT=80",
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
        print("ok  two workers registered and reachable over A2A", flush=True)

        text = REQUIREMENT.read_text(encoding="utf-8")
        project = httpx.post(f"{api}/projects", json={"name": "E2E task tracker", "requirement_text": text})
        if project.status_code != 201:
            raise StepFailed(f"create project: {project.status_code} {project.text}")
        pid = project.json()["id"]
        t0 = time.monotonic()
        tasks = httpx.post(f"{api}/projects/{pid}/decompose", timeout=600).json()
        if [t["type"] for t in tasks] != ["database", "backend", "frontend", "testing"]:
            raise StepFailed(f"decompose: unexpected tasks {[t['type'] for t in tasks]}")
        assigned = httpx.post(f"{api}/projects/{pid}/assign").json()
        if not all(t["assigned_agent_id"] for t in assigned):
            raise StepFailed("assign: a task has no agent")
        print(f"ok  project {pid}: 4 tasks decomposed and assigned (decompose took "
              f"{time.monotonic() - t0:.0f} s with {LLM['LLM_MODEL']})", flush=True)

        run = httpx.post(f"{api}/projects/{pid}/run")
        if run.status_code != 202:
            raise StepFailed(f"run: {run.status_code} {run.text}")
        t0 = time.monotonic()
        final = wait_for("project completed", lambda: (
            lambda s: s if s in ("completed", "failed") else None)(
            httpx.get(f"{api}/projects/{pid}").json()["status"]), 2400)
        if final != "completed":
            failed = [r for r in httpx.get(f"{api}/projects/{pid}/results").json() if not r["success"]]
            raise StepFailed(f"run ended as {final}: {[r['error'] for r in failed]}")
        print(f"ok  run completed on the workers ({time.monotonic() - t0:.0f} s, real model)", flush=True)

        files = httpx.get(f"{api}/projects/{pid}/files").json()
        if files != EXPECTED_FILES:
            raise StepFailed(f"workspace files: {files}")
        folder = REPO / "workspace" / pid
        log_lines = subprocess.run(["git", "log", "--format=%s"], cwd=folder, capture_output=True,
                                   text=True).stdout.splitlines()
        if len(log_lines) != 5 or not log_lines[0].startswith("master: acceptance check"):
            raise StepFailed(f"git log in {folder} has {len(log_lines)} commits: {log_lines}")
        print(f"ok  workspace/{pid}/ has the template files, 4 task commits and the check", flush=True)

        report = httpx.get(f"{api}/projects/{pid}/files/acceptance.json").json()
        if not report["started"] or report["failed"]:
            raise StepFailed(f"acceptance check: {report['summary']}: "
                             f"{[c for c in report['checks'] if c['result'] == 'fail']}")
        print(f"ok  acceptance check: {report['summary']}", flush=True)
        print(f"PROJECT_ID={pid}", flush=True)
    except StepFailed as exc:
        print(f"E2E FAILED at {exc}", flush=True)
        for name, process, log in processes:
            process.terminate()
            process.wait(10)
            print(f"--- {name} log ---\n{log.read_text(encoding='utf-8', errors='replace')[-3000:]}",
                  flush=True)
        return 1
    finally:
        for _, process, _ in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(10)
    print("E2E PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
