"""Acceptance check of a generated application, run by the master after the last task.

Owner: Baran - Sprint 3 (contract section 12).

    expected_records(tasks) -> list[str]    the "Records: ..." line of the decomposer
    check(project_id, records) -> dict      also written to workspace/<project_id>/acceptance.json

No model is asked. A copy of workspace/<project_id>/ (never the folder itself, so no
app.db or __pycache__ lands in it) is loaded in a separate Python process with a
database of its own, and the routes the template fixes are tried with TestClient:

    GET /                       the page
    GET /api/stats
    for every record type (the /api/<things> routes in /openapi.json, plus the
    expected records that have no route, which fail):
        list, search, create (body made from the openapi schema), get, update,
        delete, get again (404)

A 400 answer is a business rule saying no ("rule"), not a broken application; the
steps after it are skipped. The result:

    {"started": bool, "error": str | None, "summary": "12 of 14 checks passed",
     "passed": int, "failed": int, "rules": int,
     "checks": [{"record": str | None, "step": str, "result": "pass" | "fail" | "rule"
                 | "skipped", "detail": "POST /api/books -> 201"}]}

"started": false means the application does not even load; the orchestrator then
marks the project failed.
"""

import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from dap.master.core import integrator
from dap.shared.schemas import Task

logger = logging.getLogger(__name__)

ACCEPTANCE_FILE = "acceptance.json"
TIMEOUT_SEC = 90
MARKER = "DAP-ACCEPTANCE:"  # the result line among anything the application prints

_RECORDS = re.compile(r"Records: (.+?)\. This task covers all of them\.")

# Runs in the copied application folder; argv[1] is the JSON list of expected records.
_SCRIPT = r'''
import datetime, json, random, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
MARKER = "DAP-ACCEPTANCE:"
result = {"started": False, "error": None, "checks": []}


def finish():
    checks = result["checks"]
    count = lambda kind: sum(1 for c in checks if c["result"] == kind)
    result.update(passed=count("pass"), failed=count("fail"), rules=count("rule"))
    tried = result["passed"] + result["failed"]
    result["summary"] = (f"{result['passed']} of {tried} checks passed" if result["started"]
                         else "the application does not start")
    print(MARKER + json.dumps(result))
    sys.exit(0)


try:
    from backend import db
    db.DB_PATH = Path(tempfile.mkdtemp()) / "acceptance.db"
    from fastapi.testclient import TestClient
    from backend.main import app
    client = TestClient(app, raise_server_exceptions=False)
    result["started"] = True
except BaseException as exc:
    result["error"] = f"{type(exc).__name__}: {exc}"[:500]
    finish()


def add(record, step, result_, detail):
    result["checks"].append({"record": record, "step": step, "result": result_,
                             "detail": detail})
    return result_


def call(record, step, method, path, expected, body=None):
    """One request; the result of the check and the answer (None when it broke)."""
    try:
        response = client.request(method, path, json=body)
    except Exception as exc:
        return add(record, step, "fail", f"{method} {path} -> {type(exc).__name__}: {exc}"), None
    detail = f"{method} {path} -> {response.status_code}"
    if response.status_code in expected:
        return add(record, step, "pass", detail), response
    if response.status_code == 400:
        return add(record, step, "rule", f"{detail} {response.text[:160]}"), response
    return add(record, step, "fail", f"{detail} {response.text[:160]}"), response


def skip(record, steps):
    for step in steps:
        add(record, step, "skipped", "an earlier step did not pass")


try:
    page = client.get("/")
    ok = page.status_code == 200 and "<html" in page.text.lower()
    add(None, "page", "pass" if ok else "fail", f"GET / -> {page.status_code}")
except Exception as exc:
    add(None, "page", "fail", f"GET / -> {type(exc).__name__}: {exc}")
call(None, "stats", "GET", "/api/stats", (200,))

try:
    schema = client.get("/openapi.json").json()
except Exception as exc:
    add(None, "routes", "fail", f"GET /openapi.json -> {type(exc).__name__}: {exc}")
    finish()
paths = schema.get("paths", {})
found = [m.group(1) for p in paths if (m := re.fullmatch(r"/api/([a-z][a-z0-9_]*)", p))
         and m.group(1) != "stats" and "get" in paths[p]]
for name in json.loads(sys.argv[1]):
    if name not in found:
        add(name, "routes", "fail", f"no GET /api/{name} route for this record of the plan")


def item_path(name):
    for p in paths:
        if re.fullmatch(rf"/api/{name}/\{{[^}}]+\}}", p):
            return p
    return None


def follow(part):
    if isinstance(part, dict) and "$ref" in part:
        target = schema
        for key in part["$ref"].lstrip("#/").split("/"):
            target = target[key]
        return follow(target)
    if isinstance(part, dict) and "anyOf" in part:
        options = [o for o in part["anyOf"] if o.get("type") != "null"]
        return follow(options[0]) if options else {}
    return part if isinstance(part, dict) else {}


def first_id(things):
    try:
        rows = client.get(f"/api/{things}").json()
        return rows[0]["id"] if rows else 1
    except Exception:
        return 1


def plural(one):
    if one.endswith("y") and not one.endswith(("ay", "ey", "oy", "uy")):
        return one[:-1] + "ies"
    return one + ("es" if one.endswith(("s", "x", "ch", "sh")) else "s")


def value(name, part):
    part, low = follow(part), name.lower()
    kind, fmt = part.get("type"), part.get("format", "")
    if "enum" in part:
        return part["enum"][0]
    pattern = part.get("pattern")
    if pattern:
        # The pattern usually lists the allowed values: ^(active|completed)$.
        choices = [c.strip().strip("^$") for c in re.sub(r"[()]", "", pattern).split("|")
                   if c.strip().strip("^$")] if re.fullmatch(r"\^?\([^)]+\)\$?", pattern) else []
        if choices:
            return choices[0]
    if "default" in part and part["default"] is not None:
        return part["default"]
    if kind in ("integer", "number"):
        if low.endswith("_id"):
            return first_id(plural(low[:-3]))
        low_limit = part.get("minimum", part.get("exclusiveMinimum", 0))
        number = max(1, low_limit + (1 if "exclusiveMinimum" in part else 0))
        if "maximum" in part:
            number = min(number, part["maximum"])
        return number if kind == "integer" else float(number)
    if kind == "boolean":
        return False
    if kind == "array":
        return []
    if kind == "object":
        return {}
    today = datetime.date.today() + datetime.timedelta(days=7)
    if fmt == "date" or "date" in low:
        return today.isoformat()
    if fmt == "date-time":
        return f"{today.isoformat()}T12:00:00"
    if "time" in low:
        return "12:00"
    if fmt == "email" or "email" in low:
        return f"check{random.randint(1000, 9999)}@example.com"
    text = f"Check {low.replace('_', ' ')} {random.randint(1000, 9999)}"
    if part.get("maxLength"):
        text = text[: part["maxLength"]]
    return text.ljust(part.get("minLength", 0), "x")


def body_for(path, method):
    operation = paths.get(path, {}).get(method, {})
    content = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
    model = follow(content.get("schema", {}))
    return {name: value(name, part) for name, part in model.get("properties", {}).items()}


for name in found:
    steps = ["list", "search", "create", "get", "update", "delete", "gone"]
    base = f"/api/{name}"
    outcome, response = call(name, "list", "GET", base, (200,))
    if outcome == "pass" and not isinstance(response.json(), list):
        result["checks"][-1].update(result="fail", detail=f"GET {base} answers no list")
    call(name, "search", "GET", f"{base}?search=a", (200,))
    if "post" not in paths.get(base, {}):
        add(name, "create", "fail", f"no POST {base} route")
        skip(name, steps[3:])
        continue
    body = body_for(base, "post")
    outcome, response = call(name, "create", "POST", base, (200, 201), body)
    new_id = None
    if outcome == "pass":
        try:
            new_id = response.json().get("id")
        except Exception:
            pass
        if new_id is None:
            result["checks"][-1].update(result="fail",
                                        detail=f"POST {base} answers no record with an id")
    if new_id is None:
        skip(name, steps[3:])
        continue
    item = item_path(name)
    if item is None:
        add(name, "get", "fail", f"no {base}/{{id}} route")
        skip(name, steps[4:])
        continue
    one = re.sub(r"\{[^}]+\}", str(new_id), item)
    call(name, "get", "GET", one, (200,))
    if "put" in paths[item]:
        call(name, "update", "PUT", one, (200,), body_for(item, "put") or body)
    else:
        add(name, "update", "fail", f"no PUT {item} route")
    if "delete" in paths[item]:
        outcome, _ = call(name, "delete", "DELETE", one, (200, 204))
        if outcome == "pass":
            call(name, "gone", "GET", one, (404,))
        else:
            skip(name, ["gone"])
    else:
        add(name, "delete", "fail", f"no DELETE {item} route")
        skip(name, ["gone"])
finish()
'''


def expected_records(tasks: list[Task]) -> list[str]:
    """The record names the decomposer wrote into the task descriptions (may be empty)."""
    for task in tasks:
        match = _RECORDS.search(task.description)
        if match:
            names = [n.strip().lower().replace(" ", "_") for n in match.group(1).split(",")]
            return [n for n in names if n]
    return []


def _not_started(error: str) -> dict:
    return {"started": False, "error": error, "summary": "the application does not start",
            "passed": 0, "failed": 0, "rules": 0, "checks": []}


def run(folder: Path, records: list[str]) -> dict:
    """Load the application in folder (a copy of it) and try its routes."""
    with tempfile.TemporaryDirectory(prefix="dap-accept-") as copy:
        root = Path(copy) / "app"
        shutil.copytree(folder, root, ignore=shutil.ignore_patterns(
            ".git", "app.db", "__pycache__", ".pytest_cache"))
        try:
            done = subprocess.run([sys.executable, "-c", _SCRIPT, json.dumps(records)],
                                  cwd=root, capture_output=True, text=True,
                                  timeout=TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            return _not_started(f"the check did not finish within {TIMEOUT_SEC} s")
    for line in reversed(done.stdout.splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    lines = [line for line in done.stderr.strip().splitlines() if line.strip()]
    return _not_started("\n".join(lines[-4:]) or "the check gave no result")


def check(project_id: str, records: list[str] = ()) -> dict:
    """Run the acceptance check, write acceptance.json into the project and commit it."""
    report = run(integrator.project_dir(project_id), list(records))
    integrator.commit_master_file(project_id, ACCEPTANCE_FILE,
                                  json.dumps(report, indent=2) + "\n",
                                  f"master: acceptance check ({report['summary']})")
    logger.info("Acceptance check of project %s: %s", project_id, report["summary"])
    return report
