"""Similarity search over the local Chroma knowledge base."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from langchain_chroma import Chroma

from .ingest import get_vectorstore


@dataclass
class Chunk:
    text: str
    source: str   # file name, e.g. "Lecture 2_slides.pdf"
    page: int     # 1-based page / slide
    score: float  # distance; lower = closer

    @property
    def citation(self) -> str:
        kind = "slide" if self.source.lower().endswith((".pdf", ".pptx")) else "page"
        return f"{self.source}, {kind} {self.page}"


@lru_cache(maxsize=1)
def _store() -> Chroma:
    return get_vectorstore()


def retrieve(question: str, k: int = 5, max_distance: float | None = None) -> list[Chunk]:
    """Return the k chunks closest to the question, optionally dropping weak matches."""
    hits = _store().similarity_search_with_score(question, k=k)
    chunks = [
        Chunk(text=doc.page_content, source=doc.metadata["source"], page=int(doc.metadata["page"]), score=float(score))
        for doc, score in hits
    ]
    if max_distance is not None:
        chunks = [c for c in chunks if c.score <= max_distance]
    return chunks


def sample(n: int = 5) -> list[Chunk]:
    """Random chunks, used by the quiz agent's 'random topic' mode."""
    import random

    data = _store().get(include=["documents", "metadatas"])
    idx = random.sample(range(len(data["ids"])), k=min(n, len(data["ids"])))
    return [
        Chunk(text=data["documents"][i], source=data["metadatas"][i]["source"], page=int(data["metadatas"][i]["page"]), score=0.0)
        for i in idx
    ]


def sources() -> list[str]:
    """Distinct document names currently in the knowledge base."""
    data = _store().get(include=["metadatas"])
    return sorted({m["source"] for m in data["metadatas"]})
