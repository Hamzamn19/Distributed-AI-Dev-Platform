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
| context | 1: find an access code hidden at sentence 64 of a 101-sentence delivery log (about 2 400 tokens; the exact count depends on the model's tokenizer) | the expected code `4817` | 100 when found, otherwise 0 |

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

The script calls the OpenAI-compatible server named by `LLM_BASE_URL`, so
llama.cpp's `llama-server` works as well: point `LLM_BASE_URL` at its `/v1`
endpoint and pass any label with `--model` (see the gemma4-26b-a4b run below).

The last lines show the result, for example (the script prints the same two
lines for every run; every question line above them also shows its tokens as
`tokens <prompt>/<completion>`):

```text
RESULT  qwen2.5-coder:7b  coding=100  reasoning=50  context=100   (2.3 min)
TOKENS  prompt=2765 completion=5354 total=8119  ~89.6 tok/s
```

Fair-use rules for the numbers:

- `tok/s` is completion tokens divided by the summed time of the five calls;
  it is the one speed figure that compares across models.
- Token counts come from each model's own tokenizer, so the same text is a
  different number of tokens for every model. Compare token counts only
  between runs of the **same model** (for example the same model on two
  servers); never between different models.
- Every model is measured with the same five questions and the same server
  configuration that will run it in the demo.

`--write <agent_id>` also stores the model and the three capability scores
in `docs/agents.json` (the tokens are never written there). Copy the three
`AGENT_CAP_*` lines the script prints into the worker's `.env`.

## Serving a model and connecting to it

Every LLM call in this platform — the master's `decompose`/`assign`, the
worker's task execution and the measurement script — goes through
`dap/shared/llm_client.py` to an OpenAI-compatible server named by
`LLM_BASE_URL`. Any such server works: Ollama (contract section 4) or
llama.cpp's `llama-server`, as on Hamza-PC.

### Start the server

Example from Hamza-PC (llama.cpp, the gemma4-26b-a4b model):

```bash
local-stack/llama.cpp/bin/llama-server \
  -m local-stack/models/gemma4-26b-a4b/gemma-4-26B-A4B-it-UD-IQ2_XXS.gguf \
  -ngl 999 -c 131072 -ctk q4_0 -ctv q4_0 -fa on -b 1024 -ub 256 \
  --threads 12 --threads-batch 12 --jinja --spec-type ngram-mod -np 1 \
  --host 127.0.0.1 --port 8080
```

Check that it is ready (both must answer):

```bash
curl http://127.0.0.1:8080/health          # {"status":"ok"}
curl http://127.0.0.1:8080/v1/models       # lists the loaded model
```

With Ollama the same role is played by `ollama serve` on port `11434`.

The example binds `127.0.0.1`, so **only that PC can call the model**. Other
PCs never call it directly: the master never calls a worker (contract
section 2), each PC runs its own server and its own worker, and every
worker PC runs a different local model (contract section 10).

### How the platform talks to it

One OpenAI-compatible POST, from anywhere in the codebase:

```bash
curl http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "gemma4-26b-a4b", "messages": [{"role": "user", "content": "Say OK."}]}'
```

The addresses and names come only from `.env` (`.env.example` lists them all):

| Variable | Value for this server |
| --- | --- |
| `LLM_BASE_URL` | `http://127.0.0.1:8080/v1` (Ollama: `http://localhost:11434/v1`) |
| `LLM_API_KEY` | `none` (llama-server ignores it; Ollama uses `ollama`) |
| `LLM_MODEL` | `gemma4-26b-a4b` — any label the server accepts |
| `LLM_MOCK` | `0` — `1` returns a fixed fake answer and calls nothing |

### This PC as the master

Set the four variables above in `.env`, then start the master
(`uvicorn dap.master.main:app --port 8000`). `POST /projects/{id}/decompose`
and `/assign` now reason with this PC's own model.

### This PC as a worker (task delegation)

The master never calls this model over the network; it delegates a task to
this PC, and the worker answers with the local model. The worker's `.env`:

```bash
MASTER_URL=http://<master Tailscale IP>:8000   # contract section 2
AGENT_TOKEN=<the shared team token>            # same value on all seven PCs
AGENT_ID=agent-hamza
AGENT_NAME=Hamza-PC
AGENT_OWNER=Hamza
AGENT_ROLE_HINT=backend                        # one of: frontend, backend, database, testing, integration, code_review
AGENT_CAP_CODING=100                           # from the measurement run
AGENT_CAP_REASONING=100
AGENT_CAP_CONTEXT=100
LLM_BASE_URL=http://127.0.0.1:8080/v1          # the local model, as above
LLM_API_KEY=none
LLM_MODEL=gemma4-26b-a4b
```

The delegation flow it joins (master side already merged): register with
`POST /api/v1/agents/register`, pull work with
`GET /api/v1/agents/{agent_id}/tasks/next` (200 with a task, 204 when none
are ready), execute it with the local model, and post the file back with
`POST /api/v1/tasks/{id}/result`. The worker loop that runs this flow is
Eray's Sprint 2 card; this section is the configuration it will read.

## Results

| Agent | Model | coding | reasoning | context | Speed (tok/s) | Measured on | Date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agent-eray | qwen2.5-coder:7b | 100 | 50 | 100 | 6.0 | Eray-PC | 2026-10-24 |
| agent-hamza | gemma4-26b-a4b | 100 | 100 | 100 | 89.6 | Hamza-PC | 2026-10-24 |
| agent-fatma | to be decided | | | | | | |
| agent-can | to be decided | | | | | | |
| agent-abdurrahman | to be decided | | | | | | |
| agent-okan | to be decided | | | | | | |

Rows marked `—` were measured before the script printed tokens (21 October);
re-run them once to fill the speed column.

### Extra run: gemma4-26b-a4b (Hamza-PC, 24 October)

Measured outside the six-row set: the model is `gemma-4-26B-A4B-it` (MoE, 4B
active parameters) as GGUF `UD-IQ2_XXS`, served by llama.cpp `llama-server`
(OpenAI-compatible API on `127.0.0.1:8080`, not Ollama) with context 131072,
KV cache `q4_0`, flash attention, ngram speculative decoding and 12 threads.

Per-question result (same five questions as every other run):

| Question | Outcome | Duration | Tokens prompt/completion |
| --- | --- | --- | --- |
| coding `is_palindrome` | 6/6 unit tests | 7.7 s | 87 / 572 |
| coding `merge_intervals` | 6/6 unit tests | 40.8 s | 125 / 3 934 |
| reasoning `bat_and_ball` | correct (`5`) | 4.4 s | 61 / 336 |
| reasoning `race_order` | correct (`Dana`) | 5.1 s | 61 / 395 |
| context needle | found (`4817`) | 1.7 s | 2 431 / 117 |
| **totals** | 12/12 tests, 2/2 answers, needle found | **3.0 min** | **2 765 / 5 354 (~89.6 tok/s)** |

The needle question alone costs 2 431 prompt tokens — the haystack is about
2 400 tokens under this tokenizer; the figure depends on the model, and the
script comment now says so.

Server settings matter for the coding score: the same model and questions on a
plain Ollama server (context 2048, no flash attention, no speculative
decoding) scored `coding=50` because `merge_intervals` failed 0/6. Measure a
model with the server configuration that will also run it in the demo.
