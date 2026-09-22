"""Optional internet citation lookup via DuckDuckGo.

Privacy contract: only the user's query string leaves the machine. Retrieved
course chunks and generated answers are never sent. No API key exists.
Disabled entirely when WEB_SEARCH_ENABLED=false (used for the local-only
Wireshark capture).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import WEB_SEARCH_ENABLED


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
        raw = DDGS().text(query, max_results=n)
    except Exception as exc:  # network down, rate limit, library breakage
        print(f"[web_search] lookup failed: {exc}")
        return []
    return [
        WebResult(title=r.get("title", ""), url=r.get("href", ""), snippet=r.get("body", "")[:300])
        for r in raw
        if r.get("href")
    ]
