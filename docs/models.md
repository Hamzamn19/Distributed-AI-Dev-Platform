# Models and measured capabilities

Card S2-04 (Issue #24), contract section 10. The scores in `docs/agents.json`
come from this measurement, not from estimates. A model change means measuring
again.

## Method

`scripts/measure_model.py` asks every model the same five questions, with
temperature 0 so a second run gives the same answer.

| Dimension | Questions | Checked by | Score (0-100) |
| --- | --- | --- | --- |
| coding | 2: write `is_palindrome(s)` and `merge_intervals(intervals)` | 6 unit tests each, run in a separate Python process (10 s limit) | passed tests / 12 × 100 |
| reasoning | 2: "bat and ball" price question, five-runner order question | the expected answer (`5`, `Dana`) | correct / 2 × 100 |
| context | 1: find an access code hidden at sentence 64 of a 101-sentence delivery log (about 2 000 tokens) | the expected code `4817` | 100 when found, otherwise 0 |

The questions, the test cases and the long text are fixed in the script, so
every model gets exactly the same input. The long text is kept below Ollama's
default context window; a longer text would be cut off silently.

Limits: five questions give a rough score, not a benchmark. The context score
is either 0 or 100. Two PCs with the same model get the same scores
(contract section 10); this is expected.

## How to measure a model

From the repository root, with the virtual environment active, Ollama running
and `LLM_MOCK=0` in `.env`:

```bash
ollama pull <model>
python scripts/measure_model.py --model <model>
```

The last lines show the result, for example:

```text
RESULT  qwen2.5-coder:7b  coding=100  reasoning=50  context=100   (2.3 min)
```

`--write <agent_id>` also stores the model and the scores in `docs/agents.json`.
Copy the three `AGENT_CAP_*` lines the script prints into the worker's `.env`.

## Results

| Agent | Model | coding | reasoning | context | Measured on | Date |
| --- | --- | --- | --- | --- | --- | --- |
| agent-eray | qwen2.5-coder:7b | 100 | 50 | 100 | Eray-PC | 2026-10-21 |
| agent-fatma | to be decided | | | | | |
| agent-can | to be decided | | | | | |
| agent-abdurrahman | to be decided | | | | | |
| agent-okan | to be decided | | | | | |
| agent-hamza | to be decided | | | | | |
