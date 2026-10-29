"""The worker's self-correction loop: load checks and a second answer from the model.

The model is replaced by a fake chat(); no real model is called.
"""

import json

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
    text = json.dumps({"summary": "done", "files": [
        {"path": path, "content": content} for path, content in files.items()]})
    return LLMResponse(text=text, prompt_tokens=10, completion_tokens=20, duration_ms=30)


def test_verify_finds_the_missing_import_of_the_real_test():
    problem = executor.verify(payload(), output(backend__main_py=BROKEN_MAIN))
    assert "backend/main.py fails when it is loaded" in problem
    assert "NameError: name 'database' is not defined" in problem


def test_verify_accepts_files_that_load():
    assert executor.verify(payload(), output(backend__main_py=GOOD_MAIN)) is None


def test_verify_loads_tests_with_every_earlier_file():
    task = payload("testing", ["tests/test_app.py"],
                   ["backend/database.py", "backend/main.py", "frontend/index.html",
                    "frontend/app.js"])
    assert executor.verify(task, output(tests__test_app_py=MOCK_FILES["tests/test_app.py"])) is None


def test_verify_skips_files_that_are_not_python():
    task = payload("frontend", ["frontend/app.js"], ["backend/main.py"])
    assert executor.verify(task, output(frontend__app_js="this is not python")) is None


@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "0")
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
    assert "did not answer with JSON" in calls[1][-1]["content"]
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
    main = GOOD_MAIN.replace("return database.list_items()", "return 1 / 0")
    problem = executor.verify(payload(), output(backend__main_py=main))
    assert "GET /api/items fails: ZeroDivisionError" in problem


def frontend_task():
    return payload("frontend", ["frontend/index.html", "frontend/app.js"],
                   ["backend/database.py", "backend/main.py"])


def test_the_mock_frontend_passes_its_checks():
    files = output(frontend__index_html=MOCK_FILES["frontend/index.html"],
                   frontend__app_js=MOCK_FILES["frontend/app.js"])
    assert executor.verify(frontend_task(), files) is None


def test_frontend_routes_and_ids_must_exist():
    app_js = MOCK_FILES["frontend/app.js"].replace('fetch("/api/items")', 'fetch("/api/tasks")')
    app_js += 'document.getElementById("summary");\n'
    problem = executor.check_frontend(app_js, MOCK_FILES["frontend/index.html"], GOOD_MAIN)
    assert "frontend/app.js calls /api/tasks, which backend/main.py does not have" in problem
    assert "element ids that frontend/index.html does not have: summary" in problem


def test_frontend_paths_with_parameters_match_the_routes():
    main = '@app.get("/api/tasks/{task_id}")\n@app.post("/api/tasks/{id}/complete")\n'
    app_js = ("api(`/api/tasks/${row.id}`); api(`/api/tasks/${id}/complete`, {});"
              ' api("/api/tasks/" + id); api(`/api/tasks/${id}?full=1`);')
    assert executor.check_frontend(app_js, "", main) is None


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
