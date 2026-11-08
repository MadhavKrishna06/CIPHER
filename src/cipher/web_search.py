"""Optional internet citation lookup via DuckDuckGo.

Privacy contract: only the user's query string leaves the machine, and it goes to
exactly one host, html.duckduckgo.com. Retrieved course chunks and generated answers
are never sent. No API key exists.
Disabled entirely when WEB_SEARCH_ENABLED=false (used for the local-only
Wireshark capture).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import WEB_SEARCH_ENABLED

# The only external service this project is allowed to contact.
BACKEND = "duckduckgo"


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str


def search(query: str, n: int = 3) -> list[WebResult]:
    if not WEB_SEARCH_ENABLED:
        return []
    from ddgs import DDGS

    try:
        # Pin the engine. The library default is backend="auto", which picks from
        # eighteen engines at runtime: one query was observed contacting
        # grokipedia.com, en.wikipedia.org and html.duckduckgo.com, with the query
        # string in the URL for two of them. That makes the destination
        # non-deterministic, contradicts the documented privacy claim, and leaves the
        # Round 2 packet capture unreproducible. One engine, named in the threat
        # model, is the whole point.
        raw = DDGS().text(query, max_results=n, backend=BACKEND)
    except Exception as exc:  # network down, rate limit, library breakage
        print(f"[web_search] lookup failed: {exc}")
        return []
    return [
        WebResult(title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")[:300])
        for r in raw
        if r.get("href")
    ]
