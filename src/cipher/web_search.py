"""Optional internet citation lookup, via a short ordered list of named engines.

Privacy contract: only the user's query string leaves the machine, and it goes to one
of the engines named in BACKENDS, tried in order. Retrieved course chunks and
generated answers are never sent. No API key exists.
Disabled entirely when WEB_SEARCH_ENABLED=false (used for the local-only
Wireshark capture).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .config import WEB_SEARCH_ENABLED

# The external services this project is allowed to contact, in the order tried.
#
# The Round 2 finding was not that DuckDuckGo is trustworthy and the rest are not. It
# was that the library default, backend="auto", selects at runtime from eighteen
# engines: one query was observed contacting grokipedia.com, en.wikipedia.org and
# html.duckduckgo.com, with the query string in the URL for two of them. A
# non-deterministic destination cannot be documented in a threat model and makes a
# packet capture unreproducible.
#
# A short ordered list keeps that property: the set of possible destinations is small,
# named here, and known before the query runs. It also survives one engine failing,
# which is what happened on 2026-11-22 when the duckduckgo backend began returning
# "No results found." for every query while yahoo kept working. duckduckgo stays first
# so that behaviour reverts on its own if the backend recovers.
BACKENDS = ("duckduckgo", "yahoo")

# Both engines return "No results found." intermittently for queries that succeed on
# the next attempt, so a single pass over BACKENDS fails perhaps one time in three.
# That is a transient fault, not an answer, and the honest response to a transient
# fault is to try again rather than tell the user the internet has nothing.
ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1.5


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str
    engine: str = ""   # which entry of BACKENDS answered, for the retrieval trace


def search_with_status(query: str, n: int = 3) -> tuple[list[WebResult], str | None]:
    """Look the query up. Returns (results, error).

    error is None when the lookup was not attempted or succeeded, and a short message
    when every engine failed. An empty list on its own cannot distinguish "nothing to
    look up" from "the lookup broke", which is the difference between working as
    designed and being silently degraded.
    """
    if not WEB_SEARCH_ENABLED:
        return [], None

    from ddgs import DDGS

    failures: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        for backend in BACKENDS:
            try:
                raw = DDGS().text(query, max_results=n, backend=backend)
            except Exception as exc:  # network down, rate limit, engine blocked, library breakage
                failures.append(f"{backend} try {attempt}: {exc}")
                continue
            results = [
                WebResult(title=r.get("title", ""), url=r.get("href", ""),
                          snippet=r.get("body", "")[:300], engine=backend)
                for r in raw
                if r.get("href")
            ]
            if results:
                return results, None
            failures.append(f"{backend} try {attempt}: no results")
        if attempt < ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    message = "; ".join(failures)
    print(f"[web_search] lookup failed on every backend -- {message}")
    return [], message


def search(query: str, n: int = 3) -> list[WebResult]:
    """Results only. Callers that surface failures use search_with_status()."""
    return search_with_status(query, n)[0]
