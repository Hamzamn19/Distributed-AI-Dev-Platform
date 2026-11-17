"""The worker's self-correction loop: load checks and a second answer from the model.

The model is replaced by a fake chat(); no real model is called.
"""

import pytest

from dap.shared.schemas import DapTaskOutput, DapTaskPayload, GeneratedFile, LLMResponse
from dap.worker import executor
from dap.worker.executor import MOCK_FILES

GOOD_MAIN = MOCK_FILES["backend/main.py"]
# The mistake qwen2.5:7b made in the real test: the module import is gone.
BROKEN_MAIN = GOOD_MAIN.replace("from backend import database\n", "")


def payload(kind="backend", targets=("backend/main.py",), deps=("backend/database.py",)):
    return DapTaskPayload(
        task_id="t", project_id="p", type=kind, title=f"{kind} task", description="d",
        requirement_text="A small app with items.", target_files=list(targets),
        dependency_files=[GeneratedFile(path=p, content=MOCK_FILES[p]) for p in deps])


def output(**files):
    return DapTaskOutput(summary="s", files=[
        GeneratedFile(path=path.replace("__", "/").replace("_py", ".py"), content=content)
        for path, content in files.items()])


def answer(files: dict[str, str]) -> LLMResponse:
    """A model answer in the format of prompts.ANSWER_FORMAT."""
    blocks = "".join(f"=== FILE: {path} ===\n{content}=== END FILE ===\n"
                     for path, content in files.items())
    return LLMResponse(text=f"SUMMARY: done\n{blocks}", prompt_tokens=10,
                       completion_tokens=20, duration_ms=30)


def test_verify_finds_the_missing_import_of_the_real_test():
    problem = executor.verify(payload(), output(backend__main_py=BROKEN_MAIN))
    assert "backend/main.py fails when it is loaded" in problem
    assert "NameError: name 'database' is not defined" in problem


def test_verify_accepts_files_that_load():
    assert executor.verify(payload(), output(backend__main_py=GOOD_MAIN)) is None


def test_verify_loads_tests_with_every_earlier_file():
    task = payload("testing", ["tests/test_app.py"],
                   ["backend/database.py", "backend/main.py", "frontend/index.html"])
    assert executor.verify(task, output(tests__test_app_py=MOCK_FILES["tests/test_app.py"])) is None


def test_verify_skips_files_that_are_not_python():
    task = payload("frontend", ["frontend/index.html"], ["backend/main.py"])
    assert executor.verify(task, output(frontend__index_html="<p>not python</p>")) is None


@pytest.fixture
def real_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MOCK", "0")
    monkeypatch.setattr(executor, "REJECTED_DIR", tmp_path / "rejected")
    calls = []

    def use(*answers):
        replies = iter(answers)

        def fake_chat(messages, json_mode):
            calls.append(messages)
            return next(replies)

        monkeypatch.setattr(executor, "chat", fake_chat)
        return calls

    return use


def test_a_wrong_answer_is_corrected_with_the_error_message(real_mode):
    calls = real_mode(answer({"backend/main.py": BROKEN_MAIN}),
                      answer({"backend/main.py": GOOD_MAIN}))
    result = executor.execute(payload())
    assert len(calls) == 2
    feedback = calls[1][-1]["content"]
    assert "NameError: name 'database' is not defined" in feedback
    assert calls[1][-2]["role"] == "assistant"
    assert result.files[0].content == GOOD_MAIN
    assert result.summary == "done (corrected 1x)"
    assert (result.prompt_tokens, result.completion_tokens, result.duration_ms) == (20, 40, 60)


def test_a_right_first_answer_needs_no_correction(real_mode):
    calls = real_mode(answer({"backend/main.py": GOOD_MAIN}))
    assert executor.execute(payload()).summary == "done"
    assert len(calls) == 1


def test_broken_json_and_empty_files_are_also_sent_back(real_mode):
    broken = LLMResponse(text="not json at all", prompt_tokens=1, completion_tokens=1,
                         duration_ms=1)
    calls = real_mode(broken, answer({"backend/main.py": ""}), answer({"backend/main.py": GOOD_MAIN}))
    assert executor.execute(payload()).summary == "done (corrected 2x)"
    assert "the answer has no '=== FILE: <path> ===' blocks" in calls[1][-1]["content"]
    assert "empty file: backend/main.py" in calls[2][-1]["content"]


def test_still_wrong_after_the_corrections_fails_the_task(real_mode):
    calls = real_mode(*[answer({"backend/main.py": BROKEN_MAIN})] * 3)
    with pytest.raises(ValueError, match="(?s)still wrong after 2 corrections: .*NameError"):
        executor.execute(payload())
    assert len(calls) == 1 + executor.FIX_ROUNDS


def test_only_the_last_answer_goes_back_to_the_model(real_mode):
    calls = real_mode(answer({"backend/main.py": BROKEN_MAIN}),
                      answer({"backend/main.py": BROKEN_MAIN}),
                      answer({"backend/main.py": GOOD_MAIN}))
    executor.execute(payload())
    assert len(calls[1]) == len(calls[2]) == len(calls[0]) + 2


# ---------------------------------------- the checks of what the next agents rely on

GOOD_DATABASE = MOCK_FILES["backend/database.py"]


def database_task():
    return payload("database", ["backend/database.py"], [])


def test_database_whose_init_db_fails_on_a_restart_is_sent_back():
    # The mistake of round 2: the sample data is inserted again at every start.
    database = GOOD_DATABASE.replace(
        "name TEXT NOT NULL)\"\n        )",
        "name TEXT NOT NULL UNIQUE)\"\n        )\n"
        "        connection.execute(\"INSERT INTO items (name) VALUES ('first')\")")
    problem = executor.verify(database_task(), output(backend__database_py=database))
    assert "init_db() fails when it runs a second time" in problem
    assert "UNIQUE constraint failed" in problem


def test_database_without_the_functions_of_a_table_is_sent_back():
    # The other mistake of round 2: only the tables, none of the functions.
    database = GOOD_DATABASE.split("\n\ndef list_items")[0] + "\n"
    problem = executor.verify(database_task(), output(backend__database_py=database))
    assert ("does not define these functions: list_items, get_item, add_item, update_item, "
            "delete_item") in problem


def test_the_mock_database_passes_every_check():
    assert executor.verify(database_task(), output(backend__database_py=GOOD_DATABASE)) is None


def test_backend_that_calls_a_missing_database_function_is_sent_back():
    main = GOOD_MAIN.replace("database.add_item(item.name)", "database.add_task(item.name)")
    problem = executor.verify(payload(), output(backend__main_py=main))
    assert "uses database.add_task, which backend/database.py does not define" in problem
    assert "list_items" in problem


def test_backend_whose_get_route_fails_is_sent_back():
    main = GOOD_MAIN.replace("return database.list_items(search)", "return 1 / 0")
    problem = executor.verify(payload(), output(backend__main_py=main))
    assert "GET /api/items fails: ZeroDivisionError" in problem


def frontend_task():
    return payload("frontend", ["frontend/index.html"],
                   ["backend/database.py", "backend/main.py"])


def test_the_mock_frontend_passes_its_checks():
    files = output(frontend__index_html=MOCK_FILES["frontend/index.html"])
    assert executor.verify(frontend_task(), files) is None


def test_frontend_routes_and_ids_must_exist():
    page = MOCK_FILES["frontend/index.html"].replace('fetch("/api/items")', 'fetch("/api/tasks")')
    page = page.replace("    load();\n  </script>", '    load();\n    document.getElementById("summary");\n  </script>')
    problem = executor.check_frontend(page, GOOD_MAIN)
    assert "frontend/index.html calls /api/tasks, which backend/main.py does not have" in problem
    assert "element ids that the page does not have: summary" in problem


def test_comments_and_placeholders_of_the_template_are_not_calls():
    # Simple to-do round: the kept template comment '"/api/<things>"' was taken for a call.
    page = ('<!-- fetch("/api/books") is an example -->\n<script>\n'
            '  // relative paths such as "/api/<things>"\n'
            '  /* api("/api/old") */\n  api("/api/items");\n</script>\n')
    assert executor.check_frontend(page, GOOD_MAIN) is None
    assert executor.check_frontend('<script>api("/api/<things>")</script>', GOOD_MAIN) is None


def test_frontend_paths_with_parameters_match_the_routes():
    main = '@app.get("/api/tasks/{task_id}")\n@app.post("/api/tasks/{id}/complete")\n'
    app_js = ("api(`/api/tasks/${row.id}`); api(`/api/tasks/${id}/complete`, {});"
              ' api("/api/tasks/" + id); api(`/api/tasks/${id}?full=1`);')
    assert executor.check_frontend(f"<script>{app_js}</script>", main) is None


FAILING_TEST = '''

def test_a_route_that_does_not_exist():
    assert client.get("/api/nothing").status_code == 200
'''


def make_testing_payload():
    return payload("testing", ["tests/test_app.py"],
                   ["backend/database.py", "backend/main.py"])


def test_the_generated_tests_run_and_failures_are_sent_back():
    tests = MOCK_FILES["tests/test_app.py"] + FAILING_TEST
    problem = executor.verify(make_testing_payload(), output(tests__test_app_py=tests))
    assert problem.startswith(f"{executor.TESTS_FAIL}: 1 of 2 pass.")
    assert "test_a_route_that_does_not_exist" in problem


def test_some_failing_tests_are_accepted_after_the_last_correction(real_mode):
    tests = MOCK_FILES["tests/test_app.py"] + FAILING_TEST
    calls = real_mode(*[answer({"tests/test_app.py": tests})] * 3)
    result = executor.execute(make_testing_payload())
    assert len(calls) == 3
    assert result.summary == "done (corrected 2x) (tests: 1 of 2 pass.)"


def test_tests_that_cannot_run_are_a_real_problem():
    tests = MOCK_FILES["tests/test_app.py"].replace("def test_add_and_list_items", "def check_x")
    problem = executor.verify(make_testing_payload(), output(tests__test_app_py=tests))
    assert problem == "tests/test_app.py has no test functions (def test_...)"


# ------------------------------------------------- the FILE block answer format


def test_file_blocks_are_read_with_their_summary():
    text = ("Here you go.\nSUMMARY: two files\n"
            "=== FILE: frontend/index.html ===\n<h1>Hi</h1>\n=== END FILE ===\n"
            "=== FILE: frontend/app.js ===\n```javascript\nconst a = \"x\";\n```\n=== END FILE ===\n")
    result = executor._read_answer(text, payload("frontend", ["frontend/index.html", "frontend/app.js"], []))
    assert result.summary == "two files"
    assert [(f.path, f.content) for f in result.files] == [
        ("frontend/index.html", "<h1>Hi</h1>\n"), ("frontend/app.js", 'const a = "x";')]


def test_code_with_quotes_and_backslashes_needs_no_escaping():
    # What broke the JSON answers of qwen2.5-coder: docstrings, quotes and \n in code.
    code = 'def f():\n    """Doc."""\n    return "a\\nb"\n'
    result = executor._read_answer(
        f"SUMMARY: s\n=== FILE: backend/database.py ===\n{code}=== END FILE ===\n", database_task())
    assert result.files[0].content == code


def test_an_unclosed_file_block_is_reported():
    with pytest.raises(ValueError, match="has no '=== END FILE ===' line"):
        executor._read_answer("SUMMARY: s\n=== FILE: backend/main.py ===\nimport os\n",
                              payload())


def test_the_older_json_answer_is_still_read():
    text = '{"summary": "old", "files": [{"path": "backend/main.py", "content": "x = 1\\n"}]}'
    result = executor._read_answer(text, payload())
    assert (result.summary, result.files[0].content) == ("old", "x = 1\n")


def test_the_model_is_asked_without_json_mode(real_mode, monkeypatch):
    modes = []
    monkeypatch.setattr(executor, "chat", lambda messages, json_mode: (
        modes.append(json_mode), answer({"backend/main.py": GOOD_MAIN}))[1])
    executor.execute(payload())
    assert modes == [False]


def test_the_problem_shows_the_line_of_the_generated_file():
    # Round 3d: qwen2.5-coder passed the connection to the ready execute() helper.
    database = GOOD_DATABASE.replace(
        '    with connect() as connection:\n        connection.execute(\n',
        '    with connect() as connection:\n        execute(connection,\n')
    problem = executor.verify(database_task(), output(backend__database_py=database))
    assert 'Your line: File "backend/database.py"' in problem
    assert "execute(connection," in problem
    assert "must be str, not sqlite3.Connection" in problem


def test_a_syntax_error_shows_the_wrong_line():
    # Round 3f: three answers kept the same broken signature; the line is now in the problem.
    database = GOOD_DATABASE + "\n\ndef add_task(title: str, note: str = None, project_id: int):\n    pass\n"
    with pytest.raises(ValueError) as error:
        executor.check_output(database_task(), output(backend__database_py=database))
    assert "parameter without a default follows parameter with a default" in str(error.value)
    assert "def add_task(title: str, note: str = None, project_id: int):" in str(error.value)


# The database.py of the simple to-do round: names right, but two functions break.
ROUND_DATABASE = '''from backend.db import connect, execute, fetch_all, fetch_one


def init_db() -> None:
    execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL)")


def list_tasks(search: str | None = None) -> list[dict]:
    if search:
        sql = "SELECT * FROM tasks WHERE title LIKE ?"
        params = (f"%{search}%",)
    else:
        sql = "SELECT * FROM tasks"
    return fetch_all(sql, params)


def get_task(task_id: int) -> dict | None:
    return fetch_one("SELECT * FROM tasks WHERE id = ?", (task_id,))


def add_task(title: str) -> dict:
    execute("INSERT INTO tasks (title) VALUES (?)", (title,))
    return get_task(fetch_one("SELECT last_insert_rowid()")[0])


def update_task(task_id: int, title: str) -> dict | None:
    execute("UPDATE tasks SET title = ? WHERE id = ?", (title, task_id))
    return get_task(task_id)


def delete_task(task_id: int) -> bool:
    return execute("DELETE FROM tasks WHERE id = ?", (task_id,)) > 0
'''


def test_the_database_functions_are_really_called():
    problem = executor.verify(database_task(), output(backend__database_py=ROUND_DATABASE))
    assert "list_tasks() fails: UnboundLocalError" in problem
    assert 'Your line: File "backend/database.py"' in problem
    fixed = ROUND_DATABASE.replace('        sql = "SELECT * FROM tasks"',
                                   '        sql, params = "SELECT * FROM tasks", ()')
    problem = executor.verify(database_task(), output(backend__database_py=fixed))
    assert "add_task('Check value') fails: KeyError" in problem


def test_an_error_in_another_agents_file_is_named_as_such():
    task = payload("backend", ["backend/main.py"], [])
    task.dependency_files = [GeneratedFile(path="backend/database.py", content=ROUND_DATABASE)]
    main = GOOD_MAIN.replace("database.list_items(", "database.list_tasks(")
    main = main.replace("_item(", "_task(")  # get_, add_, update_, delete_item -> _task
    problem = executor.verify(task, output(backend__main_py=main))
    assert "The error is inside backend/database.py, which another agent wrote" in problem


def test_backend_without_the_stats_route_is_sent_back():
    # Simple to-do round: the page called /api/stats, which the backend had left out.
    main = GOOD_MAIN.split('@app.get("/api/stats")')[0] + (
        'app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))\n')
    problem = executor.verify(payload(), output(backend__main_py=main))
    assert "backend/main.py has no GET /api/stats route" in problem


def test_a_correction_names_the_files_the_agent_may_change(real_mode):
    calls = real_mode(answer({"backend/main.py": BROKEN_MAIN}),
                      answer({"backend/main.py": GOOD_MAIN}))
    executor.execute(payload())
    assert "You may change only backend/main.py." in calls[1][-1]["content"]


def test_the_page_is_read_as_a_browser_reads_it():
    # Ids without quotes are real ids; markup the script builds counts too.
    page = ('<span id=stat-tasks>0</span>\n<script>\n'
            '  document.getElementById("stat-tasks").textContent = 3;\n'
            '  list.innerHTML = `<p id="row-${n}"></p><b id="total"></b>`;\n'
            '  document.getElementById("total");\n</script>\n')
    assert executor.check_frontend(page, GOOD_MAIN) is None


def test_an_element_inside_an_unclosed_comment_does_not_count():
    page = ('<!-- the dashboard\n<span id="stat-tasks">0</span>\n'
            '<script>document.getElementById("stat-tasks");</script>\n')
    assert "looks up element ids that the page does not have: stat-tasks" in (
        executor.check_frontend(page, GOOD_MAIN) or "")


def test_a_rejected_answer_is_kept_for_a_person_to_read(real_mode):
    real_mode(answer({"backend/main.py": BROKEN_MAIN}), answer({"backend/main.py": GOOD_MAIN}))
    executor.execute(payload())
    kept = executor.REJECTED_DIR / "t-answer1.txt"
    assert "=== FILE: backend/main.py ===" in kept.read_text(encoding="utf-8")
