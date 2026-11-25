#!/usr/bin/env python3
"""Give web search real depth.

Stock `search_web` returns only `title / link / snippet`, and a snippet is about
100 characters — so every answer built on it reads as a shallow summary. This
script rewrites that function so it also pulls the page text for the top
results and ships it under a `content` key.

It is idempotent: running it against an already-patched file changes nothing.

    python3 02-search-depth.py /path/to/site-packages/open_webui
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HELPER = '''
SEARCH_CONTENT_TOP_RESULTS = 3
SEARCH_CONTENT_MAX_CHARS = 5000


async def _attach_page_content(request, payload: list[dict]) -> list[dict]:
    """Add the page's extracted text to the first few search results (best effort).

    Fetching happens concurrently because each load spins up a headless browser;
    anything that times out or returns nothing simply keeps its snippet.
    """

    async def load(entry: dict) -> dict:
        if not entry.get('link'):
            return entry
        try:
            content, _ = await asyncio.wait_for(
                get_content_from_url(request, entry['link']), timeout=30
            )
        except Exception:
            return entry
        if not content or not content.strip():
            return entry

        text = ' '.join(content.split())
        if len(text) > SEARCH_CONTENT_MAX_CHARS:
            text = text[:SEARCH_CONTENT_MAX_CHARS] + ' [...truncated]'
        return {**entry, 'content': text}

    head, tail = payload[:SEARCH_CONTENT_TOP_RESULTS], payload[SEARCH_CONTENT_TOP_RESULTS:]
    enriched = await asyncio.gather(*(load(entry) for entry in head))
    return list(enriched) + tail

'''

OLD_RETURN = '''        # Limit results
        results = results[:count] if results else []

        return JSONCodec.dumps(
            [{'title': r.title, 'link': r.link, 'snippet': r.snippet} for r in results],
            ensure_ascii=False,
        )
'''

NEW_RETURN = '''        # Limit results
        results = results[:count] if results else []
        payload = [{'title': r.title, 'link': r.link, 'snippet': r.snippet} for r in results]

        # Snippets run about 100 characters, so answers built only from them read as
        # shallow summaries. Pull the actual page text for the top results so the model
        # reasons over full content; any page that fails to load keeps its snippet.
        if payload and not await Config.get('web.search.bypass_web_loader'):
            payload = await _attach_page_content(__request__, payload)

        return JSONCodec.dumps(payload, ensure_ascii=False)
'''

OLD_DOC = '''    :return: JSON with search results containing title, link, and snippet for each result
    """
'''

NEW_DOC = '''    :return: JSON list of results with title, link, snippet, and (when the page loaded)
        the page's text under "content" — prefer "content" over "snippet" when present.
        Call fetch_url on a result's link if you need content beyond what was returned.
    """
'''


def main(site_packages: str) -> int:
    target = Path(site_packages) / "open_webui" / "tools" / "builtin.py"
    if not target.is_file():
        print(f"  FAIL: not found: {target}")
        return 1

    src = target.read_text(encoding="utf-8")
    original = src
    actions: list[str] = []

    if "_attach_page_content" not in src:
        anchor = "async def search_web(\n"
        if anchor not in src:
            print("  FAIL: could not find the search_web anchor — Open WebUI changed this file")
            return 1
        src = src.replace(anchor, HELPER + anchor, 1)
        actions.append("inserted _attach_page_content helper")

    if OLD_RETURN in src:
        src = src.replace(OLD_RETURN, NEW_RETURN, 1)
        actions.append("search_web now returns page content for top results")
    elif "payload = [{'title': r.title" in src:
        actions.append("return block already patched")
    else:
        print("  FAIL: return block not recognised — Open WebUI changed this file")
        return 1

    if OLD_DOC in src:
        src = src.replace(OLD_DOC, NEW_DOC, 1)
        actions.append("updated the tool docstring the model reads")
    elif 'the page\'s text under "content"' in src:
        actions.append("docstring already patched")

    if src == original:
        print("  already up to date — nothing to do")
        return 0

    # refuse to write something that no longer parses
    ast.parse(src)
    target.write_text(src, encoding="utf-8")
    for a in actions:
        print(f"  - {a}")
    print(f"  wrote {target}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
