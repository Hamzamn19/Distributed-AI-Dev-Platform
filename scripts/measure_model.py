"""Measure a local model's capabilities (card S2-04, contract section 10).

Every model answers the same five questions:

    coding     2 small functions, each checked by 6 unit tests
    reasoning  2 questions with one checked answer each
    context    1 fact hidden in a long text (needle in a haystack)

Each dimension gets a score from 0 to 100:

    coding     = passed unit tests / 12 * 100
    reasoning  = correct answers / 2 * 100
    context    = 100 when the fact is found, otherwise 0

Usage (repository root, virtual environment active, Ollama running):

    python scripts/measure_model.py --model qwen2.5-coder:7b
    python scripts/measure_model.py --model qwen2.5-coder:7b --write agent-eray

Without --model the script uses LLM_MODEL from .env. --write stores the model
and the three scores for that agent in docs/agents.json. The address of the
model server comes from LLM_BASE_URL in .env, as for every other LLM call.
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

AGENTS_JSON = REPO_ROOT / "docs" / "agents.json"
TEMPERATURE = 0.0  # same answer on every run, so results can be reproduced
CODE_TIMEOUT_SEC = 10

CODE_RULES = (
    "Reply with only the code in one ```python block. "
    "No explanation, no examples, no tests, no input() calls."
)

# --- The five questions -----------------------------------------------------

CODING_TASKS = [
    {
        "name": "is_palindrome",
        "prompt": (
            "Write a Python function `is_palindrome(s: str) -> bool` that returns True "
            "when s reads the same forwards and backwards, ignoring upper/lower case and "
            "ignoring every character that is not a letter or a digit. " + CODE_RULES
        ),
        "cases": [
            [["A man, a plan, a canal: Panama"], True],
            [["race a car"], False],
            [[""], True],
            [["No 'x' in Nixon"], True],
            [["ab"], False],
            [["12321"], True],
        ],
    },
    {
        "name": "merge_intervals",
        "prompt": (
            "Write a Python function `merge_intervals(intervals: list[list[int]]) -> "
            "list[list[int]]`. Each item is a [start, end] pair with start <= end. Merge "
            "all overlapping intervals (intervals that only touch, like [1, 4] and [4, 5], "
            "also merge) and return the result sorted by start. The input may be unsorted "
            "or empty. " + CODE_RULES
        ),
        "cases": [
            [[[[1, 3], [2, 6], [8, 10], [15, 18]]], [[1, 6], [8, 10], [15, 18]]],
            [[[[1, 4], [4, 5]]], [[1, 5]]],
            [[[]], []],
            [[[[5, 7], [1, 2]]], [[1, 2], [5, 7]]],
            [[[[1, 10], [2, 3], [4, 5]]], [[1, 10]]],
            [[[[3, 3]]], [[3, 3]]],
        ],
    },
]

REASONING_TASKS = [
    {
        "name": "bat_and_ball",
        "prompt": (
            "A bat and a ball cost 1.10 dollars in total. The bat costs 1.00 dollar more "
            "than the ball. How many cents does the ball cost? "
            "Answer with only the number of cents."
        ),
        "kind": "number",
        "answer": 5,
    },
    {
        "name": "race_order",
        "prompt": (
            "Five runners finished a race: Ali, Ben, Cem, Dana and Eli. Dana finished "
            "before Eli. Ben finished after Eli. Ali finished before Dana. Cem finished "
            "last. Who finished second? Answer with only the name."
        ),
        "kind": "name",
        "answer": "Dana",
        "candidates": ["Ali", "Ben", "Cem", "Dana", "Eli"],
    },
]

NEEDLE = "The access code for the north gate is 4817."
NEEDLE_ANSWER = "4817"
CONTEXT_QUESTION = (
    "What is the access code for the north gate? Answer with only the number."
)
HAYSTACK_SENTENCES = 100  # about 2 500 tokens: fits Ollama's default context window
NEEDLE_POSITION = 63


def build_haystack() -> str:
    """A long, boring text with one useful sentence in it. Always the same text."""
    rng = random.Random(42)
    cities = ["Izmir", "Bursa", "Konya", "Adana", "Samsun", "Trabzon", "Kayseri", "Mersin"]
    items = ["paper", "glass", "cotton", "steel bolts", "olive oil", "tiles", "rope", "salt"]
    sentences = []
    for n in range(1, HAYSTACK_SENTENCES + 1):
        sentences.append(
            f"Shipment {n} left the {rng.choice(cities)} depot at "
            f"{rng.randint(6, 21):02d}:{rng.choice(['00', '15', '30', '45'])} carrying "
            f"{rng.randint(2, 90)} crates of {rng.choice(items)}."
        )
    sentences.insert(NEEDLE_POSITION, NEEDLE)
    return " ".join(sentences)


def context_prompt() -> str:
    return (
        "Read the following delivery log.\n\n"
        f"{build_haystack()}\n\n"
        f"Question: {CONTEXT_QUESTION}"
    )


# --- Checking answers --------------------------------------------------------

def extract_code(text: str) -> str:
    """Take the code out of a ```python block; use the whole answer when there is none."""
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return blocks[0] if blocks else text


_HARNESS = """
import json, sys
cases = json.loads(sys.argv[3])
ns = {}
try:
    exec(compile(open(sys.argv[1], encoding="utf-8").read(), "solution", "exec"), ns)
    fn = ns[sys.argv[2]]
except Exception:
    print(json.dumps({"passed": 0}))
    sys.exit(0)
passed = 0
for args, expected in cases:
    try:
        if json.loads(json.dumps(fn(*args))) == expected:
            passed += 1
    except Exception:
        pass
print(json.dumps({"passed": passed}))
"""


def run_unit_tests(code: str, function_name: str, cases: list) -> int:
    """Run the model's code in a separate Python process; return how many cases pass."""
    with tempfile.TemporaryDirectory() as tmp:
        solution = Path(tmp) / "solution.py"
        harness = Path(tmp) / "harness.py"
        solution.write_text(code, encoding="utf-8")
        harness.write_text(_HARNESS, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-I", str(harness), str(solution), function_name, json.dumps(cases)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=CODE_TIMEOUT_SEC,
            )
            return int(json.loads(result.stdout.strip().splitlines()[-1])["passed"])
        except (subprocess.TimeoutExpired, ValueError, IndexError, KeyError):
            return 0


def check_reasoning(task: dict, answer: str) -> bool:
    if task["kind"] == "number":
        numbers = re.findall(r"\d+", answer)
        return bool(numbers) and int(numbers[-1]) == task["answer"]
    named = re.findall(r"\b(" + "|".join(task["candidates"]) + r")\b", answer)
    return bool(named) and named[-1] == task["answer"]


def check_context(answer: str) -> bool:
    return NEEDLE_ANSWER in answer


# --- Measuring ----------------------------------------------------------------

def _ask(chat, prompt: str):
    return chat([{"role": "user", "content": prompt}], temperature=TEMPERATURE)


def token_line(tokens: dict) -> str:
    """One TOKENS line: totals plus the speed the whole run averaged.

    tok/s counts completion tokens over the summed call time. Token counts
    belong to the model's own tokenizer, so compare them only between runs
    of the same model (for example the same model on two servers).
    """
    total = tokens["prompt"] + tokens["completion"]
    seconds = tokens["duration_ms"] / 1000
    rate = tokens["completion"] / seconds if seconds else 0.0
    return f"TOKENS  prompt={tokens['prompt']} completion={tokens['completion']} " \
           f"total={total}  ~{rate:.1f} tok/s"


def measure(chat, log=print) -> dict:
    """Ask the five questions through chat() and return scores plus tokens."""
    passed = total = 0
    tokens = {"prompt": 0, "completion": 0, "duration_ms": 0}

    def _tally(reply):
        tokens["prompt"] += reply.prompt_tokens
        tokens["completion"] += reply.completion_tokens
        tokens["duration_ms"] += reply.duration_ms

    for task in CODING_TASKS:
        reply = _ask(chat, task["prompt"])
        _tally(reply)
        ok = run_unit_tests(extract_code(reply.text), task["name"], task["cases"])
        passed += ok
        total += len(task["cases"])
        log(f"  coding    {task['name']:<16} {ok}/{len(task['cases'])} tests   "
            f"{reply.duration_ms} ms   tokens {reply.prompt_tokens}/{reply.completion_tokens}")

    correct = 0
    for task in REASONING_TASKS:
        reply = _ask(chat, task["prompt"])
        _tally(reply)
        ok = check_reasoning(task, reply.text)
        correct += ok
        log(f"  reasoning {task['name']:<16} {'correct' if ok else 'wrong':<9}  "
            f"{reply.duration_ms} ms   tokens {reply.prompt_tokens}/{reply.completion_tokens}"
            f"   answer: {reply.text.strip()[:60]!r}")

    reply = _ask(chat, context_prompt())
    _tally(reply)
    found = check_context(reply.text)
    log(f"  context   {'needle':<16} {'found' if found else 'missed':<9}  "
        f"{reply.duration_ms} ms   tokens {reply.prompt_tokens}/{reply.completion_tokens}"
        f"   answer: {reply.text.strip()[:60]!r}")

    return {
        "coding": round(passed / total * 100),
        "reasoning": round(correct / len(REASONING_TASKS) * 100),
        "context": 100 if found else 0,
        "tokens": tokens,
    }


def format_agents(entries: list) -> str:
    """Same layout as docs/agents.json: one key per line, capabilities on one line."""
    blocks = []
    for entry in entries:
        lines = [f"    {json.dumps(key)}: {json.dumps(value)}" for key, value in entry.items()]
        blocks.append("  {\n" + ",\n".join(lines) + "\n  }")
    return "[\n" + ",\n".join(blocks) + "\n]\n"


def write_scores(agent_id: str, model: str, scores: dict, path: Path = AGENTS_JSON) -> None:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for entry in entries:
        if entry["agent_id"] == agent_id:
            entry["model"] = model
            entry["capabilities"] = scores
            break
    else:
        raise SystemExit(f"agent_id {agent_id!r} is not in {path}")
    path.write_text(format_agents(entries), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure a local model (S2-04).")
    parser.add_argument("--model", help="Ollama model name; default: LLM_MODEL from .env")
    parser.add_argument("--write", metavar="AGENT_ID", help="store the result in docs/agents.json")
    args = parser.parse_args()

    from dap.shared import llm_client  # loads .env

    if os.getenv("LLM_MOCK", "0").strip() == "1":
        raise SystemExit("LLM_MOCK=1 in .env: set LLM_MOCK=0, a mock cannot be measured.")
    if args.model:
        os.environ["LLM_MODEL"] = args.model
    model = os.getenv("LLM_MODEL", "")
    if not model:
        raise SystemExit("No model: pass --model or set LLM_MODEL in .env.")

    print(f"Measuring {model} (5 questions, this can take a few minutes)...")
    start = time.perf_counter()
    try:
        scores = measure(llm_client.chat)
    except RuntimeError as exc:
        raise SystemExit(f"Model did not answer: {exc}")
    minutes = (time.perf_counter() - start) / 60

    print(f"\nRESULT  {model}  coding={scores['coding']}  reasoning={scores['reasoning']}  "
          f"context={scores['context']}   ({minutes:.1f} min)")
    print(token_line(scores["tokens"]))
    print("\nFor the worker's .env:")
    print(f"AGENT_CAP_CODING={scores['coding']}")
    print(f"AGENT_CAP_REASONING={scores['reasoning']}")
    print(f"AGENT_CAP_CONTEXT={scores['context']}")

    if args.write:
        # agents.json holds the three capability scores only, never the tokens.
        capabilities = {key: scores[key] for key in ("coding", "reasoning", "context")}
        write_scores(args.write, model, capabilities)
        print(f"\nSaved to docs/agents.json for {args.write}.")


if __name__ == "__main__":
    main()
