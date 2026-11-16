"""Contract-compliant HTTP smoke test for Master API and Sprint 3 Generated App."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

# Ensure repository root is importable when invoked as `python scripts/smoke_test.py`
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dap.shared.schemas import AgentRegister  # noqa: E402
from dap.worker.config import get_settings  # noqa: E402

AGENTS_REGISTRY_PATH = REPO_ROOT / "docs" / "agents.json"


def _fail(step: str, detail: str) -> None:
    print(f"[FAIL] {step}: {detail}", file=sys.stderr)
    print(f"SMOKE TEST FAILED at step: {step}", file=sys.stderr)
    sys.exit(1)


def run_smoke_test() -> None:
    settings = get_settings()
    base_url = settings.api_url
    headers = {"X-Agent-Token": settings.agent_token}

    print(f"[INFO] Running contract smoke test against {base_url}...")

    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        # 1. Health check
        step = "GET /api/v1/health"
        try:
            resp = client.get("/health")
            if resp.status_code != 200 or resp.json().get("status") != "ok":
                _fail(step, f"status={resp.status_code}, body={resp.text}")
            print(f"[PASS] {step} -> {resp.json()}")
        except Exception as exc:
            _fail(step, str(exc))

        # 2. Register all six agents from docs/agents.json
        step = "POST /api/v1/agents/register (6 agents)"
        try:
            if not AGENTS_REGISTRY_PATH.exists():
                _fail(step, f"Registry file not found: {AGENTS_REGISTRY_PATH}")
            raw_agents = json.loads(AGENTS_REGISTRY_PATH.read_text(encoding="utf-8"))
            if len(raw_agents) < 6:
                _fail(step, f"Expected 6 agents in {AGENTS_REGISTRY_PATH}, got {len(raw_agents)}")

            registered_ids: list[str] = []
            for entry in raw_agents:
                payload = AgentRegister.model_validate(entry).model_dump(mode="json")
                resp = client.post("/agents/register", json=payload, headers=headers)
                if resp.status_code != 200:
                    _fail(step, f"agent={entry.get('agent_id')} status={resp.status_code} body={resp.text}")
                registered_ids.append(entry["agent_id"])

                hb_resp = client.post(
                    f"/agents/{entry['agent_id']}/heartbeat",
                    json={"status": "idle", "current_task_id": None},
                    headers=headers,
                )
                if hb_resp.status_code != 200:
                    _fail(
                        f"POST /api/v1/agents/{entry['agent_id']}/heartbeat",
                        f"status={hb_resp.status_code} body={hb_resp.text}",
                    )
            print(f"[PASS] {step} -> registered & heartbeated {len(registered_ids)} agents")
        except SystemExit:
            raise
        except Exception as exc:
            _fail(step, str(exc))

        # 3. Create project with valid requirement_text (>= 20 chars)
        step = "POST /api/v1/projects"
        project_id = ""
        try:
            project_payload = {
                "name": "Smoke Test Todo App",
                "requirement_text": (
                    "Build a lightweight task manager web application with a FastAPI "
                    "backend, SQLite persistence, and a plain HTML/JS frontend."
                ),
            }
            resp = client.post("/projects", json=project_payload)
            if resp.status_code != 201:
                _fail(step, f"status={resp.status_code}, body={resp.text}")
            project_data = resp.json()
            project_id = project_data.get("id", "")
            if not project_id:
                _fail(step, f"Missing project id in response: {project_data}")
            print(f"[PASS] {step} -> project_id={project_id}")
        except SystemExit:
            raise
        except Exception as exc:
            _fail(step, str(exc))

        # 4. Decompose project using returned project_id
        step = f"POST /api/v1/projects/{project_id}/decompose"
        try:
            resp = client.post(f"/projects/{project_id}/decompose")
            if resp.status_code != 200:
                _fail(step, f"status={resp.status_code}, body={resp.text}")
            decomposed = resp.json()
            if not isinstance(decomposed, list) or len(decomposed) == 0:
                _fail(step, f"Expected non-empty task list, got: {decomposed}")
            print(f"[PASS] {step} -> created {len(decomposed)} tasks")
        except SystemExit:
            raise
        except Exception as exc:
            _fail(step, str(exc))

        # 5. Assign tasks using returned project_id
        step = f"POST /api/v1/projects/{project_id}/assign"
        try:
            resp = client.post(f"/projects/{project_id}/assign")
            if resp.status_code != 200:
                _fail(step, f"status={resp.status_code}, body={resp.text}")
            assigned = resp.json()
            if not isinstance(assigned, list) or len(assigned) == 0:
                _fail(step, f"Expected assigned task list, got: {assigned}")
            print(f"[PASS] {step} -> processed {len(assigned)} tasks")
        except SystemExit:
            raise
        except Exception as exc:
            _fail(step, str(exc))

        # 6. Verify tasks via GET /api/v1/projects/{project_id}/tasks
        step = f"GET /api/v1/projects/{project_id}/tasks"
        try:
            resp = client.get(f"/projects/{project_id}/tasks")
            if resp.status_code != 200:
                _fail(step, f"status={resp.status_code}, body={resp.text}")
            tasks = resp.json()
            if not isinstance(tasks, list) or len(tasks) == 0:
                _fail(step, f"No tasks returned for project {project_id}")
            assigned_count = sum(1 for t in tasks if t.get("assigned_agent_id"))
            if assigned_count == 0:
                _fail(step, "No tasks were assigned to any registered agent")
            print(f"[PASS] {step} -> verified {assigned_count}/{len(tasks)} tasks assigned")
        except SystemExit:
            raise
        except Exception as exc:
            _fail(step, str(exc))

    print("SMOKE TEST PASSED")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _locate_generated_app(workspace_dir: Path, project_id: str | None) -> tuple[Path, list[str]]:
    """Locate runnable generated app directory and command."""
    if not workspace_dir.exists():
        raise FileNotFoundError(f"Workspace directory not found: {workspace_dir}")

    candidates: list[Path] = []
    if project_id:
        target = workspace_dir / project_id
        if not target.exists():
            raise FileNotFoundError(f"Project directory not found: {target}")
        candidates.append(target)
    else:
        dirs = sorted(
            [d for d in workspace_dir.iterdir() if d.is_dir()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for proj_dir in dirs:
            # Workspace layout can be workspace/<project_id>/<run_id>/ or workspace/<project_id>/
            sub_runs = sorted(
                [d for d in proj_dir.iterdir() if d.is_dir() and d.name not in {"backend", "frontend", "database", "tests"}],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            candidates.extend(sub_runs)
            candidates.append(proj_dir)

    port = _find_free_port()
    for root in candidates:
        # 1. Contract Sprint 3 layout: backend/main.py (FastAPI)
        backend_main = root / "backend" / "main.py"
        if backend_main.exists():
            return root, [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ], port  # type: ignore[return-value]

        # 2. Root main.py (FastAPI or standalone script)
        root_main = root / "main.py"
        if root_main.exists():
            text = root_main.read_text(encoding="utf-8", errors="ignore")
            if "FastAPI" in text:
                return root, [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ], port  # type: ignore[return-value]
            return root, [sys.executable, "main.py"], int(os.getenv("GENERATED_APP_PORT", "5001"))  # type: ignore[return-value]

        # 3. Root app.py (Flask or standalone)
        root_app = root / "app.py"
        if root_app.exists():
            return root, [sys.executable, "app.py"], int(os.getenv("GENERATED_APP_PORT", "5001"))  # type: ignore[return-value]

    raise FileNotFoundError(f"No runnable generated app (backend/main.py, main.py, app.py) found in {workspace_dir}")


def run_generated_app_test(project_id: str | None = None) -> None:
    workspace_dir = REPO_ROOT / "workspace"
    try:
        located = _locate_generated_app(workspace_dir, project_id)
        app_cwd, cmd, port = located[0], located[1], located[2]  # type: ignore[index]
    except Exception as exc:
        print(f"[FAIL] Generated app discovery: {exc}", file=sys.stderr)
        sys.exit(1)

    app_url = os.getenv("GENERATED_APP_URL", f"http://127.0.0.1:{port}").rstrip("/")
    print(f"[INFO] Starting generated app in {app_cwd} via {' '.join(cmd)}...")

    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        cmd,
        cwd=str(app_cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        ready = False
        with httpx.Client(base_url=app_url, timeout=3.0) as client:
            for _ in range(25):
                if proc.poll() is not None:
                    stderr_out = (proc.stderr.read() if proc.stderr else b"").decode("utf-8", errors="ignore")
                    print(f"[FAIL] Generated app exited prematurely (code {proc.returncode}): {stderr_out}", file=sys.stderr)
                    sys.exit(1)
                for probe in ("/health", "/api/health", "/docs", "/"):
                    try:
                        r = client.get(probe)
                        if r.status_code < 500:
                            ready = True
                            break
                    except httpx.HTTPError:
                        continue
                if ready:
                    break
                time.sleep(0.4)

            if not ready:
                print(f"[FAIL] Generated app did not respond at {app_url} within timeout", file=sys.stderr)
                sys.exit(1)

            # Verify basic operations (root or OpenAPI/docs + any safe GET endpoint)
            verified = False
            for check_path in ("/", "/docs", "/health", "/api/health"):
                try:
                    resp = client.get(check_path)
                    if resp.status_code in (200, 201, 204):
                        print(f"[PASS] Generated app {check_path} -> HTTP {resp.status_code}")
                        verified = True
                        break
                except httpx.HTTPError:
                    continue

            if not verified:
                print(f"[FAIL] Generated app basic operation check failed at {app_url}", file=sys.stderr)
                sys.exit(1)

        print("GENERATED APP OK")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed AI Platform smoke tests")
    parser.add_argument(
        "mode",
        nargs="?",
        default="master",
        choices=["master", "generated"],
        help="Run 'master' API smoke test (default) or 'generated' app smoke test",
    )
    parser.add_argument(
        "--generated-app",
        action="store_true",
        help="Alias for running the Sprint 3 generated-app smoke test",
    )
    parser.add_argument(
        "--project-id",
        default=None,
        help="Optional workspace project ID for generated-app mode",
    )
    args = parser.parse_args()

    if args.generated_app or args.mode == "generated":
        run_generated_app_test(project_id=args.project_id)
    else:
        run_smoke_test()


if __name__ == "__main__":
    main()
