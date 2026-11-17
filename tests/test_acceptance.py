"""The master's acceptance check of a generated application (dap/master/core/acceptance.py)."""

import shutil

from dap.master.core import acceptance, integrator
from dap.worker.executor import MOCK_FILES

APP_HEAD = '''from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend import database

app = FastAPI()
database.init_db()


@app.get("/api/stats")
def stats() -> dict:
    return {"items": len(database.list_items())}
'''
APP_TAIL = '''
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
'''


def make_app(tmp_path, **files):
    """The template filled with the mock files; files replaces some of them."""
    folder = tmp_path / "app"
    shutil.copytree(integrator.TEMPLATE_DIR, folder)
    for path, content in {**MOCK_FILES, **files}.items():
        (folder / path).write_text(content, encoding="utf-8")
    return folder


def results_by_step(report, record):
    return {c["step"]: c["result"] for c in report["checks"] if c["record"] == record}


def test_the_mock_application_passes_every_check(tmp_path):
    folder = make_app(tmp_path)
    report = acceptance.run(folder, ["items"])
    assert report["started"] is True
    assert report["failed"] == 0, report["checks"]
    assert results_by_step(report, "items") == {
        "list": "pass", "search": "pass", "create": "pass", "get": "pass",
        "update": "pass", "delete": "pass", "gone": "pass"}
    assert report["summary"] == f"{report['passed']} of {report['passed']} checks passed"
    assert not (folder / "app.db").exists()  # it ran on a copy


def test_an_application_that_does_not_load_has_not_started(tmp_path):
    folder = make_app(tmp_path, **{"backend/main.py": "from backend import nothing_here\n"})
    report = acceptance.run(folder, [])
    assert report["started"] is False
    assert "ImportError" in report["error"]
    assert report["summary"] == "the application does not start"


def test_a_rule_saying_no_is_not_a_failure_and_missing_records_fail(tmp_path):
    main = APP_HEAD + '''
class ItemIn(BaseModel):
    name: str


@app.get("/api/items")
def list_items(search: str | None = None) -> list[dict]:
    return database.list_items(search)


@app.post("/api/items", status_code=201)
def add_item(item: ItemIn) -> dict:
    raise HTTPException(status_code=400, detail="The shop is closed")
''' + APP_TAIL
    report = acceptance.run(make_app(tmp_path, **{"backend/main.py": main}), ["items", "loans"])
    steps = results_by_step(report, "items")
    assert steps["create"] == "rule"
    assert steps["get"] == steps["gone"] == "skipped"
    assert results_by_step(report, "loans") == {"routes": "fail"}
    assert report["rules"] == 1


def test_expected_records_come_from_the_decomposer_line():
    class T:
        description = "Build it.\nRecords: books, Loan Items. This task covers all of them."
    assert acceptance.expected_records([T()]) == ["books", "loan_items"]
    T.description = "no list"
    assert acceptance.expected_records([T()]) == []
