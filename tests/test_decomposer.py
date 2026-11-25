"""Decomposer tests. conftest.py sets LLM_MOCK=1, so no model is called."""

import json
import uuid

import pytest

from dap.master.core import decomposer
from dap.shared.enums import SPRINT1_TASK_TYPES, TaskType
from dap.shared.schemas import LLMResponse, TaskCreate

REQUIREMENT = "A library app where members borrow and return books."


def _answer(text: str) -> LLMResponse:
    return LLMResponse(text=text, prompt_tokens=0, completion_tokens=0, duration_ms=0)


def _assert_valid(tasks: list[TaskCreate]) -> None:
    assert all(isinstance(t, TaskCreate) for t in tasks)
    assert {t.type for t in tasks} == set(SPRINT1_TASK_TYPES)
    ids = {t.id for t in tasks}
    assert len(ids) == len(tasks)
    for t in tasks:
        uuid.UUID(t.id, version=4)
        assert set(t.depends_on) <= ids
        assert t.id not in t.depends_on


def test_mock_answer_becomes_four_tasks_with_uuid_dependencies():
    tasks = decomposer.decompose(REQUIREMENT)
    _assert_valid(tasks)
    assert len(tasks) == 4
    by_title = {t.title: t for t in tasks}
    assert by_title["Build REST API"].depends_on == [by_title["Design database schema"].id]


def test_code_fences_around_json_are_accepted(monkeypatch):
    text = "```json\n" + json.dumps({"tasks": decomposer.FALLBACK_TASKS}) + "\n```"
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(text))
    _assert_valid(decomposer.decompose(REQUIREMENT))


def test_broken_answer_is_retried_once(monkeypatch):
    answers = iter(["not json", json.dumps({"tasks": decomposer.FALLBACK_TASKS})])
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return _answer(next(answers))

    monkeypatch.setattr(decomposer, "chat", fake_chat)
    _assert_valid(decomposer.decompose(REQUIREMENT))
    assert len(calls) == 2


@pytest.mark.parametrize("bad", [
    "not json",
    json.dumps({"subtasks": decomposer.FALLBACK_TASKS}),               # old field name
    json.dumps({"tasks": [dict(t, type="analysis") if i == 0 else t     # non-Sprint 1 type
                          for i, t in enumerate(decomposer.FALLBACK_TASKS)]}),
    json.dumps({"tasks": decomposer.FALLBACK_TASKS[:3]}),             # "testing" missing
])
def test_unusable_answers_fall_back_to_template(monkeypatch, bad):
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(bad))
    tasks = decomposer.decompose(REQUIREMENT)
    _assert_valid(tasks)
    assert [t.title for t in tasks] == [t["title"] for t in decomposer.FALLBACK_TASKS]


def test_unknown_dependency_keys_are_dropped(monkeypatch):
    data = {"tasks": [dict(t, depends_on=t["depends_on"] + ["T99", t["key"]])
                      for t in decomposer.FALLBACK_TASKS]}
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(json.dumps(data)))
    _assert_valid(decomposer.decompose(REQUIREMENT))


def test_unreachable_model_raises_runtime_error(monkeypatch):
    def down(*args, **kwargs):
        raise RuntimeError("LLM did not answer")

    monkeypatch.setattr(decomposer, "chat", down)
    with pytest.raises(RuntimeError):
        decomposer.decompose(REQUIREMENT)


def test_two_tasks_of_one_type_are_refused(monkeypatch):
    doubled = decomposer.FALLBACK_TASKS + [dict(decomposer.FALLBACK_TASKS[1], key="T5")]
    calls = []

    def fake_chat(messages, **kwargs):
        calls.append(messages)
        return _answer(json.dumps({"tasks": doubled}))

    monkeypatch.setattr(decomposer, "chat", fake_chat)
    tasks = decomposer.decompose(REQUIREMENT)
    assert len(calls) == 2  # retried once, then the fixed template
    assert "more than one task of type backend" in calls[1][-1]["content"]
    assert [t.title for t in tasks] == [t["title"] for t in decomposer.FALLBACK_TASKS]


def test_order_and_dependencies_are_fixed_whatever_the_model_answers(monkeypatch):
    reversed_tasks = [dict(t, depends_on=[]) for t in reversed(decomposer.FALLBACK_TASKS)]
    reversed_tasks[0]["title"] = "Library tests"  # the testing task, written first
    monkeypatch.setattr(decomposer, "chat",
                        lambda *a, **k: _answer(json.dumps({"tasks": reversed_tasks})))
    tasks = decomposer.decompose(REQUIREMENT)
    assert [t.type.value for t in tasks] == ["database", "backend", "frontend", "testing"]
    ids = {t.type.value: t.id for t in tasks}
    assert tasks[0].depends_on == []
    assert tasks[1].depends_on == [ids["database"]]
    assert tasks[2].depends_on == [ids["backend"]]
    assert tasks[3].depends_on == [ids["backend"], ids["frontend"]]
    assert tasks[3].title == "Library tests"


def test_every_description_names_all_records(monkeypatch):
    # Round 3e: a small model gave each task a different record; the list keeps them together.
    text = json.dumps({"records": ["team_members", "projects", "tasks"],
                       "tasks": decomposer.FALLBACK_TASKS})
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(text))
    tasks = decomposer.decompose(REQUIREMENT)
    for task in tasks:
        assert task.description.endswith(
            "\nRecords: team_members, projects, tasks. This task covers all of them.")


def test_descriptions_stay_as_they_are_without_records(monkeypatch):
    text = json.dumps({"tasks": decomposer.FALLBACK_TASKS})
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(text))
    tasks = decomposer.decompose(REQUIREMENT)
    assert "Records:" not in " ".join(t.description for t in tasks)


def test_the_visual_style_rides_on_the_frontend_task(monkeypatch):
    monkeypatch.setattr(decomposer, "chat", lambda *a, **k: _answer(
        json.dumps({"tasks": decomposer.FALLBACK_TASKS})))
    (frontend,) = [t for t in decomposer.decompose(REQUIREMENT, "midnight")
                   if t.type == TaskType.FRONTEND]
    assert 'data-theme="midnight"' in frontend.description
    (frontend_default,) = [t for t in decomposer.decompose(REQUIREMENT)
                           if t.type == TaskType.FRONTEND]
    assert "data-theme" not in frontend_default.description
