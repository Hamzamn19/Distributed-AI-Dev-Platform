# Local stack modifications

Everything that was changed to make the shared Gemma chat work the way we wanted.
This file is the record; `local-stack/patches/apply.sh` is how you put the changes
back after an Open WebUI upgrade wipes them.

- Date: 2026-10-07
- Scope: Open WebUI 0.6.x as installed by `uv`, llama-server (Gemma 4 26B), Tailscale
- Owner: local machine (hamzah)

## Goal

One URL, no login page, a single local model, web search switched on by default, and
the model able to read and edit **one** project folder and nothing else.

Stock Open WebUI gets about halfway there. Two things were missing:

1. **Page loading** — protected sites returned 403/empty, so search looked shallow.
2. **Result depth** — the built-in `search_web` tool returns ~100-character snippets,
   which is why answers read like summaries of summaries.

## Summary of every change

| # | What | Where | Committed |
|---|---|---|---|
| 1 | Real browser fingerprint, redirect handling, HTML fallback | `open_webui/retrieval/web/utils.py` (site-packages) | `local-stack/patches/01-web-loader.patch` |
| 2 | Attach page text to search results | `open_webui/tools/builtin.py` (site-packages) | `local-stack/patches/02-search-depth.py` |
| 2b | Log background-chat task failures | `open_webui/tasks.py` (site-packages) | `local-stack/patches/03-task-failure-log.py` |
| 2c | Log chat-write failures | `open_webui/models/chats.py` (site-packages) | `local-stack/patches/04-upsert-error-log.py` |
| 2d | Multi-query parallel deep search with full-page reads | DB `tool` table (`deep_search`) | `local-stack/tools/deep_search.py` + `setup.sh` (step 3) |
| 2e | Fall back to the model's own toolIds when the client sends none | `open_webui/main.py` (site-packages) | `local-stack/patches/05-model-tool-fallback.py` |
| 2f | 20 tool-call iterations (was 10) so multi-round research fits | `open-webui.service` env | `local-stack/systemd/open-webui.service` |
| 3 | Follow redirects + realistic UA | `~/.config/systemd/user/open-webui.service` | `local-stack/systemd/open-webui.service` |
| 4 | Playwright loader, result count, content cap | DB `config` table | `local-stack/setup.sh` (step 2) |
| 5 | Web search on by default, tool attached, temp 0.2 | DB `model` table | `local-stack/setup.sh` (step 4) |
| 6 | One project folder, no shell | DB `tool` table (`project_files`) | `local-stack/setup.sh` (step 3) |
| 7 | No login page | `WEBUI_AUTH=false` in the unit | `local-stack/systemd/open-webui.service` |
| 8 | Expose over Tailscale only | `tailscale serve` config | Tailscale (not in repo) |

---

## 1. Page loader — `retrieval/web/utils.py`

### What was wrong

Three separate faults stacked up:

| Fault | Effect |
|---|---|
| Playwright's default UA contains `HeadlessChrome` and `navigator.webdriver` is set | CDN bot filters refused the request before it loaded |
| `page.goto()` used the default `wait_until='load'` | Pages with never-settling resources hung until timeout → empty result |
| `AIOHTTP_CLIENT_ALLOW_REDIRECTS` defaults to false | Every 302 aborted the fetch, so wiki/news redirects returned nothing |
| `unstructured.partition.html` returned zero elements on some pages | GitHub's shell page reported 0 characters despite complete HTML |

Measured before the patch: **3 of 10** test sites returned usable text.

### What changed

- Added `PLAYWRIGHT_USER_AGENT` (Chrome/153, no `HeadlessChrome`) and
  `PLAYWRIGHT_INIT_SCRIPT`, which clears `navigator.webdriver`, sets `languages`,
  and defines `window.chrome`.
- Added `_new_playwright_context()` and used it in **both** the sync and async
  paths: `browser.new_page(...)` → `context.new_page()`, with viewport 1920×1080,
  `locale`, `timezone`, `service_workers='block'`, and an `Accept-Language` header.
  The UA can be overridden with `WEB_LOADER_USER_AGENT`.
- `page.goto(...)` now passes `wait_until='domcontentloaded'`, so the fetch returns
  as soon as the document is parseable instead of waiting for every asset.
- `_extract_html()` falls back to BeautifulSoup when `unstructured` yields nothing:
  strips `script`/`style`/`noscript`, then keeps non-empty lines.

### Result

| Site | Before | After |
|---|---|---|
| Wikipedia | 403 | **56,462 chars** |
| GitHub | 0 | **20,737 chars** |
| BBC News | fail | **11,829 chars** |
| The Guardian | fail | **3,630 chars** |
| Hacker News / docs sites | partial | **OK** |

**7 of 10** sites now load, up from 3.

### Still blocked (known limitation)

StackOverflow (403), Reuters (401), and Reddit run heavier bot protection that
defeats headless Chromium even with the fingerprint fixed. Defeating those
properly needs anti-detect tooling (or a cloud fetching API), which we decided
against for a term project.

---

## 2. Search depth — `tools/builtin.py`

### What was wrong

`search_web` returned `title` / `link` / `snippet` only. A snippet is roughly 100
characters, so the model answered from the list alone and every response had the
same thin, summary-of-a-summary feel.

Note: we deliberately did **not** switch to `legacy` function calling, which would
force a full-page RAG search every turn — that also disables every built-in tool.
Keeping native function calling and enriching this one tool preserves both.

### What changed

- New `SEARCH_CONTENT_TOP_RESULTS = 3` and `SEARCH_CONTENT_MAX_CHARS = 5000`.
- New `_attach_page_content()` loads the top 3 result pages **concurrently**
  (`asyncio.gather`, 30 s per page, best effort — a failed load keeps its snippet)
  and puts up to 5,000 characters of extracted text on each entry under `content`.
- The return statement now serialises that enriched payload instead of the bare
  snippet list.
- The docstring — which is what the model actually reads — now says to prefer
  `content` over `snippet`, and to call `fetch_url` for anything beyond it.

### Result

3 of 8 results came back with full page text in 9.1 s, and the answer cited BBC
News and TechCrunch with substantive detail instead of headlines.

---

## 3. Service environment

`AIOHTTP_CLIENT_ALLOW_REDIRECTS=true` and `USER_AGENT=...Chrome/153.0.0.0...` are
set in `open-webui.service` so the plain (non-Playwright) fetcher behaves like the
patched loader. `DATA_DIR` points at the project folder. `WEBUI_AUTH=false`
removes the login page entirely.

`CHAT_RESPONSE_MAX_TOOL_CALL_ITERATIONS=10` bounds how many rounds of tool
calling a single turn may spend. The stock default is **256**. This was added
after one test — "list the project files, then search the web" — ran away: the
model kept calling `search_web`, each round appending another ~6k tokens of page
content, until the slot sat at a 62k-token prompt and had decoded 62k tokens
without stopping. It had to be stopped by restarting `llama-server`. Ten rounds
is generous for a real turn (search, read, answer) and turns that failure into a
clear "Tool-call limit reached (10 iterations)" instead of a hang.

Full annotated copy: `local-stack/env/open-webui.env`.

---

## 4. Database configuration

Written directly into the `config` table (JSON values):

| Key | Value | Why |
|---|---|---|
| `web.loader.engine` | `"playwright"` | Render JavaScript pages instead of fetching raw HTML |
| `web.loader.playwright_timeout` | `30000` | Slow news sites need more than the default |
| `web.search.result_count` | `8` | More sources to cross-check |
| `web.fetch.max_content_length` | `20000` | Stops one huge page flooding the context window |

`local-stack/setup.sh` step 2 writes these idempotently.

> The settings page in the UI does not expose these — they were written through
> the database because Open WebUI's config API for them is inconsistent.

---

## 5. Model settings

On the Gemma row in the `model` table:

- `capabilities.web_search = true` — search available
- `defaultFeatureIds = ["web_search"]` — **on by default**, so the blue Web Search
  chip is already lit for every visitor
- `toolIds = ["project_files"]` — the scoped folder tool is attached
- `params = {"temperature": 0.2, "top_p": 0.95, "min_p": 0.05, "repeat_penalty": 1.05}`

> `POST /api/v1/models/model/update` requires the **full** `params` payload. Sending
> only the fields you want to change silently wipes the rest — temperature resets to
> the default.

The model's database id is the **file path**, so moving the `.gguf` file orphans
every setting. `setup.sh` step 4 repairs this (it rewrites `model.id`,
`access_grant.resource_id`, `chat_message.model_id`, and the `chat` JSON blob).
This happened once during the folder migration: 32 rows were rewritten.

---

## 6. Scoped file access — the `project_files` tool

The model may read and edit exactly one folder, and there is no shell.

Chosen over Jupyter because a Jupyter kernel is arbitrary Python execution — which
is a shell by another name, and the requirement was explicitly "one folder, no
shell". Instead this is a custom tool whose `_resolve()` normalises every path and
rejects anything landing outside `PROJECT_ROOT`.

- Root: `local-stack/project-files/`
- 4 tool specs: `list_project_files`, `read_project_file`, `write_project_file`, `edit_project_file`
- Absolute paths are resolved **inside** the root rather than trusted

Escape tests, all correctly refused:

| Attempt | Result |
|---|---|
| `../.bashrc` | blocked — outside the project folder |
| `../../.ssh/id_rsa` | blocked — outside the project folder |
| `/etc/shadow` | blocked — resolved inside root, does not exist |
| `list ../..` | blocked — outside the project folder |
| `write /etc/cron.d/pwn` | blocked — no file created |
| `edit /home/hamzah/.bashrc` | blocked — outside the project folder |

**6 / 6 blocked.**

---

## 7. Access

- Friend joins this tailnet (no public Funnel), then opens
  `https://hamzah.tail983031.ts.net/` — Tailscale serve, valid Let's Encrypt cert.
- `WEBUI_AUTH=false` means no login page; all visitors share the built-in admin
  identity. **Anyone on the tailnet is an admin** — that is the trade-off for
  removing the login.
- llama-server binds `127.0.0.1:8080` only; it is never reachable directly.
- Open WebUI binds `127.0.0.1:3000` only; Tailscale is the sole way in.

---

## 8. Re-applying after an upgrade

`uv tool install --with playwright --with unstructured open-webui` downloads a
fresh copy of the package and **silently discards changes 1 and 2**. Afterwards:

```bash
cd local-stack
./patches/apply.sh     # re-apply all five source patches (idempotent, verifies syntax)
./setup.sh             # restore units, DB config, tools, model settings; restart
```

Both scripts are safe to run repeatedly and detect already-applied state.

Install command, for reference:

```bash
uv tool install --python 3.12 --with playwright --with unstructured open-webui
python3 -m playwright install chromium    # if the browser download is skipped
```

Patched versions: playwright 1.63.0, unstructured 0.27.16, ddgs 9.14.4.

> The install lives at `local-stack/open-webui/app` (inside this repo) and is
> reachable from `~/.local/share/uv/tools/open-webui` by symlink, so the launcher
> still works. Because uv does not follow that symlink when listing tools,
> `uv tool list` will not show it and a `uv tool upgrade` will not touch it —
> which is what keeps these patches from being wiped. Re-run `apply.sh` after any
> manual reinstall.

---

## 9. Where everything lives now

The whole stack moved into this repository so it is one place instead of five:

| Was | Now |
|---|---|
| `~/models/gemma4-26b-a4b` (9.3 GB) | `local-stack/models/gemma4-26b-a4b` |
| `~/models/gemma4-31b` (8.0 GB) | `local-stack/models/gemma4-31b` |
| `~/apps/llama.cpp` (1.4 GB) | `local-stack/llama.cpp` |
| `~/.local/share/uv/tools/open-webui` (7.6 GB) | `local-stack/open-webui/app` |
| site-packages `open_webui/data` (webui.db) | `local-stack/open-webui/data` |
| `~/ai-project` | `local-stack/project-files` |
| `~/.config/systemd/user/*.service` | `local-stack/systemd/` (committed copies) |

Symlinks were left at the old paths, so anything still referencing them keeps
working. `.gitignore` excludes every multi-gigabyte item — `git check-ignore`
confirms the binaries are ignored while the configs stay tracked.

---

## 10. Things we decided not to do

| Considered | Why not |
|---|---|
| Cloud search/fetch API (Tavily, Firecrawl) | Needs a key and costs money; local DuckDuckGo + Playwright is free |
| Jupyter tool for file access | Arbitrary Python execution = the shell we were told not to provide |
| `legacy` function calling (forces full RAG search) | Disables every built-in tool, including the file tool |
| Anti-detect browser to beat StackOverflow/Reuters | Out of scope for a term project; 7/10 was good enough |
| Public Tailscale Funnel | Requirement was that the friend joins the tailnet |
| Committing the model binaries | 17 GB of `.gguf` in a shared repo would be a mistake |
| `web.search.bypass_embedding_and_retrieval = true` | The Playwright loader has **no content-length cap** (`max_content_length` is only honoured by the `fetch_url` tool), so bypassing the vector store would inject whole pages (56k chars for Wikipedia) into the context. The chunked RAG path bounds this; real depth comes from the `deep_search` tool, which caps every page itself |

---

## 11. Deep search (2026-10-07)

Google-AI-Mode-style depth from free local parts only — no API key, no new service.

### 11.1 Free tuning (config table, kept by `setup.sh`)

| Key | Was | Now | Why |
|---|---|---|---|
| `web.search.concurrent_requests` | 0 | 6 | The query generator emits several queries per question; run them together |
| `web.search.result_count` | 8 | 12 | Wider net for fetch + embed; cheap because only top chunks reach context |

`bypass_embedding_and_retrieval` deliberately stays `false` (see §10).

### 11.2 The `deep_search` tool

Source of truth: `local-stack/tools/deep_search.py`, mirrored into the `tool`
table (id `deep_search`, one spec, only `query` required). Attached to the model
next to `project_files`; `setup.sh` attaches every tool row that exists.

What one call does:

1. Takes `query` + up to 5 `sub_queries` (the model decomposes the question itself) and searches them **in parallel** through the configured engine (`routers/retrieval.py:2511` `search_web`, so a future engine switch needs no tool change).
2. Deduplicates by normalised URL, boosts URLs several queries agreed on, caps at 3 pages per domain for breadth.
3. Reads up to `max_pages` (default 6, hard ceiling 8) **in full** via the patched Playwright loader (`retrieval/utils.py:245` `get_content_from_url`), 35 s per-page budget, all concurrent.
4. Returns an attributed digest (`title/url/domain/snippet/content`) plus `unread` reasons and `next_steps`, so the model can run follow-up rounds with `exclude_urls`.

Hard ceilings (`MAX_PAGES = 8`, `MAX_PAGE_CHARS = 8000`) exist because the digest
lands in context in one shot. Two bugs were fixed before first use: `get_content_from_url`
returns a `(text, documents)` tuple, and a malformed `__user__` dict must not take
the whole search down. Direct test: 4 queries → 42 results → 4 pages read in 26 s.

Verified end-to-end through the UI: the model chose `deep_search`, executed it
(~57 s), and answered with per-claim source URLs (Google–Constellation 890 MW,
October 2026).

### 11.3 Two silence bugs found while verifying (§11.2)

Live UI answers vanished without any error — the backend had actually produced
and saved them. Two stock code paths swallow failures:

1. `tasks.py` `create_task` (`open_webui/tasks.py:157`) registered only a cleanup
   callback, so a raised exception was never retrieved. Fix: a `_report_failure`
   done-callback logs it (`patches/03-task-failure-log.py`).
2. `models/chats.py:1141` `upsert_message_to_chat_by_id_and_message_id` ended with
   a bare `except Exception: return None`, which the streaming pipeline reads as
   "nothing to save". Fix: `log.exception` with chat/message ids before returning
   None (`patches/04-upsert-error-log.py`).

Both fixes are additive logging only — no behaviour change — and are re-applied
by `patches/apply.sh` [3/4] and [4/4].

### 11.5 Tool fallback and research protocol (same day, later)

Two follow-ups turned one fast round into real multi-round research:

- **Fallback (`patches/05-model-tool-fallback.py`, `main.py`)**: the web UI keeps
  tool selection as per-chat composer state, so a fresh chat can arrive with no
  `tool_ids` key — the model then truthfully says it has no web tools. Now the
  server substitutes the model's own `toolIds` when the key is absent (an
  explicit `[]` still disables tools). Verified from a captured request body:
  the failing turn had no `tool_ids` and `"web_search":false`; after the fix the
  same conditions inject both tools server-side.
- **Protocol in the tool spec**: `deep_search`'s docstring now carries a DEEP
  RESEARCH PROTOCOL (minimum 4 rounds, gap-driven follow-ups via `exclude_urls`,
  stop only when every claim has a source URL), and each result's `next_steps`
  repeats the round bookkeeping. One call is one round by design — sustained
  research is the model looping, ~40-60 s per round, 5+ minutes total.
- **Iterations 10 → 20** (`CHAT_RESPONSE_MAX_TOOL_CALL_ITERATIONS` in both unit
  files): 10 left no headroom for 4-6 search rounds plus file work; 20 still
  stops a runaway loop.
- **Round planning + mandatory verification round** in the spec: one round per
  entity for multi-entity questions, then a final disputes/updates/criticism
  round; `next_steps` text adapts (planning guidance on round 1, gap +
  verification guidance afterwards).

Verified end-to-end twice through the UI on a 4-company nuclear-deals
comparison: first run 2 rounds / 5m16s / 9 sources; after the protocol
tightening, 6 rounds (one per company + value follow-ups) over **8.5 minutes**,
3707-char answer with 9 source URLs. Sustained deep research, not one fast round.

- The "stuck on Loading..." was **not** lost work: all five test answers were in
  `chat.history.messages` and the `chat_message` table. After a page reload every
  answer, source list and follow-up rendered; the managed test browser just
  receives socket.io deltas slowly through its proxy. A normal browser on the
  tailnet gets them live (emits verified server-side to the correct
  `user:{id}` room).
- `GET /api/v1/chats/{id}` returns the legacy top-level `messages` list, which
  lags behind `history.messages` — that is why API polling looked empty while
  the data was present. The frontend renders from `history`, so it is unaffected
  after reload/sync.
