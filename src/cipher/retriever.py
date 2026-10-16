"""Similarity search over the local Chroma knowledge base."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_chroma import Chroma

from .ingest import get_vectorstore
from .loaders import doc_kind
from .textfilter import is_prose


def cite(source: str, page: int, kind: str | None = None) -> str:
    """The one place a citation string is built, so every agent prints the same form.

    kind comes from chunk metadata when the knowledge base was built with it, and is
    derived from the file name otherwise. The extension is dropped because it appears
    in every citation and tells a reader nothing.
    """
    name = source[:-4] if source.lower().endswith((".pdf", ".txt", ".md")) else source
    name = name[:-5] if name.lower().endswith((".pptx", ".docx")) else name
    return f"{name.strip()}, {kind or doc_kind('', source)} {page}"


@dataclass
class Chunk:
    text: str
    source: str   # file name, e.g. "Lecture 2_slides.pdf"
    page: int     # 1-based page / slide
    score: float  # distance; lower = closer
    kind: str | None = None  # "slide" or "page"; absent in older collections

    @property
    def effective_kind(self) -> str:
        """Never guess "page" for a slide. A slide judged by textbook thresholds is
        thrown away for being short, and slides are the primary course material."""
        return self.kind or doc_kind("", self.source)

    @property
    def citation(self) -> str:
        return cite(self.source, self.page, self.kind)


@lru_cache(maxsize=1)
def _store() -> Chroma:
    return get_vectorstore()


def _diversify(chunks: list[Chunk], k: int, per_source: int = 3) -> list[Chunk]:
    """Keep the closest chunks while spreading them out.

    Without this, a question about Kerberos filled all five slots from consecutive
    pages of one textbook, so the model saw the same paragraph three times and never
    saw the lecture slide that defined the term. Adjacent pages of one document are
    near-duplicates after chunking, and a near-duplicate costs a slot without adding
    anything the model can use.
    """
    kept: list[Chunk] = []
    used: dict[str, int] = {}
    for c in chunks:
        if len(kept) >= k:
            break
        if used.get(c.source, 0) >= per_source:
            continue
        if any(o.source == c.source and abs(o.page - c.page) <= 1 for o in kept):
            continue
        kept.append(c)
        used[c.source] = used.get(c.source, 0) + 1

    # Backfill rather than return fewer than asked for: a sparse topic is better
    # served by near-duplicates than by an empty context. Relax the per-source cap
    # first and the adjacency rule only as a last resort, because a topic covered by
    # one book should still not spend three slots on one paragraph.
    def _fill(allow_adjacent: bool) -> None:
        for c in chunks:
            if len(kept) >= k:
                return
            if c in kept:
                continue
            if not allow_adjacent and any(
                o.source == c.source and abs(o.page - c.page) <= 1 for o in kept
            ):
                continue
            kept.append(c)

    _fill(allow_adjacent=False)
    _fill(allow_adjacent=True)
    return kept


def retrieve(question: str, k: int = 5, max_distance: float | None = None,
             diversify: bool = True) -> list[Chunk]:
    """Return the k best chunks for the question.

    Oversamples and then filters, because non-prose chunks and near-duplicates would
    otherwise take slots that the model needs for actual explanation.
    """
    fetch = k * 3 if diversify else k
    hits = _store().similarity_search_with_score(question, k=fetch)
    chunks = [
        Chunk(text=doc.page_content, source=doc.metadata["source"], page=int(doc.metadata["page"]),
              score=float(score), kind=doc.metadata.get("kind"))
        for doc, score in hits
    ]
    if max_distance is not None:
        chunks = [c for c in chunks if c.score <= max_distance]

    if not diversify:
        return chunks[:k]

    # Second line of defence. Ingest skips these pages now, but a knowledge base
    # built before that change still holds them.
    prose = [c for c in chunks if is_prose(c.text, c.effective_kind)]
    return _diversify(prose or chunks, k)


def sample(n: int = 5) -> list[Chunk]:
    """Random chunks, used by the quiz agent's 'random topic' mode."""
    import random

    data = _store().get(include=["documents", "metadatas"])
    idx = random.sample(range(len(data["ids"])), k=min(n, len(data["ids"])))
    return [
        Chunk(text=data["documents"][i], source=data["metadatas"][i]["source"],
              page=int(data["metadatas"][i]["page"]), score=0.0,
              kind=data["metadatas"][i].get("kind"))
        for i in idx
    ]


def count() -> int:
    """Number of chunks in the collection, shown by the health endpoint."""
    return _store()._collection.count()


def sources() -> list[str]:
    """Distinct document names currently in the knowledge base."""
    data = _store().get(include=["metadatas"])
    return sorted({m["source"] for m in data["metadatas"]})
