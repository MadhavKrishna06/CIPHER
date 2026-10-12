"""Embedding similarity, used to score how close a student answer is to the reference.

The grader needs a measure that does not come from the language model judging its
own output. Cosine similarity between two embeddings is deterministic, carries no
prompt, and so cannot be talked out of its verdict by text inside the answer.

The embedding model here is the same one that built the vector database, so the
notion of "close" matches what retrieval already uses.
"""

from __future__ import annotations

import math
from functools import lru_cache

from langchain_ollama import OllamaEmbeddings

from .config import EMBED_MODEL, OLLAMA_HOST


@lru_cache(maxsize=1)
def _embedder() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_HOST)


def embed(text: str) -> list[float]:
    return _embedder().embed_query(text)


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine of the angle between two vectors, in [-1, 1]. 1 means identical direction."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def text_similarity(a: str, b: str) -> float:
    """Cosine similarity of two strings. Two embedding calls, no LLM."""
    if not a.strip() or not b.strip():
        return 0.0
    return cosine(embed(a), embed(b))
