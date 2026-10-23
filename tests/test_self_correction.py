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
