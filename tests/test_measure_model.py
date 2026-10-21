"""Tests for scripts/measure_model.py (S2-04). No real model is called."""

import importlib.util
from pathlib import Path

from dap.shared.schemas import LLMResponse

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("measure_model", REPO_ROOT / "scripts" / "measure_model.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

GOOD_PALINDROME = """```python
def is_palindrome(s: str) -> bool:
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
```"""

GOOD_MERGE = """```python
def merge_intervals(intervals):
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out
```"""


def _reply(text: str) -> LLMResponse:
    return LLMResponse(text=text, prompt_tokens=0, completion_tokens=0, duration_ms=1)


def test_extract_code_takes_the_python_block():
    assert mm.extract_code("Here:\n```python\nx = 1\n```\nDone").strip() == "x = 1"
    assert mm.extract_code("x = 1") == "x = 1"


def test_correct_code_passes_every_case():
    task = mm.CODING_TASKS[0]
    assert mm.run_unit_tests(mm.extract_code(GOOD_PALINDROME), task["name"], task["cases"]) == 6


def test_wrong_or_broken_code_scores_low():
    task = mm.CODING_TASKS[0]
    always_true = "def is_palindrome(s):\n    return True\n"
    assert mm.run_unit_tests(always_true, task["name"], task["cases"]) == 4
    assert mm.run_unit_tests("def is_palindrome(:", task["name"], task["cases"]) == 0
    assert mm.run_unit_tests("x = 1", task["name"], task["cases"]) == 0


def test_endless_code_is_stopped(monkeypatch):
    monkeypatch.setattr(mm, "CODE_TIMEOUT_SEC", 1)
    task = mm.CODING_TASKS[0]
    assert mm.run_unit_tests("while True:\n    pass\n", task["name"], task["cases"]) == 0


def test_reasoning_checks():
    bat, race = mm.REASONING_TASKS
    assert mm.check_reasoning(bat, "5")
    assert mm.check_reasoning(bat, "The ball costs 5 cents.")
    assert not mm.check_reasoning(bat, "10")
    assert mm.check_reasoning(race, "Dana")
    assert not mm.check_reasoning(race, "Ali")


def test_haystack_hides_one_needle():
    text = mm.build_haystack()
    assert text == mm.build_haystack()  # same text on every run
    assert text.count(mm.NEEDLE_ANSWER) == 1
    assert mm.check_context("4817") and not mm.check_context("I don't know")


def test_measure_gives_full_scores_for_perfect_answers():
    def fake_chat(messages, *, temperature):
        prompt = messages[0]["content"]
        if "is_palindrome" in prompt:
            return _reply(GOOD_PALINDROME)
        if "merge_intervals" in prompt:
            return _reply(GOOD_MERGE)
        if "bat" in prompt:
            return _reply("5")
        if "runners" in prompt:
            return _reply("Dana")
        return _reply("4817")

    assert mm.measure(fake_chat, log=lambda _: None) == {"coding": 100, "reasoning": 100, "context": 100}


def test_measure_gives_zero_for_useless_answers():
    scores = mm.measure(lambda messages, *, temperature: _reply("no idea"), log=lambda _: None)
    assert scores == {"coding": 0, "reasoning": 0, "context": 0}


def test_format_keeps_agents_json_layout():
    import json

    original = mm.AGENTS_JSON.read_text(encoding="utf-8")
    assert mm.format_agents(json.loads(original)) == original


def test_write_scores_updates_one_agent(tmp_path):
    import json

    target = tmp_path / "agents.json"
    target.write_text(mm.AGENTS_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    mm.write_scores("agent-eray", "qwen2.5-coder:7b", {"coding": 75, "reasoning": 50, "context": 100}, target)
    entries = {e["agent_id"]: e for e in json.loads(target.read_text(encoding="utf-8"))}
    assert entries["agent-eray"]["model"] == "qwen2.5-coder:7b"
    assert entries["agent-eray"]["capabilities"] == {"coding": 75, "reasoning": 50, "context": 100}
    assert entries["agent-can"]["capabilities"] == {"coding": 50, "reasoning": 50, "context": 50}
