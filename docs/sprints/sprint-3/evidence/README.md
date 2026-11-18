# Evidence: real-model end-to-end run on one PC (18/19 November 2026, ~01:05)

Reproducible with the commands in `tools/`. Requirement:
`docs/sample_requirements/kisa.md` (task tracker). Master and two workers on this
PC, all served by one local model (gemma4-26b via Ollama, thinking disabled).

## Result

| Step | Result |
| --- | --- |
| Master + 2 workers over A2A | registered, agent cards fetched |
| Decompose (4 tasks + records) | 8 s with gemma4-26b |
| Run (database → backend → frontend → testing) | **131 s**, real model |
| Generated files | full template set in `workspace/<id>/` |
| Project git history | 4 task commits + the master's acceptance commit (see `generated-project-gitlog.txt`) |
| Master acceptance check | **9 of 9 checks passed** (see `acceptance.json`): app starts, `/api/stats`, per-record list, search, create, get, update, delete |

Log of the whole run: `e2e-real-run.log` (ends with `E2E PASSED`).

## How to reproduce

```bash
ollama serve                                            # or the running Ollama service
python /tmp/ollama_v1_shim.py 8787                      # /v1 shim: think:false
.venv/bin/python /tmp/e2e_real.py                       # the run itself
```

`tools/` holds both scripts. The shim exists because Ollama 0.35.1 answers a
thinking model on `/v1` with an empty content (reasoning goes to a separate
field the team's `llm_client` does not read); the shim forwards to the native
`/api/chat` with `think: false`, which returns complete answers (7 s decompose).

## Found and fixed during the run

- `dap/master/core/acceptance.py`: the probe built a `status` body value
  ("Check status 3266") that violated the generated app's `^(active|completed)$`
  pattern, so a correct app failed its own check (422). `value()` now honours a
  `pattern` of the `^(a|b)$` shape and uses the first alternative. After the fix
  the same run scores 9/9 (before: 8/9).
