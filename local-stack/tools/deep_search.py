"""
deep_search — research-grade web search.

The built-in search_web returns one query and a few snippets. This does what a
person actually does: split the question into several angles, search them all at
once, open the promising pages and read them, then hand back an attributed digest
so the answer can cite evidence instead of paraphrasing headlines.
"""

import asyncio
from typing import Optional
from urllib.parse import urlsplit

from fastapi import Request

# Hard ceilings. This result lands in the model's context window in one shot, so
# an unbounded digest turns one question into a hang.
MAX_QUERIES = 6
MAX_PAGES = 8
MAX_PAGE_CHARS = 8000
# Per-page fetch budget. Pages are fetched together, so wall clock is roughly this
# figure rather than the sum.
FETCH_TIMEOUT = 35


def clean_url(url: str) -> str:
    """Drop the fragment and tracking parameters so duplicate URLs collapse."""
    from urllib.parse import parse_qsl, urlencode, urlunsplit

    parts = urlsplit(str(url).strip())
    keep = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid'))
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/') or '/', urlencode(keep), '')
    )


def domain_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host[4:] if host.startswith('www.') else host


class Tools:
    def __init__(self):
        pass

    async def deep_search(
        self,
        query: str,
        sub_queries: Optional[list[str]] = None,
        max_pages: int = 6,
        page_chars: int = 6000,
        exclude_urls: Optional[list[str]] = None,
        __request__: Request = None,
        __user__: dict = None,
    ) -> dict:
        """
        Research the open web properly: several queries in parallel, then the best
        pages read in full rather than quoted from their snippets.

        DEEP RESEARCH PROTOCOL — one call is one round, and one round is just a
        normal web search, not research. For any non-trivial question, and always
        when the user asks for deep/in-depth research, run MULTIPLE rounds
        (minimum 4, up to 6-8) until every factual claim has a source URL:
        1. Round 1: query plus 4-5 sub_queries from genuinely different angles
           (entities named, a year, "vs", causes, criticism, numbers), max_pages=8.
        2. Read the digest and write down which sub-questions are answered and
           which still lack evidence. This gap list drives the next round.
        3. Round 2+: sub_queries aimed ONLY at the gaps, and every URL already
           read goes in exclude_urls. Never repeat a query, never re-read a URL.
        4. Stop when each claim in your planned answer cites a source URL from
           the digests, or after 6-8 rounds. Then answer with a Sources section
           citing each URL. Expect the whole research to take several minutes —
           that is normal and desired.
        5. If the question covers several entities (companies, people, events),
           plan ONE round per entity — never compress everything into one round.
        6. Mandatory final round: verification. Query each key claim with
           "disputed", "cancelled/updated 2026", "criticism/problems" angles to
           catch stale or wrong facts before writing the answer. A research with
           no verification round is incomplete.
        Prefer this over search_web whenever the answer has to rest on evidence.

        :param query: The main question, phrased the way someone would actually search.
        :param sub_queries: 2-5 other angles on the same question — different wording,
            the key entities named, a year, "vs", "causes", "criticism". This is what
            makes the search deep; a single query gives you one source's opinion.
        :param max_pages: How many result pages to open and read in full (1-8, default 6).
        :param page_chars: Characters to keep per page (500-8000, default 6000).
        :param exclude_urls: URLs already read in an earlier round, so this round
            looks for what is still missing instead of repeating itself.
        :return: dict with queries_run, sources (title/url/domain/content), unread,
            and next_steps. Cite sources by URL in the answer.
        """
        if __request__ is None:
            return {'error': 'Request context not available'}

        # Imported lazily: keeps registration cheap and avoids import cycles.
        from open_webui.models.config import Config
        from open_webui.models.users import UserModel
        from open_webui.retrieval.utils import get_content_from_url
        from open_webui.routers.retrieval import search_web as engine_search

        try:
            max_pages = max(1, min(int(max_pages), MAX_PAGES))
            page_chars = max(500, min(int(page_chars), MAX_PAGE_CHARS))
        except (TypeError, ValueError):
            max_pages, page_chars = 6, 6000

        # ----------------------------------------------------------- queries
        queries: list[str] = []
        for item in [query, *(sub_queries or [])]:
            text = str(item or '').strip()
            if text and text not in queries:
                queries.append(text)
        queries = queries[:MAX_QUERIES]
        if not queries:
            return {'error': 'No query supplied'}

        engine = await Config.get('web.search.engine')
        # Some engines want the caller, DDG does not — never let a malformed
        # identity take the whole search down.
        try:
            user = UserModel(**__user__) if __user__ else None
        except Exception:
            user = None

        # ------------------------------------------------------------ searching
        # Every query goes out at once: six angles cost about as long as one.
        async def run(q):
            try:
                return q, await engine_search(__request__, engine, q, user), None
            except Exception as exc:
                return q, [], str(exc)[:160]

        outcomes = await asyncio.gather(*(run(q) for q in queries))

        skipped = {clean_url(u) for u in (exclude_urls or [])}
        candidates: list[dict] = []
        seen: set[str] = set()
        hits: dict[str, int] = {}
        query_errors: list[dict] = []

        for q, results, error in outcomes:
            if error:
                query_errors.append({'query': q, 'error': error})
            for rank, res in enumerate(results or []):
                url = getattr(res, 'link', None)
                if not url:
                    continue
                key = clean_url(url)
                if key in seen or key in skipped:
                    continue
                seen.add(key)
                hits[key] = hits.get(key, 0) + 1
                candidates.append(
                    {
                        'title': getattr(res, 'title', '') or '',
                        'url': url,
                        'snippet': ' '.join((getattr(res, 'snippet', '') or '').split())[:400],
                        '_rank': rank,
                        '_key': key,
                    }
                )
                if len(candidates) >= 60:
                    break

        if not candidates:
            return {
                'queries_run': queries,
                'error': 'No results returned for any query',
                'query_errors': query_errors,
                'next_steps': 'Rephrase the query — it may be too narrow or too broad.',
            }

        # A URL several queries agreed on beats a lucky first hit.
        for c in candidates:
            c['_score'] = -c.pop('_rank') + hits.get(c['_key'], 1) * 5
        candidates.sort(key=lambda c: c['_score'], reverse=True)

        # Breadth is the point: never read six pages from one site.
        picked: list[dict] = []
        per_domain: dict[str, int] = {}
        for c in candidates:
            dom = domain_of(c['url'])
            if per_domain.get(dom, 0) >= 3:
                continue
            per_domain[dom] = per_domain.get(dom, 0) + 1
            picked.append(c)
            if len(picked) >= max_pages:
                break

        # ------------------------------------------------------------- reading
        async def load(entry):
            try:
                out = await asyncio.wait_for(
                    get_content_from_url(__request__, entry['url']), timeout=FETCH_TIMEOUT
                )
            except asyncio.TimeoutError:
                return {**entry, 'content': None, 'reason': f'timed out after {FETCH_TIMEOUT}s'}
            except Exception as exc:
                return {**entry, 'content': None, 'reason': str(exc)[:160]}

            # get_content_from_url returns (text, documents)
            raw = out[0] if isinstance(out, tuple) else out
            text = ' '.join((raw or '').split())
            if not text:
                return {**entry, 'content': None, 'reason': 'page returned no readable text'}

            return {
                **entry,
                'content': text[:page_chars] + (' [...truncated]' if len(text) > page_chars else ''),
                'content_chars': len(text),
            }

        loaded = await asyncio.gather(*(load(entry) for entry in picked))

        sources = [
            {
                'title': r['title'],
                'url': r['url'],
                'domain': domain_of(r['url']),
                'snippet': r['snippet'],
                'content': r['content'],
            }
            for r in loaded
            if r.get('content')
        ]
        unread = [
            {'url': r['url'], 'reason': r.get('reason', 'unknown')}
            for r in loaded
            if not r.get('content')
        ]

        return {
            'queries_run': queries,
            'results_found': len(candidates),
            'pages_read': len(sources),
            'sources': sources,
            'unread': unread,
            'query_errors': query_errors,
            'next_steps': (
                f'Round done: {len(sources)} pages read from {len(queries)} queries. '
                + (
                    'Plan one round per entity/sub-topic (minimum 4 rounds total), '
                    'then a final VERIFICATION round (disputed/updated/criticism '
                    'angles). One round is not research.'
                    if not exclude_urls else
                    'List what is answered and what still lacks evidence, then run '
                    'the next round with gap-only sub_queries and all read URLs in '
                    'exclude_urls. Finish with a VERIFICATION round before answering.'
                )
            ),
        }
