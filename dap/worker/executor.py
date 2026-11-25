"""Runs the tasks the master sends, one at a time, in the order received.

Owner: Eray - Sprint 3.

For each task: build the prompt (prompts.py), ask the local model, read the
SUMMARY line and the "=== FILE: <path> ===" blocks of the answer (the older JSON
shape {"summary", "files"} too; Markdown code fences around a file's content are
removed) and check the files: exactly the
task's target_files, none empty, Python files without syntax errors, and every
Python file really loads (verify(): the template, the dependency files and the
new files are written to a temporary folder and each new .py file is run once).
verify() then checks what the next agents rely on: init_db() runs twice and
every table has its list_/get_/add_/update_/delete_ functions; main.py calls only
defined database functions, has routes for every table and its GET routes answer;
the page calls only existing
routes and element ids; the generated tests run (some failing tests are accepted
after the last correction, with the count in the summary).

Self-correction: when a check fails, the model gets the problem (for example
"NameError: name 'database' is not defined") and answers again, at most
FIX_ROUNDS times. Still wrong after that: TASK_STATE_FAILED with the problem.
For known mistakes (HINTS) the problem also says the likely cause. A small model
often answers a correction with the very same files: it is then told so, and the
next answer is asked with more variety (REPEAT_TEMPERATURE).

With LLM_MOCK=1 no model is asked: every target file gets a fixed, working
content (MOCK_FILES), so the whole flow can be tested without Ollama.
MOCK_DELAY_SEC (default 0) makes a mock task take that long, so a demo can
show the agent as busy.
"""

import ast
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from collections.abc import Callable
from datetime import datetime, timezone
from html.parser import HTMLParser

from dap.shared.enums import A2ATaskState, AgentStatus, TaskType
from dap.shared.llm_client import chat
from dap.shared.schemas import (
    A2ATask,
    Artifact,
    DapTaskOutput,
    DapTaskPayload,
    GeneratedFile,
    Message,
    Part,
    TaskStatusA2A,
)
from dap.worker import prompts

logger = logging.getLogger("dap.worker")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ running one task


def _extract_json(text: str) -> dict:
    """Parse the model's JSON answer, tolerating code fences or stray prose."""
    text = text.strip()
    try:  # a plain JSON answer may itself contain ``` inside a file's content
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("the answer has no '=== FILE: <path> ===' blocks") from None
        return json.loads(text[start : end + 1])


_FENCE = re.compile(r"^\s*```[\w+.-]*[ \t]*\r?\n(.*?)\r?\n?```\s*$", re.DOTALL)


def clean_content(text: str) -> str:
    """Remove the Markdown code fence a model may wrap around a whole file."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def check_output(payload: DapTaskPayload, output: DapTaskOutput) -> None:
    """Exactly the target files (a revision: at least one of them), none empty,
    Python that compiles. Raises ValueError."""
    allowed = set(payload.target_files)
    written = [file.path for file in output.files]
    outside = [path for path in written if path not in allowed]
    if outside:
        raise ValueError(f"file outside target_files: {', '.join(outside)}. Write only "
                         f"{', '.join(payload.target_files)}: the other files belong to "
                         "other agents and stay as they are")
    if payload.type == TaskType.REVISION:
        # A follow-up changes only what the request needs: the unchanged files stay
        # as they are on disk, so the model does not have to repeat thousands of
        # tokens it already got (and a small model starts losing files when it must).
        if not written:
            raise ValueError("the model did not write any file: apply the request to at "
                             f"least one of {', '.join(payload.target_files)}")
    else:
        missing = [path for path in payload.target_files if path not in written]
        if missing:
            raise ValueError(f"the model did not write: {', '.join(missing)}")
    for file in output.files:
        if not file.content.strip():
            raise ValueError(f"empty file: {file.path}")
        if file.path.endswith(".py"):
            try:
                compile(file.content, file.path, "exec")
            except SyntaxError as exc:
                line = (exc.text or "").strip()  # the model sees which line to change
                raise ValueError(f"syntax error in {file.path}, line {exc.lineno}: {exc.msg}"
                                 + (f"\n    {line}" if line else "")) from None


FIX_ROUNDS = 2          # extra answers the model may give after a failed check
REPEAT_TEMPERATURE = 0.7  # for the answer after one that repeated the previous answer

_stop_event = threading.Event()  # set when the running task is cancelled (A2A CancelTask)
_live_lock = threading.Lock()
_live: dict = {}  # the model's writing progress of the current task (A2A progress)


def _live_report(round_number: int, task_type: str):
    """The on_chunk callback for the current task's model call (streaming).

    chat() reports the whole answer so far; from it we keep the current file
    (the last '=== FILE: ... ===' marker) and the last 600 characters.
    """
    marker = re.compile(r"=== FILE: *(?P<path>[^\s=]+) *===")

    def report(generated_tokens: int, text: str) -> None:
        current = None
        for match in marker.finditer(text):
            current = match.group(1)
        with _live_lock:
            _live.update(round=round_number, type=task_type, generated_tokens=generated_tokens,
                         current_file=current, tail=text[-600:])

    return report


def live_progress(task_id: str) -> dict:
    """The writing progress of one task (None when it is not generating now)."""
    with _live_lock:
        if _live.get("task_id") != task_id:
            return {}
        return {key: value for key, value in _live.items() if key != "task_id"}


def _live_start(task_id: str, task_type: str) -> None:
    with _live_lock:
        _live.clear()
        _live.update(task_id=task_id, type=task_type, round=0, generated_tokens=0,
                     current_file=None, tail="")


def _live_end() -> None:
    with _live_lock:
        _live.clear()


class TaskCanceled(Exception):
    """The master cancelled the task while the model was working on it."""


def cancel_requested() -> bool:
    """True when the task the executor is running right now was cancelled."""
    return _stop_event.is_set()

# Error text -> the likely cause, in words a small model acts on. First match wins.
HINTS: list[tuple[str, str]] = [
    ('near "WHERE": syntax error',
     "In SQL the WHERE part comes before ORDER BY and LIMIT. Build the query as "
     'sql = "SELECT * FROM <table>", add " WHERE ..." only when there is a search, '
     'and add " ORDER BY ..." at the very end.'),
    (": syntax error",
     "Check the order of the SQL parts: SELECT ... FROM ... JOIN ... WHERE ... GROUP BY "
     "... ORDER BY ... LIMIT ..., and that every opened bracket and quote is closed."),
    ("no such column",
     "A query names a column that its CREATE TABLE does not have: use the exact column "
     "names of your tables."),
    ("no such table", "A query names a table that init_db() does not create."),
    ("which backend/main.py does not have",
     "Delete from the page every part that uses those paths: its section, table, form, "
     "buttons and JavaScript. The page shows only what backend/main.py offers."),
    ("fixture 'client' not found",
     "Keep the ready lines above '--- write below this line ---' of tests/test_app.py: they "
     "give the `client`; tests/conftest.py is ready and must not be written."),
    ("UNIQUE constraint failed",
     "init_db() inserts sample data that is already there: insert it only when the table "
     "is empty."),
]


def hint(problem: str) -> str:
    """The likely cause of a known mistake, or an empty string."""
    for text, cause in HINTS:
        if text in problem:
            return f"Likely cause: {cause}"
    return ""
VERIFY_TIMEOUT_SEC = 60
TESTS_TIMEOUT_SEC = 120
# First words of the problem when only some generated tests fail. After the last
# correction such a task is still accepted, with the count in its summary.
TESTS_FAIL = "Some generated tests fail"

# Runs one generated file once, from the application folder, as `python <file>` would.
_RUN_FILE = (
    "import runpy, sys; sys.path.insert(0, '.'); "
    "runpy.run_path(sys.argv[1], run_name='dap_check')"
)

# database.py: init_db() twice (the app restarts), the five functions of every table,
# and each of them really called once: list (also with a search), add with sample values
# made from its parameters, get and delete of the new record.
_CHECK_DATABASE = '''
import inspect, sqlite3, sys, traceback
sys.path.insert(0, ".")
from backend import database, db
database.init_db()
try:
    database.init_db()
except Exception as exc:
    sys.exit(f"init_db() fails when it runs a second time (every restart of the app): "
             f"{type(exc).__name__}: {exc}. Use CREATE TABLE IF NOT EXISTS and add the "
             "sample data only when the table is empty.")


def singular(name):
    if name.endswith("ies"):
        return name[:-3] + "y"
    if name.endswith(("sses", "xes", "ches", "shes")):
        return name[:-2]
    return name[:-1] if name.endswith("s") else name


with sqlite3.connect(db.DB_PATH) as connection:
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
if not tables:
    sys.exit("init_db() creates no table")
missing = []
for table in tables:
    one = singular(table)
    for name in (f"list_{table}", f"get_{one}", f"add_{one}", f"update_{one}", f"delete_{one}"):
        if not callable(getattr(database, name, None)):
            missing.append(name)
if missing:
    sys.exit("backend/database.py does not define these functions: " + ", ".join(missing)
             + ". Write list_/get_/add_/update_/delete_ for every table.")


def call(name, *args):
    """Call a function of database.py; a broken business rule (ValueError) is allowed."""
    try:
        return getattr(database, name)(*args)
    except (ValueError, sqlite3.IntegrityError):  # a rule or a constraint said no: fine
        return None
    except Exception as exc:
        traceback.print_exc()
        shown = ", ".join(repr(a) for a in args)
        sys.exit(f"{name}({shown}) fails: {type(exc).__name__}: {exc}")


def sample(parameter):
    """A plausible value for a parameter of an add_ function."""
    kind, name = str(parameter.annotation).lower(), parameter.name.lower()
    if "bool" in kind or name.startswith(("is_", "has_")) or name in ("done", "active"):
        return True
    if "int" in kind or name.endswith("_id"):
        return 1
    if "float" in kind:
        return 1.0
    if "date" in name:
        return "2030-01-01"
    if "email" in name:
        return "check@example.com"
    return "Check value"


for table in tables:
    one = singular(table)
    rows = call(f"list_{table}")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        sys.exit(f"list_{table}() must answer a list of dicts, not {rows!r:.80}")
    if inspect.signature(getattr(database, f"list_{table}")).parameters:
        call(f"list_{table}", "a")
    add = getattr(database, f"add_{one}")
    needed = [p for p in inspect.signature(add).parameters.values()
              if p.default is inspect.Parameter.empty
              and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    values = [sample(p) for p in needed]
    record = call(f"add_{one}", *values)
    if record is None:
        continue  # the sample values broke a rule of the requirement: not a bug
    if not isinstance(record, dict) or "id" not in record:
        sys.exit(f"add_{one}(...) must answer the new record as a dict with its id, "
                 f"not {record!r:.80}. execute() answers the new id of an INSERT.")
    if not isinstance(call(f"get_{one}", record["id"]), dict):
        sys.exit(f"get_{one}({record['id']}) does not find the record add_{one} just added")
    if inspect.signature(getattr(database, f"list_{table}")).parameters:
        needle = next((str(v) for v in record.values()
                       if isinstance(v, str) and len(v.strip()) >= 3), None)
        if needle:
            hits = call(f"list_{table}", needle)
            if not any(isinstance(r, dict) and r.get("id") == record["id"] for r in hits or []):
                sys.exit(f"list_{table}({needle!r}) does not find the record add_{one} just "
                         "added: the search must really filter a text column, for example "
                         "sql += ' WHERE <text column> LIKE ?' with (f'%{search}%',).")
        misses = call(f"list_{table}", "zzqxjv77")
        if any(isinstance(r, dict) and r.get("id") == record["id"] for r in misses or []):
            sys.exit("list_<things>(search) ignores the search: a search that matches "
                     "nothing must answer an empty list, not every record.")
    call(f"delete_{one}", record["id"])
'''

# main.py: every GET route without a path parameter answers without a server error.
_CHECK_BACKEND = '''
import sys, traceback
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from backend.main import app
client = TestClient(app)
paths = [route.path for route in app.routes
         if "GET" in (getattr(route, "methods", None) or ()) and route.path.startswith("/api")
         and "{" not in route.path]
if not paths:
    sys.exit("backend/main.py has no GET route under /api")
if "/api/stats" not in paths:  # the page's dashboard relies on it (template of main.py)
    sys.exit('backend/main.py has no GET /api/stats route: add it, answering counts for '
             'the dashboard, for example {"tasks": 12, "done": 4}')
for path in paths:
    try:
        response = client.get(path)
    except Exception as exc:
        traceback.print_exc()
        sys.exit(f"GET {path} fails: {type(exc).__name__}: {exc}")
    if response.status_code >= 500:
        sys.exit(f"GET {path} answers {response.status_code}: {response.text[:200]}")
# A list route must pass ?search= on to its list_<things>(search) function: a search
# that matches nothing may not answer every record (the page's search box relies on it).
for base in [p for p in paths if p.count("/") == 2]:
    try:
        every = client.get(base).json()
        misses = client.get(base, params={"search": "zzqxjv77"}).json()
    except Exception:
        continue  # the GET checks above already failed loudly
    if (isinstance(every, list) and every and isinstance(misses, list)
            and len(misses) >= len(every)):
        sys.exit(f"GET {base}?search=... answers every record: the route must pass the "
                 "?search= value on to list_<things>(search), for example "
                 "def list_<things>(search: str | None = None) with "
                 "database.list_<things>(search).")
'''


def _run(root: Path, args: list[str], what: str, timeout: int = VERIFY_TIMEOUT_SEC,
         own: set[str] = frozenset()) -> str | None:
    """Run Python in the application folder; the last lines of the error, or None.

    own: the files of this task; the error says whether the failing line is in one
    of them or in a file of another agent.
    """
    try:
        result = subprocess.run([sys.executable, *args], cwd=root, capture_output=True,
                                text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"{what} did not finish within {timeout} s"
    if result.returncode == 0:
        return None
    lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
    return f"{what}:\n" + _failing_line(lines, root, own) + "\n".join(lines[-4:])


READY_FILES = ("backend/db.py", "frontend/lib.js", "tests/conftest.py")  # template parts no agent writes


def _failing_line(lines: list[str], root: Path, own: set[str]) -> str:
    """The deepest traceback frame in a generated file, so the model sees that line.

    The last lines of a traceback often point into a ready helper (backend/db.py),
    not into the line of the generated file that called it wrongly. When that line
    is in another agent's file, the model is told so: it cannot change that file.
    """
    frames = [i for i, line in enumerate(lines)
              if line.lstrip().startswith("File ") and root.name in line
              and not any(ready in line.replace("\\", "/") for ready in READY_FILES)]
    if not frames:
        return ""
    i = frames[-1]
    frame = lines[i].strip().replace("\\", "/")
    frame = re.sub(r'File "[^"]*' + re.escape(root.name) + r'/', 'File "', frame)
    code = lines[i + 1].strip() if i + 1 < len(lines) else ""
    path = re.match(r'File "([^"]+)"', frame)
    if not own or (path and path.group(1) in own):
        return f"Your line: {frame}\n    {code}\n"
    return (f"The error is inside {path.group(1) if path else 'another file'}, which another "
            f"agent wrote and you cannot change: call its functions exactly as they are "
            f"defined there.\n    {frame}\n    {code}\n")


def _defined_names(source: str) -> set[str]:
    """Top-level functions, classes, variables and imports of a Python file."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
    return names


HELPERS = {"connect", "execute", "fetch_all", "fetch_one"}  # backend/db.py


def check_database_calls(main_source: str, database_source: str) -> str | None:
    """Every database.<name> that main.py uses must be defined in database.py."""
    used = sorted({node.attr for node in ast.walk(ast.parse(main_source))
                   if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                   and node.value.id == "database"})
    defined = _defined_names(database_source)
    missing = [name for name in used if name not in defined]
    if not missing:
        return None
    functions = sorted(n for n in defined
                       if not n.startswith("_") and n[0].islower() and n not in HELPERS)
    return ("backend/main.py uses database." + ", database.".join(missing)
            + ", which backend/database.py does not define. Use only: " + ", ".join(functions))


_ROUTE = re.compile(r"@app\.(?:get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']")
_LIST_FUNCTION = re.compile(r"^def list_(\w+)\(", re.MULTILINE)


def check_routes_cover_tables(main_source: str, database_source: str) -> str | None:
    """Every table of database.py (a list_<things> function) has its /api/<things> routes.

    Pre-test of 17 November: database.py had a third table, main.py left it out, and
    the page then called routes that did not exist.
    """
    tables = _LIST_FUNCTION.findall(database_source)
    routed = {path.split("/")[2] for path in _ROUTE.findall(main_source)
              if path.startswith("/api/") and len(path.split("/")) > 2}
    missing = [table for table in tables if table not in routed]
    if not missing:
        return None
    return ("backend/main.py has no routes for " + ", ".join(missing) + ", although "
            "backend/database.py has their tables (list_" + ", list_".join(missing) + "). "
            "Add for each: GET /api/<things> (with ?search=), GET /api/<things>/{id}, "
            "POST /api/<things>, PUT /api/<things>/{id} and DELETE /api/<things>/{id}.")
_API_PATH = re.compile(r"[\"'`](/api/[^\"'`\s]*)")
_ELEMENT = re.compile(r"getElementById\(\s*[\"'`]([^\"'`$]+)[\"'`]\s*\)")
# An id given in markup the script builds, or set on an element: id="x", id=x, .id = "x"
_ID_IN_SCRIPT = re.compile(r"\bid\s*=\s*\\?[\"']?([\w-]+)")
_JS_COMMENTS = re.compile(r"/\*.*?\*/|^[ \t]*//[^\n]*", re.DOTALL | re.MULTILINE)


class _Page(HTMLParser):
    """Reads a page as a browser does: the ids of its elements and its inline scripts.

    Comments are skipped, ids may be written without quotes, and the text of a
    <script> block is kept as code.
    """

    def __init__(self, page: str):
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.scripts: list[str] = []
        self._in_script = False
        self.feed(page)
        self.close()

    def handle_comment(self, data):
        # A script inside a comment still names its lookups (the checker reports
        # them), while ids of elements inside a comment do not count.
        for body in re.findall(r"<script[^>]*>(.*?)</script>", data, re.DOTALL):
            self.scripts.append(body)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        self._in_script = tag == "script" and "src" not in values

    def handle_startendtag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_script:
            self.scripts.append(data)


def _route_pattern(path: str) -> re.Pattern:
    """/api/tasks/{id} -> a pattern that matches /api/tasks/7 (and a trailing slash).

    A page's template-literal segment (`${recordType}`) becomes `[^/]+` too: the
    page may build one call for several record types (for example api(`/api/${rt}`)
    over tickets, spots and payments). Its literal segments must still match.
    """
    parts = re.split(r"\{[^}]*\}|\$\{[^}]*\}", path)
    return re.compile("[^/]+".join(re.escape(part) for part in parts) + "/?")


def _path_matches(page_path: str, route: str) -> bool:
    """One page call matches one route, segment by segment.

    A template-literal segment of the page (`${recordType}`) may be any real
    segment (the page builds one call for several record types); a route
    parameter ({ticket_id}) accepts any value; literal segments must match.
    """
    page_segments = page_path.strip("/").split("/")
    route_segments = route.strip("/").split("/")
    if len(page_segments) != len(route_segments):
        return False
    for page_segment, route_segment in zip(page_segments, route_segments):
        if page_segment.startswith("${") or route_segment.startswith("{"):
            continue
        if page_segment != route_segment:
            return False
    return True


def check_frontend(page: str, main_source: str) -> str | None:
    """The page calls only routes of main.py and looks up only ids it has.

    The page is read as a browser reads it (_Page): comments are left out (the
    template's own comments show example paths), and so are template placeholders
    such as /api/<things>.
    """
    parsed = _Page(page)
    code = _JS_COMMENTS.sub("", "\n".join(parsed.scripts))
    route_paths = [p.split("?")[0] for p in _ROUTE.findall(main_source)]
    unknown = []
    for raw in _API_PATH.findall(code):
        if "<" in raw:
            continue
        path = raw.split("?")[0]
        base = path.rstrip("/")
        # '/api/tasks/' + id: the concatenated value is one more dynamic segment.
        candidates = [base, base + "/${next}"] if path.endswith("/") else [base]
        if not any(_path_matches(candidate, route.rstrip("/"))
                   for candidate in candidates for route in route_paths):
            unknown.append(raw)
    problems = []
    if unknown:
        problems.append("frontend/index.html calls " + ", ".join(sorted(set(unknown)))
                        + ", which backend/main.py does not have. Call only its routes: "
                        + ", ".join(sorted(set(route_paths)))
                        + " (backend/main.py stays as it is)")
    defined = parsed.ids | set(_ID_IN_SCRIPT.findall(code))
    missing = sorted({i for i in _ELEMENT.findall(code) if i not in defined})
    if missing:
        problems.append("the script of frontend/index.html looks up element ids that the "
                        "page does not have: " + ", ".join(missing) + " (give an element "
                        "that id, outside any <!-- comment -->, or look up an id it has)")
    return "\n".join(problems) or None


def run_generated_tests(root: Path) -> str | None:
    """Run the generated tests; None when they all pass.

    A test that errors in its setup (for example a fixture that does not exist) counts
    like a failing one, and its cause (the "E ..." line) goes back to the model too.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-rfE", "--tb=line", "-p", "no:cacheprovider",
             "tests"], cwd=root, capture_output=True, text=True, timeout=TESTS_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return f"the generated tests did not finish within {TESTS_TIMEOUT_SEC} s"
    if result.returncode == 0:
        return None
    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    count = lambda word: int(m.group(1)) if (m := re.search(rf"(\d+) {word}", result.stdout)) else 0
    failed, errors = count("failed"), count("errors?")
    if result.returncode == 1 and failed + errors:
        total = count("passed") + failed + errors
        listed = [line for line in lines if line.startswith(("FAILED", "ERROR"))][:12]
        # the cause of each error, once: "E       fixture 'client' not found"
        causes = list(dict.fromkeys(line[1:].strip() for line in lines if line.startswith("E ")))[:4]
        return (f"{TESTS_FAIL}: {count('passed')} of {total} pass.\n" + "\n".join(listed + causes)
                + "\nFix the tests that use wrong routes, fields, status codes or data; "
                  "backend/main.py and backend/database.py stay as they are.")
    if result.returncode == 5:
        return "tests/test_app.py has no test functions (def test_...)"
    return "the generated tests cannot run:\n" + "\n".join(lines[-6:])


def verify(payload: DapTaskPayload, output: DapTaskOutput) -> str | None:
    """Put the new files next to the template and the dependency files and check them.

    Every new Python file must load. Then, by file: database.py survives a second
    init_db() and has the five functions of every table; main.py calls only defined
    database functions, has routes for every table and its GET routes answer; the page
    calls existing routes
    and element ids; the generated tests run and pass. Returns the problem, or None.
    """
    written = {f.path for f in output.files}
    with tempfile.TemporaryDirectory(prefix="dap-check-") as folder:
        root = Path(folder)
        if prompts.TEMPLATE_DIR.is_dir():
            shutil.copytree(prompts.TEMPLATE_DIR, root, dirs_exist_ok=True)
        for file in [*payload.dependency_files, *output.files]:
            target = root / file.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file.content, encoding="utf-8")

        def text(path: str) -> str:
            file = root / path
            return file.read_text(encoding="utf-8") if file.is_file() else ""

        for path in sorted(p for p in written if p.endswith(".py")):
            problem = _run(root, ["-c", _RUN_FILE, path], f"{path} fails when it is loaded",
                           own=written)
            if problem:
                return problem
        if "backend/database.py" in written:
            problem = _run(root, ["-c", _CHECK_DATABASE], "backend/database.py check",
                           own=written)
            if problem:
                return problem
        if "backend/main.py" in written:
            problem = (check_database_calls(text("backend/main.py"), text("backend/database.py"))
                       or check_routes_cover_tables(text("backend/main.py"),
                                                    text("backend/database.py"))
                       or _run(root, ["-c", _CHECK_BACKEND], "the GET routes of backend/main.py",
                               own=written))
            if problem:
                return problem
        if "frontend/index.html" in written:
            problem = check_frontend(text("frontend/index.html"), text("backend/main.py"))
            if problem:
                return problem
        if "tests/test_app.py" in written:
            return run_generated_tests(root)
    return None


_FILE_BLOCK = re.compile(
    r"^=== FILE: *(?P<path>[^\s=]+) *===[ \t]*\r?\n(?P<content>.*?)^=== END FILE ===",
    re.DOTALL | re.MULTILINE)
_SUMMARY = re.compile(r"^SUMMARY:[ \t]*(?P<summary>.+?)\s*$", re.MULTILINE)


def _read_answer(text: str, payload: DapTaskPayload) -> DapTaskOutput:
    """The SUMMARY line and FILE blocks of the answer (prompts.ANSWER_FORMAT).

    An answer in the older JSON shape {"summary", "files"} is read too.
    """
    blocks = list(_FILE_BLOCK.finditer(text))
    if blocks:
        summary = _SUMMARY.search(text)
        files = [GeneratedFile(path=block["path"], content=clean_content(block["content"]))
                 for block in blocks]
        return DapTaskOutput(summary=summary["summary"] if summary else payload.title,
                             files=files)
    if "=== FILE:" in text:
        raise ValueError("a FILE block has no '=== END FILE ===' line (the answer may be "
                         "cut off): write every file completely and close each block")
    data = _extract_json(text)
    files = [GeneratedFile(path=str(f.get("path", "")),
                           content=clean_content(str(f.get("content", ""))))
             for f in data.get("files", []) if isinstance(f, dict)]
    return DapTaskOutput(summary=str(data.get("summary") or payload.title), files=files)


REJECTED_DIR = Path(tempfile.gettempdir()) / "dap-rejected"


def _keep_rejected(payload: DapTaskPayload, round_number: int, text: str) -> Path:
    """Save a rejected model answer, so a person can see what the check refused."""
    REJECTED_DIR.mkdir(exist_ok=True)
    file = REJECTED_DIR / f"{payload.task_id}-answer{round_number + 1}.txt"
    file.write_text(text, encoding="utf-8")
    return file


def execute(payload: DapTaskPayload) -> DapTaskOutput:
    """Do one task with the local model (or the mock) and return its files.

    Raises TaskCanceled when the master cancelled the task in the meantime: the
    answer is thrown away and no file is written.
    """
    if os.getenv("LLM_MOCK", "0").strip() == "1":
        time.sleep(float(os.getenv("MOCK_DELAY_SEC", "0")))
        if cancel_requested():
            raise TaskCanceled("cancelled by the user")
        files = [GeneratedFile(path=path, content=MOCK_FILES.get(path, f"# {path}\n"))
                 for path in payload.target_files]
        return DapTaskOutput(summary=f"Mock output for: {payload.title}", files=files)

    first = prompts.build_messages(payload)
    messages = first
    prompt_tokens = completion_tokens = duration_ms = 0
    problem = previous = ""
    repeated = False
    for round_number in range(1 + FIX_ROUNDS):
        if cancel_requested():
            raise TaskCanceled("cancelled by the user")
        # plain text blocks; RuntimeError: model down — streamed, so the master's
        # /projects/{id}/live endpoint shows the model writing live (Sprint 4)
        answer = ((chat(messages, json_mode=False, temperature=REPEAT_TEMPERATURE,
                        on_chunk=_live_report(round_number, payload.type.value)) if repeated
                  else chat(messages, json_mode=False,
                            on_chunk=_live_report(round_number, payload.type.value))))
        prompt_tokens += answer.prompt_tokens
        completion_tokens += answer.completion_tokens
        duration_ms += answer.duration_ms
        logger.info("Task %s, answer %d: %d prompt + %d completion tokens, %.0f s",
                    payload.title, round_number + 1, answer.prompt_tokens,
                    answer.completion_tokens, answer.duration_ms / 1000)
        output = None
        try:
            output = _read_answer(answer.text, payload)
            check_output(payload, output)
            if cancel_requested():
                raise TaskCanceled("cancelled by the user")
            problem = verify(payload, output) or ""
        except (ValueError, json.JSONDecodeError) as exc:
            problem = str(exc)
        last_round = round_number == FIX_ROUNDS
        if not problem or (last_round and problem.startswith(TESTS_FAIL)):
            output.prompt_tokens, output.completion_tokens = prompt_tokens, completion_tokens
            output.duration_ms = duration_ms
            if round_number:
                output.summary += f" (corrected {round_number}x)"
            if problem:
                output.summary += f" (tests: {problem.splitlines()[0][len(TESTS_FAIL) + 2:]})"
            return output
        logger.warning("Task %s, answer %d: %s (answer kept in %s)", payload.title,
                       round_number + 1, problem, _keep_rejected(payload, round_number, answer.text))
        repeated = answer.text.strip() == previous
        previous = answer.text.strip()
        cause = hint(problem)
        same = ("\nYour answer was exactly the same as your previous one, so the problem is "
                "still there: change the failing line." if repeated else "")
        # Only the last answer goes back, so the conversation does not grow every round.
        messages = [*first, {"role": "assistant", "content": answer.text}, {
            "role": "user",
            "content": f"Your files have this problem:\n{problem}\n"
                       f"{cause + chr(10) if cause else ''}{same}\nFix it. You may change "
                       f"only {', '.join(payload.target_files)}. Answer again with the "
                       "complete corrected files, in the same format: the SUMMARY line and "
                       "one FILE block per path, no Markdown fences.",
        }]
    raise ValueError(f"still wrong after {FIX_ROUNDS} corrections: {problem}")


# ------------------------------------------------------------ the queue of A2A tasks


class Executor:
    """In-memory A2A task store plus one thread that runs the tasks in order."""

    def __init__(self, run: Callable[[DapTaskPayload], DapTaskOutput] = execute):
        self._run = run
        self._tasks: dict[str, A2ATask] = {}
        self._payloads: dict[str, DapTaskPayload] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._current: str | None = None
        self._canceled: set[str] = set()  # A2A CancelTask: stop at the next check
        threading.Thread(target=self._loop, name="executor", daemon=True).start()

    def submit(self, payload: DapTaskPayload, context_id: str | None) -> A2ATask:
        """Store a new task as SUBMITTED and queue it; returns at once."""
        task = A2ATask(
            id=str(uuid.uuid4()),
            context_id=context_id,
            status=TaskStatusA2A(state=A2ATaskState.SUBMITTED, timestamp=_now()),
        )
        with self._lock:
            self._tasks[task.id] = task
            self._payloads[task.id] = payload
        self._queue.put(task.id)
        logger.info("Queued task %s (%s: %s)", task.id, payload.type.value, payload.title)
        return task.model_copy(deep=True)

    def get(self, task_id: str) -> A2ATask | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def cancel(self, task_id: str) -> bool:
        """A2A CancelTask: the task stops at its next check; True when it was open.

        A task that is still queued never starts. A task the model is working on
        stops at its next round (the running model call itself finishes; its
        answer is thrown away). A finished task cannot be cancelled.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.status.state in (
                    A2ATaskState.COMPLETED, A2ATaskState.FAILED, A2ATaskState.CANCELED):
                return False
            self._canceled.add(task_id)
        if self._current == task_id:
            _stop_event.set()
        return True

    def status(self) -> tuple[AgentStatus, str | None]:
        """For the heartbeat: busy with the master's task id while work is waiting."""
        with self._lock:
            if self._current is not None:
                return AgentStatus.BUSY, self._payloads[self._current].task_id
        if not self._queue.empty():
            return AgentStatus.BUSY, None
        return AgentStatus.IDLE, None

    def _set(self, task_id: str, state: A2ATaskState, *, error: str | None = None,
             output: DapTaskOutput | None = None) -> None:
        with self._lock:
            task = self._tasks[task_id]
            message = None
            if error is not None:
                message = Message(message_id=str(uuid.uuid4()), role="ROLE_AGENT",
                                  parts=[Part(text=error)])
            task.status = TaskStatusA2A(state=state, message=message, timestamp=_now())
            if output is not None:
                task.artifacts = [Artifact(
                    artifact_id=str(uuid.uuid4()), name="result",
                    parts=[Part(data=output.model_dump(mode="json"),
                                media_type="application/json")],
                )]

    def _loop(self) -> None:
        while True:
            task_id = self._queue.get()
            payload = self._payloads[task_id]
            if task_id in self._canceled:  # cancelled while it was still queued
                self._set(task_id, A2ATaskState.CANCELED, error="cancelled by the user")
                continue
            with self._lock:
                self._current = task_id
            _stop_event.clear()
            _live_start(task_id, payload.type.value)
            self._set(task_id, A2ATaskState.WORKING)
            logger.info("Working on %s (%s)", task_id, payload.title)
            start = time.perf_counter()
            try:
                output = self._run(payload)
                if task_id in self._canceled:  # cancelled while the model worked
                    raise TaskCanceled("cancelled by the user")
                check_output(payload, output)
                if not output.duration_ms:
                    output.duration_ms = int((time.perf_counter() - start) * 1000)
                self._set(task_id, A2ATaskState.COMPLETED, output=output)
                logger.info("Completed %s: %s", task_id, output.summary)
            except TaskCanceled:
                self._set(task_id, A2ATaskState.CANCELED, error="cancelled by the user")
                logger.info("Cancelled %s", task_id)
            except Exception as exc:  # the model, the JSON or the files: report, never crash
                self._set(task_id, A2ATaskState.FAILED, error=f"{type(exc).__name__}: {exc}")
                logger.error("Task %s failed: %s", task_id, exc)
            finally:
                with self._lock:
                    self._current = None
                _live_end()
                _stop_event.clear()
                self._canceled.discard(task_id)


# ------------------------------------------- LLM_MOCK=1: a small app that really runs
# One working "items" application. Phase 5 checks that these files, written into
# the template, start with `uvicorn backend.main:app` and answer on /api/items.

MOCK_FILES: dict[str, str] = {
    "backend/database.py": '''"""SQLite storage (mock output): one table of items."""

from backend.db import connect, execute, fetch_all, fetch_one


def init_db() -> None:
    with connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL)"
        )


def list_items(search: str | None = None) -> list[dict]:
    return fetch_all("SELECT id, name FROM items WHERE name LIKE ? ORDER BY id",
                     (f"%{search or ''}%",))


def get_item(item_id: int) -> dict | None:
    return fetch_one("SELECT id, name FROM items WHERE id = ?", (item_id,))


def add_item(name: str) -> dict:
    return get_item(execute("INSERT INTO items (name) VALUES (?)", (name,)))


def update_item(item_id: int, name: str) -> dict | None:
    execute("UPDATE items SET name = ? WHERE id = ?", (name, item_id))
    return get_item(item_id)


def delete_item(item_id: int) -> bool:
    return execute("DELETE FROM items WHERE id = ?", (item_id,)) > 0
''',
    "backend/main.py": '''"""FastAPI routes (mock output). Run from the app folder: uvicorn backend.main:app"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import database

app = FastAPI(title="Generated app")
database.init_db()


class ItemIn(BaseModel):
    name: str


def found(record):
    if not record:
        raise HTTPException(status_code=404, detail="Item not found")
    return record


@app.get("/api/items")
def list_items(search: str | None = None) -> list[dict]:
    return database.list_items(search)


@app.get("/api/items/{item_id}")
def get_item(item_id: int) -> dict:
    return found(database.get_item(item_id))


@app.post("/api/items", status_code=201)
def add_item(item: ItemIn) -> dict:
    return database.add_item(item.name)


@app.put("/api/items/{item_id}")
def update_item(item_id: int, item: ItemIn) -> dict:
    return found(database.update_item(item_id, item.name))


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(item_id: int) -> None:
    found(database.delete_item(item_id))


@app.get("/api/stats")
def stats() -> dict:
    return {"items": len(database.list_items())}


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
''',
    "frontend/index.html": '''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Generated app</title></head>
<body>
  <h1>Items</h1>
  <form id="add"><input id="name" placeholder="Name" required> <button>Add</button></form>
  <ul id="items"></ul>
  <script>
    // Mock output: lists the items and adds new ones through the /api routes.
    async function load() {
      const items = await (await fetch("/api/items")).json();
      document.getElementById("items").innerHTML = items.map((i) => `<li>${i.name}</li>`).join("");
    }

    document.getElementById("add").addEventListener("submit", async (event) => {
      event.preventDefault();
      const name = document.getElementById("name");
      await fetch("/api/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.value }),
      });
      name.value = "";
      load();
    });

    load();
  </script>
</body>
</html>
''',
    "tests/test_app.py": '''"""Tests of the generated backend (mock output). Run from the app folder: python -m pytest"""

from fastapi.testclient import TestClient

from backend.main import app  # tests/conftest.py has already pointed it at a test database

client = TestClient(app)


def test_add_and_list_items():
    created = client.post("/api/items", json={"name": "First"})
    assert created.status_code == 201
    assert any(item["name"] == "First" for item in client.get("/api/items").json())
''',
}
