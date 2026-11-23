"""Decomposer tests. conftest.py sets LLM_MOCK=1, so no model is called."""

import json
import uuid

import pytest

from dap.master.core import decomposer
from dap.shared.enums import TaskType
from dap.shared.schemas import LLMResponse, TaskCreate

ORDER = [TaskType.DATABASE, TaskType.BACKEND, TaskType.FRONTEND, TaskType.TESTING]
RECORDS = ["customers", "orders"]
REQUIREMENT = "A library app where members borrow and return books."


def _answer(text: str) -> LLMResponse:
    return LLMResponse(text=text, prompt_tokens=0, completion_tokens=0, duration_ms=0)


def _assert_valid(tasks: list[TaskCreate]) -> None:
    assert all(isinstance(t, TaskCreate) for t in tasks)
    assert [t.type for t in tasks] == ORDER
    ids = {t.id for t in tasks}
    assert len(ids) == len(tasks)
    for t in tasks:
        uuid.UUID(t.id, version=4)
    database, backend, frontend, testing = tasks
    assert database.depends_on == []
    assert backend.depends_on == [database.id]
    assert frontend.depends_on == [backend.id]
    assert testing.depends_on == [backend.id, frontend.id]


def test_mock_answer_becomes_four_tasks_in_fixed_order():
    _assert_valid(decomposer.decompose(REQUIREMENT))


def test_shuffled_duplicate_tasks_are_reduced_to_one_per_type_in_order(monkeypatch):
    t = {x["type"]: x for x in decomposer.FALLBACK_TASKS}
    shuffled = [t["testing"], t["frontend"], t["backend"], dict(t["backend"], title="Second API"),
                t["database"]]
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(json.dumps({"records": RECORDS, "tasks": shuffled})))
    tasks = decomposer.decompose(REQUIREMENT)
    _assert_valid(tasks)
    assert [x.title for x in tasks] == [t[k.value]["title"] for k in ORDER]


def test_records_line_is_added_to_every_task(monkeypatch):
    data = {"records": ["customers", "Orders", "bad name!", "customers"],
            "tasks": decomposer.FALLBACK_TASKS}
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(json.dumps(data)))
    tasks = decomposer.decompose(REQUIREMENT)
    _assert_valid(tasks)
    assert all(t.description.endswith("Records: customers, orders. This task covers all of them.") for t in tasks)


def test_mock_client_answer_carries_records_in_the_contract_format():
    tasks = decomposer.decompose(REQUIREMENT)  # LLM_MOCK=1
    assert all(t.description.endswith("Records: customers, orders. This task covers all of them.")
               for t in tasks)


@pytest.mark.parametrize("records", [
    None, [], "customers", ["bad name!", "1x"], [f"t{i}" for i in range(13)],
])
def test_missing_or_bad_records_make_the_answer_broken(monkeypatch, records):
    data = {"tasks": decomposer.FALLBACK_TASKS}
    if records is not None:
        data["records"] = records
    calls = []
    monkeypatch.setattr(decomposer, "chat",
                        lambda *a, **k: calls.append(1) or _answer(json.dumps(data)))
    tasks = decomposer.decompose(REQUIREMENT)
    assert len(calls) == decomposer.ATTEMPTS          # asked again once
    _assert_valid(tasks)                                # then the fixed template
    assert all("Records:" not in t.description for t in tasks)


def test_twelve_records_are_accepted(monkeypatch):
    names = [f"t{i}" for i in range(12)]
    data = {"records": names, "tasks": decomposer.FALLBACK_TASKS}
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(json.dumps(data)))
    tasks = decomposer.decompose(REQUIREMENT)
    assert all(t.description.endswith(f"Records: {', '.join(names)}. This task covers all of them.")
               for t in tasks)


def test_code_fences_around_json_are_accepted(monkeypatch):
    text = "```json\n" + json.dumps({"records": RECORDS, "tasks": decomposer.FALLBACK_TASKS}) + "\n```"
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(text))
    _assert_valid(decomposer.decompose(REQUIREMENT))


def test_broken_answer_is_retried_once(monkeypatch):
    answers = iter(["not json", json.dumps({"records": RECORDS, "tasks": decomposer.FALLBACK_TASKS})])
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return _answer(next(answers))

    monkeypatch.setattr(decomposer, "chat", fake_chat)
    _assert_valid(decomposer.decompose(REQUIREMENT))
    assert len(calls) == 2


@pytest.mark.parametrize("bad", [
    "not json",
    json.dumps({"records": RECORDS, "subtasks": decomposer.FALLBACK_TASKS}),               # old field name
    json.dumps({"records": RECORDS, "tasks": [dict(t, type="analysis") if i == 0 else t     # non-Sprint 1 type
                          for i, t in enumerate(decomposer.FALLBACK_TASKS)]}),
    json.dumps({"records": RECORDS, "tasks": decomposer.FALLBACK_TASKS[:3]}),             # "testing" missing
])
def test_unusable_answers_fall_back_to_template(monkeypatch, bad):
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(bad))
    tasks = decomposer.decompose(REQUIREMENT)
    _assert_valid(tasks)
    assert [t.title for t in tasks] == [t["title"] for t in decomposer.FALLBACK_TASKS]


def test_unreachable_model_raises_runtime_error(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("LLM did not answer")

    monkeypatch.setattr(decomposer, "chat", down)
    with pytest.raises(RuntimeError):
        decomposer.decompose(REQUIREMENT)
